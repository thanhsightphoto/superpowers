from l5k_sim.ir import Controller, Instruction, Program, Project, Routine, Rung, Tag
from l5k_sim.engine import ScanEngine


def _eng(tags, *elements):
    r = Rung(0, None, list(elements), "")
    prog = Program("P", "Main", tags, [Routine("Main", None, [r])])
    return ScanEngine(Project(Controller("C", "x", [], [], [], [prog])))


def test_move_literal_and_tag():
    tags = [Tag("dst", "DINT", "P", None, "0", None), Tag("src", "DINT", "P", None, "7", None)]
    eng = _eng(tags, Instruction("MOVE", ["40", "dst"], ""))
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "dst") == 40
    eng2 = _eng(tags, Instruction("MOVE", ["src", "dst"], ""))
    eng2.call_routine("P", "Main")
    assert eng2.db.read("P", "dst") == 7


def test_math_ops():
    tags = [Tag("a", "DINT", "P", None, "10", None), Tag("b", "DINT", "P", None, "3", None),
            Tag("d", "DINT", "P", None, "0", None)]
    eng = _eng(tags, Instruction("SUB", ["a", "b", "d"], ""))
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "d") == 7


def test_cpt_expression():
    tags = [Tag("v1", "DINT", "P", None, "100", None), Tag("v2", "DINT", "P", None, "40", None),
            Tag("period", "DINT", "P", None, "60", None), Tag("speed", "REAL", "P", None, None, None)]
    eng = _eng(tags, Instruction("CPT", ["speed", "(v1 - v2) * 60000 / period"], ""))
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "speed") == (100 - 40) * 60000 / 60


def test_compare_gates_output():
    tags = [Tag("step", "DINT", "P", None, "40", None), Tag("y", "BOOL", "P", None, "0", None)]
    eng = _eng(tags, Instruction("EQ", ["step", "40"], ""), Instruction("OTE", ["y"], ""))
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "y") is True
    eng.db.write("P", "step", 41)
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "y") is False


def test_limit_inclusive():
    tags = [Tag("t", "DINT", "P", None, "5", None), Tag("y", "BOOL", "P", None, "0", None)]
    eng = _eng(tags, Instruction("LIMIT", ["1", "t", "10"], ""), Instruction("OTE", ["y"], ""))
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "y") is True
