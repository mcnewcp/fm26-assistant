"""Configuration loading for the fm26-assistant agent."""

from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

_REPO_ROOT = Path(__file__).parent.parent.parent


class ConfigError(Exception):
    """Raised when configuration is invalid or a required field is missing."""


class OrchestrationConfig(BaseModel):
    max_steps: int = 50
    screenshot_history_size: int = 3


class PlannerConfig(BaseModel):
    provider: str = "nvidia"
    model: str = "nemotron-3-nano-omni-30b-a3b-reasoning"
    base_url: str = "https://integrate.api.nvidia.com/v1"


class GrounderConfig(BaseModel):
    provider: str = "mlx_local"
    model_path: str = "./models/Holo2-8B-MLX-4bit"
    server_url: str = "http://localhost:8080/v1"


class ActionConfig(BaseModel):
    mcp_server: str = "computer-control-mcp"


class ScenariosConfig(BaseModel):
    directory: str = "scenarios"


class ObservabilityConfig(BaseModel):
    sessions_dir: str = "runs"


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")

    # Required: must be provided via NVIDIA_API_KEY env var or config.toml.
    # Default "" triggers the validator below when neither source supplies a value.
    nvidia_api_key: str = Field(default="", validate_default=True)

    @field_validator("nvidia_api_key")
    @classmethod
    def _require_api_key(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "nvidia_api_key is required; set the NVIDIA_API_KEY environment variable"
            )
        return v

    orchestration: OrchestrationConfig = OrchestrationConfig()
    planner: PlannerConfig = PlannerConfig()
    grounder: GrounderConfig = GrounderConfig()
    action: ActionConfig = ActionConfig()
    scenarios: ScenariosConfig = ScenariosConfig()
    observability: ObservabilityConfig = ObservabilityConfig()


def load_config(config_path: Path | None = None) -> Config:
    """Load config from TOML file with environment-variable overrides for secrets.

    Secrets (e.g. NVIDIA_API_KEY) are read from env and never written to the TOML.
    Raises ConfigError when a required field is missing from both TOML and env.
    """
    toml_path = config_path if config_path is not None else _REPO_ROOT / "config.toml"

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
            sources: list[PydanticBaseSettingsSource] = [env_settings]
            if toml_path.exists():
                sources.append(TomlConfigSettingsSource(settings_cls, toml_file=toml_path))
            sources.append(init_settings)
            return tuple(sources)

    try:
        return _Config()
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc
