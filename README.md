# fm26-assistant

A computer-use agent that drives Football Manager 26, handling high-volume routine tasks and surfacing moments that need the player's attention.

## Quickstart

**Requirements:** Python 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
# Install all dependencies (including dev tools)
uv sync

# Run tests
uv run pytest

# Type-check
uv run pyright src/

# Lint
uv run ruff check src/
```

## Configuration

Copy the example config and set your API key:

```bash
cp config.example.toml config.toml
export NVIDIA_API_KEY=nvapi-...   # never put secrets in config.toml
```

Then run the agent:

```bash
uv run fm26 "advance to the next match"
```

## Package layout

```
src/agent/
├── agent.py          # Public Agent class — the entry point for all surfaces
├── cli.py            # CLI shell over Agent.run()
├── config.py         # Config model (pydantic-settings + config.toml)
├── orchestration/    # Layer 1 — LangGraph nodes, agent state, graph composition
├── operator/         # Layer 2 — Operator protocol, planner, grounder
├── action/           # Layer 3 — MCP server client, tool surface
├── scenarios/        # Scenario markdown loading and router
├── safety/           # Kill switch and abort handling
└── observability/    # Structured logging and screenshot persistence
```

Session outputs (screenshots, logs) are written to `runs/` at the repo root.

## Working with this repo

See [README workflow section](README.md) for the planning → triage → implement loop powered by [`mattpocock/skills`](https://github.com/mattpocock/skills). Architecture details live in [`notes/architecture/01-HLAv1.md`](notes/architecture/01-HLAv1.md).
