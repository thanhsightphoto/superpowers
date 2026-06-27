from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Instruction:
    mnemonic: str
    operands: list[str]
    raw: str


@dataclass
class Branch:
    legs: "list[list[RungElement]]"


RungElement = Instruction | Branch


@dataclass
class Rung:
    number: int
    comment: str | None
    elements: list[RungElement]
    raw: str


@dataclass
class Routine:
    name: str
    description: str | None
    rungs: list[Rung] = field(default_factory=list)


@dataclass
class Tag:
    name: str
    data_type: str
    scope: str
    usage: str | None
    initial: str | None
    description: str | None


@dataclass
class AOIDef:
    name: str
    parameters: list[Tag]
    logic: Routine | None


@dataclass
class DataType:
    name: str
    members: list[tuple[str, str]]


@dataclass
class Program:
    name: str
    main_routine: str | None
    tags: list[Tag] = field(default_factory=list)
    routines: list[Routine] = field(default_factory=list)


@dataclass
class Controller:
    name: str
    processor: str
    controller_tags: list[Tag] = field(default_factory=list)
    datatypes: list[DataType] = field(default_factory=list)
    aois: list[AOIDef] = field(default_factory=list)
    programs: list[Program] = field(default_factory=list)


@dataclass
class Project:
    controller: Controller
    diagnostics: list[str] = field(default_factory=list)


# ---- serialization (explicit, so the RungElement union stays unambiguous) ----

def _element_to_dict(e: RungElement) -> dict:
    if isinstance(e, Instruction):
        return {"kind": "instruction", "mnemonic": e.mnemonic, "operands": list(e.operands), "raw": e.raw}
    return {"kind": "branch", "legs": [[_element_to_dict(x) for x in leg] for leg in e.legs]}


def _element_from_dict(d: dict) -> RungElement:
    if d["kind"] == "instruction":
        return Instruction(d["mnemonic"], list(d["operands"]), d["raw"])
    return Branch([[_element_from_dict(x) for x in leg] for leg in d["legs"]])


def _tag_to_dict(t: Tag) -> dict:
    return {"name": t.name, "data_type": t.data_type, "scope": t.scope,
            "usage": t.usage, "initial": t.initial, "description": t.description}


def _tag_from_dict(d: dict) -> Tag:
    return Tag(d["name"], d["data_type"], d["scope"], d["usage"], d["initial"], d["description"])


def _rung_to_dict(r: Rung) -> dict:
    return {"number": r.number, "comment": r.comment,
            "elements": [_element_to_dict(e) for e in r.elements], "raw": r.raw}


def _rung_from_dict(d: dict) -> Rung:
    return Rung(d["number"], d["comment"], [_element_from_dict(e) for e in d["elements"]], d["raw"])


def _routine_to_dict(r: Routine) -> dict:
    return {"name": r.name, "description": r.description, "rungs": [_rung_to_dict(x) for x in r.rungs]}


def _routine_from_dict(d: dict) -> Routine:
    return Routine(d["name"], d["description"], [_rung_from_dict(x) for x in d["rungs"]])


def project_to_dict(p: Project) -> dict:
    c = p.controller
    return {
        "diagnostics": list(p.diagnostics),
        "controller": {
            "name": c.name,
            "processor": c.processor,
            "controller_tags": [_tag_to_dict(t) for t in c.controller_tags],
            "datatypes": [{"name": dt.name, "members": [list(m) for m in dt.members]} for dt in c.datatypes],
            "aois": [{"name": a.name,
                      "parameters": [_tag_to_dict(t) for t in a.parameters],
                      "logic": _routine_to_dict(a.logic) if a.logic else None} for a in c.aois],
            "programs": [{"name": pr.name, "main_routine": pr.main_routine,
                          "tags": [_tag_to_dict(t) for t in pr.tags],
                          "routines": [_routine_to_dict(r) for r in pr.routines]} for pr in c.programs],
        },
    }


def project_from_dict(d: dict) -> Project:
    cd = d["controller"]
    ctrl = Controller(
        name=cd["name"], processor=cd["processor"],
        controller_tags=[_tag_from_dict(t) for t in cd["controller_tags"]],
        datatypes=[DataType(x["name"], [tuple(m) for m in x["members"]]) for x in cd["datatypes"]],
        aois=[AOIDef(a["name"], [_tag_from_dict(t) for t in a["parameters"]],
                     _routine_from_dict(a["logic"]) if a["logic"] else None) for a in cd["aois"]],
        programs=[Program(pr["name"], pr["main_routine"],
                          [_tag_from_dict(t) for t in pr["tags"]],
                          [_routine_from_dict(r) for r in pr["routines"]]) for pr in cd["programs"]],
    )
    return Project(ctrl, diagnostics=list(d["diagnostics"]))
