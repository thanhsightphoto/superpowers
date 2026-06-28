from l5k_sim.ir import Branch, Controller, Instruction, Program, Project, Routine, Rung, Tag
from l5k_sim.engine import ScanEngine


def _engine(tags, *elements):
    r = Rung(0, None, list(elements), "")
    prog = Program("P", "Main", tags, [Routine("Main", None, [r])])
    return ScanEngine(Project(Controller("C", "x", [], [], [], [prog])))


def test_trace_records_hot_elements_after_scan():
    tags = [Tag("a", "BOOL", "P", None, "1", None), Tag("y", "BOOL", "P", None, "0", None)]
    eng = _engine(tags, Instruction("XIC", ["a"], ""), Instruction("OTE", ["y"], ""))
    eng.scan()
    assert eng.trace["P/Main/0.0"] is True    # XIC conducted
    assert eng.trace["P/Main/0.1"] is True     # OTE energized


def test_trace_records_cold_elements():
    tags = [Tag("a", "BOOL", "P", None, "0", None), Tag("y", "BOOL", "P", None, "0", None)]
    eng = _engine(tags, Instruction("XIC", ["a"], ""), Instruction("OTE", ["y"], ""))
    eng.scan()
    assert eng.trace["P/Main/0.0"] is False
    assert eng.trace["P/Main/0.1"] is False


def test_trace_keys_branch_legs():
    tags = [Tag("a", "BOOL", "P", None, "0", None), Tag("b", "BOOL", "P", None, "1", None),
            Tag("y", "BOOL", "P", None, "0", None)]
    branch = Branch([[Instruction("XIC", ["a"], "")], [Instruction("XIC", ["b"], "")]])
    eng = _engine(tags, branch, Instruction("OTE", ["y"], ""))
    eng.scan()
    assert eng.trace["P/Main/0.0.0.0"] is False   # leg 0: XIC(a) cold
    assert eng.trace["P/Main/0.0.1.0"] is True     # leg 1: XIC(b) hot
    assert eng.trace["P/Main/0.1"] is True          # OTE after branch (a OR b)


def test_trace_cleared_each_scan():
    tags = [Tag("a", "BOOL", "P", None, "1", None), Tag("y", "BOOL", "P", None, "0", None)]
    eng = _engine(tags, Instruction("XIC", ["a"], ""), Instruction("OTE", ["y"], ""))
    eng.scan()
    eng.db.write("P", "a", False)
    eng.scan()
    assert eng.trace["P/Main/0.0"] is False        # reflects latest scan, not stale
