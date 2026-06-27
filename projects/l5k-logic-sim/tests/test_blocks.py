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


def test_stray_lines_are_ignored():
    text = "STRAY_GARBAGE_LINE\nPROGRAM Foo\nEND_PROGRAM\nMORE_STRAY\n"
    blocks = scan_blocks(text)
    assert [b.keyword for b in blocks] == ["PROGRAM"]
    assert blocks[0].header.strip() == "Foo"


def test_missing_end_terminates_gracefully():
    # no END_PROGRAM — should not loop forever or raise; returns the partial block
    text = "PROGRAM Foo\n\tROUTINE Main\n\t\tN: NOP();\n\tEND_ROUTINE\n"
    blocks = scan_blocks(text)
    assert blocks[0].keyword == "PROGRAM"
    assert any(c.keyword == "ROUTINE" for c in blocks[0].children)


def test_deep_nesting_three_levels():
    text = (
        "CONTROLLER Ctl\n"
        "\tPROGRAM Foo\n"
        "\t\tROUTINE Main\n"
        "\t\t\tN: NOP();\n"
        "\t\tEND_ROUTINE\n"
        "\tEND_PROGRAM\n"
        "END_CONTROLLER\n"
    )
    ctl = scan_blocks(text)[0]
    assert ctl.keyword == "CONTROLLER"
    prog = ctl.children[0]
    assert prog.keyword == "PROGRAM"
    assert prog.children[0].keyword == "ROUTINE"
