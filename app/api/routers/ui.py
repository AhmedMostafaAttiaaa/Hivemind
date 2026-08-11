from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["ui"])

UI_FILE = Path(__file__).resolve().parent.parent.parent / "static" / "ui.html"


@router.get("/ui", response_class=HTMLResponse)
async def serve_ui() -> str:
    """A very small browser UI for testing the swarm: chat + a live status orb."""
    return UI_FILE.read_text(encoding="utf-8")
