import re

from bs4 import BeautifulSoup

from app.core.http import async_client
from app.tools.base import Tool
from app.tools.web_search import USER_AGENT

MAX_CHARS = 8000


async def fetch_page(url: str) -> str:
    try:
        async with async_client(
            timeout=25, headers={"User-Agent": USER_AGENT}, follow_redirects=True
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except Exception as e:
        return f"Failed to fetch {url}: {e}"

    content_type = resp.headers.get("content-type", "")
    if "html" not in content_type and "text" not in content_type:
        return f"Unsupported content type at {url}: {content_type}"

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside", "form"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()

    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + f"\n\n[Truncated at {MAX_CHARS} characters]"
    return text or f"No readable text extracted from {url}."


fetch_page_tool = Tool(
    name="fetch_page",
    description="Download a URL and return its readable text content (scripts/nav stripped, truncated).",
    parameters={
        "type": "object",
        "properties": {"url": {"type": "string", "description": "The full URL to fetch"}},
        "required": ["url"],
    },
    func=fetch_page,
)
