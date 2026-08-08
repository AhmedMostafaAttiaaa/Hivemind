"""A tiny "system info" MCP server (stdio, JSON-RPC 2.0), stdlib only.

Exposes `get_system_info` so agents can answer questions about the host machine
(OS, Python version, CPU count) without guessing.

Add it to mcp.json:
    "sysinfo": { "command": "python", "args": ["examples/mcp_sysinfo_server.py"] }

IMPORTANT: stdout is the JSON-RPC channel — only protocol messages may be
printed there. Any debugging must go to stderr.
"""

import json
import os
import platform
import sys

TOOLS = [
    {
        "name": "get_system_info",
        "description": "Get basic info about the host machine: OS, Python version, CPU count.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def get_system_info() -> str:
    info = {
        "os": f"{platform.system()} {platform.release()}",
        "python_version": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "machine": platform.machine(),
    }
    return json.dumps(info)


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
                "serverInfo": {"name": "hivemind-sysinfo", "version": "0.1.0"},
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = msg.get("params", {})
        name = params.get("name")
        try:
            if name == "get_system_info":
                out = get_system_info()
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
