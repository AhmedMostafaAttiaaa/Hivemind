import httpx

from app.core.config import get_settings


def async_client(**kwargs) -> httpx.AsyncClient:
    """httpx.AsyncClient honoring the ssl_verify setting (for corp TLS proxies)."""
    kwargs.setdefault("verify", get_settings().ssl_verify)
    return httpx.AsyncClient(**kwargs)
