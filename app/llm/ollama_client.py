import json
import uuid
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.http import async_client
from app.llm.base import BaseLLM, LLMResponse, ToolCall


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

        try:
            async with async_client(timeout=600) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
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
            raise RuntimeError(
                f"Ollama API error {e.response.status_code} at {self.base_url} "
                f"(model={self.model!r}): {body}"
            ) from e

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
        return LLMResponse(content=message.get("content", "") or "", tool_calls=tool_calls)
