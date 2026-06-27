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

**Plan 1 (custom parser → IR) COMPLETE** — built via subagent-driven development, all
7 tasks reviewed + final whole-branch review resolved. Full suite **38 tests passing**
on Python 3.11.15. Next: Plan 2 (scan engine).

| Task | What | State |
|------|------|-------|
| 1 | IR data model + JSON round-trip | ✅ |
| 2 | Depth-aware string helpers (`scan.py`) | ✅ |
| 3 | Rung parser — instructions | ✅ |
| 4 | Rung parser — nested branches | ✅ |
| 5 | Block scanner (`blocks.py`) | ✅ |
| 6 | Tag/routine decl parsers (`decls.py`) | ✅ |
| 7 | Project assembler + coverage (`l5k_parser.py`, `coverage.py`) | ✅ |

**Validated on a real 862 KB export** (`briles_main_rev_023.L5K`): parses end-to-end —
9 programs, 12 AOIs, 4,820 instructions, **98.2% in the v1 supported set**, 0 unparseable
rungs. The ~1.8% unsupported are the deferred AOI/encoder/string/comms instructions
(`MisFeed`, `Scroll`, `RIN`, `CLR`, `GSV`, `DTOS`, `RTO`, `TOF`, …) — the Plan-2+ roadmap.

### Try it
```bash
cd projects/l5k-logic-sim
PYTHONPATH=src .venv/bin/python -c "from l5k_sim.l5k_parser import parse_l5k; from l5k_sim.coverage import coverage_report; import json; print(json.dumps(coverage_report(parse_l5k('YOUR_FILE.L5K')), indent=2)[:600])"
```

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
