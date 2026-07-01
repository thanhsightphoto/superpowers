# AOI Invocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute Add-On Instruction (AOI) calls — bind positional arguments to the instance's parameters, run the AOI's Logic routine against the instance, and copy outputs back to the caller — so real AOIs (`scaler_dint`, `max_dint`, `min_dint`, `SCP`, `Pulse_Angle`, `EncoderPuls_to_RPM`, `Scroll`) compute real values instead of no-opping.

**Architecture:** The engine gains an AOI registry (built from `project.controller.aois`) and an `invoke_aoi` path routed from `_eval_instruction` before the "unsupported instruction" fallback. `invoke_aoi` binds Input/InOut arguments into the instance dict, executes the AOI Logic routine with the instance registered as a temporary scope, then copies Output/InOut members back to the call arguments. Argument/parameter count mismatches skip with a diagnostic (never guess-bind).

**Tech Stack:** Python 3.11 (project venv at `.venv`), standard library only, pytest.

## Global Constraints

- Python baseline is **3.11**. Use `.venv/bin/python` — never the system `python3` (it is 3.9.6).
- Run all commands from `projects/l5k-logic-sim/`. The full suite is currently **115 passing**.
- Standard library only; zero third-party dependencies.
- Call parameters = AOI parameters with `usage in ("Input","Output","InOut")` minus `EnableIn`/`EnableOut`, in declaration order. Local tags (no usage) are internal state, not call parameters.
- Bind Input/InOut args in; copy Output/InOut members back. Run Logic only when the rung delivers power.
- Degrade, never crash: count mismatch, non-dict instance, or an unsupported instruction inside Logic → diagnostic, skip/continue, never raise.
- The real `briles_main_rev_023.L5K` is git-ignored customer data at `~/Downloads/briles_main_rev_023.L5K`; never commit it, and guard any test that reads it with `skipif` on its presence.
- Every commit must leave the full suite green.

---

### Task 1: AOI registry, routing, argument binding, count-mismatch skip

Recognize AOI-call instructions and bind their input arguments into the instance dict. Logic execution and copy-back come in Task 2.

**Files:**
- Modify: `src/l5k_sim/engine.py` (`__init__`, `_eval_instruction`, new `invoke_aoi`)
- Create: `tests/test_aoi.py`

**Interfaces:**
- Consumes: `AOIDef` (`.name`, `.parameters`, `.logic`) from `project.controller.aois`; AOI-instance tags already initialize as member dicts (Plan 6).
- Produces: `self._aois: dict[str, AOIDef]`; `invoke_aoi(self, scope, instr, power_in) -> bool`. Task 2 extends `invoke_aoi` with Logic execution and copy-back.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_aoi.py`:

```python
from l5k_sim.ir import (AOIDef, Controller, Instruction, Program, Project,
                        Routine, Rung, Tag)
from l5k_sim.engine import ScanEngine


def _aoi_dbl() -> AOIDef:
    # AOI "dbl": out := in * 2
    params = [
        Tag("EnableIn", "BOOL", "dbl", "Input", None, None),
        Tag("EnableOut", "BOOL", "dbl", "Output", None, None),
        Tag("in", "DINT", "dbl", "Input", None, None),
        Tag("out", "DINT", "dbl", "Output", None, None),
    ]
    logic = Routine("Logic", None, [
        Rung(0, None, [Instruction("CPT", ["out", "in*2"], "CPT(out,in*2)")], "CPT(out,in*2)"),
    ])
    return AOIDef("dbl", params, logic)


def _project() -> Project:
    prog_tags = [
        Tag("inst", "dbl", "P", None, None, None),
        Tag("src", "DINT", "P", None, "5", None),
        Tag("dst", "DINT", "P", None, "0", None),
    ]
    prog = Program("P", None, prog_tags, [])
    return Project(Controller("C", "x", [], [], [_aoi_dbl()], [prog]))


def _call(engine, power=True):
    instr = Instruction("dbl", ["inst", "src", "dst"], "dbl(inst,src,dst)")
    return engine._eval_instruction("P", instr, power)


def test_aoi_binds_input_args_to_instance():
    e = ScanEngine(_project())
    _call(e)
    assert e.db.read("P", "inst.in") == 5       # src value bound to param 'in'


def test_aoi_count_mismatch_skips_with_diagnostic():
    e = ScanEngine(_project())
    e._eval_instruction("P", Instruction("dbl", ["inst", "src"], "dbl(inst,src)"), True)
    assert any("dbl" in d and "args" in d for d in e.diagnostics)
    assert e.db.read("P", "inst.in") == 0        # nothing bound


def test_aoi_non_dict_instance_skips():
    proj = _project()
    proj.controller.programs[0].tags[0] = Tag("inst", "DINT", "P", None, "0", None)
    e = ScanEngine(proj)
    e._eval_instruction("P", Instruction("dbl", ["inst", "src", "dst"], "dbl(inst,src,dst)"), True)
    assert any("dbl" in d for d in e.diagnostics)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_aoi.py -v`
Expected: FAIL — `_eval_instruction` currently reports `dbl` as unsupported and does not bind anything, so `inst.in` stays `0`.

- [ ] **Step 3: Add the AOI registry, routing, and binding**

In `src/l5k_sim/engine.py`, add `AOIDef` to the `l5k_sim.ir` import:

```python
from l5k_sim.ir import AOIDef, Branch, Instruction, Program, Project, Routine, Rung
```

In `__init__`, build the AOI registry (next to `self._programs`):

```python
        self._aois: dict[str, AOIDef] = {a.name: a for a in project.controller.aois}
```

In `_eval_instruction`, route AOI names before the unsupported-instruction fallback. Replace the current body:

```python
    def _eval_instruction(self, scope: str, instr: Instruction, power_in: bool) -> bool:
        handler = _ins.HANDLERS.get(instr.mnemonic)
        if handler is None:
            if instr.mnemonic in self._aois:
                try:
                    return self.invoke_aoi(scope, instr, power_in)
                except Exception as exc:
                    self.diagnostics.append(f"AOI {instr.mnemonic} in {scope} raised: {exc}")
                    return power_in
            self.diagnostics.append(f"unsupported instruction {instr.mnemonic} in {scope}")
            return power_in
        try:
            return handler(self, scope, instr, power_in)
        except Exception as exc:
            self.diagnostics.append(f"instruction {instr.mnemonic} in {scope} raised: {exc}")
            return power_in
```

Add the `invoke_aoi` method (place it right after `_eval_instruction`). This task's version binds inputs and skips on mismatch; it does NOT yet run Logic or copy back:

```python
    def invoke_aoi(self, scope: str, instr: Instruction, power_in: bool) -> bool:
        aoi = self._aois[instr.mnemonic]
        inst = self.db.read(scope, instr.operands[0])
        if not isinstance(inst, dict):
            self.diagnostics.append(
                f"AOI {instr.mnemonic}: instance {instr.operands[0]} is not structured")
            return power_in
        call_params = [p for p in aoi.parameters
                       if p.usage in ("Input", "Output", "InOut")
                       and p.name not in ("EnableIn", "EnableOut")]
        args = instr.operands[1:]
        if len(args) != len(call_params):
            self.diagnostics.append(
                f"AOI {instr.mnemonic}: {len(args)} args vs {len(call_params)} params")
            return power_in
        for p, arg in zip(call_params, args):
            if p.usage in ("Input", "InOut"):
                inst[p.name] = self._operand(scope, arg)
        if "EnableIn" in inst:
            inst["EnableIn"] = bool(power_in)
        return power_in
```

- [ ] **Step 4: Run the tests, then the full suite**

Run: `.venv/bin/python -m pytest tests/test_aoi.py -v`
Expected: PASS (binding, count-mismatch skip, non-dict skip).

Run: `.venv/bin/python -m pytest -q`
Expected: `118 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/l5k_sim/engine.py tests/test_aoi.py
git commit -m "feat(l5k-sim): recognize AOI calls and bind input arguments"
```

---

### Task 2: Execute AOI Logic and copy outputs back

Complete `invoke_aoi`: run the AOI Logic routine against the instance as scope (when powered), set `EnableOut`, and copy Output/InOut members back to the call arguments.

**Files:**
- Modify: `src/l5k_sim/engine.py` (`invoke_aoi`)
- Modify: `tests/test_aoi.py`

**Interfaces:**
- Consumes: `invoke_aoi` binding from Task 1; the existing `eval_rung` / `_operand` and `TagDatabase._container_for` scope resolution.
- Produces: fully-executing AOI calls — Logic mutates the instance, outputs flow back to the caller.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_aoi.py`:

```python
def test_aoi_logic_computes_output_in_instance():
    e = ScanEngine(_project())
    _call(e)
    assert e.db.read("P", "inst.out") == 10      # CPT: out = in * 2 = 5 * 2


def test_aoi_copies_outputs_back_to_caller():
    e = ScanEngine(_project())
    _call(e)
    assert e.db.read("P", "dst") == 10           # 'out' copied back to the 'dst' argument


def test_aoi_disabled_does_not_run_logic():
    e = ScanEngine(_project())
    _call(e, power=False)
    assert e.db.read("P", "inst.out") == 0       # Logic skipped when unpowered
    assert e.db.read("P", "dst") == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_aoi.py::test_aoi_logic_computes_output_in_instance tests/test_aoi.py::test_aoi_copies_outputs_back_to_caller tests/test_aoi.py::test_aoi_disabled_does_not_run_logic -v`
Expected: FAIL — Task 1's `invoke_aoi` does not run Logic or copy back, so `inst.out` and `dst` stay `0`.

- [ ] **Step 3: Complete `invoke_aoi`**

In `src/l5k_sim/engine.py`, replace the Task 1 `invoke_aoi` body with the full version (adds Logic execution, `EnableOut`, and copy-back):

```python
    def invoke_aoi(self, scope: str, instr: Instruction, power_in: bool) -> bool:
        aoi = self._aois[instr.mnemonic]
        inst = self.db.read(scope, instr.operands[0])
        if not isinstance(inst, dict):
            self.diagnostics.append(
                f"AOI {instr.mnemonic}: instance {instr.operands[0]} is not structured")
            return power_in
        call_params = [p for p in aoi.parameters
                       if p.usage in ("Input", "Output", "InOut")
                       and p.name not in ("EnableIn", "EnableOut")]
        args = instr.operands[1:]
        if len(args) != len(call_params):
            self.diagnostics.append(
                f"AOI {instr.mnemonic}: {len(args)} args vs {len(call_params)} params")
            return power_in
        for p, arg in zip(call_params, args):
            if p.usage in ("Input", "InOut"):
                inst[p.name] = self._operand(scope, arg)
        if "EnableIn" in inst:
            inst["EnableIn"] = bool(power_in)
        if power_in and aoi.logic is not None:
            key = f"__aoi__/{instr.mnemonic}"
            self.db.programs[key] = inst
            try:
                for rung in aoi.logic.rungs:
                    self.eval_rung(key, rung, aoi.logic.name)
            finally:
                self.db.programs.pop(key, None)
        if "EnableOut" in inst:
            inst["EnableOut"] = bool(power_in)
        for p, arg in zip(call_params, args):
            if p.usage in ("Output", "InOut"):
                self.db.write(scope, arg, inst[p.name])
        return power_in
```

- [ ] **Step 4: Run the tests, then the full suite**

Run: `.venv/bin/python -m pytest tests/test_aoi.py -v`
Expected: PASS — all six AOI tests (Task 1's three plus these three).

Run: `.venv/bin/python -m pytest -q`
Expected: `121 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/l5k_sim/engine.py tests/test_aoi.py
git commit -m "feat(l5k-sim): execute AOI Logic and copy outputs back to caller"
```

---

### Task 3: Guarded real-file regression

Prove on the real Briles file that a chained `max_dint` → `min_dint` → `scaler_dint` computation executes and composes correctly, and that scanning does not crash. (The default scan runs `programs[0]` = `Lower_KO_Valve_Adapter`, which contains this AOI chain; `MisFeed` lives in `MainProgram` and is not reached here, so its count-mismatch skip is covered by Task 1's unit test rather than this one.)

**Files:**
- Modify: `tests/test_real_file_regression.py` (add one test)

**Interfaces:**
- Consumes: the full AOI-invocation path from Tasks 1–2.
- Produces: nothing for later tasks (final verification).

- [ ] **Step 1: Add the guarded regression test**

Append to `tests/test_real_file_regression.py` (the module already defines `REAL`, `pytestmark`, `parse_l5k`, and `ScanEngine`):

```python
def test_aoi_chain_computes_on_real_file():
    engine = ScanEngine(parse_l5k(REAL))
    engine.run(5)  # must not raise
    scope = "Lower_KO_Valve_Adapter"
    # max_dint -> min_dint clamp speed to [0, 100]; scaler_dint maps [0,100] -> [0,5000].
    sc = engine.db.read(scope, "speed_clamped")
    mg = engine.db.read(scope, "magnitude")
    assert 0 <= sc <= 100          # min/max AOIs clamped correctly
    assert mg == sc * 50           # scaler_dint: out = in * (5000-0)/(100-0)
```

- [ ] **Step 2: Run the regression test**

Run: `.venv/bin/python -m pytest tests/test_real_file_regression.py -v`
Expected: PASS (the real file is present on the dev machine, so the test RUNS; if absent it is `skipped`).

If skipped, verify manually:
```bash
PYTHONPATH=src .venv/bin/python -c "from l5k_sim.l5k_parser import parse_l5k; from l5k_sim.engine import ScanEngine; e=ScanEngine(parse_l5k('$HOME/Downloads/briles_main_rev_023.L5K')); e.run(5); s='Lower_KO_Valve_Adapter'; print(e.db.read(s,'speed_clamped'), e.db.read(s,'magnitude'))"
```
Expected: prints a clamped `speed_clamped` in 0..100 and `magnitude == speed_clamped*50`.

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: `122 passed` (or `121 passed, 1 skipped` if the real file is absent).

- [ ] **Step 4: Commit**

```bash
git add tests/test_real_file_regression.py
git commit -m "test(l5k-sim): guard real-file AOI chain execution"
```

---

## Self-Review

**Spec coverage:**
- AOI registry + routing from `_eval_instruction` → Task 1. ✓
- Positional argument binding (skip EnableIn/EnableOut + locals) + count-mismatch skip + non-dict skip → Task 1. ✓
- Logic execution against the instance scope + EnableOut + disabled-holds → Task 2. ✓
- Output/InOut copy-back → Task 2. ✓
- Per-instruction isolation (AOI raise contained) → Task 1's `_eval_instruction` wrapper. ✓
- Guarded real-file regression (chained AOI compute, MisFeed safe-skip, no crash) → Task 3. ✓
- Deferred (RTO instruction, MisFeed binding fix, AOI-internal UI, nested AOIs) → intentionally not tasked; documented in the spec's Known limitations. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows complete code. ✓

**Type consistency:** `invoke_aoi(self, scope, instr, power_in) -> bool` is defined in Task 1 and completed in Task 2 with the same signature. `self._aois: dict[str, AOIDef]`. `call_params` filter and the bind/copy-back loops use the same `p.usage`/`p.name` fields consistently. The synthetic scope key `f"__aoi__/{instr.mnemonic}"` is registered and popped in the same method. Test counts increment monotonically (115 → 118 → 121 → 122). ✓
