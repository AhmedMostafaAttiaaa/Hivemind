"""Interactive chat client for the Hivemind swarm.

Talk to the model in the terminal. Each message goes through the swarm's triage
agent, which auto-routes to a specialist and turns on web search when your
message needs it (e.g. "search ...", "latest ...", a URL). While it works, a
live loading bar shows what it's doing — and switches to "Searching the web..."
the moment it actually hits the internet. Conversation history is kept via a
stable session id.

Usage:
    python chat.py                       # connects to http://127.0.0.1:8000
    python chat.py --url http://host:port
    python chat.py --web on              # force web tools on for every message

Commands inside the chat:
    /new     start a fresh conversation (new session)
    /reset   clear the current conversation's memory
    /web on|off|auto   change web mode on the fly
    /exit    quit

Run this with the env's python (or after `conda activate hivemind`), NOT via
`conda run` — conda run does not forward interactive keyboard input.
"""

import argparse
import itertools
import json
import sys
import threading
import time
import uuid

import httpx

# Windows consoles default to cp1252 and choke on non-latin glyphs; force UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

BANNER = """\
Hivemind chat - type your message. It searches the web automatically when needed.
Commands: /new  /reset  /web on|off|auto  /exit
"""


class Loader:
    """A tiny animated 'slide' loading bar with a changeable label.

    Runs on its own thread so it keeps moving while the main thread waits on the
    network. Call set_label() to change the text (e.g. to 'Searching the web...').
    """

    WIDTH = 12

    def __init__(self):
        self._label = "Thinking"
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _render(self) -> None:
        # A block that slides back and forth across a track: [===>      ]
        positions = list(range(self.WIDTH)) + list(range(self.WIDTH - 2, 0, -1))
        for pos in itertools.cycle(positions):
            if self._stop.is_set():
                break
            track = [" "] * self.WIDTH
            track[pos] = "="
            if pos + 1 < self.WIDTH:
                track[pos + 1] = ">"
            bar = "".join(track)
            sys.stdout.write(f"\r  [{bar}] {self._label}...    ")
            sys.stdout.flush()
            time.sleep(0.08)

    def set_label(self, label: str) -> None:
        self._label = label

    def start(self, label: str = "Thinking") -> None:
        self._label = label
        self._stop.clear()
        self._thread = threading.Thread(target=self._render, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join()
        # Clear the loader line so the answer prints cleanly.
        sys.stdout.write("\r" + " " * (self.WIDTH + 40) + "\r")
        sys.stdout.flush()


def _short(text: str, n: int = 48) -> str:
    text = str(text)
    return text if len(text) <= n else text[: n - 1] + "…"


def send(base: str, payload: dict) -> dict:
    """Stream the swarm run, animating a loader, and return the final result."""
    loader = Loader()
    loader.start("Thinking")
    result: dict = {}
    searched: set[str] = set()
    timeout = httpx.Timeout(180.0, connect=5.0)
    try:
        with httpx.stream("POST", f"{base}/swarm/stream", json=payload, timeout=timeout) as r:
            if r.status_code != 200:
                r.read()
                loader.stop()
                return {"_error": f"[error {r.status_code}] {r.text}"}
            for line in r.iter_lines():
                if not line.startswith("data: "):
                    continue
                ev = json.loads(line[6:])
                t = ev.get("type")
                if t == "agent":
                    loader.set_label(f"{ev['agent']} working")
                elif t == "handoff":
                    loader.set_label(f"routing to {ev['to']}")
                elif t == "tool" and ev.get("phase") == "start":
                    if ev["tool"] == "web_search":
                        q = ev.get("arguments", {}).get("query", "")
                        searched.add("web_search")
                        loader.set_label(f"Searching the web: {_short(q)}")
                    elif ev["tool"] == "fetch_page":
                        u = ev.get("arguments", {}).get("url", "")
                        searched.add("fetch_page")
                        loader.set_label(f"Reading {_short(u)}")
                elif t == "tool" and ev.get("phase") == "end":
                    loader.set_label("Reading results")
                elif t == "final":
                    result = ev
                elif t == "error":
                    loader.stop()
                    return {"_error": f"[error] {ev.get('message')}"}
    except Exception as e:  # noqa: BLE001
        loader.stop()
        return {"_error": f"[request failed: {e}]"}
    loader.stop()
    result["_searched"] = sorted(searched)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat with the Hivemind swarm.")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument("--web", choices=["on", "off", "auto"], default="auto", help="web tool mode")
    parser.add_argument("--provider", default=None, help="override LLM provider (e.g. groq)")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    web_mode = args.web
    session_id = f"chat-{uuid.uuid4().hex[:8]}"

    try:
        h = httpx.get(f"{base}/health", timeout=5).json()
        print(f"Connected to {base}  (provider: {h.get('provider')}, model: {h.get('model')})")
    except Exception as e:
        print(f"Could not reach the server at {base}. Is it running?\n  {e}")
        sys.exit(1)

    print(BANNER)

    def use_web_value() -> bool | None:
        return {"on": True, "off": False, "auto": None}[web_mode]

    while True:
        try:
            msg = input("you: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye!")
            return

        if not msg:
            continue
        if msg == "/exit":
            print("bye!")
            return
        if msg == "/new":
            session_id = f"chat-{uuid.uuid4().hex[:8]}"
            print(f"[started a new conversation: {session_id}]")
            continue
        if msg == "/reset":
            try:
                httpx.delete(f"{base}/swarm/sessions/{session_id}", timeout=10)
                print("[conversation memory cleared]")
            except Exception as e:
                print(f"[reset failed: {e}]")
            continue
        if msg.startswith("/web"):
            parts = msg.split()
            if len(parts) == 2 and parts[1] in ("on", "off", "auto"):
                web_mode = parts[1]
                print(f"[web mode: {web_mode}]")
            else:
                print("[usage: /web on|off|auto]")
            continue

        payload = {"task": msg, "session_id": session_id, "use_web": use_web_value()}
        if args.provider:
            payload["provider"] = args.provider

        data = send(base, payload)
        if data.get("_error"):
            print(data["_error"] + "\n")
            continue

        route = " -> ".join(data.get("path", []))
        trace = f"({route}"
        if data.get("_searched"):
            trace += f" | searched: {', '.join(data['_searched'])}"
        trace += ")"
        print(f"bot {trace}:\n{data.get('content', '').strip()}\n")


if __name__ == "__main__":
    main()
