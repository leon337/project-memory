from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .desktop import canonical_app_id
from .policy import Plan, plan_command

ActionName = Literal[
    "open_url",
    "capture_screen",
    "active_window",
    "move_mouse",
    "click_mouse",
    "type_text",
    "press_key",
    "open_app",
    "finish",
]
PlannerRoute = Literal["fast", "reasoning"]


class StructuredAction(BaseModel):
    """Provider-neutral action contract.

    The model selects one implemented action at a time. `finish` is internal and
    means that the original objective is fully complete based on verified history.
    """

    model_config = ConfigDict(extra="forbid")

    action: ActionName
    target: str = Field(min_length=1, max_length=500)


class Planner(Protocol):
    def plan(self, objective: str) -> Plan: ...


class StructuredPlanProvider(Protocol):
    def generate_plan(self, objective: str) -> Mapping[str, Any]: ...


class ProviderGenerationError(RuntimeError):
    """Failure that happened before any physical action was selected/executed."""

    def __init__(
        self,
        provider: str,
        message: str,
        *,
        status_code: int | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


class DeterministicPlanner:
    def plan(self, objective: str) -> Plan:
        return plan_command(objective)


_PROVIDER_APP_ALIASES = {
    "editor de texto": "editor",
    "editor texto": "editor",
    "text editor": "editor",
    "xed": "editor",
    "gedit": "editor",
    "notepad": "editor",
    "gerenciador de arquivos": "arquivos",
    "file manager": "arquivos",
    "nemo": "arquivos",
    "nautilus": "arquivos",
    "google chrome": "chromium",
    "chrome": "chromium",
    "chromium browser": "chromium",
    "vs code": "vscode",
    "visual studio code": "vscode",
    "code": "vscode",
    "gnome calculator": "calculadora",
    "mate calc": "calculadora",
    "brave": "brave-browser",
    "brave browser": "brave-browser",
    "navegador brave": "brave-browser",
}


def _normalize_provider_app_target(value: str) -> str:
    normalized = value.strip().casefold().replace("_", " ").replace("-", " ")
    normalized = " ".join(normalized.split())
    return _PROVIDER_APP_ALIASES.get(normalized, canonical_app_id(value))


def plan_from_structured(payload: Mapping[str, Any]) -> Plan:
    parsed = StructuredAction.model_validate(payload)
    target = parsed.target
    if parsed.action == "open_app":
        target = _normalize_provider_app_target(target)
    return Plan(action=parsed.action, target=target)


class ProviderPlanner:
    """Adapts one model provider to the same Plan used by the executor."""

    def __init__(self, provider: StructuredPlanProvider) -> None:
        self.provider = provider

    def plan(self, objective: str) -> Plan:
        payload = self.provider.generate_plan(objective)
        return plan_from_structured(payload)


@dataclass(frozen=True)
class ProviderCandidate:
    name: str
    provider: StructuredPlanProvider
    roles: frozenset[PlannerRoute]
    rpm_limit: int | None = None


@dataclass
class ProviderHealth:
    successes: int = 0
    failures: int = 0
    consecutive_failures: int = 0
    last_latency_ms: float | None = None
    cooldown_until: float = 0.0
    request_times: list[float] = field(default_factory=list)


class MultiProviderPlanner:
    """Routes planning calls across providers without bypassing the Policy Layer.

    Existing deterministic commands are resolved locally first, so known commands
    consume no external quota. Natural-language requests are routed by task shape,
    recent health, local RPM headroom and latency. Provider fallback happens only
    while planning, before the executor receives a Plan.
    """

    REASONING_MARKERS = (
        "analise",
        "analisa",
        "decida",
        "decidir",
        "compare",
        "comparar",
        "condição",
        "condicao",
        "caso ",
        "se ",
        "quando ",
        "verifique se",
        "avalie",
        "avaliar",
    )

    DEFAULT_ROUTE_ORDER: dict[PlannerRoute, tuple[str, ...]] = {
        "fast": ("cloudflare", "zai", "gemini"),
        "reasoning": ("zai", "gemini", "cloudflare"),
    }

    def __init__(
        self,
        candidates: list[ProviderCandidate],
        *,
        deterministic: Planner | None = None,
        cooldown_seconds: float = 30.0,
        route_order: Mapping[PlannerRoute, tuple[str, ...]] | None = None,
    ) -> None:
        if not candidates:
            raise ValueError("MultiProviderPlanner requer ao menos um provedor configurado.")
        self.candidates = {candidate.name: candidate for candidate in candidates}
        self.health = {candidate.name: ProviderHealth() for candidate in candidates}
        self.deterministic = deterministic or DeterministicPlanner()
        self.cooldown_seconds = max(1.0, cooldown_seconds)
        self.route_order = dict(route_order or self.DEFAULT_ROUTE_ORDER)
        self.last_provider: str | None = None
        self.last_route: str | None = None
        self.last_errors: dict[str, str] = {}

    @property
    def provider_names(self) -> tuple[str, ...]:
        return tuple(self.candidates)

    def _classify(self, objective: str) -> PlannerRoute:
        lowered = objective.casefold()
        if len(objective) >= 180 or any(marker in lowered for marker in self.REASONING_MARKERS):
            return "reasoning"
        return "fast"

    def _has_local_rpm_headroom(self, name: str, now: float) -> bool:
        candidate = self.candidates[name]
        if not candidate.rpm_limit:
            return True
        health = self.health[name]
        cutoff = now - 60.0
        health.request_times[:] = [timestamp for timestamp in health.request_times if timestamp > cutoff]
        return len(health.request_times) < candidate.rpm_limit

    def _ordered_candidates(self, route: PlannerRoute, now: float) -> list[str]:
        preferred = self.route_order.get(route, ())
        ranks = {name: index for index, name in enumerate(preferred)}

        available: list[str] = []
        for name, candidate in self.candidates.items():
            health = self.health[name]
            if health.cooldown_until > now:
                continue
            if not self._has_local_rpm_headroom(name, now):
                self.last_errors[name] = "limite RPM local atingido"
                continue
            available.append(name)

        def score(name: str) -> tuple[int, int, int, float]:
            candidate = self.candidates[name]
            health = self.health[name]
            role_penalty = 0 if route in candidate.roles else 1
            route_rank = ranks.get(name, len(ranks) + 10)
            latency = health.last_latency_ms if health.last_latency_ms is not None else 0.0
            return role_penalty, route_rank, health.consecutive_failures, latency

        return sorted(available, key=score)

    def _record_failure(self, name: str, exc: Exception, now: float, latency_ms: float) -> None:
        health = self.health[name]
        health.failures += 1
        health.consecutive_failures += 1
        health.last_latency_ms = latency_ms

        cooldown = self.cooldown_seconds
        if isinstance(exc, ProviderGenerationError) and exc.retry_after_seconds is not None:
            cooldown = max(cooldown, exc.retry_after_seconds)
        health.cooldown_until = now + cooldown
        self.last_errors[name] = f"{type(exc).__name__}: {exc}"

    def plan(self, objective: str) -> Plan:
        try:
            plan = self.deterministic.plan(objective)
        except (ValueError, TypeError):
            pass
        else:
            self.last_provider = "deterministic"
            self.last_route = "deterministic"
            self.last_errors = {}
            return plan

        route = self._classify(objective)
        self.last_provider = None
        self.last_route = route
        self.last_errors = {}
        now = time.monotonic()

        for name in self._ordered_candidates(route, now):
            candidate = self.candidates[name]
            health = self.health[name]
            started = time.monotonic()
            health.request_times.append(started)
            try:
                payload = candidate.provider.generate_plan(objective)
                plan = plan_from_structured(payload)
            except Exception as exc:
                finished = time.monotonic()
                self._record_failure(name, exc, finished, (finished - started) * 1000.0)
                continue

            finished = time.monotonic()
            health.successes += 1
            health.consecutive_failures = 0
            health.last_latency_ms = (finished - started) * 1000.0
            health.cooldown_until = 0.0
            self.last_provider = name
            return plan

        detail = "; ".join(f"{name}={error}" for name, error in self.last_errors.items())
        raise ProviderGenerationError(
            "router",
            "nenhum provedor conseguiu gerar um plano válido" + (f" ({detail})" if detail else ""),
        )
