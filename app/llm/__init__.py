from app.core.config import get_settings
from app.llm.base import BaseLLM
from app.llm.groq_client import GroqLLM
from app.llm.ollama_client import OllamaLLM

# Common spellings that should all resolve to the same provider.
_PROVIDER_ALIASES = {"groq": "groq", "qroq": "groq", "qrop": "groq", "ollama": "ollama"}


def resolve_provider(raw: str) -> str:
    """Normalize a provider name, tolerating common misspellings of 'groq'."""
    raw = (raw or "").lower().strip()
    return _PROVIDER_ALIASES.get(raw, raw)


def get_llm(provider: str | None = None) -> BaseLLM:
    settings = get_settings()
    provider = resolve_provider(provider or settings.llm_provider)
    if provider == "groq":
        return GroqLLM(api_key=settings.groq_api_key, model=settings.groq_model)
    if provider == "ollama":
        return OllamaLLM(base_url=settings.ollama_base_url, model=settings.ollama_model)
    raise ValueError(f"Unknown LLM provider: {provider!r} (expected 'ollama' or 'groq')")
