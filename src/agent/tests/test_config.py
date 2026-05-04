"""Tests for agent.config — TDD: written before the implementation."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.config import load_config

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


def test_loads_values_from_toml(tmp_path: Path) -> None:
    content = _MINIMAL_TOML + "\n[orchestration]\nmax_steps = 25\n"
    cfg = load_config(_cfg_file(tmp_path, content))
    assert cfg.planner.provider == "nvidia"
    assert cfg.planner.model == "nemotron-3-nano-omni-30b-a3b-reasoning"
    assert cfg.planner.base_url == "https://integrate.api.nvidia.com/v1"
    assert cfg.grounder.provider == "mlx_local"
    assert cfg.orchestration.max_steps == 25


def test_env_var_overrides_top_level_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = _MINIMAL_TOML + '\nnvidia_api_key = "from_toml"\n'
    monkeypatch.setenv("NVIDIA_API_KEY", "from_env")
    cfg = load_config(_cfg_file(tmp_path, content))
    assert cfg.nvidia_api_key == "from_env"


def test_env_var_overrides_nested_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The `__` delimiter is the only non-trivial precedence path; if this works,
    # top-level overrides also work.
    content = _MINIMAL_TOML + "\n[orchestration]\nmax_steps = 10\n"
    monkeypatch.setenv("ORCHESTRATION__MAX_STEPS", "99")
    cfg = load_config(_cfg_file(tmp_path, content))
    assert cfg.orchestration.max_steps == 99


def test_defaults_apply_when_toml_omits_them(tmp_path: Path) -> None:
    cfg = load_config(_cfg_file(tmp_path, _MINIMAL_TOML))
    assert cfg.orchestration.max_steps == 50
    assert cfg.orchestration.screenshot_history_size == 3
    assert cfg.scenarios.directory == "scenarios"
    assert cfg.observability.sessions_dir == "runs"
    assert cfg.action.mcp_server == "computer-control-mcp"
    assert cfg.nvidia_api_key == ""


def test_missing_required_field_raises_validation_error(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        load_config(_cfg_file(tmp_path, ""))
