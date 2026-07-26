"""Loads MCP servers from a config file, connects to them, and exposes their
tools as Hivemind `Tool`s so any agent can call them.

Config format mirrors Claude Desktop's `mcp.json`:

    { "mcpServers": { "demo": { "command": "python", "args": ["examples/mcp_demo_server.py"] } } }
"""

import json
from pathlib import Path

from app.core.config import get_settings
from app.mcp.client import MCPServerSession
from app.tools.base import Tool


class MCPManager:
    def __init__(self):
        self.sessions: dict[str, MCPServerSession] = {}
        self.tools: list[Tool] = []
        self.errors: dict[str, str] = {}

    def _load_config(self, path: str) -> dict:
        p = Path(path)
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("mcpServers", {})
        except Exception as e:
            self.errors["_config"] = f"could not read {path}: {e}"
            return {}

    def _wrap(self, server_name: str, session: MCPServerSession, tool_def: dict) -> Tool:
        tool_name = tool_def["name"]

        async def _call(**kwargs) -> str:
            return await session.call_tool(tool_name, kwargs)

        return Tool(
            name=f"{server_name}__{tool_name}",  # namespaced to avoid collisions
            description=f"[MCP:{server_name}] {tool_def.get('description', '')}".strip(),
            parameters=tool_def.get("inputSchema") or {"type": "object", "properties": {}},
            func=_call,
        )

    async def connect(self, config_path: str | None = None) -> None:
        """Spawn every configured MCP server and register its tools. One bad
        server logs an error but never breaks startup."""
        config_path = config_path or get_settings().mcp_config
        for name, cfg in self._load_config(config_path).items():
            try:
                session = MCPServerSession(
                    name, cfg["command"], cfg.get("args", []), cfg.get("env")
                )
                await session.start()
                self.sessions[name] = session
                for tool_def in await session.list_tools():
                    self.tools.append(self._wrap(name, session, tool_def))
            except Exception as e:
                self.errors[name] = str(e)

    async def disconnect(self) -> None:
        for session in self.sessions.values():
            await session.stop()
        self.sessions.clear()
        self.tools.clear()
        self.errors.clear()

    def describe(self) -> dict:
        return {
            "servers": {
                name: [t.name for t in self.tools if t.name.startswith(f"{name}__")]
                for name in self.sessions
            },
            "tool_count": len(self.tools),
            "errors": self.errors,
        }


mcp_manager = MCPManager()
