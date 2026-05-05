"""Operator protocol — Operator, PlannerClient, GrounderClient, ActionPlan."""

import dataclasses
from typing import Literal, Protocol


class MalformedPlannerOutputError(Exception):
    """Raised when the planner returns malformed output twice consecutively.

    Orchestration translates this to stuck_reason='malformed_planner_output'.
    """


ActionType = Literal["click", "type", "key", "screenshot"]


@dataclasses.dataclass
class ActionPlan:
    """Output of one planner step.

    Invariants enforced in __post_init__:
    - done=True requires done_reason.
    - done_reason set requires summary.
    - At most one of target_description, text, key may be set.
    """

    action_type: ActionType
    target_description: str | None = dataclasses.field(default=None)
    text: str | None = dataclasses.field(default=None)
    key: str | None = dataclasses.field(default=None)
    note: str | None = dataclasses.field(default=None)
    done: bool = dataclasses.field(default=False)
    done_reason: Literal["goal_complete", "handoff"] | None = dataclasses.field(default=None)
    summary: str | None = dataclasses.field(default=None)

    def __post_init__(self) -> None:
        if self.done and self.done_reason is None:
            raise ValueError("done=True requires done_reason")
        if self.done_reason is not None and self.summary is None:
            raise ValueError(f"done_reason='{self.done_reason}' requires summary")
        set_names = [
            name
            for name, val in (
                ("target_description", self.target_description),
                ("text", self.text),
                ("key", self.key),
            )
            if val is not None
        ]
        if len(set_names) > 1:
            raise ValueError(f"Mutually exclusive fields: {', '.join(set_names)}")


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
    async def ground(
        self,
        screenshot: bytes,
        target_description: str,
    ) -> tuple[int, int]: ...


class StubGrounderClient:
    """Dev/test stub that always returns a fixed coordinate."""

    async def ground(
        self,
        screenshot: bytes,
        target_description: str,
    ) -> tuple[int, int]:
        return (100, 100)


class Operator:
    """Composes a PlannerClient and GrounderClient behind one interface.

    Orchestration never imports a vendor SDK directly; it receives an Operator
    via dependency injection from build_operator().
    """

    def __init__(self, planner: PlannerClient, grounder: GrounderClient) -> None:
        self._planner = planner
        self._grounder = grounder

    async def plan(
        self,
        screenshot: bytes,
        goal: str,
        scenario: str = "",
        action_history: list[str] | None = None,
        notes: list[str] | None = None,
    ) -> ActionPlan:
        return await self._planner.plan(
            screenshot,
            goal,
            scenario,
            action_history if action_history is not None else [],
            notes if notes is not None else [],
        )

    async def ground(
        self,
        screenshot: bytes,
        target_description: str,
    ) -> tuple[int, int]:
        return await self._grounder.ground(screenshot, target_description)
