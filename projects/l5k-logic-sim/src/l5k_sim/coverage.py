from __future__ import annotations

from l5k_sim.ir import Branch, Instruction, Project, RungElement

SUPPORTED_V1: set[str] = {
    "XIC", "XIO", "OTE", "OTL", "OTU", "ONS", "OSF", "AFI", "NOP",
    "TON", "RES", "CTU", "MOVE", "MOV", "COP", "JSR",
    "EQ", "NE", "GT", "GE", "LT", "LE", "LIMIT",
    "ADD", "SUB", "MUL", "DIV", "CPT",
}


def _walk(elements: list[RungElement]):
    for e in elements:
        if isinstance(e, Instruction):
            yield e
        elif isinstance(e, Branch):
            for leg in e.legs:
                yield from _walk(leg)


def coverage_report(project: Project) -> dict:
    total = 0
    unsupported = 0
    unsupported_mnemonics: dict[str, int] = {}
    routines = []
    for prog in project.controller.programs:
        routines.extend(prog.routines)
    for aoi in project.controller.aois:
        if aoi.logic:
            routines.append(aoi.logic)
    for routine in routines:
        for rung in routine.rungs:
            for instr in _walk(rung.elements):
                total += 1
                if instr.mnemonic not in SUPPORTED_V1:
                    unsupported += 1
                    unsupported_mnemonics[instr.mnemonic] = unsupported_mnemonics.get(instr.mnemonic, 0) + 1
    supported = total - unsupported
    return {
        "total_instructions": total,
        "supported": supported,
        "unsupported": unsupported,
        "unsupported_mnemonics": unsupported_mnemonics,
        "supported_pct": (100.0 * supported / total) if total else 100.0,
    }
