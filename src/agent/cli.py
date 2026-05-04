"""CLI entry point — thin shell over Agent.run()."""

import asyncio
import sys

from agent.agent import Agent
from agent.config import load_config


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: fm26 <goal>", file=sys.stderr)
        sys.exit(1)
    goal = sys.argv[1]
    config = load_config()
    agent = Agent(config)
    asyncio.run(agent.run(goal))


if __name__ == "__main__":
    main()
