import asyncio
import json
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

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


@router.post("/stream")
async def stream_swarm(req: TaskRequest) -> StreamingResponse:
    """Same as /run, but streams progress events as Server-Sent Events (SSE).

    Event types (one JSON object per `data:` line):
      web_enabled {value}          - whether web tools are active for this task
      agent       {agent}          - an agent started working
      handoff     {from,to}        - routed to another agent
      tool start  {tool,arguments} - a tool (e.g. web_search) began
      tool end    {tool}           - that tool finished
      final       {content,path,final_agent,web_enabled,tool_events}
      error       {message}
    Clients use the `tool start/end` events for web_search/fetch_page to show a
    "searching the web" indicator.
    """
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(event: dict) -> None:
        await queue.put(event)

    async def drive() -> None:
        try:
            result = await engine.run(
                req.task,
                use_web=req.use_web,
                session_id=req.session_id,
                provider=req.provider,
                emit=emit,
            )
            await queue.put({"type": "final", **to_response(result).model_dump()})
        except Exception as e:  # noqa: BLE001 - surface any failure to the client
            await queue.put({"type": "error", "message": str(e)})
        finally:
            await queue.put(None)  # sentinel: stream complete

    async def event_source():
        task = asyncio.create_task(drive())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            task.cancel()

    return StreamingResponse(event_source(), media_type="text/event-stream")


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
