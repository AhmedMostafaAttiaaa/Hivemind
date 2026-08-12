import json
import re
import uuid
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.http import async_client
from app.llm.base import BaseLLM, LLMResponse, ToolCall

# Some Ollama models (observed on qwen3-vl) don't reliably use the real `tool_calls`
# field and instead write the call as plain text like:
#   <function-call>\n{"name": "web_search", "arguments": {...}}\n</function-call>
# Recover a real ToolCall from that pattern when `tool_calls` came back empty.
_FUNCTION_CALL_RE = re.compile(r"<function-call>\s*(\{.*?\})\s*</function-call>", re.DOTALL)

# When generation goes further off the rails, Ollama's own server rejects the
# request with a 400 (e.g. "Value looks like object, but can't find closing '}'
# symbol") before any message is returned at all -- there's nothing to recover,
# but a retry with the same (temperature-sampled) prompt often succeeds.
MAX_MALFORMED_RETRIES = 2


def _recover_tool_call_from_content(content: str) -> ToolCall | None:
    m = _FUNCTION_CALL_RE.search(content or "")
    if not m:
        return None
    try:
        obj = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    name = obj.get("name")
    if not name:
        return None
    return ToolCall(id=uuid.uuid4().hex[:8], name=name, arguments=obj.get("arguments") or {})


class OllamaLLM(BaseLLM):
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _suppress_reasoning(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """qwen3 ignores the API `think` flag on some Ollama builds but honors the
        `/no_think` soft switch in the prompt. Inject it so we don't pay for
        chain-of-thought tokens on already-slow CPU inference."""
        if "qwen3" not in self.model.lower():
            return messages
        patched = [dict(m) for m in messages]
        for m in patched:
            if m.get("role") == "system":
                m["content"] = f"{m.get('content', '')}\n/no_think"
                return patched
        patched.insert(0, {"role": "system", "content": "/no_think"})
        return patched

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        messages = self._suppress_reasoning(messages)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": False,  # suppress reasoning traces on models like qwen3 (ignored by others)
            "options": {"temperature": get_settings().llm_temperature},
        }
        if tools:
            payload["tools"] = tools

        data = None
        last_malformed: httpx.HTTPStatusError | None = None
        for attempt in range(MAX_MALFORMED_RETRIES):
            try:
                async with async_client(timeout=600) as client:
                    resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                break
            except httpx.TimeoutException as e:
                raise RuntimeError(
                    f"Ollama call timed out after 600s (model={self.model!r}). "
                    "CPU inference on this model is very slow; try a smaller/faster model "
                    "or set LLM_PROVIDER=groq."
                ) from e
            except httpx.ConnectError as e:
                raise RuntimeError(
                    f"Cannot reach Ollama at {self.base_url}. Is `ollama serve` running?"
                ) from e
            except httpx.HTTPStatusError as e:
                body = e.response.text[:300]
                if e.response.status_code == 404 and "not found" in body.lower():
                    raise RuntimeError(
                        f"Ollama model {self.model!r} not found on {self.base_url}. "
                        f"List what's actually available with: curl {self.base_url}/api/tags "
                        "-- then set OLLAMA_MODEL (in .env, or as an env var before launching "
                        "the server) to one of those names and restart. Note: env vars set with "
                        "`set` only last for that one terminal session, so a fresh terminal can "
                        "silently fall back to the OLLAMA_MODEL default."
                    ) from e
                if e.response.status_code == 400:
                    # Model generated invalid JSON for a tool call; Ollama itself rejected the
                    # request before returning anything to recover from. Since this is sampled
                    # (temperature > 0), retrying the identical request often succeeds.
                    last_malformed = e
                    continue
                raise RuntimeError(
                    f"Ollama API error {e.response.status_code} at {self.base_url} "
                    f"(model={self.model!r}): {body}"
                ) from e

        if data is None:
            raise RuntimeError(
                f"Ollama model {self.model!r} kept generating invalid tool-call JSON after "
                f"{MAX_MALFORMED_RETRIES} attempts (model={self.model!r}): "
                f"{last_malformed.response.text[:300] if last_malformed else ''}. "
                "This model may not be reliable enough for tool-calling tasks; try a "
                "different Ollama model or LLM_PROVIDER=groq."
            ) from last_malformed

        message = data.get("message", {})
        tool_calls = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                args = json.loads(args or "{}")
            tool_calls.append(
                ToolCall(id=tc.get("id") or uuid.uuid4().hex[:8], name=fn.get("name", ""), arguments=args)
            )

        content = message.get("content", "") or ""
        if not tool_calls:
            recovered = _recover_tool_call_from_content(content)
            if recovered is not None:
                return LLMResponse(content="", tool_calls=[recovered])

        return LLMResponse(content=content, tool_calls=tool_calls)
