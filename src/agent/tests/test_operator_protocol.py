"""Tests for ActionPlan validation invariants."""

import pytest

from agent.operator.protocol import ActionPlan, Coordinates, StubGrounderClient


# --- ActionPlan construction ---


def test_basic_click_plan():
    plan = ActionPlan(action_type="click", target_description="Submit button")
    assert plan.action_type == "click"
    assert plan.target_description == "Submit button"
    assert not plan.done


def test_basic_type_plan():
    plan = ActionPlan(action_type="type", text="hello world")
    assert plan.text == "hello world"


def test_basic_key_plan():
    plan = ActionPlan(action_type="key", key="Return")
    assert plan.key == "Return"


def test_note_is_optional():
    plan = ActionPlan(action_type="screenshot", note="Screen appears normal")
    assert plan.note == "Screen appears normal"


def test_all_optional_fields_default_to_none():
    plan = ActionPlan(action_type="screenshot")
    assert plan.target_description is None
    assert plan.text is None
    assert plan.key is None
    assert plan.note is None
    assert plan.done is False
    assert plan.done_reason is None
    assert plan.summary is None


# --- done flag invariants ---


def test_done_true_requires_done_reason():
    with pytest.raises(ValueError, match="done_reason"):
        ActionPlan(action_type="done", done=True)


def test_done_false_without_done_reason_is_valid():
    plan = ActionPlan(action_type="screenshot", done=False)
    assert plan.done_reason is None


# --- done_reason invariants ---


def test_done_reason_goal_complete_requires_summary():
    with pytest.raises(ValueError, match="summary"):
        ActionPlan(action_type="done", done=True, done_reason="goal_complete")


def test_done_reason_handoff_requires_summary():
    with pytest.raises(ValueError, match="summary"):
        ActionPlan(action_type="done", done=True, done_reason="handoff")


def test_done_goal_complete_with_summary_is_valid():
    plan = ActionPlan(
        action_type="done",
        done=True,
        done_reason="goal_complete",
        summary="Reached the next match.",
    )
    assert plan.done_reason == "goal_complete"
    assert plan.summary == "Reached the next match."


def test_done_handoff_with_summary_is_valid():
    plan = ActionPlan(
        action_type="done",
        done=True,
        done_reason="handoff",
        summary="Player injured — user attention required.",
    )
    assert plan.done_reason == "handoff"


# --- mutual-exclusion invariants ---


def test_target_description_and_text_are_mutually_exclusive():
    with pytest.raises(ValueError, match="mutually exclusive"):
        ActionPlan(action_type="type", target_description="Input field", text="hello")


def test_target_description_and_key_are_mutually_exclusive():
    with pytest.raises(ValueError, match="mutually exclusive"):
        ActionPlan(action_type="click", target_description="Button", key="Return")


def test_text_and_key_are_mutually_exclusive():
    with pytest.raises(ValueError, match="mutually exclusive"):
        ActionPlan(action_type="type", text="hello", key="Return")


def test_all_three_action_fields_are_mutually_exclusive():
    with pytest.raises(ValueError, match="mutually exclusive"):
        ActionPlan(
            action_type="click",
            target_description="Button",
            text="hello",
            key="Return",
        )


def test_all_three_action_fields_none_is_valid():
    plan = ActionPlan(action_type="screenshot")
    assert plan.target_description is None
    assert plan.text is None
    assert plan.key is None


# --- StubGrounderClient ---


async def test_stub_grounder_returns_fixed_coordinate():
    stub = StubGrounderClient()
    coord = await stub.ground(b"fake_screenshot", "Submit button")
    assert coord == Coordinates(x=640, y=400)
