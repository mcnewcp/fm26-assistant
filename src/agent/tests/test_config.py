"""Tests for config.py — TOML loading, env-var override, defaults, missing-field error."""

from pathlib import Path

import pytest

from agent.config import ConfigError, load_config


@pytest.fixture()
def minimal_toml(tmp_path: Path) -> Path:
    """Minimal valid config.toml with the required nvidia_api_key field."""
    p = tmp_path / "config.toml"
    p.write_text('nvidia_api_key = "test_key"\n')
    return p


def test_load_from_toml(minimal_toml: Path) -> None:
    """Values from TOML are loaded into the config model."""
    cfg = load_config(minimal_toml)
    assert cfg.nvidia_api_key == "test_key"


def test_toml_section_values_loaded(tmp_path: Path) -> None:
    """TOML section values override built-in defaults."""
    config_toml = tmp_path / "config.toml"
    config_toml.write_text(
        'nvidia_api_key = "k"\n\n[orchestration]\nmax_steps = 99\n'
    )
    cfg = load_config(config_toml)
    assert cfg.orchestration.max_steps == 99


def test_env_var_overrides_toml(minimal_toml: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Env var takes precedence over the same value in TOML."""
    monkeypatch.setenv("NVIDIA_API_KEY", "env_key")
    cfg = load_config(minimal_toml)
    assert cfg.nvidia_api_key == "env_key"


def test_defaults_applied(minimal_toml: Path) -> None:
    """Default values from each HLA §8 section are present when TOML omits them."""
    cfg = load_config(minimal_toml)
    assert cfg.orchestration.max_steps == 50
    assert cfg.scenarios.directory == "scenarios"
    assert cfg.observability.sessions_dir == "runs"


def test_missing_required_field_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing required field raises ConfigError, not KeyError or AttributeError."""
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    empty_toml = tmp_path / "config.toml"
    empty_toml.write_text("")
    with pytest.raises(ConfigError):
        load_config(empty_toml)
