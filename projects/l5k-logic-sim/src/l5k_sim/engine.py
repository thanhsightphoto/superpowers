from __future__ import annotations

from typing import Any

from l5k_sim.ir import Branch, Instruction, Program, Project, Routine, Rung
from l5k_sim import instructions as _ins
from l5k_sim.expr import eval_expr
from l5k_sim.tagdb import TagDatabase
from l5k_sim.values import looks_like_expr


class ScanEngine:
    def __init__(self, project: Project, scan_period_ms: int = 10) -> None:
        self.project = project
        self.db = TagDatabase.from_project(project)
        self.scan_period_ms = scan_period_ms
        self.time_ms = 0
        self.diagnostics: list[str] = []
        self._programs: dict[str, Program] = {p.name: p for p in project.controller.programs}
        self.forced: dict[tuple[str, str], Any] = {}

    # ---- operand helpers ----
    def _operand(self, scope: str, s: str) -> Any:
        if looks_like_expr(s):
            return eval_expr(s, scope, self.db)
        return self.db.read(scope, s)

    # ---- evaluation ----
    def eval_elements(self, scope: str, elements: list[Instruction | Branch], power_in: bool) -> bool:
        power = power_in
        for el in elements:
            if isinstance(el, Branch):
                outs = [self.eval_elements(scope, leg, power) for leg in el.legs]
                power = any(outs)
            elif isinstance(el, Instruction):
                power = self._eval_instruction(scope, el, power)
        return power

    def _eval_instruction(self, scope: str, instr: Instruction, power_in: bool) -> bool:
        handler = _ins.HANDLERS.get(instr.mnemonic)
        if handler is None:
            self.diagnostics.append(f"unsupported instruction {instr.mnemonic} in {scope}")
            return power_in
        return handler(self, scope, instr, power_in)

    def eval_rung(self, scope: str, rung: Rung) -> None:
        self.eval_elements(scope, rung.elements, True)

    def call_routine(self, scope: str, routine_name: str) -> None:
        prog = self._programs.get(scope)
        if prog is None:
            self.diagnostics.append(f"missing program {scope}")
            return
        routine = next((r for r in prog.routines if r.name == routine_name), None)
        if routine is None:
            self.diagnostics.append(f"missing routine {routine_name} in {scope}")
            return
        for rung in routine.rungs:
            self.eval_rung(scope, rung)

    # ---- tag access API ----
    def get(self, scope: str, operand: str) -> Any:
        return self.db.read(scope, operand)

    def set(self, scope: str, operand: str, value: Any) -> None:
        self.db.write(scope, operand, value)

    def force(self, scope: str, operand: str, value: Any) -> None:
        self.forced[(scope, operand)] = value
        self.db.write(scope, operand, value)

    def _apply_forces(self) -> None:
        for (scope, operand), value in self.forced.items():
            self.db.write(scope, operand, value)

    # ---- scan loop ----
    def scan(self, program: str | None = None) -> None:
        prog = self._programs[program] if program else self.project.controller.programs[0]
        self.time_ms += self.scan_period_ms
        self._apply_forces()
        if prog.main_routine:
            self.call_routine(prog.name, prog.main_routine)
        self._apply_forces()  # forces win even over same-scan writes

    def run(self, n: int, program: str | None = None) -> None:
        for _ in range(n):
            self.scan(program)
