# Design — AOI invocation (Add-On Instruction execution, sub-project 3)

Date: 2026-07-01
Status: Approved (design); implementation plan to follow
Branch: `project/l5k-logic-sim`

## Problem

The real `briles_main_rev_023.L5K` calls Add-On Instructions (AOIs) at 37 sites
(`MisFeed`×16, `Scroll`×10, `SCP`×2, `scaler_dint`, `min_dint`, `max_dint`,
`aoi_pulse_feedback_monitoring`×3, `Pulse_Angle`×2, `EncoderPuls_to_RPM`). Today
each is an "unsupported instruction" that no-ops, so the real computations they
perform — scaling, clamping, angle conversion, RPM — never happen, and every
value downstream of an AOI stays at its default.

Sub-project 2 made AOI-instance tags initialize as structured member dicts, which
is the prerequisite for executing them. This sub-project executes the calls.

## Findings (verified against the real file)

- **Call syntax:** `AOI(instance, arg1, …, argN)`. The first operand is the
  instance backing tag; the remaining operands map positionally to the AOI's
  **call parameters** — parameters with `usage in (Input, Output, InOut)`,
  excluding `EnableIn`/`EnableOut`, in declaration order. Local tags (no `usage`)
  are internal state, not passed in the call.
- **Verified clean bindings:** `scaler_dint` (6 args = 6 call params), `max_dint`
  (3=3), `EncoderPuls_to_RPM` (5=5), `Scroll` (7=7).
- **Logic is executable with the current instruction set.** Across all called
  AOIs, the only unsupported instruction in any Logic routine is `RTO`
  (retentive timer), used solely by `aoi_pulse_feedback_monitoring`.
- **One binding edge:** `MisFeed` presents 12 call arguments against 13 expected
  call parameters (an off-by-one from an optional/hidden parameter), so its
  binding is ambiguous and must not be guessed.

## Decisions

1. **Skip on argument/parameter count mismatch.** If the number of call arguments
   does not equal the number of call parameters, append a diagnostic and skip
   execution. Never guess-bind — a wrong binding produces wrong values, which is
   worse than a no-op. This safely defers `MisFeed` until a follow-up.

2. **InOut parameters use copy-in / copy-out.** Logix InOut parameters are
   by-reference aliases; in this single-threaded scan model, copying the argument
   value into the instance member before Logic and back out after is
   behaviorally equivalent. This covers `Scroll`'s `PositionIndex` (a BOOL array).

3. **Execute Logic only when enabled.** Run the AOI Logic routine when the rung
   delivers power (`EnableIn` true). When power is false, set `EnableOut` false,
   skip Logic, and leave outputs holding their prior values.

4. **Execution only — no AOI-internal UI visualization.** Correct output values
   flow back to the caller's tags, which the existing ladder view already
   animates. Rendering the inside of AOI Logic is out of scope.

## Components

### 1. AOI invocation handler — `src/l5k_sim/engine.py` (+ registration)

A single `invoke_aoi(scope, instr, power_in)` path, registered for every AOI
name known from `project.controller.aois`:

1. Look up the `AOIDef` by `instr.mnemonic`.
2. Resolve the instance dict: `inst = db.read(scope, instr.operands[0])`. If it is
   not a dict, append a diagnostic and return `power_in`.
3. Compute call parameters: `[p for p in aoi.parameters if p.usage in ("Input",
   "Output", "InOut") and p.name not in ("EnableIn", "EnableOut")]`.
4. `args = instr.operands[1:]`. If `len(args) != len(call_params)`, append a
   diagnostic and return `power_in`.
5. Bind inputs: for each `(param, arg)`, if `param.usage in ("Input", "InOut")`,
   set `inst[param.name] = self._operand(scope, arg)`. Set `inst["EnableIn"] =
   bool(power_in)` when that member exists.
6. If `power_in`: execute the AOI's Logic routine against the instance as scope
   (see §2). Set `inst["EnableOut"] = bool(power_in)` when present. If not
   `power_in`: set `EnableOut` false and skip Logic.
7. Copy back: for each `(param, arg)`, if `param.usage in ("Output", "InOut")`,
   `db.write(scope, arg, inst[param.name])`.
8. Return `power_in` (the rung continues; AOI is a bit-transparent block).

### 2. Executing Logic against the instance scope — `src/l5k_sim/engine.py` + `src/l5k_sim/tagdb.py`

The AOI Logic routine's operands (`in`, `out_min`, `out`, locals) resolve against
the instance dict. Register the instance dict as a temporary scope so the
existing rung evaluator can run unchanged:

- Bind a synthetic scope key (e.g. `f"__aoi__/{instr.mnemonic}"`) in
  `db.programs` pointing at the *same* instance dict object, so Logic writes
  mutate the instance in place.
- Evaluate each Logic rung with the existing `eval_elements` against that scope
  key. Element-id trace keys under the synthetic scope are harmless (the UI does
  not render them).
- Nested AOI calls are not expected in the target file and are out of scope.

`TagDatabase._container_for` already resolves a base name against the current
scope's dict, so instance-member operands resolve without changes.

### 3. Registration — `src/l5k_sim/engine.py`

At engine construction, build a set of AOI names from `project.controller.aois`.
`_eval_instruction` routes any instruction whose mnemonic is an AOI name to
`invoke_aoi` (before the "unsupported instruction" fallback). AOI names never
collide with built-in mnemonics.

## Data flow

Scan reaches an AOI call rung → `invoke_aoi` binds arguments into the instance
dict → the AOI Logic routine runs against the instance and computes outputs →
outputs are copied back to the caller's argument tags → subsequent rungs (and the
ladder view) see the real computed values.

## Error handling

- Argument/parameter count mismatch → diagnostic, skip (`MisFeed`).
- Instance operand not a dict / missing → diagnostic, skip.
- Unsupported instruction inside Logic (`RTO`) → the existing per-instruction
  isolation records a diagnostic and continues, so the rest of the AOI still
  runs.
- Any exception during binding or execution is contained by the existing
  per-instruction try/except; a single bad AOI call never crashes the scan.

## Testing strategy

TDD, one failing test per behavior.

- **Binding:** a call binds its positional arguments to the right instance
  members, skipping `EnableIn`/`EnableOut` and locals.
- **Logic execution:** a `scaler`-style AOI (MOVE + CPT with an expression)
  computes the correct `out` from bound inputs.
- **Copy-back:** Output parameters are written back to the call's argument tags.
- **Disabled:** with no rung power, Logic does not run and outputs hold.
- **Count mismatch:** a call with the wrong argument count appends a diagnostic
  and does not execute.
- **Guarded real-file regression** (`skipif` on the local Briles path): after
  scanning, a `max_dint`/`scaler_dint` chain in `Lower_KO_Valve_Adapter` produces
  a correct non-default `magnitude`/`speed_floored`, and the scan does not crash.

The full suite (currently 115 passing) must stay green.

## Known limitations (documented, deferred)

- The `RTO` instruction is not implemented; `aoi_pulse_feedback_monitoring`'s
  retentive-timer rung degrades to a diagnostic (the rest of that AOI still runs).
- `MisFeed`'s off-by-one argument/parameter binding is unresolved; its 16 call
  sites skip with a diagnostic.
- AOI-internal ladder visualization is not provided (execution only).
- Nested AOI-within-AOI calls are out of scope (not present in the target file).
