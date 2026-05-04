"""Tests for agent.config — TDD: written before the implementation."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.config import Config, load_config

# Minimal TOML that satisfies all required fields.
_MINIMAL_TOML = """\
[planner]
provider = "nvidia"
model = "nemotron-3-nano-omni-30b-a3b-reasoning"
base_url = "https://integrate.api.nvidia.com/v1"

[grounder]
provider = "mlx_local"
"""


def _cfg_file(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.toml"
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# 1. Loading values from TOML
# ---------------------------------------------------------------------------


def test_loads_planner_from_toml(tmp_path: Path) -> None:
    cfg = load_config(_cfg_file(tmp_path, _MINIMAL_TOML))
    assert cfg.planner.provider == "nvidia"
    assert cfg.planner.model == "nemotron-3-nano-omni-30b-a3b-reasoning"
    assert cfg.planner.base_url == "https://integrate.api.nvidia.com/v1"


def test_loads_non_default_orchestration_from_toml(tmp_path: Path) -> None:
    content = _MINIMAL_TOML + "\n[orchestration]\nmax_steps = 25\n"
    cfg = load_config(_cfg_file(tmp_path, content))
    assert cfg.orchestration.max_steps == 25


def test_loads_grounder_from_toml(tmp_path: Path) -> None:
    content = """\
[planner]
provider = "nvidia"
model = "nemotron-3-nano-omni-30b-a3b-reasoning"
base_url = "https://integrate.api.nvidia.com/v1"

[grounder]
provider = "mlx_local"
server_url = "http://localhost:9090/v1"
"""
    cfg = load_config(_cfg_file(tmp_path, content))
    assert cfg.grounder.server_url == "http://localhost:9090/v1"


# ---------------------------------------------------------------------------
# 2. Env-var overrides take precedence over TOML
# ---------------------------------------------------------------------------


def test_env_var_overrides_toml_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    content = _MINIMAL_TOML + '\nnvidia_api_key = "from_toml"\n'
    monkeypatch.setenv("NVIDIA_API_KEY", "from_env")
    cfg = load_config(_cfg_file(tmp_path, content))
    assert cfg.nvidia_api_key == "from_env"


def test_env_var_overrides_nested_toml_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = _MINIMAL_TOML + "\n[orchestration]\nmax_steps = 10\n"
    monkeypatch.setenv("ORCHESTRATION__MAX_STEPS", "99")
    cfg = load_config(_cfg_file(tmp_path, content))
    assert cfg.orchestration.max_steps == 99


# ---------------------------------------------------------------------------
# 3. Defaults applied where the PRD specifies them
# ---------------------------------------------------------------------------


def test_default_max_steps(tmp_path: Path) -> None:
    cfg = load_config(_cfg_file(tmp_path, _MINIMAL_TOML))
    assert cfg.orchestration.max_steps == 50


def test_default_scenarios_directory(tmp_path: Path) -> None:
    cfg = load_config(_cfg_file(tmp_path, _MINIMAL_TOML))
    assert cfg.scenarios.directory == "scenarios"


def test_default_sessions_dir(tmp_path: Path) -> None:
    cfg = load_config(_cfg_file(tmp_path, _MINIMAL_TOML))
    assert cfg.observability.sessions_dir == "runs"


def test_default_mcp_server(tmp_path: Path) -> None:
    cfg = load_config(_cfg_file(tmp_path, _MINIMAL_TOML))
    assert cfg.action.mcp_server == "computer-control-mcp"


def test_default_nvidia_api_key_is_empty(tmp_path: Path) -> None:
    cfg = load_config(_cfg_file(tmp_path, _MINIMAL_TOML))
    assert cfg.nvidia_api_key == ""


# ---------------------------------------------------------------------------
# 4. Clear typed error when a required field is missing
# ---------------------------------------------------------------------------


def test_missing_planner_raises_validation_error(tmp_path: Path) -> None:
    cfg_path = _cfg_file(tmp_path, "")  # no [planner] section
    with pytest.raises(ValidationError):
        load_config(cfg_path)


def test_missing_planner_model_raises_validation_error(tmp_path: Path) -> None:
    content = "[planner]\nprovider = \"nvidia\"\nbase_url = \"https://example.com\"\n"
    with pytest.raises(ValidationError):
        load_config(_cfg_file(tmp_path, content))


def test_missing_grounder_raises_validation_error(tmp_path: Path) -> None:
    content = "[planner]\nprovider = \"nvidia\"\nmodel = \"m\"\nbase_url = \"https://example.com\"\n"
    with pytest.raises(ValidationError):
        load_config(_cfg_file(tmp_path, content))


def test_error_is_not_key_or_attribute_error(tmp_path: Path) -> None:
    cfg_path = _cfg_file(tmp_path, "")
    with pytest.raises(Exception) as exc_info:
        load_config(cfg_path)
    assert not isinstance(exc_info.value, (KeyError, AttributeError))


# ---------------------------------------------------------------------------
# 5. Config is importable and correctly typed
# ---------------------------------------------------------------------------


def test_load_config_returns_config_instance(tmp_path: Path) -> None:
    cfg = load_config(_cfg_file(tmp_path, _MINIMAL_TOML))
    assert isinstance(cfg, Config)
