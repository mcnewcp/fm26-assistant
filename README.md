# fm26-assistant

A multi-context monorepo for the FM26 assistant project (agent, telegram bot, and other surfaces TBD).

## Quick start

```bash
# Install dependencies (creates .venv/)
uv sync

# Run tests
uv run pytest

# Type-check
uv run pyright src/

# Lint
uv run ruff check src/
```

## Configuration

Copy the example config and fill in your values:

```bash
cp config.example.toml config.toml
```

Secrets are never written to `config.toml` — set them as environment variables instead:

```bash
export NVIDIA_API_KEY=your_key_here
```

## Package layout (`src/agent/`)

| Package | Responsibility |
|---|---|
| `agent/` | Top-level package — `Agent` class, `cli.py` entrypoint, `config.py` loader |
| `agent/orchestration/` | Layer 1 — LangGraph state machine, nodes, graph composition |
| `agent/operator/` | Layer 2 — `Operator` protocol, planner and grounder implementations |
| `agent/action/` | Layer 3 — MCP client adapters, action-layer tool wrappers |
| `agent/scenarios/` | Scenario loading, routing, and system-prompt rendering |
| `agent/safety/` | Kill switch and session abort handling |
| `agent/observability/` | Structured session logging and per-run artifact storage |

Run artifacts (screenshots, logs) are saved to `runs/` at the repo root (gitignored).

## operator-smoke CLI

A lightweight CLI for testing the Operator (planner + stub grounder) in isolation, without running a full agent session.

```bash
# With a real NVIDIA NIM key:
export NVIDIA_API_KEY=your_key_here
uv run operator-smoke path/to/screenshot.png "Advance to the next match"

# Or via python -m:
uv run python -m agent.operator_smoke path/to/screenshot.png "Advance to the next match"
```

Output is the `ActionPlan` JSON produced by the planner, e.g.:

```json
{
  "action_type": "click",
  "target_description": "Continue button",
  "text": null,
  "key": null,
  "note": "Match prep screen visible.",
  "done": false,
  "done_reason": null,
  "summary": null
}
```

The grounder is stubbed (returns a fixed coordinate) in this slice — real grounding lands in slice #8.

## Working with this repo

This repo uses [`mattpocock/skills`](https://github.com/mattpocock/skills) — a set of opinionated agent skills that structure how planning, ticketing, and implementation get done. The configuration for those skills lives in [docs/agents/](docs/agents/) and is summarised in [CLAUDE.md](CLAUDE.md).

## The workflow loop

```
        ┌──── PLAN ──────┐
        │ grill-with-docs│  ← interrogate, capture decisions inline
        └────────┬───────┘
                 ▼
        ┌── CAPTURE ─────┐
        │ to-prd         │  ← if it's a feature, publish a PRD issue
        │ to-issues      │  ← break it into tracer-bullet tickets
        └────────┬───────┘
                 ▼
        ┌── TRIAGE ──────┐
        │ triage         │  ← move issues through the label state machine
        └────────┬───────┘
                 ▼
        ┌── IMPLEMENT ───┐
        │ tdd            │  ← red → green → refactor on a single ticket
        └────────┬───────┘
                 ▼
        ┌── MAINTAIN ────┐
        │ diagnose       │  ← when something breaks
        │ improve-codebase-architecture │  ← periodic refactor sweeps
        └────────────────┘
```

## When to reach for what

### Planning

- **`/grill-with-docs`** — your default planning tool. Interrogates you about a feature or design idea, checking against existing `CONTEXT.md` and ADRs. As decisions crystallise during the session, the skill writes them straight into the relevant `CONTEXT.md` (glossary, invariants) or opens a new ADR. Use whenever you have a vague idea you want to ground out.
- **`/grill-me`** — same interrogation style but no doc-awareness. Use it for non-engineering planning (process, scope, prioritisation).

### Capturing

- **`/to-prd`** — at the end of a grilling session for a *feature*, formalise it into a PRD (Problem / Solution / User Stories / Implementation Decisions / Testing Decisions / Out of Scope) and publish it as a single GitHub issue.
- **`/to-issues`** — break a PRD, plan, or spec into independently-grabbable vertical-slice tickets. Each ticket cuts end-to-end through every layer (schema → API → UI → tests) rather than being a horizontal slice. Each is tagged AFK (agent can grab it) or HITL (needs a human decision).

### Triage

- **`/triage`** — process incoming issues through a state machine:
  - `needs-triage` → maintainer needs to evaluate
  - `needs-info` → waiting on reporter
  - `ready-for-agent` → fully specified, AFK-ready
  - `ready-for-human` → needs human implementation
  - `wontfix` → will not be actioned

### Implementation

- **`/tdd`** — red → green → refactor on a single ticket. Forces tests-first, especially valuable for backend/agent logic where behaviour is testable.

### Maintenance

- **`/diagnose`** — disciplined diagnosis loop for hard bugs and performance regressions. Reproduce → minimise → hypothesise → instrument → fix → regression-test.
- **`/improve-codebase-architecture`** — periodic (not per-feature) refactor sweep. Looks for tightly-coupled modules to consolidate or deepen, informed by the domain language in `CONTEXT.md` and the decisions in `docs/adr/`.

### Utility

- **`/zoom-out`** — ask the agent for broader context when you're lost in a section of code.
- **`/caveman`** — ultra-compressed responses when you want to save tokens.
- **`/write-a-skill`** — create a new skill of your own.

## PRD vs plan

A **PRD** is a structured feature spec (Problem, Solution, User Stories, Implementation Decisions, Testing Decisions, Out of Scope). It lives as one GitHub issue and serves as the permanent reference for a feature.

A **plan** is anything else that needs to become work — a refactor, a migration, an infrastructure change, a research spike. No fixed structure; it lives in conversation context.

`/to-issues` accepts either, plus any other free-form spec. The flow is:

```
Feature work:    grill → /to-prd → PRD issue → /to-issues → ticket(s)
Non-feature:     grill →           (skip)    → /to-issues → ticket(s)
```

The PRD step is optional — it's the formalisation pass for features that benefit from a permanent reference issue.

## Domain documentation

Two kinds of documents structure this repo's domain:

- **`CONTEXT.md`** (per context, listed in `CONTEXT-MAP.md`) — glossary, invariants, and shape of one bounded context.
- **`docs/adr/`** (root + per-context) — architectural decision records.

You don't pre-write these. They emerge through `/grill-with-docs` sessions as terms and decisions actually crystallise. Hand-editing is fine.

For raw, exploratory architecture material that hasn't been distilled yet, use `notes/`. The current high-level architecture sketch lives at [notes/architecture/01-HLAv1.md](notes/architecture/01-HLAv1.md).

## Getting started

The natural first move on a fresh repo:

1. **Run `/grill-with-docs`** with `notes/architecture/01-HLAv1.md` as input. Goal: identify the bounded contexts (agent, telegram bot, etc.), write the initial `CONTEXT-MAP.md`, and capture the foundational ADRs (chat surface, agent runtime, persistence, etc.).
2. **Pick the first vertical slice** — the smallest end-to-end thing that proves the system works (e.g. "Telegram message in → agent responds with stub data"). Run `/to-prd` to publish it as a GitHub issue.
3. **Run `/to-issues`** against that PRD to break it into 3–5 grabbable tickets.
4. **Pick one ticket, run `/tdd`**, ship it. Repeat.

## Skill configuration

If you ever need to change the issue tracker, triage labels, or domain doc layout, run `/setup-matt-pocock-skills` again. Or edit [docs/agents/](docs/agents/) directly — the files are plain markdown.
