from __future__ import annotations

import re

from l5k_sim.blocks import Block
from l5k_sim.ir import Routine, Rung, Tag
from l5k_sim.rung_parser import parse_rung
from l5k_sim.scan import find_matching

_DESC_RE = re.compile(r'Description\s*:=\s*"((?:[^"\\]|\\.)*)"')
_USAGE_RE = re.compile(r'Usage\s*:=\s*(\w+)')


def _join_statements(lines: list[str]) -> list[str]:
    """Join physical lines into logical statements terminated by ';'."""
    statements: list[str] = []
    buf = ""
    for ln in lines:
        buf = ln if not buf else buf + " " + ln.strip()
        if ln.rstrip().endswith(";"):
            statements.append(buf.strip())
            buf = ""
    if buf.strip():
        statements.append(buf.strip())
    return statements


def parse_tag_block(block: Block, scope: str) -> list[Tag]:
    tags: list[Tag] = []
    for stmt in _join_statements(block.body_lines):
        s = stmt[:-1].strip() if stmt.endswith(";") else stmt.strip()
        if " : " not in s:
            continue
        name, rest = s.split(" : ", 1)
        name = name.strip()
        # initial value = tail after the last top-level ':='
        initial = None
        depth = 0
        cut = -1
        i = 0
        while i < len(rest) - 1:
            ch = rest[i]
            if ch in "([":
                depth += 1
            elif ch in ")]":
                depth -= 1
            elif depth == 0 and rest[i:i + 2] == ":=":
                cut = i
            i += 1
        if cut != -1:
            initial = rest[cut + 2:].strip()
            rest = rest[:cut].strip()
        # attribute group (...) carries Description / Usage
        description = None
        usage = None
        paren = rest.find("(")
        if paren != -1:
            close = find_matching(rest, paren)
            attrs = rest[paren + 1:close]
            data_type = rest[:paren].strip()
            md = _DESC_RE.search(attrs)
            if md:
                description = md.group(1)
            mu = _USAGE_RE.search(attrs)
            if mu:
                usage = mu.group(1)
        else:
            data_type = rest.strip()
        tags.append(Tag(name, data_type, scope, usage, initial, description))
    return tags


def parse_routine_block(block: Block) -> Routine:
    name = block.header.strip().split(None, 1)[0] if block.header.strip() else ""
    description = None
    rungs: list[Rung] = []
    pending_comment: str | None = None
    number = 0
    for stmt in _join_statements(block.body_lines):
        if stmt.startswith("RC:"):
            comment = _extract_quoted(stmt)
            if comment is not None and comment.startswith("DOC |") and not rungs and description is None:
                description = comment
            else:
                pending_comment = comment
        elif stmt.startswith("N:"):
            rll = stmt[len("N:"):].strip()
            rungs.append(Rung(number=number, comment=pending_comment,
                              elements=parse_rung(rll), raw=rll[:-1] if rll.endswith(";") else rll))
            number += 1
            pending_comment = None
    return Routine(name=name, description=description, rungs=rungs)


def _extract_quoted(stmt: str) -> str | None:
    start = stmt.find('"')
    if start == -1:
        return None
    end = stmt.rfind('"')
    if end <= start:
        return None
    return stmt[start + 1:end]
