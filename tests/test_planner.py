import pytest
from pydantic import ValidationError

from context_anchor.planner import (
    DeterministicPlanner,
    MultiProviderPlanner,
    ProviderCandidate,
    ProviderPlanner,
    plan_from_structured,
)
from context_anchor.policy import evaluate_plan


class FakeProvider:
    def __init__(self, payload: dict | None = None, *, error: Exception | None = None) -> None:
        self.payload = payload or {"action": "open_url", "target": "https://example.com"}
        self.error = error
        self.calls: list[str] = []

    def generate_plan(self, objective: str) -> dict:
        self.calls.append(objective)
        if self.error:
            raise self.error
        return self.payload


def test_deterministic_planner_preserves_current_behavior() -> None:
    plan = DeterministicPlanner().plan("pesquisar FastAPI")
    assert plan.action == "open_url"
    assert "duckduckgo.com" in plan.target


def test_structured_plan_accepts_known_action() -> None:
    plan = plan_from_structured({"action": "move_mouse", "target": "100,200"})
    assert plan.action == "move_mouse"
    assert plan.target == "100,200"


@pytest.mark.parametrize(
    "alias",
    ["editor de texto", "text editor", "text_editor", "xed", "gedit", "notepad"],
)
def test_structured_open_app_normalizes_editor_alias(alias: str) -> None:
    plan = plan_from_structured({"action": "open_app", "target": alias})

    assert plan.target == "editor"
    assert evaluate_plan(plan, desktop_enabled=True).allowed is True


@pytest.mark.parametrize(
    "target",
    ["brave-browser", "/usr/bin/xed", "xed --new-window", "bash"],
)
def test_structured_open_app_is_not_blocked_by_registration(target: str) -> None:
    plan = plan_from_structured({"action": "open_app", "target": target})
    assert evaluate_plan(plan, desktop_enabled=True).allowed is True


def test_structured_finish_action_is_valid() -> None:
    plan = plan_from_structured({"action": "finish", "target": "objetivo integralmente concluído"})
    assert plan.action == "finish"


def test_structured_plan_rejects_unknown_action_type() -> None:
    with pytest.raises(ValidationError):
        plan_from_structured({"action": "acao_inexistente", "target": "qualquer coisa"})


def test_structured_plan_rejects_extra_tool_fields() -> None:
    with pytest.raises(ValidationError):
        plan_from_structured(
            {
                "action": "open_url",
                "target": "https://example.com",
                "command": "campo extra",
            }
        )


def test_provider_adapter_returns_same_internal_plan() -> None:
    provider = FakeProvider()
    plan = ProviderPlanner(provider).plan("abra o site")
    assert plan.action == "open_url"
    assert plan.target == "https://example.com"


def test_multi_provider_keeps_known_commands_local_without_api_call() -> None:
    cloudflare = FakeProvider()
    router = MultiProviderPlanner(
        [
            ProviderCandidate(
                name="cloudflare",
                provider=cloudflare,
                roles=frozenset({"fast", "reasoning"}),
                rpm_limit=300,
            )
        ]
    )

    plan = router.plan("pesquisar FastAPI")

    assert plan.action == "open_url"
    assert router.last_provider == "deterministic"
    assert cloudflare.calls == []


def test_multi_provider_routes_non_url_open_phrase_to_ai() -> None:
    gemini = FakeProvider({"action": "open_app", "target": "brave"})
    router = MultiProviderPlanner(
        [ProviderCandidate("gemini", gemini, frozenset({"fast", "reasoning"}), 20)]
    )

    plan = router.plan("abrir o navegador brave")

    assert plan.action == "open_app"
    assert plan.target == "brave-browser"
    assert router.last_provider == "gemini"
    assert gemini.calls == ["abrir o navegador brave"]


def test_multi_provider_routes_simple_natural_language_to_cloudflare_first() -> None:
    cloudflare = FakeProvider({"action": "open_app", "target": "editor"})
    zai = FakeProvider({"action": "open_app", "target": "editor"})
    router = MultiProviderPlanner(
        [
            ProviderCandidate("zai", zai, frozenset({"fast", "reasoning"})),
            ProviderCandidate("cloudflare", cloudflare, frozenset({"fast", "reasoning"}), 300),
        ]
    )

    plan = router.plan("Por favor abra o editor de texto para mim")

    assert plan.action == "open_app"
    assert router.last_provider == "cloudflare"
    assert cloudflare.calls == ["Por favor abra o editor de texto para mim"]
    assert zai.calls == []


def test_multi_provider_routes_conditional_request_to_zai_first() -> None:
    zai = FakeProvider({"action": "open_url", "target": "https://example.com"})
    cloudflare = FakeProvider({"action": "open_url", "target": "https://fallback.example.com"})
    router = MultiProviderPlanner(
        [
            ProviderCandidate("cloudflare", cloudflare, frozenset({"fast", "reasoning"}), 300),
            ProviderCandidate("zai", zai, frozenset({"fast", "reasoning"})),
        ]
    )

    router.plan("Analise a situação e decida se devemos abrir o site")

    assert router.last_route == "reasoning"
    assert router.last_provider == "zai"
    assert len(zai.calls) == 1
    assert cloudflare.calls == []


def test_multi_provider_falls_back_before_execution_when_first_provider_fails() -> None:
    cloudflare = FakeProvider(error=RuntimeError("429"))
    zai = FakeProvider({"action": "open_app", "target": "editor"})
    router = MultiProviderPlanner(
        [
            ProviderCandidate("cloudflare", cloudflare, frozenset({"fast", "reasoning"}), 300),
            ProviderCandidate("zai", zai, frozenset({"fast", "reasoning"})),
        ],
        cooldown_seconds=30,
    )

    plan = router.plan("Por favor abra o editor de texto para mim")

    assert plan.action == "open_app"
    assert router.last_provider == "zai"
    assert "cloudflare" in router.last_errors
    assert len(cloudflare.calls) == 1
    assert len(zai.calls) == 1


def test_multi_provider_falls_back_on_invalid_structured_action() -> None:
    cloudflare = FakeProvider({"action": "acao_inexistente", "target": "nope"})
    gemini = FakeProvider({"action": "open_url", "target": "https://example.com"})
    router = MultiProviderPlanner(
        [
            ProviderCandidate("cloudflare", cloudflare, frozenset({"fast", "reasoning"}), 300),
            ProviderCandidate("gemini", gemini, frozenset({"fast", "reasoning"}), 20),
        ]
    )

    plan = router.plan("Quero visitar o site de exemplo agora")

    assert plan.action == "open_url"
    assert router.last_provider == "gemini"
    assert "cloudflare" in router.last_errors
