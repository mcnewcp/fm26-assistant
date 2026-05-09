"""NemotronPlannerClient — NVIDIA NIM planner via the OpenAI-compatible API.

This is the only module in the operator sub-package that imports a vendor SDK.
"""

from __future__ import annotations

import base64
import dataclasses
import json
from typing import Any

from openai import AsyncOpenAI
from openai.types.shared_params import ResponseFormatJSONObject

from agent.operator.protocol import ActionPlan, MalformedPlannerOutputError

_SYSTEM_PROMPT = """\
You are a computer-use agent controlling a Football Manager 26 game. \
Your task is to decide the next single action to take in order to \
accomplish the given goal.

Return a JSON object with EXACTLY these fields:
{
  "action_type": one of "click" | "double_click" | "right_click" | \
"type" | "key" | "scroll" | "screenshot" | "sleep" | "done",
  "target_description": string or null,
  "text": string or null,
  "key": string or null,
  "note": string or null,
  "done": boolean,
  "done_reason": "goal_complete" | "handoff" | null,
  "summary": string or null
}

Rules:
- Exactly one of target_description, text, key may be non-null at a time.
- Set target_description for click/scroll actions (describes the UI element).
- Set text for type actions. Set key for key-press actions (e.g. "Return", "cmd+z").
- Set note to record a short observation that should persist across steps.
- Set done=true when the goal is complete or a handoff condition is met.
- When done=true, done_reason must be "goal_complete" or "handoff".
- When done_reason is set, summary must be a user-facing sentence describing the outcome.

Respond with only a valid JSON object — no markdown fences, no explanation.
"""


def _build_messages(
    screenshot: bytes,
    goal: str,
    scenario: str,
    action_history: list[str],
    notes: list[str],
) -> list[Any]:
    image_b64 = base64.b64encode(screenshot).decode()

    parts: list[str] = [f"Goal: {goal}"]
    if scenario:
        parts.append(f"\nScenario:\n{scenario}")
    if notes:
        parts.append("\nNotes from previous steps:\n" + "\n".join(f"- {n}" for n in notes))
    if action_history:
        parts.append("\nRecent action history:\n" + "\n".join(action_history))
    parts.append("\nDecide the next single action.")

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                },
                {"type": "text", "text": "".join(parts)},
            ],
        },
    ]


def _parse_action_plan(data: dict[str, Any]) -> ActionPlan:
    valid = {f.name for f in dataclasses.fields(ActionPlan)}
    return ActionPlan(**{k: v for k, v in data.items() if k in valid})


class NemotronPlannerClient:
    """Calls the NVIDIA NIM OpenAI-compatible endpoint and returns an ActionPlan."""

    def __init__(self, model: str, base_url: str, api_key: str) -> None:
        self._model = model
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key or "not-needed")

    async def plan(
        self,
        screenshot: bytes,
        goal: str,
        scenario: str,
        action_history: list[str],
        notes: list[str],
    ) -> ActionPlan:
        messages = _build_messages(screenshot, goal, scenario, action_history, notes)
        last_exc: Exception | None = None

        for _ in range(2):
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                response_format=ResponseFormatJSONObject(type="json_object"),
                max_tokens=4096,
            )
            raw = response.choices[0].message.content or ""
            try:
                data = json.loads(raw)
                return _parse_action_plan(data)
            except (json.JSONDecodeError, ValueError) as exc:
                last_exc = exc

        raise MalformedPlannerOutputError(
            f"Planner returned an invalid ActionPlan after 2 attempts. "
            f"Last error: {last_exc!r}"
        ) from last_exc
