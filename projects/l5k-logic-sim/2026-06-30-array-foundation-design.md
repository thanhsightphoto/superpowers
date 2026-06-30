# Design — Array-tag foundation (array addressing, sub-project 1)

Date: 2026-06-30
Status: Approved (design); implementation plan to follow
Branch: `project/l5k-logic-sim`

## Problem

443 unique operands across the real `briles_main_rev_023.L5K` use `[i]` bracket
indexing (623 occurrences). None resolve today: `parse_ref` has no bracket
support, so `Cam_Cut_Dwell_Select[0]` is treated as an unknown base, auto-creates
a scalar `0`, and silently reads `0`. This is a **fidelity** gap, not a crash —
array-backed rungs compute against zeros instead of real values.

Operand shapes in the real file:

| Count | Shape | Example |
|------:|-------|---------|
| 234 | array element + member/bit | `interface.system[0].manual_prime`, `FAULT_TEST_DINT[0].10` |
| 193 | simple `tag[i]`, constant index | `Cam_Cut_Dwell_Select[0]`, `FAULTS2[28]` |
| 11 | member array `tag.arr[i]` | `Local:3:I.Data[3]` (I/O module) |
| 5 | variable index | `FAULTS2[FAULT_BIT_CTR]` |

Top-level array tags carry aggregate initializers that are not parsed today:

```
Cam_Cut_Dwell_Select : INT[12]  := [0,0,0,0,0,0,0,0,0,0,2,0]
FAULTS2              : BOOL[128] := [2#0,2#0,2#0, ...]   (2# binary literals)
```

This sub-project is the **foundation** of a three-part array-addressing effort.
It builds the general addressing mechanism and covers scalar-element arrays.
Sub-project 2 (array-of-UDT members) and sub-project 3 (variable index) build on
it and are out of scope here.

## Decisions

1. **Centralize addressing.** Extend `parse_ref` to emit typed path segments and
   make `tagdb.read`/`write` walk them generically. Rejected alternatives:
   pre-expanding arrays into flat keys (`tag[0]`, `tag[1]`) — breaks whole-array
   `MOVE`, bloats the DB, does not compose with members; and special-casing
   indices inside each instruction handler — scatters addressing logic. A typed
   walk keeps all addressing in `values.py` + `tagdb.py`.

2. **Scope: scalar-element arrays only** (BOOL / INT / DINT / SINT / REAL),
   including bit-after-index (`FAULT_TEST_DINT[0].10`). UDT-element array member
   access and variable/runtime index resolution parse *structurally* in this
   sub-project but resolve later (sub-projects 2 and 3). The mechanism is
   general; only initialization fidelity and variable-index resolution are
   deferred.

## Components

### 1. `src/l5k_sim/values.py` — literals and ref tokenizer

**Binary literals.** Add `2#` support so array initializers parse:

- `is_literal`: also match `^2#[01][01_]*$`.
- `parse_literal`: `int(t[2:].replace("_", ""), 2)` for the `2#` form.

**Typed path segments.** Introduce two frozen dataclasses plus a variable-index
marker, all in `values.py`:

```python
@dataclass(frozen=True)
class Index:
    i: int          # constant array index, e.g. [3]

@dataclass(frozen=True)
class Bit:
    n: int          # numeric bit access, e.g. .5

@dataclass(frozen=True)
class VarIndex:
    name: str       # non-constant index, e.g. [FAULT_BIT_CTR]; resolved in sub-project 3
```

A `str` path element continues to mean a struct member.

**`parse_ref` rewrite.** Tokenize a full operand into `Ref(base, path)` where
`path` is a tuple of `Index` / `Bit` / `VarIndex` / `str`:

- The base is the leading identifier, which may contain `:` (I/O names like
  `Local:3:I` stay intact as the base string).
- `[N]` where `N` is all digits → `Index(int(N))`; otherwise → `VarIndex(N)`.
- `.N` where `N` is all digits → `Bit(int(N))`.
- `.name` → `name` (str member).

Ref stays `@dataclass(frozen=True)` with `base: str` and
`path: tuple[Index | Bit | VarIndex | str, ...]`.

### 2. `src/l5k_sim/tagdb.py` — array init and generic walk

**Array initialization.** `_init_type` recognizes an array type string `TYPE[N]`:
parse the element type (before `[`) and dimension `N`, and return a list of `N`
values, each initialized via `_init_type(element_type, None)`.

**Aggregate-initializer parsing.** A new helper parses an aggregate literal
`[v0,v1,...]` for scalar element arrays:

- Strip the outer brackets; split on top-level commas using `split_top_level`
  from `scan.py`.
- Parse each element with `parse_literal` (now including `2#`).
- Assign element `i` to slot `i`; if the initializer is shorter than `N`, pad the
  remaining slots with the element default; if longer, ignore the overflow and
  append a diagnostic.
- Used when a tag's `data_type` is `TYPE[N]` and its `initial` is an aggregate.

**Generic read/write walk.** Replace the path walk in `read` and `write` with a
typed walk:

- `Index(i)` → descend into list element `i`.
- `str` member → descend into dict member.
- `Bit(n)` → terminal bit access. On read, return `bool((int(val) >> n) & 1)`.
  On write, set/clear bit `n` of the holding element and store the new integer
  back into its parent container (dict member or list slot).
- Empty path → whole value (so `MOVE` of a whole array reads/writes the list).
- Out-of-range `Index` or any `VarIndex` → append a diagnostic and degrade (read
  returns the element/scalar default; write is a no-op). Never raise.

### 3. Instructions

No changes. Handlers resolve operands through `engine._operand` → `db.read`, so
indexing is transparent once the walk supports it.

## Data flow

`parse_l5k` produces tags whose `data_type` may be `TYPE[N]` →
`TagDatabase.from_project` initializes those as lists (with aggregate initializers
applied) → at scan time, `engine._operand` calls `db.read(scope, operand)` →
`parse_ref` tokenizes the operand into typed segments → `read`/`write` walk the
segments through the nested list/dict structure.

## Error handling

- Out-of-range array index → diagnostic appended to `engine.diagnostics` (via the
  same degrade path used today); read returns the element default, write no-ops.
- `VarIndex` (variable index) → treated as unresolved in this sub-project:
  diagnostic + degrade. Full resolution is sub-project 3.
- Malformed aggregate initializer (non-literal element, unbalanced brackets) →
  skip that element / pad with default, append a diagnostic; never raise.

## Testing strategy

TDD, one failing test first per behavior.

- **values:** `2#` binary literal parses (`2#0`→0, `2#1011`→11); `parse_ref`
  tokenizes `tag[0]` → `Index(0)`, `tag[3].10` → `(Index(3), Bit(10))`,
  `tag.member[2]` → `("member", Index(2))`, `tag[FAULT_BIT_CTR]` →
  `(VarIndex("FAULT_BIT_CTR"),)`.
- **tagdb:** an `INT[12]` tag initializes to a 12-element list of `0`; the
  aggregate initializer `[0,0,0,0,0,0,0,0,0,0,2,0]` puts `2` at index 10; a
  `BOOL` array with `2#` binary initializer populates correctly; `arr[i]`
  read/write round-trips; `arr[i].n` bit read/write round-trips; whole-array read
  (no index) returns the list; out-of-range index degrades with a diagnostic and
  does not raise.
- **Regression (guarded by `skipif` on the local Briles path):** after parsing the
  real file, `Cam_Cut_Dwell_Select[10]` reads `2`; running scans produces no new
  exceptions.

The full suite (currently 97 passing) must stay green.

## Known limitations (documented, deferred)

- UDT-element arrays (`interface.system[0].manual_prime`) parse structurally but
  their initialization fidelity and member-after-index resolution are sub-project
  2.
- Variable/runtime index (`FAULTS2[FAULT_BIT_CTR]`) parses to `VarIndex` but is
  not resolved here — sub-project 3.
- I/O-module colon-base tags (`Local:3:I.Data[3]`) are not modeled as real I/O;
  they degrade as before.
- Multi-dimensional arrays (`a[i][j]`) are not present in the target file and are
  out of scope.
