# Swarm Search

A universal **swarm-agent service** that merges the ideas of
[`swarmx-framework`](https://github.com/AhmedMostafaAttiaaa/swarmx-framework)
(multi-agent orchestration with handoffs) and
[`local-web-search-agent`](https://github.com/AhmedMostafaAttiaaa/-local-web-search-agent)
(key-free live internet search), exposed as **microservice-style FastAPI routers**.

## The idea

- **One agent template, every use case.** An `Agent` is just `instructions + tools + handoffs`.
  Coder, researcher, reviewer, generalist — all the same class, different config
  ([app/agents/__init__.py](app/agents/__init__.py)). Add a new role in ~10 lines.
- **Swarm routing.** A `triage` agent classifies each task and hands off via auto-generated
  `handoff_to_<agent>` tools. The `SwarmEngine` follows the handoff chain.
- **Internet on demand.** `web_search` (SearxNG → DuckDuckGo fallback, no API key) and
  `fetch_page` are injected only when you set `use_web: true` — or automatically when the task
  looks like it needs the web ("search...", "latest...", contains a URL).
- **Provider-agnostic.** Ollama (local, default) or Groq behind one `BaseLLM` interface;
  switch globally via `.env` or per-request with `"provider": "groq"`.

## Quick start

```bash
pip install -r requirements.txt
copy .env.example .env        # then edit if needed

# default backend is local Ollama — make sure a tool-calling model is pulled:
ollama pull llama3.1

python run.py                 # serves http://127.0.0.1:8000  (docs at /docs)
```

To use Groq (recommended if you don't have a GPU — local qwen3 on CPU takes minutes per
turn, Groq answers in seconds): set `LLM_PROVIDER=groq` and `GROQ_API_KEY=...` in `.env`,
or add `"provider": "groq"` to any request body.

**Behind a corporate TLS proxy?** If outbound HTTPS fails with
`CERTIFICATE_VERIFY_FAILED`, set `SSL_VERIFY=false` in `.env`.

## API (the "microservices")

| Endpoint | What it does |
|---|---|
| `POST /swarm/run` | Any task — triage routes it to the right specialist |
| `POST /agents/search` | Researcher agent (web on by default) |
| `POST /agents/code` | Coder agent |
| `POST /agents/review` | Code-review agent (`{code, context}`) |
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

# Code review directly:
curl -X POST localhost:8000/agents/review -H "Content-Type: application/json" \
  -d '{"code": "def div(a,b): return a/b", "context": "python utility"}'

# Force internet on, keep conversation memory, use Groq for this request:
curl -X POST localhost:8000/swarm/run -H "Content-Type: application/json" \
  -d '{"task": "who won the last world cup?", "use_web": true, "session_id": "s1", "provider": "groq"}'
```

Responses include `final_agent`, the handoff `path` (e.g. `["triage", "coder"]`),
whether the web was enabled, and a log of every tool call the agents made.

## Project layout

```
app/
├── main.py               # FastAPI app, mounts all routers
├── api/                  # HTTP layer: schemas + routers (swarm, agents, web)
├── swarm/                # engine: Agent template, handoffs, SwarmEngine, session memory
├── agents/               # role definitions (triage, researcher, coder, reviewer, generalist)
├── llm/                  # BaseLLM + Ollama and Groq adapters
├── tools/                # web_search (SearxNG/DuckDuckGo) + fetch_page
└── core/                 # settings (.env)
```

## Extending

1. **New role**: add an `Agent(...)` in `app/agents/__init__.py` and put its name in
   `triage.handoffs`. It is instantly available at `POST /agents/<name>/run` and reachable
   by the router.
2. **New tool**: create a `Tool` in `app/tools/` and attach it to any agent's `tools` list.
3. **New provider**: implement `BaseLLM.chat()` in `app/llm/` and register it in `get_llm()`.
4. **Real microservices later**: each router is self-contained, so splitting `/agents/search`
   etc. into separate deployments is a copy-paste + gateway job, not a rewrite.
