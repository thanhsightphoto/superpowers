# Structured-tag Initialization Fidelity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Initialize AOI-instance tags as structured member dicts and decompose UDT-tag positional aggregate initializers into members (deriving bit-overlay members from their host word), so structured tags hold correct initial member values instead of scalar `0` / all-defaults.

**Architecture:** Extend `tagdb` initialization. AOI-typed tags initialize from their AOI parameter list. A new `_init_struct` helper builds a UDT's default member dict, then applies an aggregate `[…]` initializer positionally to the storage members (bit-overlays skipped), recursing for nested UDT/array members, and finally derives bit-overlay members from their host word's initialized bits.

**Tech Stack:** Python 3.11 (project venv at `.venv`), standard library only, pytest.

## Global Constraints

- Python baseline is **3.11**. Use `.venv/bin/python` — never the system `python3` (it is 3.9.6).
- Run all commands from `projects/l5k-logic-sim/`. The full suite is currently **108 passing**.
- Standard library only; zero third-party dependencies.
- Scope: AOI-instance **structural** init (members exist as defaults) + UDT-tag aggregate decomposition + bit-overlay derivation. Explicitly **out of scope**: AOI-instance aggregate *value* decomposition (leading-bitfield-packed BOOLs) and AOI *execution* — both deferred to sub-project 3.
- The real `briles_main_rev_023.L5K` is git-ignored customer data at `~/Downloads/briles_main_rev_023.L5K`; never commit it, and guard any test that reads it with `skipif` on its presence.
- Every commit must leave the full suite green.
- Degrade, never crash: initializer/member mismatches append a diagnostic to `self.diagnostics` and never raise.

---

### Task 1: AOI-instance tags initialize as parameter dicts

**Files:**
- Modify: `src/l5k_sim/tagdb.py` (`__init__`, `from_project`, `_init_type`)
- Test: `tests/test_tagdb.py`

**Interfaces:**
- Consumes: `AOIDef.parameters` (a `list[Tag]`) from `project.controller.aois`.
- Produces: a tag whose `data_type` names an AOI initializes to `{param_name: default_value}`. Task 2 is independent of this.

- [ ] **Step 1: Write the failing test**

In `tests/test_tagdb.py`, add `AOIDef` to the `l5k_sim.ir` import, then append:

```python
def test_aoi_instance_inits_as_param_dict():
    aoi = AOIDef("scale2", [
        Tag("EnableIn", "BOOL", "scale2", "Input", None, None),
        Tag("In", "DINT", "scale2", "Input", None, None),
        Tag("Out", "DINT", "scale2", "Output", None, None),
    ], None)
    tags = [Tag("inst", "scale2", "P", None, None, None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [], [aoi], [Program("P", None, tags, [])])))
    inst = db.read("P", "inst")
    assert isinstance(inst, dict) and set(inst) == {"EnableIn", "In", "Out"}
    assert db.read("P", "inst.In") == 0
    assert db.read("P", "inst.EnableIn") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_tagdb.py::test_aoi_instance_inits_as_param_dict -v`
Expected: FAIL — `_init_type("scale2", None)` currently falls through to `return 0`, so `db.read("P", "inst")` is `0` (not a dict), and `inst.In` raises/degrades.

- [ ] **Step 3: Populate `_aois` and add the AOI branch**

In `src/l5k_sim/tagdb.py`, add an aois map in `__init__` (next to `self._udts`):

```python
        self._aois: dict[str, list[Tag]] = {}
```

In `from_project`, populate it right after the `_udts` line:

```python
        db._aois = {a.name: a.parameters for a in project.controller.aois}
```

In `_init_type`, add an AOI branch immediately before the final `return 0`:

```python
        if data_type in self._aois:
            return {p.name: self._init_type(p.data_type, p.initial) for p in self._aois[data_type]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_tagdb.py::test_aoi_instance_inits_as_param_dict -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: `109 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/l5k_sim/tagdb.py tests/test_tagdb.py
git commit -m "feat(l5k-sim): initialize AOI-instance tags as parameter dicts"
```

---

### Task 2: `_init_struct` — UDT positional aggregate decomposition

Extract the inline UDT default-build into a `_init_struct` helper and add positional aggregate-initializer decomposition over storage members (scalars, arrays, nested UDTs). Bit-overlay members remain at their `False` default in this task (derivation is Task 3).

**Files:**
- Modify: `src/l5k_sim/tagdb.py` (add `_init_struct`, rewire the UDT branch of `_init_type`)
- Test: `tests/test_tagdb.py`

**Interfaces:**
- Consumes: `Member` fields (`name`, `data_type`, `dim`, `bit_host`), `split_top_level`, `_init_array`, `_init_type`.
- Produces: `_init_struct(data_type, initial) -> dict`. A UDT tag with an aggregate initializer has its storage members filled positionally; nested UDT/array members recurse. Task 3 adds bit-overlay derivation into this same helper.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tagdb.py`:

```python
def test_udt_aggregate_decomposition_scalars():
    udt = DataType("blk", [Member("host", "SINT"), Member("val", "REAL")])
    tags = [Tag("b", "blk", "P", None, "[3,25.5]", None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [udt], [], [Program("P", None, tags, [])])))
    assert db.read("P", "b.host") == 3
    assert db.read("P", "b.val") == 25.5


def test_udt_aggregate_decomposition_nested_udt():
    inner = DataType("inner", [Member("a", "DINT"), Member("b", "DINT")])
    outer = DataType("outer", [Member("x", "DINT"), Member("sub", "inner")])
    tags = [Tag("o", "outer", "P", None, "[7,[10,20]]", None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [inner, outer], [], [Program("P", None, tags, [])])))
    assert db.read("P", "o.x") == 7
    assert db.read("P", "o.sub.a") == 10
    assert db.read("P", "o.sub.b") == 20


def test_udt_aggregate_decomposition_array_member():
    udt = DataType("rec", [Member("n", "DINT"), Member("data", "DINT", dim=3)])
    tags = [Tag("r", "rec", "P", None, "[5,[1,2,3]]", None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [udt], [], [Program("P", None, tags, [])])))
    assert db.read("P", "r.n") == 5
    assert db.read("P", "r.data") == [1, 2, 3]


def test_udt_aggregate_longer_than_members_diagnoses():
    udt = DataType("blk", [Member("host", "SINT")])
    tags = [Tag("b", "blk", "P", None, "[1,2,3]", None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [udt], [], [Program("P", None, tags, [])])))
    assert db.read("P", "b.host") == 1
    assert any("struct initializer longer" in d for d in db.diagnostics)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_tagdb.py::test_udt_aggregate_decomposition_scalars tests/test_tagdb.py::test_udt_aggregate_decomposition_nested_udt tests/test_tagdb.py::test_udt_aggregate_decomposition_array_member tests/test_tagdb.py::test_udt_aggregate_longer_than_members_diagnoses -v`
Expected: FAIL — the current UDT branch ignores `initial`, so members stay at defaults (`b.host` is `0`, no diagnostic).

- [ ] **Step 3: Add `_init_struct` and rewire the UDT branch**

In `src/l5k_sim/tagdb.py`, replace the inline UDT branch of `_init_type` (currently):

```python
        if data_type in self._udts:
            out: dict[str, Any] = {}
            for mem in self._udts[data_type]:
                if mem.bit_host is not None:
                    out[mem.name] = False
                elif mem.dim is not None:
                    out[mem.name] = [self._init_type(mem.data_type, None) for _ in range(mem.dim)]
                else:
                    out[mem.name] = self._init_type(mem.data_type, None)
            return out
```

with a delegation:

```python
        if data_type in self._udts:
            return self._init_struct(data_type, initial)
```

Then add the `_init_struct` helper method (place it right after `_init_array`):

```python
    def _init_struct(self, data_type: str, initial: str | None) -> dict:
        members = self._udts[data_type]
        out: dict[str, Any] = {}
        for mem in members:
            if mem.bit_host is not None:
                out[mem.name] = False
            elif mem.dim is not None:
                out[mem.name] = [self._init_type(mem.data_type, None) for _ in range(mem.dim)]
            else:
                out[mem.name] = self._init_type(mem.data_type, None)
        if initial:
            s = initial.strip()
            if s.startswith("[") and s.endswith("]"):
                items = split_top_level(s[1:-1])
                storage = [m for m in members if m.bit_host is None]
                for i, mem in enumerate(storage):
                    if i >= len(items):
                        break
                    item = items[i].strip()
                    if not item:
                        continue
                    if mem.dim is not None:
                        out[mem.name] = self._init_array(mem.data_type, mem.dim, item)
                    elif mem.data_type in self._udts:
                        out[mem.name] = self._init_struct(mem.data_type, item)
                    else:
                        out[mem.name] = self._init_type(mem.data_type, item)
                if len(items) > len(storage):
                    self.diagnostics.append(
                        f"struct initializer longer than members ({len(storage)}): {initial}")
        return out
```

- [ ] **Step 4: Run the tests, then the full suite**

Run: `.venv/bin/python -m pytest tests/test_tagdb.py -v`
Expected: PASS — the four new tests plus all existing tagdb tests (the delegation preserves default-build behavior for `initial=None`).

Run: `.venv/bin/python -m pytest -q`
Expected: `113 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/l5k_sim/tagdb.py tests/test_tagdb.py
git commit -m "feat(l5k-sim): decompose UDT aggregate initializers into members"
```

---

### Task 3: Derive bit-overlay members from the host word

After a struct's storage members are assigned, set each bit-overlay member from the corresponding bit of its host word's initialized value.

**Files:**
- Modify: `src/l5k_sim/tagdb.py` (`_init_struct`)
- Test: `tests/test_tagdb.py`

**Interfaces:**
- Consumes: `Member.bit_host` / `Member.bit_pos`, and the storage-member values already assigned in `_init_struct`.
- Produces: bit-overlay members reflect their host word's initialized bits.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tagdb.py`:

```python
def test_bit_overlay_derived_from_host_word():
    udt = DataType("bt", [
        Member("host", "SINT"),
        Member("b0", "BIT", bit_host="host", bit_pos=0),
        Member("b1", "BIT", bit_host="host", bit_pos=1),
        Member("b2", "BIT", bit_host="host", bit_pos=2),
    ])
    tags = [Tag("t", "bt", "P", None, "[3]", None)]   # host = 3 -> bits 0,1 set; bit 2 clear
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [udt], [], [Program("P", None, tags, [])])))
    assert db.read("P", "t.host") == 3
    assert db.read("P", "t.b0") is True
    assert db.read("P", "t.b1") is True
    assert db.read("P", "t.b2") is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_tagdb.py::test_bit_overlay_derived_from_host_word -v`
Expected: FAIL — bit-overlay members currently stay at their `False` default, so `t.b0` is `False` (should be `True`).

- [ ] **Step 3: Add the derivation pass to `_init_struct`**

In `src/l5k_sim/tagdb.py`, in `_init_struct`, add a derivation loop immediately before `return out`:

```python
        for mem in members:
            if mem.bit_host is not None and isinstance(out.get(mem.bit_host), int):
                out[mem.name] = bool((int(out[mem.bit_host]) >> (mem.bit_pos or 0)) & 1)
        return out
```

(Replace the existing bare `return out` at the end of `_init_struct` with the loop above followed by `return out`.)

- [ ] **Step 4: Run the test, then the full suite**

Run: `.venv/bin/python -m pytest tests/test_tagdb.py::test_bit_overlay_derived_from_host_word -v`
Expected: PASS.

Run: `.venv/bin/python -m pytest -q`
Expected: `114 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/l5k_sim/tagdb.py tests/test_tagdb.py
git commit -m "feat(l5k-sim): derive UDT bit-overlay members from host word init"
```

---

### Task 4: Guarded real-file regression

Prove on the real Briles file that a UDT tag's aggregate initializer decomposes to real member values (including a derived bit-overlay), an AOI instance is a structured dict, and scanning does not crash.

**Files:**
- Modify: `tests/test_real_file_regression.py` (add one test)

**Interfaces:**
- Consumes: the full pipeline as built by Tasks 1–3.
- Produces: nothing for later tasks (final verification).

- [ ] **Step 1: Add the guarded regression test**

Append to `tests/test_real_file_regression.py` (the module already defines `REAL`, `pytestmark`, `parse_l5k`, and `ScanEngine`):

```python
def test_structured_tag_init_resolves_on_real_file():
    engine = ScanEngine(parse_l5k(REAL))
    db = engine.db
    # UDT tag aggregate decomposition: real non-zero member values.
    assert db.read("controller", "briles_special_modes.ram_position") == 359.0
    assert db.read("controller", "briles_special_modes.lower_ko_valve_cmd") == 5000
    # Bit-overlay derived from host word (special_mo_inputs_x = 4 -> bit 2 set).
    assert db.read("controller", "briles_special_modes.ram_cycle_finished") is True
    # AOI instance is a structured dict, not scalar 0.
    inst = db.read("Lower_KO_Valve_Adapter", "scaler_inst")
    assert isinstance(inst, dict) and "in_max" in inst
    engine.run(5)  # must not raise
```

- [ ] **Step 2: Run the regression test**

Run: `.venv/bin/python -m pytest tests/test_real_file_regression.py -v`
Expected: PASS (the real file is present on the dev machine, so the test RUNS; if absent it is `skipped`).

If skipped, verify manually:
```bash
PYTHONPATH=src .venv/bin/python -c "from l5k_sim.l5k_parser import parse_l5k; from l5k_sim.engine import ScanEngine; d=ScanEngine(parse_l5k('$HOME/Downloads/briles_main_rev_023.L5K')).db; print(d.read('controller','briles_special_modes.ram_position'), d.read('controller','briles_special_modes.ram_cycle_finished'), type(d.read('Lower_KO_Valve_Adapter','scaler_inst')).__name__)"
```
Expected: prints `359.0 True dict`.

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: `115 passed` (or `114 passed, 1 skipped` if the real file is absent).

- [ ] **Step 4: Commit**

```bash
git add tests/test_real_file_regression.py
git commit -m "test(l5k-sim): guard real-file structured-tag init fidelity"
```

---

## Self-Review

**Spec coverage:**
- AOI-instance tags init as parameter dicts → Task 1. ✓
- UDT-tag positional aggregate decomposition (scalars, arrays, nested UDT, mismatch diagnostic) → Task 2. ✓
- Bit-overlay derivation from host word → Task 3. ✓
- Recursive nesting (covers J_mem) → emergent from Task 2's `_init_struct`/`_init_array` composition; exercised by `test_udt_aggregate_decomposition_nested_udt` and `_array_member`. ✓
- Guarded real-file regression (real member values, derived bit, AOI dict, no crash) → Task 4. ✓
- Deferred (AOI value decomposition, AOI execution) → intentionally not tasked; documented in the spec's Known limitations. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows complete code. ✓

**Type consistency:** `_init_struct(data_type, initial) -> dict` is defined in Task 2 and extended in Task 3; the UDT branch delegates to it. `_aois: dict[str, list[Tag]]` introduced in Task 1. `_init_array(elem_type, dim, item)` and `_init_type(member_type, item)` calls match existing signatures. Test counts increment monotonically (108 → 109 → 113 → 114 → 115). ✓
