"""Tests for ActionPlan validation invariants."""

import pytest

from agent.operator.protocol import ActionPlan


def test_valid_click_action() -> None:
    plan = ActionPlan(action_type="click", target_description="Submit button")
    assert plan.action_type == "click"
    assert plan.target_description == "Submit button"
    assert plan.done is False


def test_valid_type_action() -> None:
    plan = ActionPlan(action_type="type", text="hello world")
    assert plan.text == "hello world"


def test_valid_key_action() -> None:
    plan = ActionPlan(action_type="key", key="return")
    assert plan.key == "return"


def test_valid_screenshot_action() -> None:
    plan = ActionPlan(action_type="screenshot")
    assert plan.done is False
    assert plan.done_reason is None


def test_valid_goal_complete() -> None:
    plan = ActionPlan(
        action_type="screenshot",
        done=True,
        done_reason="goal_complete",
        summary="Reached the match-prep screen.",
    )
    assert plan.done_reason == "goal_complete"
    assert plan.summary == "Reached the match-prep screen."


def test_valid_handoff() -> None:
    plan = ActionPlan(
        action_type="screenshot",
        done=True,
        done_reason="handoff",
        summary="Player injury detected.",
    )
    assert plan.done_reason == "handoff"


def test_note_is_optional_and_preserved() -> None:
    plan = ActionPlan(action_type="click", target_description="OK", note="Board message read.")
    assert plan.note == "Board message read."


# --- invariant: done=True requires done_reason ---

def test_done_true_without_done_reason_raises() -> None:
    with pytest.raises(ValueError, match="done_reason"):
        ActionPlan(action_type="screenshot", done=True)


# --- invariant: done_reason requires summary ---

def test_goal_complete_without_summary_raises() -> None:
    with pytest.raises(ValueError, match="summary"):
        ActionPlan(action_type="screenshot", done=True, done_reason="goal_complete")


def test_handoff_without_summary_raises() -> None:
    with pytest.raises(ValueError, match="summary"):
        ActionPlan(action_type="screenshot", done=True, done_reason="handoff")


# --- invariant: mutually exclusive action fields ---

def test_target_description_and_text_are_exclusive() -> None:
    with pytest.raises(ValueError, match="Mutually exclusive"):
        ActionPlan(action_type="click", target_description="Submit", text="hello")


def test_target_description_and_key_are_exclusive() -> None:
    with pytest.raises(ValueError, match="Mutually exclusive"):
        ActionPlan(action_type="click", target_description="Submit", key="return")


def test_text_and_key_are_exclusive() -> None:
    with pytest.raises(ValueError, match="Mutually exclusive"):
        ActionPlan(action_type="type", text="hello", key="return")


def test_all_three_action_fields_exclusive() -> None:
    with pytest.raises(ValueError, match="Mutually exclusive"):
        ActionPlan(
            action_type="click",
            target_description="x",
            text="y",
            key="z",
        )
