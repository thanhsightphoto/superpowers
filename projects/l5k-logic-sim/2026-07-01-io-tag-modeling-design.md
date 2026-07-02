# Design — Forgiving I/O / module-tag modeling (coverage sub-project 3)

Date: 2026-07-01
Status: Approved (design); implementation plan to follow
Branch: `project/l5k-logic-sim`

## Problem

A full-controller scan of the real `briles_main_rev_023.L5K` still degrades on the
**physical I/O boundary** — member/index access on tags the simulator can't model:

- **Colon I/O module tags** (`Local:4:I.Data[1]`, `Remote_Slot0_AENT:3:I.Ch0Data`)
  — 177 occurrences. These are not declared as tags; they come from the module
  I/O tree. `_container_for` auto-creates the base as scalar `0`, so `.Data[1]`
  raises `'int' object is not subscriptable`.
- **Module-defined / built-in-typed tags** — ~46 tags declared with types absent
  from the L5K `DATATYPE` section: `REDUNDANT_INPUT` (26), `REDUNDANT_OUTPUT` (6),
  `AXIS_CIP_DRIVE`/`MOTION_GROUP`/`MOTION_INSTRUCTION`, `EMERGENCY_STOP`,
  `TWO_HAND_RUN_STATION`, `DIVERSE_INPUT`, `SCALE`, `FBD_MATH`. `_init_type`
  returns scalar `0` for these unknown types, so member access (`.O1`, `.BP`,
  `.ActualPosition`) fails the same way.

We do not have the Rockwell member layouts for these types, and hardcoding dozens
of them would be large, brittle, and low-value: in an offline simulator these are
the physical I/O boundary — external stimulus the operator forces, not values the
logic computes.

## Decision

Model boundary tags as **forgiving, auto-vivifying, forceable structures**. A
boundary tag returns `0`/`False` defaults for any member/index/bit access and
holds any value written or forced to a given sub-path. **Known UDT/AOI/array tags
remain strict**, preserving the debuggability of real control logic (a genuine
UDT member typo still surfaces). No hardcoded Rockwell type layouts.

Boundary tags are:
1. Declared tags whose data type is not modeled (not scalar / UDT / AOI / TIMER /
   COUNTER / array-of-those) — i.e. the current `_init_type` "unknown type"
   fallback.
2. Undeclared bases auto-created during resolution (the colon I/O tags).

## Components (all in `src/l5k_sim/tagdb.py`)

### 1. `IOStub` marker type

```python
class IOStub(dict):
    """Forgiving store for an unmodeled I/O / module-defined tag.
    Keys are canonical sub-path strings; missing keys read as defaults."""
```

A `dict` subclass so it is easy to detect via `isinstance` and to store
sub-path → value entries.

### 2. Initialization

- `_init_type`: change the final unknown-type fallback from `return 0` to
  `return IOStub()`.
- `_container_for`: change the auto-create of an undeclared base from
  `prog[base] = 0` to `prog[base] = IOStub()`.

### 3. Canonical sub-path key

A helper `_canon(path)` reconstructs a stable string from the typed segments
(`Index`, `Bit`, member-`str`) produced by `parse_ref`:

- member `str` → `.name` (leading dot dropped for the first segment)
- `Index(i)` → `[i]`
- `Bit(n)` → `.n`

e.g. `("Data", Index(1))` → `"Data[1]"`; `("Data", Bit(5))` → `"Data.5"`;
`("O1",)` → `"O1"`. Read and write of the same operand produce the same key.

### 4. Forgiving read / write

In `read`, immediately after resolving `val = container[ref.base]`:

```python
        if isinstance(val, IOStub):
            if not ref.path:
                return 0
            default = False if isinstance(ref.path[-1], Bit) else 0
            return val.get(_canon(ref.path), default)
```

In `write`, after resolving the container:

```python
        base_val = container[ref.base]
        if isinstance(base_val, IOStub):
            if not ref.path:
                container[ref.base] = value
            else:
                base_val[_canon(ref.path)] = value
            return
```

The existing strict walk (for real dicts/lists) is unchanged and only runs for
non-`IOStub` values. `force` already routes through `write`, so boundary tags are
forceable.

## Data flow

`from_project` initializes unmodeled-type tags as `IOStub`; `_container_for`
creates colon I/O bases as `IOStub` on first access. At scan time, reads of
boundary tags return forceable defaults (no diagnostic), and writes/forces store
per-sub-path values that read back. Logic downstream of I/O computes with a real
(forceable) value instead of skipping the instruction.

## Error handling

- Boundary reads never raise and, by design, do not append a diagnostic (these are
  expected external I/O, previously the dominant diagnostic source).
- The strict path for known tags is unchanged: genuine member/index errors on real
  UDT/array tags still surface via the existing per-instruction isolation.

## Testing strategy

TDD, one failing test per behavior (in `tests/test_tagdb.py`):

- An unmodeled-type declared tag (e.g. `REDUNDANT_OUTPUT`) initializes as an
  `IOStub`; reading `.O1` returns `0` (no raise); writing `.O1 = True` reads back
  `True`.
- A colon I/O base (`Local:4:I`) auto-creates as an `IOStub`; `Local:4:I.Data[1]`
  reads `0`; forcing it reads back the forced value.
- A bit sub-path (`Local:1:I.Data.5`) reads `False` by default and holds a written
  `True`.
- A bare undeclared read still returns `0` (empty-path IOStub behavior preserved).
- A known UDT tag is unaffected (strict access still works; not an `IOStub`).
- **Guarded real-file regression**: a full scan of every program produces no
  `'int' object is not subscriptable` / `does not support item assignment`
  diagnostics, and does not crash.

The full suite (currently 140 passing) must stay green.

## Known limitations (documented, deferred)

- Word/bit coherence within a boundary tag is not modeled (a bit sub-path and its
  parent word are independent flat keys) — acceptable for forced I/O.
- The niche instructions that operate on these tags (`RIN`, `ESTOP`, `ROUT`,
  `THRS`, `GSV`, `SSV`, `DTOS`, `MAH`) remain safe "unsupported instruction"
  no-ops; implementing their semantics is separate, lower-value work.
- No hardcoded Rockwell member layouts; boundary tags carry no predefined members.
