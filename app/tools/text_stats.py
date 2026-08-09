import re

from app.tools.base import Tool


async def text_stats(text: str) -> str:
    """Count words, characters, lines, and sentences in a piece of text."""
    words = len(text.split())
    chars = len(text)
    chars_no_spaces = len(text.replace(" ", "").replace("\n", "").replace("\t", ""))
    lines = text.count("\n") + 1 if text else 0
    sentences = len([s for s in re.split(r"[.!?]+", text) if s.strip()])
    return (
        f"words={words}, characters={chars}, characters_no_spaces={chars_no_spaces}, "
        f"lines={lines}, sentences={sentences}"
    )


text_stats_tool = Tool(
    name="text_stats",
    description="Count words, characters, lines, and sentences in a given text. "
    "Use this instead of counting by hand when asked about text length/size.",
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string", "description": "The text to analyze"}},
        "required": ["text"],
    },
    func=text_stats,
)
