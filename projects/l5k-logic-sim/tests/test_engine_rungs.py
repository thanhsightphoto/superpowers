# tests/test_engine_rungs.py
from l5k_sim.ir import Branch, Controller, Instruction, Program, Project, Routine, Rung, Tag
from l5k_sim.engine import ScanEngine


def _engine(tags, routine) -> ScanEngine:
    prog = Program("P", "Main", tags, [routine])
    return ScanEngine(Project(Controller("C", "x", [], [], [], [prog])))


def _rung(*elements):
    return Rung(0, None, list(elements), "")


def test_xic_oturns_on_ote_when_input_true():
    tags = [Tag("a", "BOOL", "P", None, "1", None), Tag("y", "BOOL", "P", None, "0", None)]
    r = _rung(Instruction("XIC", ["a"], ""), Instruction("OTE", ["y"], ""))
    eng = _engine(tags, Routine("Main", None, [r]))
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "y") is True


def test_xio_blocks_and_ote_deenergizes():
    tags = [Tag("a", "BOOL", "P", None, "1", None), Tag("y", "BOOL", "P", None, "1", None)]
    r = _rung(Instruction("XIO", ["a"], ""), Instruction("OTE", ["y"], ""))
    eng = _engine(tags, Routine("Main", None, [r]))
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "y") is False  # OTE follows rung power every scan


def test_parallel_branch_is_or():
    tags = [Tag("a", "BOOL", "P", None, "0", None), Tag("b", "BOOL", "P", None, "1", None),
            Tag("y", "BOOL", "P", None, "0", None)]
    # [XIC(a) , XIC(b)] OTE(y)  -> y = a OR b
    branch = Branch([[Instruction("XIC", ["a"], "")], [Instruction("XIC", ["b"], "")]])
    r = _rung(branch, Instruction("OTE", ["y"], ""))
    eng = _engine(tags, Routine("Main", None, [r]))
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "y") is True


def test_otl_latches_and_otu_unlatches_only_when_powered():
    tags = [Tag("a", "BOOL", "P", None, "0", None), Tag("y", "BOOL", "P", None, "0", None)]
    # OTL with no power should NOT latch
    r = _rung(Instruction("XIC", ["a"], ""), Instruction("OTL", ["y"], ""))
    eng = _engine(tags, Routine("Main", None, [r]))
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "y") is False
    eng.db.write("P", "a", True)
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "y") is True


def test_jsr_calls_subroutine():
    tags = [Tag("y", "BOOL", "P", None, "0", None)]
    sub = Routine("Sub", None, [_rung(Instruction("OTE", ["y"], ""))])
    main = Routine("Main", None, [_rung(Instruction("JSR", ["Sub", "0"], ""))])
    prog = Program("P", "Main", tags, [main, sub])
    eng = ScanEngine(Project(Controller("C", "x", [], [], [], [prog])))
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "y") is True


def test_branch_side_effects_fire_in_all_legs():
    tags = [Tag("a", "BOOL", "P", None, "1", None),
            Tag("b", "BOOL", "P", None, "1", None),
            Tag("ya", "BOOL", "P", None, "0", None),
            Tag("yb", "BOOL", "P", None, "0", None)]
    branch = Branch([
        [Instruction("XIC", ["a"], ""), Instruction("OTE", ["ya"], "")],
        [Instruction("XIC", ["b"], ""), Instruction("OTE", ["yb"], "")],
    ])
    r = _rung(branch)
    eng = _engine(tags, Routine("Main", None, [r]))
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "ya") is True
    assert eng.db.read("P", "yb") is True   # fires even though leg[0] already succeeded


def test_unknown_mnemonic_records_diagnostic_and_passes_through():
    tags = [Tag("y", "BOOL", "P", None, "0", None)]
    r = _rung(Instruction("WIDGET", ["z"], ""), Instruction("OTE", ["y"], ""))
    eng = _engine(tags, Routine("Main", None, [r]))
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "y") is True  # passed through
    assert any("WIDGET" in d for d in eng.diagnostics)
