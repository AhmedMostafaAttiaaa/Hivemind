"""Interactive chat client for the Hivemind swarm.

Talk to the model in the terminal. Each message goes through the swarm's triage
agent, which auto-routes to a specialist and turns on web search when your
message needs it (e.g. "search ...", "latest ...", a URL). Conversation history
is kept via a stable session id.

Usage:
    python chat.py                       # connects to http://127.0.0.1:8000
    python chat.py --url http://host:port
    python chat.py --web on              # force web tools on for every message

Commands inside the chat:
    /new     start a fresh conversation (new session)
    /reset   clear the current conversation's memory
    /web on|off|auto   change web mode on the fly
    /exit    quit
"""

import argparse
import sys
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat with the Hivemind swarm.")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument("--web", choices=["on", "off", "auto"], default="auto", help="web tool mode")
    parser.add_argument("--provider", default=None, help="override LLM provider (e.g. groq)")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    web_mode = args.web
    session_id = f"chat-{uuid.uuid4().hex[:8]}"

    # Fail fast with a friendly message if the server isn't up.
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

        try:
            r = httpx.post(f"{base}/swarm/run", json=payload, timeout=180)
            if r.status_code != 200:
                print(f"[error {r.status_code}] {r.text}\n")
                continue
            data = r.json()
        except Exception as e:
            print(f"[request failed: {e}]\n")
            continue

        # Show a small trace: which agents handled it and whether it searched.
        route = " -> ".join(data.get("path", []))
        searched = [e["tool"] for e in data.get("tool_events", []) if e["tool"] in ("web_search", "fetch_page")]
        trace = f"({route}"
        if data.get("web_enabled") and searched:
            trace += f" | searched: {', '.join(sorted(set(searched)))}"
        trace += ")"

        print(f"bot {trace}:\n{data.get('content', '').strip()}\n")


if __name__ == "__main__":
    main()
