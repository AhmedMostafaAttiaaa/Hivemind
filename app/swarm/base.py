import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.llm import get_llm
from app.tools.base import Tool

HANDOFF_PREFIX = "handoff_to_"

# Optional async callback used to stream progress events (agent start, handoff,
# tool start/end) to a live client. None = no streaming.
Emitter = Callable[[dict[str, Any]], Awaitable[None]]


async def _emit(emit: Emitter | None, event: dict[str, Any]) -> None:
    if emit is not None:
        await emit(event)


@dataclass
class ToolEvent:
    agent: str
    tool: str
    arguments: dict[str, Any]
    result_preview: str


@dataclass
class AgentOutput:
    agent: str
    content: str
    next_agent: str | None = None
    tool_events: list[ToolEvent] = field(default_factory=list)


@dataclass
class Agent:
    """One reusable template for every role: coder, searcher, reviewer, ...

    A role is just instructions + tools + allowed handoffs.
    """

    name: str
    description: str
    instructions: str
    tools: list[Tool] = field(default_factory=list)
    handoffs: list[str] = field(default_factory=list)
    provider: str | None = None  # override global LLM provider per agent

    def _handoff_schemas(self, registry: dict[str, "Agent"]) -> list[dict[str, Any]]:
        schemas = []
        for target in self.handoffs:
            agent = registry.get(target)
            if not agent:
                continue
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": f"{HANDOFF_PREFIX}{target}",
                        "description": f"Hand the task off to the '{target}' agent. {agent.description}",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "reason": {"type": "string", "description": "Why this agent fits the task"}
                            },
                            "required": ["reason"],
                        },
                    },
                }
            )
        return schemas

    async def run(
        self,
        messages: list[dict[str, Any]],
        registry: dict[str, "Agent"] | None = None,
        extra_tools: list[Tool] | None = None,
        provider: str | None = None,
        emit: Emitter | None = None,
    ) -> AgentOutput:
        settings = get_settings()
        registry = registry or {}
        llm = get_llm(provider or self.provider)

        tools = list(self.tools) + list(extra_tools or [])
        tool_map = {t.name: t for t in tools}
        tool_schemas = [t.schema() for t in tools] + self._handoff_schemas(registry)

        convo: list[dict[str, Any]] = [{"role": "system", "content": self.instructions}, *messages]
        events: list[ToolEvent] = []

        for _ in range(settings.max_tool_iterations):
            response = await llm.chat(convo, tools=tool_schemas or None)

            if not response.tool_calls:
                return AgentOutput(agent=self.name, content=response.content, tool_events=events)

            convo.append(
                {
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                        }
                        for tc in response.tool_calls
                    ],
                }
            )

            for tc in response.tool_calls:
                if tc.name.startswith(HANDOFF_PREFIX):
                    target = tc.name[len(HANDOFF_PREFIX):]
                    return AgentOutput(
                        agent=self.name,
                        content=response.content or tc.arguments.get("reason", ""),
                        next_agent=target,
                        tool_events=events,
                    )

                tool = tool_map.get(tc.name)
                await _emit(emit, {"type": "tool", "phase": "start", "agent": self.name,
                                   "tool": tc.name, "arguments": tc.arguments})
                if tool:
                    try:
                        result = await tool.func(**tc.arguments)
                    except Exception as e:
                        result = f"Tool {tc.name} failed: {e}"
                else:
                    result = f"Unknown tool: {tc.name}"
                await _emit(emit, {"type": "tool", "phase": "end", "agent": self.name, "tool": tc.name})

                events.append(
                    ToolEvent(agent=self.name, tool=tc.name, arguments=tc.arguments, result_preview=result[:300])
                )
                convo.append({"role": "tool", "tool_call_id": tc.id, "name": tc.name, "content": result})

        # Iteration budget exhausted: ask for a final answer without tools
        final = await llm.chat(
            convo + [{"role": "user", "content": "Give your final answer now based on what you have."}]
        )
        return AgentOutput(agent=self.name, content=final.content, tool_events=events)
