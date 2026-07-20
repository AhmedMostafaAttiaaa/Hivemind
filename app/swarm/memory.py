from collections import defaultdict
from typing import Any

MAX_HISTORY_MESSAGES = 30


class SessionMemory:
    """In-memory per-session chat history. Swap for Redis/DB when scaling out."""

    def __init__(self):
        self._sessions: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def get(self, session_id: str) -> list[dict[str, Any]]:
        return list(self._sessions[session_id])

    def append(self, session_id: str, role: str, content: str) -> None:
        history = self._sessions[session_id]
        history.append({"role": role, "content": content})
        if len(history) > MAX_HISTORY_MESSAGES:
            del history[: len(history) - MAX_HISTORY_MESSAGES]

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


memory = SessionMemory()
