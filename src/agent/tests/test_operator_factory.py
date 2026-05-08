"""Tests for operator.factory — build_operator wiring."""

from pathlib import Path

import pytest

from agent.config import load_config
from agent.operator.factory import build_operator
from agent.operator.nemotron_planner import NemotronPlannerClient
from agent.operator.protocol import Operator, StubGrounderClient

_NVIDIA_STUB_TOML = """\
[planner]
provider = "nvidia"
model = "nemotron-3-nano-omni-30b-a3b-reasoning"
base_url = "https://integrate.api.nvidia.com/v1"

[grounder]
provider = "stub"
"""


def _config_file(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.toml"
    p.write_text(content)
    return p


def test_nvidia_planner_with_stub_grounder(tmp_path: Path) -> None:
    cfg = load_config(_config_file(tmp_path, _NVIDIA_STUB_TOML))
    op = build_operator(cfg)
    assert isinstance(op, Operator)
    assert isinstance(op._planner, NemotronPlannerClient)
    assert isinstance(op._grounder, StubGrounderClient)


def test_unknown_planner_provider_raises(tmp_path: Path) -> None:
    toml = _NVIDIA_STUB_TOML.replace('provider = "nvidia"', 'provider = "unknown_provider"')
    cfg = load_config(_config_file(tmp_path, toml))
    with pytest.raises(ValueError, match="planner provider"):
        build_operator(cfg)


def test_unknown_grounder_provider_raises(tmp_path: Path) -> None:
    toml = _NVIDIA_STUB_TOML.replace('provider = "stub"', 'provider = "unknown_grounder"')
    cfg = load_config(_config_file(tmp_path, toml))
    with pytest.raises(ValueError, match="grounder provider"):
        build_operator(cfg)
