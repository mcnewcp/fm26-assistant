# Scenario: advance_to_next_match

## When to use

The user wants to move forward in time without paying close attention until the next fixture begins. Typical phrasings: "advance to the next match," "go to the next game," "skip to match day," "play through to the next fixture." Not appropriate for goals that require active management decisions (training, tactics, transfers).

## Goal restatement

Advance simulated time until either (a) the match-preparation screen for the next fixture is reached, or (b) a handoff trigger fires. Read every inbox message that arrives during the period — none are skipped — so the user receives a complete digest at the end.

## Decomposition

The agent moves through three repeating phases:

1. **Advance time.** From the main screen, advance the simulation. The simplest action is the spacebar (the "continue" hotkey); fall back to clicking the continue button if the spacebar is not accepted in the current state.
2. **Process interrupts.** When the simulation pauses, classify the interrupt and respond:
   - **Inbox notification (unread indicator visible)**: open the inbox, click into each unread message in turn, read it from the screenshot, attach a note describing the message, then return to the main screen.
   - **Modal popup**: read the popup, attach a note, dismiss it (Escape, or the close/OK control). If the popup matches a handoff trigger, halt instead of dismissing.
   - **Tactical / fixture prompt**: this is the done state — see "Done criteria."
3. **Check for handoff triggers.** Before every continue action, scan the visible screen for handoff-trigger conditions. If any fires, halt with a handoff.

The phases are not strictly sequential — the planner adapts. The key invariant: **every inbox message during the period is read.**

## UI knowledge

> ⚠ This section is a sketch. The agent author should refine it against the real FM26 UI before the scenario is used in anger.

- **Main screen / club overview**: the agent's home base between simulated days. From here, the continue button or spacebar advances time.
- **Inbox**: accessed from a navigation icon (likely top bar). Unread messages have a visual indicator (number badge or bold styling). Each message opens into a full-pane reader.
- **Continue button**: large, typically labelled "Continue" or showing a forward-arrow symbol. Visible on the main screen between events.
- **Match-prep / fixture screen**: distinctive layout shown when the next fixture is imminent — typically displays opposing teams, lineup options, and a "play match" call-to-action.

Common pitfalls (verify against real game):

- A modal popup may steal keyboard focus — spacebar might not advance until the popup is dismissed.
- Some inbox messages have multiple panes or attachments (scout reports, analysis tabs) — read all panes before noting and dismissing.
- Avoid Enter as a generic "OK" — it can confirm tactical decisions accidentally. Prefer Escape to dismiss when uncertain.

What to ignore:

- Background animations and ambient UI changes (squad fitness bars, sponsor banners) are not interrupts unless they manifest as a popup.

## Note-taking discipline

For every inbox message read, attach a note in this shape:

> `Inbox message from <sender>: <one-line summary>. Significance: <routine | noteworthy | handoff-candidate>.`

For every popup dismissed, attach a note in this shape:

> `Popup: <one-line summary>. Action: dismissed.`

Do not take notes for routine continue actions or simple screen transitions — they clutter the digest without adding signal.

## Done criteria

The session is done when the screen shows the **match-preparation screen for the next fixture**. Visual signals (verify against real game):

- Two team names / crests displayed prominently (home vs. away)
- Lineup or tactics options visible
- A "Play match" / "Continue to match" call-to-action

When these are present, emit `done_reason='goal_complete'` with a short `summary` (e.g. `"Reached match-prep vs <opponent>."`).

## Handoff triggers

V1 has one trigger:

### Player injury (own team)

- **Visual signal:** a popup or inbox message from the medical / coaching staff reporting that a player has been injured (in training or in a previous match). The injured player is on the user's team (not an opponent).
- **Surfaced summary:** `"<Player name> injured. Expected out: <duration if visible>. Source: <training | match | other>."`
- **After surfacing:** terminate immediately. Do not continue advancing time.
