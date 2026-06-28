from __future__ import annotations

from typing import Callable

HANDLERS: dict[str, Callable] = {}


def register(*mnemonics: str):
    def deco(fn: Callable) -> Callable:
        for m in mnemonics:
            HANDLERS[m] = fn
        return fn
    return deco


@register("NOP")
def _nop(engine, scope, instr, power_in):
    return power_in


@register("AFI")
def _afi(engine, scope, instr, power_in):
    return False


@register("XIC")
def _xic(engine, scope, instr, power_in):
    return power_in and bool(engine._operand(scope, instr.operands[0]))


@register("XIO")
def _xio(engine, scope, instr, power_in):
    return power_in and not bool(engine._operand(scope, instr.operands[0]))


@register("OTE")
def _ote(engine, scope, instr, power_in):
    engine.db.write(scope, instr.operands[0], bool(power_in))
    return power_in


@register("OTL")
def _otl(engine, scope, instr, power_in):
    if power_in:
        engine.db.write(scope, instr.operands[0], True)
    return power_in


@register("OTU")
def _otu(engine, scope, instr, power_in):
    if power_in:
        engine.db.write(scope, instr.operands[0], False)
    return power_in


@register("JSR")
def _jsr(engine, scope, instr, power_in):
    if power_in and instr.operands:
        engine.call_routine(scope, instr.operands[0])
    return power_in
