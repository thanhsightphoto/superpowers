import pytest
from l5k_sim.ir import Controller, Program, Project, Tag
from l5k_sim.tagdb import TagDatabase
from l5k_sim.expr import eval_expr


def _db(**vals) -> TagDatabase:
    tags = [Tag(k, "REAL" if isinstance(v, float) else "DINT", "P", None, None, None) for k, v in vals.items()]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [], [], [Program("P", None, tags, [])])))
    for k, v in vals.items():
        db.write("P", k, v)
    return db


def test_arithmetic_with_tags_and_parens():
    db = _db(Value1=100, Value2=40, Period=60)
    assert eval_expr("(Value1 - Value2) * 60000 / Period", "P", db) == (100 - 40) * 60000 / 60


def test_constant_only():
    db = _db()
    assert eval_expr("60000.0 / 1000", "P", db) == 60.0


def test_member_operand_in_expr():
    db = _db(a=5)
    db.write("P", "a", 5)
    assert eval_expr("a + 3", "P", db) == 8


def test_rejects_calls():
    db = _db()
    with pytest.raises(ValueError):
        eval_expr("__import__('os').system('echo hi')", "P", db)
