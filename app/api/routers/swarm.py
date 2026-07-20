from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from app.agents import REGISTRY
from app.api.schemas import TaskRequest, TaskResponse
from app.swarm import SwarmEngine, SwarmResult
from app.swarm.memory import memory

router = APIRouter(prefix="/swarm", tags=["swarm"])
engine = SwarmEngine(registry=REGISTRY, entry_agent="triage")


def to_response(result: SwarmResult) -> TaskResponse:
    return TaskResponse(
        content=result.content,
        final_agent=result.final_agent,
        path=result.path,
        web_enabled=result.web_enabled,
        tool_events=[asdict(e) for e in result.tool_events],
    )


@router.post("/run", response_model=TaskResponse)
async def run_swarm(req: TaskRequest) -> TaskResponse:
    """Any task: the triage agent routes it to the right specialist automatically."""
    try:
        result = await engine.run(
            req.task, use_web=req.use_web, session_id=req.session_id, provider=req.provider
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return to_response(result)


@router.get("/agents")
async def list_agents() -> list[dict]:
    return [
        {"name": a.name, "description": a.description, "handoffs": a.handoffs}
        for a in REGISTRY.values()
    ]


@router.delete("/sessions/{session_id}")
async def clear_session(session_id: str) -> dict:
    memory.clear(session_id)
    return {"cleared": session_id}
