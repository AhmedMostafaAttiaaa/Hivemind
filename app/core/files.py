from pathlib import Path

MAX_FILE_BYTES = 200_000


def read_source_file(path: str, max_bytes: int = MAX_FILE_BYTES) -> str:
    """Read a local source file for review.

    Returns the file text, or raises ValueError with a clear message the API can
    surface. Local-dev convenience: it reads any path you point it at, so only
    expose this on a trusted machine.
    """
    p = Path(path).expanduser()
    if not p.exists():
        raise ValueError(f"File not found: {path}")
    if not p.is_file():
        raise ValueError(f"Not a file: {path}")

    data = p.read_bytes()
    truncated = len(data) > max_bytes
    text = data[:max_bytes].decode("utf-8", errors="replace")
    if truncated:
        text += f"\n\n[Truncated at {max_bytes} bytes of {len(data)}]"
    return text
