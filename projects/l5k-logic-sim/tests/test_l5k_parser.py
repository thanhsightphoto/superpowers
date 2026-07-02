import os
from l5k_sim.l5k_parser import parse_l5k

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "mode1.L5K")


def test_controller_identity():
    p = parse_l5k(FIXTURE)
    assert p.controller.name == "Sutherland_IPress_CompactGuard"
    assert p.controller.processor == "1769-L30ERMS"


def test_datatype_and_controller_tag():
    p = parse_l5k(FIXTURE)
    dt = next(dt for dt in p.controller.datatypes if dt.name == "briles_special_modes")
    by_name = {m.name: m for m in dt.members}
    # plain type-first member
    assert by_name["active_mode"].data_type == "DINT"
    assert by_name["active_mode"].bit_host is None and by_name["active_mode"].dim is None
    # hidden host word retained as an ordinary plain member
    assert by_name["ZZZZZZZZZZspecial_mo0"].data_type == "SINT"
    # bit overlay
    bit = by_name["out_ram_cycle_cmd"]
    assert bit.data_type == "BIT" and bit.bit_host == "ZZZZZZZZZZspecial_mo0" and bit.bit_pos == 0
    # controller tag still parses
    assert any(t.name == "global_estop" and t.scope == "controller"
               for t in p.controller.controller_tags)


def test_datatype_plain_and_array_members(tmp_path):
    text = (
        'CONTROLLER C (ProcessorType := "1769-L30ERMS")\n'
        '\tDATATYPE FaultRecord (FamilyType := NoFamily)\n'
        '\t\tDINT TimeLow;\n'
        '\t\tINT Code;\n'
        '\t\tDINT Info[8] (Radix := Hex);\n'
        '\tEND_DATATYPE\n'
        'END_CONTROLLER\n'
    )
    f = tmp_path / "dt.L5K"
    f.write_text(text)
    p = parse_l5k(str(f))
    dt = next(dt for dt in p.controller.datatypes if dt.name == "FaultRecord")
    by_name = {m.name: m for m in dt.members}
    assert set(by_name) == {"TimeLow", "Code", "Info"}        # nothing dropped
    assert by_name["TimeLow"].data_type == "DINT"
    assert by_name["Info"].data_type == "DINT" and by_name["Info"].dim == 8


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


def test_malformed_datatype_member_degrades_to_diagnostic(tmp_path):
    # A member line with an unbalanced '(' would make find_matching raise ValueError.
    # The parser must NOT raise; it must skip the bad line, still parse the good one,
    # and record a diagnostic.
    text = (
        'CONTROLLER C (ProcessorType := "1769-L30ERMS")\n'
        '\tDATATYPE BadDT (FamilyType := NoFamily)\n'
        '\t\tDINT GoodMember;\n'
        '\t\tDINT BrokenMember (Radix := Decimal;\n'  # unbalanced '(' — no closing ')'
        '\tEND_DATATYPE\n'
        'END_CONTROLLER\n'
    )
    f = tmp_path / "bad_dt.L5K"
    f.write_text(text)
    proj = parse_l5k(str(f))   # must NOT raise
    dt = next(dt for dt in proj.controller.datatypes if dt.name == "BadDT")
    assert any(m.name == "GoodMember" for m in dt.members), "well-formed member must still be parsed"
    assert not any(m.name == "BrokenMember" for m in dt.members), "malformed member must be skipped"
    assert any("BadDT" in d for d in proj.diagnostics), "a diagnostic mentioning the type must be recorded"
    assert any("BrokenMember" in d or "malformed datatype member" in d for d in proj.diagnostics), \
        "diagnostic must mention the malformed line"


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


def test_parse_required_attribute(tmp_path):
    text = (
        'CONTROLLER C (ProcessorType := "1769-L30ERMS")\n'
        '\tADD_ON_INSTRUCTION_DEFINITION myaoi (Class := Standard)\n'
        '\t\tPARAMETERS\n'
        '\t\t\tEnableIn : BOOL (Usage := Input, Required := No);\n'
        '\t\t\ta : DINT (Usage := Input, Required := Yes);\n'
        '\t\t\tb : DINT (Usage := Input, Required := No);\n'
        '\t\tEND_PARAMETERS\n'
        '\tEND_ADD_ON_INSTRUCTION_DEFINITION\n'
        'END_CONTROLLER\n'
    )
    f = tmp_path / "aoi.L5K"
    f.write_text(text)
    p = parse_l5k(str(f))
    params = {pm.name: pm for pm in p.controller.aois[0].parameters}
    assert params["EnableIn"].required is False
    assert params["a"].required is True
    assert params["b"].required is False
