"""Tests for operator.factory.build_operator wiring."""

from pathlib import Path

import pytest

from agent.config import Config, load_config
from agent.operator.factory import build_operator
from agent.operator.nemotron_planner import NemotronPlannerClient
from agent.operator.protocol import Operator, StubGrounderClient

_NVIDIA_TOML = """\
[planner]
provider = "nvidia"
model = "nemotron-3-nano-omni-30b-a3b-reasoning"
base_url = "https://integrate.api.nvidia.com/v1"

[grounder]
provider = "mlx_local"
"""


def _load(tmp_path: Path, content: str) -> Config:
    p = tmp_path / "config.toml"
    p.write_text(content)
    return load_config(p)


def test_build_operator_returns_operator_instance(tmp_path: Path) -> None:
    cfg = _load(tmp_path, _NVIDIA_TOML)
    op = build_operator(cfg)
    assert isinstance(op, Operator)


def test_nvidia_provider_wires_nemotron_planner(tmp_path: Path) -> None:
    cfg = _load(tmp_path, _NVIDIA_TOML)
    op = build_operator(cfg)
    assert isinstance(op._planner, NemotronPlannerClient)


def test_grounder_is_stub_for_mlx_local(tmp_path: Path) -> None:
    cfg = _load(tmp_path, _NVIDIA_TOML)
    op = build_operator(cfg)
    assert isinstance(op._grounder, StubGrounderClient)


def test_unknown_planner_provider_raises(tmp_path: Path) -> None:
    toml = """\
[planner]
provider = "unknown_provider"
model = "some-model"
base_url = "http://localhost"

[grounder]
provider = "mlx_local"
"""
    cfg = _load(tmp_path, toml)
    with pytest.raises(ValueError, match="Unknown planner provider"):
        build_operator(cfg)


def test_nvidia_api_key_passed_to_planner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key-abc")
    cfg = _load(tmp_path, _NVIDIA_TOML)
    op = build_operator(cfg)
    assert isinstance(op._planner, NemotronPlannerClient)
    assert op._planner._api_key == "test-key-abc"
