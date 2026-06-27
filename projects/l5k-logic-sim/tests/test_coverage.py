import os
from l5k_sim.l5k_parser import parse_l5k
from l5k_sim.coverage import coverage_report, SUPPORTED_V1

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "mode1.L5K")


def test_coverage_counts_and_flags_unsupported():
    p = parse_l5k(FIXTURE)
    rep = coverage_report(p)
    # WIDGET is the only unsupported mnemonic in the fixture
    assert rep["unsupported_mnemonics"] == {"WIDGET": 1}
    assert rep["unsupported"] == 1
    assert rep["total_instructions"] >= 7
    assert 0.0 <= rep["supported_pct"] <= 100.0


def test_supported_set_includes_core_bits():
    for m in ("XIC", "XIO", "OTE", "OTL", "OTU", "TON", "CTU", "MOVE", "JSR", "EQ"):
        assert m in SUPPORTED_V1
