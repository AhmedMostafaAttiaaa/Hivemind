from fastapi import APIRouter

from app.api.schemas import FetchRequest, SearchRequest
from app.tools.fetch_page import fetch_page
from app.tools.web_search import web_search

router = APIRouter(prefix="/web", tags=["web"])


@router.post("/search")
async def search(req: SearchRequest) -> dict:
    """Raw web search (no LLM) — SearxNG if configured, DuckDuckGo fallback."""
    return {"query": req.query, "results": await web_search(req.query, req.max_results)}


@router.post("/fetch")
async def fetch(req: FetchRequest) -> dict:
    """Raw page fetch (no LLM) — returns readable text of a URL."""
    return {"url": req.url, "content": await fetch_page(req.url)}
