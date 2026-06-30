from __future__ import annotations

import re

from l5k_sim.blocks import Block, scan_blocks, block_name
from l5k_sim.decls import parse_routine_block, parse_tag_block
from l5k_sim.scan import find_matching
from l5k_sim.ir import (
    AOIDef, Controller, DataType, Member, Program, Project, Routine, Tag,
)

_PROC_RE = re.compile(r'ProcessorType\s*:=\s*"([^"]+)"')
_MAIN_RE = re.compile(r'MAIN\s*:=\s*"([^"]+)"')


def parse_l5k(path: str) -> Project:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    top = scan_blocks(text)
    controller_block = next((b for b in top if b.keyword == "CONTROLLER"), None)
    if controller_block is None:
        return Project(Controller(name="", processor=""), diagnostics=["no CONTROLLER block"])
    diagnostics: list[str] = []
    controller = _build_controller(controller_block, diagnostics)
    return Project(controller, diagnostics)


def _build_controller(block: Block, diagnostics: list[str]) -> Controller:
    name = block_name(block)
    proc_match = _PROC_RE.search(block.header)
    processor = proc_match.group(1) if proc_match else ""

    controller_tags: list[Tag] = []
    datatypes: list[DataType] = []
    aois: list[AOIDef] = []
    programs: list[Program] = []

    for child in block.children:
        if child.keyword == "TAG":
            controller_tags.extend(parse_tag_block(child, scope="controller"))
        elif child.keyword == "DATATYPE":
            datatypes.append(_build_datatype(child, diagnostics))
        elif child.keyword == "ADD_ON_INSTRUCTION_DEFINITION":
            aois.append(_build_aoi(child, diagnostics))
        elif child.keyword == "PROGRAM":
            programs.append(_build_program(child, diagnostics))

    return Controller(name=name, processor=processor, controller_tags=controller_tags,
                      datatypes=datatypes, aois=aois, programs=programs)


def _build_datatype(block: Block, diagnostics: list[str] | None = None) -> DataType:
    name = block_name(block)
    members: list[Member] = []
    for line in block.body_lines:
        s = line.strip()
        if not s.endswith(";"):
            continue
        s = s[:-1].strip()
        try:
            # strip the outer (attrs) group, if present
            paren = s.find("(")
            if paren != -1:
                close = find_matching(s, paren)
                s = (s[:paren] + s[close + 1:]).strip()
            if not s:
                continue
            if s.startswith("BIT ") and ":" in s:
                head, bitpos = s.split(":", 1)
                toks = head.split()  # ["BIT", <name>, <host>]
                if len(toks) >= 3 and bitpos.strip().lstrip("+-").isdigit():
                    members.append(Member(toks[1], "BIT", bit_host=toks[2], bit_pos=int(bitpos.strip())))
                    continue
            # plain type-first member: "<TYPE> <name>[dim]?"
            toks = s.split(None, 1)
            if len(toks) != 2:
                continue
            mtype, mname = toks[0], toks[1].strip()
            dim = None
            if mname.endswith("]") and "[" in mname:
                base, _, rest = mname.partition("[")
                inner = rest[:-1].strip()
                if inner.isdigit():
                    dim = int(inner)
                    mname = base.strip()
            members.append(Member(mname, mtype, dim=dim))
        except Exception as exc:
            if diagnostics is not None:
                diagnostics.append(f"malformed datatype member in {name!r}: {line.strip()} ({exc})")
            continue
    return DataType(name=name, members=members)


def _build_aoi(block: Block, diagnostics: list[str]) -> AOIDef:
    name = block_name(block)
    params: list[Tag] = []
    logic: Routine | None = None
    for child in block.children:
        if child.keyword in ("PARAMETERS", "LOCAL_TAGS"):
            params.extend(parse_tag_block(child, scope=name))
        elif child.keyword == "ROUTINE":
            routine = parse_routine_block(child, diagnostics)
            if routine.name == "Logic" or logic is None:
                logic = routine
    return AOIDef(name=name, parameters=params, logic=logic)


def _build_program(block: Block, diagnostics: list[str]) -> Program:
    name = block_name(block)
    main_match = _MAIN_RE.search(block.header)
    main_routine = main_match.group(1) if main_match else None
    tags: list[Tag] = []
    routines: list[Routine] = []
    for child in block.children:
        if child.keyword == "TAG":
            tags.extend(parse_tag_block(child, scope=name))
        elif child.keyword == "ROUTINE":
            routines.append(parse_routine_block(child, diagnostics))
    return Program(name=name, main_routine=main_routine, tags=tags, routines=routines)
