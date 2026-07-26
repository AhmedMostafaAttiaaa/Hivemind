from fastapi import APIRouter

from app.mcp import mcp_manager

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/servers")
async def list_servers() -> dict:
    """Which MCP servers are connected, their tools, and any connection errors."""
    return mcp_manager.describe()


@router.get("/tools")
async def list_tools() -> list[dict]:
    """The MCP tools currently exposed to the agents (namespaced as server__tool)."""
    return [
        {"name": t.name, "description": t.description, "parameters": t.parameters}
        for t in mcp_manager.tools
    ]
