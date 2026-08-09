import pytest

from context_anchor.policy import Plan, evaluate_plan, plan_command


def test_plan_search() -> None:
    plan = plan_command("pesquisar FastAPI agentes")
    assert plan.action == "open_url"
    assert "duckduckgo.com" in plan.target
    assert "FastAPI+agentes" in plan.target


def test_plan_open_adds_https() -> None:
    plan = plan_command("abrir example.com")
    assert plan.target == "https://example.com"


def test_deterministic_open_only_claims_targets_that_look_like_urls() -> None:
    with pytest.raises(ValueError, match="não parece uma URL"):
        plan_command("abrir o navegador brave")


def test_policy_allows_localhost_in_trusted_local_profile() -> None:
    plan = plan_command("abrir http://localhost:8000")
    decision = evaluate_plan(plan)
    assert decision.allowed is True


def test_policy_allows_private_ip_in_trusted_local_profile() -> None:
    plan = plan_command("abrir http://192.168.1.10")
    decision = evaluate_plan(plan)
    assert decision.allowed is True


def test_policy_allows_public_https() -> None:
    plan = plan_command("abrir https://example.com")
    decision = evaluate_plan(plan)
    assert decision.allowed is True


def test_desktop_is_disabled_when_explicitly_off() -> None:
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


def test_open_app_is_permitted_without_registration() -> None:
    brave = Plan("open_app", "brave-browser")
    custom = Plan("open_app", "meu-aplicativo-local")
    assert evaluate_plan(brave, desktop_enabled=True).allowed is True
    assert evaluate_plan(custom, desktop_enabled=True).allowed is True


def test_press_key_is_permissive_for_printable_key_names() -> None:
    assert evaluate_plan(plan_command("tecla enter"), desktop_enabled=True).allowed is True
    assert evaluate_plan(plan_command("tecla delete"), desktop_enabled=True).allowed is True


def test_finish_is_internal_and_allowed() -> None:
    assert evaluate_plan(Plan("finish", "objetivo concluído"), desktop_enabled=True).allowed is True


def test_unknown_command_is_rejected_by_deterministic_parser() -> None:
    with pytest.raises(ValueError):
        plan_command("apague todos os arquivos")
