from __future__ import annotations

import re

from l5k_sim.blocks import Block, scan_blocks
from l5k_sim.decls import parse_routine_block, parse_tag_block
from l5k_sim.ir import (
    AOIDef, Controller, DataType, Program, Project, Routine, Tag,
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
    return Project(_build_controller(controller_block))


def _build_controller(block: Block) -> Controller:
    name = block.header.strip().split(None, 1)[0] if block.header.strip() else ""
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
            datatypes.append(_build_datatype(child))
        elif child.keyword == "ADD_ON_INSTRUCTION_DEFINITION":
            aois.append(_build_aoi(child))
        elif child.keyword == "PROGRAM":
            programs.append(_build_program(child))

    return Controller(name=name, processor=processor, controller_tags=controller_tags,
                      datatypes=datatypes, aois=aois, programs=programs)


def _build_datatype(block: Block) -> DataType:
    name = block.header.strip().split(None, 1)[0] if block.header.strip() else ""
    members: list[tuple[str, str]] = []
    for line in block.body_lines:
        s = line.strip()
        if s.endswith(";") and " : " in s:
            mname, rest = s[:-1].split(" : ", 1)
            mtype = rest.strip().split(None, 1)[0].rstrip(";")
            members.append((mname.strip(), mtype))
    return DataType(name=name, members=members)


def _build_aoi(block: Block) -> AOIDef:
    name = block.header.strip().split(None, 1)[0] if block.header.strip() else ""
    params: list[Tag] = []
    logic: Routine | None = None
    for child in block.children:
        if child.keyword in ("PARAMETERS", "LOCAL_TAGS"):
            params.extend(parse_tag_block(child, scope=name))
        elif child.keyword == "ROUTINE":
            routine = parse_routine_block(child)
            if routine.name == "Logic" or logic is None:
                logic = routine
    return AOIDef(name=name, parameters=params, logic=logic)


def _build_program(block: Block) -> Program:
    name = block.header.strip().split(None, 1)[0] if block.header.strip() else ""
    main_match = _MAIN_RE.search(block.header)
    main_routine = main_match.group(1) if main_match else None
    tags: list[Tag] = []
    routines: list[Routine] = []
    for child in block.children:
        if child.keyword == "TAG":
            tags.extend(parse_tag_block(child, scope=name))
        elif child.keyword == "ROUTINE":
            routines.append(parse_routine_block(child))
    return Program(name=name, main_routine=main_routine, tags=tags, routines=routines)
