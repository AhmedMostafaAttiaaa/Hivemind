from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.core.http import async_client
from app.tools.base import Tool

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"


async def _searxng_search(query: str, max_results: int) -> list[dict]:
    settings = get_settings()
    async with async_client(timeout=20, headers={"User-Agent": USER_AGENT}) as client:
        resp = await client.get(
            f"{settings.searxng_url.rstrip('/')}/search",
            params={"q": query, "format": "json"},
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")}
        for r in results[:max_results]
    ]


def _decode_ddg_href(href: str) -> str:
    # DuckDuckGo wraps result URLs in a redirect: //duckduckgo.com/l/?uddg=<encoded>
    if "uddg=" in href:
        qs = parse_qs(urlparse(href).query)
        if qs.get("uddg"):
            return unquote(qs["uddg"][0])
    return href


async def _duckduckgo_search(query: str, max_results: int) -> list[dict]:
    async with async_client(timeout=20, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        resp = await client.post("https://html.duckduckgo.com/html/", data={"q": query})
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for result in soup.select(".result"):
        link = result.select_one("a.result__a")
        if not link or not link.get("href"):
            continue
        snippet = result.select_one(".result__snippet")
        results.append(
            {
                "title": link.get_text(strip=True),
                "url": _decode_ddg_href(link["href"]),
                "snippet": snippet.get_text(strip=True) if snippet else "",
            }
        )
        if len(results) >= max_results:
            break
    return results


async def web_search(query: str, max_results: int = 5) -> str:
    settings = get_settings()
    results: list[dict] = []
    errors: list[str] = []

    if settings.searxng_url:
        try:
            results = await _searxng_search(query, max_results)
        except Exception as e:
            errors.append(f"searxng: {e}")

    if not results:
        try:
            results = await _duckduckgo_search(query, max_results)
        except Exception as e:
            errors.append(f"duckduckgo: {e}")

    if not results:
        return f"No results found for {query!r}." + (f" Errors: {'; '.join(errors)}" if errors else "")

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}\n   URL: {r['url']}\n   {r['snippet']}")
    return "\n".join(lines)


web_search_tool = Tool(
    name="web_search",
    description="Search the live internet. Returns numbered results with title, URL and snippet. "
    "Use fetch_page afterwards to read a promising URL in full.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query"},
            "max_results": {"type": "integer", "description": "Max results to return (default 5)"},
        },
        "required": ["query"],
    },
    func=web_search,
)
