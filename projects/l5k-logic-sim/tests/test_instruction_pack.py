from l5k_sim.ir import Controller, Instruction, Program, Project, Tag
from l5k_sim.engine import ScanEngine


def _engine(tags):
    prog = Program("P", None, tags, [])
    return ScanEngine(Project(Controller("C", "x", [], [], [], [prog])))


def _run(e, mnem, operands, power=True):
    return e._eval_instruction("P", Instruction(mnem, operands, f"{mnem}(...)"), power)


def test_clr_sets_zero_when_powered():
    e = _engine([Tag("d", "DINT", "P", None, "42", None)])
    _run(e, "CLR", ["d"])
    assert e.db.read("P", "d") == 0


def test_clr_noop_when_unpowered():
    e = _engine([Tag("d", "DINT", "P", None, "42", None)])
    _run(e, "CLR", ["d"], power=False)
    assert e.db.read("P", "d") == 42


def test_abs():
    e = _engine([Tag("s", "DINT", "P", None, "-7", None), Tag("d", "DINT", "P", None, "0", None)])
    _run(e, "ABS", ["s", "d"])
    assert e.db.read("P", "d") == 7


def test_neg():
    e = _engine([Tag("s", "DINT", "P", None, "5", None), Tag("d", "DINT", "P", None, "0", None)])
    _run(e, "NEG", ["s", "d"])
    assert e.db.read("P", "d") == -5


def test_mod():
    e = _engine([Tag("a", "DINT", "P", None, "17", None), Tag("b", "DINT", "P", None, "5", None),
                 Tag("d", "DINT", "P", None, "0", None)])
    _run(e, "MOD", ["a", "b", "d"])
    assert e.db.read("P", "d") == 2


def test_mod_by_zero_degrades():
    e = _engine([Tag("a", "DINT", "P", None, "17", None), Tag("b", "DINT", "P", None, "0", None),
                 Tag("d", "DINT", "P", None, "9", None)])
    _run(e, "MOD", ["a", "b", "d"])
    assert e.db.read("P", "d") == 9
    assert any("MOD by zero" in x for x in e.diagnostics)


def test_cop_copies_elements():
    e = _engine([Tag("s", "DINT[3]", "P", None, "[1,2,3]", None),
                 Tag("d", "DINT[3]", "P", None, "[0,0,0]", None)])
    _run(e, "COP", ["s", "d", "3"])
    assert e.db.read("P", "d") == [1, 2, 3]


def test_cop_independent_and_bounds():
    e = _engine([Tag("s", "DINT[3]", "P", None, "[1,2,3]", None),
                 Tag("d", "DINT[3]", "P", None, "[0,0,0]", None)])
    _run(e, "COP", ["s", "d", "3"])
    e.db.write("P", "s[0]", 99)
    assert e.db.read("P", "d[0]") == 1        # copy is independent of source
    _run(e, "COP", ["s", "d", "99"])          # length beyond array bounds
    assert any("out of range" in x for x in e.diagnostics)
