from __future__ import annotations

import pytest

from context_anchor.local_agent import execute_command
from context_anchor.planner import DeterministicPlanner
from context_anchor.policy import Plan


class ScriptedPlanner:
    provider_names = ("gemini",)

    def __init__(self, plans: list[Plan]) -> None:
        self.plans = list(plans)
        self.calls: list[str] = []
        self.last_provider = "gemini"
        self.last_route = "fast"
        self.last_errors: dict[str, str] = {}

    def plan(self, objective: str) -> Plan:
        self.calls.append(objective)
        if not self.plans:
            raise AssertionError("planner chamado além do roteiro do teste")
        self.last_provider = "gemini"
        self.last_route = "fast"
        self.last_errors = {}
        return self.plans.pop(0)


class FakeExecutor:
    desktop_enabled = True

    def __init__(self, *, fail_verification_on: str | None = None) -> None:
        self.executed: list[Plan] = []
        self.fail_verification_on = fail_verification_on

    def execute(self, plan: Plan) -> dict:
        self.executed.append(plan)
        verified = plan.action != self.fail_verification_on
        if plan.action == "open_app":
            return {
                "action": "open_app",
                "app": plan.target,
                "executable": "/usr/bin/xed",
                "window_id": "200",
                "window_title": "Documento não-salvo 1",
                "window_changed": True,
                "verified": verified,
            }
        if plan.action == "type_text":
            return {
                "action": "type_text",
                "characters": len(plan.target),
                "window_id": "200",
                "window_title": "Documento não-salvo 1",
                "verified": verified,
            }
        return {"action": plan.action, "verified": verified}


def test_ai_goal_loop_continues_until_finish() -> None:
    planner = ScriptedPlanner(
        [
            Plan("open_app", "editor"),
            Plan("type_text", "Olá mundo"),
            Plan("finish", "Editor aberto e texto digitado."),
        ]
    )
    executor = FakeExecutor()
    objective = "Analise o objetivo e use o editor conforme necessário"

    result = execute_command(
        executor,
        objective,
        planner=planner,
        max_goal_steps=5,
    )

    assert [plan.action for plan in executor.executed] == ["open_app", "type_text"]
    assert result["goal_completed"] is True
    assert result["verified"] is True
    assert len(result["steps"]) == 2
    assert result["steps"][0]["action"] == "open_app"
    assert result["steps"][1]["action"] == "type_text"
    assert result["planner_provider"] == "gemini"
    assert len(planner.calls) == 3
    assert planner.calls[0] == objective
    assert "OBJETIVO ORIGINAL" in planner.calls[1]
    assert "open_app" in planner.calls[1]
    assert "type_text" in planner.calls[2]


def test_known_compound_goal_runs_without_provider_calls() -> None:
    planner = ScriptedPlanner([])
    executor = FakeExecutor()

    result = execute_command(
        executor,
        "Abra o editor de texto e escreva Olá mundo",
        planner=planner,
        max_goal_steps=5,
    )

    assert planner.calls == []
    assert executor.executed == [
        Plan("open_app", "editor"),
        Plan("type_text", "Olá mundo"),
    ]
    assert result["goal_completed"] is True
    assert result["verified"] is True
    assert result["planner_provider"] == "deterministic"
    assert result["planner_route"] == "local-sequence"
    assert len(result["steps"]) == 2


def test_ai_goal_loop_refuses_false_success_when_step_is_not_verified() -> None:
    planner = ScriptedPlanner(
        [
            Plan("open_app", "editor"),
            Plan("finish", "feito"),
        ]
    )
    executor = FakeExecutor(fail_verification_on="open_app")

    with pytest.raises(RuntimeError, match="não foi verificada"):
        execute_command(
            executor,
            "Analise e abra o editor se necessário",
            planner=planner,
            max_goal_steps=5,
        )

    assert len(executor.executed) == 1
    assert len(planner.calls) == 1


def test_ai_goal_loop_stops_when_step_limit_is_exhausted() -> None:
    planner = ScriptedPlanner(
        [
            Plan("open_app", "editor"),
            Plan("type_text", "ainda falta"),
        ]
    )
    executor = FakeExecutor()

    with pytest.raises(RuntimeError, match="limite de 1 etapas"):
        execute_command(
            executor,
            "Faça várias coisas",
            planner=planner,
            max_goal_steps=1,
        )

    assert [plan.action for plan in executor.executed] == ["open_app"]


def test_deterministic_command_keeps_single_step_behavior() -> None:
    executor = FakeExecutor()

    result = execute_command(
        executor,
        "digitar teste",
        planner=DeterministicPlanner(),
    )

    assert [plan.action for plan in executor.executed] == ["type_text"]
    assert result["verified"] is True
