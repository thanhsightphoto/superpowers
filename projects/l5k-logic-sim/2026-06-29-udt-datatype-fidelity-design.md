# Design — UDT DATATYPE-grammar fidelity

Date: 2026-06-29
Status: Approved (design); implementation plan to follow
Branch: `project/l5k-logic-sim`

## Problem

The engine runs the real `briles_main_rev_023.L5K` without crashing, but six
instructions in scope `Lower_KO_Valve_Adapter` silently no-op every scan because
member reads/writes raise `KeyError`:

```
XIC  interface.out_lower_ko_ext            -> KeyError('out_lower_ko_ext')
XIC  interface.out_lower_ko_ret            -> KeyError('out_lower_ko_ret')
MOVE interface.lower_ko_speed_pct  ...     -> KeyError('lower_ko_speed_pct')
MOVE interface.lower_ko_valve_monitor ...  -> KeyError('lower_ko_valve_monitor')
MOVE interface.lower_ko_valve_stiction_tolerance ...   -> KeyError
MOVE interface.lower_ko_valve_stiction_timeout_ms ...  -> KeyError
```

The handoff attributed this to "uninitialized nested/InOut UDT members." That is
wrong. The real cause is a **DATATYPE grammar parser bug**.

### Root cause

Real Logix writes DATATYPE members **type-first**:

```
DATATYPE FaultRecord (FamilyType := NoFamily)
    DINT TimeLow;                                          -- plain member
    DINT Info[8] (Radix := Hex);                           -- array member
    SINT ZZZZZZZZZZspecial_mo9 (Hidden := 1);              -- hidden host word
    BIT out_lower_ko_ext ZZZZZZZZZZspecial_mo9 : 6 (...);  -- bit overlay on host bit 6
END_DATATYPE
```

But `_build_datatype` (`src/l5k_sim/l5k_parser.py`) only understands a fictional
`name : TYPE` grammar that the synthetic `tests/fixtures/mode1.L5K` invented.
The parser was built and tested against that fake grammar. Against the real
file:

- **Plain members** (`DINT TimeLow`) have no ` : ` separator, so they are
  silently dropped. Four datatypes (`FaultRecord`, `if_lubrication`, `if_tdc`,
  `Scroll_Bool`) lost **every** member.
- **Bit overlays** parse but garbled: member name becomes
  `"BIT out_lower_ko_ext ZZZZZZZZZZspecial_mo9"`, type becomes `"6"`.

So `interface.out_lower_ko_ext` and friends are never present in the tag DB
dict, and the instruction handler raises `KeyError`, which the engine catches
into a diagnostic and no-ops.

Member-kind census across all 13 real datatypes: 167 plain, 84 bit-overlay, 3
array members. The grammar fix covers ~250 of 254 members.

## Decisions

1. **Bit-overlay representation: independent booleans.** Each named BIT member
   is its own boolean key in the UDT instance dict
   (`interface["out_lower_ko_ext"] = False`). The hidden host words are kept as
   their own integer members so any stray word reference resolves, but bit and
   word are **not** kept coherent. Rationale: logic always references the
   friendly bit name, never the `Hidden := 1` host by name; the generic dict
   walker in `tagdb` stays simple; all by-name logic works correctly.

2. **Scope: DATATYPE grammar only.** Rewrite the member parser, evolve the IR
   member model, and initialize all member kinds. Scalar array members are
   initialized as lists (existence only). Explicitly **out of scope**: `[i]`
   bracket-index operand addressing (441 operands across the file, e.g.
   `interface.system[0].manual_prime`, `cycle_time_timer[2]`), array-of-UDT
   element resolution, the `max_dint`/`scaler_dint` AOI-call instructions, and
   the `ABS` instruction. Those are separate follow-up work.

## Components

### 1. IR member model — `src/l5k_sim/ir.py`

Replace `DataType.members: list[tuple[str, str]]` with a `Member` dataclass:

```python
@dataclass
class Member:
    name: str
    data_type: str            # "DINT" | "BOOL" | "BIT" | UDT name | ...
    dim: int | None = None    # array length: Info[8] -> 8
    bit_host: str | None = None   # bit overlay: backing member name
    bit_pos: int | None = None    # bit overlay: bit index within host
```

`DataType.members` becomes `list[Member]`. Update `project_to_dict` /
`project_from_dict` serialization to the new shape (a member dict carrying the
five fields; absent optional fields serialize as null).

### 2. DATATYPE parser — `src/l5k_sim/l5k_parser._build_datatype`

For each member line (one statement terminated by `;`):

1. Drop the trailing `;`.
2. Strip the outer `(attrs)` group if present, locating it with the existing
   `find_matching` helper from `scan.py` (attrs may themselves contain `:=` and
   nested parens).
3. Classify:
   - Starts with `BIT ` **and** the remaining text contains a top-level `:` →
     overlay. Grammar `BIT <name> <host> : <bitpos>`. Produce
     `Member(name, "BIT", bit_host=host, bit_pos=int(bitpos))`.
   - Otherwise type-first `<TYPE> <name>[dim]?`. First whitespace token is the
     type; the remainder is the member name, which may carry a `[N]` array
     dimension. Produce `Member(name, TYPE, dim=N or None)`.

Hidden host words (`SINT ZZZ... (Hidden := 1)`) fall through the type-first
branch as ordinary plain members and are kept.

### 3. Tag DB init — `src/l5k_sim/tagdb`

When instantiating a UDT value, iterate its `Member`s:

- Bit-overlay member → its own `False` key (independent bool).
- Plain scalar member → recurse via `_init_type` on its `data_type`; add a new
  case so `BIT` initializes to `False`.
- Array member (`dim` set) → a list of `dim` initialized element values of the
  member's element type.
- Existing TIMER / COUNTER / nested-UDT recursion is preserved.

`_init_type` continues to take an optional `initial`; UDT members carry no
per-member initial (tag-level aggregate initializers are not decomposed — see
Known limitations).

### 4. Fixtures and tests

- Rewrite the DATATYPE block in `tests/fixtures/mode1.L5K` to **real**
  type-first grammar, including at least one real BIT overlay backed by a hidden
  host word, so the fixture stops teaching a fictional grammar.
- Migrate the unit tests that build `DataType` with `(name, type)` tuples
  (`tests/test_ir.py`, `tests/test_tagdb.py`) to construct `Member` objects.
- The existing `tests/test_l5k_parser.py::test_datatype_and_controller_tag`
  only asserts a datatype name exists; extend it to assert real member parsing.

## Data flow

`parse_l5k` → `_build_datatype` produces `DataType(name, [Member, ...])` →
`TagDatabase.from_project` walks each tag's type, and for UDT-typed tags builds
a nested dict whose keys are member names (bit members as bools, scalars by
type, arrays as lists) → `engine` read/write resolve `tag.member` paths against
that dict exactly as today.

## Error handling

- A member line that matches neither branch (malformed) is skipped and a
  diagnostic is appended to the project diagnostics, mirroring existing
  best-effort parsing. The parser never raises on a single bad member.
- Unknown member types continue to fall back to the existing scalar default in
  `_init_type` so initialization never raises.

## Testing strategy

TDD, one failing test first per behavior:

- **Parser:** plain type-first member; array member dimension; bit-overlay
  name/host/bit; hidden host retained; a datatype that previously parsed to zero
  members now populated.
- **Tag DB:** UDT with bit members initializes them as independent bools;
  read/write `tag.bitmember` round-trips; array member is a list of the right
  length; nested UDT still initializes.
- **Regression (guarded):** parse the real Briles file (skip via `skipif` when
  the local git-ignored path is absent), run five scans, assert none of the six
  `interface.*` `KeyError` diagnostics appear.

Full suite (currently 92 passing) must stay green.

## Known limitations (documented, not addressed here)

- Bit/word non-coherence: writing a bit member does not update the hidden host
  word and vice versa (independent-bools model).
- Tag-level aggregate initializers (e.g. `[3,0,0,100]`) are still not
  decomposed into member values.
- `[i]` operand indexing and array-of-UDT element addressing remain deferred
  (the 441 bracketed operands).
- AOI-call instructions (`max_dint`, `scaler_dint`, etc.) and `ABS` remain
  unsupported — separate instruction-coverage work.
