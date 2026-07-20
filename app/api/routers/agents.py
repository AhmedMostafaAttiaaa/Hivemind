from fastapi import APIRouter, HTTPException

from app.agents import REGISTRY
from app.api.schemas import (
    ReviewFileRequest,
    ReviewQuestionsResponse,
    ReviewRequest,
    TaskRequest,
    TaskResponse,
)
from app.api.routers.swarm import engine, to_response
from app.core.files import read_source_file

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


@router.post("/review/questions", response_model=ReviewQuestionsResponse)
async def review_file_questions(req: ReviewFileRequest) -> ReviewQuestionsResponse:
    """Step 1 of file review: point at a file, get the reviewer's clarifying questions.

    The reviewer reads the file and returns the questions it wants answered BEFORE
    reviewing (language/runtime, intended behavior, constraints...). Answer them,
    then call /agents/review/file with those answers.
    """
    try:
        code = read_source_file(req.file_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    task = (
        f"You are about to review the code in the file '{req.file_path}'.\n"
        f"Context: {req.context or 'none provided'}\n\n"
        "BEFORE reviewing, ask the clarifying questions you need to do a thorough review "
        "(e.g. target language/runtime version, intended behavior, performance or security "
        "constraints, coding standards, what recently changed). Output ONLY a numbered list "
        "of 3-6 concise questions. Do NOT review the code yet.\n\n"
        f"Code:\n```\n{code}\n```"
    )
    try:
        result = await engine.run(task, agent_name="reviewer", use_web=False, provider=req.provider)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    return ReviewQuestionsResponse(
        file_path=req.file_path, questions=result.content, lines=code.count("\n") + 1
    )


@router.post("/review/file", response_model=TaskResponse)
async def review_file(req: ReviewFileRequest) -> TaskResponse:
    """Step 2 of file review: review the file, using answers to the reviewer's questions.

    You can call this directly (answers optional), but the intended flow is to call
    /agents/review/questions first, answer, then pass those answers here.
    """
    try:
        code = read_source_file(req.file_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    task = (
        f"Review the code in the file '{req.file_path}'.\n"
        f"Context: {req.context or 'none provided'}\n"
        f"Answers to your clarifying questions:\n{req.answers or 'none provided'}\n\n"
        "Give a thorough review: correctness bugs, security, performance, readability. "
        "Rank findings by severity, reference specific lines, and suggest concrete fixes. "
        "End with a short verdict.\n\n"
        f"Code:\n```\n{code}\n```"
    )
    return await _run_direct("reviewer", TaskRequest(task=task, use_web=False, provider=req.provider))


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
