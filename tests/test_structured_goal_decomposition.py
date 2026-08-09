from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from context_anchor.emergency_stop import EmergencyStopTriggered
from context_anchor.planner import (
    MultiProviderPlanner,
    ProviderCandidate,
    ProviderGenerationError,
    ProviderPlanner,
    StructuredGoalDecomposition,
    decomposition_from_structured,
    plan_from_goal_step,
    resolve_goal_value,
)


OBJECTIVE = (
    "Pesquise inteligência artificial e escreva o título do primeiro resultado "
    "em um editor."
)


def valid_decomposition(*, objective: str = OBJECTIVE) -> dict:
    return {
        "schema_version": "1.0",
        "objective": objective,
        "capabilities": [
            {
                "id": "web.search",
                "description": "Pesquisar e observar resultados web",
            },
            {
                "id": "text.edit",
                "description": "Editar texto em uma superfície local",
                "hint": "editor de texto",
            },
        ],
        "criteria": [
            {
                "id": "results_observed",
                "description": "Resultados reais da consulta foram observados",
                "observable": "browser.search_results",
                "evidence_kind": "observation",
                "check": "truthy",
                "expected_value": None,
                "required": True,
            },
            {
                "id": "editor_open",
                "description": "Uma superfície de edição foi observada",
                "observable": "desktop.application",
                "evidence_kind": "observation",
                "check": "truthy",
                "expected_value": None,
                "required": True,
            },
            {
                "id": "title_present",
                "description": "O título extraído está presente no editor",
                "observable": "desktop.text",
                "evidence_kind": "readback",
                "check": "equals",
                "expected_value": "{{first_result_title}}",
                "required": True,
            },
        ],
        "subgoals": [
            {
                "id": "research",
                "description": "Pesquisar e extrair o primeiro resultado",
                "capability_ids": ["web.search"],
                "criterion_ids": ["results_observed"],
                "depends_on": [],
            },
            {
                "id": "record_result",
                "description": "Abrir editor e registrar o título",
                "capability_ids": ["text.edit"],
                "criterion_ids": ["editor_open", "title_present"],
                "depends_on": ["research"],
            },
        ],
        "steps": [
            {
                "id": "search_web",
                "subgoal_id": "research",
                "capability_id": "web.search",
                "operation": "navigate",
                "target": "https://www.bing.com/search?q=inteligencia+artificial",
                "criterion_ids": ["results_observed"],
                "depends_on": [],
                "consumes": [],
                "produces": ["first_result_title"],
            },
            {
                "id": "open_editor",
                "subgoal_id": "record_result",
                "capability_id": "text.edit",
                "operation": "open_capability",
                "target": None,
                "criterion_ids": ["editor_open"],
                "depends_on": ["search_web"],
                "consumes": [],
                "produces": [],
            },
            {
                "id": "write_title",
                "subgoal_id": "record_result",
                "capability_id": "text.edit",
                "operation": "write_text",
                "target": "{{first_result_title}}",
                "criterion_ids": ["title_present"],
                "depends_on": ["search_web", "open_editor"],
                "consumes": ["first_result_title"],
                "produces": [],
            },
        ],
    }


def navigation_and_capture_decomposition(
    objective: str,
    *,
    target: str,
) -> dict:
    return {
        "schema_version": "1.0",
        "objective": objective,
        "capabilities": [
            {"id": "browser.navigate", "description": "Navegar e observar"},
            {"id": "screen.capture", "description": "Capturar a tela"},
        ],
        "criteria": [
            {
                "id": "page_observed",
                "description": "Destino observado",
                "observable": "browser.url",
                "evidence_kind": "observation",
                "check": "truthy",
                "expected_value": None,
                "required": True,
            },
            {
                "id": "screen_observed",
                "description": "Captura observada",
                "observable": "filesystem.exists",
                "evidence_kind": "observation",
                "check": "truthy",
                "expected_value": None,
                "required": True,
            },
        ],
        "subgoals": [
            {
                "id": "visit",
                "description": "Visitar destino",
                "capability_ids": ["browser.navigate"],
                "criterion_ids": ["page_observed"],
                "depends_on": [],
            },
            {
                "id": "capture",
                "description": "Capturar depois da visita",
                "capability_ids": ["screen.capture"],
                "criterion_ids": ["screen_observed"],
                "depends_on": ["visit"],
            },
        ],
        "steps": [
            {
                "id": "navigate",
                "subgoal_id": "visit",
                "capability_id": "browser.navigate",
                "operation": "navigate",
                "target": target,
                "criterion_ids": ["page_observed"],
                "depends_on": [],
                "consumes": [],
                "produces": [],
            },
            {
                "id": "capture",
                "subgoal_id": "capture",
                "capability_id": "screen.capture",
                "operation": "capture_screen",
                "target": None,
                "criterion_ids": ["screen_observed"],
                "depends_on": ["navigate"],
                "consumes": [],
                "produces": [],
            },
        ],
    }


class GoalProvider:
    name = "goal-provider"

    def __init__(
        self,
        payload: dict | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.payload = payload or valid_decomposition()
        self.error = error
        self.decomposition_calls: list[str] = []
        self.legacy_plan_calls: list[str] = []

    def generate_goal_decomposition(self, objective: str) -> dict:
        self.decomposition_calls.append(objective)
        if self.error is not None:
            raise self.error
        return self.payload

    def generate_plan(self, objective: str) -> dict:
        self.legacy_plan_calls.append(objective)
        return {"action": "finish", "target": "confie em mim"}


def test_complete_decomposition_is_validated_before_steps_are_materialized() -> None:
    decomposition = decomposition_from_structured(
        valid_decomposition(),
        expected_objective=OBJECTIVE,
    )

    assert isinstance(decomposition, StructuredGoalDecomposition)
    assert [item.id for item in decomposition.subgoals] == ["research", "record_result"]
    assert [item.id for item in decomposition.criteria] == [
        "results_observed",
        "editor_open",
        "title_present",
    ]

    navigation = plan_from_goal_step(decomposition.steps[0], desktop_enabled=True)
    assert navigation.action == "open_url"
    assert navigation.target.startswith("https://www.bing.com/search")

    with pytest.raises(ValueError, match="target resolvido"):
        plan_from_goal_step(decomposition.steps[1], desktop_enabled=True)

    editor = plan_from_goal_step(
        decomposition.steps[1],
        resolved_capability_target="xed --new-window",
        desktop_enabled=True,
    )
    assert editor.action == "open_app"
    assert editor.target == "xed --new-window"

    artifacts = {"first_result_title": "Inteligência artificial — definição"}
    write = plan_from_goal_step(
        decomposition.steps[2],
        artifacts=artifacts,
        desktop_enabled=True,
    )
    assert write.action == "type_text"
    assert write.target == artifacts["first_result_title"]
    assert resolve_goal_value(
        decomposition.criteria[2].expected_value,
        artifacts=artifacts,
    ) == artifacts["first_result_title"]


def test_decomposition_rejects_provider_that_changes_original_objective() -> None:
    with pytest.raises(ValueError, match="alterou o objetivo"):
        decomposition_from_structured(
            valid_decomposition(objective="Abra somente a busca"),
            expected_objective=OBJECTIVE,
        )


@pytest.mark.parametrize("evidence_kind", ["execution_receipt", "assertion"])
def test_provider_cannot_use_receipt_or_assertion_as_goal_evidence(
    evidence_kind: str,
) -> None:
    payload = valid_decomposition()
    payload["criteria"][0]["evidence_kind"] = evidence_kind

    with pytest.raises(ValidationError):
        decomposition_from_structured(payload, expected_objective=OBJECTIVE)


def test_single_free_action_or_finish_is_not_a_goal_decomposition() -> None:
    with pytest.raises(ValidationError):
        decomposition_from_structured(
            {"action": "finish", "target": "objetivo pronto"},
            expected_objective=OBJECTIVE,
        )


def test_every_criterion_must_exist_before_execution_and_have_one_observer_step() -> None:
    payload = valid_decomposition()
    payload["steps"][2]["criterion_ids"] = ["editor_open"]

    with pytest.raises(ValidationError, match="outro subgoal|mais de um step"):
        decomposition_from_structured(payload, expected_objective=OBJECTIVE)


def test_step_cannot_claim_an_observable_its_operation_cannot_collect() -> None:
    payload = valid_decomposition()
    payload["criteria"][0]["observable"] = "desktop.application"

    with pytest.raises(ValidationError, match="não pode observar"):
        decomposition_from_structured(payload, expected_objective=OBJECTIVE)


def test_write_text_requires_independent_exact_readback() -> None:
    payload = valid_decomposition()
    payload["criteria"][2]["check"] = "contains"

    with pytest.raises(ValidationError, match="readback equals"):
        decomposition_from_structured(payload, expected_objective=OBJECTIVE)


def test_write_text_requires_an_observed_open_surface_dependency() -> None:
    objective = "Escreva 'feito' em uma ferramenta apropriada"
    payload = valid_decomposition(objective=objective)
    payload["steps"] = [payload["steps"][2]]
    payload["steps"][0].update(
        {
            "id": "write_only",
            "subgoal_id": "record_result",
            "target": "feito",
            "criterion_ids": ["title_present"],
            "depends_on": [],
            "consumes": [],
        }
    )
    payload["criteria"] = [payload["criteria"][2]]
    payload["criteria"][0]["expected_value"] = "feito"
    payload["subgoals"] = [payload["subgoals"][1]]
    payload["subgoals"][0].update(
        {
            "depends_on": [],
            "criterion_ids": ["title_present"],
        }
    )
    payload["capabilities"] = [payload["capabilities"][1]]

    with pytest.raises(ValidationError, match="open_capability anterior"):
        decomposition_from_structured(payload, expected_objective=objective)


@pytest.mark.parametrize("invented_target", ["APAGUE TUDO", "Olá", "a"])
def test_provider_cannot_invent_or_weaken_literal_text_target(
    invented_target: str,
) -> None:
    objective = "Escreva Olá mundo usando uma ferramenta apropriada"
    payload = valid_decomposition(objective=objective)
    payload["steps"] = payload["steps"][1:]
    payload["steps"][0]["depends_on"] = []
    payload["steps"][1].update(
        {
            "target": invented_target,
            "depends_on": ["open_editor"],
            "consumes": [],
        }
    )
    payload["criteria"] = payload["criteria"][1:]
    payload["criteria"][1]["expected_value"] = invented_target
    payload["subgoals"] = [payload["subgoals"][1]]
    payload["subgoals"][0].update(
        {
            "depends_on": [],
            "criterion_ids": ["editor_open", "title_present"],
        }
    )
    payload["capabilities"] = [payload["capabilities"][1]]

    with pytest.raises(ValidationError, match="target sem proveniência"):
        decomposition_from_structured(payload, expected_objective=objective)


def test_provider_cannot_turn_search_into_link_local_request() -> None:
    objective = "Pesquise inteligência artificial"
    payload = valid_decomposition(objective=objective)
    payload["steps"] = [payload["steps"][0]]
    payload["steps"][0]["target"] = (
        "http://169.254.169.254/latest/meta-data?q=inteligencia+artificial"
    )
    payload["criteria"] = [payload["criteria"][0]]
    payload["subgoals"] = [payload["subgoals"][0]]
    payload["capabilities"] = [payload["capabilities"][0]]

    with pytest.raises(ValidationError, match="busca local segura"):
        decomposition_from_structured(payload, expected_objective=objective)


def test_explicit_navigation_path_cannot_be_replaced_by_provider() -> None:
    objective = "Abra https://example.com/pedido e capture a tela."
    payload = navigation_and_capture_decomposition(
        objective,
        target="https://example.com/outro",
    )

    with pytest.raises(ValidationError, match="destino sem proveniência"):
        decomposition_from_structured(payload, expected_objective=objective)


@pytest.mark.parametrize(
    "objective",
    [
        "Abra https://example.com/pedido e capture a tela.",
        "Acesse example.com e capture a tela.",
    ],
)
def test_known_capture_effect_cannot_hide_omitted_navigation(objective: str) -> None:
    payload = navigation_and_capture_decomposition(
        objective,
        target="https://example.com/pedido",
    )
    payload["capabilities"] = [payload["capabilities"][1]]
    payload["criteria"] = [payload["criteria"][1]]
    payload["subgoals"] = [payload["subgoals"][1]]
    payload["subgoals"][0]["depends_on"] = []
    payload["steps"] = [payload["steps"][1]]
    payload["steps"][0]["depends_on"] = []

    with pytest.raises(ValidationError, match="não cobre os efeitos"):
        decomposition_from_structured(payload, expected_objective=objective)


def test_explicit_code_editor_cannot_be_replaced_by_provider_hint() -> None:
    objective = "Abra o VS Code e capture a tela."
    payload = navigation_and_capture_decomposition(
        objective,
        target="https://example.com",
    )
    payload["capabilities"][0] = {
        "id": "code.edit",
        "description": "Editar código",
        "hint": "Sublime Text",
    }
    payload["criteria"][0]["observable"] = "desktop.application"
    payload["subgoals"][0]["capability_ids"] = ["code.edit"]
    payload["steps"][0].update(
        {
            "id": "open_code",
            "capability_id": "code.edit",
            "operation": "open_capability",
            "target": None,
        }
    )
    payload["steps"][1]["depends_on"] = ["open_code"]

    with pytest.raises(ValidationError, match="não corresponde ao aplicativo"):
        decomposition_from_structured(payload, expected_objective=objective)


def test_structured_steps_preserve_human_effect_order() -> None:
    objective = "Capture a tela e depois abra o VS Code."
    payload = navigation_and_capture_decomposition(
        objective,
        target="https://example.com",
    )
    payload["capabilities"][0] = {
        "id": "code.edit",
        "description": "Editar código",
        "hint": "VS Code",
    }
    payload["criteria"][0]["observable"] = "desktop.application"
    payload["subgoals"][0]["capability_ids"] = ["code.edit"]
    payload["steps"][0].update(
        capability_id="code.edit",
        operation="open_capability",
        target=None,
    )

    with pytest.raises(ValidationError, match="ordem dos steps"):
        decomposition_from_structured(payload, expected_objective=objective)


def test_search_cannot_be_executed_after_a_downstream_capture() -> None:
    objective = "Pesquise gatos e depois capture a tela."
    payload = navigation_and_capture_decomposition(
        objective,
        target="https://www.bing.com/search?q=gatos",
    )
    payload["capabilities"][0]["id"] = "web.search"
    payload["criteria"][0]["observable"] = "browser.search_results"
    payload["subgoals"][0]["capability_ids"] = ["web.search"]
    payload["steps"][0]["capability_id"] = "web.search"
    payload["steps"] = [payload["steps"][1], payload["steps"][0]]
    payload["subgoals"][1]["depends_on"] = []
    payload["steps"][0]["depends_on"] = []
    payload["steps"][1]["depends_on"] = ["capture"]

    with pytest.raises(ValidationError, match="ordem dos steps"):
        decomposition_from_structured(payload, expected_objective=objective)


@pytest.mark.parametrize(
    "objective",
    [
        "Faça login e capture a tela.",
        "Execute malware e capture a tela.",
        "Compre algo e capture a tela.",
        "Clique em aceitar e capture a tela.",
    ],
)
def test_known_effect_cannot_hide_unclassified_material_clause(objective: str) -> None:
    payload = navigation_and_capture_decomposition(
        objective,
        target="https://example.com",
    )
    payload["capabilities"] = [payload["capabilities"][1]]
    payload["criteria"] = [payload["criteria"][1]]
    payload["subgoals"] = [payload["subgoals"][1]]
    payload["subgoals"][0]["depends_on"] = []
    payload["steps"] = [payload["steps"][1]]
    payload["steps"][0]["depends_on"] = []

    with pytest.raises(ValidationError, match="não classificada|não cobre"):
        decomposition_from_structured(payload, expected_objective=objective)


def test_search_requires_real_result_collection_not_title_or_page_text() -> None:
    payload = valid_decomposition()
    payload["criteria"][0]["observable"] = "browser.title"

    with pytest.raises(ValidationError, match="evidência de conteúdo"):
        decomposition_from_structured(payload, expected_objective=OBJECTIVE)


def test_supported_partial_effect_cannot_hide_unsupported_email_clause() -> None:
    objective = "Envie um email e escreva 'feito' em uma ferramenta apropriada"
    payload = valid_decomposition(objective=objective)

    with pytest.raises(ValidationError, match="fora do vocabulário"):
        decomposition_from_structured(payload, expected_objective=objective)


def test_invalid_navigation_is_refused_by_existing_policy_during_validation() -> None:
    payload = valid_decomposition()
    payload["steps"][0]["target"] = "file:///etc/passwd"

    with pytest.raises(ValidationError, match="Policy recusou"):
        decomposition_from_structured(payload, expected_objective=OBJECTIVE)


def test_artifact_must_be_produced_before_use_and_have_explicit_dependency() -> None:
    payload = valid_decomposition()
    payload["steps"][2]["depends_on"] = ["open_editor"]

    with pytest.raises(ValidationError, match="depender explicitamente do produtor"):
        decomposition_from_structured(payload, expected_objective=OBJECTIVE)


def test_duplicate_physical_effect_is_rejected_before_execution() -> None:
    payload = valid_decomposition()
    payload["criteria"].append(
        {
            "id": "editor_still_open",
            "description": "O mesmo editor continua observado",
            "observable": "desktop.application",
            "evidence_kind": "observation",
            "check": "truthy",
            "expected_value": None,
            "required": True,
        }
    )
    payload["subgoals"][1]["criterion_ids"].append("editor_still_open")
    duplicate = deepcopy(payload["steps"][1])
    duplicate["id"] = "open_editor_again"
    duplicate["criterion_ids"] = ["editor_still_open"]
    payload["steps"].append(duplicate)

    with pytest.raises(ValidationError, match="efeito físico duplicado"):
        decomposition_from_structured(payload, expected_objective=OBJECTIVE)


def test_provider_adapter_fails_closed_when_only_legacy_action_api_exists() -> None:
    class LegacyOnlyProvider:
        name = "legacy"

        def __init__(self) -> None:
            self.calls = 0

        def generate_plan(self, objective: str) -> dict:
            self.calls += 1
            return {"action": "open_url", "target": "https://example.com"}

    provider = LegacyOnlyProvider()

    with pytest.raises(ProviderGenerationError, match="ação livre não será usada"):
        ProviderPlanner(provider).decompose(OBJECTIVE)

    assert provider.calls == 0


def test_multi_provider_decomposition_falls_back_before_any_action_and_keeps_trace() -> None:
    invalid_payload = valid_decomposition(objective="Objetivo reduzido")
    first = GoalProvider(invalid_payload)
    second = GoalProvider(valid_decomposition())
    router = MultiProviderPlanner(
        [
            ProviderCandidate("cloudflare", first, frozenset({"fast", "reasoning"})),
            ProviderCandidate("zai", second, frozenset({"fast", "reasoning"})),
        ],
        route_order={
            "fast": ("cloudflare", "zai"),
            "reasoning": ("cloudflare", "zai"),
        },
    )

    decomposition = router.decompose(OBJECTIVE)

    assert decomposition.objective == OBJECTIVE
    assert router.last_provider == "zai"
    assert "cloudflare" in router.last_errors
    assert first.decomposition_calls == [OBJECTIVE]
    assert second.decomposition_calls == [OBJECTIVE]
    assert first.legacy_plan_calls == []
    assert second.legacy_plan_calls == []


def test_multi_provider_never_falls_back_to_free_action_api() -> None:
    class LegacyOnlyProvider:
        def __init__(self) -> None:
            self.plan_calls = 0

        def generate_plan(self, objective: str) -> dict:
            self.plan_calls += 1
            return {"action": "finish", "target": "feito"}

    legacy = LegacyOnlyProvider()
    router = MultiProviderPlanner(
        [ProviderCandidate("legacy", legacy, frozenset({"fast", "reasoning"}))]
    )

    with pytest.raises(ProviderGenerationError, match="contrato válido"):
        router.decompose(OBJECTIVE)

    assert legacy.plan_calls == 0
    assert "legacy" in router.last_errors


def test_multi_provider_never_falls_back_after_a_safety_interrupt() -> None:
    class StopProvider:
        def generate_goal_decomposition(self, objective: str) -> dict:
            raise EmergencyStopTriggered(f"stop during {objective}")

    second = GoalProvider(valid_decomposition())
    router = MultiProviderPlanner(
        [
            ProviderCandidate("stop", StopProvider(), frozenset({"fast", "reasoning"})),
            ProviderCandidate("second", second, frozenset({"fast", "reasoning"})),
        ],
        route_order={
            "fast": ("stop", "second"),
            "reasoning": ("stop", "second"),
        },
    )

    with pytest.raises(EmergencyStopTriggered):
        router.decompose(OBJECTIVE)

    assert second.decomposition_calls == []
    assert router.last_errors == {}


def test_decomposition_cannot_omit_the_requested_report_content() -> None:
    objective = "Produza um relatório trimestral usando um editor"
    payload = {
        "schema_version": "1.0",
        "objective": objective,
        "capabilities": [
            {"id": "text.edit", "description": "Editar texto", "hint": "editor"}
        ],
        "criteria": [
            {
                "id": "editor_open",
                "description": "Editor observado",
                "observable": "desktop.application",
                "evidence_kind": "observation",
                "check": "truthy",
                "expected_value": None,
                "required": True,
            }
        ],
        "subgoals": [
            {
                "id": "open_editor",
                "description": "Abrir editor",
                "capability_ids": ["text.edit"],
                "criterion_ids": ["editor_open"],
                "depends_on": [],
            }
        ],
        "steps": [
            {
                "id": "open_editor",
                "subgoal_id": "open_editor",
                "capability_id": "text.edit",
                "operation": "open_capability",
                "target": None,
                "criterion_ids": ["editor_open"],
                "depends_on": [],
                "consumes": [],
                "produces": [],
            }
        ],
    }

    with pytest.raises(ValidationError, match="criativo|omitiu|não classificada"):
        decomposition_from_structured(payload, expected_objective=objective)
