from __future__ import annotations

from l5k_sim.ir import Branch, Instruction, RungElement
from l5k_sim.scan import find_matching, split_top_level

_IDENT = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_")


def parse_rung(text: str) -> list[RungElement]:
    s = text.strip()
    if s.endswith(";"):
        s = s[:-1].strip()
    return _parse_sequence(s)


def _parse_sequence(s: str) -> list[RungElement]:
    elements: list[RungElement] = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "[":
            close = find_matching(s, i)
            elements.append(_parse_branch(s[i + 1:close]))
            i = close + 1
            continue
        # otherwise: an instruction MNEMONIC(args)
        if ch not in _IDENT:
            raise ValueError(f"unexpected character {ch!r} at {i} in {s!r}")
        j = i
        while j < n and s[j] in _IDENT:
            j += 1
        mnemonic = s[i:j]
        if j >= n or s[j] != "(":
            raise ValueError(f"expected '(' after mnemonic {mnemonic!r} at {i} in {s!r}")
        close = find_matching(s, j)
        arg_str = s[j + 1:close]
        operands = [] if arg_str.strip() == "" else split_top_level(arg_str)
        elements.append(Instruction(mnemonic, operands, f"{mnemonic}({arg_str})"))
        i = close + 1
    return elements


def _parse_branch(inner: str) -> Branch:
    legs = [_parse_sequence(leg) for leg in split_top_level(inner)]
    return Branch(legs)
