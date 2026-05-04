"""Public Agent class — the single entry point for running one session."""

from agent.config import Config


class Agent:
    """Drives one session of the FM26 assistant agent end-to-end.

    Instantiate with a loaded Config, then call run() with a goal string.
    All output flows through the on_event callback; nothing is printed directly.
    """

    def __init__(self, config: Config) -> None:
        self._config = config

    async def run(self, goal: str) -> None:
        """Execute one session from goal receipt to a terminal state."""
        raise NotImplementedError
