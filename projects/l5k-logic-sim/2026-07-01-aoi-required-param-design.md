# Design — AOI required-parameter binding (coverage sub-project 2)

Date: 2026-07-01
Status: Approved (design); implementation plan to follow
Branch: `project/l5k-logic-sim`

## Problem

AOI invocation (Plan 7) binds call arguments to an AOI's parameters positionally,
computing "call parameters" as `usage in (Input, Output, InOut)` minus
`EnableIn`/`EnableOut`. That heuristic is wrong for AOIs with **optional**
parameters: `MisFeed` has 13 such params but only 12 call arguments, because one
input parameter (`Input`) is marked `Required := No` and is omitted from the call.
Result: all 16 `MisFeed` call sites skip with a count-mismatch diagnostic.

Verified in the L5K: every AOI parameter carries a `Required := Yes|No` attribute.
`EnableIn`/`EnableOut` are `Required := No`; the visible call parameters are
exactly those with `Required := Yes`, in declaration order. This is the
authoritative source for the call-parameter list.

## Decisions

1. **Parse `Required` and use it as the authoritative call-parameter set.** Add a
   `required` field to `Tag`, parse `Required := Yes|No` in the tag/parameter
   parser, and build AOI call parameters from parameters with `required is True`,
   in declaration order. This drops `EnableIn`/`EnableOut` and optional params
   uniformly, fixing `MisFeed` and any other optional-param AOI.
2. **Preserve a fallback for parameter lists without `Required` info.** When no
   parameter of an AOI carries a `Required` value (e.g. hand-constructed AOIs in
   unit tests), keep the existing usage-based heuristic. This avoids breaking
   existing AOI tests while making real (parsed) AOIs authoritative.
3. **Backward-compatible `Tag`.** `required` is added as a trailing field with a
   default of `None`, so all existing positional `Tag(...)` construction (many
   tests) continues to work.

## Components

### 1. `Tag.required` — `src/l5k_sim/ir.py`

Add a trailing field:

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

Update `_tag_to_dict` / `_tag_from_dict` to round-trip `required` (emit the value;
read with `.get("required")` so older serialized blobs still load).

### 2. Parse `Required` — `src/l5k_sim/decls.py`

In `parse_tag_block`, add a `Required := Yes|No` extraction (a regex like the
existing `_USAGE_RE`), applied to the attribute group, and pass it into the `Tag`.
`Yes` → `True`, `No` → `False`, absent → `None`.

### 3. Required-based call parameters — `src/l5k_sim/engine.py`

In `invoke_aoi`, replace the call-parameter computation with:

```python
        if any(p.required is not None for p in aoi.parameters):
            call_params = [p for p in aoi.parameters if p.required]
        else:
            call_params = [p for p in aoi.parameters
                           if p.usage in ("Input", "Output", "InOut")
                           and p.name not in ("EnableIn", "EnableOut")]
```

Everything else in `invoke_aoi` (binding, Logic execution, copy-back) is
unchanged. Required params in declaration order match the call-argument order.

## Data flow

`parse_l5k` now records `required` on each AOI parameter → `invoke_aoi` builds
`call_params` from the required params → `MisFeed`'s 12 required params match its
12 call arguments, so it binds and executes instead of skipping.

## Error handling

Unchanged: a genuine count mismatch (after using the authoritative required set)
still appends a diagnostic and skips; a non-dict instance still skips. Never
raises.

## Testing strategy

TDD, one failing test per behavior:

- **Parse:** an AOI parameter with `Required := Yes` parses to `required is True`;
  `Required := No` → `False`; absent → `None`. (Inline `tmp_path` L5K.)
- **Serialization:** a `Tag` with `required` round-trips through
  `project_to_dict`/`project_from_dict`.
- **Binding via required:** an AOI whose parameters include a non-required extra
  input binds only the required params to the call args (a call with N args and
  N required params executes; the non-required param keeps its default).
- **Fallback preserved:** an AOI whose params have `required is None` still binds
  via the usage heuristic (existing behavior).
- **Guarded real-file regression:** after scanning `MainProgram`, there is no
  `MisFeed: … args vs … params` diagnostic (MisFeed now binds), and the scan does
  not crash.

The full suite (currently 135 passing) must stay green.

## Known limitations (documented, deferred)

- I/O-boundary tags that MisFeed's arguments reference (safety/field inputs)
  remain unmodeled — addressed by coverage sub-project 3 (I/O-tag modeling).
- `aoi_pulse_feedback_monitoring` uses `RTO` (now implemented in sub-project 1)
  and binds via required params here, so it also runs after this sub-project.
