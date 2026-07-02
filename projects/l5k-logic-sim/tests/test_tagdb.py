from l5k_sim.ir import AOIDef, Controller, DataType, Member, Program, Project, Tag
from l5k_sim.tagdb import TagDatabase



def _project() -> Project:
    udt = DataType("io_t", [Member("active_mode", "DINT"), Member("running", "BOOL")])
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
    udt = DataType("blk", [Member("word", "DINT")])
    tags = [Tag("u", "blk", "P", None, None, None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [udt], [], [Program("P", None, tags, [])])))
    assert db.read("P", "u.word.3") is False
    db.write("P", "u.word.3", True)
    assert db.read("P", "u.word.3") is True
    assert db.read("P", "u.word") == 8


def test_bit_overlay_members_init_as_independent_bools():
    udt = DataType("bits_t", [
        Member("host", "SINT"),
        Member("ext", "BIT", bit_host="host", bit_pos=6),
        Member("ret", "BIT", bit_host="host", bit_pos=7),
    ])
    tags = [Tag("iface", "bits_t", "P", "InOut", None, None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [udt], [], [Program("P", None, tags, [])])))
    assert db.read("P", "iface.ext") is False
    db.write("P", "iface.ext", True)
    assert db.read("P", "iface.ext") is True
    assert db.read("P", "iface.ret") is False   # independent of ext


def test_array_member_init_as_list():
    udt = DataType("rec_t", [Member("Info", "DINT", dim=8)])
    tags = [Tag("rec", "rec_t", "P", None, None, None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [udt], [], [Program("P", None, tags, [])])))
    info = db.read("P", "rec.Info")
    assert isinstance(info, list) and len(info) == 8 and info == [0] * 8


def test_array_index_read_write():
    db = TagDatabase.from_project(_project())
    db.write("P", "step", 0)            # ensure scope P exists
    db.write("P", "arr", [10, 20, 30])  # whole-array write creates the list
    assert db.read("P", "arr") == [10, 20, 30]
    assert db.read("P", "arr[1]") == 20
    db.write("P", "arr[1]", 99)
    assert db.read("P", "arr[1]") == 99
    assert db.read("P", "arr") == [10, 99, 30]


def test_bit_after_index_round_trips():
    db = TagDatabase.from_project(_project())
    db.write("P", "words", [0, 0])
    assert db.read("P", "words[1].3") is False
    db.write("P", "words[1].3", True)
    assert db.read("P", "words[1].3") is True
    assert db.read("P", "words[1]") == 8       # bit 3 set on element 1
    assert db.read("P", "words[0]") == 0       # element 0 untouched


def test_array_index_out_of_range_degrades():
    db = TagDatabase.from_project(_project())
    db.write("P", "arr", [1, 2, 3])
    assert db.read("P", "arr[9]") == 0          # degrades to default, no raise
    db.write("P", "arr[9]", 5)                  # no-op, no raise
    assert db.read("P", "arr") == [1, 2, 3]     # unchanged
    assert any("index out of range" in d for d in db.diagnostics)


def test_array_tag_inits_to_list():
    tags = [Tag("counts", "INT[12]", "P", None, None, None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [], [], [Program("P", None, tags, [])])))
    counts = db.read("P", "counts")
    assert isinstance(counts, list) and len(counts) == 12 and counts == [0] * 12
    assert db.read("P", "counts[5]") == 0


def test_aggregate_initializer_scalar():
    tags = [Tag("counts", "INT[12]", "P", None, "[0,0,0,0,0,0,0,0,0,0,2,0]", None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [], [], [Program("P", None, tags, [])])))
    assert db.read("P", "counts[10]") == 2
    assert db.read("P", "counts[0]") == 0
    assert db.read("P", "counts") == [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0]


def test_aggregate_initializer_binary_bool():
    tags = [Tag("flags", "BOOL[4]", "P", None, "[2#1,2#0,2#1,2#0]", None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [], [], [Program("P", None, tags, [])])))
    assert db.read("P", "flags") == [True, False, True, False]


def test_aggregate_initializer_short_pads_with_default():
    tags = [Tag("counts", "INT[5]", "P", None, "[7,8]", None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [], [], [Program("P", None, tags, [])])))
    assert db.read("P", "counts") == [7, 8, 0, 0, 0]


def test_whole_array_write_copies_not_aliases():
    db = TagDatabase.from_project(_project())
    db.write("P", "a", [1, 2, 3])
    db.write("P", "b", db.read("P", "a"))   # simulates MOV a -> b
    db.write("P", "b[0]", 99)
    assert db.read("P", "a") == [1, 2, 3]    # source must be unchanged
    assert db.read("P", "b") == [99, 2, 3]
    assert db.read("P", "a") is not db.read("P", "b")


def test_aoi_instance_inits_as_param_dict():
    aoi = AOIDef("scale2", [
        Tag("EnableIn", "BOOL", "scale2", "Input", None, None),
        Tag("In", "DINT", "scale2", "Input", None, None),
        Tag("Out", "DINT", "scale2", "Output", None, None),
    ], None)
    tags = [Tag("inst", "scale2", "P", None, None, None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [], [aoi], [Program("P", None, tags, [])])))
    inst = db.read("P", "inst")
    assert isinstance(inst, dict) and set(inst) == {"EnableIn", "In", "Out"}
    assert db.read("P", "inst.In") == 0
    assert db.read("P", "inst.EnableIn") is False


def test_udt_aggregate_decomposition_scalars():
    udt = DataType("blk", [Member("host", "SINT"), Member("val", "REAL")])
    tags = [Tag("b", "blk", "P", None, "[3,25.5]", None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [udt], [], [Program("P", None, tags, [])])))
    assert db.read("P", "b.host") == 3
    assert db.read("P", "b.val") == 25.5


def test_udt_aggregate_decomposition_nested_udt():
    inner = DataType("inner", [Member("a", "DINT"), Member("b", "DINT")])
    outer = DataType("outer", [Member("x", "DINT"), Member("sub", "inner")])
    tags = [Tag("o", "outer", "P", None, "[7,[10,20]]", None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [inner, outer], [], [Program("P", None, tags, [])])))
    assert db.read("P", "o.x") == 7
    assert db.read("P", "o.sub.a") == 10
    assert db.read("P", "o.sub.b") == 20


def test_udt_aggregate_decomposition_array_member():
    udt = DataType("rec", [Member("n", "DINT"), Member("data", "DINT", dim=3)])
    tags = [Tag("r", "rec", "P", None, "[5,[1,2,3]]", None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [udt], [], [Program("P", None, tags, [])])))
    assert db.read("P", "r.n") == 5
    assert db.read("P", "r.data") == [1, 2, 3]


def test_udt_aggregate_longer_than_members_diagnoses():
    udt = DataType("blk", [Member("host", "SINT")])
    tags = [Tag("b", "blk", "P", None, "[1,2,3]", None)]
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [udt], [], [Program("P", None, tags, [])])))
    assert db.read("P", "b.host") == 1
    assert any("struct initializer longer" in d for d in db.diagnostics)


def test_bit_overlay_derived_from_host_word():
    udt = DataType("bt", [
        Member("host", "SINT"),
        Member("b0", "BIT", bit_host="host", bit_pos=0),
        Member("b1", "BIT", bit_host="host", bit_pos=1),
        Member("b2", "BIT", bit_host="host", bit_pos=2),
    ])
    tags = [Tag("t", "bt", "P", None, "[3]", None)]   # host = 3 -> bits 0,1 set; bit 2 clear
    db = TagDatabase.from_project(Project(Controller("C", "x", [], [udt], [], [Program("P", None, tags, [])])))
    assert db.read("P", "t.host") == 3
    assert db.read("P", "t.b0") is True
    assert db.read("P", "t.b1") is True
    assert db.read("P", "t.b2") is False


def _db(tags, datatypes=None):
    prog = Program("P", None, tags, [])
    return TagDatabase.from_project(
        Project(Controller("C", "x", [], datatypes or [], [], [prog])))


def test_unmodeled_type_tag_member_access_is_forgiving():
    db = _db([Tag("relay", "REDUNDANT_OUTPUT", "P", None, None, None)])
    assert db.read("P", "relay.O1") == 0           # forgiving default, no raise
    db.write("P", "relay.O1", True)
    assert db.read("P", "relay.O1") is True


def test_colon_io_tag_auto_creates_forgiving():
    db = _db([])
    assert db.read("P", "Local:4:I.Data[1]") == 0
    db.write("P", "Local:4:I.Data[1]", 55)
    assert db.read("P", "Local:4:I.Data[1]") == 55


def test_io_bit_subpath_default_and_hold():
    db = _db([])
    assert db.read("P", "Local:1:I.Data.5") is False
    db.write("P", "Local:1:I.Data.5", True)
    assert db.read("P", "Local:1:I.Data.5") is True


def test_bare_undeclared_read_still_zero():
    db = _db([])
    assert db.read("P", "never_written") == 0


def test_known_udt_stays_strict():
    from l5k_sim.tagdb import IOStub
    udt = DataType("blk", [Member("word", "DINT")])
    db = _db([Tag("u", "blk", "P", None, None, None)], datatypes=[udt])
    db.write("P", "u.word", 7)
    assert db.read("P", "u.word") == 7
    assert not isinstance(db.programs["P"]["u"], IOStub)
