"""Public Agent class — single entry point for all surfaces (CLI, Telegram, etc.)."""

from collections.abc import Callable

from agent.config import Config


class Agent:
    def __init__(self, config: Config) -> None:
        self._config = config

    async def run(
        self,
        goal: str,
        *,
        on_event: Callable[[object], None] | None = None,
    ) -> None:
        """Execute one full session from goal to a terminal state."""
        raise NotImplementedError
