# Design — Core instruction pack (coverage sub-project 1)

Date: 2026-07-01
Status: Approved (design); implementation plan to follow
Branch: `project/l5k-logic-sim`

## Problem

A full-controller scan of the real `briles_main_rev_023.L5K` (all 9 programs) still
reports a tail of unsupported instructions. Eight of them have clean, standard
Logix semantics and fit the existing instruction-handler pattern; implementing
them removes real degradation across programs and provides `RTO`, which the last
unrun AOI (`aoi_pulse_feedback_monitoring`) needs.

Unsupported-instruction inventory (all programs + AOI Logic), clean tier:

| Instr | Count | Meaning |
|-------|------:|---------|
| CLR   | 7 | clear destination to 0 |
| RTO   | 6 | retentive on-timer |
| DTOS  | 6 | (deferred — string) |
| TOF   | 3 | off-delay timer |
| COP   | 2 | array copy |
| ABS   | 1 | absolute value |
| MOD   | 1 | modulo |
| NEG   | 1 | negate |
| CTD   | 1 | count down |

This sub-project implements `CLR`, `ABS`, `NEG`, `MOD`, `COP`, `CTD`, `TOF`, `RTO`.

## Decisions

1. **Pure handler additions.** All eight are added to
   `src/l5k_sim/instructions.py` via the existing `@register(...)` / `HANDLERS`
   mechanism. No engine or tag-DB changes.
2. **Timer/counter instructions follow the existing pattern.** `TON`/`CTU`/`RES`
   already read and write `<tag>.PRE/.ACC/.DN/...` from the tag's struct and
   ignore the `?` placeholder operands that L5K emits for PRE/ACC. `TOF`, `RTO`,
   and `CTD` do the same.
3. **Degrade, never crash.** Division/modulo by zero and out-of-range copies
   append a diagnostic (via the existing per-instruction isolation) and skip the
   write.
4. **Deferred:** `RET` (control-flow early return — more invasive, 2 sites) and
   the boundary/niche tier (`GSV`, `SSV`, `DTOS`, `MAH`, `RIN`, `ESTOP`, `ROUT`,
   `THRS`), which remain safe diagnostic no-ops until coverage sub-project 3
   (I/O-tag modeling) gives them real tags to act on.

## Components (all in `src/l5k_sim/instructions.py`)

Semantics (operands are resolved via `engine._operand`; writes via
`engine.db.write`):

- **`CLR(dest)`** — `write(dest, 0)`. Returns `power_in` (only acts when powered).
- **`ABS(src, dest)`** — when powered, `dest = abs(_operand(src))`.
- **`NEG(src, dest)`** — when powered, `dest = -_operand(src)`.
- **`MOD(a, b, dest)`** — when powered, with `a,b = _operand(a), _operand(b)`:
  if `b == 0`, append a diagnostic and skip; else `dest = a - b * int(a / b)`
  (truncation toward zero, matching Logix `MOD`).
- **`COP(src, dest, length)`** — when powered, copy `length` elements from array
  `src` to array `dest`: read the `src` list and `dest` list; for
  `i in range(length)`, if both indices are in range, `dest[i] =
  deepcopy(src[i])`. Out-of-range indices append a diagnostic and stop. `length`
  is resolved via `_operand` (may be a literal). Writes back the mutated `dest`
  list.
- **`CTD(counter, …)`** — count-down companion to `CTU`. Read
  `pre = counter.PRE`, `acc = counter.ACC`, `prev = counter.prev_cd`. On a
  false→true transition (`power_in and not prev`), `acc -= 1` and write
  `counter.ACC`. Always write `counter.prev_cd = power_in` and
  `counter.DN = acc >= pre`. (Mirrors the existing `CTU`, which uses `prev_cu`;
  the COUNTER struct already carries `CD` and `prev_cu` — add `prev_cd` handling
  analogous to `CTU`.) Returns the down-done state.
- **`TOF(timer, …)`** — off-delay timer, the inverse of `TON`. When powered:
  `EN=1, TT=0, DN=1, ACC=0`. When unpowered: `EN=0`; accumulate
  `ACC = min(PRE, ACC + scan_period_ms)`; `DN = ACC < PRE` (stays true while
  timing, false once elapsed); `TT = ACC < PRE`. Returns `DN`.
- **`RTO(timer, …)`** — retentive on-timer, like `TON` but `ACC` is **not**
  cleared when unpowered. When powered: `EN=1`; if not `DN`,
  `ACC = min(PRE, ACC + scan_period_ms)`; `DN = ACC >= PRE`; `TT = not DN`. When
  unpowered: `EN=0, TT=0`; `ACC` and `DN` **retain** their values. (`RES` already
  resets timer structs, so retention is releasable.) Returns `DN`.

## Data flow

Unchanged: the scan evaluator calls `_eval_instruction` → `HANDLERS[mnemonic]`.
These eight handlers now exist, so the corresponding rungs execute instead of
appending an "unsupported instruction" diagnostic.

## Error handling

- `MOD` by zero, `COP` bounds violations → diagnostic + skip the write; never
  raise (the engine's per-instruction try/except is the backstop regardless).
- Timer/counter handlers read struct members via the tag DB; a missing member
  is contained by the existing isolation.

## Testing strategy

TDD, one failing test per instruction (new `tests/test_engine_pack.py` or added
to `tests/test_engine_math.py` following existing patterns):

- `CLR` sets a value to 0 only when powered.
- `ABS`/`NEG` compute correctly for positive and negative inputs.
- `MOD` computes trunc-toward-zero modulo; `MOD` by zero degrades without writing.
- `COP` copies N elements between arrays and is copy-independent (mutating dest
  does not affect src); out-of-range length degrades.
- `CTD` decrements on a false→true edge and sets `DN` at/below preset.
- `TOF` holds `DN` true while powered and for `PRE` ms after power loss, then
  clears (uses `scan_period_ms`).
- `RTO` accumulates while powered and **retains** `ACC`/`DN` across a power loss;
  `RES` clears it.
- Guarded real-file regression: after a full scan of the program that uses these,
  none of the eight appear in the "unsupported instruction" diagnostics, and the
  scan does not crash.

The full suite (currently 122 passing) must stay green.

## Known limitations (documented, deferred)

- `RET` (early return from a routine) is not implemented (2 sites); routines
  continue evaluating all rungs.
- Boundary/niche instructions (`GSV`, `SSV`, `DTOS`, `MAH`, `RIN`, `ESTOP`,
  `ROUT`, `THRS`) remain safe diagnostic no-ops — addressed with I/O-tag modeling
  in coverage sub-project 3.
