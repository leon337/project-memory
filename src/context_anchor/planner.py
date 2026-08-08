from __future__ import annotations

from typing import Any, Literal, Mapping, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .policy import Plan, plan_command

ActionName = Literal[
    "open_url",
    "capture_screen",
    "active_window",
    "move_mouse",
    "click_mouse",
    "type_text",
    "press_key",
    "open_app",
]


class StructuredAction(BaseModel):
    """Provider-neutral action contract.

    Model output is intentionally small: no shell, executable path, Python code,
    credentials or free-form tool calls are part of this schema.
    """

    model_config = ConfigDict(extra="forbid")

    action: ActionName
    target: str = Field(min_length=1, max_length=500)


class Planner(Protocol):
    def plan(self, objective: str) -> Plan: ...


class StructuredPlanProvider(Protocol):
    def generate_plan(self, objective: str) -> Mapping[str, Any]: ...


class DeterministicPlanner:
    def plan(self, objective: str) -> Plan:
        return plan_command(objective)


def plan_from_structured(payload: Mapping[str, Any]) -> Plan:
    parsed = StructuredAction.model_validate(payload)
    return Plan(action=parsed.action, target=parsed.target)


class ProviderPlanner:
    """Adapts a future model provider to the same Plan used by the executor.

    The provider can only return the StructuredAction schema. Policy evaluation
    still happens after planning, so valid syntax does not imply permission.
    """

    def __init__(self, provider: StructuredPlanProvider) -> None:
        self.provider = provider

    def plan(self, objective: str) -> Plan:
        payload = self.provider.generate_plan(objective)
        return plan_from_structured(payload)
