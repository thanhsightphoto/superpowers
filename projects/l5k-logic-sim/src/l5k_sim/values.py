from __future__ import annotations

import re
from dataclasses import dataclass

_DEC_INT = re.compile(r"^[+-]?\d+$")
_FLOAT = re.compile(r"^[+-]?\d+\.\d+$")
_HEX = re.compile(r"^16#[0-9A-Fa-f_]+$")
_EXPR_CHARS = re.compile(r"[+\-*/]| ")


@dataclass(frozen=True)
class Ref:
    base: str
    path: tuple[str | int, ...]


def is_literal(s: str) -> bool:
    t = s.strip()
    return bool(_DEC_INT.match(t) or _FLOAT.match(t) or _HEX.match(t))


def parse_literal(s: str) -> int | float | bool:
    t = s.strip()
    if _HEX.match(t):
        return int(t[3:].replace("_", ""), 16)
    if _FLOAT.match(t):
        return float(t)
    return int(t)


def looks_like_expr(s: str) -> bool:
    t = s.strip()
    if is_literal(t):
        return False
    # a plain ref (possibly dotted) has no operators or internal spaces
    return bool(_EXPR_CHARS.search(t))


def parse_ref(s: str) -> Ref:
    t = s.strip()
    parts = t.split(".")
    base = parts[0]
    segs: list[str | int] = []
    for p in parts[1:]:
        segs.append(int(p) if p.isdigit() else p)
    return Ref(base, tuple(segs))
