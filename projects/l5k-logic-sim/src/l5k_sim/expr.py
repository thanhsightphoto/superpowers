from __future__ import annotations

import ast

from l5k_sim.tagdb import TagDatabase

_BINOPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
           ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b}


def eval_expr(expr: str, scope: str, db: TagDatabase) -> int | float:
    tree = ast.parse(expr, mode="eval")
    return _eval(tree.body, scope, db)


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    raise ValueError(f"unsupported reference node: {ast.dump(node)}")


def _eval(node: ast.AST, scope: str, db: TagDatabase):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name):
        return db.read(scope, node.id)
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
