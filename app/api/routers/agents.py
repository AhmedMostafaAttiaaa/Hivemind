from fastapi import APIRouter, HTTPException

from app.agents import REGISTRY
from app.api.schemas import ReviewRequest, TaskRequest, TaskResponse
from app.api.routers.swarm import engine, to_response

router = APIRouter(prefix="/agents", tags=["agents"])


async def _run_direct(agent_name: str, req: TaskRequest) -> TaskResponse:
    try:
        result = await engine.run(
            req.task,
            agent_name=agent_name,
            use_web=req.use_web,
            session_id=req.session_id,
            provider=req.provider,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return to_response(result)


@router.post("/search", response_model=TaskResponse)
async def run_researcher(req: TaskRequest) -> TaskResponse:
    """Research/search microservice — web tools on by default."""
    if req.use_web is None:
        req.use_web = True
    return await _run_direct("researcher", req)


@router.post("/code", response_model=TaskResponse)
async def run_coder(req: TaskRequest) -> TaskResponse:
    """Coding microservice — writes/fixes code."""
    return await _run_direct("coder", req)


@router.post("/review", response_model=TaskResponse)
async def run_reviewer(req: ReviewRequest) -> TaskResponse:
    """Code review microservice."""
    task = f"Review this code.\n\nContext: {req.context or 'none provided'}\n\n```\n{req.code}\n```"
    return await _run_direct(
        "reviewer", TaskRequest(task=task, use_web=req.use_web, provider=req.provider)
    )


@router.post("/general", response_model=TaskResponse)
async def run_generalist(req: TaskRequest) -> TaskResponse:
    """General assistant microservice."""
    return await _run_direct("generalist", req)


@router.post("/{agent_name}/run", response_model=TaskResponse)
async def run_any_agent(agent_name: str, req: TaskRequest) -> TaskResponse:
    """Run any registered agent by name (works for agents you add later)."""
    if agent_name not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_name}. Available: {sorted(REGISTRY)}")
    return await _run_direct(agent_name, req)
