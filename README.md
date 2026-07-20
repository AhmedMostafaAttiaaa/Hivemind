#  Hivemind

A universal **swarm-agent service** that merges the ideas of
[`swarmx-framework`](https://github.com/AhmedMostafaAttiaaa/swarmx-framework)
(multi-agent orchestration with handoffs) and
[`local-web-search-agent`](https://github.com/AhmedMostafaAttiaaa/-local-web-search-agent)
(key-free live internet search), exposed as **microservice-style FastAPI routers**.

 **[View the project overview page →](https://ahmedmostafaattiaaa.github.io/Hivemind/)**
&nbsp;(the styled `index.html`, served via GitHub Pages)

## The idea

- **One agent template, every use case.** An `Agent` is just `instructions + tools + handoffs`.
  Coder, researcher, reviewer, generalist — all the same class, different config
  ([app/agents/__init__.py](app/agents/__init__.py)). Add a new role in ~10 lines.
- **Swarm routing.** A `triage` agent classifies each task and hands off via auto-generated
  `handoff_to_<agent>` tools. The `SwarmEngine` follows the handoff chain, so one request can
  flow `triage → coder → reviewer`.
- **Internet on demand.** `web_search` (SearXNG → DuckDuckGo fallback, no API key) and
  `fetch_page` are injected only when you set `use_web: true` — or automatically when the task
  looks like it needs the web ("search...", "latest...", contains a URL).
- **Chat that searches, with a live loader.** Talk to it in the terminal; it searches the web on
  its own when needed and shows a "Searching the web…" indicator (streamed over SSE).
- **Personable & consistent.** Every agent answers as *Ahmed Attia's assistant*, at a low
  temperature for steady, on-persona replies.
- **Provider-agnostic.** Ollama (local) or Groq (fast cloud) behind one `BaseLLM` interface;
  switch globally via `.env` or per-request with `"provider": "groq"`.

## Quick start

```bash
pip install -r requirements.txt          # or: conda create -n hivemind python=3.11 && pip install -r requirements.txt
copy .env.example .env                    # then edit

python run.py                             # serves http://127.0.0.1:8000  (docs at /docs)
```

**Provider:** set `LLM_PROVIDER=groq` + `GROQ_API_KEY=...` in `.env` for fast cloud inference
(recommended without a GPU), or `LLM_PROVIDER=ollama` + `ollama pull llama3.1` for fully local.

**Behind a corporate TLS proxy?** If outbound HTTPS fails with `CERTIFICATE_VERIFY_FAILED`,
set `SSL_VERIFY=false` in `.env`.

## Chat (with live "searching" loader)

```bash
python chat.py                 # connects to http://127.0.0.1:8000
```
Just chat — it auto-searches when a message needs the web, showing a sliding loader that
switches to `Searching the web…` / `Reading …` while it's online. In-chat commands:
`/new`, `/reset`, `/web on|off|auto`, `/exit`.
(Run it with the env's python or after `conda activate` — not `conda run`.)

## SearXNG via Docker (optional, better search)

```bash
docker compose up -d                      # SearXNG on http://localhost:8080 (JSON API enabled)
# then set SEARXNG_URL=http://localhost:8080 in .env and restart the server
```
With `SEARXNG_URL` set, `web_search` prefers SearXNG and falls back to DuckDuckGo scraping.

## API (the "microservices")

| Endpoint | What it does |
|---|---|
| `POST /swarm/run` | Any task — triage routes it to the right specialist |
| `POST /swarm/stream` | Same as `/run` but streams progress as **SSE** (drives the chat loader / a UI) |
| `POST /agents/search` | Researcher agent (web on by default) |
| `POST /agents/code` | Coder agent |
| `POST /agents/review` | Code review from inline `{code, context}` |
| `POST /agents/review/questions` | Point at a file → reviewer's clarifying **questions** first |
| `POST /agents/review/file` | Review a file, using your `answers` to those questions |
| `POST /agents/general` | Generalist agent |
| `POST /agents/{name}/run` | Run any registered agent directly |
| `GET /swarm/agents` | List registered agents |
| `POST /web/search`, `POST /web/fetch` | Raw search/fetch, no LLM |
| `GET /health` | Provider + model status |

### Examples

```bash
# Let the swarm decide (auto-detects it needs the web):
curl -X POST localhost:8000/swarm/run -H "Content-Type: application/json" \
  -d '{"task": "search for the latest FastAPI release and summarize what is new"}'

# Coding task — triage hands off to the coder:
curl -X POST localhost:8000/swarm/run -H "Content-Type: application/json" \
  -d '{"task": "write a python function that merges two sorted lists"}'

# File review — step 1: get the reviewer's questions, step 2: review with answers
curl -X POST localhost:8000/agents/review/questions -H "Content-Type: application/json" \
  -d '{"file_path": "path/to/file.py", "context": "python module"}'
curl -X POST localhost:8000/agents/review/file -H "Content-Type: application/json" \
  -d '{"file_path": "path/to/file.py", "answers": "1. Python 3.11  2. ..."}'
```

Responses include `final_agent`, the handoff `path` (e.g. `["triage", "coder"]`),
whether the web was enabled, and a log of every tool call the agents made.

## Project layout

```
app/
├── main.py               # FastAPI app, mounts all routers
├── api/                  # HTTP layer: schemas + routers (swarm, agents, web)
├── swarm/                # engine: Agent template, handoffs, SwarmEngine, session memory, SSE events
├── agents/               # role definitions + shared "Ahmed Attia's assistant" persona
├── llm/                  # BaseLLM + Ollama and Groq adapters (configurable temperature)
├── tools/                # web_search (SearXNG/DuckDuckGo) + fetch_page
└── core/                 # settings (.env), shared http client, file reader
chat.py                   # interactive chat client with the live search loader
docker-compose.yml        # SearXNG service
index.html                # project overview page (GitHub Pages)
```

## Extending

1. **New role**: add an `Agent(...)` in `app/agents/__init__.py` and put its name in
   `triage.handoffs`. It is instantly available at `POST /agents/<name>/run` and reachable
   by the router.
2. **Multi-agent pipelines**: list other agents in an agent's `handoffs` (e.g. `coder`→`reviewer`
   →`tester`); the engine follows the chain up to `MAX_HANDOFFS`.
3. **New tool**: create a `Tool` in `app/tools/` and attach it to any agent's `tools` list.
4. **New provider**: implement `BaseLLM.chat()` in `app/llm/` and register it in `get_llm()`.

---
Built by **Ahmed Attia**.
