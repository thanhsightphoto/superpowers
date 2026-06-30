from l5k_sim.values import Ref, Index, Bit, VarIndex, is_literal, parse_literal, looks_like_expr, parse_ref


def test_decimal_and_float_and_hex_literals():
    assert is_literal("40") and parse_literal("40") == 40
    assert is_literal("38.01") and parse_literal("38.01") == 38.01
    assert is_literal("16#ff") and parse_literal("16#ff") == 255
    assert is_literal("16#0000_3f9a") and parse_literal("16#0000_3f9a") == 0x3f9a
    assert not is_literal("16#_")          # underscore-only hex body is not a literal


def test_tag_names_are_not_literals():
    assert not is_literal("step")
    assert not is_literal("dwell.DN")
    assert not is_literal("interface.active_mode")


def test_parse_ref_member_and_bit():
    assert parse_ref("step") == Ref("step", ())
    assert parse_ref("dwell.DN") == Ref("dwell", ("DN",))
    assert parse_ref("interface.active_mode") == Ref("interface", ("active_mode",))
    assert parse_ref("v37.01") == Ref("v37", (Bit(1),))   # numeric segment -> bit index
    assert parse_ref("ons.0") == Ref("ons", (Bit(0),))


def test_looks_like_expr():
    assert looks_like_expr("(Value1 - Value2) * 60000/Period")
    assert looks_like_expr("a + b")
    assert not looks_like_expr("dwell.DN")
    assert not looks_like_expr("40")


def test_tab_whitespace_is_expr_separator():
    assert looks_like_expr("a\tb")


def test_parse_ref_typed_segments():
    assert parse_ref("arr[0]") == Ref("arr", (Index(0),))
    assert parse_ref("arr[3].10") == Ref("arr", (Index(3), Bit(10)))
    assert parse_ref("rec.system[2]") == Ref("rec", ("system", Index(2)))
    assert parse_ref("rec.system[2].flag") == Ref("rec", ("system", Index(2), "flag"))
    assert parse_ref("arr[FAULT_BIT_CTR]") == Ref("arr", (VarIndex("FAULT_BIT_CTR"),))
    assert parse_ref("Local:3:I.Data[3]") == Ref("Local:3:I", ("Data", Index(3)))


def test_binary_literals():
    assert is_literal("2#0") and parse_literal("2#0") == 0
    assert is_literal("2#1") and parse_literal("2#1") == 1
    assert is_literal("2#1011") and parse_literal("2#1011") == 11
    assert is_literal("2#0000_1111") and parse_literal("2#0000_1111") == 15
    assert not is_literal("2#")          # empty binary body is not a literal
