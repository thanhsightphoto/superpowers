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


def test_array_tag_initializer_resolves_on_real_file():
    engine = ScanEngine(parse_l5k(REAL))
    # Cam_Cut_Dwell_Select : INT[12] := [0,0,0,0,0,0,0,0,0,0,2,0] in MainProgram scope.
    assert engine.db.read("MainProgram", "Cam_Cut_Dwell_Select[10]") == 2
    assert engine.db.read("MainProgram", "Cam_Cut_Dwell_Select[0]") == 0
    engine.run(5)  # must not raise


def test_structured_tag_init_resolves_on_real_file():
    engine = ScanEngine(parse_l5k(REAL))
    db = engine.db
    # UDT tag aggregate decomposition: real non-zero member values.
    assert db.read("controller", "briles_special_modes.ram_position") == 359.0
    assert db.read("controller", "briles_special_modes.lower_ko_valve_cmd") == 5000
    # Bit-overlay derived from host word (special_mo_inputs_x = 4 -> bit 2 set).
    assert db.read("controller", "briles_special_modes.ram_cycle_finished") is True
    # AOI instance is a structured dict, not scalar 0.
    inst = db.read("Lower_KO_Valve_Adapter", "scaler_inst")
    assert isinstance(inst, dict) and "in_max" in inst
    engine.run(5)  # must not raise


def test_aoi_chain_computes_on_real_file():
    engine = ScanEngine(parse_l5k(REAL))
    engine.run(5)  # must not raise
    scope = "Lower_KO_Valve_Adapter"
    # max_dint -> min_dint clamp speed to [0, 100]; scaler_dint maps [0,100] -> [0,5000].
    sc = engine.db.read(scope, "speed_clamped")
    mg = engine.db.read(scope, "magnitude")
    assert 0 <= sc <= 100          # min/max AOIs clamped correctly
    assert mg == sc * 50           # scaler_dint: out = in * (5000-0)/(100-0)
    # scaler_inst.in_max is bound from the literal call argument (100) every scan,
    # so it is non-zero regardless of machine state — proves binding ran on the real file.
    scaler_inst = engine.db.read(scope, "scaler_inst")
    assert scaler_inst["in_max"] == 100
