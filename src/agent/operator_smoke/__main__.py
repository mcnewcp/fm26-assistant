"""Operator smoke CLI.

Usage:
    python -m agent.operator_smoke <screenshot_path> <goal>

Loads config.toml, builds an Operator with the configured planner and a
stub grounder, calls propose_action, and prints the resulting ActionPlan as JSON.
The stub grounder returns a fixed coordinate (640, 400) for any grounding
request, so no local model or grounder API key is needed.

Requires NVIDIA_API_KEY in the environment (or config.toml) when
planner.provider = "nvidia".
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import sys
from pathlib import Path

from agent.config import GrounderConfig, load_config
from agent.operator.factory import build_operator


async def _main() -> None:
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
    screenshot = screenshot_path.read_bytes()

    cfg = load_config()
    # Use stub grounder — the real grounder (mlx_local) is wired in #8.
    smoke_cfg = cfg.model_copy(update={"grounder": GrounderConfig(provider="stub")})
    operator = build_operator(smoke_cfg)

    plan = await operator.propose_action(
        screenshot=screenshot,
        goal=goal,
        scenario="",
        action_history=[],
        notes=[],
    )
    print(json.dumps(dataclasses.asdict(plan), indent=2))


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
