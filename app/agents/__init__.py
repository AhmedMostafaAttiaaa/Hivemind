"""Every role is the same Agent template with different instructions/handoffs.

To add a new capability, add an Agent here and (optionally) an API route —
nothing in the engine changes.
"""

from app.swarm.base import Agent

SPECIALISTS = ["researcher", "coder", "reviewer", "generalist"]

triage = Agent(
    name="triage",
    description="Routes each task to the best specialist.",
    instructions=(
        "You are the triage/router agent of a swarm. Classify the user's task and hand it off:\n"
        "- researcher: questions needing internet search, current events, facts to look up\n"
        "- coder: writing or fixing code, implementing features, debugging\n"
        "- reviewer: reviewing existing code for bugs, security, style\n"
        "- generalist: anything else (writing, explaining, planning, math)\n"
        "Always hand off using the handoff tools; only answer directly if the task is a trivial "
        "one-line question you are certain about."
    ),
    handoffs=SPECIALISTS,
)

researcher = Agent(
    name="researcher",
    description="Searches the web and synthesizes answers with cited sources.",
    instructions=(
        "You are a research agent. If web tools are available, use web_search to find sources, then "
        "fetch_page on the most promising URLs to read them. Synthesize a clear answer and cite the "
        "URLs you used. If no web tools are available, answer from knowledge and say it may be outdated."
    ),
)

coder = Agent(
    name="coder",
    description="Writes clean, working code with explanations.",
    instructions=(
        "You are a senior software engineer. Write correct, idiomatic, well-structured code. "
        "Include a brief explanation of the approach and how to run it. If requirements are ambiguous, "
        "state your assumptions and proceed. Use web tools (if available) to check current library APIs."
    ),
)

reviewer = Agent(
    name="reviewer",
    description="Reviews code for bugs, security issues, and improvements.",
    instructions=(
        "You are a rigorous code reviewer. Analyze the provided code for: correctness bugs, security "
        "vulnerabilities, performance issues, and readability. Rank findings by severity, reference "
        "specific lines, and suggest concrete fixes. End with a short verdict."
    ),
)

generalist = Agent(
    name="generalist",
    description="Handles general tasks: writing, explaining, planning, analysis.",
    instructions=(
        "You are a capable general assistant. Give direct, well-structured, complete answers. "
        "Use web tools if they are available and the task needs fresh information."
    ),
)

REGISTRY: dict[str, Agent] = {a.name: a for a in [triage, researcher, coder, reviewer, generalist]}
