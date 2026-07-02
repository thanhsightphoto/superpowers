# AOI Required-Parameter Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse each AOI parameter's `Required := Yes|No` attribute and use the required parameters (in declaration order) as the authoritative call-parameter set, so optional-param AOIs like `MisFeed` bind and execute instead of skipping on a count mismatch.

**Architecture:** Add a `required` field to `Tag`, parse `Required` in the tag/parameter parser, and change `invoke_aoi` to build `call_params` from required parameters when that information is present (falling back to the existing usage heuristic for parameter lists without it).

**Tech Stack:** Python 3.11 (project venv at `.venv`), standard library only, pytest.

## Global Constraints

- Python baseline is **3.11**. Use `.venv/bin/python` — never the system `python3` (it is 3.9.6).
- Run all commands from `projects/l5k-logic-sim/`. The full suite is currently **135 passing**.
- Standard library only; zero third-party dependencies.
- `Tag.required` is a trailing field defaulting to `None` — existing positional `Tag(...)` construction must keep working.
- The real `briles_main_rev_023.L5K` is git-ignored at `~/Downloads/briles_main_rev_023.L5K`; never commit it, guard real-file tests with `skipif`.
- Every commit must leave the full suite green.

---

### Task 1: `Tag.required` field, parsing, and serialization

**Files:**
- Modify: `src/l5k_sim/ir.py` (`Tag`, `_tag_to_dict`, `_tag_from_dict`)
- Modify: `src/l5k_sim/decls.py` (`parse_tag_block`)
- Modify: `tests/test_ir.py`, `tests/test_l5k_parser.py`

**Interfaces:**
- Produces: `Tag.required: bool | None` (default `None`); parser sets it from `Required := Yes|No`. Task 2 consumes it.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_l5k_parser.py`:

```python
def test_parse_required_attribute(tmp_path):
    text = (
        'CONTROLLER C (ProcessorType := "1769-L30ERMS")\n'
        '\tADD_ON_INSTRUCTION_DEFINITION myaoi (Class := Standard)\n'
        '\t\tPARAMETERS\n'
        '\t\t\tEnableIn : BOOL (Usage := Input, Required := No);\n'
        '\t\t\ta : DINT (Usage := Input, Required := Yes);\n'
        '\t\t\tb : DINT (Usage := Input, Required := No);\n'
        '\t\tEND_PARAMETERS\n'
        '\tEND_ADD_ON_INSTRUCTION_DEFINITION\n'
        'END_CONTROLLER\n'
    )
    f = tmp_path / "aoi.L5K"
    f.write_text(text)
    p = parse_l5k(str(f))
    params = {pm.name: pm for pm in p.controller.aois[0].parameters}
    assert params["EnableIn"].required is False
    assert params["a"].required is True
    assert params["b"].required is False
```

Add to `tests/test_ir.py` (ensure `Tag`, `AOIDef`, `Program`, `Controller`, `Project`, `project_to_dict`, `project_from_dict` are imported — most already are):

```python
def test_tag_required_survives_round_trip():
    t = Tag("p", "DINT", "aoi", "Input", None, None, required=True)
    aoi = AOIDef("aoi", [t], None)
    prog = Program("P", "Main", [], [])
    p = Project(Controller("C", "x", [], [], [aoi], [prog]))
    back = project_from_dict(json.loads(json.dumps(project_to_dict(p))))
    assert back.controller.aois[0].parameters[0].required is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_l5k_parser.py::test_parse_required_attribute tests/test_ir.py::test_tag_required_survives_round_trip -v`
Expected: FAIL — `Tag` has no `required` field (`TypeError` on the keyword) and the parser doesn't set it.

- [ ] **Step 3: Add the `Tag.required` field and serialization**

In `src/l5k_sim/ir.py`, add the trailing field to `Tag`:

```python
@dataclass
class Tag:
    name: str
    data_type: str
    scope: str
    usage: str | None
    initial: str | None
    description: str | None
    required: bool | None = None
```

Update `_tag_to_dict` to include it:

```python
def _tag_to_dict(t: Tag) -> dict:
    return {"name": t.name, "data_type": t.data_type, "scope": t.scope,
            "usage": t.usage, "initial": t.initial, "description": t.description,
            "required": t.required}
```

Update `_tag_from_dict` to read it (tolerating older blobs):

```python
def _tag_from_dict(d: dict) -> Tag:
    return Tag(d["name"], d["data_type"], d["scope"], d["usage"], d["initial"],
               d["description"], d.get("required"))
```

- [ ] **Step 4: Parse `Required` in `parse_tag_block`**

In `src/l5k_sim/decls.py`, add a regex next to `_USAGE_RE`:

```python
_REQUIRED_RE = re.compile(r'Required\s*:=\s*(Yes|No)')
```

In `parse_tag_block`, inside the block that parses the attribute group (where `usage` is set via `_USAGE_RE`), also extract `required` and pass it to `Tag`. Set `required = True` for `Yes`, `False` for `No`, leave `None` when absent. Change the final `Tag(...)` construction to include `required`:

```python
        required = None
        # ... within the `if paren != -1:` attribute-parsing branch, after usage:
        mr = _REQUIRED_RE.search(attrs)
        if mr:
            required = (mr.group(1) == "Yes")
        # ...
        tags.append(Tag(name, data_type, scope, usage, initial, description, required))
```

(Ensure `required` is initialized to `None` before the attribute branch so tags without an attribute group still construct correctly.)

- [ ] **Step 5: Run the tests, then the full suite**

Run: `.venv/bin/python -m pytest tests/test_l5k_parser.py tests/test_ir.py -v`
Expected: PASS (new tests plus existing parser/IR tests, including the existing lossless round-trip).

Run: `.venv/bin/python -m pytest -q`
Expected: `137 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/l5k_sim/ir.py src/l5k_sim/decls.py tests/test_ir.py tests/test_l5k_parser.py
git commit -m "feat(l5k-sim): parse AOI parameter Required attribute"
```

---

### Task 2: Required-based AOI call parameters

**Files:**
- Modify: `src/l5k_sim/engine.py` (`invoke_aoi`)
- Modify: `tests/test_aoi.py`

**Interfaces:**
- Consumes: `Tag.required` (Task 1).
- Produces: `invoke_aoi` builds `call_params` from required params when present; usage-heuristic fallback otherwise.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_aoi.py`:

```python
def _aoi_with_optional():
    # required params: in, out ; non-required extra input: spare (omitted from calls)
    params = [
        Tag("EnableIn", "BOOL", "opt", "Input", None, None, required=False),
        Tag("in", "DINT", "opt", "Input", None, None, required=True),
        Tag("spare", "DINT", "opt", "Input", None, None, required=False),
        Tag("out", "DINT", "opt", "Output", None, None, required=True),
    ]
    logic = Routine("Logic", None, [
        Rung(0, None, [Instruction("MOVE", ["in", "out"], "MOVE(in,out)")], "MOVE(in,out)"),
    ])
    return AOIDef("opt", params, logic)


def test_aoi_binds_only_required_params():
    prog_tags = [Tag("inst", "opt", "P", None, None, None),
                 Tag("src", "DINT", "P", None, "7", None),
                 Tag("dst", "DINT", "P", None, "0", None)]
    e = ScanEngine(Project(Controller("C", "x", [], [], [_aoi_with_optional()],
                                      [Program("P", None, prog_tags, [])])))
    # 2 args match the 2 required params (in, out); the non-required 'spare' is skipped
    e._eval_instruction("P", Instruction("opt", ["inst", "src", "dst"], "opt(inst,src,dst)"), True)
    assert e.db.read("P", "dst") == 7
    assert not any("args vs" in d for d in e.diagnostics)


def test_aoi_fallback_when_no_required_info():
    # params have required=None -> usage heuristic still applies (dbl from earlier helper)
    e = ScanEngine(_project())   # _project() uses _aoi_dbl() whose params have required=None
    _call(e)
    assert e.db.read("P", "dst") == 10
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_aoi.py::test_aoi_binds_only_required_params -v`
Expected: FAIL — the current heuristic counts `in`, `spare`, `out` (3 call params) vs 2 args → count-mismatch skip, so `dst` stays `0`.

- [ ] **Step 3: Use required params when present**

In `src/l5k_sim/engine.py`, in `invoke_aoi`, replace the current `call_params = [...]` computation with:

```python
        if any(p.required is not None for p in aoi.parameters):
            call_params = [p for p in aoi.parameters if p.required]
        else:
            call_params = [p for p in aoi.parameters
                           if p.usage in ("Input", "Output", "InOut")
                           and p.name not in ("EnableIn", "EnableOut")]
```

Leave the rest of `invoke_aoi` unchanged.

- [ ] **Step 4: Run the tests, then the full suite**

Run: `.venv/bin/python -m pytest tests/test_aoi.py -v`
Expected: PASS (new tests plus the existing AOI tests, which use `required=None` params and hit the fallback).

Run: `.venv/bin/python -m pytest -q`
Expected: `139 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/l5k_sim/engine.py tests/test_aoi.py
git commit -m "feat(l5k-sim): bind AOI calls by required parameters"
```

---

### Task 3: Guarded real-file regression

**Files:**
- Modify: `tests/test_real_file_regression.py`

**Interfaces:**
- Consumes: required-based binding (Tasks 1–2).
- Produces: nothing for later tasks (final verification).

- [ ] **Step 1: Add the guarded regression test**

Append to `tests/test_real_file_regression.py` (module already defines `REAL`, `pytestmark`, `parse_l5k`, `ScanEngine`):

```python
def test_misfeed_binds_on_real_file():
    engine = ScanEngine(parse_l5k(REAL))
    engine.scan("MainProgram")  # MainProgram hosts the 16 MisFeed calls; must not raise
    assert not any("MisFeed" in d and "args vs" in d for d in engine.diagnostics), \
        [d for d in engine.diagnostics if "MisFeed" in d]
```

- [ ] **Step 2: Run the regression test**

Run: `.venv/bin/python -m pytest tests/test_real_file_regression.py -v`
Expected: PASS (runs on the dev machine; skipped if the file is absent). MisFeed now binds its 12 required params to its 12 args, so no count-mismatch diagnostic.

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: `140 passed` (or `139 passed, 1 skipped` if the real file is absent).

- [ ] **Step 4: Commit**

```bash
git add tests/test_real_file_regression.py
git commit -m "test(l5k-sim): guard real-file MisFeed required-param binding"
```

---

## Self-Review

**Spec coverage:** `Tag.required` + parse + serialization → Task 1; required-based `call_params` with fallback → Task 2; guarded real-file MisFeed regression → Task 3. Deferred items (I/O tags, already-covered RTO) documented in the spec. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✓

**Type consistency:** `Tag.required: bool | None` used consistently across ir/decls/engine; `invoke_aoi` fallback preserves the exact prior heuristic for `required is None` params (so existing AOI tests pass). Test counts increment monotonically (135 → 137 → 139 → 140). ✓
