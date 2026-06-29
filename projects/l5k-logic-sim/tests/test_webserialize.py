import json
from l5k_sim.ir import Controller, Instruction, Program, Project, Routine, Rung, Tag
from l5k_sim.engine import ScanEngine
from l5k_sim.webserialize import serialize_ir, serialize_state


def _project():
    r = Rung(0, "cmt", [Instruction("XIC", ["a"], "XIC(a)"), Instruction("OTE", ["y"], "OTE(y)")], "XIC(a)OTE(y)")
    prog = Program("P", "Main", [Tag("a", "BOOL", "P", None, "1", None), Tag("y", "BOOL", "P", None, "0", None)],
                   [Routine("Main", None, [r])])
    return Project(Controller("C", "1769", [], [], [], [prog]))


def test_serialize_ir_is_json_and_has_programs():
    d = serialize_ir(_project())
    json.dumps(d)  # must not raise
    assert d["programs"][0]["name"] == "P"
    rung = d["programs"][0]["routines"][0]["rungs"][0]
    assert rung["number"] == 0 and rung["comment"] == "cmt"
    assert rung["elements"][0]["mnemonic"] == "XIC"


def test_serialize_state_shape():
    eng = ScanEngine(_project())
    eng.scan()
    s = serialize_state(eng)
    json.dumps(s)  # must not raise
    assert set(s) == {"time_ms", "diagnostics", "trace", "tags"}
    assert s["time_ms"] == eng.scan_period_ms
    assert s["trace"]["P/Main/0.0"] is True
    assert s["tags"]["programs"]["P"]["y"] is True
