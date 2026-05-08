"""Vendor-neutral protocols and types for Layer 2 (model layer)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


ActionType = Literal[
    "click",
    "double_click",
    "right_click",
    "type",
    "key",
    "scroll",
    "screenshot",
    "sleep",
    "done",
]


class MalformedPlannerOutputError(Exception):
    """Raised when the planner emits unparseable output twice consecutively.

    Orchestration maps this to stuck_reason='malformed_planner_output'.
    """


@dataclass
class ActionPlan:
    """Single-step action emitted by the planner."""

    action_type: ActionType
    target_description: str | None = None
    text: str | None = None
    key: str | None = None
    note: str | None = None
    done: bool = False
    done_reason: Literal["goal_complete", "handoff"] | None = None
    summary: str | None = None

    def __post_init__(self) -> None:
        if self.done and self.done_reason is None:
            raise ValueError("done=True requires done_reason")
        if self.done_reason in ("goal_complete", "handoff") and self.summary is None:
            raise ValueError(f"done_reason='{self.done_reason}' requires summary")
        exclusive = [f for f in (self.target_description, self.text, self.key) if f is not None]
        if len(exclusive) > 1:
            raise ValueError("target_description, text, and key are mutually exclusive")


@dataclass
class Coordinates:
    x: int
    y: int


class PlannerClient(Protocol):
    async def plan(
        self,
        screenshot: bytes,
        goal: str,
        scenario: str,
        action_history: list[str],
        notes: list[str],
    ) -> ActionPlan: ...


class GrounderClient(Protocol):
    async def ground(self, screenshot: bytes, target_description: str) -> Coordinates: ...


class Operator:
    """Composes a PlannerClient and GrounderClient into a single interface."""

    def __init__(self, planner: PlannerClient, grounder: GrounderClient) -> None:
        self._planner = planner
        self._grounder = grounder

    async def propose_action(
        self,
        screenshot: bytes,
        goal: str,
        scenario: str,
        action_history: list[str],
        notes: list[str],
    ) -> ActionPlan:
        return await self._planner.plan(screenshot, goal, scenario, action_history, notes)

    async def ground(self, screenshot: bytes, target_description: str) -> Coordinates:
        return await self._grounder.ground(screenshot, target_description)


class StubGrounderClient:
    """Fixed-coordinate grounder for dev/test — returns (640, 400) for every request."""

    async def ground(self, screenshot: bytes, target_description: str) -> Coordinates:
        return Coordinates(x=640, y=400)
