import os
from l5k_sim.l5k_parser import parse_l5k
from l5k_sim.engine import ScanEngine

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "seq.L5K")


def _engine() -> ScanEngine:
    proj = parse_l5k(FIXTURE)
    eng = ScanEngine(proj, scan_period_ms=50)
    eng.db.write("P", "dwell.PRE", 100)   # done after 2 scans of accrual
    eng.db.write("P", "presses.PRE", 5)
    return eng


def test_sequence_advances_through_steps_and_counts():
    eng = _engine()
    eng.set("P", "start", True)
    eng.scan()                                   # step 0 -> 5; dwell ACC 50; presses 1
    assert eng.get("P", "step") == 5
    assert eng.get("P", "running") is False
    assert eng.get("P", "presses.ACC") == 1
    eng.scan()                                   # dwell DN -> step 10; running on
    assert eng.get("P", "step") == 10
    assert eng.get("P", "running") is True
    assert eng.get("P", "presses.ACC") == 1      # start held -> no new edge
    eng.set("P", "stop", True)
    eng.scan()                                   # stop -> step 0; running off
    assert eng.get("P", "step") == 0
    assert eng.get("P", "running") is False


def test_force_overrides_logic_each_scan():
    eng = _engine()
    eng.force("P", "running", True)              # pin running on
    eng.set("P", "start", True)
    eng.run(3)
    assert eng.get("P", "running") is True       # logic tried to drive it off, force wins


def test_time_advances_deterministically():
    eng = _engine()
    eng.run(4)
    assert eng.time_ms == 200                     # 4 * 50ms
