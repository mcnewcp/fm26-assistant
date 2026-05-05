"""Optional integration tests for NemotronPlannerClient against real NVIDIA NIM.

These tests are skipped unless NVIDIA_API_KEY is set in the environment.
Run them explicitly when validating the planner against real NIM:

    NVIDIA_API_KEY=<key> uv run pytest src/agent/tests/test_operator_integration.py -v
"""

import os
import struct
import zlib

import pytest

from agent.operator.nemotron_planner import NemotronPlannerClient
from agent.operator.protocol import ActionPlan

pytestmark = pytest.mark.skipif(
    not os.environ.get("NVIDIA_API_KEY"),
    reason="NVIDIA_API_KEY not set — skipping live NIM integration tests",
)

_NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
_NIM_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"


def _minimal_png() -> bytes:
    """Build a 1×1 white PNG in memory for use as a fixture screenshot."""

    def _chunk(tag: bytes, data: bytes) -> bytes:
        payload = tag + data
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", crc)

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    idat = _chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff"))
    iend = _chunk(b"IEND", b"")
    return header + ihdr + idat + iend


@pytest.fixture
def fixture_screenshot() -> bytes:
    return _minimal_png()


async def test_nemotron_planner_returns_valid_action_plan(fixture_screenshot: bytes) -> None:
    api_key = os.environ["NVIDIA_API_KEY"]
    client = NemotronPlannerClient(
        model=_NIM_MODEL,
        base_url=_NIM_BASE_URL,
        api_key=api_key,
    )
    plan = await client.plan(
        screenshot=fixture_screenshot,
        goal="Take a screenshot to observe the current screen state.",
        scenario="",
        action_history=[],
        notes=[],
    )
    assert isinstance(plan, ActionPlan)
    assert plan.action_type in ("click", "type", "key", "screenshot")
    if plan.done:
        assert plan.done_reason is not None
        assert plan.summary is not None
