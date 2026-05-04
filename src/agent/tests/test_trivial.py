"""Smoke test: the package and all sub-packages can be imported."""

import agent
import agent.action
import agent.observability
import agent.operator
import agent.orchestration
import agent.safety
import agent.scenarios


def test_package_importable() -> None:
    assert agent is not None


def test_sub_packages_importable() -> None:
    for mod in (
        agent.orchestration,
        agent.operator,
        agent.action,
        agent.scenarios,
        agent.safety,
        agent.observability,
    ):
        assert mod is not None
