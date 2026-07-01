from __future__ import annotations

import re
from dataclasses import dataclass

_DEC_INT = re.compile(r"^[+-]?\d+$")
_FLOAT = re.compile(r"^[+-]?\d+\.\d+$")
_FLOAT_EXP = re.compile(r"^[+-]?\d+\.?\d*[eE][+-]?\d+$")
_BIN = re.compile(r"^2#[01][01_]*$")
_HEX = re.compile(r"^16#[0-9A-Fa-f][0-9A-Fa-f_]*$")
_EXPR_CHARS = re.compile(r"[-+*/]|\s")


@dataclass(frozen=True)
class Index:
    i: int          # constant array index, e.g. [3]


@dataclass(frozen=True)
class Bit:
    n: int          # numeric bit access, e.g. .5


@dataclass(frozen=True)
class VarIndex:
    name: str       # non-constant index, e.g. [FAULT_BIT_CTR]; resolved in a later sub-project


@dataclass(frozen=True)
class Ref:
    base: str
    path: tuple[Index | Bit | VarIndex | str, ...]


def is_literal(s: str) -> bool:
    t = s.strip()
    return bool(_DEC_INT.match(t) or _FLOAT.match(t) or _FLOAT_EXP.match(t) or _BIN.match(t) or _HEX.match(t))


def parse_literal(s: str) -> int | float | bool:
    t = s.strip()
    if _BIN.match(t):
        return int(t[2:].replace("_", ""), 2)
    if _HEX.match(t):
        return int(t[3:].replace("_", ""), 16)
    if _FLOAT.match(t) or _FLOAT_EXP.match(t):
        return float(t)
    return int(t)


def looks_like_expr(s: str) -> bool:
    t = s.strip()
    if is_literal(t):
        return False
    # a plain ref (possibly dotted) has no operators or internal spaces
    return bool(_EXPR_CHARS.search(t))


_REF_SEG = re.compile(r"\.([^.\[]+)|\[([^\]]*)\]")


def parse_ref(s: str) -> Ref:
    t = s.strip()
    m = re.match(r"[^.\[]+", t)
    base = m.group(0) if m else t
    rest = t[m.end():] if m else ""
    segs: list[Index | Bit | VarIndex | str] = []
    for tok in _REF_SEG.finditer(rest):
        dot, brk = tok.group(1), tok.group(2)
        if dot is not None:
            segs.append(Bit(int(dot)) if dot.isdigit() else dot)
        else:
            inner = brk.strip()
            segs.append(Index(int(inner)) if inner.isdigit() else VarIndex(inner))
    return Ref(base, tuple(segs))
