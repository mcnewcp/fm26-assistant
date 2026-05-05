"""Operator smoke CLI.

Usage:
    python -m agent.operator_smoke <screenshot_path> <goal>

Reads config.toml from the repo root (same as the main agent CLI).
Prints the resulting ActionPlan as JSON to stdout.
"""

import asyncio
import dataclasses
import json
import sys
from pathlib import Path

from agent.config import load_config
from agent.operator.factory import build_operator


async def _run(screenshot_path: Path, goal: str) -> None:
    screenshot = screenshot_path.read_bytes()
    config = load_config()
    operator = build_operator(config)
    plan = await operator.plan(screenshot, goal)
    print(json.dumps(dataclasses.asdict(plan), indent=2))


def main() -> None:
    if len(sys.argv) < 3:
        print(
            "Usage: python -m agent.operator_smoke <screenshot_path> <goal>",
            file=sys.stderr,
        )
        sys.exit(1)
    screenshot_path = Path(sys.argv[1])
    if not screenshot_path.exists():
        print(f"Error: screenshot not found: {screenshot_path}", file=sys.stderr)
        sys.exit(1)
    goal = sys.argv[2]
    asyncio.run(_run(screenshot_path, goal))


if __name__ == "__main__":
    main()
