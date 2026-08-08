import ast
import operator

from app.tools.base import Tool

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("unsupported expression")


async def calculator(expression: str) -> str:
    """Safely evaluate a basic arithmetic expression (+ - * / // % **), no eval()."""
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_eval(tree.body))
    except Exception as e:
        return f"Could not evaluate {expression!r}: {e}"


calculator_tool = Tool(
    name="calculator",
    description="Evaluate a basic arithmetic expression, e.g. '(3 + 4) * 2 / 7'. "
    "Supports + - * / // % ** and parentheses only, no variables or functions.",
    parameters={
        "type": "object",
        "properties": {"expression": {"type": "string", "description": "The math expression to evaluate"}},
        "required": ["expression"],
    },
    func=calculator,
)
