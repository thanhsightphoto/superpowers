# L5K Logic Sim

Offline tool to ingest a Rockwell **L5K** export, interpret the logic, and
**simulate it visually** (RSLogix-online feel — rungs light up, run/single-step,
force tags, modify live) so logic can be validated *before* going on-site.

Independent project parked in this Superpowers fork for cross-laptop syncing.
**Not** part of the Superpowers plugin; never PR upstream.

- **Design / notes:** [`2026-06-27-design.md`](2026-06-27-design.md) — start here.
- **Status:** design approved (Approach 2: custom parser + scan engine + web UI,
  vertical-slice-first). Next: implementation plan.

> Customer project files (`*.L5K`, `*.L5X`, `*.ACD`) are git-ignored — keep them local.
