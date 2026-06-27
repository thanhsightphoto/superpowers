from __future__ import annotations

_PAIRS = {"(": ")", "[": "]"}
_CLOSERS = {v: k for k, v in _PAIRS.items()}


def find_matching(s: str, open_idx: int) -> int:
    opener = s[open_idx]
    if opener not in _PAIRS:
        raise ValueError(f"char at {open_idx} is not an opener: {opener!r}")
    depth = 0
    for i in range(open_idx, len(s)):
        ch = s[i]
        if ch in _PAIRS:
            depth += 1
        elif ch in _CLOSERS:
            depth -= 1
            if depth == 0:
                return i
    raise ValueError(f"unbalanced {opener!r} starting at {open_idx} in {s!r}")


def split_top_level(s: str, sep: str = ",") -> list[str]:
    pieces: list[str] = []
    depth = 0
    start = 0
    for i, ch in enumerate(s):
        if ch in _PAIRS:
            depth += 1
        elif ch in _CLOSERS:
            depth -= 1
        elif ch == sep and depth == 0:
            pieces.append(s[start:i].strip())
            start = i + 1
    pieces.append(s[start:].strip())
    return pieces
