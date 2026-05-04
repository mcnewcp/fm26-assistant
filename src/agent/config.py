"""Configuration loader for the FM26 agent.

Reads config.toml from the repository root; environment variables override
any matching field (e.g. NVIDIA_API_KEY overrides nvidia_api_key).
Required fields (planner.provider, planner.model, planner.base_url,
grounder.provider) raise pydantic.ValidationError when absent.
"""

from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

# Repository root: src/agent/config.py → parents[2] is the repo root.
_REPO_ROOT = Path(__file__).parents[2]


class OrchestrationConfig(BaseModel):
    max_steps: int = 50
    screenshot_history_size: int = 3


class PlannerConfig(BaseModel):
    provider: str
    model: str
    base_url: str


class GrounderConfig(BaseModel):
    provider: str
    model_path: str = ""
    server_url: str = ""


class ActionConfig(BaseModel):
    mcp_server: str = "computer-control-mcp"


class ScenariosConfig(BaseModel):
    directory: str = "scenarios"


class ObservabilityConfig(BaseModel):
    sessions_dir: str = "runs"


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")

    orchestration: OrchestrationConfig = OrchestrationConfig()
    planner: PlannerConfig
    grounder: GrounderConfig
    action: ActionConfig = ActionConfig()
    scenarios: ScenariosConfig = ScenariosConfig()
    observability: ObservabilityConfig = ObservabilityConfig()

    # Secret populated from NVIDIA_API_KEY env var; never written to config.toml.
    nvidia_api_key: str = ""


def load_config(config_path: Path | None = None) -> Config:
    """Load Config from config.toml with environment-variable overrides.

    Priority (highest to lowest): env vars → TOML file → field defaults.
    Raises pydantic.ValidationError when required fields are absent.
    """
    base = Path(config_path) if config_path is not None else _REPO_ROOT / "config.toml"
    toml_path_str = str(base.resolve())

    class _Config(Config):
        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return (
                init_settings,
                env_settings,
                TomlConfigSettingsSource(settings_cls, toml_file=toml_path_str),
            )

    return _Config()  # type: ignore[call-arg]  # required fields are loaded from TOML/env
