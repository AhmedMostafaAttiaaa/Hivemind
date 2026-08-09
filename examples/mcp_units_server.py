"""A tiny "unit conversion" MCP server (stdio, JSON-RPC 2.0), stdlib only.

Exposes `convert_units` for common length/weight/temperature conversions, so
agents get exact conversion factors instead of recalling them approximately.

Add it to mcp.json:
    "units": { "command": "python", "args": ["examples/mcp_units_server.py"] }

IMPORTANT: stdout is the JSON-RPC channel — only protocol messages may be
printed there. Any debugging must go to stderr.
"""

import json
import sys

# (from_unit, to_unit) -> multiplier, for simple linear conversions.
_LINEAR = {
    ("km", "mi"): 0.621371, ("mi", "km"): 1.60934,
    ("m", "ft"): 3.28084, ("ft", "m"): 0.3048,
    ("cm", "in"): 0.393701, ("in", "cm"): 2.54,
    ("kg", "lb"): 2.20462, ("lb", "kg"): 0.453592,
    ("g", "oz"): 0.035274, ("oz", "g"): 28.3495,
    ("l", "gal"): 0.264172, ("gal", "l"): 3.78541,
}

TOOLS = [
    {
        "name": "convert_units",
        "description": "Convert a value between units. Supports length (km/mi, m/ft, cm/in), "
        "weight (kg/lb, g/oz), volume (l/gal), and temperature (c/f/k).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "value": {"type": "number", "description": "The numeric value to convert"},
                "from_unit": {"type": "string", "description": "Source unit, e.g. 'km', 'kg', 'c'"},
                "to_unit": {"type": "string", "description": "Target unit, e.g. 'mi', 'lb', 'f'"},
            },
            "required": ["value", "from_unit", "to_unit"],
        },
    },
]


def send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _to_celsius(value: float, unit: str) -> float:
    if unit == "c":
        return value
    if unit == "f":
        return (value - 32) * 5 / 9
    if unit == "k":
        return value - 273.15
    raise ValueError(f"unknown temperature unit: {unit}")


def _from_celsius(value: float, unit: str) -> float:
    if unit == "c":
        return value
    if unit == "f":
        return value * 9 / 5 + 32
    if unit == "k":
        return value + 273.15
    raise ValueError(f"unknown temperature unit: {unit}")


def convert_units(value: float, from_unit: str, to_unit: str) -> str:
    f, t = from_unit.strip().lower(), to_unit.strip().lower()
    if f == t:
        return str(value)

    if {f, t} <= {"c", "f", "k"}:
        result = _from_celsius(_to_celsius(float(value), f), t)
        return f"{result:.4g} {t}"

    if (f, t) in _LINEAR:
        result = float(value) * _LINEAR[(f, t)]
        return f"{result:.4g} {t}"

    supported = sorted({u for pair in _LINEAR for u in pair} | {"c", "f", "k"})
    raise ValueError(f"unsupported conversion {f!r} -> {t!r}. Supported units: {supported}")


def handle(msg: dict):
    method = msg.get("method")
    mid = msg.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": mid,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "hivemind-units", "version": "0.1.0"},
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = msg.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {})
        try:
            if name == "convert_units":
                out = convert_units(**args)
            else:
                out = f"unknown tool: {name}"
            return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": out}]}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32000, "message": str(e)}}
    if mid is not None:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return None


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(msg)
        if resp is not None:
            send(resp)


if __name__ == "__main__":
    main()
