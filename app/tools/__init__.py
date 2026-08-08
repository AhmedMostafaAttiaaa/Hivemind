from app.tools.base import Tool
from app.tools.calculator import calculator_tool
from app.tools.fetch_page import fetch_page_tool
from app.tools.web_search import web_search_tool

WEB_TOOLS: list[Tool] = [web_search_tool, fetch_page_tool]

# Small, safe, no-network utilities always available to every agent.
UTILITY_TOOLS: list[Tool] = [calculator_tool]
