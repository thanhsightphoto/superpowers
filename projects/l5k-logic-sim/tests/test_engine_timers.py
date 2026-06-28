# tests/test_engine_timers.py
from l5k_sim.ir import Controller, Instruction, Program, Project, Routine, Rung, Tag
from l5k_sim.engine import ScanEngine


def _eng(tags, *elements, period=50):
    r = Rung(0, None, list(elements), "")
    prog = Program("P", "Main", tags, [Routine("Main", None, [r])])
    return ScanEngine(Project(Controller("C", "x", [], [], [], [prog])), scan_period_ms=period)


def test_ton_accrues_and_sets_dn():
    tags = [Tag("en", "BOOL", "P", None, "1", None), Tag("t", "TIMER", "P", None, None, None)]
    eng = _eng(tags, Instruction("XIC", ["en"], ""), Instruction("TON", ["t", "?", "?"], ""), period=50)
    eng.db.write("P", "t.PRE", 100)
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "t.ACC") == 50 and eng.db.read("P", "t.DN") is False
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "t.ACC") == 100 and eng.db.read("P", "t.DN") is True


def test_ton_resets_when_input_drops():
    tags = [Tag("en", "BOOL", "P", None, "1", None), Tag("t", "TIMER", "P", None, None, None)]
    eng = _eng(tags, Instruction("XIC", ["en"], ""), Instruction("TON", ["t", "?", "?"], ""), period=50)
    eng.db.write("P", "t.PRE", 100)
    eng.call_routine("P", "Main")
    eng.db.write("P", "en", False)
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "t.ACC") == 0 and eng.db.read("P", "t.DN") is False


def test_ctu_counts_rising_edges_only():
    tags = [Tag("in", "BOOL", "P", None, "0", None), Tag("c", "COUNTER", "P", None, None, None)]
    eng = _eng(tags, Instruction("XIC", ["in"], ""), Instruction("CTU", ["c", "?", "?"], ""))
    eng.db.write("P", "c.PRE", 2)
    eng.db.write("P", "in", True)
    eng.call_routine("P", "Main")       # rising edge -> 1
    eng.call_routine("P", "Main")       # held high -> still 1
    assert eng.db.read("P", "c.ACC") == 1
    eng.db.write("P", "in", False)
    eng.call_routine("P", "Main")
    eng.db.write("P", "in", True)
    eng.call_routine("P", "Main")       # new rising edge -> 2
    assert eng.db.read("P", "c.ACC") == 2 and eng.db.read("P", "c.DN") is True


def test_ons_pulses_one_scan():
    tags = [Tag("in", "BOOL", "P", None, "1", None), Tag("s", "DINT", "P", None, "0", None),
            Tag("y", "DINT", "P", None, "0", None)]
    # XIC(in) ONS(s.0) and count how many scans it passes by incrementing via OTL on a bit
    eng = _eng(tags, Instruction("XIC", ["in"], ""), Instruction("ONS", ["s.0"], ""),
               Instruction("OTL", ["y.0"], ""))
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "y.0") is True   # latched on the rising-edge scan
    eng.db.write("P", "y.0", False)
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "y.0") is False  # ONS no longer passes on the second scan


def test_osf_pulses_on_falling_edge():
    tags = [Tag("in", "BOOL", "P", None, "1", None), Tag("s", "DINT", "P", None, "0", None),
            Tag("y", "DINT", "P", None, "0", None)]
    eng = _eng(tags, Instruction("XIC", ["in"], ""), Instruction("OSF", ["s.0"], ""),
               Instruction("OTL", ["y.0"], ""))
    eng.call_routine("P", "Main")               # in high -> no falling edge -> no pulse
    assert eng.db.read("P", "y.0") is False
    eng.db.write("P", "in", False)
    eng.call_routine("P", "Main")               # falling edge -> one-scan pulse
    assert eng.db.read("P", "y.0") is True
    eng.db.write("P", "y.0", False)
    eng.call_routine("P", "Main")               # held low -> no second pulse
    assert eng.db.read("P", "y.0") is False


def test_res_clears_timer_state():
    tags = [Tag("rst", "BOOL", "P", None, "1", None), Tag("t", "TIMER", "P", None, None, None)]
    eng = _eng(tags, Instruction("XIC", ["rst"], ""), Instruction("RES", ["t"], ""))
    eng.db.write("P", "t.ACC", 100)
    eng.db.write("P", "t.DN", True)
    eng.db.write("P", "t.EN", True)
    eng.call_routine("P", "Main")
    assert eng.db.read("P", "t.ACC") == 0
    assert eng.db.read("P", "t.DN") is False
    assert eng.db.read("P", "t.EN") is False
