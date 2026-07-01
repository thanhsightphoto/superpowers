from __future__ import annotations

import ast
import keyword
import re

from l5k_sim.tagdb import TagDatabase

_BINOPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
           ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b}

# PLC identifiers may collide with Python keywords (e.g. "in", "and", "or").
# Mangle them before parsing; un-mangle when resolving against the tag DB.
_PLC_KEYWORDS = set(keyword.kwlist) - {"True", "False", "None"}
_MANGLE_PREFIX = "__plckw_"
_MANGLE_RE = re.compile(r"\b([A-Za-z_]\w*)\b")
_UNMANGLE_RE = re.compile(r"^" + re.escape(_MANGLE_PREFIX) + r"(.+)$")


def _mangle(expr: str) -> str:
    """Replace Python-keyword identifiers in a PLC expression with safe names."""
    def _sub(m: re.Match) -> str:
        w = m.group(1)
        return f"{_MANGLE_PREFIX}{w}" if w in _PLC_KEYWORDS else w
    return _MANGLE_RE.sub(_sub, expr)


def _unmangle(name: str) -> str:
    """Reverse the mangling applied by _mangle."""
    m = _UNMANGLE_RE.match(name)
    return m.group(1) if m else name


def eval_expr(expr: str, scope: str, db: TagDatabase) -> int | float:
    tree = ast.parse(_mangle(expr), mode="eval")
    return _eval(tree.body, scope, db)


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return _unmangle(node.id)
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{_unmangle(node.attr)}"
    raise ValueError(f"unsupported reference node: {ast.dump(node)}")


def _eval(node: ast.AST, scope: str, db: TagDatabase) -> int | float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name):
        return db.read(scope, _unmangle(node.id))
    if isinstance(node, ast.Attribute):
        return db.read(scope, _dotted(node))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _eval(node.operand, scope, db)
        return +v if isinstance(node.op, ast.UAdd) else -v
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        left = _eval(node.left, scope, db)
        right = _eval(node.right, scope, db)
        return _BINOPS[type(node.op)](left, right)
    raise ValueError(f"unsupported expression node: {ast.dump(node)}")
