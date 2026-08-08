from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.tools.base import Tool


async def get_current_datetime(timezone: str = "UTC") -> str:
    """Return the current date and time, optionally in a given IANA timezone."""
    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        return f"Unknown timezone {timezone!r}. Use an IANA name, e.g. 'Africa/Cairo', 'UTC', 'America/New_York'."
    now = datetime.now(tz)
    return now.strftime(f"%A, %Y-%m-%d %H:%M:%S %Z ({timezone})")


datetime_tool = Tool(
    name="get_current_datetime",
    description="Get the current date and time. Use this instead of guessing 'today's date' "
    "or doing time-zone math yourself.",
    parameters={
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "IANA timezone name, e.g. 'UTC', 'Africa/Cairo', 'America/New_York'. Defaults to UTC.",
            }
        },
        "required": [],
    },
    func=get_current_datetime,
)
