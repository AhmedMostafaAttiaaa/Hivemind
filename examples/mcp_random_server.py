"""A tiny "randomness" MCP server (stdio, JSON-RPC 2.0), stdlib only.

Exposes `roll_dice`, `coin_flip`, and `random_number` — useful for games,
decisions, sampling, or just letting an agent do real randomness instead of
picking a suspiciously "random-looking" number itself.

Add it to mcp.json:
    "random": { "command": "python", "args": ["examples/mcp_random_server.py"] }

IMPORTANT: stdout is the JSON-RPC channel — only protocol messages may be
printed there. Any debugging must go to stderr.
"""

import json
import random
import sys

TOOLS = [
    {
        "name": "roll_dice",
        "description": "Roll N dice with S sides each and return the individual results and total.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "description": "Number of dice to roll (default 1)"},
                "sides": {"type": "integer", "description": "Sides per die (default 6)"},
            },
        },
    },
    {
        "name": "coin_flip",
        "description": "Flip a coin, returns 'heads' or 'tails'.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "random_number",
        "description": "Return a random integer between min and max, inclusive.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "min": {"type": "integer", "description": "Minimum value (default 1)"},
                "max": {"type": "integer", "description": "Maximum value (default 100)"},
            },
        },
    },
]


def send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def roll_dice(count: int = 1, sides: int = 6) -> str:
    count = max(1, min(int(count), 100))
    sides = max(2, min(int(sides), 1000))
    rolls = [random.randint(1, sides) for _ in range(count)]
    return f"rolls={rolls}, total={sum(rolls)}"


def coin_flip() -> str:
    return random.choice(["heads", "tails"])


def random_number(min: int = 1, max: int = 100) -> str:
    lo, hi = int(min), int(max)
    if lo > hi:
        lo, hi = hi, lo
    return str(random.randint(lo, hi))


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
                "serverInfo": {"name": "hivemind-random", "version": "0.1.0"},
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
            if name == "roll_dice":
                out = roll_dice(**args)
            elif name == "coin_flip":
                out = coin_flip()
            elif name == "random_number":
                out = random_number(**args)
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
