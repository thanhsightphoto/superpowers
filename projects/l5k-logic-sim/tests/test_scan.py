import pytest
from l5k_sim.scan import find_matching, split_top_level


def test_find_matching_parens():
    s = "EQ(a,(b+c))X"
    assert find_matching(s, 2) == len(s) - 2  # the ')' before 'X'


def test_find_matching_brackets_with_nested_parens():
    s = "[GT(a,b) ,LT(c,d) ]"
    assert find_matching(s, 0) == len(s) - 1


def test_find_matching_raises_on_imbalance():
    with pytest.raises(ValueError):
        find_matching("(a,b", 0)


def test_split_top_level_ignores_nested_commas():
    assert split_top_level("a,(b,c),d") == ["a", "(b,c)", "d"]


def test_split_top_level_ignores_bracketed_commas():
    assert split_top_level("x ,[GT(a,b) ,LT(c,d) ] ,y") == ["x", "[GT(a,b) ,LT(c,d) ]", "y"]


def test_split_top_level_single_piece():
    assert split_top_level("(Value1 - Value2) * 60000/Period") == ["(Value1 - Value2) * 60000/Period"]
