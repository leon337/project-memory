from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import pytest

import context_anchor.goal_execution as goal_execution
from context_anchor.capabilities import ResolvedCapability
from context_anchor.emergency_stop import EmergencyStopTriggered
from context_anchor.goal_execution import GoalExecutionFailed
from context_anchor.goal_interpreter import GoalIntent, IntentKind
from context_anchor.local_agent import execute_command
from context_anchor.planner import decomposition_from_structured
from context_anchor.policy import Plan
from context_anchor.session_context import ArtifactKind, SessionContext


class FakeExecutor:
    """Action receipts and observations are deliberately independent inputs."""

    desktop_enabled = True

    def __init__(
        self,
        *,
        browser_observations: tuple[dict[str, Any] | Exception, ...] = (),
        application_observations: tuple[dict[str, Any] | Exception, ...] = (),
        readbacks: tuple[dict[str, Any] | Exception, ...] = (),
        receipt_verified: bool = True,
        fail_target_contains: tuple[str, ...] = (),
        screenshot_path: Path | None = None,
    ) -> None:
        self.executed: list[Plan] = []
        self.browser_observer_calls = 0
        self.application_observer_calls = 0
        self.readback_calls = 0
        self._browser_observations = deque(browser_observations)
        self._application_observations = deque(application_observations)
        self._readbacks = deque(readbacks)
        self._last_browser_observation: dict[str, Any] | Exception | None = None
        self._last_application_observation: dict[str, Any] | Exception | None = None
        self._last_readback: dict[str, Any] | Exception | None = None
        self.receipt_verified = receipt_verified
        self.fail_target_contains = set(fail_target_contains)
        self.screenshot_path = screenshot_path

    @staticmethod
    def _copy_or_raise(value: dict[str, Any] | Exception) -> dict[str, Any]:
        if isinstance(value, Exception):
            raise value
        return dict(value)

    def execute(self, plan: Plan) -> dict[str, Any]:
        self.executed.append(plan)
        for marker in tuple(self.fail_target_contains):
            if marker in plan.target:
                self.fail_target_contains.remove(marker)
                raise RuntimeError(f"falha física simulada para {marker}")

        receipt: dict[str, Any] = {
            "action": plan.action,
            "verified": self.receipt_verified,
        }
        if plan.action == "open_url":
            receipt.update(
                requested_url=plan.target,
                final_url=plan.target,
                title="título presente apenas no recibo",
                http_status=200,
            )
        elif plan.action == "open_app":
            receipt.update(
                app=plan.target,
                executable=plan.target.split()[0],
                pid=4242,
                window_changed=True,
                window_id="receipt-window",
                window_title="janela presente apenas no recibo",
            )
        elif plan.action == "type_text":
            receipt.update(
                characters=len(plan.target),
                window_id="receipt-window",
                window_title="janela presente apenas no recibo",
            )
        elif plan.action == "capture_screen":
            receipt["path"] = str(self.screenshot_path or "/missing/fake-screen.png")
        return receipt

    def observe_browser(self) -> dict[str, Any]:
        self.browser_observer_calls += 1
        if self._browser_observations:
            value = self._browser_observations.popleft()
            self._last_browser_observation = value
        elif self._last_browser_observation is not None:
            value = self._last_browser_observation
        else:
            raise AssertionError("observe_browser chamado sem observação independente")
        return self._copy_or_raise(value)

    def observe_application(
        self,
        app_id: str,
        *,
        pid: int | None = None,
        expected_argument: str | None = None,
    ) -> dict[str, Any]:
        del app_id, pid, expected_argument
        self.application_observer_calls += 1
        if self._application_observations:
            value = self._application_observations.popleft()
            self._last_application_observation = value
        elif self._last_application_observation is not None:
            value = self._last_application_observation
        else:
            raise AssertionError(
                "observe_application chamado sem observação independente"
            )
        return self._copy_or_raise(value)

    def read_active_text(self, *, max_chars: int = 4096) -> dict[str, Any]:
        del max_chars
        self.readback_calls += 1
        if self._readbacks:
            value = self._readbacks.popleft()
            self._last_readback = value
        elif self._last_readback is not None:
            value = self._last_readback
        else:
            raise AssertionError("read_active_text chamado sem readback independente")
        return self._copy_or_raise(value)

    def observe_active_window(self) -> dict[str, Any]:
        return {
            "verified": True,
            "window_id": "observed-window",
            "title": "Janela observada",
        }


class MockCapabilityResolver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def resolve(
        self, capability: str, hint: str | None = None
    ) -> ResolvedCapability:
        self.calls.append((capability, hint))
        app_ids = {
            "text.edit": "fake-editor",
            "code.edit": "code",
            "calculate": "fake-calculator",
            "web.search": "brave-browser",
            "web.read": "brave-browser",
            "browser.navigate": "brave-browser",
        }
        app_id = app_ids[capability]
        return ResolvedCapability(
            capability=capability,
            app_id=app_id,
            display_name={
                "fake-editor": "Editor Mock",
                "code": "Visual Studio Code Mock",
                "fake-calculator": "Calculadora Mock",
                "brave-browser": "Brave Mock",
            }[app_id],
            executable=f"/mock/{app_id}",
            source="mock-registry",
        )


class ExplodingPlanner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def plan(self, objective: str) -> Plan:
        self.calls.append(objective)
        raise AssertionError("o planner não deveria participar deste intent tipado")


class ReceiptThenFinishPlanner:
    last_provider = "provider-a"
    last_route = "reasoning"
    last_errors: dict[str, str] = {}

    def __init__(self) -> None:
        self.calls: list[str] = []

    def plan(self, objective: str) -> Plan:
        self.calls.append(objective)
        if len(self.calls) == 1:
            return Plan("open_app", "/mock/fake-editor")
        return Plan("finish", "feito")


class DuplicateAcrossProvidersPlanner:
    last_provider = "provider-a"
    last_route = "reasoning"
    last_errors: dict[str, str] = {}

    def __init__(self) -> None:
        self.calls: list[str] = []

    def plan(self, objective: str) -> Plan:
        self.calls.append(objective)
        decision = len(self.calls)
        if decision == 1:
            self.last_provider = "provider-a"
            return Plan("open_app", "/mock/fake-editor")
        if decision == 2:
            self.last_provider = "provider-b"
            self.last_errors = {"provider-a": "fallback simulado"}
            return Plan("open_app", "/mock/fake-editor")
        self.last_provider = "provider-b"
        self.last_errors = {}
        return Plan("finish", "efeito observado")


class GenericOnlyInterpreter:
    def interpret(self, command: str) -> GoalIntent:
        return GoalIntent(IntentKind.GENERIC, command)


class StructuredOpenAndWritePlanner:
    last_provider = "structured-provider"
    last_route = "reasoning"
    last_errors = {"unavailable-provider": "fallback antes da execução"}

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.legacy_calls: list[str] = []

    def decompose(self, objective: str):
        self.calls.append(objective)
        payload = {
            "schema_version": "1.0",
            "objective": objective,
            "capabilities": [
                {
                    "id": "text.edit",
                    "description": "Editar texto em superfície local",
                    "hint": "editor",
                }
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
                },
                {
                    "id": "text_present",
                    "description": "Texto relido exatamente",
                    "observable": "desktop.text",
                    "evidence_kind": "readback",
                    "check": "equals",
                    "expected_value": "Olá mundo",
                    "required": True,
                },
            ],
            "subgoals": [
                {
                    "id": "open_editor",
                    "description": "Abrir editor",
                    "capability_ids": ["text.edit"],
                    "criterion_ids": ["editor_open"],
                    "depends_on": [],
                },
                {
                    "id": "write_text",
                    "description": "Escrever texto",
                    "capability_ids": ["text.edit"],
                    "criterion_ids": ["text_present"],
                    "depends_on": ["open_editor"],
                },
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
                },
                {
                    "id": "write_text",
                    "subgoal_id": "write_text",
                    "capability_id": "text.edit",
                    "operation": "write_text",
                    "target": "Olá mundo",
                    "criterion_ids": ["text_present"],
                    "depends_on": ["open_editor"],
                    "consumes": [],
                    "produces": [],
                },
            ],
        }
        return decomposition_from_structured(payload, expected_objective=objective)

    def plan(self, objective: str) -> Plan:
        self.legacy_calls.append(objective)
        return Plan("finish", "não deve ser usado")


@pytest.fixture(autouse=True)
def no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(goal_execution.time, "sleep", lambda _seconds: None)


def _application_observation(
    *,
    app: str = "fake-editor",
    title: str = "Editor Mock — Documento sem título",
    verified: bool = True,
) -> dict[str, Any]:
    return {
        "action": "observe_application",
        "app": app,
        "identity_observed": verified,
        "class_identity_observed": verified,
        "process_identity_observed": verified,
        "argument_observed": verified,
        "window_id": "observed-window",
        "window_title": title,
        "window_class": app,
        "verified": verified,
    }


def _readback(text: str, *, verified: bool = True) -> dict[str, Any]:
    return {
        "action": "read_active_text",
        "text": text,
        "characters": len(text),
        "source": "fake-independent-readback",
        "window_id": "observed-window",
        "window_title": "Editor Mock — Documento sem título",
        "clipboard_restored": True,
        "verified": verified,
    }


def _search_snapshot(
    query: str,
    *,
    engine: str = "bing",
    first_title: str | None = "Resultado observado",
    status: int = 200,
    include_results: bool = True,
) -> dict[str, Any]:
    search_urls = {
        "bing": f"https://www.bing.com/search?q={quote_plus(query)}",
        "google": f"https://www.google.com/search?q={quote_plus(query)}",
        "duckduckgo": f"https://duckduckgo.com/?q={quote_plus(query)}",
    }
    results = (
        [
            {
                "position": 1,
                "title": first_title or "Resultado sem título estruturado",
                "url": "https://result.example/first",
            }
        ]
        if include_results
        else []
    )
    return {
        "url": search_urls[engine],
        "title": f"{query} - pesquisa {engine}",
        "text": f"Página observada para {query}",
        "http_status": status,
        "search_results": results,
        "first_result_title": first_title,
        "first_result_url": (
            "https://result.example/first" if first_title is not None else None
        ),
    }


def _assert_succeeded(result: dict[str, Any]) -> None:
    assert result["action"] == "goal"
    assert result["status"] == "succeeded"
    assert result["goal_completed"] is True
    assert result["verified"] is True
    assert result["metrics"]["status"] == "succeeded"
    assert result["metrics"]["criteria"]["pending"] == 0


def test_legacy_finish_planner_cannot_create_criteria_from_its_own_actions() -> None:
    executor = FakeExecutor(
        application_observations=(
            _application_observation(verified=False),
        )
    )
    planner = ReceiptThenFinishPlanner()

    with pytest.raises(GoalExecutionFailed) as caught:
        execute_command(
            executor,
            "Organize meu trabalho usando uma ferramenta apropriada",
            planner=planner,
            max_goal_steps=2,
        )

    result = caught.value.result
    assert executor.executed == []
    assert planner.calls == []
    assert result["goal_completed"] is False
    assert result["verified"] is False
    assert result["status"] == "failed"
    assert result["criteria"][0]["status"] == "pending"
    assert result["criteria"][0]["id"] == "structured_decomposition"
    assert result["steps"] == []
    assert result["evidence"] == []


def test_basic_open_and_write_uses_capability_and_independent_readback() -> None:
    resolver = MockCapabilityResolver()
    executor = FakeExecutor(
        application_observations=(_application_observation(),),
        readbacks=(_readback("Olá mundo"),),
    )

    result = execute_command(
        executor,
        "Abra o editor de texto e escreva Olá mundo",
        capability_resolver=resolver,
    )

    _assert_succeeded(result)
    assert resolver.calls == [("text.edit", "editor")]
    assert executor.executed == [
        Plan("open_app", "/mock/fake-editor"),
        Plan("type_text", "Olá mundo"),
    ]
    assert [item["id"] for item in result["criteria"]] == [
        "editor_open",
        "text_present",
    ]
    text_evidence = [
        item for item in result["evidence"] if item["criterion_id"] == "text_present"
    ]
    assert {item["kind"] for item in text_evidence} == {
        "execution_receipt",
        "readback",
    }
    persisted_readback = next(
        item for item in text_evidence if item["kind"] == "readback"
    )["observed_value"]
    assert persisted_readback["redacted"] is True
    assert persisted_readback["matched_expected"] is True
    assert persisted_readback["characters"] == len("Olá mundo")


def test_basic_browser_navigation_is_closed_by_an_observation() -> None:
    executor = FakeExecutor(
        browser_observations=(
            {
                "url": "https://globo.com/",
                "title": "Globo",
                "text": "Página inicial observada",
                "http_status": 200,
            },
        )
    )

    result = execute_command(executor, "Abra o navegador e acesse o site globo.com")

    _assert_succeeded(result)
    assert executor.executed == [Plan("open_url", "https://globo.com")]
    assert result["steps"][0]["strategy"] == "deterministic"
    assert {item["kind"] for item in result["evidence"]} == {
        "execution_receipt",
        "observation",
    }


def test_navigation_requires_the_requested_path_not_only_the_hostname() -> None:
    executor = FakeExecutor(
        browser_observations=(
            {
                "url": "https://example.com/",
                "title": "Example home",
                "text": "Home page",
                "http_status": 200,
            },
        )
    )

    with pytest.raises(GoalExecutionFailed) as caught:
        execute_command(executor, "Visite https://example.com/documento-especifico")

    assert caught.value.result["goal_completed"] is False
    observation = next(
        item
        for item in caught.value.result["evidence"]
        if item["kind"] == "observation"
    )
    assert observation["verified"] is False
    assert observation["metadata"]["target_matches"] is False


def test_basic_named_browser_search_observes_browser_identity_and_query() -> None:
    resolver = MockCapabilityResolver()
    executor = FakeExecutor(
        application_observations=(
            _application_observation(
                app="brave-browser",
                title="São Lourenço da Mata - Pesquisa Google - Brave",
            ),
        )
    )

    result = execute_command(
        executor,
        "Abra o navegador brave e acesse o site google.com e pesquise São Lourenço da Mata",
        capability_resolver=resolver,
    )

    _assert_succeeded(result)
    assert resolver.calls == [("web.search", "brave-browser")]
    assert len(executor.executed) == 1
    assert executor.executed[0].action == "open_app"
    assert executor.executed[0].target.startswith("/mock/brave-browser ")
    assert "google.com/search" in executor.executed[0].target
    assert {item["id"] for item in result["criteria"]} == {
        "browser_open",
        "query_observed",
    }


@pytest.mark.parametrize(
    ("command", "expected_capability"),
    [
        ("Abra o VS Code", "code.edit"),
        ("Preciso fazer algumas contas.", "calculate"),
        (
            "Quero fazer uma anotação. Abra alguma coisa onde eu possa escrever.",
            "text.edit",
        ),
    ],
)
def test_basic_capability_intents_open_an_observed_provider(
    command: str, expected_capability: str
) -> None:
    resolver = MockCapabilityResolver()
    executor = FakeExecutor(
        application_observations=(
            _application_observation(app=expected_capability),
        )
    )

    result = execute_command(
        executor,
        command,
        capability_resolver=resolver,
    )

    _assert_succeeded(result)
    assert resolver.calls[0][0] == expected_capability
    assert [plan.action for plan in executor.executed] == ["open_app"]
    assert result["criteria"] == [
        {
            "id": "capability_ready",
            "description": "a ferramenta adequada foi observada",
            "required": True,
            "check": "truthy",
            "expected_value": None,
            "status": "satisfied",
            "evidence_ids": result["criteria"][0]["evidence_ids"],
        }
    ]


def test_gui_capability_requires_an_observed_window_not_only_a_process() -> None:
    process_only = {
        "verified": True,
        "identity_observed": True,
        "process_alive": True,
        "window_id": None,
        "window_title": None,
        "window_class": None,
    }
    executor = FakeExecutor(application_observations=(process_only,))

    with pytest.raises(GoalExecutionFailed) as caught:
        execute_command(
            executor,
            "Abra o VS Code",
            capability_resolver=MockCapabilityResolver(),
        )

    assert caught.value.result["goal_completed"] is False
    observation = next(
        item
        for item in caught.value.result["evidence"]
        if item["kind"] == "observation"
    )
    assert observation["verified"] is False
    assert observation["metadata"]["window_observed"] is False


def test_gui_capability_waits_for_the_target_window_without_relaunching() -> None:
    process_only = {
        "verified": False,
        "identity_observed": False,
        "process_identity_observed": True,
        "class_identity_observed": False,
        "process_alive": True,
        "window_id": None,
        "window_title": None,
        "window_class": None,
    }
    executor = FakeExecutor(
        application_observations=(process_only, _application_observation()),
    )

    result = execute_command(
        executor,
        "Abra o VS Code",
        capability_resolver=MockCapabilityResolver(),
    )

    _assert_succeeded(result)
    assert executor.executed == [Plan("open_app", "/mock/code")]
    assert executor.application_observer_calls == 2


def test_capability_fallback_never_launches_a_second_app_after_first_launch() -> None:
    first = ResolvedCapability(
        capability="text.edit",
        app_id="first-editor",
        display_name="First Editor",
        executable="/mock/first-editor",
        source="mock",
    )
    second = ResolvedCapability(
        capability="text.edit",
        app_id="second-editor",
        display_name="Second Editor",
        executable="/mock/second-editor",
        source="mock",
    )

    class Resolver:
        def resolve(self, capability: str, hint: str | None = None) -> ResolvedCapability:
            del capability, hint
            return first

        def available(self, capability: str) -> tuple[ResolvedCapability, ...]:
            del capability
            return (first, second)

    executor = FakeExecutor(
        application_observations=(_application_observation(verified=False),)
    )

    with pytest.raises(GoalExecutionFailed):
        execute_command(
            executor,
            "Quero fazer uma anotação. Abra alguma coisa onde eu possa escrever.",
            capability_resolver=Resolver(),  # type: ignore[arg-type]
        )

    assert executor.executed == [Plan("open_app", "/mock/first-editor")]


def test_structured_write_is_not_replayed_after_backend_error() -> None:
    executor = FakeExecutor(
        application_observations=(_application_observation(),),
        fail_target_contains=("Olá mundo",),
    )

    with pytest.raises(GoalExecutionFailed):
        execute_command(
            executor,
            "Escreva Olá mundo usando uma ferramenta apropriada",
            planner=StructuredOpenAndWritePlanner(),
            interpreter=GenericOnlyInterpreter(),
            capability_resolver=MockCapabilityResolver(),
        )

    assert [plan.action for plan in executor.executed] == ["open_app", "type_text"]


@pytest.mark.parametrize(
    ("command", "query", "information"),
    [
        ("Pesquise inteligência artificial", "inteligência artificial", False),
        (
            "Quero saber o significado do nome Josiel.",
            "significado do nome Josiel",
            True,
        ),
    ],
)
def test_basic_search_and_information_intents_require_structured_results(
    command: str, query: str, information: bool
) -> None:
    executor = FakeExecutor(browser_observations=(_search_snapshot(query),))

    result = execute_command(executor, command)

    _assert_succeeded(result)
    assert len(executor.executed) == 1
    assert executor.executed[0].action == "open_url"
    assert "bing.com/search" in executor.executed[0].target
    criterion_ids = {item["id"] for item in result["criteria"]}
    assert {"query_observed", "results_observed"} <= criterion_ids
    assert ("information_observed" in criterion_ids) is information
    assert all(
        any(
            evidence["kind"] == "observation" and evidence["verified"]
            for evidence in result["evidence"]
            if evidence["criterion_id"] == criterion_id
        )
        for criterion_id in criterion_ids
    )


def test_critical_search_title_editor_dataflow_has_complete_result_and_metrics() -> None:
    query = "inteligência artificial"
    first_title = "Inteligência artificial: conceitos e aplicações"
    planner = ExplodingPlanner()
    resolver = MockCapabilityResolver()
    executor = FakeExecutor(
        browser_observations=(
            _search_snapshot(query, first_title=first_title),
        ),
        application_observations=(_application_observation(),),
        readbacks=(_readback(first_title),),
    )

    result = execute_command(
        executor,
        "Pesquise inteligência artificial e depois abra um editor de texto e escreva o título do primeiro resultado.",
        planner=planner,
        capability_resolver=resolver,
        task_id="task-critical",
    )

    _assert_succeeded(result)
    assert planner.calls == []
    assert [plan.action for plan in executor.executed] == [
        "open_url",
        "open_app",
        "type_text",
    ]
    assert executor.executed[-1].target == first_title
    assert result["task_id"] == "task-critical"
    assert result["goal_id"]
    assert result["artifacts"]["first_result_title"] == first_title
    assert result["artifacts"]["first_result_url"] == (
        "https://result.example/[redacted-path]"
    )
    assert result["artifacts"]["editor"] == "Editor Mock"
    assert [item["id"] for item in result["subgoals"]] == [
        "search",
        "open_editor",
        "write_title",
    ]
    assert {item["status"] for item in result["subgoals"]} == {"satisfied"}
    assert {item["status"] for item in result["criteria"]} == {"satisfied"}

    metrics = result["metrics"]
    assert metrics["goal_id"] == result["goal_id"]
    assert metrics["task_id"] == "task-critical"
    assert metrics["steps"] == 3
    assert metrics["subgoals"] == {"satisfied": 3, "pending": 0}
    assert metrics["criteria"] == {"satisfied": 5, "pending": 0}
    step_providers = {
        step["provider"] for step in result["steps"] if step["provider"] is not None
    }
    assert set(metrics["providers"]) == step_providers
    assert {"bing", "mock-registry"} < step_providers
    assert metrics["fallbacks"] == 0
    assert metrics["retries"] == {"total": 0, "by_strategy": {}}
    assert metrics["final_reason"] == result["completion"]

    evidence_by_id = {item["id"]: item for item in result["evidence"]}
    assert evidence_by_id
    for step in result["steps"]:
        assert step["evidence_ids"]
        assert all(
            evidence_by_id[evidence_id]["step_id"] == step["id"]
            for evidence_id in step["evidence_ids"]
        )
    for criterion in result["criteria"]:
        criterion_evidence = [
            evidence_by_id[evidence_id]
            for evidence_id in criterion["evidence_ids"]
        ]
        assert any(
            item["kind"] in {"observation", "readback"} and item["verified"]
            for item in criterion_evidence
        )


def test_compound_fast_path_cannot_report_partial_search_as_success() -> None:
    query = "inteligência artificial"
    planner = ExplodingPlanner()
    resolver = MockCapabilityResolver()
    executor = FakeExecutor(
        browser_observations=(
            _search_snapshot(query, engine="bing", first_title=None),
            _search_snapshot(query, engine="google", first_title=None),
            _search_snapshot(query, engine="duckduckgo", first_title=None),
        ),
        application_observations=(_application_observation(),),
    )

    with pytest.raises(GoalExecutionFailed) as caught:
        execute_command(
            executor,
            "Pesquise inteligência artificial e depois abra um editor de texto e escreva o título do primeiro resultado.",
            planner=planner,
            capability_resolver=resolver,
        )

    result = caught.value.result
    assert planner.calls == []
    assert result["goal_completed"] is False
    assert result["verified"] is False
    statuses = {item["id"]: item["status"] for item in result["criteria"]}
    assert statuses["query_observed"] == "satisfied"
    assert statuses["results_observed"] == "satisfied"
    assert statuses["first_title_extracted"] == "pending"
    assert statuses["text_present"] == "pending"
    assert [plan.action for plan in executor.executed] == [
        "open_url",
        "open_url",
        "open_url",
    ]
    assert "type_text" not in [plan.action for plan in executor.executed]


@pytest.mark.parametrize(
    ("http_status", "expected_branch", "expected_text"),
    [
        (200, "true", "site acessível"),
        (503, "false", "site indisponível"),
    ],
)
def test_conditional_goal_executes_and_reads_back_only_the_observed_branch(
    monkeypatch: pytest.MonkeyPatch,
    http_status: int,
    expected_branch: str,
    expected_text: str,
) -> None:
    def unexpected_http_fallback(_url: str) -> dict[str, Any]:
        raise AssertionError("o browser forneceu uma observação; fallback HTTP indevido")

    monkeypatch.setattr(goal_execution, "_probe_url", unexpected_http_fallback)
    resolver = MockCapabilityResolver()
    executor = FakeExecutor(
        browser_observations=(
            {
                "url": "https://example.com/",
                "title": "Example Domain",
                "text": "Example Domain",
                "http_status": http_status,
            },
        ),
        application_observations=(_application_observation(),),
        readbacks=(_readback(expected_text),),
    )

    result = execute_command(
        executor,
        'Verifique se example.com está acessível. Se estiver, abra um editor e escreva "site acessível". Se não estiver, escreva "site indisponível".',
        capability_resolver=resolver,
    )

    _assert_succeeded(result)
    assert result["artifacts"]["selected_branch"] == expected_branch
    assert result["artifacts"]["branch_text"]["redacted"] is True
    assert result["artifacts"]["branch_text"]["characters"] == len(expected_text)
    assert result["artifacts"]["condition"]["accessible"] is (http_status == 200)
    assert executor.executed[-1] == Plan("type_text", expected_text)
    condition_evidence = [
        item
        for item in result["evidence"]
        if item["criterion_id"] == "condition_observed"
    ]
    assert {item["kind"] for item in condition_evidence} == {
        "execution_receipt",
        "observation",
    }
    assert next(
        item for item in condition_evidence if item["kind"] == "observation"
    )["observed_value"] == {"accessible": http_status == 200}


def test_conditional_rejects_unrelated_browser_snapshot_before_http_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probed: list[str] = []

    def target_probe(url: str) -> dict[str, Any]:
        probed.append(url)
        return {
            "accessible": False,
            "verified": True,
            "source": "httpx.head_get",
            "status": 503,
            "final_url": url,
        }

    monkeypatch.setattr(goal_execution, "_probe_url", target_probe)
    executor = FakeExecutor(
        browser_observations=(
            {
                "url": "https://unrelated.test/",
                "title": "Unrelated",
                "text": "Unrelated page",
                "http_status": 200,
            },
        ),
        application_observations=(_application_observation(),),
        readbacks=(_readback("site indisponível"),),
    )

    result = execute_command(
        executor,
        'Verifique se example.com está acessível. Se estiver, abra um editor e escreva "site acessível". Se não estiver, escreva "site indisponível".',
        capability_resolver=MockCapabilityResolver(),
    )

    _assert_succeeded(result)
    assert probed == ["https://example.com"]
    assert result["artifacts"]["selected_branch"] == "false"
    assert result["artifacts"]["condition"]["source"] == "httpx.head_get"


def test_context_from_one_task_resolves_la_in_the_next_task(tmp_path: Path) -> None:
    context = SessionContext(tmp_path / "session-context.json")
    first_query = "São Lourenço da Mata"
    first_executor = FakeExecutor(
        browser_observations=(_search_snapshot(first_query),)
    )

    first_result = execute_command(
        first_executor,
        "Pesquise São Lourenço da Mata",
        task_id="task-location",
        session_context=context,
    )

    _assert_succeeded(first_result)
    assert context.get(ArtifactKind.LOCATION) == first_query

    resolved_query = "a previsão do tempo de São Lourenço da Mata"
    second_executor = FakeExecutor(
        browser_observations=(_search_snapshot(resolved_query),)
    )
    second_result = execute_command(
        second_executor,
        "Agora pesquise a previsão do tempo de lá.",
        task_id="task-weather",
        session_context=context,
    )

    _assert_succeeded(second_result)
    resolved_goal = "Agora pesquise a previsão do tempo de São Lourenço da Mata."
    assert second_result["resolved_goal"] == (
        f"[redacted goal; characters={len(resolved_goal)}]"
    )
    assert second_result["context_resolution"] == {
        "changed": True,
        "artifacts": [
            {
                "kind": "location",
                "value": {"redacted": True, "characters": len(first_query)},
                "origin_task_id": "task-location",
                "timestamp": second_result["context_resolution"]["artifacts"][0][
                    "timestamp"
                ],
            }
        ],
    }
    assert "S%C3%A3o+Louren%C3%A7o+da+Mata" in second_executor.executed[0].target


def test_search_falls_back_to_another_engine_and_reports_the_attempts() -> None:
    query = "testes resilientes"
    executor = FakeExecutor(
        fail_target_contains=("www.bing.com",),
        browser_observations=(
            _search_snapshot(query, engine="google", first_title="Testes resilientes"),
        ),
    )

    result = execute_command(executor, f"Pesquise {query}")

    _assert_succeeded(result)
    assert len(executor.executed) == 2
    assert "www.bing.com" in executor.executed[0].target
    assert "www.google.com" in executor.executed[1].target
    assert result["steps"][0]["status"] == "failed"
    assert result["steps"][0]["provider"] == "bing"
    assert result["steps"][1]["status"] == "succeeded"
    assert result["steps"][1]["provider"] == "google"
    assert result["steps"][1]["fallback_from"] == "RuntimeError"
    assert result["metrics"]["providers"] == ["bing", "google"]
    assert result["metrics"]["fallbacks"] == 1
    assert result["planner_fallbacks"] == ["RuntimeError"]


def test_legacy_provider_fallback_cannot_reintroduce_free_physical_actions() -> None:
    planner = DuplicateAcrossProvidersPlanner()
    executor = FakeExecutor(
        application_observations=(_application_observation(),),
    )

    with pytest.raises(GoalExecutionFailed) as caught:
        execute_command(
            executor,
            "Organize meu trabalho usando uma ferramenta apropriada",
            planner=planner,
            max_goal_steps=4,
        )

    assert caught.value.result["goal_completed"] is False
    assert planner.calls == []
    assert executor.executed == []


def test_emergency_stop_aborts_search_without_retry_or_fallback() -> None:
    class StopExecutor(FakeExecutor):
        def execute(self, plan: Plan) -> dict[str, Any]:
            self.executed.append(plan)
            raise EmergencyStopTriggered("stop ativo")

    executor = StopExecutor()

    with pytest.raises(EmergencyStopTriggered, match="stop ativo"):
        execute_command(executor, "Pesquise segurança operacional")

    assert len(executor.executed) == 1
    assert "bing.com" in executor.executed[0].target


def test_search_fallback_cannot_combine_query_and_unrelated_results() -> None:
    query = "inteligência artificial"
    unrelated = "receitas de bolo"
    executor = FakeExecutor(
        browser_observations=(
            _search_snapshot(query, engine="bing", include_results=False),
            _search_snapshot(
                unrelated,
                engine="google",
                first_title="Bolo de chocolate",
            ),
            _search_snapshot(
                unrelated,
                engine="duckduckgo",
                first_title="Receita fácil",
            ),
        )
    )

    with pytest.raises(GoalExecutionFailed) as caught:
        execute_command(
            executor,
            "Pesquise inteligência artificial e depois abra um editor de texto e escreva o título do primeiro resultado.",
            capability_resolver=MockCapabilityResolver(),
        )

    assert caught.value.result["goal_completed"] is False
    assert [plan.action for plan in executor.executed] == [
        "open_url",
        "open_url",
        "open_url",
    ]
    assert all(plan.action != "type_text" for plan in executor.executed)
    unrelated_results = [
        item
        for item in caught.value.result["evidence"]
        if item["criterion_id"] == "results_observed"
        and item["metadata"].get("engine") in {"google", "duckduckgo"}
    ]
    assert unrelated_results
    assert all(item["verified"] is False for item in unrelated_results)


def test_search_requires_the_observed_engine_host_not_only_matching_query() -> None:
    query = "inteligência artificial"
    malicious = _search_snapshot(query, first_title="Malicioso")
    malicious["url"] = (
        "https://evil.test/search?q=inteligencia+artificial"
    )
    executor = FakeExecutor(browser_observations=(malicious, malicious, malicious))

    with pytest.raises(GoalExecutionFailed) as caught:
        execute_command(executor, "Pesquise inteligência artificial")

    assert caught.value.result["goal_completed"] is False
    query_evidence = [
        item
        for item in caught.value.result["evidence"]
        if item["criterion_id"] == "query_observed"
        and item["kind"] == "observation"
    ]
    assert query_evidence
    assert all(item["verified"] is False for item in query_evidence)
    assert all(item["metadata"]["host_match"] is False for item in query_evidence)


def test_named_browser_requires_observed_launch_argument_as_well_as_title() -> None:
    observed = _application_observation(
        app="brave-browser",
        title="São Lourenço da Mata - Pesquisa Google - Brave",
    )
    observed["argument_observed"] = False
    executor = FakeExecutor(application_observations=(observed,))

    with pytest.raises(GoalExecutionFailed) as caught:
        execute_command(
            executor,
            "Abra o navegador brave e acesse o site google.com e pesquise São Lourenço da Mata",
            capability_resolver=MockCapabilityResolver(),
        )

    assert caught.value.result["goal_completed"] is False
    assert {item["status"] for item in caught.value.result["criteria"]} == {"pending"}


def test_generic_goal_without_structured_decomposition_fails_before_action() -> None:
    planner = ReceiptThenFinishPlanner()
    executor = FakeExecutor()

    with pytest.raises(GoalExecutionFailed, match="decomposição"):
        execute_command(executor, "Faça backup dos meus arquivos", planner=planner)

    assert planner.calls == []
    assert executor.executed == []


def test_failed_decomposition_preserves_provider_attempt_telemetry() -> None:
    class FailingDecomposer:
        last_provider = None
        last_route = "reasoning"
        last_errors = {"zai": "timeout", "cloudflare": "429"}

        def decompose(self, objective: str):
            del objective
            raise RuntimeError("nenhum contrato aceito")

    with pytest.raises(GoalExecutionFailed) as caught:
        execute_command(
            FakeExecutor(),
            "Produza um relatório complexo",
            planner=FailingDecomposer(),  # type: ignore[arg-type]
            interpreter=GenericOnlyInterpreter(),
        )

    result = caught.value.result
    assert result["planner_provider"] is None
    assert result["planner_route"] == "reasoning"
    assert result["planner_fallbacks"] == ["cloudflare", "zai"]
    assert result["metrics"]["providers"] == ["cloudflare", "zai"]
    assert result["steps"] == []


def test_generic_goal_uses_complete_decomposition_before_any_action() -> None:
    planner = StructuredOpenAndWritePlanner()
    executor = FakeExecutor(
        application_observations=(_application_observation(),),
        readbacks=(_readback("Olá mundo"),),
    )

    result = execute_command(
        executor,
        "Escreva Olá mundo usando uma ferramenta apropriada",
        planner=planner,
        interpreter=GenericOnlyInterpreter(),
        capability_resolver=MockCapabilityResolver(),
    )

    _assert_succeeded(result)
    assert planner.calls == ["Escreva Olá mundo usando uma ferramenta apropriada"]
    assert planner.legacy_calls == []
    assert [plan.action for plan in executor.executed] == ["open_app", "type_text"]
    assert result["planner_provider"] == "structured-provider"
    assert result["planner_fallbacks"] == ["unavailable-provider"]
    assert result["artifacts"]["decomposition"]["step_ids"] == [
        "open_editor",
        "write_text",
    ]


def test_persisted_goal_result_redacts_typed_text_readback_and_secret_values() -> None:
    secret = "super-secret-value"
    requested = f"API_KEY={secret}"
    executor = FakeExecutor(
        application_observations=(_application_observation(),),
        readbacks=(_readback(requested),),
    )

    result = execute_command(
        executor,
        f"Abra o editor de texto e escreva {requested}",
        capability_resolver=MockCapabilityResolver(),
    )

    serialized = json.dumps(result, ensure_ascii=False)
    assert secret not in serialized
    assert requested not in serialized
    assert result["steps"][-1]["target"]["redacted"] is True
    readback = next(
        item for item in result["evidence"] if item["kind"] == "readback"
    )
    assert readback["observed_value"]["matched_expected"] is True
