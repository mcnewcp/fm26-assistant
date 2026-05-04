"""Scenario loader: parses markdown scenario files into typed Pydantic records."""

import re
from pathlib import Path

from markdown_it import MarkdownIt
from pydantic import BaseModel

_md = MarkdownIt()

# H2 section heading text → Scenario field name (for the six prose fields).
_PROSE_SECTION_MAP: dict[str, str] = {
    "When to use": "when_to_use",
    "Goal restatement": "goal_restatement",
    "Decomposition": "decomposition",
    "UI knowledge": "ui_knowledge",
    "Note-taking discipline": "note_taking",
    "Done criteria": "done_criteria",
}

# All seven required H2 headings (prose + the structural triggers section).
_REQUIRED_HEADINGS: list[str] = list(_PROSE_SECTION_MAP.keys()) + ["Handoff triggers"]

# Trigger bullet field label → HandoffTrigger field name.
_TRIGGER_FIELD_MAP: dict[str, str] = {
    "Visual signal": "visual_signal",
    "Surfaced summary": "surfaced_summary",
    "After surfacing": "after_surfacing",
}


class ScenarioParseError(Exception):
    """Raised when a scenario file cannot be parsed due to missing or malformed content."""


class MissingDefaultScenarioError(Exception):
    """Raised when no scenario named 'default' is present in the scenario list."""


class HandoffTrigger(BaseModel):
    name: str
    visual_signal: str
    surfaced_summary: str
    after_surfacing: str


class Scenario(BaseModel):
    name: str
    when_to_use: str
    goal_restatement: str
    decomposition: str
    ui_knowledge: str
    note_taking: str
    done_criteria: str
    handoff_triggers: list[HandoffTrigger]


def _headings_with_lines(source: str) -> list[tuple[int, str, int]]:
    """Return (level, heading_text, start_line) for every heading in source."""
    tokens = _md.parse(source)
    result: list[tuple[int, str, int]] = []
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.map is not None:
            level = int(tok.tag[1])
            heading_text = tokens[i + 1].content
            result.append((level, heading_text, tok.map[0]))
    return result


def _extract_h2_sections(source: str) -> dict[str, str]:
    """Return {heading_text: raw_markdown_content} for every H2 section."""
    lines = source.splitlines()
    h2s = [(text, start) for level, text, start in _headings_with_lines(source) if level == 2]
    sections: dict[str, str] = {}
    for idx, (title, start_line) in enumerate(h2s):
        content_start = start_line + 1
        content_end = h2s[idx + 1][1] if idx + 1 < len(h2s) else len(lines)
        sections[title] = "\n".join(lines[content_start:content_end]).strip()
    return sections


def _extract_h3_subsections(section_raw: str) -> list[tuple[str, str]]:
    """Return [(name, raw_content)] for every H3 sub-section in section_raw."""
    lines = section_raw.splitlines()
    h3s = [(text, start) for level, text, start in _headings_with_lines(section_raw) if level == 3]
    result: list[tuple[str, str]] = []
    for idx, (name, start_line) in enumerate(h3s):
        content_start = start_line + 1
        content_end = h3s[idx + 1][1] if idx + 1 < len(h3s) else len(lines)
        content = "\n".join(lines[content_start:content_end]).strip()
        result.append((name, content))
    return result


def _parse_trigger(name: str, content: str) -> HandoffTrigger:
    """Parse a single HandoffTrigger from the raw content of an H3 sub-section."""
    found: dict[str, str] = {}
    for field_label, field_key in _TRIGGER_FIELD_MAP.items():
        # Handle both **Field:** (colon inside bold) and **Field**: (colon outside bold).
        pattern = re.compile(r"\*\*" + re.escape(field_label) + r"(?::\*\*|\*\*:)\s*(.*)")
        for line in content.splitlines():
            m = pattern.search(line)
            if m:
                found[field_key] = m.group(1).strip()
                break

    missing = [k for k in _TRIGGER_FIELD_MAP.values() if k not in found]
    if missing:
        raise ScenarioParseError(
            f"Trigger '{name}' is missing required field(s): {', '.join(missing)}"
        )

    return HandoffTrigger(
        name=name,
        visual_signal=found["visual_signal"],
        surfaced_summary=found["surfaced_summary"],
        after_surfacing=found["after_surfacing"],
    )


def parse_scenario_file(path: Path) -> Scenario:
    """Parse a single scenario markdown file into a Scenario record.

    Raises ScenarioParseError if any required section or trigger field is absent.
    The scenario name is derived from the filename stem, not the H1 heading.
    """
    source = path.read_text(encoding="utf-8")
    sections = _extract_h2_sections(source)

    for heading in _REQUIRED_HEADINGS:
        if heading not in sections:
            field_name = _PROSE_SECTION_MAP.get(
                heading, heading.lower().replace(" ", "_").replace("-", "_")
            )
            raise ScenarioParseError(
                f"Scenario '{path.stem}' is missing required section "
                f"'## {heading}' (field: {field_name})"
            )

    triggers = [
        _parse_trigger(name, content)
        for name, content in _extract_h3_subsections(sections["Handoff triggers"])
    ]

    return Scenario(
        name=path.stem,
        when_to_use=sections["When to use"],
        goal_restatement=sections["Goal restatement"],
        decomposition=sections["Decomposition"],
        ui_knowledge=sections["UI knowledge"],
        note_taking=sections["Note-taking discipline"],
        done_criteria=sections["Done criteria"],
        handoff_triggers=triggers,
    )


def load_scenarios(directory: Path) -> list[Scenario]:
    """Parse every *.md file in directory and return the resulting Scenario records."""
    return [parse_scenario_file(p) for p in sorted(directory.glob("*.md"))]


def get_universal_handoff_triggers(scenarios: list[Scenario]) -> list[HandoffTrigger]:
    """Return the handoff triggers from the 'default' scenario.

    These are the universal triggers that apply to every session regardless of
    which scenario is active — declared once in default.md and inherited by all.
    Raises MissingDefaultScenarioError if no scenario named 'default' is present.
    """
    for s in scenarios:
        if s.name == "default":
            return s.handoff_triggers
    raise MissingDefaultScenarioError(
        "No 'default' scenario found in the provided list; "
        "cannot determine universal handoff triggers."
    )
