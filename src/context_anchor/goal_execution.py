from __future__ import annotations

import inspect
import re
import shlex
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, parse_qsl, quote_plus, unquote_plus, urlparse
from uuid import uuid4

import httpx

from .actions import ActionExecutor
from .capabilities import CapabilityResolver, ResolvedCapability
from .desktop import DesktopFailsafeTriggered
from .emergency_stop import EmergencyStopTriggered
from .goal_interpreter import GoalIntent, SemanticGoalInterpreter
from .lease import LeaseOwnershipLost, is_safety_interrupt
from .goal_runtime import (
    CriterionCheck,
    EvidenceKind,
    EvidenceRecord,
    GoalBudget,
    GoalContract,
    GoalCriterion,
    GoalRunState,
    GoalRunStatus,
    GoalStep,
    GoalStepStatus,
    GoalSubgoal,
    GoalVerifier,
    ProgressStatus,
    StepBlockReason,
)
from .planner import (
    Planner,
    StructuredGoalDecomposition,
    StructuredGoalStep,
    plan_from_goal_step,
    resolve_goal_value,
    structured_capability_requires_strict_hint,
)
from .policy import Plan, evaluate_plan
from .redaction import contains_sensitive_data, redact_text, redact_url, redact_value
from .session_context import ArtifactKind, ContextResolution, SessionContext


class GoalExecutionFailed(RuntimeError):
    """A goal ended without a verifier-authorized success verdict."""

    def __init__(self, message: str, result: dict[str, Any]) -> None:
        super().__init__(message)
        self.result = result


def _is_safety_interrupt(exc: BaseException) -> bool:
    """Return true for safety controls that must never enter fallback/retry."""

    return is_safety_interrupt(exc)


@dataclass(frozen=True, slots=True)
class _EvidenceSpec:
    criterion_id: str
    kind: EvidenceKind
    source: str
    verified: bool
    observed_value: Any
    metadata: dict[str, Any] | None = None


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_text).split())


def _safe_value(value: Any, *, depth: int = 0) -> Any:
    if depth >= 3:
        return str(value)[:240]
    if isinstance(value, str):
        return value[:800]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    if isinstance(value, dict):
        return {
            str(key)[:80]: _safe_value(item, depth=depth + 1)
            for key, item in list(value.items())[:20]
        }
    if isinstance(value, (list, tuple)):
        return [_safe_value(item, depth=depth + 1) for item in value[:12]]
    return str(value)[:400]


def _redact_url(value: str) -> str:
    return redact_url(value)


def _public_string(value: str) -> str:
    return redact_text(value, max_chars=800)


def _public_value(value: Any, *, depth: int = 0) -> Any:
    return redact_value(value, depth=depth)


def _private_text_summary(value: Any, *, salt: str) -> dict[str, Any]:
    # ``salt`` remains in the call signature for compatibility with older
    # integrations, but a persisted digest still enables cross-result
    # correlation and offline guessing.  Length is sufficient diagnostics.
    del salt
    text = value if isinstance(value, str) else ""
    return {
        "redacted": True,
        "characters": len(text),
    }


def _private_literals(run: GoalRunState) -> tuple[str, ...]:
    values: set[str] = set()
    for step in run.steps:
        if step.metadata.get("action") == "type_text":
            target = step.metadata.get("target")
            if isinstance(target, str) and target:
                values.add(target)
    for criterion in run.contract.criteria:
        if (
            EvidenceKind.READBACK in criterion.allowed_evidence_kinds
            and isinstance(criterion.expected_value, str)
            and criterion.expected_value
        ):
            values.add(criterion.expected_value)
    for key in ("branch_text", "written_text", "written.text"):
        value = run.contract.artifacts.get(key)
        if isinstance(value, str) and value:
            values.add(value)
    return tuple(sorted(values, key=len, reverse=True))


def _public_run_string(run: GoalRunState, value: str) -> str:
    for private_value in _private_literals(run):
        value = value.replace(private_value, "[redacted]")
    return _public_string(value)


def _public_goal_string(run: GoalRunState, value: str) -> str:
    # Free-form goals can contain names, locations, health topics or credentials
    # that no finite token regex can classify safely. The task already owns the
    # executable command in its protected queue; result/evidence payloads retain
    # only useful length metadata and never duplicate the text.
    del run
    return f"[redacted goal; characters={len(value)}]"


def _normalized_host(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or "").casefold().removeprefix("www.")


def _normalized_navigation_key(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = _normalized_host(value)
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    query = tuple(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    return f"{host}{path}|{query!r}"


def _navigation_matches(requested: str, observed: str) -> bool:
    requested_url = urlparse(
        requested if "://" in requested else f"https://{requested}"
    )
    observed_url = urlparse(observed if "://" in observed else f"https://{observed}")
    requested_scheme = requested_url.scheme.casefold()
    observed_scheme = observed_url.scheme.casefold()
    if requested_scheme == "https" and observed_scheme != "https":
        return False
    if requested_scheme == "http" and observed_scheme not in {"http", "https"}:
        return False
    if not _normalized_host(requested) or _normalized_host(requested) != _normalized_host(
        observed
    ):
        return False
    requested_port = requested_url.port
    observed_port = observed_url.port
    if requested_port not in {None, observed_port}:
        return False
    requested_path = (requested_url.path or "/").rstrip("/") or "/"
    observed_path = (observed_url.path or "/").rstrip("/") or "/"
    if requested_path != observed_path:
        return False
    requested_query = parse_qsl(requested_url.query, keep_blank_values=True)
    observed_query = list(parse_qsl(observed_url.query, keep_blank_values=True))
    return all(observed_query.count(pair) >= requested_query.count(pair) for pair in set(requested_query))


def _criterion(
    criterion_id: str,
    description: str,
    *,
    check: CriterionCheck = CriterionCheck.TRUTHY,
    expected: Any = None,
) -> GoalCriterion:
    return GoalCriterion(
        id=criterion_id,
        description=description,
        check=check,
        expected_value=expected,
    )


def _subgoal(
    subgoal_id: str,
    description: str,
    *criterion_ids: str,
    depends_on: tuple[str, ...] = (),
) -> GoalSubgoal:
    # ``produces`` holds the concrete criterion effects for this small runtime
    # increment. Contract artifacts still carry dataflow values themselves.
    return GoalSubgoal(
        id=subgoal_id,
        description=description,
        depends_on=list(depends_on),
        produces=list(criterion_ids),
    )


def _intent_kind(intent: GoalIntent) -> str:
    kind = getattr(intent, "kind", "generic")
    return str(getattr(kind, "value", kind)).casefold()


def _field(intent: GoalIntent, name: str, default: Any = None) -> Any:
    value = getattr(intent, name, default)
    return default if value is None else value


def _build_contract(
    intent: GoalIntent,
    original_goal: str,
) -> GoalContract:
    kind = _intent_kind(intent)

    if kind == "search_to_editor":
        return GoalContract(
            original_goal=original_goal,
            criteria=[
                _criterion("query_observed", "a consulta correta foi observada"),
                _criterion("results_observed", "resultados reais foram observados"),
                _criterion("first_title_extracted", "o primeiro título foi extraído"),
                _criterion("editor_open", "uma superfície de edição foi observada"),
                _criterion(
                    "text_present",
                    "o título extraído está presente no editor",
                    check=CriterionCheck.EQUALS,
                ),
            ],
            subgoals=[
                _subgoal(
                    "search",
                    "pesquisar e observar resultados",
                    "query_observed",
                    "results_observed",
                    "first_title_extracted",
                ),
                _subgoal("open_editor", "abrir editor", "editor_open", depends_on=("search",)),
                _subgoal("write_title", "escrever título extraído", "text_present", depends_on=("open_editor",)),
            ],
        )

    if kind == "conditional_site":
        return GoalContract(
            original_goal=original_goal,
            criteria=[
                _criterion("condition_observed", "a acessibilidade do site foi observada"),
                _criterion("editor_open", "uma superfície de edição foi observada"),
                _criterion(
                    "text_present",
                    "o texto do branch correto está presente",
                    check=CriterionCheck.EQUALS,
                ),
            ],
            subgoals=[
                _subgoal("observe_condition", "observar condição", "condition_observed"),
                _subgoal("open_editor", "abrir editor", "editor_open", depends_on=("observe_condition",)),
                _subgoal("execute_branch", "executar e verificar branch", "text_present", depends_on=("open_editor",)),
            ],
        )

    if kind == "open_and_write":
        expected_text = str(_field(intent, "text", ""))
        return GoalContract(
            original_goal=original_goal,
            criteria=[
                _criterion("editor_open", "a superfície de edição foi observada"),
                _criterion(
                    "text_present",
                    "o texto solicitado está presente",
                    check=CriterionCheck.EQUALS,
                    expected=expected_text,
                ),
            ],
            subgoals=[
                _subgoal("open_editor", "abrir editor", "editor_open"),
                _subgoal("write_text", "escrever e reler texto", "text_present", depends_on=("open_editor",)),
            ],
        )

    if kind == "named_browser_search":
        return GoalContract(
            original_goal=original_goal,
            criteria=[
                _criterion("browser_open", "o navegador solicitado foi observado"),
                _criterion("query_observed", "a pesquisa correta foi observada"),
            ],
            subgoals=[
                _subgoal("named_search", "abrir navegador e pesquisar", "browser_open", "query_observed")
            ],
        )

    if kind in {"search", "information"}:
        criteria = [
            _criterion("query_observed", "a consulta correta foi observada"),
            _criterion("results_observed", "resultados relevantes foram observados"),
        ]
        if kind == "information":
            criteria.append(
                _criterion("information_observed", "informação relevante foi observada")
            )
        return GoalContract(
            original_goal=original_goal,
            criteria=criteria,
            subgoals=[
                _subgoal(
                    "research",
                    "pesquisar e observar informação",
                    *(criterion.id for criterion in criteria),
                )
            ],
        )

    if kind == "open_capability":
        return GoalContract(
            original_goal=original_goal,
            criteria=[_criterion("capability_ready", "a ferramenta adequada foi observada")],
            subgoals=[_subgoal("resolve_and_open", "resolver e abrir capacidade", "capability_ready")],
        )

    if kind == "deterministic":
        plans = tuple(_field(intent, "plans", ()))
        criteria: list[GoalCriterion] = []
        subgoals: list[GoalSubgoal] = []
        for index, plan in enumerate(plans, start=1):
            criterion_id = f"deterministic_effect_{index}"
            check = CriterionCheck.TRUTHY
            expected: Any = None
            if plan.action == "type_text":
                check = CriterionCheck.EQUALS
                expected = plan.target
            elif plan.action == "open_url":
                check = CriterionCheck.EQUALS
                expected = _normalized_navigation_key(plan.target)
            criteria.append(
                _criterion(
                    criterion_id,
                    f"efeito observado da etapa determinística {plan.action}",
                    check=check,
                    expected=expected,
                )
            )
            subgoals.append(
                _subgoal(
                    f"deterministic_step_{index}",
                    f"executar e observar {plan.action}",
                    criterion_id,
                )
            )
        return GoalContract(
            original_goal=original_goal,
            criteria=criteria,
            subgoals=subgoals,
        )

    # An ambiguous goal must be decomposed into explicit criteria before any
    # physical action. A planner-selected action cannot define its own success
    # contract after the fact.
    return GoalContract(original_goal=original_goal, criteria=[], subgoals=[])


def _contract_from_decomposition(
    decomposition: StructuredGoalDecomposition,
    original_goal: str,
) -> GoalContract:
    check_by_name = {
        "truthy": CriterionCheck.TRUTHY,
        "equals": CriterionCheck.EQUALS,
        "contains": CriterionCheck.CONTAINS,
    }
    kind_by_name = {
        "observation": EvidenceKind.OBSERVATION,
        "readback": EvidenceKind.READBACK,
    }
    contract = GoalContract(
        original_goal=original_goal,
        criteria=[
            GoalCriterion(
                id=item.id,
                description=item.description,
                required=True,
                check=check_by_name[item.check],
                expected_value=item.expected_value,
                allowed_evidence_kinds=(kind_by_name[item.evidence_kind],),
            )
            for item in decomposition.criteria
        ],
        subgoals=[
            GoalSubgoal(
                id=item.id,
                description=item.description,
                depends_on=list(item.depends_on),
                produces=list(item.criterion_ids),
            )
            for item in decomposition.subgoals
        ],
    )
    contract.artifacts["decomposition"] = {
        "schema_version": decomposition.schema_version,
        "capabilities": [
            {
                "id": item.id,
                "description": item.description,
                "hint": item.hint,
            }
            for item in decomposition.capabilities
        ],
        "step_ids": [item.id for item in decomposition.steps],
    }
    return contract


def _decomposition_failure_contract(original_goal: str) -> GoalContract:
    return GoalContract(
        original_goal=original_goal,
        criteria=[
            _criterion(
                "structured_decomposition",
                "o objetivo precisa de decomposição estruturada antes da execução",
            )
        ],
        subgoals=[
            _subgoal(
                "decompose_goal",
                "decompor objetivo em capacidades, critérios e steps",
                "structured_decomposition",
            )
        ],
    )


def _refresh_subgoals(run: GoalRunState) -> None:
    known_criteria = {criterion.id: criterion for criterion in run.contract.criteria}
    for subgoal in run.contract.subgoals:
        dependencies_ready = all(
            next(
                (candidate.status is ProgressStatus.SATISFIED for candidate in run.contract.subgoals if candidate.id == dependency),
                False,
            )
            for dependency in subgoal.depends_on
        )
        effects = [known_criteria[item] for item in subgoal.produces if item in known_criteria]
        if effects and dependencies_ready and all(
            criterion.status is ProgressStatus.SATISFIED for criterion in effects
        ):
            subgoal.status = ProgressStatus.SATISFIED
        elif dependencies_ready:
            subgoal.status = ProgressStatus.RUNNING
        else:
            subgoal.status = ProgressStatus.PENDING


def _action_key(plan: Plan, prefix: str = "") -> str:
    target = " ".join(plan.target.split())
    return f"{prefix}:{plan.action}:{target}" if prefix else f"{plan.action}:{target}"


def _receipt_summary(receipt: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "action",
        "app",
        "executable",
        "argv",
        "pid",
        "window_changed",
        "window_id",
        "window_title",
        "verified",
        "characters",
        "input_method",
        "requested_url",
        "final_url",
        "title",
        "http_status",
        "path",
    )
    return {key: _safe_value(receipt[key]) for key in keys if key in receipt}


def _record_evidence(
    run: GoalRunState,
    spec: _EvidenceSpec,
    *,
    step_id: str,
) -> str:
    evidence_id = f"e-{uuid4().hex}"
    run.record_evidence(
        EvidenceRecord(
            id=evidence_id,
            criterion_id=spec.criterion_id,
            kind=spec.kind,
            source=spec.source,
            verified=spec.verified,
            observed_value=spec.observed_value,
            step_id=step_id,
            metadata=spec.metadata or {},
        )
    )
    return evidence_id


def _execute_observed_step(
    run: GoalRunState,
    executor: ActionExecutor,
    plan: Plan,
    *,
    strategy: str,
    provider: str | None,
    subgoal_id: str | None,
    criterion_ids: tuple[str, ...],
    observer: Callable[[dict[str, Any]], list[_EvidenceSpec]],
    action_key: str | None = None,
    fallback_from: str | None = None,
) -> dict[str, Any]:
    key = action_key or _action_key(plan)
    guard = run.can_attempt_step(key, strategy)
    if not guard:
        raise RuntimeError(guard.detail)

    decision = evaluate_plan(plan, desktop_enabled=executor.desktop_enabled)
    if not decision.allowed:
        raise PermissionError(decision.reason)

    step_id = f"s-{uuid4().hex}"
    verifier = GoalVerifier()
    verifier.evaluate(run)
    satisfied_before = {
        criterion.id
        for criterion in run.contract.criteria
        if criterion.status is ProgressStatus.SATISFIED
    }

    try:
        receipt = executor.execute(plan)
    except Exception as exc:
        if _is_safety_interrupt(exc):
            raise
        run.record_step(
            GoalStep(
                id=step_id,
                action_key=key,
                strategy=strategy,
                status=GoalStepStatus.FAILED,
                provider=provider,
                subgoal_id=subgoal_id,
                fallback_from=fallback_from,
                made_progress=False,
                error=f"{type(exc).__name__}: {exc}",
                metadata={"action": plan.action, "target": plan.target},
            )
        )
        raise

    try:
        specs = observer(receipt)
    except Exception as exc:
        if _is_safety_interrupt(exc):
            raise
        run.record_step(
            GoalStep(
                id=step_id,
                action_key=key,
                strategy=strategy,
                status=GoalStepStatus.SUCCEEDED,
                provider=provider,
                subgoal_id=subgoal_id,
                fallback_from=fallback_from,
                made_progress=False,
                error=f"observation {type(exc).__name__}: {exc}",
                metadata={
                    "action": plan.action,
                    "target": plan.target,
                    "receipt": _receipt_summary(receipt),
                },
            )
        )
        raise

    step = GoalStep(
        id=step_id,
        action_key=key,
        strategy=strategy,
        status=GoalStepStatus.SUCCEEDED,
        provider=provider,
        subgoal_id=subgoal_id,
        fallback_from=fallback_from,
        made_progress=False,
        metadata={
            "action": plan.action,
            "target": plan.target,
            "policy_reason": decision.reason,
            "receipt": _receipt_summary(receipt),
        },
    )
    run.record_step(step)

    for criterion_id in criterion_ids:
        _record_evidence(
            run,
            _EvidenceSpec(
                criterion_id=criterion_id,
                kind=EvidenceKind.EXECUTION_RECEIPT,
                source=plan.action,
                verified=bool(receipt.get("verified")),
                observed_value=_receipt_summary(receipt),
                metadata={"policy_reason": decision.reason},
            ),
            step_id=step_id,
        )

    for spec in specs:
        _record_evidence(run, spec, step_id=step_id)

    verifier.evaluate(run)
    satisfied_after = {
        criterion.id
        for criterion in run.contract.criteria
        if criterion.status is ProgressStatus.SATISFIED
    }
    step.made_progress = bool(satisfied_after - satisfied_before)
    if step.made_progress:
        run.consecutive_no_progress = 0
    _refresh_subgoals(run)
    return receipt


def _observe_browser_with_retry(executor: ActionExecutor) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            snapshot = executor.observe_browser()
            if snapshot.get("url"):
                return snapshot
        except Exception as exc:
            if _is_safety_interrupt(exc) or isinstance(exc, PermissionError):
                raise
            last_error = exc
        if attempt < 2:
            time.sleep(0.35)
    if last_error is not None:
        raise last_error
    raise RuntimeError("A página atual não produziu uma observação estruturada.")


def _observe_application_with_retry(
    executor: ActionExecutor,
    app_id: str,
    *,
    pid: int | None,
    expected_argument: str | None = None,
    ready: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for attempt in range(4):
        last = executor.observe_application(
            app_id,
            pid=pid,
            expected_argument=expected_argument,
        )
        if (ready(last) if ready is not None else bool(last.get("verified"))):
            return last
        if attempt < 3:
            time.sleep(0.35)
    return last


def _query_tokens(query: str) -> tuple[str, ...]:
    stopwords = {
        "a",
        "as",
        "de",
        "da",
        "das",
        "do",
        "dos",
        "e",
        "o",
        "os",
        "para",
        "por",
        "sobre",
        "um",
        "uma",
    }
    return tuple(
        token
        for token in _normalized(query).split()
        if token not in stopwords and len(token) > 1
    )


def _browser_query_matches(snapshot: dict[str, Any], query: str) -> bool:
    parsed = urlparse(str(snapshot.get("url") or ""))
    url_queries = parse_qs(parsed.query)
    encoded_query = " ".join(
        unquote_plus(value)
        for key in ("q", "query", "p", "text")
        for value in url_queries.get(key, [])
    )
    observed = _normalized(
        " ".join(
            (
                encoded_query,
                str(snapshot.get("title") or ""),
                str(snapshot.get("text") or "")[:1600],
            )
        )
    )
    tokens = _query_tokens(query)
    return bool(tokens) and all(token in observed for token in tokens)


def _browser_page_is_loaded(snapshot: dict[str, Any]) -> bool:
    status = snapshot.get("http_status")
    status_ok = status is None or (isinstance(status, int) and 200 <= status < 400)
    return bool(snapshot.get("url") and status_ok and (snapshot.get("title") or snapshot.get("text")))


def _search_url(engine: str, query: str) -> str:
    encoded = quote_plus(query.strip())
    if engine == "bing":
        return f"https://www.bing.com/search?q={encoded}"
    if engine == "google":
        return f"https://www.google.com/search?q={encoded}"
    return f"https://duckduckgo.com/?q={encoded}"


def _search_engines(intent: GoalIntent) -> tuple[str, ...]:
    requested_url = str(_field(intent, "url", ""))
    host = (urlparse(requested_url if "://" in requested_url else f"https://{requested_url}").hostname or "").casefold()
    if "google." in host:
        return ("google", "bing", "duckduckgo")
    if "duckduckgo." in host:
        return ("duckduckgo", "bing", "google")
    if "bing." in host:
        return ("bing", "google", "duckduckgo")
    # Bing is the currently observed healthy structured provider on this host.
    return ("bing", "google", "duckduckgo")


def _run_structured_search(
    run: GoalRunState,
    executor: ActionExecutor,
    intent: GoalIntent,
    query: str,
    *,
    need_title: bool,
    information: bool,
) -> dict[str, Any]:
    last_error: Exception | None = None

    for engine in _search_engines(intent):
        url = _search_url(engine, query)
        plan = Plan("open_url", url)
        attempt_snapshot: dict[str, Any] = {}
        attempt_verified = False

        def observer(_: dict[str, Any]) -> list[_EvidenceSpec]:
            nonlocal attempt_snapshot, attempt_verified
            attempt_snapshot = _observe_browser_with_retry(executor)
            page_loaded = _browser_page_is_loaded(attempt_snapshot)
            expected_host = _normalized_host(url)
            observed_host = _normalized_host(str(attempt_snapshot.get("url") or ""))
            host_match = bool(
                expected_host
                and expected_host == observed_host
                and _navigation_matches(
                    url,
                    str(attempt_snapshot.get("url") or ""),
                )
            )
            query_match = bool(
                page_loaded
                and host_match
                and _browser_query_matches(attempt_snapshot, query)
            )
            results = attempt_snapshot.get("search_results") or []
            first_title = attempt_snapshot.get("first_result_title")
            coherent_results = bool(query_match and results)
            coherent_title = bool(coherent_results and first_title)
            useful = first_title or (attempt_snapshot.get("text") or "")[:800]
            coherent_information = bool(coherent_results and useful)
            attempt_verified = bool(
                query_match
                and coherent_results
                and (not need_title or coherent_title)
                and (not information or coherent_information)
            )
            attempt_id = f"{engine}:{url}"
            specs = [
                _EvidenceSpec(
                    "query_observed",
                    EvidenceKind.OBSERVATION,
                    "browser.playwright_dom",
                    bool(query_match),
                    bool(query_match),
                    {
                        "attempt": attempt_id,
                        "engine": engine,
                        "url": attempt_snapshot.get("url"),
                        "title": attempt_snapshot.get("title"),
                        "host_match": host_match,
                    },
                ),
                _EvidenceSpec(
                    "results_observed",
                    EvidenceKind.OBSERVATION,
                    "browser.search_results",
                    coherent_results,
                    results,
                    {
                        "attempt": attempt_id,
                        "engine": engine,
                        "count": len(results),
                        "query_match": bool(query_match),
                        "host_match": host_match,
                    },
                ),
            ]
            if need_title:
                specs.append(
                    _EvidenceSpec(
                        "first_title_extracted",
                        EvidenceKind.OBSERVATION,
                        "browser.first_result",
                        coherent_title,
                        first_title,
                        {
                            "attempt": attempt_id,
                            "url": attempt_snapshot.get("first_result_url"),
                            "query_match": bool(query_match),
                            "results_observed": bool(results),
                        },
                    )
                )
            if information:
                specs.append(
                    _EvidenceSpec(
                        "information_observed",
                        EvidenceKind.OBSERVATION,
                        "browser.visible_text",
                        coherent_information,
                        useful,
                        {
                            "attempt": attempt_id,
                            "result_url": attempt_snapshot.get("first_result_url"),
                            "query_match": bool(query_match),
                        },
                    )
                )
            return specs

        criterion_ids = ["query_observed", "results_observed"]
        if need_title:
            criterion_ids.append("first_title_extracted")
        if information:
            criterion_ids.append("information_observed")
        try:
            _execute_observed_step(
                run,
                executor,
                plan,
                strategy=f"web.search:{engine}",
                provider=engine,
                subgoal_id="search" if need_title else "research",
                criterion_ids=tuple(criterion_ids),
                observer=observer,
                fallback_from=(last_error.__class__.__name__ if last_error else None),
            )
        except Exception as exc:
            if _is_safety_interrupt(exc) or isinstance(exc, PermissionError):
                raise
            last_error = exc
            if run.consecutive_no_progress >= run.budget.max_no_progress_steps:
                run.acknowledge_replan()
            continue

        if attempt_verified:
            return attempt_snapshot
        last_error = RuntimeError(f"{engine} não produziu resultados estruturados verificáveis")
        run.acknowledge_replan()

    raise last_error or RuntimeError("Nenhum mecanismo produziu uma busca verificável.")


def _resolve_capability(
    resolver: CapabilityResolver,
    capability: str,
    hint: str | None,
    *,
    strict_hint: bool = False,
) -> ResolvedCapability:
    resolve = resolver.resolve
    parameters = inspect.signature(resolve).parameters
    if strict_hint and "strict_hint" in parameters:
        resolved = resolve(capability, hint=hint or None, strict_hint=True)
    else:
        resolved = resolve(capability, hint=hint or None)

    if strict_hint and hint:
        expected = _normalized(hint)
        identities = _normalized(
            " ".join(
                (
                    resolved.app_id,
                    resolved.display_name,
                    Path(resolved.executable).name,
                )
            )
        )
        alias_markers = {
            "brave browser": ("brave",),
            "brave": ("brave",),
            "firefox": ("firefox",),
            "visual studio code": ("visual studio code", " code "),
            "vs code": ("visual studio code", " code "),
            "vscode": ("visual studio code", " code "),
            "google chrome": ("google chrome",),
            "chromium": ("chromium",),
        }
        markers = alias_markers.get(expected, (expected,))
        padded_identities = f" {identities} "
        if not any(marker in padded_identities for marker in markers):
            raise RuntimeError(
                f"A aplicação resolvida {resolved.display_name!r} não corresponde "
                f"ao aplicativo explicitamente solicitado {hint!r}."
            )
    return resolved


def _open_capability(
    run: GoalRunState,
    executor: ActionExecutor,
    resolved: ResolvedCapability,
    *,
    criterion_id: str,
    subgoal_id: str,
    fallback_from: str | None = None,
) -> dict[str, Any]:
    plan = Plan("open_app", resolved.open_app_target)

    def observer(receipt: dict[str, Any]) -> list[_EvidenceSpec]:
        observed = _observe_application_with_retry(
            executor,
            resolved.startup_wm_class or resolved.app_id,
            pid=receipt.get("pid") if isinstance(receipt.get("pid"), int) else None,
            ready=lambda item: bool(
                item.get("verified")
                and item.get("window_id")
                and item.get("class_identity_observed")
            ),
        )
        window_observed = bool(
            observed.get("window_id")
            and observed.get("window_class")
            and observed.get("class_identity_observed")
        )
        return [
            _EvidenceSpec(
                criterion_id,
                EvidenceKind.OBSERVATION,
                "desktop.x11_proc",
                bool(observed.get("verified") and window_observed),
                bool(observed.get("identity_observed") and window_observed),
                {**_safe_value(observed), "window_observed": window_observed},
            )
        ]

    receipt = _execute_observed_step(
        run,
        executor,
        plan,
        strategy=f"capability:{resolved.capability}:{resolved.app_id}",
        provider=resolved.source,
        subgoal_id=subgoal_id,
        criterion_ids=(criterion_id,),
        observer=observer,
        fallback_from=fallback_from,
    )
    run.contract.artifacts[f"{resolved.capability}.provider"] = {
        "app_id": resolved.app_id,
        "display_name": resolved.display_name,
        "executable": resolved.executable,
        "source": resolved.source,
        "startup_wm_class": resolved.startup_wm_class,
    }
    return receipt


def _open_capability_with_fallback(
    run: GoalRunState,
    executor: ActionExecutor,
    resolver: CapabilityResolver,
    capability: str,
    hint: str | None,
    *,
    criterion_id: str,
    subgoal_id: str,
    allow_fallback: bool = True,
    strict_hint: bool = False,
) -> ResolvedCapability:
    """Resolve one installed provider and require observation after one launch.

    Resolver discovery may choose an installed fallback before execution. Once
    ``open_app`` is entered, however, neither a raised exception nor a failed
    observation proves that no window/process was created. Launching a second
    app would replay a non-idempotent physical effect, so this boundary fails
    closed after the first attempt.
    """

    primary = _resolve_capability(
        resolver,
        capability,
        hint,
        strict_hint=strict_hint,
    )
    del allow_fallback  # kept for API compatibility; resolution already ranks fallbacks.
    try:
        _open_capability(
            run,
            executor,
            primary,
            criterion_id=criterion_id,
            subgoal_id=subgoal_id,
        )
    except Exception as exc:
        if _is_safety_interrupt(exc) or isinstance(exc, PermissionError):
            raise
        raise RuntimeError(
            f"{primary.display_name} não pôde ser comprovado após uma única "
            "tentativa física; nenhum segundo aplicativo será lançado"
        ) from exc

    verdict = GoalVerifier().evaluate(run)
    if criterion_id in verdict.pending_criteria:
        raise RuntimeError(
            f"{primary.display_name} abriu, mas a capacidade não foi observada"
        )
    return primary


def _type_and_readback(
    run: GoalRunState,
    executor: ActionExecutor,
    text: str,
    *,
    criterion_id: str,
    subgoal_id: str,
) -> dict[str, Any]:
    criterion = run.contract.criterion(criterion_id)
    criterion.check = CriterionCheck.EQUALS
    criterion.expected_value = text
    plan = Plan("type_text", text)

    def observer(_: dict[str, Any]) -> list[_EvidenceSpec]:
        observed: dict[str, Any] = {}
        for attempt in range(3):
            observed = executor.read_active_text(max_chars=max(4096, len(text) + 64))
            if observed.get("verified") and observed.get("text") is not None:
                break
            if attempt < 2:
                time.sleep(0.25)
        return [
            _EvidenceSpec(
                criterion_id,
                EvidenceKind.READBACK,
                str(observed.get("source") or "desktop.readback"),
                bool(observed.get("verified")),
                observed.get("text"),
                {
                    "window_id": observed.get("window_id"),
                    "window_title": observed.get("window_title"),
                    "characters": observed.get("characters"),
                    "clipboard_restored": observed.get("clipboard_restored"),
                },
            )
        ]

    return _execute_observed_step(
        run,
        executor,
        plan,
        strategy="desktop.type-and-readback",
        provider="pyautogui+atspi",
        subgoal_id=subgoal_id,
        criterion_ids=(criterion_id,),
        observer=observer,
    )


def _probe_url(url: str) -> dict[str, Any]:
    try:
        response = httpx.get(url, follow_redirects=True, timeout=12)
    except httpx.HTTPError as exc:
        return {
            "accessible": False,
            "source": "httpx-probe",
            "verified": True,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "accessible": 200 <= response.status_code < 400,
        "source": "httpx-probe",
        "verified": True,
        "status": response.status_code,
        "final_url": str(response.url),
    }


def _result_payload(
    run: GoalRunState,
    verdict_reason: str,
    *,
    resolved_goal: str,
    resolution: ContextResolution | None,
) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    for item in run.evidence:
        criterion = run.contract.criterion(item.criterion_id)
        if item.kind is EvidenceKind.READBACK:
            observed_value: Any = {
                **_private_text_summary(item.observed_value, salt=run.goal_id),
                "matched_expected": GoalVerifier._matches(criterion, item),
            }
        else:
            observed_value = _public_value(item.observed_value)
        evidence.append(
            {
                "id": _public_string(item.id),
                "criterion_id": _public_string(item.criterion_id),
                "step_id": _public_string(item.step_id) if item.step_id else None,
                "kind": item.kind.value,
                "source": _public_string(item.source),
                "verified": item.verified,
                "observed_value": observed_value,
                "metadata": _public_value(item.metadata),
                "created_at": item.created_at.isoformat(),
            }
        )
    raw_metrics = run.metrics().as_dict()
    metrics = _public_value(raw_metrics)
    if isinstance(raw_metrics.get("final_reason"), str):
        metrics["final_reason"] = _public_run_string(
            run, raw_metrics["final_reason"]
        )
    planner_steps = [step for step in run.steps if step.strategy.startswith("planner:")]
    decomposition_metadata = run.contract.artifacts.get("decomposition")
    decomposition_provider = (
        decomposition_metadata.get("provider")
        if isinstance(decomposition_metadata, dict)
        else None
    )
    if isinstance(decomposition_metadata, dict):
        planner_provider = decomposition_provider
    elif planner_steps:
        planner_provider = planner_steps[-1].provider
    else:
        planner_provider = "deterministic"
    decomposition_fallbacks = (
        decomposition_metadata.get("fallbacks", [])
        if isinstance(decomposition_metadata, dict)
        else []
    )
    decomposition_route = (
        decomposition_metadata.get("route")
        if isinstance(decomposition_metadata, dict)
        else None
    )
    attempted_decomposition_providers = {
        str(item) for item in decomposition_fallbacks
    }
    if decomposition_provider:
        attempted_decomposition_providers.add(str(decomposition_provider))
    if attempted_decomposition_providers:
        metrics["providers"] = sorted(
            set(metrics.get("providers", ())).union(attempted_decomposition_providers)
        )
        metrics["fallbacks"] = max(
            int(metrics.get("fallbacks", 0)),
            max(0, len(attempted_decomposition_providers) - 1),
        )
    public_artifacts = _public_value(run.contract.artifacts)
    if isinstance(public_artifacts, dict):
        for private_key in ("branch_text", "written_text", "written.text"):
            if private_key in run.contract.artifacts:
                public_artifacts[private_key] = _private_text_summary(
                    run.contract.artifacts[private_key],
                    salt=run.goal_id,
                )
    return {
        "action": "goal",
        "goal_id": _public_string(run.goal_id),
        "task_id": _public_string(run.task_id),
        "status": run.status.value,
        "goal_completed": run.status is GoalRunStatus.SUCCEEDED,
        "verified": run.status is GoalRunStatus.SUCCEEDED,
        "completion": _public_run_string(run, verdict_reason),
        "original_goal": _public_goal_string(run, run.contract.original_goal),
        "resolved_goal": _public_goal_string(run, resolved_goal),
        "context_resolution": {
            "changed": bool(resolution and resolution.changed),
            "artifacts": [
                {
                    "kind": item.kind.value,
                    "value": _private_text_summary(item.value, salt=run.goal_id),
                    "origin_task_id": _public_string(item.origin_task_id),
                    "timestamp": item.timestamp.isoformat(),
                }
                for item in (resolution.artifacts if resolution else ())
            ],
        },
        "steps": [
            {
                "step": index,
                "id": _public_string(step.id),
                "action_key": (
                    "type_text:[redacted]"
                    if step.metadata.get("action") == "type_text"
                    else _public_string(step.action_key)
                ),
                "action": _public_value(step.metadata.get("action")),
                "target": (
                    _private_text_summary(
                        step.metadata.get("target"),
                        salt=run.goal_id,
                    )
                    if step.metadata.get("action") == "type_text"
                    else _public_value(step.metadata.get("target"))
                ),
                "strategy": _public_string(step.strategy),
                "provider": _public_string(step.provider) if step.provider else None,
                "fallback_from": (
                    _public_string(step.fallback_from) if step.fallback_from else None
                ),
                "status": step.status.value,
                "made_progress": step.made_progress,
                "subgoal_id": (
                    _public_string(step.subgoal_id) if step.subgoal_id else None
                ),
                "evidence_ids": [_public_string(item) for item in step.evidence_ids],
                "error": _public_run_string(run, step.error) if step.error else None,
                "receipt": _public_value(step.metadata.get("receipt")),
            }
            for index, step in enumerate(run.steps, start=1)
        ],
        "subgoals": [
            {
                "id": _public_string(item.id),
                "description": _public_run_string(run, item.description),
                "status": item.status.value,
                "depends_on": [_public_string(value) for value in item.depends_on],
            }
            for item in run.contract.subgoals
        ],
        "criteria": [
            {
                "id": _public_string(item.id),
                "description": _public_run_string(run, item.description),
                "required": item.required,
                "check": item.check.value,
                "expected_value": (
                    _private_text_summary(item.expected_value, salt=run.goal_id)
                    if EvidenceKind.READBACK in item.allowed_evidence_kinds
                    and isinstance(item.expected_value, str)
                    else _public_value(item.expected_value)
                ),
                "status": item.status.value,
                "evidence_ids": [_public_string(value) for value in item.evidence_ids],
            }
            for item in run.contract.criteria
        ],
        "evidence": evidence,
        "artifacts": public_artifacts,
        "metrics": metrics,
        "planner_provider": (
            _public_string(str(planner_provider)) if planner_provider is not None else None
        ),
        "planner_route": (
            _public_string(str(decomposition_route))
            if decomposition_route
            else "goal-runtime"
        ),
        "planner_fallbacks": sorted(
            _public_string(value)
            for value in {
                step.fallback_from
                for step in run.steps
                if step.fallback_from
            }.union(str(item) for item in decomposition_fallbacks)
        ),
        "planner_trace": [
            {
                "decision": index,
                "provider": _public_string(step.provider) if step.provider else None,
                "route": _public_string(step.strategy),
                "fallbacks": (
                    [_public_string(step.fallback_from)] if step.fallback_from else []
                ),
                "action": _public_value(step.metadata.get("action")),
                "target": (
                    _private_text_summary(step.metadata.get("target"), salt=run.goal_id)
                    if step.metadata.get("action") == "type_text"
                    else _public_value(step.metadata.get("target"))
                ),
            }
            for index, step in enumerate(run.steps, start=1)
        ],
    }


def _finalize(
    run: GoalRunState,
    *,
    resolved_goal: str,
    resolution: ContextResolution | None,
) -> dict[str, Any]:
    verifier = GoalVerifier()
    verdict = verifier.finalize(run)
    _refresh_subgoals(run)
    if verdict.complete:
        return _result_payload(
            run,
            verdict.reason,
            resolved_goal=resolved_goal,
            resolution=resolution,
        )

    if verdict.status is GoalRunStatus.FAILED:
        run.failure_reason = verdict.reason
    else:
        pending = ", ".join(verdict.pending_criteria) or "unknown"
        run.failure_reason = f"GoalVerifier recusou conclusão; critérios pendentes: {pending}"
    failed_verdict = verifier.finalize(run)
    _refresh_subgoals(run)
    result = _result_payload(
        run,
        failed_verdict.reason,
        resolved_goal=resolved_goal,
        resolution=resolution,
    )
    raise GoalExecutionFailed(run.failure_reason, result)


def _remember_context(
    context: SessionContext | None,
    run: GoalRunState,
    intent: GoalIntent,
) -> None:
    if context is None:
        return
    values: dict[ArtifactKind | str, str | None] = {}
    query = str(_field(intent, "query", "")).strip()
    if query:
        values[ArtifactKind.SUBJECT] = query
        normalized_query = _normalized(query)
        words = [word for word in query.split() if _normalized(word) not in {"da", "de", "do", "e"}]
        likely_location = (
            "sao " in normalized_query
            or "cidade" in normalized_query
            or (len(words) >= 2 and sum(word[:1].isupper() for word in words) >= 2)
        )
        if likely_location and not any(
            marker in normalized_query for marker in ("previsao", "tempo", "significado")
        ):
            values[ArtifactKind.LOCATION] = query

    url = str(_field(intent, "url", "")).strip()
    if url:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        values[ArtifactKind.SITE] = parsed.hostname
    browser = run.contract.artifacts.get("browser")
    editor = run.contract.artifacts.get("editor")
    first_title = run.contract.artifacts.get("first_result_title")
    values[ArtifactKind.BROWSER] = str(browser) if browser else None
    values[ArtifactKind.EDITOR] = str(editor) if editor else None
    values[ArtifactKind.RESULT] = str(first_title) if first_title else None
    context.remember_many(
        run.task_id,
        {
            kind: value
            for kind, value in values.items()
            if value is None or not contains_sensitive_data(value)
        },
    )


def _planner_snapshot(planner: Planner) -> dict[str, Any]:
    errors = getattr(planner, "last_errors", None) or {}
    return {
        "provider": getattr(planner, "last_provider", None) or "deterministic",
        "route": getattr(planner, "last_route", None) or "planner",
        "fallbacks": sorted(str(name) for name in errors),
    }


def _planner_prompt(
    objective: str,
    run: GoalRunState,
    *,
    note: str | None = None,
) -> str:
    steps = [
        {
            "action": step.metadata.get("action"),
            "target": step.metadata.get("target"),
            "status": step.status.value,
            "made_progress": step.made_progress,
            "error": step.error,
        }
        for step in run.steps
    ]
    pending = [
        criterion.id
        for criterion in run.contract.criteria
        if criterion.required and criterion.status is not ProgressStatus.SATISFIED
    ]
    return (
        f"OBJETIVO ORIGINAL:\n{objective}\n\n"
        f"ETAPAS JÁ EXECUTADAS E OBSERVADAS:\n{_safe_value(steps)}\n\n"
        f"CRITÉRIOS PENDENTES:\n{pending}\n\n"
        + (f"NOTA DE REPLANEJAMENTO:\n{note}\n\n" if note else "")
        + "Decida somente a PRÓXIMA ação necessária. Não repita ação já executada. "
        "Use finish somente se todos os efeitos estiverem observados; finish será "
        "avaliado pelo GoalVerifier e não possui autoridade própria."
    )


def _add_plan_criterion(run: GoalRunState, plan: Plan, index: int) -> tuple[str, str]:
    criterion_id = f"planned_effect_{index}"
    subgoal_id = f"planned_step_{index}"
    check = CriterionCheck.TRUTHY
    expected: Any = None
    if plan.action == "type_text":
        check = CriterionCheck.EQUALS
        expected = plan.target
    elif plan.action == "open_url":
        check = CriterionCheck.CONTAINS
        expected = urlparse(plan.target).hostname or plan.target
    run.contract.criteria.append(
        _criterion(
            criterion_id,
            f"efeito observado da ação planejada {plan.action}",
            check=check,
            expected=expected,
        )
    )
    run.contract.subgoals.append(
        _subgoal(subgoal_id, f"executar e observar {plan.action}", criterion_id)
    )
    return criterion_id, subgoal_id


def _generic_plan_observer(
    executor: ActionExecutor,
    plan: Plan,
    criterion_id: str,
) -> Callable[[dict[str, Any]], list[_EvidenceSpec]]:
    def observer(receipt: dict[str, Any]) -> list[_EvidenceSpec]:
        if plan.action == "open_url":
            snapshot = _observe_browser_with_retry(executor)
            loaded = _browser_page_is_loaded(snapshot)
            observed_url = str(snapshot.get("url") or "")
            target_matches = _navigation_matches(plan.target, observed_url)
            expected_key = _normalized_navigation_key(plan.target)
            observed_key = (
                expected_key
                if target_matches
                else _normalized_navigation_key(observed_url)
            )
            return [
                _EvidenceSpec(
                    criterion_id,
                    EvidenceKind.OBSERVATION,
                    "browser.playwright_dom",
                    bool(loaded and target_matches),
                    observed_key,
                    {
                        "requested_url": plan.target,
                        "observed_url": snapshot.get("url"),
                        "title": snapshot.get("title"),
                        "target_matches": target_matches,
                    },
                )
            ]
        if plan.action == "open_app":
            app_id = shlex.split(plan.target)[0] if shlex.split(plan.target) else plan.target
            expected_argument = shlex.split(plan.target)[1] if len(shlex.split(plan.target)) > 1 else None
            observed = _observe_application_with_retry(
                executor,
                app_id,
                pid=receipt.get("pid") if isinstance(receipt.get("pid"), int) else None,
                expected_argument=expected_argument,
            )
            argument_ready = (
                expected_argument is None
                or observed.get("argument_observed") is True
            )
            return [
                _EvidenceSpec(
                    criterion_id,
                    EvidenceKind.OBSERVATION,
                    "desktop.x11_proc",
                    bool(observed.get("verified") and argument_ready),
                    bool(observed.get("identity_observed") and argument_ready),
                    _safe_value(observed),
                )
            ]
        if plan.action == "type_text":
            observed = executor.read_active_text(max_chars=max(4096, len(plan.target) + 64))
            return [
                _EvidenceSpec(
                    criterion_id,
                    EvidenceKind.READBACK,
                    str(observed.get("source") or "desktop.readback"),
                    bool(observed.get("verified")),
                    observed.get("text"),
                    _safe_value(observed),
                )
            ]
        if plan.action == "active_window":
            observed = executor.observe_active_window()
            return [
                _EvidenceSpec(
                    criterion_id,
                    EvidenceKind.OBSERVATION,
                    "desktop.active_window",
                    bool(observed.get("verified")),
                    observed.get("title"),
                    _safe_value(observed),
                )
            ]
        if plan.action == "capture_screen":
            path = Path(str(receipt.get("path") or ""))
            exists = bool(path.is_file())
            return [
                _EvidenceSpec(
                    criterion_id,
                    EvidenceKind.OBSERVATION,
                    "filesystem.stat",
                    exists,
                    exists,
                    {"path": str(path)},
                )
            ]
        # No observer exists for this effect yet. The receipt is still recorded,
        # but the criterion deliberately remains pending.
        return [
            _EvidenceSpec(
                criterion_id,
                EvidenceKind.OBSERVATION,
                "observer.unavailable",
                False,
                None,
                {"action": plan.action},
            )
        ]

    return observer


def _structured_navigation_observer(
    executor: ActionExecutor,
    step: StructuredGoalStep,
    criterion_specs: dict[str, Any],
    plan: Plan,
    snapshot_holder: dict[str, Any],
) -> Callable[[dict[str, Any]], list[_EvidenceSpec]]:
    def observer(_: dict[str, Any]) -> list[_EvidenceSpec]:
        snapshot = _observe_browser_with_retry(executor)
        snapshot_holder.clear()
        snapshot_holder.update(snapshot)
        loaded = _browser_page_is_loaded(snapshot)
        target_url = urlparse(plan.target)
        target_queries = parse_qs(target_url.query)
        target_query = " ".join(
            unquote_plus(value)
            for name in ("q", "query", "p", "text")
            for value in target_queries.get(name, [])
        ).strip()
        target_observed = bool(
            loaded
            and _navigation_matches(plan.target, str(snapshot.get("url") or ""))
            and (
                _browser_query_matches(snapshot, target_query)
                if target_query
                else True
            )
        )
        observed_by_kind: dict[str, Any] = {
            "browser.url": snapshot.get("url"),
            "browser.title": snapshot.get("title"),
            "browser.text": snapshot.get("text"),
            "browser.search_results": snapshot.get("search_results") or [],
        }
        return [
            _EvidenceSpec(
                criterion_id,
                EvidenceKind.OBSERVATION,
                f"browser.playwright_dom:{spec.observable}",
                bool(target_observed and observed_by_kind[spec.observable]),
                observed_by_kind[spec.observable],
                {
                    "structured_step_id": step.id,
                    "requested_url": plan.target,
                    "observed_url": snapshot.get("url"),
                    "target_query": target_query or None,
                    "target_observed": target_observed,
                },
            )
            for criterion_id in step.criterion_ids
            for spec in (criterion_specs[criterion_id],)
        ]

    return observer


def _store_structured_artifacts(
    run: GoalRunState,
    step: StructuredGoalStep,
    *,
    snapshot: dict[str, Any] | None = None,
    resolved_capability: ResolvedCapability | None = None,
    receipt: dict[str, Any] | None = None,
) -> None:
    values = {
        "first_result_title": (snapshot or {}).get("first_result_title"),
        "first_result_url": (snapshot or {}).get("first_result_url"),
        "browser_url": (snapshot or {}).get("url"),
        "browser_title": (snapshot or {}).get("title"),
        "browser_text": str((snapshot or {}).get("text") or "")[:800] or None,
        "application_id": resolved_capability.app_id if resolved_capability else None,
        "application_name": (
            resolved_capability.display_name if resolved_capability else None
        ),
        "screenshot_path": (receipt or {}).get("path"),
        "written_text": (receipt or {}).get("text"),
    }
    aliases = {
        "browser.url": "browser_url",
        "browser.title": "browser_title",
        "browser.text": "browser_text",
        "application.id": "application_id",
        "application.name": "application_name",
        "screenshot.path": "screenshot_path",
        "written.text": "written_text",
    }
    for artifact_id in step.produces:
        source_id = aliases.get(artifact_id, artifact_id)
        value = values.get(source_id)
        if value is None or value == "":
            raise RuntimeError(
                f"Step estruturado {step.id} não produziu artifact {artifact_id!r}."
            )
        run.contract.artifacts[artifact_id] = _safe_value(value)


def _run_recoverable_step(
    run: GoalRunState,
    operation: Callable[[], dict[str, Any]],
    *,
    action_key: str,
    strategy: str,
    retry_safe: bool = True,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for _attempt in range(run.budget.max_retries_per_strategy + 1):
        try:
            return operation()
        except Exception as exc:
            if _is_safety_interrupt(exc) or isinstance(exc, PermissionError):
                raise
            last_error = exc
            # Once a non-idempotent backend was entered, an exception cannot
            # prove that it produced no partial physical effect. Never type or
            # launch again blindly; reconciliation must be read-only.
            if not retry_safe:
                raise
            # A successful physical action is never replayed merely because its
            # observer failed. Observers already have their own read-only retry.
            if run.action_was_completed(action_key):
                raise
            if run.consecutive_no_progress >= run.budget.max_no_progress_steps:
                run.acknowledge_replan()
            guard = run.can_attempt_step(action_key, strategy)
            if not guard:
                raise RuntimeError(guard.detail) from exc
    raise last_error or RuntimeError(f"Step {action_key!r} falhou sem diagnóstico.")


def _execute_structured_decomposition(
    run: GoalRunState,
    executor: ActionExecutor,
    resolver: CapabilityResolver,
    decomposition: StructuredGoalDecomposition,
) -> None:
    capabilities = {item.id: item for item in decomposition.capabilities}
    criterion_specs = {item.id: item for item in decomposition.criteria}
    structured_subgoals = {item.id: item for item in decomposition.subgoals}
    completed_steps: set[str] = set()

    for structured_step in decomposition.steps:
        missing_dependencies = set(structured_step.depends_on) - completed_steps
        if missing_dependencies:
            raise RuntimeError(
                f"Step {structured_step.id} possui dependências não comprovadas: "
                f"{sorted(missing_dependencies)}"
            )
        _refresh_subgoals(run)
        subgoal = structured_subgoals[structured_step.subgoal_id]
        unsatisfied_subgoals = [
            dependency
            for dependency in subgoal.depends_on
            if next(
                (
                    item.status is not ProgressStatus.SATISFIED
                    for item in run.contract.subgoals
                    if item.id == dependency
                ),
                True,
            )
        ]
        if unsatisfied_subgoals:
            raise RuntimeError(
                f"Step {structured_step.id} não pode iniciar antes dos subgoals: "
                f"{unsatisfied_subgoals}"
            )

        for criterion_id in structured_step.criterion_ids:
            spec = criterion_specs[criterion_id]
            run.contract.criterion(criterion_id).expected_value = resolve_goal_value(
                spec.expected_value,
                artifacts=run.contract.artifacts,
            )

        snapshot: dict[str, Any] = {}
        receipt: dict[str, Any] = {}
        resolved: ResolvedCapability | None = None

        if structured_step.operation == "open_capability":
            capability = capabilities[structured_step.capability_id]
            if len(structured_step.criterion_ids) != 1:
                raise RuntimeError("open_capability exige exatamente um critério observável")
            primary = _resolve_capability(resolver, capability.id, capability.hint)
            plan_from_goal_step(
                structured_step,
                resolved_capability_target=primary.open_app_target,
                artifacts=run.contract.artifacts,
                desktop_enabled=executor.desktop_enabled,
            )
            resolved = _open_capability_with_fallback(
                run,
                executor,
                resolver,
                capability.id,
                capability.hint,
                criterion_id=structured_step.criterion_ids[0],
                subgoal_id=structured_step.subgoal_id,
                allow_fallback=not structured_capability_requires_strict_hint(
                    decomposition.objective,
                    capability.id,
                ),
                strict_hint=structured_capability_requires_strict_hint(
                    decomposition.objective,
                    capability.id,
                ),
            )

        elif structured_step.operation == "write_text":
            if len(structured_step.criterion_ids) != 1:
                raise RuntimeError("write_text exige exatamente um critério de readback")
            plan = plan_from_goal_step(
                structured_step,
                artifacts=run.contract.artifacts,
                desktop_enabled=executor.desktop_enabled,
            )
            receipt = _run_recoverable_step(
                run,
                lambda: _type_and_readback(
                    run,
                    executor,
                    plan.target,
                    criterion_id=structured_step.criterion_ids[0],
                    subgoal_id=structured_step.subgoal_id,
                ),
                action_key=_action_key(plan),
                strategy="desktop.type-and-readback",
                retry_safe=False,
            )
            receipt = {**receipt, "text": plan.target}

        else:
            plan = plan_from_goal_step(
                structured_step,
                artifacts=run.contract.artifacts,
                desktop_enabled=executor.desktop_enabled,
            )
            if structured_step.operation == "navigate":
                observer = _structured_navigation_observer(
                    executor,
                    structured_step,
                    criterion_specs,
                    plan,
                    snapshot,
                )
                provider = "playwright"
            else:
                observer = _generic_plan_observer(
                    executor,
                    plan,
                    structured_step.criterion_ids[0],
                )
                provider = "x11" if plan.action == "active_window" else "filesystem"
            strategy = f"structured:{structured_step.operation}"
            action_key = _action_key(plan, f"structured:{structured_step.id}")
            receipt = _run_recoverable_step(
                run,
                lambda: _execute_observed_step(
                    run,
                    executor,
                    plan,
                    strategy=strategy,
                    provider=provider,
                    subgoal_id=structured_step.subgoal_id,
                    criterion_ids=tuple(structured_step.criterion_ids),
                    observer=observer,
                    action_key=action_key,
                ),
                action_key=action_key,
                strategy=strategy,
            )

        verdict = GoalVerifier().evaluate(run)
        pending_for_step = set(structured_step.criterion_ids).intersection(
            verdict.pending_criteria
        )
        if pending_for_step:
            raise RuntimeError(
                f"Step estruturado {structured_step.id} não comprovou critérios: "
                f"{sorted(pending_for_step)}"
            )
        completed_steps.add(structured_step.id)
        _store_structured_artifacts(
            run,
            structured_step,
            snapshot=snapshot,
            resolved_capability=resolved,
            receipt=receipt,
        )


def _execute_planner_goal(
    run: GoalRunState,
    executor: ActionExecutor,
    objective: str,
    planner: Planner,
) -> None:
    prompt = objective
    decisions = 0
    max_decisions = max(run.budget.max_steps * 3, 6)

    while decisions < max_decisions:
        plan = planner.plan(prompt)
        decisions += 1
        snapshot = _planner_snapshot(planner)

        if plan.action == "finish":
            if not run.steps:
                if not run.contract.criteria:
                    run.contract.criteria.append(
                        _criterion("observable_effect", "ao menos um efeito independente do objetivo")
                    )
                prompt = _planner_prompt(
                    objective,
                    run,
                    note="finish recusado porque nenhuma etapa observável foi executada",
                )
                continue
            verdict = GoalVerifier().evaluate(run)
            if verdict.complete:
                return
            prompt = _planner_prompt(
                objective,
                run,
                note=f"finish recusado; critérios pendentes: {list(verdict.pending_criteria)}",
            )
            continue

        key = _action_key(plan)
        guard = run.can_attempt_step(key, f"planner:{snapshot['route']}")
        if not guard:
            if guard.reason is StepBlockReason.ACTION_ALREADY_COMPLETED:
                run.acknowledge_replan()
                prompt = _planner_prompt(
                    objective,
                    run,
                    note=f"ação física duplicada suprimida: {key}",
                )
                continue
            raise RuntimeError(guard.detail)

        criterion_id, subgoal_id = _add_plan_criterion(
            run,
            plan,
            len(run.contract.criteria) + 1,
        )
        _execute_observed_step(
            run,
            executor,
            plan,
            strategy=f"planner:{snapshot['route']}",
            provider=snapshot["provider"],
            subgoal_id=subgoal_id,
            criterion_ids=(criterion_id,),
            observer=_generic_plan_observer(executor, plan, criterion_id),
            action_key=key,
            fallback_from=",".join(snapshot["fallbacks"]) or None,
        )
        prompt = _planner_prompt(objective, run)

    raise RuntimeError(f"Planner não concluiu o Goal após {max_decisions} decisões.")


def _execute_deterministic_plans(
    run: GoalRunState,
    executor: ActionExecutor,
    plans: tuple[Plan, ...],
) -> None:
    for index, plan in enumerate(plans, start=1):
        criterion_id = f"deterministic_effect_{index}"
        subgoal_id = f"deterministic_step_{index}"
        run.contract.criterion(criterion_id)
        _execute_observed_step(
            run,
            executor,
            plan,
            strategy="deterministic",
            provider="deterministic",
            subgoal_id=subgoal_id,
            criterion_ids=(criterion_id,),
            observer=_generic_plan_observer(executor, plan, criterion_id),
        )


def execute_goal(
    executor: ActionExecutor,
    command: str,
    *,
    planner: Planner | None = None,
    max_goal_steps: int = 8,
    task_id: str | None = None,
    session_context: SessionContext | None = None,
    capability_resolver: CapabilityResolver | None = None,
    interpreter: SemanticGoalInterpreter | None = None,
) -> dict[str, Any]:
    """Execute every command through one evidence-gated Goal Runtime."""

    if not command.strip():
        raise ValueError("O objetivo não pode ser vazio.")

    resolution = (
        session_context.resolve_with_provenance(command)
        if session_context is not None
        else None
    )
    resolved_goal = resolution.resolved_text if resolution else command
    active_interpreter = interpreter or SemanticGoalInterpreter()
    intent = active_interpreter.interpret(resolved_goal)
    kind = _intent_kind(intent)
    decomposition: StructuredGoalDecomposition | None = None
    decomposition_error: Exception | None = None
    if kind == "generic":
        decompose = getattr(planner, "decompose", None)
        if not callable(decompose):
            decomposition_error = RuntimeError(
                "O objetivo é ambíguo e nenhuma decomposição estruturada está disponível."
            )
            contract = _decomposition_failure_contract(command)
        else:
            try:
                decomposition = decompose(resolved_goal)
                contract = _contract_from_decomposition(decomposition, command)
            except Exception as exc:
                if _is_safety_interrupt(exc):
                    raise
                decomposition_error = exc
                contract = _decomposition_failure_contract(command)
    else:
        contract = _build_contract(intent, command)
    run = GoalRunState(
        contract=contract,
        task_id=task_id or uuid4().hex,
        budget=GoalBudget(
            max_steps=max_goal_steps,
            max_retries_per_strategy=1,
            max_repeated_actions=2,
            max_no_progress_steps=2,
        ),
    )
    resolver = capability_resolver or CapabilityResolver()
    if kind == "generic" and planner is not None:
        decomposition_metadata = run.contract.artifacts.setdefault(
            "decomposition",
            {
                "accepted": decomposition is not None,
                "step_ids": [],
            },
        )
        decomposition_metadata["accepted"] = decomposition is not None
        decomposition_metadata["provider"] = getattr(planner, "last_provider", None)
        decomposition_metadata["route"] = getattr(planner, "last_route", None)
        decomposition_metadata["fallbacks"] = sorted(
            str(name) for name in (getattr(planner, "last_errors", None) or {})
        )

    try:
        if kind == "search_to_editor":
            query = str(_field(intent, "query", "")).strip()
            snapshot = _run_structured_search(
                run,
                executor,
                intent,
                query,
                need_title=True,
                information=False,
            )
            title = str(snapshot.get("first_result_title") or "").strip()
            if title:
                run.contract.artifacts["first_result_title"] = title
                run.contract.artifacts["first_result_url"] = snapshot.get("first_result_url")
            editor = _open_capability_with_fallback(
                run,
                executor,
                resolver,
                "text.edit",
                str(_field(intent, "app_hint", "")),
                criterion_id="editor_open",
                subgoal_id="open_editor",
            )
            run.contract.artifacts["editor"] = editor.display_name
            _type_and_readback(
                run,
                executor,
                title,
                criterion_id="text_present",
                subgoal_id="write_title",
            )

        elif kind == "conditional_site":
            url = str(_field(intent, "url", "")).strip()
            if "://" not in url:
                url = f"https://{url}"
            plan = Plan("open_url", url)
            probe: dict[str, Any] = {}
            accessible = False

            def condition_observer(_: dict[str, Any]) -> list[_EvidenceSpec]:
                nonlocal probe, accessible
                snapshot = _observe_browser_with_retry(executor)
                observed_url = str(snapshot.get("url") or "")
                if not _navigation_matches(url, observed_url):
                    raise RuntimeError(
                        "A observação do navegador não corresponde ao site da condição: "
                        f"esperado={_normalized_navigation_key(url)!r}, "
                        f"observado={_normalized_navigation_key(observed_url)!r}."
                    )
                accessible = _browser_page_is_loaded(snapshot)
                probe = {
                    "accessible": accessible,
                    "verified": True,
                    "source": "browser.playwright_dom",
                    "status": snapshot.get("http_status"),
                    "final_url": snapshot.get("url"),
                }
                return [
                    _EvidenceSpec(
                        "condition_observed",
                        EvidenceKind.OBSERVATION,
                        "browser.playwright_dom",
                        True,
                        {"accessible": accessible},
                        _safe_value(probe),
                    )
                ]

            try:
                _execute_observed_step(
                    run,
                    executor,
                    plan,
                    strategy="condition:browser",
                    provider="playwright",
                    subgoal_id="observe_condition",
                    criterion_ids=("condition_observed",),
                    observer=condition_observer,
                    action_key=_action_key(plan, "condition"),
                )
            except Exception as browser_error:
                if _is_safety_interrupt(browser_error) or isinstance(
                    browser_error, PermissionError
                ):
                    raise
                assert_authorized = getattr(executor, "assert_authorized", None)
                if callable(assert_authorized):
                    assert_authorized()
                probe = _probe_url(url)
                if callable(assert_authorized):
                    assert_authorized()
                accessible = bool(probe["accessible"])
                step_id = f"s-{uuid4().hex}"
                run.record_step(
                    GoalStep(
                        id=step_id,
                        action_key=f"http_probe:{url}",
                        strategy="condition:http-fallback",
                        status=GoalStepStatus.SUCCEEDED,
                        provider="httpx",
                        subgoal_id="observe_condition",
                        fallback_from="playwright",
                        made_progress=True,
                        error=f"{type(browser_error).__name__}: {browser_error}",
                        metadata={"action": "http_probe", "target": url},
                    )
                )
                run.record_evidence(
                    EvidenceRecord(
                        id=f"e-{uuid4().hex}",
                        criterion_id="condition_observed",
                        kind=EvidenceKind.OBSERVATION,
                        source=str(probe["source"]),
                        verified=bool(probe["verified"]),
                        observed_value={"accessible": accessible},
                        step_id=step_id,
                        metadata=_safe_value(probe),
                    )
                )
            run.contract.artifacts["condition"] = {
                "url": url,
                "accessible": accessible,
                "source": probe["source"],
            }
            true_text = str(_field(intent, "true_text", "site acessível"))
            false_text = str(_field(intent, "false_text", "site indisponível"))
            branch_text = true_text if accessible else false_text
            run.contract.artifacts["selected_branch"] = "true" if accessible else "false"
            run.contract.artifacts["branch_text"] = branch_text
            GoalVerifier().evaluate(run)
            _refresh_subgoals(run)
            editor = _open_capability_with_fallback(
                run,
                executor,
                resolver,
                "text.edit",
                str(_field(intent, "app_hint", "")),
                criterion_id="editor_open",
                subgoal_id="open_editor",
            )
            run.contract.artifacts["editor"] = editor.display_name
            _type_and_readback(
                run,
                executor,
                branch_text,
                criterion_id="text_present",
                subgoal_id="execute_branch",
            )

        elif kind == "open_and_write":
            text = str(_field(intent, "text", ""))
            editor = _open_capability_with_fallback(
                run,
                executor,
                resolver,
                "text.edit",
                str(_field(intent, "app_hint", "")),
                criterion_id="editor_open",
                subgoal_id="open_editor",
            )
            run.contract.artifacts["editor"] = editor.display_name
            _type_and_readback(
                run,
                executor,
                text,
                criterion_id="text_present",
                subgoal_id="write_text",
            )

        elif kind == "named_browser_search":
            query = str(_field(intent, "query", "")).strip()
            browser_hint = str(
                _field(intent, "browser", _field(intent, "app_hint", ""))
            )
            browser = _resolve_capability(
                resolver,
                "web.search",
                browser_hint,
                strict_hint=True,
            )
            engines = _search_engines(intent)
            url = _search_url(engines[0], query)
            target = f"{browser.open_app_target} {shlex.quote(url)}"
            plan = Plan("open_app", target)

            def named_observer(receipt: dict[str, Any]) -> list[_EvidenceSpec]:
                observed: dict[str, Any] = {}
                query_match = False
                argument_observed = False
                pid = receipt.get("pid") if isinstance(receipt.get("pid"), int) else None
                for attempt in range(30):
                    observed = executor.observe_application(
                        browser.startup_wm_class or browser.app_id,
                        pid=pid,
                        expected_argument=url,
                    )
                    title_text = _normalized(
                        str(observed.get("window_title") or "")
                    )
                    title_match = all(
                        token in title_text for token in _query_tokens(query)
                    )
                    engine_match = engines[0] in title_text
                    query_match = bool(title_match and engine_match)
                    argument_observed = observed.get("argument_observed") is True
                    window_identity_ready = bool(
                        observed.get("identity_observed")
                        and observed.get("class_identity_observed")
                        and observed.get("window_id")
                    )
                    if (
                        window_identity_ready
                        and argument_observed
                        and query_match
                    ):
                        break
                    if attempt < 29:
                        time.sleep(0.5)
                return [
                    _EvidenceSpec(
                        "browser_open",
                        EvidenceKind.OBSERVATION,
                        "desktop.x11_proc",
                        bool(window_identity_ready and argument_observed),
                        bool(window_identity_ready and argument_observed),
                        _safe_value(observed),
                    ),
                    _EvidenceSpec(
                        "query_observed",
                        EvidenceKind.OBSERVATION,
                        "desktop.browser_window",
                        bool(query_match and argument_observed and window_identity_ready),
                        bool(query_match and argument_observed and window_identity_ready),
                        {
                            "window_title": observed.get("window_title"),
                            "engine": engines[0],
                            "argument_observed": argument_observed,
                        },
                    ),
                ]

            _execute_observed_step(
                run,
                executor,
                plan,
                strategy="capability:web.search.named-browser",
                provider=browser.source,
                subgoal_id="named_search",
                criterion_ids=("browser_open", "query_observed"),
                observer=named_observer,
            )
            run.contract.artifacts["browser"] = browser.display_name
            run.contract.artifacts["search_url"] = url

        elif kind in {"search", "information"}:
            query = str(_field(intent, "query", "")).strip()
            snapshot = _run_structured_search(
                run,
                executor,
                intent,
                query,
                need_title=False,
                information=kind == "information",
            )
            if snapshot.get("first_result_title"):
                run.contract.artifacts["first_result_title"] = snapshot["first_result_title"]
                run.contract.artifacts["first_result_url"] = snapshot.get("first_result_url")
            run.contract.artifacts["information_preview"] = str(snapshot.get("text") or "")[:800]

        elif kind == "open_capability":
            capability = str(_field(intent, "capability", "text.edit"))
            hint = str(_field(intent, "app_hint", ""))
            resolved = _open_capability_with_fallback(
                run,
                executor,
                resolver,
                capability,
                hint,
                criterion_id="capability_ready",
                subgoal_id="resolve_and_open",
                allow_fallback=(hint.casefold() in {"", "editor", "calculadora"}),
                strict_hint=(hint.casefold() not in {"", "editor", "calculadora"}),
            )
            if capability == "text.edit":
                run.contract.artifacts["editor"] = resolved.display_name
            if capability.startswith("web."):
                run.contract.artifacts["browser"] = resolved.display_name

        elif kind == "deterministic":
            plans = tuple(_field(intent, "plans", ()))
            if not plans:
                plan = _field(intent, "plan", None)
                plans = (plan,) if isinstance(plan, Plan) else ()
            if not plans:
                raise RuntimeError("Intent determinístico não produziu steps.")
            _execute_deterministic_plans(run, executor, plans)

        else:
            if decomposition_error is not None:
                raise decomposition_error
            if decomposition is None:
                raise RuntimeError("Decomposição estruturada ausente.")
            required_step_budget = len(decomposition.steps)
            if required_step_budget > run.budget.max_steps:
                raise RuntimeError(
                    "A decomposição excede o budget antes da primeira ação: "
                    f"necessário={required_step_budget}, disponível={run.budget.max_steps}."
                )
            _execute_structured_decomposition(
                run,
                executor,
                resolver,
                decomposition,
            )

        result = _finalize(
            run,
            resolved_goal=resolved_goal,
            resolution=resolution,
        )
        _remember_context(session_context, run, intent)
        return result
    except GoalExecutionFailed:
        raise
    except EmergencyStopTriggered:
        raise
    except Exception as exc:
        if _is_safety_interrupt(exc):
            raise
        run.failure_reason = f"{type(exc).__name__}: {exc}"
        GoalVerifier().finalize(run)
        _refresh_subgoals(run)
        result = _result_payload(
            run,
            run.failure_reason,
            resolved_goal=resolved_goal,
            resolution=resolution,
        )
        raise GoalExecutionFailed(run.failure_reason, result) from exc


__all__ = ["GoalExecutionFailed", "execute_goal"]
