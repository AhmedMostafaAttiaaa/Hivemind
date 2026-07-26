"""Minimal MCP (Model Context Protocol) stdio client.

Speaks JSON-RPC 2.0 over a subprocess's stdin/stdout (newline-delimited), which
is how MCP stdio servers communicate. No external SDK — just asyncio.

Lifecycle: start() spawns the server and does the initialize handshake; then
list_tools() and call_tool() are available until stop().
"""

import asyncio
import json
import sys
from typing import Any

PROTOCOL_VERSION = "2024-11-05"


class MCPServerSession:
    def __init__(self, name: str, command: str, args: list[str] | None = None, env: dict | None = None):
        self.name = name
        # Route bare "python"/"python3" to the interpreter running us, so a demo
        # server launches under the same environment regardless of PATH.
        self.command = sys.executable if command in ("python", "python3") else command
        self.args = args or []
        self.env = env
        self.proc: asyncio.subprocess.Process | None = None
        self._id = 0
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self.proc = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=self.env,
        )
        await self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "hivemind", "version": "0.1.0"},
            },
        )
        await self._notify("notifications/initialized")

    async def _send(self, obj: dict) -> None:
        assert self.proc and self.proc.stdin
        self.proc.stdin.write((json.dumps(obj) + "\n").encode())
        await self.proc.stdin.drain()

    async def _notify(self, method: str, params: dict | None = None) -> None:
        await self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    async def _request(self, method: str, params: dict | None = None) -> dict:
        assert self.proc and self.proc.stdout
        self._id += 1
        req_id = self._id
        await self._send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}})
        # Read lines until we see the response matching our id (skip notifications).
        while True:
            line = await self.proc.stdout.readline()
            if not line:
                raise RuntimeError(f"MCP server '{self.name}' closed the connection")
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == req_id:
                if "error" in msg:
                    raise RuntimeError(msg["error"].get("message", "MCP error"))
                return msg.get("result", {})

    async def list_tools(self) -> list[dict[str, Any]]:
        async with self._lock:
            result = await self._request("tools/list")
        return result.get("tools", [])

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        async with self._lock:
            result = await self._request("tools/call", {"name": name, "arguments": arguments})
        # MCP returns content as a list of typed parts; join the text parts.
        parts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
        return "\n".join(parts) if parts else json.dumps(result)

    async def stop(self) -> None:
        if self.proc and self.proc.returncode is None:
            try:
                self.proc.terminate()
                await asyncio.wait_for(self.proc.wait(), timeout=5)
            except Exception:
                self.proc.kill()
