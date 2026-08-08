import pytest
from pydantic import ValidationError

from context_anchor.planner import DeterministicPlanner, ProviderPlanner, plan_from_structured


class FakeProvider:
    def generate_plan(self, objective: str) -> dict:
        assert objective == "abra o site"
        return {"action": "open_url", "target": "https://example.com"}


def test_deterministic_planner_preserves_current_behavior() -> None:
    plan = DeterministicPlanner().plan("pesquisar FastAPI")
    assert plan.action == "open_url"
    assert "duckduckgo.com" in plan.target


def test_structured_plan_accepts_known_action() -> None:
    plan = plan_from_structured({"action": "move_mouse", "target": "100,200"})
    assert plan.action == "move_mouse"
    assert plan.target == "100,200"


def test_structured_plan_rejects_shell_action() -> None:
    with pytest.raises(ValidationError):
        plan_from_structured({"action": "shell", "target": "rm -rf /"})


def test_structured_plan_rejects_extra_tool_fields() -> None:
    with pytest.raises(ValidationError):
        plan_from_structured(
            {
                "action": "open_url",
                "target": "https://example.com",
                "command": "curl example.com",
            }
        )


def test_provider_adapter_returns_same_internal_plan() -> None:
    plan = ProviderPlanner(FakeProvider()).plan("abra o site")
    assert plan.action == "open_url"
    assert plan.target == "https://example.com"
