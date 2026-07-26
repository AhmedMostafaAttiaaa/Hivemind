"""A tiny demo MCP server (stdio, JSON-RPC 2.0) for testing Hivemind's MCP client.

It exposes two trivial tools — `add` and `current_time` — so you can see MCP tools
show up in the swarm without installing anything. Point mcp.json at it:

    { "mcpServers": { "demo": { "command": "python", "args": ["examples/mcp_demo_server.py"] } } }

IMPORTANT: stdout is the JSON-RPC channel — only protocol messages may be printed
there. Any debugging must go to stderr.
"""

import json
import sys
from datetime import datetime

TOOLS = [
    {
        "name": "add",
        "description": "Add two numbers and return the sum.",
        "inputSchema": {
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    },
    {
        "name": "current_time",
        "description": "Return the current server time in ISO 8601 format.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


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
                "serverInfo": {"name": "hivemind-demo", "version": "0.1.0"},
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
            if name == "add":
                out = str(args["a"] + args["b"])
            elif name == "current_time":
                out = datetime.now().isoformat()
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
