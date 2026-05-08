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


@pytest.fixture(scope="module")
def scenarios() -> list[Scenario]:
    return load_scenarios(_SCENARIOS_DIR)


@pytest.fixture(scope="module")
def default_scenario(scenarios: list[Scenario]) -> Scenario:
    return next(s for s in scenarios if s.name == "default")


@pytest.fixture(scope="module")
def advance_scenario(scenarios: list[Scenario]) -> Scenario:
    return next(s for s in scenarios if s.name == "advance_to_next_match")


# ---------------------------------------------------------------------------
# Happy-path: default.md
# ---------------------------------------------------------------------------


def test_load_default_scenario_name(default_scenario: Scenario) -> None:
    assert default_scenario.name == "default"


def test_load_default_scenario_prose_sections_populated(default_scenario: Scenario) -> None:
    assert default_scenario.when_to_use
    assert default_scenario.goal_restatement
    assert default_scenario.decomposition
    assert default_scenario.ui_knowledge
    assert default_scenario.note_taking
    assert default_scenario.done_criteria


def test_load_default_scenario_handoff_trigger_count(default_scenario: Scenario) -> None:
    assert len(default_scenario.handoff_triggers) == 2


def test_load_default_scenario_handoff_trigger_names(default_scenario: Scenario) -> None:
    names = [t.name for t in default_scenario.handoff_triggers]
    assert "Application crash / unresponsive state" in names
    assert "Bizarre / unrecognized state" in names


def test_load_default_scenario_trigger_fields_populated(default_scenario: Scenario) -> None:
    for trigger in default_scenario.handoff_triggers:
        assert trigger.visual_signal
        assert trigger.surfaced_summary
        assert trigger.after_surfacing


# ---------------------------------------------------------------------------
# Happy-path: advance_to_next_match.md
# ---------------------------------------------------------------------------


def test_load_advance_scenario_name(advance_scenario: Scenario) -> None:
    assert advance_scenario.name == "advance_to_next_match"


def test_load_advance_scenario_prose_sections_populated(advance_scenario: Scenario) -> None:
    assert advance_scenario.when_to_use
    assert advance_scenario.goal_restatement
    assert advance_scenario.decomposition
    assert advance_scenario.ui_knowledge
    assert advance_scenario.note_taking
    assert advance_scenario.done_criteria


def test_load_advance_scenario_handoff_trigger_count(advance_scenario: Scenario) -> None:
    assert len(advance_scenario.handoff_triggers) == 1


def test_load_advance_scenario_handoff_trigger_name(advance_scenario: Scenario) -> None:
    assert advance_scenario.handoff_triggers[0].name == "Player injury (own team)"


def test_load_advance_scenario_trigger_fields_populated(advance_scenario: Scenario) -> None:
    trigger = advance_scenario.handoff_triggers[0]
    assert trigger.visual_signal
    assert trigger.surfaced_summary
    assert trigger.after_surfacing


# ---------------------------------------------------------------------------
# Model types
# ---------------------------------------------------------------------------


def test_scenario_is_scenario_type(scenarios: list[Scenario]) -> None:
    for s in scenarios:
        assert isinstance(s, Scenario)


def test_handoff_trigger_is_handofftrigger_type(default_scenario: Scenario) -> None:
    for t in default_scenario.handoff_triggers:
        assert isinstance(t, HandoffTrigger)


# ---------------------------------------------------------------------------
# Section slicing — fixture with unique markers per section catches off-by-one
# bugs in the H2/H3 line-map slicing that the truthiness checks above miss.
# ---------------------------------------------------------------------------


def test_section_slicing_routes_each_marker_to_its_own_field() -> None:
    scenario = parse_scenario_file(_FIXTURES_DIR / "section_boundaries.md")

    field_to_marker = {
        "when_to_use": "WHEN_TO_USE_MARKER",
        "goal_restatement": "GOAL_RESTATEMENT_MARKER",
        "decomposition": "DECOMPOSITION_MARKER",
        "ui_knowledge": "UI_KNOWLEDGE_MARKER",
        "note_taking": "NOTE_TAKING_MARKER",
        "done_criteria": "DONE_CRITERIA_MARKER",
    }

    for field, own_marker in field_to_marker.items():
        value = getattr(scenario, field)
        assert own_marker in value, f"{field} missing its own marker {own_marker}"
        for other_field, other_marker in field_to_marker.items():
            if other_field == field:
                continue
            assert other_marker not in value, (
                f"{field} leaked content from {other_field} ({other_marker})"
            )


def test_section_slicing_routes_each_trigger_marker_to_its_own_field() -> None:
    scenario = parse_scenario_file(_FIXTURES_DIR / "section_boundaries.md")
    assert len(scenario.handoff_triggers) == 1
    trigger = scenario.handoff_triggers[0]
    assert trigger.name == "Boundary trigger"

    field_to_marker = {
        "visual_signal": "VISUAL_SIGNAL_MARKER",
        "surfaced_summary": "SURFACED_SUMMARY_MARKER",
        "after_surfacing": "AFTER_SURFACING_MARKER",
    }

    for field, own_marker in field_to_marker.items():
        value = getattr(trigger, field)
        assert own_marker in value, f"{field} missing its own marker {own_marker}"
        for other_field, other_marker in field_to_marker.items():
            if other_field == field:
                continue
            assert other_marker not in value, (
                f"{field} leaked content from {other_field} ({other_marker})"
            )


# ---------------------------------------------------------------------------
# get_universal_handoff_triggers
# ---------------------------------------------------------------------------


def test_universal_triggers_returns_default_triggers(scenarios: list[Scenario]) -> None:
    universal = get_universal_handoff_triggers(scenarios)
    assert len(universal) == 2
    names = [t.name for t in universal]
    assert "Application crash / unresponsive state" in names
    assert "Bizarre / unrecognized state" in names


def test_universal_triggers_raises_when_no_default(scenarios: list[Scenario]) -> None:
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
