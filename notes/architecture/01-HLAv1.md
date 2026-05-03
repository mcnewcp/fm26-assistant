# Computer Use Agent — V1 POC architecture

## 1. Purpose

Build a vendor-neutral computer use agent in Python that observes a single native desktop application via screenshots, decides what to do, and operates the OS through mouse and keyboard. V1 is a proof of concept for a single domain.

**The target application is Football Manager 26.** The agent functions as an "assistant manager" that handles the high-volume, low-judgement drudgery of the game — advancing time through uneventful periods, processing routine inbox traffic, capturing scouting data, and surfacing the moments that actually want the player's attention. The architecture is general (any desktop app) but every V1 design decision is anchored to this use case.

The architecture must keep the planner LLM, the grounding VLM, and the action layer independently swappable so we can shop for the best price/performance combination as the market evolves.

### V1 success criteria

- Agent can complete a defined multi-step scenario end-to-end (e.g., "proceed to the next match") on the developer's local machine.
- All four layers are wired and exercised; the loop runs until the goal is reached or a step budget is hit.
- The planner LLM, the grounder VLM, and the action layer can each be swapped via configuration without touching the other layers.
- A kill switch exists and reliably halts the agent within one action of the user reclaiming input.

### Explicitly out of scope for V1

- Multi-app orchestration. V1 controls one application.
- A polished UI. V1 has a CLI entrypoint and structured logs. The CLI must be a thin shell over a programmatic Python API (see §3 "Entrypoint design") so that V2 can add additional surfaces (Telegram bot, web UI, voice) without rewriting the agent.
- Production-grade observability, tracing, evals.
- The deterministic Python script integration for scenarios (markdown-only in V1).
- Cross-platform parity. V1 targets the developer's macOS Macbook; Windows/Linux is V2.

## 2. High-level architecture

Four layers, each with a single responsibility, connected by narrow contracts:

```
┌──────────────────────────────────────────────────────────────────┐
│ Layer 1 — Orchestration (LangGraph)                              │
│ Agent loop, state, scenario selection, kill switch, retry policy │
└─────────────────────┬──────────────────────────▲─────────────────┘
                      │ goal + screenshot         │ next screenshot
                      │ + history + scenario      │ + tool result
                      ▼                           │
┌──────────────────────────────────────────────────────────────────┐
│ Layer 2 — Model layer (Operator interface)                       │
│  ┌──────────────────────┐    ┌──────────────────────┐            │
│  │ Planner LLM          │ -> │ Grounder VLM         │            │
│  │ Nemotron Nano Omni   │    │ Holo2-8B (MLX)       │            │
│  │ via NVIDIA NIM       │    │ or Holo API fallback │            │
│  └──────────────────────┘    └──────────────────────┘            │
└─────────────────────┬──────────────────────────▲─────────────────┘
                      │ MCP tool call             │ result + screenshot
                      │ click(x,y) / key / type   │
                      ▼                           │
┌──────────────────────────────────────────────────────────────────┐
│ Layer 3 — Action layer (MCP server)                              │
│ Tools: screenshot, click, type, key, scroll, sleep               │
└─────────────────────┬──────────────────────────▲─────────────────┘
                      │ native API calls          │ pixel data
                      ▼                           │
┌──────────────────────────────────────────────────────────────────┐
│ Layer 4 — Execution (OS + target application)                    │
│ Mouse, keyboard, framebuffer                                     │
└──────────────────────────────────────────────────────────────────┘
```

The loop turns once per agent step: the planner sees the latest screenshot, decides the next single action, the grounder converts a UI description to coordinates if needed, the MCP server executes the action, a fresh screenshot is captured, and control returns to Layer 1. The agent never plans the entire sequence upfront.

## 3. Layer 1 — Orchestration

### Choice

LangGraph as the orchestration framework. LangChain is used only as a model client abstraction (`init_chat_model`); all agent logic lives in a LangGraph `StateGraph`.

Rationale: LangGraph gives us explicit state, conditional edges, checkpointing, and human-in-the-loop primitives without forcing a particular agent design. We want a hand-rolled loop, not a prebuilt ReAct or tool-calling agent — we have specific control-flow needs (skip grounder for keyboard actions, abort on kill switch, route to scenario subgraphs later).

### State shape

```python
class AgentState(TypedDict):
    goal: str                           # user's top-level instruction
    scenario: Optional[str]             # selected scenario markdown
    current_screenshot: Optional[Image] # only the latest; not a list
    previous_screenshot: Optional[Image] # one prior, for change detection
    action_history: list[ActionRecord]  # textual log of past actions
    last_action_result: Optional[dict]  # MCP tool response
    step: int                           # iteration counter
    max_steps: int                      # budget, default ~50
    done: bool
    final_summary: Optional[str]
```

The state holds at most two screenshots in memory at any time, not a growing list. All earlier screenshots are persisted to disk by the observability layer (§9) for replay, but they are not part of the live state. The agent's "memory" of what happened earlier in the session lives in `action_history`, which is plain text and cheap.

### What the planner actually sees

A point worth being explicit about: **`AgentState` is the orchestration layer's working memory. The planner LLM does not see it.** The planner only sees what the `plan` node deliberately packages into the `messages` array of its API call.

In code:

```python
def plan(state: AgentState) -> dict:
    messages = [
        {"role": "system", "content": render_system_prompt(state["scenario"])},
        {"role": "user", "content": [
            {"type": "text", "text":
                f"Goal: {state['goal']}\n\n"
                f"Recent actions:\n{format_history(state['action_history'][-15:])}\n\n"
                f"Decide the next single action."},
            {"type": "image_url", "image_url": image_to_data_url(state["current_screenshot"])},
        ]},
    ]
    response = planner_client.chat.completions.create(messages=messages, ...)
    return {"last_plan": parse_response(response)}
```

State fields like `step`, `done`, `final_summary`, `last_action_result`, and the full untrimmed `action_history` exist in the program but are not sent to the planner unless `plan` chooses to include them. The same goes for `previous_screenshot` — it can live in state for orchestration-layer use (e.g., a "did the screen change after the last click?" check) without ever appearing in the planner's prompt.

This separation is why the context-management discipline above works. The state is the program's memory; the planner's context window holds only what we deliberately render into the prompt on each turn.

### Context window management

This is load-bearing for the design and easy to get wrong. **Naively appending every screenshot to the planner's context on each turn will blow up the context window within ~30 steps and degrade planner quality long before the nominal limit.**

Some sizing intuition. A full-screen capture from a 1440p Macbook display is roughly 2,000–4,000 vision tokens for a Qwen3-VL-class model after the image processor's tiling. A 50-step session that sent every screenshot to the planner would be ~150K image tokens — most of Nemotron Nano Omni's 256K window — before counting any text. Beyond cost, vision-language models empirically degrade in instruction-following well before they hit their context limit, especially when many similar images compete for attention.

What actually goes into the planner's context on each `plan` call:

- **One screenshot** — the current one. This is the thing the planner is reasoning about right now.
- **A textual action history** — `"step 12: clicked inbox icon → step 13: pressed Escape → step 14: clicked continue arrow"`. Plain text. ~10 tokens per step. Capped at the last ~20 entries.
- **The scenario markdown and the original goal** — static, sent every turn.
- **Optionally, the immediately previous screenshot** — only included when the planner explicitly needs to reason about what changed (e.g., "did my last click do what I expected?"). The default is to omit it; the planner can request it via a "compare with previous frame" prompt mode.

What does NOT go into the planner's context:

- Screenshots from steps older than the previous one. They're on disk; the planner doesn't see them.
- Raw MCP tool responses beyond the last one.
- The full grounder request/response history (the planner doesn't need to know about coordinates it didn't pick).

### Implementation note: LangGraph reducers

LangGraph's default `add_messages` reducer appends to message lists. Used naively with multimodal messages, this creates exactly the runaway state problem above. The orchestration layer must use a **custom reducer** (or, simpler, a dedicated `prune_state` node that runs before `plan`) that:

1. Drops the previous screenshot when capturing a new one (unless explicitly retained for one turn).
2. Truncates `action_history` to the last N entries.
3. Strips images from older messages if using a message-list-based design.

The planner's input is therefore reconstructed every turn from the current state, not accumulated across turns. This is the "render the prompt fresh each call" pattern, which is also easier to debug than a long-lived message thread.

### Node graph

The graph has five nodes plus an entry:

1. `select_scenario` — runs once at start; chooses which scenario markdown to load (see §7).
2. `capture` — calls MCP `screenshot`, appends to state.
3. `plan` — calls the Planner LLM with a freshly-rendered context (current screenshot + textual history + scenario), returns either an `ActionPlan` or `done=true`.
4. `ground` — conditional; runs only if the planner's action requires coordinates.
5. `execute` — calls the MCP server with the resolved action, captures fresh screenshot.

Edges:

- `entry -> select_scenario -> capture -> plan`
- `plan -> done?` → if `true`, terminate with summary
- `plan -> ground` if action type ∈ {click, drag, double-click}
- `plan -> execute` otherwise (keyboard, scroll, sleep)
- `ground -> execute`
- `execute -> capture` (loop back)

The `capture` node moves the previous `current_screenshot` into `previous_screenshot` (or discards it) and writes the new one into `current_screenshot`. Pruning is a property of how `capture` updates state and how `plan` renders its prompt — it does not need its own node.

### Loop budget and termination

- Hard cap on `step` (default 50). Exceeding it returns a "stuck" summary to the user.
- The planner can declare `done` whenever the goal is satisfied.
- The kill switch can force termination from outside the graph (see §9).

### Entrypoint design

V1 ships a CLI, but the long-term plan is to drive the agent from a Telegram bot (and possibly other surfaces — web UI, voice, scheduled triggers). The CLI must therefore not become the agent's API. Instead:

The agent's public interface is a Python class — call it `Agent` — with one main method:

```python
class Agent:
    def __init__(self, config: Config): ...
    async def run(self, goal: str, *, on_event: Callable[[Event], None] | None = None) -> RunResult: ...
```

`run()` executes one full session (one user goal) end-to-end and returns a `RunResult` with the final summary, step count, and links to the session's saved screenshots. The optional `on_event` callback receives structured events as they happen (`StepStarted`, `ActionTaken`, `ScreenshotCaptured`, `Stuck`, `Done`) so any frontend can render progress.

The V1 CLI is a ~30-line shell over this:

```python
# cli.py
async def main():
    agent = Agent(load_config())
    goal = sys.argv[1]
    result = await agent.run(goal, on_event=print_event_to_stdout)
    print(result.summary)
```

V2's Telegram bot becomes another ~50-line shell over the same `Agent`:

```python
# telegram_bot.py
@bot.message_handler()
async def handle(msg):
    result = await agent.run(msg.text, on_event=lambda e: bot.send(msg.chat_id, format(e)))
    await bot.send(msg.chat_id, result.summary)
```

No changes to the agent. No changes to LangGraph nodes. Just a different shell calling the same method.

The discipline that makes this work in V1: **`Agent.run()` must not import `argparse`, must not call `print()` directly, must not assume a TTY exists.** All output flows through `on_event`. All input arrives via the `goal` argument. If V1 honors this constraint, V2 is a weekend project. If V1 violates it, V2 becomes a refactor.

Two practical considerations for the Telegram future, parked here for V2:

- **Concurrency model.** A bot will eventually receive a second goal mid-run. V1 doesn't need to handle this (one session at a time, CLI is single-user), but `Agent.run()` being `async` from day one preserves the option without forcing the work now.
- **Remote machine, remote eyes.** If the bot runs on the same Macbook as the target app, you can already control your machine from your phone. If you want to keep the bot reachable when the Macbook is asleep, that's a deployment question for V2 (e.g., a small always-on relay process), not an architecture question.

### Why not LangChain prebuilt agents

`create_react_agent` and `create_tool_calling_agent` hide the loop. We need to inject the grounder between planner and execution, and we need fine-grained control over screenshot capture timing and the kill switch. A custom `StateGraph` is cleaner.

## 4. Layer 2 — Model layer

### The Operator interface

All model interactions go through a thin Python protocol:

```python
class Operator(Protocol):
    def propose_action(self, screenshot, goal, history, scenario) -> ActionPlan: ...
    def ground(self, screenshot, target_description: str) -> Coordinates: ...
```

`ActionPlan` is a dataclass containing `action_type`, optional `target_description` (for clicks), optional `text` (for typing), optional `key`, and `done: bool` plus a `thought` field for logging.

Implementations for V1:

- `NvidiaNemotronOperator` — uses NVIDIA NIM for both planning and grounding fallback.
- `HybridLocalOperator` — Nemotron via NIM for planning, local Holo2-8B via MLX for grounding.
- `HybridHoloApiOperator` — Nemotron via NIM for planning, hosted Holo API for grounding.

The orchestration layer never imports a vendor SDK directly. It receives an `Operator` instance via dependency injection.

### Planner LLM choice for V1

**Default: NVIDIA Nemotron 3 Nano Omni 30B-A3B-Reasoning** via the hosted NIM endpoint at `https://integrate.api.nvidia.com/v1`.

Why:

- Multimodal (image input) — required to read screenshots. (NVIDIA explicitly lists "GUI automation for AI agentic applications" as a target use case.)
- 30B total / 3B active MoE — fast inference, cheap per call, important because an agent loop makes many calls per task.
- Free tier with 1,000 credits at signup, OpenAI-compatible API, no credit card.
- Same container is self-hostable later with no code changes if we exhaust the free tier.

**Escalation path:**

1. If Nemotron Nano's planning quality is insufficient → try **Kimi K2.6** on NIM. Caveat: Kimi K2.6 is a 1T-parameter frontier model. It's smarter but per-call latency and cost are much higher, which compounds over agent loops with many steps. Worth trying once Nemotron's failure modes are characterized — it may be smarter than we need.
2. If both open models underperform → escalate to a paid frontier API (Anthropic Claude Sonnet 4.6 or OpenAI GPT-5.4) for the planner only. The grounder can stay local.

### Grounder VLM choice for V1

**Default: Holo2-8B via mlx-vlm** on the developer's Macbook (32 GB unified memory). Self-converted to 4-bit MLX from `Hcompany/Holo2-8B`.

Why:

- **Purpose-built for the V1 use case.** Holo2 (released Nov 2025 by H Company) is the successor to Holo1.5 and is the first Holo generation explicitly trained on **desktop and mobile** environments in addition to web. Holo1.5 was web-focused; native desktop apps were second-class. Holo2 changes that, which matters because V1's target is a native desktop application.
- **MLX path is known-good.** Holo2 is fine-tuned from `Qwen3-VL-8B-Thinking`. Qwen3-VL has confirmed working MLX ports — LM Studio publishes `lmstudio-community/Qwen3-VL-8B-Thinking-MLX-4bit` officially, and the Qwen3-VL technical report calls out "stronger 2D grounding" as a headline feature. Holo2-8B converts via the same `mlx_vlm.convert` path with no architectural changes.
- **Memory footprint.** ~5–6 GB at 4-bit. Comfortable on 32 GB unified memory alongside macOS, dev tools, and the target application.
- **License.** Apache-2.0. (Holo2-30B-A3B and Holo2-235B are research-only; the 4B and 8B are commercial-friendly.)
- **Active development.** H Company is actively shipping in this space; Bytedance has shifted focus to closed UI-TARS-2.

### Deployment strategy

One-time conversion, then run as a local OpenAI-compatible server:

```bash
pip install mlx-vlm

# One-time: convert Holo2-8B to 4-bit MLX (~10–15 minutes)
python -m mlx_vlm.convert \
  --hf-path Hcompany/Holo2-8B \
  -q --q-bits 4 \
  --mlx-path ./models/Holo2-8B-MLX-4bit

# Run as an OpenAI-compatible server
mlx_vlm.server \
  --model ./models/Holo2-8B-MLX-4bit \
  --port 8080
```

The grounder slot in the `Operator` interface then talks to `http://localhost:8080/v1/chat/completions` — same wire format as the NVIDIA NIM planner endpoint, just a different `base_url`. This means the grounder implementation is a near-clone of the planner implementation, with different prompts.

### Alternatives, in order of preference

1. **`lmstudio-community/Qwen3-VL-8B-Thinking-MLX-4bit`** — already converted, zero conversion step, but generic (not GUI-specialized). Worth using as a baseline in the grounder validation harness (§10 step 1): if the generic Qwen3-VL grounds the target app's UI well enough, we may not need Holo2 at all. This is also a useful sanity check that the MLX path is healthy on the developer's machine.
2. **Holo2-4B if 8B is too slow** — same family, ~3 GB at 4-bit, drop-in replacement. Use this if grounding latency dominates the loop.
3. **Holo Cloud API** (`hcompany.ai/holo-models-api`) — known-good hosted version, removes local-inference variables entirely. Use as a hard fallback if local MLX inference has problems we can't quickly resolve. Costs per call but the planner-plus-grounder split means we still control the planner cost separately.
4. **UI-TARS-1.5-7B via MLX** — the original V1 candidate. Demoted because the community MLX conversions have a documented coordinate-accuracy bug and Bytedance has not shipped an official MLX port. Worth revisiting only if a fixed conversion is published or if Holo2 performs worse than expected on the specific game UI.
5. **Planner-emits-coordinates degraded mode** — last resort. The Nemotron planner is asked for coordinates directly. Accuracy will be poor on dense UI; not a real design, just a way to keep the system running while debugging upstream.

### Why split planner and grounder

End-to-end models (Anthropic computer use, ByteDance UI-TARS-2 full size) achieve higher monolithic OSWorld scores but lock us to one vendor. The planner-plus-grounder split lets us upgrade either piece independently. Recent research (Agent-S2, GTA1, Surfer-H — note that Surfer-H is H Company's own agent built on the Holo line, which is part of why the Holo line is purpose-shaped for this role) shows specialist sub-10B grounders match or beat much larger generalist models on coordinate prediction. The split isn't just for portability — it's competitive on quality.

## 5. Layer 3 — Action layer

### Choice

A single MCP server exposing six tools: `screenshot`, `click`, `type`, `key`, `scroll`, `sleep`.

For V1, start with **`AB498/computer-control-mcp`** (`uvx computer-control-mcp@latest`). Cross-platform, pure Python, PyAutoGUI + RapidOCR + ONNXRuntime, zero external dependencies. We will likely outgrow it (PyAutoGUI is in maintenance mode and has multi-monitor and HiDPI quirks), but it is the fastest path to a working system.

Migration path: when we hit PyAutoGUI's limitations, fork the server or write our own using `pynput` (input) plus `mss` (screenshots) plus `atomacos` for macOS accessibility tree access. This is a Layer 3 concern only — the agent loop and the model layer don't care which MCP server is on the other side of the protocol.

### Why MCP, not a direct Python tool

Two reasons:

1. **Portability.** The same MCP server can be driven by our LangGraph agent today, by Claude Desktop tomorrow, by Cursor or ChatGPT next month. The protocol is the contract.
2. **Process isolation.** The MCP server runs in its own process. If the agent crashes, the action layer is unaffected. If the action layer hangs, the agent times out cleanly. This also makes the kill switch easier to implement.

LangChain's `langchain-mcp-adapters` package provides a clean way to consume MCP tools as LangChain `BaseTool` instances inside the LangGraph nodes.

### Tool surface (V1)

```
screenshot()                     -> {image: bytes, width: int, height: int}
click(x: int, y: int, button="left", count=1)  -> {ok: bool}
type(text: str)                  -> {ok: bool}
key(key_or_combo: str)           -> {ok: bool}    # "Escape", "cmd+c"
scroll(x: int, y: int, dy: int)  -> {ok: bool}
sleep(seconds: float)            -> {ok: bool}
```

Deliberately small. Anything fancier (drag, multi-key sequences, focused-window-aware screenshots) is V2.

## 6. Layer 4 — Execution

The OS and the target application. Layer 4 is "not our code." V1 only requires:

- The target app is in the foreground when the agent runs.
- macOS Accessibility permission is granted to the MCP server's process.
- The user is willing to surrender mouse/keyboard during agent execution.

No special V4 work for V1 beyond a one-time permissions setup.

## 7. Domain knowledge — scenarios

### Recommendation for V1

**Scenarios are markdown files loaded into the planner's system prompt.** A simple lightweight router selects which scenario to load based on the user's goal at the start of a session.

Concretely:

```
scenarios/
  proceed_to_next_match.md
  scout_a_player.md
  respond_to_transfer_offers.md
  ...
```

Each scenario contains:

- **When to use this scenario** — short description for the router.
- **Goal decomposition** — how a goal of this type breaks into sub-tasks.
- **UI knowledge** — where things live in the app, common pitfalls, what to ignore.
- **Termination criteria** — what "done" looks like for this scenario.

This mirrors how Claude Code skills work and is the simplest thing that could possibly work. It defers the harder questions (subgraphs, Python tool integration) until we have real scenarios to design against.

### Scenario selection

V1 router: a single LLM call (using the same Nemotron model, no need for a separate router) that takes the user's goal plus the list of scenario titles and descriptions and returns the best match (or `none`, in which case a generic system prompt is used). This is a node in the LangGraph (`select_scenario`) that runs once per session.

This is intentionally not embedding-based. Embeddings would be premature optimization; with a handful of scenarios in V1, a single LLM call is fine and gives us better matching when goals are phrased loosely.

### Why not subgraphs (V1)

The user proposed letting the planner navigate node pathways. That's a good V2 design — it lets you encode hard constraints and inject deterministic Python steps mid-flow. For V1, every scenario fits the same loop shape (plan → ground → execute → repeat), so subgraphs add complexity without buying us anything. We revisit this when we have a scenario that genuinely needs a different control flow.

### Future Python script integration (V2 sketch, not V1 work)

Scenarios will be able to declare deterministic Python tools (e.g., `parse_match_schedule(screenshot) -> MatchInfo`). These get registered with the MCP server at scenario load time and become additional tools the planner can call. The scenario markdown describes when to use them. This keeps the Layer 3 boundary intact — Python tools are just more MCP tools — while letting us bypass the LLM for tasks where determinism matters.

## 8. Configuration and dependency injection

A single `config.toml` (or pydantic settings file) defines the active stack:

```toml
[orchestration]
max_steps = 50
screenshot_history_size = 3

[planner]
provider = "nvidia"        # nvidia | anthropic | openai | moonshot
model = "nemotron-3-nano-omni-30b-a3b-reasoning"
base_url = "https://integrate.api.nvidia.com/v1"

[grounder]
provider = "mlx_local"     # mlx_local | holo_api | planner_inline
model_path = "./models/Holo2-8B-MLX-4bit"
server_url = "http://localhost:8080/v1"

[action]
mcp_server = "computer-control-mcp"

[scenarios]
directory = "./scenarios"
```

The factory pattern wires the right `Operator` implementation based on `[planner]` and `[grounder]` config. Swapping providers is editing this file, nothing else.

## 9. Cross-cutting concerns

### Kill switch

Non-negotiable. The agent operates the user's machine.

V1 implementation: a background thread using `pynput.mouse.Listener` with the `injected` callback (1.8.1+). Real mouse movement detected → set a flag in agent state. The `execute` node checks this flag before every action; if set, it raises `UserAbort` and the graph terminates cleanly.

A keyboard shortcut (`cmd+shift+escape`) is the secondary kill switch, also via pynput.

### Observability

V1 minimum:

- Structured JSON logs of every node entry/exit with timing.
- Every screenshot saved to a per-session directory with a sequence number.
- Every Planner and Grounder request/response saved as JSON next to the screenshot.

This gives us a complete replayable trace of any session for debugging and eval.

### Eval harness (light)

V1 eval is manual: a fixed list of scenarios with expected end-states. Run each, watch, mark pass/fail. Postpone automated end-state verification to V2.

A separate, narrow eval that *is* worth automating in V1: **grounder accuracy on a fixed screenshot test set.** We need this to compare grounder candidates (Holo2-8B local, Qwen3-VL-8B baseline, Holo API) empirically before committing.

## 10. V1 build sequence

Suggested order for the planner agent that consumes this doc:

1. **Spike: grounder accuracy.** Build a tiny test harness: 20 screenshots from the target app with hand-labeled ground-truth coordinates for known UI elements. Define "correct" as the predicted point falling inside the target's bounding box. Run three candidates against it and pick the cheapest one that meets the accuracy bar:
   - **Baseline:** `lmstudio-community/Qwen3-VL-8B-Thinking-MLX-4bit` (already converted, zero setup). This also confirms the MLX path is healthy on the developer's machine before investing in conversion.
   - **Primary:** Self-converted `Hcompany/Holo2-8B` to MLX 4-bit via `mlx_vlm.convert`. Expected to outperform the baseline on dense GUI grounding.
   - **Hosted fallback:** Holo Cloud API. Use this to set the upper-bound accuracy number — if local Holo2 lands within ~5 points of the API, ship local.

   Decide grounder before building the rest.
2. **Layer 3 working standalone.** Get `computer-control-mcp` running locally. Manually drive it with a few tool calls. Confirm screenshots, clicks, and key presses work on the target app.
3. **Operator interface + Nemotron planner.** Implement `NvidiaNemotronOperator.propose_action`. Verify it can read a screenshot and emit a sensible action.
4. **LangGraph skeleton.** Wire the five nodes. Run end-to-end on a hard-coded scenario (no scenario file yet).
5. **Kill switch.** Add and test.
6. **Scenario loading.** Add `select_scenario` node and one real scenario markdown file. Run the "proceed to next match" flow.
7. **Logging and replay.** Wire the observability described in §9.

Each step has a hard pass/fail outcome and can be tested in isolation.

## 11. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Context window grows unbounded across long sessions | Medium | High | §3 mandates state holds only current+previous screenshot; older frames live on disk. Validate with a 50-step session in the eval harness. |
| Self-converted Holo2-8B MLX produces inaccurate coordinates on dense game UI | Medium | High | Step 1 of build sequence runs three candidates side-by-side. If local fails, Holo Cloud API is a known-good drop-in. |
| Holo2-8B inference latency too slow for tight loops on this Macbook | Low | Medium | Drop to Holo2-4B (same family, ~3 GB at 4-bit). Drop to Holo Cloud API if local is fundamentally too slow. |
| `mlx_vlm.convert` fails on Holo2-8B (rare for Qwen3-VL-derived models, but possible) | Low | Medium | Use `lmstudio-community/Qwen3-VL-8B-Thinking-MLX-4bit` as a ready-made stand-in; trade GUI specialization for working inference. |
| NVIDIA NIM rate limit (~40 RPM) bottlenecks dev | Medium | Medium | Cache screenshots in dev to avoid re-running planner on identical state; consider self-hosted NIM if it bites. |
| Nemotron Nano insufficient for planning | Medium | Medium | Escalation path to Kimi K2.6 then paid APIs is planned in §4. |
| Kill switch race condition | Medium | High | Test exhaustively in step 5. Worst case, fall back to a polling check before each action. |
| MCP server hangs on a misbehaving app | Low | Medium | Per-tool timeout in the MCP client; graph-level timeout above that. |
| Target app's UI changes between sessions | Variable | Medium | Scenarios encode "where things live" knowledge; updates are markdown edits, not code. |
| Frontmost-window assumption breaks (notification, modal) | Medium | Low | The planner can see the screenshot — it should handle this. Validate during scenario testing. |

## 12. What stays stable, what evolves

Stable across V1 → V5:

- The four-layer split.
- The Operator interface contract.
- MCP as the action-layer protocol.
- Scenarios as markdown.

Expected to evolve:

- Specific model choices (planner and grounder both).
- The MCP server implementation.
- Scenario format (will likely gain frontmatter, Python tool refs).
- The graph itself (subgraphs for scenarios with non-standard control flow).

This document describes V1 only. Decisions that are explicitly left for later are marked as such.

## 13. Post-V1 roadmap

These are sketched, not specified. Each is a feature that has been reasoned about enough to know it fits the architecture; none should be built until V1 is working and the Football Manager domain has revealed which of these matters most. Order is "rough priority based on what unlocks daily use," not a commitment.

### Phase 2 — Telegram frontend (remote control)

**Goal:** chat with the assistant manager from a phone or any device, anywhere.

**Fit with V1:** trivial if §3's entrypoint discipline holds. A python-telegram-bot handler imports the same `Agent` class, calls `await agent.run(goal, on_event=...)`, and forwards events to the chat. No agent code changes.

**Open questions to settle in Phase 2, not now:**
- **Always-on host.** If the bot runs on the Macbook and the lid is closed, both the bot and the game are unreachable. Options: caffeinate the Mac during sessions, run the bot on a small home server that wakes the Mac on demand, or accept "only available when I'm at my desk." This is a deployment decision, not an architecture one.
- **Authentication.** Whitelist of Telegram user IDs in config. Anything fancier is over-engineered for one user.
- **Concurrency.** Probably one session at a time, queued. FM is single-player; there's no value in parallel runs against the same game state.
- **Streaming progress.** The `on_event` callback already gives us this. Format `StepStarted`, `ActionTaken`, `Stuck` events as Telegram messages. Throttle aggressively so the agent doesn't flood the chat — probably one update per ~5 actions plus immediate updates for `Stuck` and `Done`.

### Phase 3 — Structured data extraction (scouting and player attributes)

**Goal:** when the agent visits a player profile or scouting screen, capture the table data into a structured form rather than just acting on it visually.

**Why this is a distinct phase:** the V1 grounder (Holo2-8B) is trained for "where to click," not "what does this table say." Asking it to extract 40 numerical attributes from a player profile is using the wrong tool. A specialized extraction model is much better.

**Recommended model:** **NVIDIA Nemotron-Parse v1.2** (1B params, 1.5GB at FP16). Designed exactly for this — table extraction, key-value pairs, structured output from documents and screenshots. Two deployment options:

1. **NIM hosted endpoint** at `build.nvidia.com/nvidia/nemotron-parse` — same OpenAI-compatible pattern as the Nemotron Nano planner, free credits at signup. Use this first.
2. **Local self-host** from `huggingface.co/nvidia/NVIDIA-Nemotron-Parse-v1.2` — the model is small enough (1B) to run alongside Holo2-8B on the Macbook with room to spare. ~3GB combined VRAM at 4-bit. Worth doing once usage justifies it.

**Architectural fit:** Nemotron-Parse becomes a third slot in the model layer alongside planner and grounder, surfaced through the `Operator` interface as a new method:

```python
def extract_structured(self, screenshot, schema: dict) -> dict: ...
```

The planner decides when to invoke it (e.g., "we just opened a player profile — extract attributes before doing anything else"). The result is shipped to the database (Phase 4), not back into the planner's context — that would burn tokens for no reason since the planner doesn't need to reason about the raw numbers, only act on summaries.

**Pairing with scenarios:** a `scout_player.md` scenario describes the navigation steps and declares the schema for what should be extracted. The deterministic Python tool integration mentioned in §7 is exactly the hook for this — `extract_structured` is registered as an MCP tool that scenarios can invoke.

### Phase 4 — Persistent database

**Goal:** track players, scout reports, transfer targets, season progression, the assistant's own observations across sessions.

**Recommended starting point:** **SQLite via an MCP server.** Specifically `modelcontextprotocol/servers` ships an official SQLite MCP server, or write a thin custom one with a curated schema. Either way, the database access is just more MCP tools — same protocol as the action layer, accessible to any planner.

**Schema sketch (for thinking, not committing):**

- `players` — id, name, club, position, age, last_seen_attributes (JSON), source_screenshot_path
- `scout_reports` — player_id, scouted_on, scout_name, recommendation, attributes_at_scout (JSON)
- `targets` — player_id, priority, status (watching | bidding | rejected), notes
- `seasons` — id, year, league, position, key_events (JSON)
- `agent_notes` — free-form things the assistant wants to remember across sessions

**Why MCP and not a Python ORM call:** keeping the database behind MCP means (a) the database is reachable from Claude Desktop, the Telegram bot, or a future web UI without writing each integration separately, (b) it's swappable to Postgres or DuckDB later without touching the agent, and (c) it's a clean tool surface for the planner to query naturally ("how does this player compare to my current squad at the same age?").

**Read vs. write discipline:** the agent should write freely (every scout result, every match outcome) but reads from the DB into the planner context should be deliberate and small. A per-scenario "load relevant DB context" step in the prompt rendering avoids dumping the whole player table every turn.

### Phase 5 — Obsidian vault as shared brain

**Goal:** a markdown notebook that both the user and the agent can read and edit. Depth charts, tactical philosophy, season narratives, anything semi-structured that benefits from being human-editable.

**Recommended integration:** **`obsidian-mcp-server`** (community MCP server, several implementations on GitHub). The agent reads and writes notes through MCP tools; the user edits the same files through Obsidian's UI on desktop or mobile. Sync is whatever Obsidian itself uses (Sync, iCloud, Git).

**What goes in the vault vs. the database:** rough rule — if it's structured data the agent generates and reads back, it goes in the database. If it's narrative or judgement-laden content the user wants to see and edit, it goes in the vault. Examples:

- Database: player attribute snapshots, match results, scout reports, transfer offers received.
- Vault: "Tactical philosophy for this season" note, "Depth chart" with drag-and-drop tables the user can rearrange, "Season story so far" narrative the agent writes after each month, transfer wishlist with the user's own thoughts.

**Conflict handling:** when both sides edit the same note, last-write-wins is fine for V5 — this isn't a multi-user system. The agent can write change-log entries as a footer to its own edits to make it easy to see what it touched.

**Why this matters for the assistant pattern:** the vault becomes the place where domain knowledge lives long-term. Scenarios (§7) describe how to operate the game; the vault describes what the user actually believes about their save. The planner can be prompted to read relevant notes before acting on a high-judgement decision (transfer offers, tactical changes), giving it personality and continuity that pure scenarios can't.

### Phase 6 and beyond — sketches only

- **Multi-app awareness.** When the agent needs to consult the FM-Base or fmscout websites, it should be able to switch to a browser, look something up, and return. This stretches the action layer to be window-aware, which is a meaningful change to Layer 3.
- **Proactive triggers.** "Run a scouting sweep every Sunday morning at 8am." Cron over `Agent.run()`, with the goal preset. Easy if the entrypoint design holds.
- **Subgraph scenarios.** When a scenario has genuinely different control flow (e.g., "respond to a transfer offer" branches into negotiate / accept / reject), it becomes a LangGraph subgraph rather than a markdown prompt. §7 already flagged this as deferred.
- **Local planner.** When NVIDIA NIM rate limits or cost become real, self-host Nemotron Nano Omni or move to a paid frontier API for the planner only.
- **Voice frontend.** The same `Agent.run` + `on_event` pattern that supports Telegram supports a voice loop. Whisper for input, any TTS for output, the agent in between.

### Phase ordering and trigger conditions

Don't build phases in a fixed order — build them when V1 reveals which is missing most. Likely triggers:

| Phase | Triggered by |
|---|---|
| 2 (Telegram) | "I want to advance time while at lunch." |
| 3 (Extraction) | "I keep asking the agent to scout but it can't remember what it saw." |
| 4 (Database) | "Phase 3 happened and now I have data with nowhere to put it." |
| 5 (Obsidian) | "I want to give the agent my opinions and have it remember." |
| 6 | Whenever — these are independent. |

Phases 3 and 4 are joined at the hip — extraction without storage is wasted work, storage without extraction is empty schemas. Plan them as one effort once the trigger fires for either.

---

This roadmap is illustrative, not binding. The shape of FM26 — what's tedious, what's interesting, what the agent is actually good at — will reshape it. The architecture is built to absorb that.
