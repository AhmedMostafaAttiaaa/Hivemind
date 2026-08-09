import uuid

from app.tools.base import Tool


async def generate_uuid(count: int = 1) -> str:
    """Generate one or more random UUIDs (v4)."""
    count = max(1, min(count, 20))  # sane bounds, no runaway generation
    return "\n".join(str(uuid.uuid4()) for _ in range(count))


uuid_tool = Tool(
    name="generate_uuid",
    description="Generate one or more random UUIDs (v4). Use this instead of making up an id "
    "when the user needs a unique identifier.",
    parameters={
        "type": "object",
        "properties": {
            "count": {"type": "integer", "description": "How many UUIDs to generate (default 1, max 20)"}
        },
        "required": [],
    },
    func=generate_uuid,
)
