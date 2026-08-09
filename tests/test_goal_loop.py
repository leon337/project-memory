from __future__ import annotations

import pytest

from context_anchor.capabilities import ResolvedCapability
from context_anchor.goal_execution import GoalExecutionFailed
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
        self.active_app: str | None = None
        self.active_text = ""

    def execute(self, plan: Plan) -> dict:
        self.executed.append(plan)
        verified = plan.action != self.fail_verification_on
        if plan.action == "open_app":
            self.active_app = "editor"
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
            self.active_text += plan.target
            return {
                "action": "type_text",
                "characters": len(plan.target),
                "window_id": "200",
                "window_title": "Documento não-salvo 1",
                "verified": verified,
            }
        return {"action": plan.action, "verified": verified}

    def observe_application(
        self,
        app_id: str,
        *,
        pid: int | None = None,
        expected_argument: str | None = None,
    ) -> dict:
        verified = self.active_app is not None and self.fail_verification_on != "open_app"
        return {
            "action": "observe_application",
            "app": self.active_app,
            "identity_observed": verified,
            "class_identity_observed": verified,
            "process_identity_observed": verified,
            "argument_observed": expected_argument is not None,
            "window_id": "200" if verified else None,
            "window_title": "Documento não-salvo 1" if verified else None,
            "window_class": "xed.Xed" if verified else None,
            "verified": verified,
        }

    def read_active_text(self, *, max_chars: int = 4096) -> dict:
        verified = self.fail_verification_on != "type_text"
        return {
            "action": "read_active_text",
            "text": self.active_text[:max_chars],
            "characters": len(self.active_text),
            "source": "fake-independent-readback",
            "clipboard_restored": True,
            "verified": verified,
        }


class FakeCapabilityResolver:
    def resolve(self, capability: str, hint: str | None = None) -> ResolvedCapability:
        return ResolvedCapability(
            capability=capability,
            app_id="editor",
            display_name="Fake Editor",
            executable="/usr/bin/xed",
            source="test",
        )


def test_legacy_ai_action_loop_cannot_define_its_own_goal_contract() -> None:
    planner = ScriptedPlanner(
        [
            Plan("open_app", "editor"),
            Plan("type_text", "Olá mundo"),
            Plan("finish", "Editor aberto e texto digitado."),
        ]
    )
    executor = FakeExecutor()
    objective = "Analise o objetivo e use o editor conforme necessário"

    with pytest.raises(GoalExecutionFailed, match="decomposição estruturada"):
        execute_command(
            executor,
            objective,
            planner=planner,
            max_goal_steps=5,
            capability_resolver=FakeCapabilityResolver(),
        )

    assert executor.executed == []
    assert planner.calls == []


def test_known_compound_goal_runs_without_provider_calls() -> None:
    planner = ScriptedPlanner([])
    executor = FakeExecutor()

    result = execute_command(
        executor,
        "Abra o editor de texto e escreva Olá mundo",
        planner=planner,
        max_goal_steps=5,
        capability_resolver=FakeCapabilityResolver(),
    )

    assert planner.calls == []
    assert executor.executed == [
        Plan("open_app", "/usr/bin/xed"),
        Plan("type_text", "Olá mundo"),
    ]
    assert result["goal_completed"] is True
    assert result["verified"] is True
    assert result["planner_provider"] == "deterministic"
    assert result["planner_route"] == "goal-runtime"
    assert len(result["steps"]) == 2


def test_ai_goal_loop_refuses_false_success_when_step_is_not_verified() -> None:
    planner = ScriptedPlanner(
        [
            Plan("open_app", "editor"),
            Plan("finish", "feito"),
        ]
    )
    executor = FakeExecutor(fail_verification_on="open_app")

    with pytest.raises(GoalExecutionFailed, match="decomposição estruturada"):
        execute_command(
            executor,
            "Analise e abra o editor se necessário",
            planner=planner,
            max_goal_steps=5,
            capability_resolver=FakeCapabilityResolver(),
        )

    assert executor.executed == []
    assert planner.calls == []


def test_ai_goal_loop_stops_when_step_limit_is_exhausted() -> None:
    planner = ScriptedPlanner(
        [
            Plan("open_app", "editor"),
            Plan("type_text", "ainda falta"),
        ]
    )
    executor = FakeExecutor()

    with pytest.raises(GoalExecutionFailed, match="step budget exhausted"):
        execute_command(
            executor,
            "Abra o editor de texto e escreva ainda falta",
            planner=planner,
            max_goal_steps=1,
            capability_resolver=FakeCapabilityResolver(),
        )

    assert [plan.action for plan in executor.executed] == ["open_app"]
    assert planner.calls == []


def test_deterministic_command_keeps_single_step_behavior() -> None:
    executor = FakeExecutor()

    result = execute_command(
        executor,
        "digitar teste",
        planner=DeterministicPlanner(),
    )

    assert [plan.action for plan in executor.executed] == ["type_text"]
    assert result["verified"] is True
