from l5k_sim.blocks import scan_blocks


SAMPLE = """\
PROGRAM Mode_1 (Class := Standard,
                MAIN := "Main")
	TAG
		step : DINT := 0;
	END_TAG
	ROUTINE Main
		N: NOP();
	END_ROUTINE
END_PROGRAM
"""


def test_scan_finds_program_with_children():
    blocks = scan_blocks(SAMPLE)
    assert len(blocks) == 1
    prog = blocks[0]
    assert prog.keyword == "PROGRAM"
    assert prog.header.startswith("Mode_1")
    assert "MAIN := \"Main\"" in prog.header
    assert {c.keyword for c in prog.children} == {"TAG", "ROUTINE"}


def test_tag_body_lines_captured():
    prog = scan_blocks(SAMPLE)[0]
    tag = next(c for c in prog.children if c.keyword == "TAG")
    assert any("step : DINT := 0;" in ln for ln in tag.body_lines)


def test_routine_body_has_rung_line():
    prog = scan_blocks(SAMPLE)[0]
    routine = next(c for c in prog.children if c.keyword == "ROUTINE")
    assert routine.header.strip() == "Main"
    assert any("N: NOP();" in ln for ln in routine.body_lines)
