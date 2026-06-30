import os
import pytest

from l5k_sim.l5k_parser import parse_l5k
from l5k_sim.engine import ScanEngine

REAL = os.path.expanduser("~/Downloads/briles_main_rev_023.L5K")
pytestmark = pytest.mark.skipif(not os.path.exists(REAL), reason="real Briles L5K not present")

# the six member accesses that previously raised KeyError in Lower_KO_Valve_Adapter
_PREV_FAILING = [
    "out_lower_ko_ext", "out_lower_ko_ret", "lower_ko_speed_pct",
    "lower_ko_valve_monitor", "lower_ko_valve_stiction_tolerance",
    "lower_ko_valve_stiction_timeout_ms",
]


def test_interface_member_keyerrors_are_gone():
    engine = ScanEngine(parse_l5k(REAL))
    engine.run(5)
    assert any(k.startswith("Lower_KO_Valve_Adapter/") for k in engine.trace), \
        "regression scope was not scanned — test would be vacuous"
    raised = [d for d in engine.diagnostics if "raised:" in d]
    for member in _PREV_FAILING:
        assert not any(member in d for d in raised), f"{member} still raising: {raised}"
