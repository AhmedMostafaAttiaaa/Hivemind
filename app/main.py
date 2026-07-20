from fastapi import FastAPI

from app.api.routers import agents, swarm, web
from app.core.config import get_settings

app = FastAPI(
    title="Swarm Search",
    description=(
        "A universal swarm-agent service: one agent template, many roles "
        "(search, coding, review, general), with on-demand internet access. "
        "Exposed as microservice-style FastAPI routers."
    ),
    version="0.1.0",
)

app.include_router(swarm.router)
app.include_router(agents.router)
app.include_router(web.router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "provider": settings.llm_provider,
        "model": settings.groq_model if settings.llm_provider == "groq" else settings.ollama_model,
    }
