# Context Map

V1 has a single context. Additional contexts will appear as later phases (§13 of [the HLA](./notes/architecture/01-HLAv1.md)) introduce them.

## Contexts

- [Agent](./src/agent/CONTEXT.md) — the four-layer computer-use agent that observes screenshots, decides actions, and operates the OS to drive a target desktop application.

## Future contexts (sketched in HLA §13, not yet built)

Each gets its own `CONTEXT.md` when the phase is built — language is expected to diverge from `agent`:

- **Telegram bot** (Phase 2) — chat frontend that drives `Agent.run()` from a phone.
- **Scouting DB** (Phases 3 + 4) — structured player data extracted via Nemotron-Parse, persisted in SQLite via MCP.
- **Vault** (Phase 5) — Obsidian markdown notebook shared between user and agent.
