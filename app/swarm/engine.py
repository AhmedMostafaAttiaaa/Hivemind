import re
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.swarm.base import Agent, AgentOutput, Emitter, ToolEvent, _emit
from app.swarm.memory import memory
from app.tools import WEB_TOOLS

WEB_INTENT = re.compile(
    r"\b(search|google|look up|lookup|latest|news|current|today|browse|internet|web|online|website)\b|https?://",
    re.IGNORECASE,
)


def wants_web(task: str) -> bool:
    return bool(WEB_INTENT.search(task))


@dataclass
class SwarmResult:
    content: str
    final_agent: str
    path: list[str] = field(default_factory=list)
    web_enabled: bool = False
    tool_events: list[ToolEvent] = field(default_factory=list)


class SwarmEngine:
    """Routes a task through the agent registry, following handoffs.

    The same engine serves every use case (coding, search, review, ...) —
    behavior comes entirely from the agents registered in it.
    """

    def __init__(self, registry: dict[str, Agent], entry_agent: str = "triage"):
        self.registry = registry
        self.entry_agent = entry_agent

    async def run(
        self,
        task: str,
        agent_name: str | None = None,
        use_web: bool | None = None,
        session_id: str | None = None,
        provider: str | None = None,
        emit: Emitter | None = None,
    ) -> SwarmResult:
        settings = get_settings()

        # Web tools: explicit flag wins; otherwise auto-detect from the task
        web_enabled = wants_web(task) if use_web is None else use_web
        extra_tools = WEB_TOOLS if web_enabled else []
        await _emit(emit, {"type": "web_enabled", "value": web_enabled})

        history = memory.get(session_id) if session_id else []
        messages = [*history, {"role": "user", "content": task}]

        current = agent_name or self.entry_agent
        if current not in self.registry:
            raise KeyError(f"Unknown agent: {current!r}. Available: {sorted(self.registry)}")

        path: list[str] = []
        all_events: list[ToolEvent] = []
        output: AgentOutput | None = None

        for _ in range(settings.max_handoffs + 1):
            agent = self.registry[current]
            path.append(current)
            await _emit(emit, {"type": "agent", "agent": current})
            output = await agent.run(
                messages, registry=self.registry, extra_tools=extra_tools, provider=provider, emit=emit
            )
            all_events.extend(output.tool_events)

            if not output.next_agent or output.next_agent not in self.registry:
                break
            await _emit(emit, {"type": "handoff", "from": current, "to": output.next_agent})
            # Carry the handoff context forward so the next agent knows why it got the task
            if output.content:
                messages = [*messages, {"role": "assistant", "content": f"[{current} → {output.next_agent}] {output.content}"}]
            current = output.next_agent

        assert output is not None
        if session_id:
            memory.append(session_id, "user", task)
            memory.append(session_id, "assistant", output.content)

        return SwarmResult(
            content=output.content,
            final_agent=path[-1],
            path=path,
            web_enabled=web_enabled,
            tool_events=all_events,
        )
