from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routers import agents, mcp, swarm, ui, web
from app.core.config import get_settings
from app.llm import resolve_provider
from app.mcp import mcp_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to any configured MCP servers on startup; their tools become
    # available to the agents. Disconnect (terminate subprocesses) on shutdown.
    await mcp_manager.connect()
    yield
    await mcp_manager.disconnect()


app = FastAPI(
    title="Hivemind",
    description=(
        "A universal swarm-agent service: one agent template, many roles "
        "(search, coding, review, general), with on-demand internet access "
        "and MCP tool integration. Exposed as microservice-style FastAPI routers."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(swarm.router)
app.include_router(agents.router)
app.include_router(web.router)
app.include_router(mcp.router)
app.include_router(ui.router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    settings = get_settings()
    provider = resolve_provider(settings.llm_provider)
    return {
        "status": "ok",
        "provider": provider,
        "model": settings.groq_model if provider == "groq" else settings.ollama_model,
    }
