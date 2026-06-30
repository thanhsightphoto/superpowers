# UDT DATATYPE-grammar Fidelity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse the real Logix DATATYPE member grammar (type-first plain members, array members, and BIT overlays) and initialize every member kind in the tag DB, so real-file rungs that read/write UDT members compute real values instead of silently no-opping on `KeyError`.

**Architecture:** Introduce a `Member` dataclass as the IR representation of a UDT member (replacing `tuple[str, str]`). Rewrite `_build_datatype` to parse the real type-first grammar into `Member`s. Teach `TagDatabase` to initialize bit-overlay members as independent booleans, array members as lists, and `BIT` scalars as `False`. A guarded regression test proves the six real-file `KeyError`s are gone.

**Tech Stack:** Python 3.11 (project venv at `.venv`), stdlib only, pytest. Zero third-party dependencies.

## Global Constraints

- Python baseline is **3.11**. Use `.venv/bin/python` — never the system `python3` (it is 3.9.6).
- Run all commands from `projects/l5k-logic-sim/` (the package resolves `src/` on the pytest path already; the full suite is currently **92 passing**).
- Zero third-party dependencies. Standard library only.
- Bit-overlay members are modeled as **independent booleans** (no bit/word coherence) — per the approved design.
- The real `briles_main_rev_023.L5K` is git-ignored customer data at `~/Downloads/briles_main_rev_023.L5K`; never commit it, and guard any test that reads it with `skipif` on its presence.
- Every commit must leave the full suite green.

---

### Task 1: IR `Member` dataclass + serialization (pure model swap, no behavior change)

Introduce the `Member` model and migrate every consumer to it **without changing any parsing or initialization behavior**. After this task the parser still produces the same (old-grammar) results and the tag DB initializes members exactly as before — only the in-memory representation changes.

**Files:**
- Modify: `src/l5k_sim/ir.py` (add `Member`, change `DataType.members`, update serialization)
- Modify: `src/l5k_sim/l5k_parser.py` (`_build_datatype` emits `Member` objects)
- Modify: `src/l5k_sim/tagdb.py` (`from_project` / `_init_type` consume `Member`)
- Modify: `tests/test_ir.py` (construct `Member` in the round-trip sample)
- Modify: `tests/test_tagdb.py` (construct `Member` in fixtures)

**Interfaces:**
- Produces: `Member(name: str, data_type: str, dim: int | None = None, bit_host: str | None = None, bit_pos: int | None = None)` dataclass exported from `l5k_sim.ir`; `DataType.members: list[Member]`.
- Consumes: nothing from earlier tasks.

- [ ] **Step 1: Update the IR round-trip test to use `Member`**

In `tests/test_ir.py`, add `Member` to the existing multi-line import (lines 5–9) and change the `DataType` construction on line 27. The import currently reads:

```python
from l5k_sim.ir import (
    Instruction, Branch, Rung, Routine, Tag, AOIDef, DataType,
    Program, Controller, Project, project_to_dict, project_from_dict,
    _element_from_dict,
)
```

Add `Member` to the first line of names (do not remove `_element_from_dict` or anything else):

```python
from l5k_sim.ir import (
    Instruction, Branch, Rung, Routine, Tag, AOIDef, DataType, Member,
    Program, Controller, Project, project_to_dict, project_from_dict,
    _element_from_dict,
)
```

```python
# line 27 — was: [DataType("ud", [("m", "BOOL")])],
    ctrl = Controller("Sutherland", "1769-L30ERMS", [], [DataType("ud", [Member("m", "BOOL")])],
                      [AOIDef("scaler_dint", [Tag("In", "DINT", "scaler_dint", "Input", None, None)], None)],
                      [prog])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_ir.py::test_project_json_round_trip_is_lossless -v`
Expected: FAIL with `ImportError: cannot import name 'Member'` (or `AttributeError`).

- [ ] **Step 3: Add the `Member` dataclass and switch `DataType.members`**

In `src/l5k_sim/ir.py`, replace the `DataType` dataclass (currently lines 53–56) with:

```python
@dataclass
class Member:
    name: str
    data_type: str
    dim: int | None = None
    bit_host: str | None = None
    bit_pos: int | None = None


@dataclass
class DataType:
    name: str
    members: list[Member]
```

- [ ] **Step 4: Update serialization for the new member shape**

In `src/l5k_sim/ir.py`, add these two helpers next to the other `_*_to_dict` helpers:

```python
def _member_to_dict(m: Member) -> dict:
    return {"name": m.name, "data_type": m.data_type, "dim": m.dim,
            "bit_host": m.bit_host, "bit_pos": m.bit_pos}


def _member_from_dict(d: dict) -> Member:
    return Member(d["name"], d["data_type"], d.get("dim"), d.get("bit_host"), d.get("bit_pos"))
```

In `project_to_dict`, change the `datatypes` line (currently uses `[list(m) for m in dt.members]`) to:

```python
            "datatypes": [{"name": dt.name, "members": [_member_to_dict(m) for m in dt.members]} for dt in c.datatypes],
```

In `project_from_dict`, change the `datatypes` construction (currently `DataType(x["name"], [tuple(m) for m in x["members"]])`) to:

```python
        datatypes=[DataType(x["name"], [_member_from_dict(m) for m in x["members"]]) for x in cd["datatypes"]],
```

- [ ] **Step 5: Make `_build_datatype` emit `Member` objects (behavior preserved)**

In `src/l5k_sim/l5k_parser.py`, add `Member` to the `ir` import, and change `_build_datatype` (currently lines 51–60) so the member list holds `Member`s instead of tuples — same parsing logic, new type:

```python
def _build_datatype(block: Block) -> DataType:
    name = block_name(block)
    members: list[Member] = []
    for line in block.body_lines:
        s = line.strip()
        if s.endswith(";") and " : " in s:
            mname, rest = s[:-1].split(" : ", 1)
            mtype = rest.strip().split(None, 1)[0].rstrip(";")
            members.append(Member(mname.strip(), mtype))
    return DataType(name=name, members=members)
```

- [ ] **Step 6: Make `TagDatabase` consume `Member` (behavior preserved)**

In `src/l5k_sim/tagdb.py`, the `_udts` map already stores `dt.members`. Change the UDT-instantiation branch in `_init_type` (currently the `if data_type in self._udts:` line that does `{m: self._init_type(mt, None) for m, mt in self._udts[data_type]}`) to iterate `Member`s:

```python
        if data_type in self._udts:
            out: dict[str, Any] = {}
            for mem in self._udts[data_type]:
                out[mem.name] = self._init_type(mem.data_type, None)
            return out
```

Update the type annotation on `self._udts` in `__init__` from `dict[str, list[tuple[str, str]]]` to `dict[str, list]` (or `dict[str, list["Member"]]` with a `Member` import).

- [ ] **Step 7: Update `tests/test_tagdb.py` fixtures to `Member`**

In `tests/test_tagdb.py`, add `Member` to the import on line 1, then change the two `DataType` constructions:

```python
from l5k_sim.ir import Controller, DataType, Member, Program, Project, Tag
```

```python
# line 7 — was: DataType("io_t", [("active_mode", "DINT"), ("running", "BOOL")])
    udt = DataType("io_t", [Member("active_mode", "DINT"), Member("running", "BOOL")])
```

```python
# line 64 — was: DataType("blk", [("word", "DINT")])
    udt = DataType("blk", [Member("word", "DINT")])
```

- [ ] **Step 8: Run the full suite to verify green**

Run: `.venv/bin/python -m pytest -q`
Expected: `92 passed` (count unchanged — this task only swaps the representation).

- [ ] **Step 9: Commit**

```bash
git add src/l5k_sim/ir.py src/l5k_sim/l5k_parser.py src/l5k_sim/tagdb.py tests/test_ir.py tests/test_tagdb.py
git commit -m "refactor(l5k-sim): introduce Member IR for UDT members"
```

---

### Task 2: Real DATATYPE grammar parser

Rewrite `_build_datatype` to parse the real type-first Logix grammar: plain members (`<TYPE> <name>[dim]?`), and BIT overlays (`BIT <name> <host> : <bit>`). Fix the synthetic fixture so it stops teaching the fictional grammar.

**Files:**
- Modify: `src/l5k_sim/l5k_parser.py:_build_datatype`
- Modify: `tests/fixtures/mode1.L5K` (real DATATYPE grammar)
- Modify: `tests/test_l5k_parser.py` (assert real member parsing)

**Interfaces:**
- Consumes: `Member` from Task 1.
- Produces: `_build_datatype` returns a `DataType` whose `members` are real `Member`s — plain (`dim`/`bit_host`/`bit_pos` all `None`), array (`dim` set), or bit overlay (`bit_host` + `bit_pos` set, `data_type == "BIT"`).

- [ ] **Step 1: Rewrite the fixture's DATATYPE block to real grammar**

In `tests/fixtures/mode1.L5K`, replace the DATATYPE block (currently lines 3–6) with real type-first grammar that keeps the `briles_special_modes` name and the `out_ram_cycle_cmd` member used by the Outputs routine:

```
	DATATYPE briles_special_modes (FamilyType := NoFamily)
		DINT active_mode (Description := "current mode");
		SINT ZZZZZZZZZZspecial_mo0 (Hidden := 1);
		BIT out_ram_cycle_cmd ZZZZZZZZZZspecial_mo0 : 0 (Description := "ram cycle command");
	END_DATATYPE
```

Leave the rest of the file unchanged.

- [ ] **Step 2: Write the failing parser tests**

In `tests/test_l5k_parser.py`, replace the body of `test_datatype_and_controller_tag` (lines 13–17) with assertions on real member parsing, and add a new test for arrays and a previously-dropped plain member using an inline `tmp_path` L5K:

```python
def test_datatype_and_controller_tag():
    p = parse_l5k(FIXTURE)
    dt = next(dt for dt in p.controller.datatypes if dt.name == "briles_special_modes")
    by_name = {m.name: m for m in dt.members}
    # plain type-first member
    assert by_name["active_mode"].data_type == "DINT"
    assert by_name["active_mode"].bit_host is None and by_name["active_mode"].dim is None
    # hidden host word retained as an ordinary plain member
    assert by_name["ZZZZZZZZZZspecial_mo0"].data_type == "SINT"
    # bit overlay
    bit = by_name["out_ram_cycle_cmd"]
    assert bit.data_type == "BIT" and bit.bit_host == "ZZZZZZZZZZspecial_mo0" and bit.bit_pos == 0
    # controller tag still parses
    assert any(t.name == "global_estop" and t.scope == "controller"
               for t in p.controller.controller_tags)


def test_datatype_plain_and_array_members(tmp_path):
    text = (
        'CONTROLLER C (ProcessorType := "1769-L30ERMS")\n'
        '\tDATATYPE FaultRecord (FamilyType := NoFamily)\n'
        '\t\tDINT TimeLow;\n'
        '\t\tINT Code;\n'
        '\t\tDINT Info[8] (Radix := Hex);\n'
        '\tEND_DATATYPE\n'
        'END_CONTROLLER\n'
    )
    f = tmp_path / "dt.L5K"
    f.write_text(text)
    p = parse_l5k(str(f))
    dt = next(dt for dt in p.controller.datatypes if dt.name == "FaultRecord")
    by_name = {m.name: m for m in dt.members}
    assert set(by_name) == {"TimeLow", "Code", "Info"}        # nothing dropped
    assert by_name["TimeLow"].data_type == "DINT"
    assert by_name["Info"].data_type == "DINT" and by_name["Info"].dim == 8
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_l5k_parser.py::test_datatype_and_controller_tag tests/test_l5k_parser.py::test_datatype_plain_and_array_members -v`
Expected: FAIL — old parser produces no `active_mode`/`Info` members (KeyError in the test) and mis-parses the bit overlay.

- [ ] **Step 4: Rewrite `_build_datatype` for the real grammar**

In `src/l5k_sim/l5k_parser.py`, replace `_build_datatype` (the function introduced in Task 1) with:

```python
def _build_datatype(block: Block) -> DataType:
    name = block_name(block)
    members: list[Member] = []
    for line in block.body_lines:
        s = line.strip()
        if not s.endswith(";"):
            continue
        s = s[:-1].strip()
        # strip the outer (attrs) group, if present
        paren = s.find("(")
        if paren != -1:
            close = find_matching(s, paren)
            s = (s[:paren] + s[close + 1:]).strip()
        if not s:
            continue
        if s.startswith("BIT ") and ":" in s:
            head, bitpos = s.split(":", 1)
            toks = head.split()  # ["BIT", <name>, <host>]
            if len(toks) >= 3 and bitpos.strip().lstrip("+-").isdigit():
                members.append(Member(toks[1], "BIT", bit_host=toks[2], bit_pos=int(bitpos.strip())))
                continue
        # plain type-first member: "<TYPE> <name>[dim]?"
        toks = s.split(None, 1)
        if len(toks) != 2:
            continue
        mtype, mname = toks[0], toks[1].strip()
        dim = None
        if mname.endswith("]") and "[" in mname:
            base, _, rest = mname.partition("[")
            inner = rest[:-1].strip()
            if inner.isdigit():
                dim = int(inner)
                mname = base.strip()
        members.append(Member(mname, mtype, dim=dim))
    return DataType(name=name, members=members)
```

Ensure `find_matching` is imported at the top of `l5k_parser.py`:

```python
from l5k_sim.scan import find_matching
```

- [ ] **Step 5: Run the new tests, then the full suite**

Run: `.venv/bin/python -m pytest tests/test_l5k_parser.py -v`
Expected: PASS for both new assertions and the existing parser tests.

Run: `.venv/bin/python -m pytest -q`
Expected: `93 passed` (one new test added; nothing broken).

- [ ] **Step 6: Commit**

```bash
git add src/l5k_sim/l5k_parser.py tests/fixtures/mode1.L5K tests/test_l5k_parser.py
git commit -m "feat(l5k-sim): parse real DATATYPE grammar (plain, array, BIT overlay)"
```

---

### Task 3: Tag DB initialization for bit overlays, arrays, and BIT scalars

Teach `TagDatabase` to initialize each member kind: bit-overlay members as independent booleans, array members as lists, and a bare `BIT` type as `False`.

**Files:**
- Modify: `src/l5k_sim/tagdb.py` (`_init_type` UDT branch + `BIT` case)
- Modify: `tests/test_tagdb.py` (new init tests)

**Interfaces:**
- Consumes: `Member` (Task 1) with `dim` / `bit_host` / `bit_pos`; the real-grammar parser output (Task 2).
- Produces: a UDT instance dict where bit members are `bool`, array members are `list` of length `dim`, and scalar members keep their existing init.

- [ ] **Step 1: Write the failing tag DB tests**

Append to `tests/test_tagdb.py`:

```python
def test_bit_overlay_members_init_as_independent_bools():
    udt = DataType("bits_t", [
        Member("host", "SINT"),
        Member("ext", "BIT", bit_host="host", bit_pos=6),
        Member("ret", "BIT", bit_host="host", bit_pos=7),
    ])
    tags = [Tag("iface", "bits_t", "P", "InOut", None, None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [udt], [], [Program("P", None, tags, [])])))
    assert db.read("P", "iface.ext") is False
    db.write("P", "iface.ext", True)
    assert db.read("P", "iface.ext") is True
    assert db.read("P", "iface.ret") is False   # independent of ext


def test_array_member_init_as_list():
    udt = DataType("rec_t", [Member("Info", "DINT", dim=8)])
    tags = [Tag("rec", "rec_t", "P", None, None, None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [udt], [], [Program("P", None, tags, [])])))
    info = db.read("P", "rec.Info")
    assert isinstance(info, list) and len(info) == 8 and info == [0] * 8
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_tagdb.py::test_bit_overlay_members_init_as_independent_bools tests/test_tagdb.py::test_array_member_init_as_list -v`
Expected: FAIL — bit member currently inits via `_init_type("BIT")` to `0` (not `False`), and the array member inits to a scalar `0`, not a list.

- [ ] **Step 3: Add the `BIT` scalar case to `_init_type`**

In `src/l5k_sim/tagdb.py`, add a `BIT` branch alongside the `BOOL` branch in `_init_type` (right after the `if dt == "BOOL":` block):

```python
        if dt == "BIT":
            return bool(parse_literal(initial)) if (initial and is_literal(initial)) else False
```

- [ ] **Step 4: Initialize bit and array members in the UDT branch**

In `src/l5k_sim/tagdb.py`, replace the UDT-instantiation branch from Task 1 with:

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

- [ ] **Step 5: Run the new tests, then the full suite**

Run: `.venv/bin/python -m pytest tests/test_tagdb.py -v`
Expected: PASS for both new tests and all existing tagdb tests.

Run: `.venv/bin/python -m pytest -q`
Expected: `95 passed` (two new tests added).

- [ ] **Step 6: Commit**

```bash
git add src/l5k_sim/tagdb.py tests/test_tagdb.py
git commit -m "feat(l5k-sim): init UDT bit-overlay (bool), array (list), and BIT members"
```

---

### Task 4: Real-file regression test (guarded)

Prove the end-to-end fix: parsing the real Briles file and running scans no longer produces the six `interface.*` `KeyError` diagnostics. Skips cleanly when the git-ignored file is absent.

**Files:**
- Create: `tests/test_real_file_regression.py`

**Interfaces:**
- Consumes: the full pipeline (`parse_l5k`, `ScanEngine`) as fixed by Tasks 1–3.
- Produces: nothing for later tasks (final verification).

- [ ] **Step 1: Write the guarded regression test**

Create `tests/test_real_file_regression.py`:

```python
import os
import pytest

from l5k_sim.l5k_parser import parse_l5k
from l5k_sim.engine import ScanEngine

REAL = os.path.expanduser("~/Downloads/briles_main_rev_023.L5K")
pytestmark = pytest.mark.skipif(not os.path.exists(REAL), reason="real Briles L5K not present")

# the six member accesses that previously raised KeyError in Lower_KO_Valve_Adapter
_PREV_FAILING = [
    "out_lower_ko_ext", "out_lower_ko_ret", "lower_ko_speed_pct",
    "lower_ko_valve_monitor", "lower_ko_valve_stiction_tolerance",
    "lower_ko_valve_stiction_timeout_ms",
]


def test_interface_member_keyerrors_are_gone():
    engine = ScanEngine(parse_l5k(REAL))
    engine.run(5)
    raised = [d for d in engine.diagnostics if "raised:" in d]
    for member in _PREV_FAILING:
        assert not any(member in d for d in raised), f"{member} still raising: {raised}"
```

- [ ] **Step 2: Run the regression test**

Run: `.venv/bin/python -m pytest tests/test_real_file_regression.py -v`
Expected: PASS (or `skipped` if the file is absent on this machine — in which case verify manually with the smoke command below).

Manual smoke (only if skipped):
```bash
PYTHONPATH=src .venv/bin/python -c "from l5k_sim.l5k_parser import parse_l5k; from l5k_sim.engine import ScanEngine; e=ScanEngine(parse_l5k('$HOME/Downloads/briles_main_rev_023.L5K')); e.run(5); print([d for d in e.diagnostics if 'raised:' in d])"
```
Expected: the printed list contains none of the six member names.

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: `96 passed` (or `95 passed, 1 skipped` when the real file is absent).

- [ ] **Step 4: Commit**

```bash
git add tests/test_real_file_regression.py
git commit -m "test(l5k-sim): guard real-file UDT member resolution against regression"
```

---

## Self-Review

**Spec coverage:**
- IR `Member` model + serialization → Task 1. ✓
- Real DATATYPE grammar parser (plain / array / BIT overlay, hidden host retained) → Task 2. ✓
- Tag DB init (bit = independent bool, array = list, BIT scalar = False, nested/TIMER/COUNTER preserved) → Task 3. ✓
- Fixture rewrite to real grammar + test migration → Tasks 1–2. ✓
- Guarded real-file regression on the six KeyErrors → Task 4. ✓
- Out-of-scope items (`[i]` indexing, array-of-UDT, AOI calls, `ABS`, bit/word coherence, aggregate initializers) → intentionally not tasked, documented in the spec. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows complete code. ✓

**Type consistency:** `Member(name, data_type, dim, bit_host, bit_pos)` is used identically in Tasks 1–4. `_build_datatype` returns `DataType` with `list[Member]`; `_init_type` reads `mem.name` / `mem.data_type` / `mem.dim` / `mem.bit_host` consistently. Test counts increment monotonically (92 → 93 → 95 → 96). ✓
