import os
from l5k_sim.l5k_parser import parse_l5k

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "mode1.L5K")


def test_controller_identity():
    p = parse_l5k(FIXTURE)
    assert p.controller.name == "Sutherland_IPress_CompactGuard"
    assert p.controller.processor == "1769-L30ERMS"


def test_datatype_and_controller_tag():
    p = parse_l5k(FIXTURE)
    assert any(dt.name == "briles_special_modes" for dt in p.controller.datatypes)
    assert any(t.name == "global_estop" and t.scope == "controller"
               for t in p.controller.controller_tags)


def test_aoi_with_params_and_logic():
    p = parse_l5k(FIXTURE)
    aoi = next(a for a in p.controller.aois if a.name == "scaler_dint")
    assert {t.name for t in aoi.parameters} == {"In", "Out"}
    assert aoi.logic is not None and aoi.logic.rungs[0].elements[0].mnemonic == "MOVE"


def test_program_routines_and_rungs():
    p = parse_l5k(FIXTURE)
    prog = next(pr for pr in p.controller.programs if pr.name == "Mode_1")
    assert prog.main_routine == "Main"
    assert {r.name for r in prog.routines} == {"Main", "Outputs"}
    outputs = next(r for r in prog.routines if r.name == "Outputs")
    assert outputs.rungs[0].comment == "cycle cmd"
    assert outputs.rungs[0].elements[0].mnemonic == "EQ"


def test_missing_controller_block_returns_diagnostic(tmp_path):
    p = tmp_path / "no_controller.L5K"
    p.write_text("SOME_GARBAGE_LINE\nMORE_GARBAGE\n")
    proj = parse_l5k(str(p))
    assert proj.controller.name == ""
    assert proj.diagnostics == ["no CONTROLLER block"]


def test_malformed_rung_degrades_to_diagnostic(tmp_path):
    text = (
        'CONTROLLER C (ProcessorType := "1769-L30ERMS")\n'
        '\tPROGRAM P (MAIN := "Main")\n'
        '\t\tROUTINE Main\n'
        '\t\t\tN: XIC(ok)OTE(good);\n'
        '\t\t\tN: XIC(a)$bad(b);\n'
        '\t\tEND_ROUTINE\n'
        '\tEND_PROGRAM\n'
        'END_CONTROLLER\n'
    )
    p = tmp_path / "bad.L5K"
    p.write_text(text)
    proj = parse_l5k(str(p))  # must NOT raise
    routine = proj.controller.programs[0].routines[0]
    assert len(routine.rungs) == 2
    assert routine.rungs[0].elements[0].mnemonic == "XIC"   # good rung parsed
    assert routine.rungs[1].elements == []                   # malformed rung degraded
    assert routine.rungs[1].raw == "XIC(a)$bad(b)"           # raw text preserved
    assert any("unparseable rung" in d for d in proj.diagnostics)
