# tests/test_decls.py
from l5k_sim.blocks import scan_blocks
from l5k_sim.decls import parse_tag_block, parse_routine_block


TAGS = """\
TAG
\tmode_enabled : BOOL (Description := "true when active",
\t            RADIX := Decimal) := 0;
\tinterface : briles_special_modes (Usage := InOut);
\tstroke_watchdog : TIMER (Description := "watchdog") := [0,0,0];
END_TAG
"""

ROUTINE = """\
ROUTINE Outputs
\t\tRC: "DOC | maps step to outputs";
\t\tN: NOP();
\t\tRC: "cycle cmd on during step 40";
\t\tN: EQ(step,40)XIO(stop_at_tdc)OTE(interface.out_ram_cycle_cmd);
END_ROUTINE
"""


def test_parse_tag_block_types_and_attrs():
    block = scan_blocks(TAGS)[0]
    tags = parse_tag_block(block, scope="Mode_1")
    by_name = {t.name: t for t in tags}
    assert by_name["mode_enabled"].data_type == "BOOL"
    assert by_name["mode_enabled"].initial == "0"
    assert by_name["mode_enabled"].description == "true when active"
    assert by_name["interface"].data_type == "briles_special_modes"
    assert by_name["interface"].usage == "InOut"
    assert by_name["stroke_watchdog"].initial == "[0,0,0]"


def test_parse_routine_block_description_and_rungs():
    block = scan_blocks(ROUTINE)[0]
    routine = parse_routine_block(block)
    assert routine.name == "Outputs"
    assert routine.description.startswith("DOC | maps step")
    assert len(routine.rungs) == 2
    assert routine.rungs[0].comment is None  # the DOC line is the routine desc, not a rung comment
    assert routine.rungs[1].comment == "cycle cmd on during step 40"
    assert routine.rungs[1].elements[0].mnemonic == "EQ"
