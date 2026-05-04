# Session termination model: done, handoff, stuck, aborted

A session ends in one of **four** terminal states, not two as the HLA implies. The new state is **handoff** — the planner halts because game state demands user attention (e.g. a player injury), surfacing a reason. This is the architectural primitive behind the HLA's "surface the moments that actually want the player's attention" framing in §1; without it, scenarios couldn't declare halt conditions, the planner had no schema for halting-with-reason, and the user-facing artifact of a run was unspecified.

## Decision

| Terminal state | Trigger | Initiator |
|---|---|---|
| **Done** | Goal satisfied | Planner |
| **Handoff** | Scenario-declared condition met (e.g. injury); reason surfaced | Planner |
| **Stuck** | Step budget exhausted, persistent transport failure, or malformed planner output | Orchestration |
| **Aborted** | Mouse movement or `cmd+shift+escape` (kill switch) | User |

`Done` and `Handoff` are unified in `ActionPlan`:

```python
done: bool = False
done_reason: Literal["goal_complete", "handoff"] | None = None
summary: str | None = None  # set when done=True
```

`Stuck` is set by the orchestration layer for any unrecoverable orchestration-level failure, with a discriminated reason:

```python
# Set by orchestration when entering Stuck state — not on ActionPlan:
stuck_reason: Literal[
    "budget_exhausted",         # step counter hit max_steps
    "model_unreachable",        # planner or grounder API persistently failing after backoff
    "malformed_planner_output", # JSON mode failed twice consecutively
]
```

The reason is surfaced in the final digest so the user can distinguish "ran out of steps" from "lost the network." `Aborted` is handled by the kill-switch path outside the graph and produces no `ActionPlan`.

To make `Handoff` summaries meaningful, `AgentState.notes` is populated by the planner via an optional `note: str` on each `ActionPlan`. A single end-of-run LLM call digests notes into the user-facing artifact for any of the first three terminal states.

V1 **terminates** on handoff. V2 (Telegram) will pause-and-resume by leveraging LangGraph's checkpointer — V1 writes checkpoints from day one so V2 is additive, not a refactor.

## Considered alternatives

- **Single `done` flag, no reason.** Rejected: the user can't distinguish "the agent finished the job" from "the agent bailed because something happened."
- **Pause-and-resume in V1.** Rejected: a CLI doesn't naturally pause for user input mid-run. Defer to V2 (Telegram), where pause-and-resume is the natural mode.
- **Dedicated `observe` node calling the planner separately to populate notes.** Rejected for V1: doubles planner calls per step. Worth revisiting if the planner is later downsized or specialized (HLA Phase 3 territory).
