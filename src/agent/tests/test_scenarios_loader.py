"""Tests for agent.scenarios.loader — written before the implementation (TDD)."""

from pathlib import Path

import pytest

from agent.scenarios.loader import (
    HandoffTrigger,
    MissingDefaultScenarioError,
    Scenario,
    ScenarioParseError,
    get_universal_handoff_triggers,
    load_scenarios,
    parse_scenario_file,
)

# Paths anchored to the repo layout — not duplicated as fixtures.
_REPO_ROOT = Path(__file__).parents[3]
_SCENARIOS_DIR = _REPO_ROOT / "scenarios"
_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "scenarios"


# ---------------------------------------------------------------------------
# Happy-path: default.md
# ---------------------------------------------------------------------------


def test_load_default_scenario_name() -> None:
    scenarios = load_scenarios(_SCENARIOS_DIR)
    default = next(s for s in scenarios if s.name == "default")
    assert default.name == "default"


def test_load_default_scenario_prose_sections_populated() -> None:
    scenarios = load_scenarios(_SCENARIOS_DIR)
    default = next(s for s in scenarios if s.name == "default")
    assert default.when_to_use
    assert default.goal_restatement
    assert default.decomposition
    assert default.ui_knowledge
    assert default.note_taking
    assert default.done_criteria


def test_load_default_scenario_handoff_trigger_count() -> None:
    scenarios = load_scenarios(_SCENARIOS_DIR)
    default = next(s for s in scenarios if s.name == "default")
    assert len(default.handoff_triggers) == 2


def test_load_default_scenario_handoff_trigger_names() -> None:
    scenarios = load_scenarios(_SCENARIOS_DIR)
    default = next(s for s in scenarios if s.name == "default")
    names = [t.name for t in default.handoff_triggers]
    assert "Application crash / unresponsive state" in names
    assert "Bizarre / unrecognized state" in names


def test_load_default_scenario_trigger_fields_populated() -> None:
    scenarios = load_scenarios(_SCENARIOS_DIR)
    default = next(s for s in scenarios if s.name == "default")
    for trigger in default.handoff_triggers:
        assert trigger.visual_signal
        assert trigger.surfaced_summary
        assert trigger.after_surfacing


# ---------------------------------------------------------------------------
# Happy-path: advance_to_next_match.md
# ---------------------------------------------------------------------------


def test_load_advance_scenario_name() -> None:
    scenarios = load_scenarios(_SCENARIOS_DIR)
    advance = next(s for s in scenarios if s.name == "advance_to_next_match")
    assert advance.name == "advance_to_next_match"


def test_load_advance_scenario_prose_sections_populated() -> None:
    scenarios = load_scenarios(_SCENARIOS_DIR)
    advance = next(s for s in scenarios if s.name == "advance_to_next_match")
    assert advance.when_to_use
    assert advance.goal_restatement
    assert advance.decomposition
    assert advance.ui_knowledge
    assert advance.note_taking
    assert advance.done_criteria


def test_load_advance_scenario_handoff_trigger_count() -> None:
    scenarios = load_scenarios(_SCENARIOS_DIR)
    advance = next(s for s in scenarios if s.name == "advance_to_next_match")
    assert len(advance.handoff_triggers) == 1


def test_load_advance_scenario_handoff_trigger_name() -> None:
    scenarios = load_scenarios(_SCENARIOS_DIR)
    advance = next(s for s in scenarios if s.name == "advance_to_next_match")
    assert advance.handoff_triggers[0].name == "Player injury (own team)"


def test_load_advance_scenario_trigger_fields_populated() -> None:
    scenarios = load_scenarios(_SCENARIOS_DIR)
    advance = next(s for s in scenarios if s.name == "advance_to_next_match")
    trigger = advance.handoff_triggers[0]
    assert trigger.visual_signal
    assert trigger.surfaced_summary
    assert trigger.after_surfacing


# ---------------------------------------------------------------------------
# Model types
# ---------------------------------------------------------------------------


def test_scenario_is_scenario_type() -> None:
    scenarios = load_scenarios(_SCENARIOS_DIR)
    for s in scenarios:
        assert isinstance(s, Scenario)


def test_handoff_trigger_is_handofftrigger_type() -> None:
    scenarios = load_scenarios(_SCENARIOS_DIR)
    default = next(s for s in scenarios if s.name == "default")
    for t in default.handoff_triggers:
        assert isinstance(t, HandoffTrigger)


# ---------------------------------------------------------------------------
# get_universal_handoff_triggers
# ---------------------------------------------------------------------------


def test_universal_triggers_returns_default_triggers() -> None:
    scenarios = load_scenarios(_SCENARIOS_DIR)
    universal = get_universal_handoff_triggers(scenarios)
    assert len(universal) == 2
    names = [t.name for t in universal]
    assert "Application crash / unresponsive state" in names
    assert "Bizarre / unrecognized state" in names


def test_universal_triggers_raises_when_no_default() -> None:
    scenarios = load_scenarios(_SCENARIOS_DIR)
    non_default = [s for s in scenarios if s.name != "default"]
    with pytest.raises(MissingDefaultScenarioError):
        get_universal_handoff_triggers(non_default)


def test_universal_triggers_raises_when_list_is_empty() -> None:
    with pytest.raises(MissingDefaultScenarioError):
        get_universal_handoff_triggers([])


# ---------------------------------------------------------------------------
# Error cases: fixture files — parsed individually to isolate each failure.
# ---------------------------------------------------------------------------


def test_missing_section_raises_parse_error() -> None:
    fixture = _FIXTURES_DIR / "missing_section.md"
    with pytest.raises(ScenarioParseError) as exc_info:
        parse_scenario_file(fixture)
    err = str(exc_info.value).lower()
    assert "done_criteria" in err or "done criteria" in err


def test_malformed_trigger_raises_parse_error() -> None:
    fixture = _FIXTURES_DIR / "malformed_trigger.md"
    with pytest.raises(ScenarioParseError) as exc_info:
        parse_scenario_file(fixture)
    err = str(exc_info.value).lower()
    assert "incomplete trigger" in err
    assert "after_surfacing" in err or "after surfacing" in err
