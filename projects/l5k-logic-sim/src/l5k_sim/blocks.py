from __future__ import annotations

from dataclasses import dataclass, field

OPENERS = {
    "CONTROLLER", "DATATYPE", "ADD_ON_INSTRUCTION_DEFINITION", "PROGRAM",
    "ROUTINE", "TAG", "TASK", "MODULE", "PARAMETERS", "LOCAL_TAGS",
}


@dataclass
class Block:
    keyword: str
    header: str
    body_lines: list[str] = field(default_factory=list)
    children: list[Block] = field(default_factory=list)


def _first_token(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""
    return stripped.split(None, 1)[0]


def scan_blocks(text: str) -> list[Block]:
    lines = text.splitlines()
    pos = 0

    def parse_top_level() -> list[Block]:
        nonlocal pos
        result: list[Block] = []
        while pos < len(lines):
            token = _first_token(lines[pos])
            if token in OPENERS:
                result.append(parse_one(token))
            else:
                pos += 1  # stray line, ignore
        return result

    def parse_one(keyword: str) -> Block:
        nonlocal pos
        # gather header across continuation lines until parens balance / line has no '('
        header_parts: list[str] = []
        first = lines[pos].strip()
        header_parts.append(first[len(keyword):].strip())
        pos += 1
        depth = header_parts[0].count("(") - header_parts[0].count(")")
        while depth > 0 and pos < len(lines):
            cont = lines[pos]
            header_parts.append(cont.strip())
            depth += cont.count("(") - cont.count(")")
            pos += 1
        block = Block(keyword=keyword, header=" ".join(p for p in header_parts if p))
        # body + children until END_<keyword>
        while pos < len(lines):
            token = _first_token(lines[pos])
            if token == f"END_{keyword}":
                pos += 1
                break
            if token in OPENERS:
                block.children.append(parse_one(token))
            else:
                block.body_lines.append(lines[pos])
                pos += 1
        return block

    return parse_top_level()
