"""Factory for assembling an Operator from a Config."""

from agent.config import Config
from agent.operator.nemotron_planner import NemotronPlannerClient
from agent.operator.protocol import GrounderClient, Operator, StubGrounderClient


def build_operator(config: Config) -> Operator:
    """Compose an Operator from config.planner and config.grounder settings.

    Planner providers: 'nvidia'
    Grounder providers: 'stub'  (mlx_local and others land in #8)
    """
    if config.planner.provider == "nvidia":
        planner = NemotronPlannerClient(
            model=config.planner.model,
            base_url=config.planner.base_url,
            api_key=config.nvidia_api_key,
        )
    else:
        raise ValueError(
            f"Unknown planner provider: {config.planner.provider!r}. Supported: 'nvidia'."
        )

    grounder: GrounderClient
    if config.grounder.provider == "stub":
        grounder = StubGrounderClient()
    else:
        raise ValueError(
            f"Unknown grounder provider: {config.grounder.provider!r}. "
            "Supported: 'stub'. (mlx_local and others land in #8)"
        )

    return Operator(planner=planner, grounder=grounder)
