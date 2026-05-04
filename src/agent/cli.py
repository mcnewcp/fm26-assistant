"""CLI entrypoint — thin shell over Agent.run()."""

import asyncio
import sys

from agent.agent import Agent
from agent.config import load_config


async def _main() -> None:
    if len(sys.argv) < 2:
        print("Usage: agent <goal>", file=sys.stderr)
        sys.exit(1)
    goal = sys.argv[1]
    cfg = load_config()
    agent = Agent(cfg)
    await agent.run(goal)


def main() -> None:
    asyncio.run(_main())
