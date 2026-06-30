# Array-tag Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make scalar-element array operands (`tag[i]`, `tag[i].n`) resolve to real values by adding typed path-segment parsing, array-tag initialization with aggregate initializers, and a generic indexed read/write walk.

**Architecture:** Centralize addressing — `parse_ref` tokenizes a full operand into typed segments (`Index`/`Bit`/`VarIndex`/member-`str`), and `tagdb.read`/`write` walk those segments generically through the nested list/dict tag structure. Top-level array tags initialize as Python lists, with aggregate initializers (`[…]`, including `2#` binary literals) applied per element.

**Tech Stack:** Python 3.11 (project venv at `.venv`), standard library only, pytest.

## Global Constraints

- Python baseline is **3.11**. Use `.venv/bin/python` — never the system `python3` (it is 3.9.6).
- Run all commands from `projects/l5k-logic-sim/`. The full suite is currently **97 passing**.
- Standard library only; zero third-party dependencies.
- Scope is **scalar-element arrays** (BOOL/INT/DINT/SINT/REAL), including bit-after-index. UDT-element array member resolution and variable/runtime index resolution parse structurally but are NOT resolved here (deferred to sub-projects 2 and 3).
- The real `briles_main_rev_023.L5K` is git-ignored customer data at `~/Downloads/briles_main_rev_023.L5K`; never commit it, and guard any test that reads it with `skipif` on its presence.
- Every commit must leave the full suite green.
- Degrade, never crash: an out-of-range index or an unresolved variable index appends a diagnostic and returns a default (read) / no-ops (write).

---

### Task 1: `2#` binary literal support

**Files:**
- Modify: `src/l5k_sim/values.py` (`is_literal`, `parse_literal`)
- Test: `tests/test_values.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `is_literal("2#1011")` → `True`; `parse_literal("2#1011")` → `11`. Later tasks rely on `parse_literal` accepting the `2#` form for array initializers.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_values.py`:

```python
def test_binary_literals():
    assert is_literal("2#0") and parse_literal("2#0") == 0
    assert is_literal("2#1") and parse_literal("2#1") == 1
    assert is_literal("2#1011") and parse_literal("2#1011") == 11
    assert is_literal("2#0000_1111") and parse_literal("2#0000_1111") == 15
    assert not is_literal("2#")          # empty binary body is not a literal
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_values.py::test_binary_literals -v`
Expected: FAIL (`is_literal("2#0")` is currently False; `parse_literal("2#0")` raises `ValueError`).

- [ ] **Step 3: Implement binary literal support**

In `src/l5k_sim/values.py`, add a binary regex next to the existing literal regexes (after the `_HEX` line):

```python
_BIN = re.compile(r"^2#[01][01_]*$")
```

Update `is_literal` to include it:

```python
def is_literal(s: str) -> bool:
    t = s.strip()
    return bool(_DEC_INT.match(t) or _FLOAT.match(t) or _HEX.match(t) or _BIN.match(t))
```

Update `parse_literal` to handle it (add the binary branch before the hex branch):

```python
def parse_literal(s: str) -> int | float | bool:
    t = s.strip()
    if _BIN.match(t):
        return int(t[2:].replace("_", ""), 2)
    if _HEX.match(t):
        return int(t[3:].replace("_", ""), 16)
    if _FLOAT.match(t):
        return float(t)
    return int(t)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_values.py -v`
Expected: PASS (new test and all existing values tests).

- [ ] **Step 5: Commit**

```bash
git add src/l5k_sim/values.py tests/test_values.py
git commit -m "feat(l5k-sim): support 2# binary literals"
```

---

### Task 2: Typed path segments, parse_ref rewrite, and indexed read/write walk

This is the core addressing change. `parse_ref` emits typed segments and `tagdb.read`/`write` walk them generically. The change spans `values.py`, `tagdb.py`, and one line of `engine.py` (sharing the per-scan diagnostics list so degrade messages surface). Existing bit/member behavior is preserved.

**Files:**
- Modify: `src/l5k_sim/values.py` (add `Index`/`Bit`/`VarIndex`, rewrite `parse_ref`, update `Ref` annotation)
- Modify: `src/l5k_sim/tagdb.py` (import new segments, add `self.diagnostics`, rewrite `read`/`write`)
- Modify: `src/l5k_sim/engine.py` (share the per-scan diagnostics list with the tag DB)
- Test: `tests/test_values.py`, `tests/test_tagdb.py`

**Interfaces:**
- Consumes: `parse_literal` with `2#` support (Task 1).
- Produces:
  - `Index(i: int)`, `Bit(n: int)`, `VarIndex(name: str)` frozen dataclasses exported from `l5k_sim.values`.
  - `parse_ref(s)` returns `Ref(base, path)` where `path` is a tuple whose elements are `Index` / `Bit` / `VarIndex` / `str` (member).
  - `TagDatabase` gains `self.diagnostics: list[str]`; out-of-range index and `VarIndex` append to it and degrade. Later tasks rely on `read`/`write` resolving `Index` into Python lists.

- [ ] **Step 1: Write the failing tests**

In `tests/test_values.py`, add the import for the new segment types at the top:

```python
from l5k_sim.values import Ref, Index, Bit, VarIndex, is_literal, parse_literal, looks_like_expr, parse_ref
```

Update the existing `test_parse_ref_member_and_bit` so the two numeric-segment lines use `Bit`:

```python
    assert parse_ref("v37.01") == Ref("v37", (Bit(1),))   # numeric segment -> bit index
    assert parse_ref("ons.0") == Ref("ons", (Bit(0),))
```

Add a new test for indexed tokenization:

```python
def test_parse_ref_typed_segments():
    assert parse_ref("arr[0]") == Ref("arr", (Index(0),))
    assert parse_ref("arr[3].10") == Ref("arr", (Index(3), Bit(10)))
    assert parse_ref("rec.system[2]") == Ref("rec", ("system", Index(2)))
    assert parse_ref("rec.system[2].flag") == Ref("rec", ("system", Index(2), "flag"))
    assert parse_ref("arr[FAULT_BIT_CTR]") == Ref("arr", (VarIndex("FAULT_BIT_CTR"),))
    assert parse_ref("Local:3:I.Data[3]") == Ref("Local:3:I", ("Data", Index(3)))
```

In `tests/test_tagdb.py`, add the import and three tests:

```python
from l5k_sim.ir import Controller, DataType, Member, Program, Project, Tag
from l5k_sim.tagdb import TagDatabase


def test_array_index_read_write():
    db = TagDatabase.from_project(_project())
    db.write("P", "step", 0)            # ensure scope P exists
    db.write("P", "arr", [10, 20, 30])  # whole-array write creates the list
    assert db.read("P", "arr") == [10, 20, 30]
    assert db.read("P", "arr[1]") == 20
    db.write("P", "arr[1]", 99)
    assert db.read("P", "arr[1]") == 99
    assert db.read("P", "arr") == [10, 99, 30]


def test_bit_after_index_round_trips():
    db = TagDatabase.from_project(_project())
    db.write("P", "words", [0, 0])
    assert db.read("P", "words[1].3") is False
    db.write("P", "words[1].3", True)
    assert db.read("P", "words[1].3") is True
    assert db.read("P", "words[1]") == 8       # bit 3 set on element 1
    assert db.read("P", "words[0]") == 0       # element 0 untouched


def test_array_index_out_of_range_degrades():
    db = TagDatabase.from_project(_project())
    db.write("P", "arr", [1, 2, 3])
    assert db.read("P", "arr[9]") == 0          # degrades to default, no raise
    db.write("P", "arr[9]", 5)                  # no-op, no raise
    assert db.read("P", "arr") == [1, 2, 3]     # unchanged
    assert any("index out of range" in d for d in db.diagnostics)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_values.py::test_parse_ref_typed_segments tests/test_tagdb.py::test_array_index_read_write tests/test_tagdb.py::test_bit_after_index_round_trips tests/test_tagdb.py::test_array_index_out_of_range_degrades -v`
Expected: FAIL with `ImportError: cannot import name 'Index'` (and related).

- [ ] **Step 3: Add typed segments and rewrite `parse_ref`**

In `src/l5k_sim/values.py`, add the segment dataclasses after the `Ref` dataclass and update `Ref`'s annotation:

```python
@dataclass(frozen=True)
class Index:
    i: int          # constant array index, e.g. [3]


@dataclass(frozen=True)
class Bit:
    n: int          # numeric bit access, e.g. .5


@dataclass(frozen=True)
class VarIndex:
    name: str       # non-constant index, e.g. [FAULT_BIT_CTR]; resolved in a later sub-project


@dataclass(frozen=True)
class Ref:
    base: str
    path: tuple[Index | Bit | VarIndex | str, ...]
```

(Delete the old `Ref` definition — there must be exactly one `Ref` class.)

Replace `parse_ref` with the tokenizer:

```python
_REF_SEG = re.compile(r"\.([^.\[]+)|\[([^\]]*)\]")


def parse_ref(s: str) -> Ref:
    t = s.strip()
    m = re.match(r"[^.\[]+", t)
    base = m.group(0) if m else t
    rest = t[m.end():] if m else ""
    segs: list[Index | Bit | VarIndex | str] = []
    for tok in _REF_SEG.finditer(rest):
        dot, brk = tok.group(1), tok.group(2)
        if dot is not None:
            segs.append(Bit(int(dot)) if dot.isdigit() else dot)
        else:
            inner = brk.strip()
            segs.append(Index(int(inner)) if inner.isdigit() else VarIndex(inner))
    return Ref(base, tuple(segs))
```

- [ ] **Step 4: Rewrite the tag DB walk to handle typed segments**

In `src/l5k_sim/tagdb.py`, update the values import to include the new segment types:

```python
from l5k_sim.values import Bit, Index, VarIndex, is_literal, parse_literal, parse_ref
```

Add a diagnostics list in `__init__` (next to the existing attributes):

```python
        self.diagnostics: list[str] = []
```

Replace `read` and `write` entirely with the typed-segment walk:

```python
    def read(self, scope: str, operand: str) -> Any:
        if is_literal(operand):
            return parse_literal(operand)
        ref = parse_ref(operand)
        container = self._container_for(scope, ref.base)
        val = container[ref.base]
        for seg in ref.path:
            if isinstance(seg, Bit):
                return bool((int(val) >> seg.n) & 1)
            if isinstance(seg, Index):
                if not isinstance(val, list) or not (0 <= seg.i < len(val)):
                    self.diagnostics.append(f"index out of range: {operand}")
                    return 0
                val = val[seg.i]
            elif isinstance(seg, VarIndex):
                self.diagnostics.append(f"unresolved variable index: {operand}")
                return 0
            else:  # member (str)
                val = val[seg]
        return val

    def write(self, scope: str, operand: str, value: Any) -> None:
        ref = parse_ref(operand)
        container = self._container_for(scope, ref.base)
        if not ref.path:
            container[ref.base] = value
            return
        # Navigate to the (holder, key) that owns the final segment.
        holder: Any = container
        key: Any = ref.base
        for seg in ref.path[:-1]:
            parent_val = holder[key]
            if isinstance(seg, Index):
                if not isinstance(parent_val, list) or not (0 <= seg.i < len(parent_val)):
                    self.diagnostics.append(f"index out of range: {operand}")
                    return
                holder, key = parent_val, seg.i
            elif isinstance(seg, VarIndex):
                self.diagnostics.append(f"unresolved variable index: {operand}")
                return
            else:  # member (str)
                holder, key = parent_val, seg
        leaf = ref.path[-1]
        if isinstance(leaf, Bit):
            cur = int(holder[key])
            holder[key] = (cur | (1 << leaf.n)) if value else (cur & ~(1 << leaf.n))
        elif isinstance(leaf, Index):
            target = holder[key]
            if not isinstance(target, list) or not (0 <= leaf.i < len(target)):
                self.diagnostics.append(f"index out of range: {operand}")
                return
            target[leaf.i] = value
        elif isinstance(leaf, VarIndex):
            self.diagnostics.append(f"unresolved variable index: {operand}")
            return
        else:  # member (str)
            holder[key][leaf] = value
```

- [ ] **Step 5: Share the per-scan diagnostics list with the tag DB**

In `src/l5k_sim/engine.py`, in the `scan` method, immediately after the line `self.diagnostics = []`, add:

```python
        self.db.diagnostics = self.diagnostics
```

This makes any degrade diagnostic the tag DB appends during a scan land in the engine's per-scan diagnostics.

- [ ] **Step 6: Run the new tests, then the full suite**

Run: `.venv/bin/python -m pytest tests/test_values.py tests/test_tagdb.py -v`
Expected: PASS — new tests plus all migrated/existing values and tagdb tests.

Run: `.venv/bin/python -m pytest -q`
Expected: `102 passed`. (After Task 1 the suite is at 98; this task adds 4 new test functions — `test_parse_ref_typed_segments` in test_values, plus `test_array_index_read_write`, `test_bit_after_index_round_trips`, `test_array_index_out_of_range_degrades` in test_tagdb — and modifies one existing test in place.)

- [ ] **Step 7: Commit**

```bash
git add src/l5k_sim/values.py src/l5k_sim/tagdb.py src/l5k_sim/engine.py tests/test_values.py tests/test_tagdb.py
git commit -m "feat(l5k-sim): typed ref segments and generic indexed read/write walk"
```

---

### Task 3: Array-tag initialization

Teach `_init_type` to recognize an array type string `TYPE[N]` and build a list of `N` initialized element values.

**Files:**
- Modify: `src/l5k_sim/tagdb.py` (`_init_type`)
- Test: `tests/test_tagdb.py`

**Interfaces:**
- Consumes: the indexed read walk (Task 2).
- Produces: a tag whose `data_type` is `TYPE[N]` initializes to a Python list of length `N`. Task 4 layers aggregate initializers onto this.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tagdb.py`:

```python
def test_array_tag_inits_to_list():
    tags = [Tag("counts", "INT[12]", "P", None, None, None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [], [], [Program("P", None, tags, [])])))
    counts = db.read("P", "counts")
    assert isinstance(counts, list) and len(counts) == 12 and counts == [0] * 12
    assert db.read("P", "counts[5]") == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_tagdb.py::test_array_tag_inits_to_list -v`
Expected: FAIL — `_init_type("INT[12]", None)` currently falls through to the scalar fallback and returns `0`, so `read` returns `0` (not a list).

- [ ] **Step 3: Add array detection to `_init_type`**

In `src/l5k_sim/tagdb.py`, add an array regex near the top of the module (next to `_TIMER`/`_COUNTER`):

```python
import re

_ARRAY = re.compile(r"^(\w+)\[(\d+)\]$")
```

In `_init_type`, add an array branch immediately before the `if data_type in self._udts:` branch:

```python
        arr = _ARRAY.match(data_type.strip())
        if arr:
            elem_type, n = arr.group(1), int(arr.group(2))
            return [self._init_type(elem_type, None) for _ in range(n)]
```

- [ ] **Step 4: Run the test, then the full suite**

Run: `.venv/bin/python -m pytest tests/test_tagdb.py::test_array_tag_inits_to_list -v`
Expected: PASS.

Run: `.venv/bin/python -m pytest -q`
Expected: `103 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/l5k_sim/tagdb.py tests/test_tagdb.py
git commit -m "feat(l5k-sim): initialize array-typed tags as lists"
```

---

### Task 4: Aggregate-initializer parsing

Apply a tag's aggregate initializer (`[v0,v1,…]`, including `2#` binary literals) to its array elements, padding short initializers with the element default and ignoring overflow.

**Files:**
- Modify: `src/l5k_sim/tagdb.py` (array branch of `_init_type`, new `_init_array` helper)
- Test: `tests/test_tagdb.py`

**Interfaces:**
- Consumes: array init (Task 3), `split_top_level` from `scan.py`, `2#` literals (Task 1).
- Produces: an array tag whose `initial` is an aggregate populates element values; per-element coercion follows the element type.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tagdb.py`:

```python
def test_aggregate_initializer_scalar():
    tags = [Tag("counts", "INT[12]", "P", None, "[0,0,0,0,0,0,0,0,0,0,2,0]", None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [], [], [Program("P", None, tags, [])])))
    assert db.read("P", "counts[10]") == 2
    assert db.read("P", "counts[0]") == 0
    assert db.read("P", "counts") == [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0]


def test_aggregate_initializer_binary_bool():
    tags = [Tag("flags", "BOOL[4]", "P", None, "[2#1,2#0,2#1,2#0]", None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [], [], [Program("P", None, tags, [])])))
    assert db.read("P", "flags") == [True, False, True, False]


def test_aggregate_initializer_short_pads_with_default():
    tags = [Tag("counts", "INT[5]", "P", None, "[7,8]", None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [], [], [Program("P", None, tags, [])])))
    assert db.read("P", "counts") == [7, 8, 0, 0, 0]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_tagdb.py::test_aggregate_initializer_scalar tests/test_tagdb.py::test_aggregate_initializer_binary_bool tests/test_tagdb.py::test_aggregate_initializer_short_pads_with_default -v`
Expected: FAIL — Task 3 ignores `initial`, so all elements are the default.

- [ ] **Step 3: Add the `_init_array` helper and wire it in**

In `src/l5k_sim/tagdb.py`, add the `split_top_level` import:

```python
from l5k_sim.scan import split_top_level
```

Add the helper method to `TagDatabase`:

```python
    def _init_array(self, elem_type: str, n: int, initial: str | None) -> list:
        out = [self._init_type(elem_type, None) for _ in range(n)]
        if not initial:
            return out
        s = initial.strip()
        if not (s.startswith("[") and s.endswith("]")):
            return out
        items = split_top_level(s[1:-1])
        for i, item in enumerate(items):
            if i >= n:
                self.diagnostics.append(f"array initializer longer than dim {n}: {initial}")
                break
            item = item.strip()
            if item:
                out[i] = self._init_type(elem_type, item)
        return out
```

Change the array branch of `_init_type` (added in Task 3) to delegate to the helper so the initializer is applied:

```python
        arr = _ARRAY.match(data_type.strip())
        if arr:
            return self._init_array(arr.group(1), int(arr.group(2)), initial)
```

- [ ] **Step 4: Run the tests, then the full suite**

Run: `.venv/bin/python -m pytest tests/test_tagdb.py -v`
Expected: PASS — the three new tests plus all existing tagdb tests.

Run: `.venv/bin/python -m pytest -q`
Expected: `106 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/l5k_sim/tagdb.py tests/test_tagdb.py
git commit -m "feat(l5k-sim): apply aggregate initializers to scalar array tags"
```

---

### Task 5: Guarded real-file regression

Prove on the real Briles file that a known array tag initializes from its aggregate initializer and reads correctly through an index, and that scanning does not crash.

**Files:**
- Modify: `tests/test_real_file_regression.py` (add one test)

**Interfaces:**
- Consumes: the full pipeline as built by Tasks 1–4.
- Produces: nothing for later tasks (final verification).

- [ ] **Step 1: Add the guarded regression test**

Append to `tests/test_real_file_regression.py` (the module already defines `REAL`, `pytestmark`, `parse_l5k`, and `ScanEngine`):

```python
def test_array_tag_initializer_resolves_on_real_file():
    engine = ScanEngine(parse_l5k(REAL))
    # Cam_Cut_Dwell_Select : INT[12] := [0,0,0,0,0,0,0,0,0,0,2,0] in MainProgram scope.
    assert engine.db.read("MainProgram", "Cam_Cut_Dwell_Select[10]") == 2
    assert engine.db.read("MainProgram", "Cam_Cut_Dwell_Select[0]") == 0
    engine.run(5)  # must not raise
```

- [ ] **Step 2: Run the regression test**

Run: `.venv/bin/python -m pytest tests/test_real_file_regression.py -v`
Expected: PASS (the real file is present on the dev machine, so the test RUNS; if absent it is `skipped`).

If skipped, verify manually:
```bash
PYTHONPATH=src .venv/bin/python -c "from l5k_sim.l5k_parser import parse_l5k; from l5k_sim.engine import ScanEngine; e=ScanEngine(parse_l5k('$HOME/Downloads/briles_main_rev_023.L5K')); print(e.db.read('MainProgram','Cam_Cut_Dwell_Select[10]'))"
```
Expected: prints `2`.

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: `107 passed` (or `106 passed, 1 skipped` if the real file is absent).

- [ ] **Step 4: Commit**

```bash
git add tests/test_real_file_regression.py
git commit -m "test(l5k-sim): guard real-file array initializer + indexed read"
```

---

## Self-Review

**Spec coverage:**
- `2#` binary literals → Task 1. ✓
- Typed segments (`Index`/`Bit`/`VarIndex`) + `parse_ref` rewrite → Task 2. ✓
- Generic indexed read/write walk (Index/Bit/member; whole-array read; out-of-range + VarIndex degrade with diagnostic) → Task 2. ✓
- Diagnostics surfaced via shared per-scan list → Task 2 (engine.py). ✓
- Array-tag init as lists → Task 3. ✓
- Aggregate-initializer parsing (scalar, `2#`, padding, overflow diagnostic) → Task 4. ✓
- Guarded real-file regression (`Cam_Cut_Dwell_Select[10] == 2`, no crash) → Task 5. ✓
- Deferred (UDT-element array resolution, variable index resolution, I/O colon tags, multi-dim) → intentionally not tasked; documented in the spec's Known limitations. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows complete code. ✓

**Type consistency:** `Index(i)`, `Bit(n)`, `VarIndex(name)` are used identically across Tasks 2–4. `parse_ref` returns `Ref(base, path)` with those segment types; `read`/`write` branch on `isinstance(seg, Bit|Index|VarIndex)` else member-`str`. `_init_array(elem_type, n, initial)` signature matches its caller in `_init_type`. `db.diagnostics` is introduced in Task 2 and reused by `_init_array` in Task 4. Test counts increment monotonically (97 → 98 → 102 → 103 → 106 → 107). ✓
