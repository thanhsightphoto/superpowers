from __future__ import annotations

import copy
import re
from typing import Any

from l5k_sim.ir import Project, Tag, Member
from l5k_sim.scan import split_top_level
from l5k_sim.values import Bit, Index, VarIndex, is_literal, parse_literal, parse_ref

_TIMER = {"PRE": 0, "ACC": 0, "EN": False, "TT": False, "DN": False}
_COUNTER = {"PRE": 0, "ACC": 0, "CU": False, "CD": False, "DN": False, "prev_cu": False, "prev_cd": False}
_ARRAY = re.compile(r"^(\w+)\[(\d+)\]$")


class IOStub(dict):
    """Forgiving store for an unmodeled I/O / module-defined tag.

    Keys are canonical sub-path strings; missing keys read as defaults.
    """


def _canon(path) -> str:
    out = ""
    for seg in path:
        if isinstance(seg, Index):
            out += f"[{seg.i}]"
        elif isinstance(seg, VarIndex):
            out += f"[{seg.name}]"
        elif isinstance(seg, Bit):
            out += f".{seg.n}"
        else:  # member str
            out += (f".{seg}" if out else str(seg))
    return out


class TagDatabase:
    def __init__(self) -> None:
        self.controller: dict[str, Any] = {}
        self.programs: dict[str, dict[str, Any]] = {}
        self._udts: dict[str, list[Member]] = {}
        self._aois: dict[str, list[Tag]] = {}
        self.diagnostics: list[str] = []

    @classmethod
    def from_project(cls, project: Project) -> "TagDatabase":
        db = cls()
        db._udts = {dt.name: dt.members for dt in project.controller.datatypes}
        db._aois = {a.name: a.parameters for a in project.controller.aois}
        for t in project.controller.controller_tags:
            db.controller[t.name] = db._init_value(t)
        for prog in project.controller.programs:
            scope: dict[str, Any] = {}
            for t in prog.tags:
                scope[t.name] = db._init_value(t)
            db.programs[prog.name] = scope
        return db

    def _init_value(self, t: Tag) -> Any:
        return self._init_type(t.data_type, t.initial)

    def _init_type(self, data_type: str, initial: str | None) -> Any:
        dt = data_type.upper()
        if dt == "BOOL":
            return bool(parse_literal(initial)) if (initial and is_literal(initial)) else False
        if dt == "BIT":
            return bool(parse_literal(initial)) if (initial and is_literal(initial)) else False
        if dt in ("DINT", "INT", "SINT"):
            return parse_literal(initial) if (initial and is_literal(initial)) else 0
        if dt == "REAL":
            return float(parse_literal(initial)) if (initial and is_literal(initial)) else 0.0
        if dt == "TIMER":
            return dict(_TIMER)
        if dt == "COUNTER":
            return dict(_COUNTER)
        arr = _ARRAY.match(data_type.strip())
        if arr:
            return self._init_array(arr.group(1), int(arr.group(2)), initial)
        if data_type in self._udts:
            return self._init_struct(data_type, initial)
        if data_type in self._aois:
            return {p.name: self._init_type(p.data_type, p.initial) for p in self._aois[data_type]}
        return IOStub()  # unmodeled type -> forgiving, forceable I/O stub

    def _init_array(self, elem_type: str, n: int, initial: str | None) -> list:
        out = [self._init_type(elem_type, None) for _ in range(n)]
        if not initial:
            return out
        s = initial.strip()
        if not (s.startswith("[") and s.endswith("]")):
            return out
        items = split_top_level(s[1:-1])
        for i, item in enumerate(items):
            if i >= n:
                self.diagnostics.append(f"array initializer longer than dim {n}: {initial}")
                break
            item = item.strip()
            if item:
                out[i] = self._init_type(elem_type, item)
        return out

    def _init_struct(self, data_type: str, initial: str | None) -> dict:
        members = self._udts[data_type]
        out: dict[str, Any] = {}
        for mem in members:
            if mem.bit_host is not None:
                out[mem.name] = False
            elif mem.dim is not None:
                out[mem.name] = [self._init_type(mem.data_type, None) for _ in range(mem.dim)]
            else:
                out[mem.name] = self._init_type(mem.data_type, None)
        if initial:
            s = initial.strip()
            if s.startswith("[") and s.endswith("]"):
                items = split_top_level(s[1:-1])
                storage = [m for m in members if m.bit_host is None]
                for i, mem in enumerate(storage):
                    if i >= len(items):
                        break
                    item = items[i].strip()
                    if not item:
                        continue
                    if mem.dim is not None:
                        out[mem.name] = self._init_array(mem.data_type, mem.dim, item)
                    elif mem.data_type in self._udts:
                        out[mem.name] = self._init_struct(mem.data_type, item)
                    else:
                        out[mem.name] = self._init_type(mem.data_type, item)
                if len(items) > len(storage):
                    self.diagnostics.append(
                        f"struct initializer longer than members ({len(storage)}): {initial}")
        for mem in members:
            if mem.bit_host is not None and isinstance(out.get(mem.bit_host), int):
                out[mem.name] = bool((int(out[mem.bit_host]) >> (mem.bit_pos or 0)) & 1)
        return out

    # ---- resolution ----
    def _container_for(self, scope: str, base: str) -> dict[str, Any]:
        prog = self.programs.setdefault(scope, {})
        if base in prog:
            return prog
        if base in self.controller:
            return self.controller
        # auto-create in program scope so writes to undeclared tags don't crash
        prog[base] = IOStub()
        return prog

    def read(self, scope: str, operand: str) -> Any:
        if is_literal(operand):
            return parse_literal(operand)
        ref = parse_ref(operand)
        container = self._container_for(scope, ref.base)
        val = container[ref.base]
        if isinstance(val, IOStub):
            if not ref.path:
                return 0
            default = False if isinstance(ref.path[-1], Bit) else 0
            return val.get(_canon(ref.path), default)
        for seg in ref.path:
            if isinstance(seg, Bit):
                return bool((int(val) >> seg.n) & 1)
            if isinstance(seg, Index):
                if not isinstance(val, list) or not (0 <= seg.i < len(val)):
                    self.diagnostics.append(f"index out of range: {operand}")
                    return 0
                val = val[seg.i]
            elif isinstance(seg, VarIndex):
                self.diagnostics.append(f"unresolved variable index: {operand}")
                return 0
            else:  # member (str)
                val = val[seg]
        return val

    def write(self, scope: str, operand: str, value: Any) -> None:
        ref = parse_ref(operand)
        container = self._container_for(scope, ref.base)
        base_val = container[ref.base]
        if isinstance(base_val, IOStub):
            if not ref.path:
                container[ref.base] = copy.deepcopy(value) if isinstance(value, (list, dict)) else value
            else:
                base_val[_canon(ref.path)] = value
            return
        if not ref.path:
            container[ref.base] = copy.deepcopy(value) if isinstance(value, (list, dict)) else value
            return
        # Navigate to the (holder, key) that owns the final segment.
        holder: Any = container
        key: Any = ref.base
        for seg in ref.path[:-1]:
            parent_val = holder[key]
            if isinstance(seg, Index):
                if not isinstance(parent_val, list) or not (0 <= seg.i < len(parent_val)):
                    self.diagnostics.append(f"index out of range: {operand}")
                    return
                holder, key = parent_val, seg.i
            elif isinstance(seg, VarIndex):
                self.diagnostics.append(f"unresolved variable index: {operand}")
                return
            else:  # member (str)
                holder, key = parent_val, seg
        leaf = ref.path[-1]
        if isinstance(leaf, Bit):
            cur = int(holder[key])
            holder[key] = (cur | (1 << leaf.n)) if value else (cur & ~(1 << leaf.n))
        elif isinstance(leaf, Index):
            target = holder[key]
            if not isinstance(target, list) or not (0 <= leaf.i < len(target)):
                self.diagnostics.append(f"index out of range: {operand}")
                return
            target[leaf.i] = value
        elif isinstance(leaf, VarIndex):
            self.diagnostics.append(f"unresolved variable index: {operand}")
            return
        else:  # member (str)
            holder[key][leaf] = value

    def snapshot(self) -> dict[str, Any]:
        return {"controller": copy.deepcopy(self.controller),
                "programs": copy.deepcopy(self.programs)}
