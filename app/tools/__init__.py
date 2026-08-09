from app.tools.base import Tool
from app.tools.calculator import calculator_tool
from app.tools.datetime_tool import datetime_tool
from app.tools.fetch_page import fetch_page_tool
from app.tools.text_stats import text_stats_tool
from app.tools.uuid_tool import uuid_tool
from app.tools.web_search import web_search_tool

WEB_TOOLS: list[Tool] = [web_search_tool, fetch_page_tool]

# Small, safe, no-network utilities always available to every agent.
UTILITY_TOOLS: list[Tool] = [calculator_tool, datetime_tool, text_stats_tool, uuid_tool]
