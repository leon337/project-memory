import pytest

from context_anchor.policy import evaluate_plan, plan_command


def test_plan_search() -> None:
    plan = plan_command("pesquisar FastAPI agentes")
    assert plan.action == "open_url"
    assert "duckduckgo.com" in plan.target
    assert "FastAPI+agentes" in plan.target


def test_plan_open_adds_https() -> None:
    plan = plan_command("abrir example.com")
    assert plan.target == "https://example.com"


def test_policy_blocks_localhost() -> None:
    plan = plan_command("abrir http://localhost:8000")
    decision = evaluate_plan(plan)
    assert decision.allowed is False


def test_policy_blocks_private_ip() -> None:
    plan = plan_command("abrir http://192.168.1.10")
    decision = evaluate_plan(plan)
    assert decision.allowed is False


def test_policy_allows_public_https() -> None:
    plan = plan_command("abrir https://example.com")
    decision = evaluate_plan(plan)
    assert decision.allowed is True


def test_unknown_command_is_rejected() -> None:
    with pytest.raises(ValueError):
        plan_command("apague todos os arquivos")
