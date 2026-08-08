"""A tiny file-backed "notes" MCP server (stdio, JSON-RPC 2.0).

Exposes `write_note` and `list_notes` so agents can save and recall short notes
across a session/day. Notes are stored as plain lines in `notes.txt` next to
this script — good enough for a demo, not meant for concurrent/production use.

Add it to mcp.json:
    "notes": { "command": "python", "args": ["examples/mcp_notes_server.py"] }

IMPORTANT: stdout is the JSON-RPC channel — only protocol messages may be
printed there. Any debugging must go to stderr.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

NOTES_FILE = Path(__file__).parent / "notes.txt"

TOOLS = [
    {
        "name": "write_note",
        "description": "Save a short note for later recall.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "The note to save"}},
            "required": ["text"],
        },
    },
    {
        "name": "list_notes",
        "description": "List all previously saved notes, newest first.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def write_note(text: str) -> str:
    timestamp = datetime.now().isoformat(timespec="seconds")
    with NOTES_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{timestamp}\t{text}\n")
    return f"Saved note at {timestamp}."


def list_notes() -> str:
    if not NOTES_FILE.exists():
        return "No notes yet."
    lines = NOTES_FILE.read_text(encoding="utf-8").splitlines()
    if not lines:
        return "No notes yet."
    return "\n".join(f"- [{line.split(chr(9), 1)[0]}] {line.split(chr(9), 1)[1]}" for line in reversed(lines))


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
                "serverInfo": {"name": "hivemind-notes", "version": "0.1.0"},
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
            if name == "write_note":
                out = write_note(args["text"])
            elif name == "list_notes":
                out = list_notes()
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
