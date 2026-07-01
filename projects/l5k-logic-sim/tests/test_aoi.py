from l5k_sim.ir import (AOIDef, Controller, Instruction, Program, Project,
                        Routine, Rung, Tag)
from l5k_sim.engine import ScanEngine


def _aoi_dbl() -> AOIDef:
    # AOI "dbl": out := in * 2
    params = [
        Tag("EnableIn", "BOOL", "dbl", "Input", None, None),
        Tag("EnableOut", "BOOL", "dbl", "Output", None, None),
        Tag("in", "DINT", "dbl", "Input", None, None),
        Tag("out", "DINT", "dbl", "Output", None, None),
    ]
    logic = Routine("Logic", None, [
        Rung(0, None, [Instruction("CPT", ["out", "in*2"], "CPT(out,in*2)")], "CPT(out,in*2)"),
    ])
    return AOIDef("dbl", params, logic)


def _project() -> Project:
    prog_tags = [
        Tag("inst", "dbl", "P", None, None, None),
        Tag("src", "DINT", "P", None, "5", None),
        Tag("dst", "DINT", "P", None, "0", None),
    ]
    prog = Program("P", None, prog_tags, [])
    return Project(Controller("C", "x", [], [], [_aoi_dbl()], [prog]))


def _call(engine, power=True):
    instr = Instruction("dbl", ["inst", "src", "dst"], "dbl(inst,src,dst)")
    return engine._eval_instruction("P", instr, power)


def test_aoi_binds_input_args_to_instance():
    e = ScanEngine(_project())
    _call(e)
    assert e.db.read("P", "inst.in") == 5       # src value bound to param 'in'


def test_aoi_count_mismatch_skips_with_diagnostic():
    e = ScanEngine(_project())
    e._eval_instruction("P", Instruction("dbl", ["inst", "src"], "dbl(inst,src)"), True)
    assert any("dbl" in d and "args" in d for d in e.diagnostics)
    assert e.db.read("P", "inst.in") == 0        # nothing bound


def test_aoi_non_dict_instance_skips():
    proj = _project()
    proj.controller.programs[0].tags[0] = Tag("inst", "DINT", "P", None, "0", None)
    e = ScanEngine(proj)
    e._eval_instruction("P", Instruction("dbl", ["inst", "src", "dst"], "dbl(inst,src,dst)"), True)
    assert any("dbl" in d for d in e.diagnostics)
