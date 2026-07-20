# Hivemind — Full Project Documentation

Everything about this project in one place: what it is, how it's built, **why** each
technology was chosen, how the pieces fit together, and how to reuse or integrate it in
future projects and tasks.

> Companion files: [README.md](README.md) (quick start), `COMMANDS.md` (local run/test
> cheat sheet, gitignored), `secu.md` (environment security notes, gitignored),
> [index.html](index.html) (visual overview page).

---

## 1. What Hivemind is

Hivemind is a **universal multi-agent "swarm" service** exposed over an HTTP API. You give
it a task in plain language; it decides which specialist should handle it, does the work
(including searching the live internet when needed), and returns the answer.

It merges two earlier ideas of ours:
- **swarmx-framework** — orchestrating multiple AI agents that hand work off to each other.
- **local-web-search-agent** — giving a model key-free access to real web search.

The design goal: **one small, reusable agent template that works for every kind of task**
(coding, research, code review, general Q&A), instead of a separate bespoke bot per task.

---

## 2. The core idea (mental model)

Three concepts carry the whole system:

1. **An Agent is just data.** Every "role" is the *same* `Agent` class configured with three
   things: `instructions` (its system prompt / personality), `tools` (functions it may call),
   and `handoffs` (other agents it may delegate to). A coder and a researcher differ only in
   configuration — not in code.

2. **A swarm routes and delegates.** A special `triage` agent reads the request and hands it
   to the best specialist using auto-generated `handoff_to_<agent>` tools. The `SwarmEngine`
   follows that chain of handoffs until an agent produces a final answer. One request can flow
   `triage → coder → reviewer`.

3. **Tools are injected on demand.** The web tools (`web_search`, `fetch_page`) are only given
   to the agent when the task needs them — either because you set `use_web: true`, or because
   the engine detected web-intent words ("search", "latest", a URL). The model can't browse
   unless we hand it the tools, so this is also a safety boundary.

Because behavior lives in configuration, adding a capability is ~10 lines (a new `Agent`),
and nothing in the engine changes.

---

## 3. Architecture at a glance

```
                       HTTP request (JSON)
                              │
                    ┌─────────▼──────────┐
                    │   FastAPI routers  │   app/api/routers/{swarm,agents,web}.py
                    │  /swarm  /agents   │
                    │  /web    /health   │
                    └─────────┬──────────┘
                              │ task, use_web, session_id, provider
                    ┌─────────▼──────────┐
                    │    SwarmEngine     │   app/swarm/engine.py
                    │  route + handoffs  │   - web-intent detection
                    │  + emit events     │   - session memory
                    └─────────┬──────────┘
                              │ runs agents in a loop
                    ┌─────────▼──────────┐        ┌──────────────────┐
                    │       Agent        │───────▶│      Tools       │  app/tools/
                    │ instructions+tools │  calls │ web_search       │
                    │ tool-calling loop  │◀───────│ fetch_page       │
                    └─────────┬──────────┘        └──────────────────┘
                              │ chat()
                    ┌─────────▼──────────┐
                    │      BaseLLM       │   app/llm/
                    │  Ollama  │  Groq   │   provider-agnostic adapters
                    └────────────────────┘
```

The **request lifecycle** (walkthrough of one call to `POST /swarm/run`):

1. Router receives `{task, use_web?, session_id?, provider?}` and calls `engine.run(...)`.
2. Engine decides if web tools are active (`use_web` flag, else auto-detect from the task).
3. Engine loads any prior conversation from session memory and starts at the `triage` agent.
4. The agent sends the conversation + its tool schemas to the LLM (`BaseLLM.chat`).
5. If the model calls a **handoff** tool → the engine switches to that agent and repeats.
   If it calls a **real tool** (e.g. `web_search`) → the tool runs, its result is fed back,
   and the agent continues. If it returns plain text → that's the final answer.
6. The engine records the answer to memory and returns a `SwarmResult` with the answer, the
   `path` of agents, whether the web was used, and a log of tool calls.

`POST /swarm/stream` does the same but **emits each step as it happens** (Server-Sent Events),
which is what powers the terminal chat's live "Searching the web…" loader.

---

## 4. The tech stack — what and why

| Technology | Role in Hivemind | Why we chose it |
|---|---|---|
| **Python 3.11** | Everything | The lingua franca of AI/LLM tooling; every model SDK and scraping lib is Python-first. 3.11 for speed + modern typing (`X | None`). |
| **FastAPI** | The HTTP layer / "microservices" | Async-native (essential — most time is spent awaiting the LLM and network), automatic request validation via type hints, and free interactive docs at `/docs`. Turning a function into an endpoint is one decorator. |
| **Uvicorn** | ASGI server that runs FastAPI | The standard, fast ASGI server; `--reload` gives instant dev feedback. |
| **httpx** | All outbound HTTP (LLM APIs, web search, page fetch) | A modern `requests` with **async** support and streaming — needed so many awaited calls don't block the event loop. One client style for every call, routed through a shared factory that honors `SSL_VERIFY`. |
| **Pydantic v2 + pydantic-settings** | Request/response schemas + config from `.env` | Validation and typed settings for free. Bad requests are rejected with clear errors before our code runs; config is just a typed class. |
| **BeautifulSoup4** | HTML → clean text in `fetch_page` and the DuckDuckGo fallback | Robust, forgiving HTML parsing to strip scripts/nav and extract readable content for the model. |
| **Server-Sent Events (SSE)** | Streaming progress from `/swarm/stream` | One-way server→client streaming is exactly what a "live status" needs; it's plain HTTP (works through proxies, no WebSocket handshake) and is trivially consumed by both a CLI and a browser `EventSource` — so the future UI reuses the same endpoint. |
| **Ollama** | Local LLM provider | Runs models on your own machine, no API key, full privacy. Great default for offline/dev. |
| **Groq** | Cloud LLM provider | Extremely fast inference (seconds vs minutes on CPU). The practical choice when there's no GPU. Same OpenAI-style tool-calling API. |
| **SearXNG (Docker)** | Self-hosted metasearch engine | Aggregates many search engines, returns clean JSON, no API key or rate-limit account. Dockerized so it's one command to run and isolated from the app. |
| **DuckDuckGo (scrape)** | Search fallback | Zero setup; works when SearXNG isn't running so the demo never hard-fails. |
| **Docker Compose** | Runs SearXNG | Reproducible, isolated infra with one `up -d`; keeps the search engine out of the Python process. |
| **Conda** | Environment management | Clean, reproducible Python env (`hivemind`) separate from system Python, avoiding dependency clashes. |

**Cross-cutting design choices and why:**
- **Provider-agnostic `BaseLLM`.** Both Ollama and Groq normalize to one `LLMResponse` shape,
  so the agents/engine never know which model they're using. Swapping providers is a config
  change; adding OpenAI/Anthropic later is one new adapter.
- **Low, configurable temperature (`LLM_TEMPERATURE`, default 0.2).** Keeps answers steady and
  on-persona and makes tool-calling far more reliable (models emit cleaner JSON at low temp).
- **Auto web-intent detection.** Convenience + control: users don't have to remember a flag,
  but web access is still off by default and only enabled when relevant.
- **Session memory as a swappable component.** In-memory dict today; the interface is small
  enough to replace with Redis/DB for multi-instance deployments.

---

## 5. Directory map

```
app/
├── main.py                     # FastAPI app; mounts routers; /health
├── api/
│   ├── schemas.py              # Pydantic request/response models
│   └── routers/
│       ├── swarm.py            # /swarm/run, /swarm/stream (SSE), /swarm/agents, sessions
│       ├── agents.py           # /agents/{search,code,review,review/questions,review/file,general,{name}/run}
│       └── web.py              # /web/search, /web/fetch (raw, no LLM)
├── swarm/
│   ├── base.py                 # Agent template + tool-calling loop + event emitter
│   ├── engine.py               # SwarmEngine: routing, handoffs, web-intent, sessions
│   └── memory.py               # per-session conversation history
├── agents/__init__.py          # role definitions + shared "Ahmed Attia's assistant" persona
├── llm/
│   ├── base.py                 # BaseLLM interface + LLMResponse/ToolCall
│   ├── ollama_client.py        # local provider (+ qwen3 /no_think handling)
│   ├── groq_client.py          # cloud provider (+ malformed tool-call recovery)
│   └── __init__.py             # get_llm() factory + provider aliases (groq/qroq)
├── tools/
│   ├── base.py                 # Tool dataclass (name, description, params, func)
│   ├── web_search.py           # SearXNG → DuckDuckGo fallback
│   └── fetch_page.py           # URL → readable text
└── core/
    ├── config.py               # Settings from .env (pydantic-settings)
    ├── http.py                 # async httpx client honoring SSL_VERIFY
    └── files.py                # safe source-file reader (for file review)

chat.py                         # interactive chat client with the live search loader (SSE)
run.py                          # convenience launcher (uvicorn on :8000)
docker-compose.yml + searxng/   # SearXNG service (JSON API enabled)
index.html                      # visual project overview (GitHub Pages)
requirements.txt / .env.example
```

---

## 6. Configuration (`.env`)

| Key | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama` (local) or `groq` (cloud). `qroq`/`qrop` are accepted aliases. |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | `localhost:11434` / `llama3.1` | Local model settings. |
| `GROQ_API_KEY` / `GROQ_MODEL` | — / `llama-3.3-70b-versatile` | Cloud model settings. |
| `LLM_TEMPERATURE` | `0.2` | Sampling temperature (low = steady, reliable tool calls). |
| `SEARXNG_URL` | empty | If set (e.g. `http://localhost:8080`), search uses SearXNG first. |
| `MAX_TOOL_ITERATIONS` | `6` | Max tool calls per agent before forcing a final answer. |
| `MAX_HANDOFFS` | `4` | Max agent handoffs per request (prevents loops). |
| `SSL_VERIFY` | `true` | Set `false` only behind a TLS-intercepting corporate proxy. |

Per-request overrides in the JSON body: `provider`, `use_web`, `session_id`.

---

## 7. Notable design decisions & the problems they solved

These are the non-obvious calls made while building it (useful if you fork or debug):

- **qwen3 `/no_think`.** Some Ollama builds ignore the API `think:false` flag, so qwen3 wastes
  minutes emitting chain-of-thought. We inject the `/no_think` soft switch into the prompt for
  qwen3 models. (See `app/llm/ollama_client.py`.)
- **Groq malformed tool-call recovery.** Llama-on-Groq occasionally emits a tool call as
  `<function=name {json}</function>` instead of JSON, which Groq rejects with `tool_use_failed`.
  We run at low temperature and, if it still happens, parse the intended call out of the error
  payload. (See `app/llm/groq_client.py`.)
- **`SSL_VERIFY` toggle.** A corporate proxy that MITMs TLS breaks certificate verification.
  A single setting, threaded through one shared httpx factory, unblocks that environment
  (details and the safer CA-bundle alternative are in `secu.md`).
- **CPU vs GPU reality.** Ollama on CPU (`size_vram: 0`) is minutes-per-turn; Groq answers in
  seconds. That's why Groq is the recommended provider for testing here.

---

## 8. How to extend it

1. **Add a specialist:** define an `Agent(name, description, instructions, tools=?, handoffs=?)`
   in `app/agents/__init__.py`, add its name to the registry list (and to `triage.handoffs` if
   triage should route to it). Instantly available at `POST /agents/<name>/run`.
2. **Build a multi-agent pipeline:** list downstream agents in an agent's `handoffs`
   (e.g. `coder` → `reviewer` → `tester`); the engine follows the chain up to `MAX_HANDOFFS`,
   and the response `path` shows every agent that touched the task.
3. **Add a tool:** create a `Tool` in `app/tools/` and attach it to any agent's `tools` list
   (or inject it globally like the web tools). Tools are just async functions with a JSON schema.
4. **Add a provider:** implement `BaseLLM.chat()` in `app/llm/` (normalize to `LLMResponse`)
   and register it in `get_llm()`. Agents and the engine need no changes.

---

## 9. Using Hivemind in other projects and tasks (the future)

Hivemind is deliberately a **service with a small, stable HTTP contract**, so other systems can
use it without importing any of its code. Ways to integrate:

**A. As a backend microservice (most common).**
Any app — a web frontend, a mobile app, another backend — calls `POST /swarm/run` (or the
per-agent endpoints) over HTTP. Because it's already router-per-capability, you can later split
`/agents/search`, `/agents/code`, etc. into separately deployed services behind a gateway with
no rewrite.

**B. Embed the library directly.**
Skip HTTP and import the engine in another Python program:
```python
from app.agents import REGISTRY
from app.swarm import SwarmEngine

engine = SwarmEngine(registry=REGISTRY)
result = await engine.run("summarize the latest AI news", use_web=True, provider="groq")
print(result.content, result.path)
```
Useful for scripts, notebooks, or building a bigger app around the swarm.

**C. Power a UI with the streaming endpoint.**
`POST /swarm/stream` emits SSE events (`agent`, `handoff`, `tool start/end`, `final`). A browser
`EventSource` (or the existing `chat.py`) can render live "thinking / searching" status. The web
UI you build later reuses this endpoint unchanged.

**D. As a chat bot.**
Wrap the API in a Slack/Discord/Telegram bot: forward each message to `/swarm/run` with a stable
`session_id` per channel/user for memory. The persona and auto-search come for free.

**E. In CI / developer tooling.**
The file-review endpoints (`/agents/review/questions` → `/agents/review/file`) fit a code-review
step: point them at changed files in a pull request, capture the review as a comment. Because the
reviewer asks clarifying questions first, you can pre-seed answers (target runtime, standards) in
the `answers` field for consistent automated reviews.

**F. As a tool for *other* AI agents (MCP / function-calling).**
Expose `swarm/run` as a single callable tool to another LLM/agent framework (e.g. wrap it as an
MCP server or an OpenAI/Anthropic function). Then a higher-level agent can delegate whole
sub-tasks — "research X", "review this file" — to Hivemind as one action.

**G. Scaling for production.**
- Swap `app/swarm/memory.py` (in-memory dict) for Redis/Postgres so multiple server instances
  share sessions.
- Put the API behind auth (API keys / OAuth) and rate limiting.
- Run SearXNG and the API as separate Docker services; add more provider adapters
  (OpenAI, Anthropic, Gemini) behind `BaseLLM`.
- Add observability (the SSE events are already a natural hook for metrics/tracing).

---

## 10. Limitations & roadmap

- **Memory is in-process** — fine for one server; needs Redis/DB to scale out.
- **File review reads local paths** — convenient for a trusted dev machine; add sandboxing/allow-
  lists before exposing it publicly.
- **No auth** on the API yet — add before any non-local deployment.
- **Only swarm (routing) mode** is implemented; fixed **workflow** and **parallel/graph** modes
  are natural next additions to the engine.
- **Two providers** (Ollama, Groq) — the `BaseLLM` seam makes adding more straightforward.

---

## 11. TL;DR

Hivemind is one reusable agent template, a small routing engine, and pluggable tools/providers,
wrapped in a FastAPI service. It chats, codes, researches (with real web access and a live
loader), and reviews code — and because it's a clean HTTP service with a streaming endpoint and a
provider-agnostic core, you can drop it behind a UI, a bot, a CI pipeline, or a bigger agent with
almost no glue code.

*Built by Ahmed Attia.*
