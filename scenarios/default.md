# Scenario: default

## When to use

The default scenario for any goal that doesn't match a more specific scenario. Selected by the router when nothing else fits. Appropriate when the user's intent is loose ("look around the squad screen") or when no specialized scenario has been authored for the task yet. The agent has wide latitude under this scenario.

## Goal restatement

The user's literal goal, passed through verbatim. The planner interprets it directly.

## Decomposition

You have wide latitude. Plan one action at a time based on the current screenshot, the goal, the action history, and the notes accumulated so far. Take notes generously when you observe something potentially relevant — under the default scenario you do not yet know what is worth remembering, so err toward more.

Declare `done_reason='goal_complete'` when you believe the goal is satisfied. If a universal handoff trigger fires (see below), declare `done_reason='handoff'`. **Do not invent FM-specific handoff triggers under this scenario** — those belong in dedicated scenarios.

## UI knowledge

None specific. Apply general knowledge of how desktop applications behave: click visible buttons; press keys associated with their visible labels; do not click on elements you cannot identify.

## Note-taking discipline

Take a note for any action whose outcome is non-obvious from the action itself — anything the user might want to know about afterwards. Format:

> `<one-line observation>`

Skip notes for trivial transitions (the screen scrolled, a hover state changed). The final digest under the default scenario will be richer than for specialized scenarios; that's expected.

## Done criteria

Declare done when either:

- The visible screen evidences the goal is satisfied (planner judgment, not visual checklist), **or**
- You have tried multiple plausible paths and are confident no further progress can be made (a "graceful give-up"). Emit `done_reason='goal_complete'` with a `summary` that explains the give-up; the digest will surface the explanation to the user.

The give-up branch is intentionally `goal_complete`, not `stuck`. `Stuck` is reserved for budget exhaustion or unrecoverable orchestration failures (network errors, malformed model output) — not for "the planner doesn't see a path."

## Handoff triggers

The following triggers are **universal** — they apply to every scenario via this default fallback. Specific scenarios may add their own triggers; they cannot remove these.

### Application crash / unresponsive state

- **Visual signal:** a modal indicating the application is crashing, hung, or asking to restart. Or a blank / black screen where the application UI should be. Or no response to repeated continue actions across several steps.
- **Surfaced summary:** `"Application appears to have crashed or hung. Last visible state: <one-line description>."`
- **After surfacing:** terminate immediately.

### Bizarre / unrecognized state

- **Visual signal:** the planner cannot identify the visible screen as anything plausible. Could be a different application, an OS dialog (permissions prompt, software update, security alert), or a screen the planner has no model of.
- **Surfaced summary:** `"Unrecognized screen state — likely outside the target application. Visible: <one-line description>."`
- **After surfacing:** terminate immediately.
