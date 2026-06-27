import pytest

from l5k_sim.rung_parser import parse_rung
from l5k_sim.ir import Instruction, Branch


def test_single_instruction():
    els = parse_rung("NOP();")
    assert els == [Instruction("NOP", [], "NOP()")]


def test_series_of_instructions():
    els = parse_rung("EQ(step,40)XIO(stop_at_tdc)OTE(interface.out_ram_cycle_cmd)")
    assert [e.mnemonic for e in els] == ["EQ", "XIO", "OTE"]
    assert els[0].operands == ["step", "40"]
    assert els[2].operands == ["interface.out_ram_cycle_cmd"]


def test_expression_operand_with_inner_parens_and_spaces():
    els = parse_rung("CPT(Speed,(Value1 - Value2) * 60000/Period)")
    assert els[0].mnemonic == "CPT"
    assert els[0].operands == ["Speed", "(Value1 - Value2) * 60000/Period"]


def test_question_mark_operands_preserved():
    els = parse_rung("CTU(feedback_counter,?,?)")
    assert els[0].operands == ["feedback_counter", "?", "?"]


def test_operands_are_stripped_of_surrounding_spaces():
    els = parse_rung("EQ( step , 40 )")
    assert els[0].operands == ["step", "40"]


def test_middle_instruction_operand_covered():
    els = parse_rung("EQ(step,40)XIO(stop_at_tdc)OTE(out)")
    assert els[1].operands == ["stop_at_tdc"]


def test_unexpected_character_raises():
    with pytest.raises(ValueError):
        parse_rung("@bad")


def test_series_with_trailing_branch():
    els = parse_rung("XIC(grace)[GT(cpm,max) OTE(over) ,LT(cpm,min) OTE(under) ]MOVE(Speed,RPM)")
    assert isinstance(els[0], Instruction) and els[0].mnemonic == "XIC"
    assert isinstance(els[1], Branch)
    assert len(els[1].legs) == 2
    assert [e.mnemonic for e in els[1].legs[0]] == ["GT", "OTE"]
    assert [e.mnemonic for e in els[1].legs[1]] == ["LT", "OTE"]
    assert isinstance(els[2], Instruction) and els[2].mnemonic == "MOVE"


def test_leading_branch_then_branch():
    text = "[XIC(a) ,XIO(b) ONS(ons.1) ][CPT(x,1) ,RES(c) RES(d) ]"
    els = parse_rung(text)
    assert isinstance(els[0], Branch) and isinstance(els[1], Branch)
    assert [e.mnemonic for e in els[0].legs[1]] == ["XIO", "ONS"]
    assert [e.mnemonic for e in els[1].legs[1]] == ["RES", "RES"]


def test_nested_branch():
    text = "XIC(en)[GT(a,b) ,[LT(c,d) ,EQ(e,f) ]OTE(g) ]"
    els = parse_rung(text)
    branch = els[1]
    assert isinstance(branch, Branch)
    inner = branch.legs[1][0]
    assert isinstance(inner, Branch)
    assert [leg[0].mnemonic for leg in inner.legs] == ["LT", "EQ"]
