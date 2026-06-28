from l5k_sim.ir import Controller, DataType, Program, Project, Tag
from l5k_sim.tagdb import TagDatabase



def _project() -> Project:
    udt = DataType("io_t", [("active_mode", "DINT"), ("running", "BOOL")])
    ctrl_tags = [Tag("g_flag", "BOOL", "controller", None, "1", None)]
    prog_tags = [
        Tag("step", "DINT", "P", None, "0", None),
        Tag("dwell", "TIMER", "P", None, None, None),
        Tag("ons", "DINT", "P", None, "0", None),
        Tag("io", "io_t", "P", "InOut", None, None),
    ]
    prog = Program("P", "Main", prog_tags, [])
    return Project(Controller("C", "x", ctrl_tags, [udt], [], [prog]))


def test_scalar_read_write_and_initial():
    db = TagDatabase.from_project(_project())
    assert db.read("P", "step") == 0
    db.write("P", "step", 40)
    assert db.read("P", "step") == 40
    assert db.read("P", "g_flag") is True  # controller-scope fallback, initial "1"


def test_literal_passthrough():
    db = TagDatabase.from_project(_project())
    assert db.read("P", "40") == 40
    assert db.read("P", "16#ff") == 255


def test_timer_member_access():
    db = TagDatabase.from_project(_project())
    assert db.read("P", "dwell.ACC") == 0
    db.write("P", "dwell.DN", True)
    assert db.read("P", "dwell.DN") is True


def test_udt_member_access():
    db = TagDatabase.from_project(_project())
    assert db.read("P", "io.active_mode") == 0
    db.write("P", "io.active_mode", 3)
    assert db.read("P", "io.active_mode") == 3


def test_write_to_unknown_scope_persists():
    db = TagDatabase.from_project(_project())
    db.write("OTHER", "newtag", 9)
    assert db.read("OTHER", "newtag") == 9


def test_bit_access():
    db = TagDatabase.from_project(_project())
    assert db.read("P", "ons.0") is False
    db.write("P", "ons.0", True)
    assert db.read("P", "ons.0") is True
    assert db.read("P", "ons") == 1  # bit 0 set
    db.write("P", "ons.2", True)
    assert db.read("P", "ons") == 5


def test_nested_member_bit_write_symmetric_with_read():
    udt = DataType("blk", [("word", "DINT")])
    tags = [Tag("u", "blk", "P", None, None, None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [udt], [], [Program("P", None, tags, [])])))
    assert db.read("P", "u.word.3") is False
    db.write("P", "u.word.3", True)
    assert db.read("P", "u.word.3") is True
    assert db.read("P", "u.word") == 8
