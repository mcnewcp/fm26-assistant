"""Factory: build_operator composes planner and grounder from Config."""

from agent.config import Config
from agent.operator.nemotron_planner import NemotronPlannerClient
from agent.operator.protocol import GrounderClient, Operator, StubGrounderClient


def build_operator(config: Config) -> Operator:
    """Construct an Operator wired to the providers named in config."""
    planner = _build_planner(config)
    grounder = _build_grounder(config)
    return Operator(planner=planner, grounder=grounder)


def _build_planner(config: Config) -> NemotronPlannerClient:
    if config.planner.provider == "nvidia":
        return NemotronPlannerClient(
            model=config.planner.model,
            base_url=config.planner.base_url,
            api_key=config.nvidia_api_key,
        )
    raise ValueError(f"Unknown planner provider: {config.planner.provider!r}")


def _build_grounder(config: Config) -> GrounderClient:
    # Real grounder implementations arrive in slice #8.
    # All configured providers resolve to the stub until then.
    return StubGrounderClient()
