# L5K Logic Sim

Offline tool to ingest a Rockwell **L5K** export, interpret the logic, and
**simulate it visually** (RSLogix-online feel — rungs light up, run/single-step,
force tags, modify live) so logic can be validated *before* going on-site.

Independent project parked in this Superpowers fork for cross-laptop syncing.
**Not** part of the Superpowers plugin; never PR upstream.

## Docs

- **Design / notes:** [`2026-06-27-design.md`](2026-06-27-design.md) — start here.
- **Plan 1 (parser → IR):** [`2026-06-27-plan-01-parser.md`](2026-06-27-plan-01-parser.md)
- Plans 2 (scan engine) and 3 (web UI) follow after Plan 1 lands.

## Status

Executing **Plan 1** (custom parser → IR) via subagent-driven development.

| Task | What | State |
|------|------|-------|
| 1 | IR data model + JSON round-trip | ✅ done (`fbcaedb`, `f251e15`) |
| 2 | Depth-aware string helpers | ⬜ |
| 3 | Rung parser — instructions | ⬜ |
| 4 | Rung parser — branches | ⬜ |
| 5 | Block scanner | ⬜ |
| 6 | Tag/routine decl parsers | ⬜ |
| 7 | Project assembler + coverage | ⬜ |

## Dev setup

**Baseline: Python 3.11** (the system `python3` on macOS may be older — use 3.11 explicitly).

```bash
cd projects/l5k-logic-sim
python3.11 -m venv .venv            # one-time, per laptop
.venv/bin/python -m pip install -U pip pytest
.venv/bin/python -m pytest          # run the test suite
```

The `.venv/` is git-ignored, so recreate it on each laptop with the commands above.

> Customer project files (`*.L5K`, `*.L5X`, `*.ACD`) are git-ignored — keep them local.
> The only committed `*.L5K` is a tiny synthetic test fixture under `tests/fixtures/`.
