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


def test_desktop_is_disabled_by_default() -> None:
    plan = plan_command("capturar tela")
    decision = evaluate_plan(plan)
    assert plan.action == "capture_screen"
    assert decision.allowed is False


def test_desktop_capture_allowed_when_enabled() -> None:
    decision = evaluate_plan(plan_command("capturar tela"), desktop_enabled=True)
    assert decision.allowed is True


def test_plan_mouse_move() -> None:
    plan = plan_command("mover mouse 120 350")
    assert plan.action == "move_mouse"
    assert plan.target == "120,350"
    assert evaluate_plan(plan, desktop_enabled=True).allowed is True


def test_plan_type_text_does_not_allow_newline() -> None:
    plan = plan_command("digitar hello\nworld")
    assert evaluate_plan(plan, desktop_enabled=True).allowed is False


def test_open_app_uses_fixed_allowlist() -> None:
    allowed = plan_command("abrir aplicativo firefox")
    denied = plan_command("abrir aplicativo bash")
    assert evaluate_plan(allowed, desktop_enabled=True).allowed is True
    assert evaluate_plan(denied, desktop_enabled=True).allowed is False


def test_key_allowlist() -> None:
    assert evaluate_plan(plan_command("tecla enter"), desktop_enabled=True).allowed is True
    assert evaluate_plan(plan_command("tecla delete"), desktop_enabled=True).allowed is False


def test_unknown_command_is_rejected() -> None:
    with pytest.raises(ValueError):
        plan_command("apague todos os arquivos")
