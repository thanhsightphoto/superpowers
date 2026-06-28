import pytest
from l5k_sim.values import Ref, is_literal, parse_literal, looks_like_expr, parse_ref


def test_decimal_and_float_and_hex_literals():
    assert is_literal("40") and parse_literal("40") == 40
    assert is_literal("38.01") and parse_literal("38.01") == 38.01
    assert is_literal("16#ff") and parse_literal("16#ff") == 255
    assert is_literal("16#0000_3f9a") and parse_literal("16#0000_3f9a") == 0x3f9a


def test_tag_names_are_not_literals():
    assert not is_literal("step")
    assert not is_literal("dwell.DN")
    assert not is_literal("interface.active_mode")


def test_parse_ref_member_and_bit():
    assert parse_ref("step") == Ref("step", ())
    assert parse_ref("dwell.DN") == Ref("dwell", ("DN",))
    assert parse_ref("interface.active_mode") == Ref("interface", ("active_mode",))
    assert parse_ref("v37.01") == Ref("v37", (1,))   # numeric segment -> bit index
    assert parse_ref("ons.0") == Ref("ons", (0,))


def test_looks_like_expr():
    assert looks_like_expr("(Value1 - Value2) * 60000/Period")
    assert looks_like_expr("a + b")
    assert not looks_like_expr("dwell.DN")
    assert not looks_like_expr("40")
