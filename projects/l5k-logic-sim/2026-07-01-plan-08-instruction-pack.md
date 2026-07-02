# Core Instruction Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement eight standard Logix instructions — `CLR`, `ABS`, `NEG`, `MOD`, `COP`, `CTD`, `TOF`, `RTO` — so the corresponding real-file rungs execute instead of reporting "unsupported instruction".

**Architecture:** All eight are pure handler additions to `src/l5k_sim/instructions.py` via the existing `@register(...)`/`HANDLERS` mechanism. Timer/counter handlers read and write `<tag>.PRE/.ACC/.DN/...` from the tag's struct exactly like the existing `TON`/`CTU`. `CTD` requires adding `prev_cd` to the COUNTER struct (`tagdb.py`) and to `RES`.

**Tech Stack:** Python 3.11 (project venv at `.venv`), standard library only, pytest.

## Global Constraints

- Python baseline is **3.11**. Use `.venv/bin/python` — never the system `python3` (it is 3.9.6).
- Run all commands from `projects/l5k-logic-sim/`. The full suite is currently **122 passing**.
- Standard library only; zero third-party dependencies.
- Handlers act only when powered (return `power_in` for data ops); degrade with a diagnostic and skip the write on error (MOD-by-zero, COP out-of-range), never raise.
- Timer/counter handlers use `engine.scan_period_ms` for accumulation and ignore the `?` placeholder operands L5K emits (operand[0] is the struct tag), matching the existing `TON`/`CTU`/`RES`.
- The real `briles_main_rev_023.L5K` is git-ignored at `~/Downloads/briles_main_rev_023.L5K`; never commit it, guard real-file tests with `skipif`.
- Every commit must leave the full suite green.

---

### Task 1: Data/math instructions — CLR, ABS, NEG, MOD

**Files:**
- Modify: `src/l5k_sim/instructions.py`
- Create: `tests/test_instruction_pack.py`

**Interfaces:**
- Consumes: `engine._operand`, `engine.db.write`, `engine.diagnostics`.
- Produces: `HANDLERS` entries for `CLR`, `ABS`, `NEG`, `MOD`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_instruction_pack.py`:

```python
from l5k_sim.ir import Controller, Instruction, Program, Project, Tag
from l5k_sim.engine import ScanEngine


def _engine(tags):
    prog = Program("P", None, tags, [])
    return ScanEngine(Project(Controller("C", "x", [], [], [], [prog])))


def _run(e, mnem, operands, power=True):
    return e._eval_instruction("P", Instruction(mnem, operands, f"{mnem}(...)"), power)


def test_clr_sets_zero_when_powered():
    e = _engine([Tag("d", "DINT", "P", None, "42", None)])
    _run(e, "CLR", ["d"])
    assert e.db.read("P", "d") == 0


def test_clr_noop_when_unpowered():
    e = _engine([Tag("d", "DINT", "P", None, "42", None)])
    _run(e, "CLR", ["d"], power=False)
    assert e.db.read("P", "d") == 42


def test_abs():
    e = _engine([Tag("s", "DINT", "P", None, "-7", None), Tag("d", "DINT", "P", None, "0", None)])
    _run(e, "ABS", ["s", "d"])
    assert e.db.read("P", "d") == 7


def test_neg():
    e = _engine([Tag("s", "DINT", "P", None, "5", None), Tag("d", "DINT", "P", None, "0", None)])
    _run(e, "NEG", ["s", "d"])
    assert e.db.read("P", "d") == -5


def test_mod():
    e = _engine([Tag("a", "DINT", "P", None, "17", None), Tag("b", "DINT", "P", None, "5", None),
                 Tag("d", "DINT", "P", None, "0", None)])
    _run(e, "MOD", ["a", "b", "d"])
    assert e.db.read("P", "d") == 2


def test_mod_by_zero_degrades():
    e = _engine([Tag("a", "DINT", "P", None, "17", None), Tag("b", "DINT", "P", None, "0", None),
                 Tag("d", "DINT", "P", None, "9", None)])
    _run(e, "MOD", ["a", "b", "d"])
    assert e.db.read("P", "d") == 9
    assert any("MOD by zero" in x for x in e.diagnostics)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_instruction_pack.py -v`
Expected: FAIL — `_eval_instruction` reports `CLR`/`ABS`/`NEG`/`MOD` as unsupported (no write happens).

- [ ] **Step 3: Implement the four handlers**

In `src/l5k_sim/instructions.py`, append:

```python
@register("CLR")
def _clr(engine, scope, instr, power_in):
    if power_in:
        engine.db.write(scope, instr.operands[0], 0)
    return power_in


@register("ABS")
def _abs(engine, scope, instr, power_in):
    if power_in:
        engine.db.write(scope, instr.operands[1], abs(engine._operand(scope, instr.operands[0])))
    return power_in


@register("NEG")
def _neg(engine, scope, instr, power_in):
    if power_in:
        engine.db.write(scope, instr.operands[1], -engine._operand(scope, instr.operands[0]))
    return power_in


@register("MOD")
def _mod(engine, scope, instr, power_in):
    if power_in:
        a = engine._operand(scope, instr.operands[0])
        b = engine._operand(scope, instr.operands[1])
        if b == 0:
            engine.diagnostics.append(f"MOD by zero in {scope}")
            return power_in
        engine.db.write(scope, instr.operands[2], a - b * int(a / b))
    return power_in
```

- [ ] **Step 4: Run the tests, then the full suite**

Run: `.venv/bin/python -m pytest tests/test_instruction_pack.py -v`
Expected: PASS (6 tests).

Run: `.venv/bin/python -m pytest -q`
Expected: `128 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/l5k_sim/instructions.py tests/test_instruction_pack.py
git commit -m "feat(l5k-sim): add CLR/ABS/NEG/MOD instructions"
```

---

### Task 2: Array copy — COP

**Files:**
- Modify: `src/l5k_sim/instructions.py` (add `import copy` at top if absent; add `COP` handler)
- Modify: `tests/test_instruction_pack.py`

**Interfaces:**
- Consumes: `engine.db.read` (returns live list objects), `engine._operand`, `engine.diagnostics`.
- Produces: `HANDLERS["COP"]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_instruction_pack.py`:

```python
def test_cop_copies_elements():
    e = _engine([Tag("s", "DINT[3]", "P", None, "[1,2,3]", None),
                 Tag("d", "DINT[3]", "P", None, "[0,0,0]", None)])
    _run(e, "COP", ["s", "d", "3"])
    assert e.db.read("P", "d") == [1, 2, 3]


def test_cop_independent_and_bounds():
    e = _engine([Tag("s", "DINT[3]", "P", None, "[1,2,3]", None),
                 Tag("d", "DINT[3]", "P", None, "[0,0,0]", None)])
    _run(e, "COP", ["s", "d", "3"])
    e.db.write("P", "s[0]", 99)
    assert e.db.read("P", "d[0]") == 1        # copy is independent of source
    _run(e, "COP", ["s", "d", "99"])          # length beyond array bounds
    assert any("out of range" in x for x in e.diagnostics)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_instruction_pack.py::test_cop_copies_elements tests/test_instruction_pack.py::test_cop_independent_and_bounds -v`
Expected: FAIL — `COP` unsupported, `d` stays `[0,0,0]`.

- [ ] **Step 3: Implement COP**

In `src/l5k_sim/instructions.py`, ensure `import copy` is present near the top (next to `import operator as _op`). Append the handler:

```python
@register("COP")
def _cop(engine, scope, instr, power_in):
    if not power_in:
        return power_in
    src = engine.db.read(scope, instr.operands[0])
    dst = engine.db.read(scope, instr.operands[1])
    n = int(engine._operand(scope, instr.operands[2]))
    if not isinstance(src, list) or not isinstance(dst, list):
        engine.diagnostics.append(f"COP non-array operand in {scope}")
        return power_in
    for i in range(n):
        if i < len(src) and i < len(dst):
            dst[i] = copy.deepcopy(src[i])
        else:
            engine.diagnostics.append(f"COP out of range in {scope}")
            break
    return power_in
```

- [ ] **Step 4: Run the tests, then the full suite**

Run: `.venv/bin/python -m pytest tests/test_instruction_pack.py -v`
Expected: PASS.

Run: `.venv/bin/python -m pytest -q`
Expected: `130 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/l5k_sim/instructions.py tests/test_instruction_pack.py
git commit -m "feat(l5k-sim): add COP array-copy instruction"
```

---

### Task 3: Timers — TOF, RTO

**Files:**
- Modify: `src/l5k_sim/instructions.py`
- Modify: `tests/test_instruction_pack.py`

**Interfaces:**
- Consumes: `engine.scan_period_ms`, `engine.db` timer-struct access (`.PRE/.ACC/.EN/.TT/.DN`), the existing `RES` handler.
- Produces: `HANDLERS["TOF"]`, `HANDLERS["RTO"]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_instruction_pack.py`:

```python
def test_tof_holds_then_clears():
    e = _engine([Tag("t", "TIMER", "P", None, None, None)])
    e.db.write("P", "t.PRE", 30)
    _run(e, "TOF", ["t", "?", "?"], power=True)
    assert e.db.read("P", "t.DN") is True and e.db.read("P", "t.ACC") == 0
    _run(e, "TOF", ["t", "?", "?"], power=False)  # ACC 10
    _run(e, "TOF", ["t", "?", "?"], power=False)  # ACC 20
    assert e.db.read("P", "t.DN") is True          # still timing
    _run(e, "TOF", ["t", "?", "?"], power=False)  # ACC 30 -> elapsed
    assert e.db.read("P", "t.DN") is False


def test_rto_accumulates_and_retains():
    e = _engine([Tag("t", "TIMER", "P", None, None, None)])
    e.db.write("P", "t.PRE", 30)
    _run(e, "RTO", ["t", "?", "?"], power=True)   # ACC 10
    _run(e, "RTO", ["t", "?", "?"], power=True)   # ACC 20
    assert e.db.read("P", "t.ACC") == 20
    _run(e, "RTO", ["t", "?", "?"], power=False)  # retains, not reset
    assert e.db.read("P", "t.ACC") == 20
    _run(e, "RTO", ["t", "?", "?"], power=True)   # ACC 30 -> done
    assert e.db.read("P", "t.DN") is True


def test_rto_res_clears():
    e = _engine([Tag("t", "TIMER", "P", None, None, None)])
    e.db.write("P", "t.PRE", 30)
    e.db.write("P", "t.ACC", 30)
    e.db.write("P", "t.DN", True)
    _run(e, "RES", ["t"], power=True)
    assert e.db.read("P", "t.ACC") == 0 and e.db.read("P", "t.DN") is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_instruction_pack.py::test_tof_holds_then_clears tests/test_instruction_pack.py::test_rto_accumulates_and_retains -v`
Expected: FAIL — `TOF`/`RTO` unsupported. (`test_rto_res_clears` uses the existing `RES` and would pass on its own; it guards that retention is releasable.)

- [ ] **Step 3: Implement TOF and RTO**

In `src/l5k_sim/instructions.py`, append:

```python
@register("TOF")
def _tof(engine, scope, instr, power_in):
    name = instr.operands[0]
    pre = int(engine.db.read(scope, f"{name}.PRE"))
    acc = int(engine.db.read(scope, f"{name}.ACC"))
    if power_in:
        engine.db.write(scope, f"{name}.EN", True)
        engine.db.write(scope, f"{name}.DN", True)
        engine.db.write(scope, f"{name}.TT", False)
        engine.db.write(scope, f"{name}.ACC", 0)
        return True
    engine.db.write(scope, f"{name}.EN", False)
    if acc < pre:
        acc = min(pre, acc + engine.scan_period_ms)
        engine.db.write(scope, f"{name}.ACC", acc)
    dn = acc < pre
    engine.db.write(scope, f"{name}.DN", dn)
    engine.db.write(scope, f"{name}.TT", dn)
    return dn


@register("RTO")
def _rto(engine, scope, instr, power_in):
    name = instr.operands[0]
    pre = int(engine.db.read(scope, f"{name}.PRE"))
    acc = int(engine.db.read(scope, f"{name}.ACC"))
    if power_in:
        engine.db.write(scope, f"{name}.EN", True)
        if acc < pre:
            acc = min(pre, acc + engine.scan_period_ms)
            engine.db.write(scope, f"{name}.ACC", acc)
        done = acc >= pre
        engine.db.write(scope, f"{name}.DN", done)
        engine.db.write(scope, f"{name}.TT", not done)
        return done
    # unpowered: retain ACC and DN (RES releases)
    engine.db.write(scope, f"{name}.EN", False)
    engine.db.write(scope, f"{name}.TT", False)
    return acc >= pre
```

- [ ] **Step 4: Run the tests, then the full suite**

Run: `.venv/bin/python -m pytest tests/test_instruction_pack.py -v`
Expected: PASS.

Run: `.venv/bin/python -m pytest -q`
Expected: `133 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/l5k_sim/instructions.py tests/test_instruction_pack.py
git commit -m "feat(l5k-sim): add TOF and RTO timer instructions"
```

---

### Task 4: Count-down — CTD (+ COUNTER struct)

**Files:**
- Modify: `src/l5k_sim/tagdb.py` (add `prev_cd` to `_COUNTER`)
- Modify: `src/l5k_sim/instructions.py` (add `CTD`; add `prev_cd` to `RES`'s reset list)
- Modify: `tests/test_instruction_pack.py`

**Interfaces:**
- Consumes: COUNTER struct access (`.PRE/.ACC/.DN/.prev_cd`), `engine.scan` semantics.
- Produces: `HANDLERS["CTD"]`; COUNTER struct carries `prev_cd`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_instruction_pack.py`:

```python
def test_ctd_decrements_on_edge():
    e = _engine([Tag("c", "COUNTER", "P", None, None, None)])
    e.db.write("P", "c.ACC", 5)
    e.db.write("P", "c.PRE", 3)
    _run(e, "CTD", ["c", "?", "?"], power=True)    # false->true edge: 5 -> 4
    assert e.db.read("P", "c.ACC") == 4
    _run(e, "CTD", ["c", "?", "?"], power=True)    # no new edge: stays 4
    assert e.db.read("P", "c.ACC") == 4
    _run(e, "CTD", ["c", "?", "?"], power=False)   # reset edge
    _run(e, "CTD", ["c", "?", "?"], power=True)    # edge: 4 -> 3
    assert e.db.read("P", "c.ACC") == 3
    assert e.db.read("P", "c.DN") is True          # 3 >= 3
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_instruction_pack.py::test_ctd_decrements_on_edge -v`
Expected: FAIL — `CTD` unsupported.

- [ ] **Step 3: Add `prev_cd` to the COUNTER struct and implement CTD**

In `src/l5k_sim/tagdb.py`, add `prev_cd` to `_COUNTER`:

```python
_COUNTER = {"PRE": 0, "ACC": 0, "CU": False, "CD": False, "DN": False, "prev_cu": False, "prev_cd": False}
```

In `src/l5k_sim/instructions.py`, add `"prev_cd"` to the member tuple in the `RES` handler (so resetting a counter clears the down-edge memory too):

```python
            for member in ("ACC", "DN", "TT", "EN", "CU", "CD", "prev_cu", "prev_cd"):
```

Append the `CTD` handler:

```python
@register("CTD")
def _ctd(engine, scope, instr, power_in):
    name = instr.operands[0]
    pre = int(engine.db.read(scope, f"{name}.PRE"))
    acc = int(engine.db.read(scope, f"{name}.ACC"))
    prev = bool(engine.db.read(scope, f"{name}.prev_cd"))
    if power_in and not prev:
        acc -= 1
        engine.db.write(scope, f"{name}.ACC", acc)
    engine.db.write(scope, f"{name}.prev_cd", bool(power_in))
    done = acc >= pre
    engine.db.write(scope, f"{name}.DN", done)
    return done
```

- [ ] **Step 4: Run the test, then the full suite**

Run: `.venv/bin/python -m pytest tests/test_instruction_pack.py::test_ctd_decrements_on_edge -v`
Expected: PASS.

Run: `.venv/bin/python -m pytest -q`
Expected: `134 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/l5k_sim/tagdb.py src/l5k_sim/instructions.py tests/test_instruction_pack.py
git commit -m "feat(l5k-sim): add CTD count-down instruction"
```

---

### Task 5: Guarded real-file regression

**Files:**
- Modify: `tests/test_real_file_regression.py`

**Interfaces:**
- Consumes: the eight new handlers (Tasks 1–4).
- Produces: nothing for later tasks (final verification).

- [ ] **Step 1: Add the guarded regression test**

Append to `tests/test_real_file_regression.py` (the module already defines `REAL`, `pytestmark`, `parse_l5k`, `ScanEngine`):

```python
def test_instruction_pack_no_longer_unsupported_on_real_file():
    engine = ScanEngine(parse_l5k(REAL))
    pack = {"CLR", "ABS", "NEG", "MOD", "COP", "CTD", "TOF", "RTO"}
    for prog in engine.project.controller.programs:
        engine.scan(prog.name)  # must not raise
        unsup = {d.split("unsupported instruction", 1)[1].split(" in ")[0].strip()
                 for d in engine.diagnostics if "unsupported instruction" in d}
        assert not (pack & unsup), f"{prog.name}: still unsupported {pack & unsup}"
```

- [ ] **Step 2: Run the regression test**

Run: `.venv/bin/python -m pytest tests/test_real_file_regression.py -v`
Expected: PASS (runs on the dev machine; skipped if the file is absent).

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: `135 passed` (or `134 passed, 1 skipped` if the real file is absent).

- [ ] **Step 4: Commit**

```bash
git add tests/test_real_file_regression.py
git commit -m "test(l5k-sim): guard real-file instruction-pack coverage"
```

---

## Self-Review

**Spec coverage:** CLR/ABS/NEG/MOD → Task 1; COP → Task 2; TOF/RTO → Task 3; CTD (+ COUNTER `prev_cd` + RES) → Task 4; guarded real-file regression → Task 5. All eight instructions covered. Deferred items (RET, boundary/niche instructions) intentionally not tasked, documented in the spec. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✓

**Type consistency:** Handlers use `engine._operand`/`engine.db.write`/`engine.db.read` consistently; timer/counter handlers mirror the existing `TON`/`CTU`/`RES` struct-access pattern; `prev_cd` is added to `_COUNTER` and to `RES` in the same task that introduces `CTD`. Test counts increment monotonically (122 → 128 → 130 → 133 → 134 → 135). ✓
