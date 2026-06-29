from __future__ import annotations

from l5k_sim.engine import ScanEngine
from l5k_sim.ir import Project, project_to_dict


def serialize_ir(project: Project) -> dict:
    d = project_to_dict(project)
    d["programs"] = d["controller"]["programs"]
    d["controller_name"] = d["controller"]["name"]
    return d


def serialize_state(engine: ScanEngine) -> dict:
    return {
        "time_ms": engine.time_ms,
        "diagnostics": list(engine.diagnostics),
        "trace": dict(engine.trace),
        "tags": engine.db.snapshot(),
    }
