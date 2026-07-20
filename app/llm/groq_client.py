import json
import re
import uuid
from typing import Any

from app.core.http import async_client
from app.llm.base import BaseLLM, LLMResponse, ToolCall

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Llama-on-Groq occasionally emits a tool call as `<function=name {json}</function>`
# (note: no closing `>` on the opening tag) instead of proper tool_calls; Groq then
# 400s with code "tool_use_failed". Capture name + the full JSON object.
_FAILED_CALL_RE = re.compile(r"<function=([\w-]+)\s*(\{.*\})", re.DOTALL)


def _recover_tool_call(failed_generation: str) -> ToolCall | None:
    m = _FAILED_CALL_RE.search(failed_generation or "")
    if not m:
        return None
    try:
        args = json.loads(m.group(2))
    except json.JSONDecodeError:
        return None
    return ToolCall(id=uuid.uuid4().hex[:8], name=m.group(1), arguments=args)


class GroqLLM(BaseLLM):
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set; set it in .env or switch LLM_PROVIDER=ollama")
        self.api_key = api_key
        self.model = model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        # temperature=0 sharply reduces Llama-on-Groq emitting malformed tool calls
        # (the <function=...> format that triggers `tool_use_failed`).
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": 0}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with async_client(timeout=120) as client:
            resp = await client.post(
                GROQ_API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            if resp.status_code >= 400:
                recovered = self._try_recover(resp)
                if recovered is not None:
                    return recovered
                raise RuntimeError(f"Groq API {resp.status_code}: {resp.text}")
            data = resp.json()

        message = data["choices"][0]["message"]
        tool_calls = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function", {})
            args = fn.get("arguments", "{}")
            if isinstance(args, str):
                args = json.loads(args or "{}")
            tool_calls.append(
                ToolCall(id=tc.get("id") or uuid.uuid4().hex[:8], name=fn.get("name", ""), arguments=args)
            )
        return LLMResponse(content=message.get("content") or "", tool_calls=tool_calls)

    def _try_recover(self, resp) -> LLMResponse | None:
        try:
            err = resp.json().get("error", {})
        except Exception:
            return None
        if err.get("code") != "tool_use_failed":
            return None
        recovered = _recover_tool_call(err.get("failed_generation", ""))
        if recovered is None:
            return None
        return LLMResponse(content="", tool_calls=[recovered])
