from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: str = "ollama"

    ollama_base_url: str = "http://10.51.1.95:11434"
    ollama_model: str = "llama3.1"

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Sampling temperature (0 = most deterministic). Kept low for consistent,
    # on-persona answers and reliable tool calling.
    llm_temperature: float = 0.2

    searxng_url: str = ""

    # Path to an MCP server config file (Claude-desktop `mcp.json` format).
    # Connected MCP servers' tools become available to the agents.
    mcp_config: str = "mcp.json"

    max_tool_iterations: int = 6
    max_handoffs: int = 4

    # Set false only behind a TLS-intercepting corporate proxy that presents a
    # self-signed cert. Disables certificate verification for outbound calls.
    ssl_verify: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
