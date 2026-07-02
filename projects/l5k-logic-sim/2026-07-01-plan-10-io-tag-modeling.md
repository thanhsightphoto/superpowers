# Forgiving I/O / Module-Tag Modeling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make unmodeled I/O and module-defined tags forgiving and forceable — returning `0`/`False` defaults for any member/index/bit access and holding written/forced values — so the physical-I/O boundary stops degrading and downstream logic computes instead of skipping. Known UDT/AOI/array tags stay strict.

**Architecture:** Introduce an `IOStub(dict)` marker in `src/l5k_sim/tagdb.py`. Unmodeled-type tags initialize as `IOStub`; undeclared bases auto-create as `IOStub`. `read`/`write` gain an early forgiving branch for `IOStub` bases keyed by a canonical sub-path string. The existing strict walk is unchanged for real dicts/lists.

**Tech Stack:** Python 3.11 (project venv at `.venv`), standard library only, pytest.

## Global Constraints

- Python baseline is **3.11**. Use `.venv/bin/python` — never the system `python3` (it is 3.9.6).
- Run all commands from `projects/l5k-logic-sim/`. The full suite is currently **140 passing**.
- Standard library only; zero third-party dependencies.
- Boundary tags (unmodeled declared types + undeclared colon bases) are forgiving; **known UDT/AOI/array tags remain strict** (unchanged behavior).
- Forgiving reads return `0`/`False` defaults and append **no** diagnostic (expected I/O). Bare (empty-path) reads of a boundary base still return `0`.
- The real `briles_main_rev_023.L5K` is git-ignored at `~/Downloads/briles_main_rev_023.L5K`; never commit it, guard real-file tests with `skipif`.
- Every commit must leave the full suite green.

---

### Task 1: `IOStub` type, init, canonical sub-path, forgiving read/write

**Files:**
- Modify: `src/l5k_sim/tagdb.py`
- Modify: `tests/test_tagdb.py`

**Interfaces:**
- Consumes: `parse_ref` typed segments (`Index`, `Bit`, `VarIndex`, member-`str`), already imported in `tagdb.py`.
- Produces: `IOStub(dict)` marker; unmodeled/undeclared tags resolve forgivingly; `write`/`force` on them persist per-sub-path.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tagdb.py` (helper + tests):

```python
def _db(tags, datatypes=None):
    prog = Program("P", None, tags, [])
    return TagDatabase.from_project(
        Project(Controller("C", "x", [], datatypes or [], [], [prog])))


def test_unmodeled_type_tag_member_access_is_forgiving():
    db = _db([Tag("relay", "REDUNDANT_OUTPUT", "P", None, None, None)])
    assert db.read("P", "relay.O1") == 0           # forgiving default, no raise
    db.write("P", "relay.O1", True)
    assert db.read("P", "relay.O1") is True


def test_colon_io_tag_auto_creates_forgiving():
    db = _db([])
    assert db.read("P", "Local:4:I.Data[1]") == 0
    db.write("P", "Local:4:I.Data[1]", 55)
    assert db.read("P", "Local:4:I.Data[1]") == 55


def test_io_bit_subpath_default_and_hold():
    db = _db([])
    assert db.read("P", "Local:1:I.Data.5") is False
    db.write("P", "Local:1:I.Data.5", True)
    assert db.read("P", "Local:1:I.Data.5") is True


def test_bare_undeclared_read_still_zero():
    db = _db([])
    assert db.read("P", "never_written") == 0


def test_known_udt_stays_strict():
    from l5k_sim.tagdb import IOStub
    udt = DataType("blk", [Member("word", "DINT")])
    db = _db([Tag("u", "blk", "P", None, None, None)], datatypes=[udt])
    db.write("P", "u.word", 7)
    assert db.read("P", "u.word") == 7
    assert not isinstance(db.programs["P"]["u"], IOStub)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_tagdb.py::test_unmodeled_type_tag_member_access_is_forgiving tests/test_tagdb.py::test_colon_io_tag_auto_creates_forgiving tests/test_tagdb.py::test_io_bit_subpath_default_and_hold -v`
Expected: FAIL — today unmodeled/undeclared bases are scalar `0`, so `relay.O1` / `Local:4:I.Data[1]` raise (caught only at the engine layer, but at the DB layer these calls raise `TypeError`/`KeyError`).

- [ ] **Step 3: Add `IOStub`, the canonical helper, and init changes**

In `src/l5k_sim/tagdb.py`, add the marker class near the top (after the imports / struct constants):

```python
class IOStub(dict):
    """Forgiving store for an unmodeled I/O / module-defined tag.

    Keys are canonical sub-path strings; missing keys read as defaults.
    """
```

Add a module-level canonical-path helper (near `_ARRAY`):

```python
def _canon(path) -> str:
    out = ""
    for seg in path:
        if isinstance(seg, Index):
            out += f"[{seg.i}]"
        elif isinstance(seg, VarIndex):
            out += f"[{seg.name}]"
        elif isinstance(seg, Bit):
            out += f".{seg.n}"
        else:  # member str
            out += (f".{seg}" if out else str(seg))
    return out
```

Change the unknown-type fallback at the end of `_init_type` from `return 0` to:

```python
        return IOStub()  # unmodeled type -> forgiving, forceable I/O stub
```

In `_container_for`, change the auto-create of an undeclared base from
`prog[base] = 0` to:

```python
        prog[base] = IOStub()
```

- [ ] **Step 4: Add the forgiving branch to `read` and `write`**

In `read`, immediately after `val = container[ref.base]` and before the strict walk loop:

```python
        if isinstance(val, IOStub):
            if not ref.path:
                return 0
            default = False if isinstance(ref.path[-1], Bit) else 0
            return val.get(_canon(ref.path), default)
```

In `write`, immediately after resolving `container = self._container_for(scope, ref.base)` and before the existing `if not ref.path:` handling, add:

```python
        base_val = container[ref.base]
        if isinstance(base_val, IOStub):
            if not ref.path:
                container[ref.base] = value
            else:
                base_val[_canon(ref.path)] = value
            return
```

(The existing strict `read`/`write` logic runs only when the base value is not an `IOStub`.)

- [ ] **Step 5: Run the tests, then the full suite**

Run: `.venv/bin/python -m pytest tests/test_tagdb.py -v`
Expected: PASS — the 5 new tests plus all existing tagdb tests (known UDT/array/bit behavior unchanged).

Run: `.venv/bin/python -m pytest -q`
Expected: `145 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/l5k_sim/tagdb.py tests/test_tagdb.py
git commit -m "feat(l5k-sim): model unmodeled I/O tags as forgiving forceable stubs"
```

---

### Task 2: Guarded real-file regression

**Files:**
- Modify: `tests/test_real_file_regression.py`

**Interfaces:**
- Consumes: forgiving boundary tags (Task 1).
- Produces: nothing for later tasks (final verification).

- [ ] **Step 1: Add the guarded regression test**

Append to `tests/test_real_file_regression.py` (module already defines `REAL`, `pytestmark`, `parse_l5k`, `ScanEngine`):

```python
def test_no_io_subscript_degradation_on_real_file():
    engine = ScanEngine(parse_l5k(REAL))
    for prog in engine.project.controller.programs:
        engine.scan(prog.name)  # must not raise
        bad = [d for d in engine.diagnostics
               if "not subscriptable" in d or "does not support item assignment" in d]
        assert not bad, f"{prog.name}: I/O subscript degradations remain: {bad[:5]}"
```

- [ ] **Step 2: Run the regression test**

Run: `.venv/bin/python -m pytest tests/test_real_file_regression.py -v`
Expected: PASS (runs on the dev machine; skipped if the file is absent). Colon I/O and module-typed tags now resolve forgivingly, so no subscript degradations remain.

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: `146 passed` (or `145 passed, 1 skipped` if the real file is absent).

- [ ] **Step 4: Commit**

```bash
git add tests/test_real_file_regression.py
git commit -m "test(l5k-sim): guard real-file I/O boundary against subscript degradation"
```

---

## Self-Review

**Spec coverage:** `IOStub` + init (unknown→IOStub, auto-create→IOStub) + `_canon` + forgiving read/write → Task 1; guarded real-file regression → Task 2. Deferred items (niche instructions, word/bit coherence, no hardcoded layouts) documented in the spec. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✓

**Type consistency:** `IOStub(dict)` detected via `isinstance` in both `read` and `write`; `_canon(path)` consumes the same `Index`/`Bit`/`VarIndex`/str segments `parse_ref` emits; the forgiving branch precedes the strict walk in both methods so known tags are unaffected. Test counts increment monotonically (140 → 145 → 146). ✓
