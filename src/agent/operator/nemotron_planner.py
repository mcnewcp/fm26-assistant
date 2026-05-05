"""NemotronPlannerClient — NVIDIA NIM OpenAI-compatible planner."""

import base64
import dataclasses
import json

import httpx

from agent.operator.protocol import ActionPlan, MalformedPlannerOutputError

_SYSTEM_PROMPT = """\
You are a computer-use agent driving a desktop application.
Given a screenshot and a goal, decide the single next action to take.

Respond with a JSON object matching this schema exactly:
{
  "action_type": "click" | "type" | "key" | "screenshot",
  "target_description": string | null,
  "text": string | null,
  "key": string | null,
  "note": string | null,
  "done": boolean,
  "done_reason": null | "goal_complete" | "handoff",
  "summary": string | null
}

Field rules:
- action_type="click"      → set target_description, leave text/key null
- action_type="type"       → set text, leave target_description/key null
- action_type="key"        → set key (e.g. "return", "escape", "cmd+c"), leave others null
- action_type="screenshot" → leave target_description/text/key null
- done=true                → set done_reason ("goal_complete" or "handoff") and summary
- done=false               → leave done_reason and summary null
- note                     → optional short observation to carry forward

Respond with the JSON object only — no markdown, no prose."""

_KNOWN_FIELDS: frozenset[str] = frozenset(f.name for f in dataclasses.fields(ActionPlan))


def _build_payload(
    model: str,
    screenshot: bytes,
    goal: str,
    scenario: str,
    action_history: list[str],
    notes: list[str],
) -> dict[str, object]:
    image_b64 = base64.b64encode(screenshot).decode()
    history_lines = "\n".join(f"  {h}" for h in action_history) if action_history else "  (none)"
    notes_lines = "\n".join(f"  {n}" for n in notes) if notes else "  (none)"
    user_text = (
        f"Goal: {goal}\n\n"
        f"Scenario:\n{scenario or '(default)'}\n\n"
        f"Action history:\n{history_lines}\n\n"
        f"Notes:\n{notes_lines}\n\n"
        "Decide the next action."
    )
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                    {"type": "text", "text": user_text},
                ],
            },
        ],
        "response_format": {"type": "json_object"},
    }


def _parse(content: str) -> ActionPlan:
    data: object = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object, got {type(data).__name__}")
    filtered = {k: v for k, v in data.items() if k in _KNOWN_FIELDS}
    return ActionPlan(**filtered)  # type: ignore[arg-type]


class NemotronPlannerClient:
    """Calls NVIDIA NIM's OpenAI-compatible endpoint and returns an ActionPlan.

    One retry on malformed JSON; second failure raises MalformedPlannerOutputError.
    No vendor SDK imports here — only httpx.
    """

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._client = client

    async def plan(
        self,
        screenshot: bytes,
        goal: str,
        scenario: str,
        action_history: list[str],
        notes: list[str],
    ) -> ActionPlan:
        payload = _build_payload(self._model, screenshot, goal, scenario, action_history, notes)
        last_exc: Exception = Exception("no attempts made")
        for _ in range(2):
            raw = await self._post(payload)
            try:
                return _parse(raw)
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                last_exc = exc
        raise MalformedPlannerOutputError(
            f"Planner returned malformed output twice: {last_exc}"
        ) from last_exc

    async def _post(self, payload: dict[str, object]) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/chat/completions"
        if self._client is not None:
            resp = await self._client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return str(resp.json()["choices"][0]["message"]["content"])
        async with httpx.AsyncClient() as c:
            resp = await c.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return str(resp.json()["choices"][0]["message"]["content"])
