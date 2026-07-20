from typing import Any

from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    task: str = Field(..., min_length=1, description="What you want the swarm to do")
    use_web: bool | None = Field(
        None,
        description="true = force internet tools on, false = force off, null = auto-detect from the task",
    )
    session_id: str | None = Field(None, description="Reuse an id to keep conversation history")
    provider: str | None = Field(None, description="Override LLM provider for this request: 'ollama' or 'groq'")


class ToolEventOut(BaseModel):
    agent: str
    tool: str
    arguments: dict[str, Any]
    result_preview: str


class TaskResponse(BaseModel):
    content: str
    final_agent: str
    path: list[str]
    web_enabled: bool
    tool_events: list[ToolEventOut]


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    max_results: int = Field(5, ge=1, le=15)


class FetchRequest(BaseModel):
    url: str = Field(..., min_length=1)


class ReviewRequest(BaseModel):
    code: str = Field(..., min_length=1, description="The code to review")
    context: str = Field("", description="Optional context: language, what the code should do, concerns")
    use_web: bool | None = None
    provider: str | None = None
