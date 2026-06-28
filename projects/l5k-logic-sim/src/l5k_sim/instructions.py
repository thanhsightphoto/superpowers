from __future__ import annotations

from typing import Callable

HANDLERS: dict[str, Callable] = {}


def register(*mnemonics: str) -> Callable[[Callable], Callable]:
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


@register("ONS")
def _ons(engine, scope, instr, power_in):
    storage = instr.operands[0]
    prev = bool(engine.db.read(scope, storage))
    engine.db.write(scope, storage, bool(power_in))
    return power_in and not prev


@register("OSF")
def _osf(engine, scope, instr, power_in):
    storage = instr.operands[0]
    prev = bool(engine.db.read(scope, storage))
    engine.db.write(scope, storage, bool(power_in))
    return (not power_in) and prev


@register("TON")
def _ton(engine, scope, instr, power_in):
    name = instr.operands[0]
    pre = int(engine.db.read(scope, f"{name}.PRE"))
    acc = int(engine.db.read(scope, f"{name}.ACC"))
    if power_in:
        engine.db.write(scope, f"{name}.EN", True)
        dn = bool(engine.db.read(scope, f"{name}.DN"))
        if not dn:
            acc = min(pre, acc + engine.scan_period_ms)
        engine.db.write(scope, f"{name}.ACC", acc)
        done = acc >= pre
        engine.db.write(scope, f"{name}.DN", done)
        engine.db.write(scope, f"{name}.TT", not done)
        return done
    engine.db.write(scope, f"{name}.EN", False)
    engine.db.write(scope, f"{name}.TT", False)
    engine.db.write(scope, f"{name}.DN", False)
    engine.db.write(scope, f"{name}.ACC", 0)
    return False


@register("RES")
def _res(engine, scope, instr, power_in):
    if power_in:
        name = instr.operands[0]
        for member in ("ACC", "DN", "TT", "EN", "CU", "CD", "prev_cu"):
            try:
                engine.db.write(scope, f"{name}.{member}", 0 if member == "ACC" else False)
            except (KeyError, TypeError):
                pass
    return power_in


@register("CTU")
def _ctu(engine, scope, instr, power_in):
    name = instr.operands[0]
    pre = int(engine.db.read(scope, f"{name}.PRE"))
    acc = int(engine.db.read(scope, f"{name}.ACC"))
    prev = bool(engine.db.read(scope, f"{name}.prev_cu"))
    if power_in and not prev:
        acc += 1
        engine.db.write(scope, f"{name}.ACC", acc)
    engine.db.write(scope, f"{name}.prev_cu", bool(power_in))
    done = acc >= pre
    engine.db.write(scope, f"{name}.DN", done)
    return done
