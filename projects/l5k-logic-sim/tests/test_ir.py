import json

import pytest

from l5k_sim.ir import (
    Instruction, Branch, Rung, Routine, Tag, AOIDef, DataType,
    Program, Controller, Project, project_to_dict, project_from_dict,
    _element_from_dict,
)


def _sample_project() -> Project:
    rung = Rung(
        number=0,
        comment="cycle cmd",
        elements=[
            Instruction("EQ", ["step", "40"], "EQ(step,40)"),
            Branch(legs=[
                [Instruction("OTE", ["a"], "OTE(a)")],
                [Instruction("OTE", ["b"], "OTE(b)")],
            ]),
        ],
        raw="EQ(step,40)[OTE(a) ,OTE(b) ]",
    )
    routine = Routine("Outputs", "DOC | maps step to outputs", [rung])
    prog = Program("Mode_1", "Main", [Tag("step", "DINT", "Mode_1", None, "0", "state")], [routine])
    ctrl = Controller("Sutherland", "1769-L30ERMS", [], [DataType("ud", [("m", "BOOL")])],
                      [AOIDef("scaler_dint", [Tag("In", "DINT", "scaler_dint", "Input", None, None)], None)],
                      [prog])
    return Project(ctrl, diagnostics=["unsupported: FOO at Mode_1/Outputs rung 3"])


def test_project_json_round_trip_is_lossless():
    p = _sample_project()
    blob = json.dumps(project_to_dict(p))
    back = project_from_dict(json.loads(blob))
    assert project_to_dict(back) == project_to_dict(p)


def test_branch_round_trips_with_kind_discriminator():
    p = _sample_project()
    d = project_to_dict(p)
    rung0 = d["controller"]["programs"][0]["routines"][0]["rungs"][0]
    assert rung0["elements"][0]["kind"] == "instruction"
    assert rung0["elements"][1]["kind"] == "branch"


def test_unknown_element_kind_raises():
    with pytest.raises(ValueError):
        _element_from_dict({"kind": "bogus"})
