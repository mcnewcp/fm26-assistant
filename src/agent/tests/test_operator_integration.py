"""Integration test for NemotronPlannerClient — gated by NVIDIA_API_KEY.

Run with:
    NVIDIA_API_KEY=<key> uv run pytest src/agent/tests/test_operator_integration.py -v
"""

import os
from pathlib import Path

import pytest

from agent.operator.nemotron_planner import NemotronPlannerClient
from agent.operator.protocol import ActionPlan

_NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")

pytestmark = pytest.mark.skipif(
    not _NVIDIA_API_KEY,
    reason="NVIDIA_API_KEY not set",
)

_FIXTURE_SCREENSHOT = Path(__file__).parent / "fixtures" / "screenshot.png"

_VALID_ACTION_TYPES = frozenset(
    {"click", "double_click", "right_click", "type", "key", "scroll", "screenshot", "sleep", "done"}
)


async def test_nemotron_planner_returns_valid_action_plan() -> None:
    planner = NemotronPlannerClient(
        model="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=_NVIDIA_API_KEY,
    )
    screenshot = _FIXTURE_SCREENSHOT.read_bytes()

    plan = await planner.plan(
        screenshot=screenshot,
        goal="Take a screenshot to observe the current state",
        scenario="",
        action_history=[],
        notes=[],
    )

    assert isinstance(plan, ActionPlan)
    assert plan.action_type in _VALID_ACTION_TYPES
    if plan.done:
        assert plan.done_reason in ("goal_complete", "handoff")
        assert plan.summary is not None
    if plan.done_reason is not None:
        assert plan.summary is not None
    exclusive = [f for f in (plan.target_description, plan.text, plan.key) if f is not None]
    assert len(exclusive) <= 1
