from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import parse_qs, parse_qsl, unquote_plus, urlparse
from typing import Any, Literal, Mapping, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .desktop import canonical_app_id
from .goal_interpreter import analyze_semantic_effects
from .lease import is_safety_interrupt
from .policy import Plan, evaluate_plan, plan_command

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

GoalStepOperation = Literal[
    "open_capability",
    "navigate",
    "write_text",
    "observe_active_window",
    "capture_screen",
]
GoalCriterionCheck = Literal["truthy", "equals", "contains"]
GoalObservable = Literal[
    "browser.url",
    "browser.title",
    "browser.text",
    "browser.search_results",
    "desktop.application",
    "desktop.active_window",
    "desktop.text",
    "filesystem.exists",
]
GoalEvidenceKind = Literal["observation", "readback"]
GoalScalar = str | int | float | bool | None

_STRUCTURED_ID_PATTERN = r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
_ARTIFACT_REFERENCE = re.compile(r"^\{\{([a-z][a-z0-9]*(?:[._-][a-z0-9]+)*)\}\}$")
_OBJECTIVE_URL = re.compile(
    r"(?:https?://[^\s<>\"']+|(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?:/[^\s<>\"']*)?)",
    re.IGNORECASE,
)
_SEARCH_HOSTS = frozenset(
    {
        "bing.com",
        "google.com",
        "duckduckgo.com",
    }
)


def _objective_words(value: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", value.casefold())
    ascii_value = "".join(char for char in folded if not unicodedata.combining(char))
    return set(re.findall(r"[a-z0-9]+", ascii_value))


def _objective_has_unsupported_effect(value: str) -> bool:
    words = _objective_words(value)
    unsupported_actions = {
        "apague",
        "apagar",
        "delete",
        "deletar",
        "enviar",
        "envie",
        "exclua",
        "excluir",
        "instale",
        "instalar",
        "mande",
        "mandar",
        "publique",
        "publicar",
        "remova",
        "remover",
        "upload",
    }
    backup_requested = bool(
        words.intersection({"backup", "copia"})
        and words.intersection({"crie", "criar", "faca", "fazer", "gere", "gerar"})
    )
    return bool(words.intersection(unsupported_actions) or backup_requested)


def _normalized_host(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or "").casefold().removeprefix("www.")


def _objective_urls(value: str) -> tuple[str, ...]:
    return tuple(
        raw if "://" in raw else f"https://{raw}"
        for match in _OBJECTIVE_URL.finditer(value)
        if (raw := match.group(0).rstrip(".,;:!?)]}"))
    )


def _navigation_matches(requested: str, candidate: str) -> bool:
    requested_url = urlparse(
        requested if "://" in requested else f"https://{requested}"
    )
    candidate_url = urlparse(candidate if "://" in candidate else f"https://{candidate}")
    if requested_url.scheme.casefold() != candidate_url.scheme.casefold():
        return False
    if _normalized_host(requested) != _normalized_host(candidate):
        return False
    if requested_url.port not in {None, candidate_url.port}:
        return False
    requested_path = (requested_url.path or "/").rstrip("/") or "/"
    candidate_path = (candidate_url.path or "/").rstrip("/") or "/"
    if requested_path != candidate_path:
        return False
    requested_query = parse_qsl(requested_url.query, keep_blank_values=True)
    candidate_query = parse_qsl(candidate_url.query, keep_blank_values=True)
    return sorted(requested_query) == sorted(candidate_query)


_AppRequirement = tuple[frozenset[str], frozenset[str] | None, str]


def _classify_open_target(value: str) -> _AppRequirement | None:
    folded = _fold_text(value)
    web_capabilities = frozenset({"browser.navigate", "web.read", "web.search"})
    if re.search(r"\b(?:vs\s+code|vscode|visual\s+studio\s+code)\b", folded):
        return (
            frozenset({"code.edit"}),
            frozenset({"vs code", "vscode"}),
            "VS Code",
        )
    if re.search(r"\bxed\b", folded):
        return (frozenset({"text.edit"}), frozenset({"editor", "xed"}), "Xed")
    if re.search(r"\beditor\s+(?:de\s+)?(?:video|imagem|audio)\b", folded):
        return None
    if re.search(r"\beditor\s+(?:de\s+)?codigo\b", folded):
        return (frozenset({"code.edit"}), None, "editor de código")
    if re.search(r"\b(?:editor(?:\s+de\s+texto)?|bloco\s+de\s+notas)\b", folded):
        return (frozenset({"text.edit"}), None, "editor de texto")
    if re.search(r"\b(?:aplicativo|coisa|ferramenta|programa)\b", folded) and re.search(
        r"\b(?:anotacao|anotar|digite|escreva|escrever|nota|notas|texto)\b",
        folded,
    ):
        return (frozenset({"text.edit"}), None, "ferramenta de texto")
    if re.search(r"\bcalculadora\b", folded):
        return (frozenset({"calculate"}), None, "calculadora")
    if re.search(r"\bfirefox\b", folded):
        return (web_capabilities, frozenset({"firefox"}), "Firefox")
    if re.search(r"\bbrave(?:\s+browser)?\b", folded):
        return (
            web_capabilities,
            frozenset({"brave-browser", "brave"}),
            "Brave",
        )
    if re.search(r"\b(?:google\s+chrome|chrome|chromium)\b", folded):
        return (
            web_capabilities,
            frozenset({"chromium", "chrome", "google chrome"}),
            "Chrome/Chromium",
        )
    if re.search(r"\b(?:browser|navegador)\s+de\s+arquivos\b", folded):
        return None
    if re.search(r"\b(?:browser|navegador)\b", folded):
        return (web_capabilities, None, "navegador")
    return None


def _explicit_open_clauses(objective: str) -> tuple[str, ...]:
    folded = _fold_text(objective)
    matches = list(
        re.finditer(
            r"\b(?:abra|abre|abrir|execute|executar|inicie|iniciar|lance|lancar)\b",
            folded,
        )
    )
    clauses: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(folded)
        clause = folded[match.start() : end]
        boundary = re.search(
            r"(?:[.;]|\be\b)\s*(?=(?:acesse|abra|capture|calcule|copie|digite|"
            r"escreva|execute|inicie|pesquise|registre|verifique|visite)\b)",
            clause,
        )
        if boundary is not None:
            clause = clause[: boundary.start()]
        clauses.append(clause.strip())
    return tuple(clauses)


def _explicit_open_app_clauses(objective: str) -> tuple[str, ...]:
    return tuple(
        clause
        for clause in _explicit_open_clauses(objective)
        if not _objective_urls(clause)
    )


def _explicit_open_app_requirements(objective: str) -> tuple[_AppRequirement, ...]:
    return tuple(
        requirement
        for clause in _explicit_open_app_clauses(objective)
        if (requirement := _classify_open_target(clause)) is not None
    )


def _explicit_open_url_count(objective: str) -> int:
    return sum(
        bool(_objective_urls(clause))
        for clause in _explicit_open_clauses(objective)
    )


def _open_app_requirements(objective: str) -> tuple[_AppRequirement, ...]:
    requirements = list(_explicit_open_app_requirements(objective))
    words = _objective_words(objective)
    needs_text_surface = bool(
        words.intersection(
            {
                "anotacao",
                "anotar",
                "copie",
                "digite",
                "escreva",
                "escrever",
                "nota",
                "notas",
                "registre",
                "transcreva",
            }
        )
    )
    has_text_surface = any(
        capability_ids.intersection({"text.edit", "code.edit"})
        for capability_ids, _, _ in requirements
    )
    if needs_text_surface and not has_text_surface:
        requirements.append((frozenset({"text.edit"}), None, "superfície de texto"))
    return tuple(requirements)


def structured_capability_requires_strict_hint(
    objective: str,
    capability_id: str,
) -> bool:
    return any(
        accepted_hints is not None and capability_id in capability_ids
        for capability_ids, accepted_hints, _label in _open_app_requirements(objective)
    )


def _fold_text(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    return " ".join(
        "".join(char for char in folded if not unicodedata.combining(char)).split()
    )


def _search_query_from_url(value: str) -> str:
    parsed = urlparse(value)
    values = parse_qs(parsed.query)
    return " ".join(
        unquote_plus(item)
        for name in ("q", "query", "p", "text")
        for item in values.get(name, [])
    ).strip()


def _objective_search_query(value: str) -> str | None:
    """Extract the requested query span without trusting the provider target."""

    match = re.search(
        r"\b(?:busca|buscar|busque|encontre|pesquisa|pesquisar|pesquise|procure|search)\b"
        r"\s+(?:(?:na|pela)\s+(?:web|internet)\s+)?(?:por|sobre)?\s*(.+)",
        value,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    query = match.group(1)
    query = re.split(
        r"(?:\s*;\s*|\s*,?\s+\b(?:e\s+depois|depois|entao|em\s+seguida|"
        r"na\s+sequencia|e)\s+)(?=(?:abra|abre|acesse|calcule|capture|copie|"
        r"digite|escreva|inicie|lance|pesquise|registre|transcreva|verifique|"
        r"visite)\b)",
        query,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    query = re.sub(r"\s+(?:por\s+favor|para\s+mim)\s*$", "", query, flags=re.IGNORECASE)
    return query.strip(" \t\r\n,;:.!?") or None


def _objective_write_target(value: str) -> str | None:
    """Extract an explicit human-authored text effect for literal write steps."""

    match = re.search(
        r"\b(?:anote|copie|digite|escreva|insira|registre|transcreva)\b",
        value,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    tail = value[match.end() :].lstrip(" \t\r\n,;:")
    quoted = re.match(r'"([^"\n]+)"|“([^”\n]+)”|\'([^\'\n]+)\'', tail)
    if quoted is not None:
        return next(group for group in quoted.groups() if group is not None).strip()
    tail = re.sub(r"^(?:o\s+)?texto\s*:?\s*", "", tail, flags=re.IGNORECASE)
    tail = re.split(
        r"\s+(?:em|no|num|usando|com)\s+(?:(?:um|uma)\s+)?"
        r"(?:aplicativo|editor|ferramenta|programa)\b",
        tail,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    tail = re.split(
        r"(?:\s*;\s*|\s*,?\s+\b(?:e\s+depois|depois|entao|em\s+seguida|e)\s+)"
        r"(?=(?:abra|acesse|capture|inicie|pesquise|visite)\b)",
        tail,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    tail = re.sub(r"\s+(?:por\s+favor|para\s+mim)\s*$", "", tail, flags=re.IGNORECASE)
    return tail.strip(" \t\r\n,;:.!?") or None


class StructuredCapability(BaseModel):
    """A capability requested by a model, never a guessed executable."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80, pattern=_STRUCTURED_ID_PATTERN)
    description: str = Field(min_length=1, max_length=300)
    hint: str | None = Field(default=None, min_length=1, max_length=120)


class StructuredGoalCriterion(BaseModel):
    """An independently observable, mandatory success criterion.

    Provider assertions and execution receipts are intentionally absent from the
    evidence vocabulary. A generated contract therefore cannot make its own
    action receipt sufficient for completion.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80, pattern=_STRUCTURED_ID_PATTERN)
    description: str = Field(min_length=1, max_length=400)
    observable: GoalObservable
    evidence_kind: GoalEvidenceKind
    check: GoalCriterionCheck
    expected_value: GoalScalar = None
    required: Literal[True] = True

    @model_validator(mode="after")
    def validate_check_and_evidence(self) -> "StructuredGoalCriterion":
        expected_kind: GoalEvidenceKind = (
            "readback" if self.observable == "desktop.text" else "observation"
        )
        if self.evidence_kind != expected_kind:
            raise ValueError(
                f"{self.observable} exige evidence_kind={expected_kind}; "
                "receipts/assertions não são aceitos"
            )
        if self.check in {"equals", "contains"} and self.expected_value is None:
            raise ValueError(f"check={self.check} exige expected_value")
        if self.check == "truthy" and self.expected_value is not None:
            raise ValueError("check=truthy não aceita expected_value")
        if self.check == "contains" and not isinstance(self.expected_value, str):
            raise ValueError("check=contains exige expected_value textual")
        if self.observable in {
            "desktop.application",
            "browser.search_results",
            "filesystem.exists",
        } and self.check != "truthy":
            raise ValueError(f"{self.observable} aceita somente check=truthy")
        if self.observable == "desktop.text" and self.check != "equals":
            raise ValueError("desktop.text exige readback equals exato")
        return self


class StructuredGoalSubgoal(BaseModel):
    """A bounded portion of the objective and the criteria that close it."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80, pattern=_STRUCTURED_ID_PATTERN)
    description: str = Field(min_length=1, max_length=400)
    capability_ids: list[str] = Field(min_length=1, max_length=8)
    criterion_ids: list[str] = Field(min_length=1, max_length=12)
    depends_on: list[str] = Field(default_factory=list, max_length=12)


class StructuredGoalStep(BaseModel):
    """A declarative, policy-materializable step in a complete decomposition.

    ``open_capability`` deliberately carries no executable. The runtime must ask
    its Capability Resolver for a concrete target and then call
    :func:`plan_from_goal_step`, which applies the Policy Layer. This prevents a
    provider from turning a human need directly into an invented command.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80, pattern=_STRUCTURED_ID_PATTERN)
    subgoal_id: str = Field(min_length=1, max_length=80, pattern=_STRUCTURED_ID_PATTERN)
    capability_id: str = Field(min_length=1, max_length=80, pattern=_STRUCTURED_ID_PATTERN)
    operation: GoalStepOperation
    target: str | None = Field(default=None, min_length=1, max_length=500)
    criterion_ids: list[str] = Field(min_length=1, max_length=12)
    depends_on: list[str] = Field(default_factory=list, max_length=16)
    consumes: list[str] = Field(default_factory=list, max_length=12)
    produces: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_target_shape(self) -> "StructuredGoalStep":
        needs_target = self.operation in {"navigate", "write_text"}
        if needs_target and self.target is None:
            raise ValueError(f"operation={self.operation} exige target")
        if not needs_target and self.target is not None:
            raise ValueError(f"operation={self.operation} não aceita target")
        if self.target is not None and not all(char.isprintable() for char in self.target):
            raise ValueError("target contém caracteres de controle")
        if self.operation != "navigate" and len(self.criterion_ids) != 1:
            raise ValueError(
                f"operation={self.operation} exige exatamente um criterion_id"
            )

        for field_name, values in (
            ("criterion_ids", self.criterion_ids),
            ("depends_on", self.depends_on),
            ("consumes", self.consumes),
            ("produces", self.produces),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} contém identificadores duplicados")
            invalid = [value for value in values if not re.fullmatch(_STRUCTURED_ID_PATTERN, value)]
            if invalid:
                raise ValueError(f"{field_name} contém identificador inválido: {invalid[0]}")

        reference = _ARTIFACT_REFERENCE.fullmatch(self.target or "")
        if reference and reference.group(1) not in self.consumes:
            raise ValueError("artifact usado no target precisa estar declarado em consumes")

        producible_by_operation = {
            "open_capability": {
                "application_id",
                "application_name",
                "application.id",
                "application.name",
            },
            "navigate": {
                "first_result_title",
                "first_result_url",
                "browser_url",
                "browser_title",
                "browser_text",
                "browser.url",
                "browser.title",
                "browser.text",
            },
            "write_text": {"written_text", "written.text"},
            "observe_active_window": set(),
            "capture_screen": {"screenshot_path", "screenshot.path"},
        }
        unsupported = set(self.produces) - producible_by_operation[self.operation]
        if unsupported:
            raise ValueError(
                f"operation={self.operation} não pode produzir artifact "
                f"{sorted(unsupported)[0]}"
            )
        return self


_OBSERVABLES_BY_OPERATION: dict[GoalStepOperation, frozenset[GoalObservable]] = {
    "open_capability": frozenset({"desktop.application"}),
    "navigate": frozenset(
        {"browser.url", "browser.title", "browser.text", "browser.search_results"}
    ),
    "write_text": frozenset({"desktop.text"}),
    "observe_active_window": frozenset({"desktop.active_window"}),
    "capture_screen": frozenset({"filesystem.exists"}),
}


def _require_unique_ids(values: list[Any], label: str) -> dict[str, Any]:
    indexed = {value.id: value for value in values}
    if len(indexed) != len(values):
        raise ValueError(f"{label} contém ids duplicados")
    return indexed


def _require_prior_references(
    values: list[Any],
    *,
    dependency_attribute: str,
    label: str,
) -> None:
    seen: set[str] = set()
    for value in values:
        dependencies = getattr(value, dependency_attribute)
        missing = [dependency for dependency in dependencies if dependency not in seen]
        if missing:
            raise ValueError(
                f"{label} {value.id} depende de item ausente ou não anterior: {missing[0]}"
            )
        seen.add(value.id)


class StructuredGoalDecomposition(BaseModel):
    """Complete provider-neutral contract generated before any physical action."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    objective: str = Field(min_length=1, max_length=4000)
    capabilities: list[StructuredCapability] = Field(min_length=1, max_length=12)
    criteria: list[StructuredGoalCriterion] = Field(min_length=1, max_length=24)
    subgoals: list[StructuredGoalSubgoal] = Field(min_length=1, max_length=16)
    steps: list[StructuredGoalStep] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def validate_closed_contract(self) -> "StructuredGoalDecomposition":
        if _objective_has_unsupported_effect(self.objective):
            raise ValueError(
                "objetivo exige efeito fora do vocabulário observável desta decomposição"
            )
        capabilities = _require_unique_ids(self.capabilities, "capabilities")
        criteria = _require_unique_ids(self.criteria, "criteria")
        subgoals = _require_unique_ids(self.subgoals, "subgoals")
        steps = _require_unique_ids(self.steps, "steps")

        _require_prior_references(
            self.subgoals,
            dependency_attribute="depends_on",
            label="subgoal",
        )
        _require_prior_references(
            self.steps,
            dependency_attribute="depends_on",
            label="step",
        )

        criterion_subgoal_owners: dict[str, str] = {}
        used_capabilities: set[str] = set()
        for subgoal in self.subgoals:
            unknown_capabilities = [
                item for item in subgoal.capability_ids if item not in capabilities
            ]
            if unknown_capabilities:
                raise ValueError(
                    f"subgoal {subgoal.id} referencia capability desconhecida: "
                    f"{unknown_capabilities[0]}"
                )
            unknown_criteria = [item for item in subgoal.criterion_ids if item not in criteria]
            if unknown_criteria:
                raise ValueError(
                    f"subgoal {subgoal.id} referencia criterion desconhecido: "
                    f"{unknown_criteria[0]}"
                )
            if len(subgoal.capability_ids) != len(set(subgoal.capability_ids)):
                raise ValueError(f"subgoal {subgoal.id} repete capability")
            if len(subgoal.criterion_ids) != len(set(subgoal.criterion_ids)):
                raise ValueError(f"subgoal {subgoal.id} repete criterion")
            for criterion_id in subgoal.criterion_ids:
                if criterion_id in criterion_subgoal_owners:
                    raise ValueError(
                        f"criterion {criterion_id} pertence a mais de um subgoal"
                    )
                criterion_subgoal_owners[criterion_id] = subgoal.id

        if set(criteria) != set(criterion_subgoal_owners):
            missing = sorted(set(criteria) - set(criterion_subgoal_owners))
            raise ValueError(f"criterion sem subgoal: {missing[0]}")

        criterion_step_owners: dict[str, str] = {}
        produced_by: dict[str, str] = {}
        effects: set[tuple[str, str, str]] = set()
        for step in self.steps:
            if step.subgoal_id not in subgoals:
                raise ValueError(f"step {step.id} referencia subgoal desconhecido")
            if step.capability_id not in capabilities:
                raise ValueError(f"step {step.id} referencia capability desconhecida")
            subgoal = subgoals[step.subgoal_id]
            if step.capability_id not in subgoal.capability_ids:
                raise ValueError(
                    f"step {step.id} usa capability fora de seu subgoal"
                )
            used_capabilities.add(step.capability_id)

            for criterion_id in step.criterion_ids:
                if criterion_id not in criteria:
                    raise ValueError(
                        f"step {step.id} referencia criterion desconhecido: {criterion_id}"
                    )
                if criterion_id not in subgoal.criterion_ids:
                    raise ValueError(
                        f"step {step.id} tenta provar criterion de outro subgoal"
                    )
                if criterion_id in criterion_step_owners:
                    raise ValueError(
                        f"criterion {criterion_id} está ligado a mais de um step"
                    )
                criterion = criteria[criterion_id]
                if criterion.observable not in _OBSERVABLES_BY_OPERATION[step.operation]:
                    raise ValueError(
                        f"step {step.id} ({step.operation}) não pode observar "
                        f"{criterion.observable}"
                    )
                expected_reference = _ARTIFACT_REFERENCE.fullmatch(
                    criterion.expected_value
                    if isinstance(criterion.expected_value, str)
                    else ""
                )
                if expected_reference and expected_reference.group(1) not in step.consumes:
                    raise ValueError(
                        f"criterion {criterion_id} usa artifact não declarado em "
                        f"consumes do step {step.id}"
                    )
                criterion_step_owners[criterion_id] = step.id

            effect = (step.operation, step.capability_id, step.target or "")
            if effect in effects:
                raise ValueError(f"efeito físico duplicado na decomposição: {step.id}")
            effects.add(effect)

            for artifact in step.consumes:
                producer = produced_by.get(artifact)
                if producer is None:
                    raise ValueError(
                        f"step {step.id} consome artifact sem produtor anterior: {artifact}"
                    )
                if producer not in step.depends_on:
                    raise ValueError(
                        f"step {step.id} precisa depender explicitamente do produtor "
                        f"{producer} para consumir {artifact}"
                    )
            for artifact in step.produces:
                if artifact in produced_by:
                    raise ValueError(f"artifact possui mais de um produtor: {artifact}")
                produced_by[artifact] = step.id

            if step.operation == "write_text":
                matching_readback = any(
                    criteria[item].observable == "desktop.text"
                    and criteria[item].check == "equals"
                    and criteria[item].expected_value == step.target
                    for item in step.criterion_ids
                )
                if not matching_readback:
                    raise ValueError(
                        f"step {step.id} write_text exige readback equals do target"
                    )

            if step.operation != "open_capability" and not _ARTIFACT_REFERENCE.fullmatch(
                step.target or ""
            ):
                # Syntax/scheme validation from the existing Policy Layer. The
                # runtime must apply the policy again immediately before action.
                plan_from_goal_step(step, desktop_enabled=True)

        if set(criteria) != set(criterion_step_owners):
            missing = sorted(set(criteria) - set(criterion_step_owners))
            raise ValueError(f"criterion sem step observador: {missing[0]}")

        step_positions = {step.id: index for index, step in enumerate(self.steps)}
        steps_by_subgoal = {
            subgoal.id: [step for step in self.steps if step.subgoal_id == subgoal.id]
            for subgoal in self.subgoals
        }
        for subgoal in self.subgoals:
            own_steps = steps_by_subgoal[subgoal.id]
            if not own_steps:
                raise ValueError(f"subgoal sem step: {subgoal.id}")
            for dependency_id in subgoal.depends_on:
                dependency_steps = steps_by_subgoal[dependency_id]
                terminal_dependency = dependency_steps[-1]
                for step in own_steps:
                    if step_positions[step.id] <= step_positions[terminal_dependency.id]:
                        raise ValueError(
                            f"step {step.id} aparece antes de concluir subgoal "
                            f"dependente {dependency_id}"
                        )
                    if terminal_dependency.id not in step.depends_on:
                        raise ValueError(
                            f"step {step.id} precisa depender do step terminal "
                            f"{terminal_dependency.id} do subgoal {dependency_id}"
                        )

        # Typing is only safe after this very decomposition opened and observed
        # the intended surface.  An already-focused user window is not an
        # implicit precondition and must never receive provider-selected text.
        for step in self.steps:
            if step.operation != "write_text":
                continue
            matching_opens = [
                candidate
                for candidate in self.steps[: step_positions[step.id]]
                if candidate.operation == "open_capability"
                and candidate.capability_id == step.capability_id
            ]
            if not matching_opens:
                raise ValueError(
                    f"step {step.id} write_text exige open_capability anterior "
                    "da mesma superfície"
                )
            opened_by = matching_opens[-1]
            if opened_by.id not in step.depends_on:
                raise ValueError(
                    f"step {step.id} write_text precisa depender explicitamente "
                    f"de {opened_by.id}"
                )
        if set(capabilities) != used_capabilities:
            missing = sorted(set(capabilities) - used_capabilities)
            raise ValueError(f"capability declarada mas não usada: {missing[0]}")

        allowed_capabilities = {
            "text.edit",
            "code.edit",
            "calculate",
            "web.search",
            "web.read",
            "browser.navigate",
            "desktop.observe",
            "screen.capture",
        }
        unknown_capabilities = set(capabilities) - allowed_capabilities
        if unknown_capabilities:
            raise ValueError(
                f"capability fora do vocabulário local: {sorted(unknown_capabilities)[0]}"
            )
        capabilities_by_operation = {
            "open_capability": {
                "text.edit",
                "code.edit",
                "calculate",
                "web.search",
                "web.read",
                "browser.navigate",
            },
            "navigate": {"web.search", "web.read", "browser.navigate"},
            "write_text": {"text.edit", "code.edit"},
            "observe_active_window": {"desktop.observe"},
            "capture_screen": {"screen.capture"},
        }
        for step in self.steps:
            if step.capability_id not in capabilities_by_operation[step.operation]:
                raise ValueError(
                    f"capability {step.capability_id} incompatível com "
                    f"operation={step.operation}"
                )

        coverage = analyze_semantic_effects(self.objective)
        if coverage.has_unclassified_clause:
            raise ValueError(
                "objetivo contém cláusula material não classificada; "
                "a decomposição deve falhar fechado"
            )
        event_counts: dict[str, int] = {}
        for event in coverage.events:
            event_counts[event] = event_counts.get(event, 0) + 1
        unsupported_events = set(event_counts) - {
            "capture",
            "navigate",
            "open",
            "search",
            "write",
        }
        if unsupported_events:
            raise ValueError(
                "efeito material não é representável pelo runtime estruturado: "
                f"{sorted(unsupported_events)[0]}"
            )
        if event_counts.get("search", 0) > 1 or event_counts.get("write", 0) > 1:
            raise ValueError(
                "múltiplos efeitos de busca/escrita ainda não possuem grounding "
                "1:1 seguro"
            )
        operation_counts = {
            operation: sum(step.operation == operation for step in self.steps)
            for operation in {
                "open_capability",
                "navigate",
                "write_text",
                "observe_active_window",
                "capture_screen",
            }
        }
        explicit_urls = _objective_urls(self.objective)
        open_url_events = _explicit_open_url_count(self.objective)
        explicit_open_clauses = _explicit_open_app_clauses(self.objective)
        explicit_open = len(explicit_open_clauses)
        if explicit_open + open_url_events != event_counts.get("open", 0):
            raise ValueError(
                "efeitos open do objetivo não puderam ser pareados por cláusula"
            )
        required_navigate = (
            event_counts.get("search", 0)
            + event_counts.get("navigate", 0)
            + open_url_events
        )
        required_write = event_counts.get("write", 0)
        required_capture = event_counts.get("capture", 0)
        note_need = bool(
            _objective_words(self.objective).intersection(
                {"anotacao", "anotacoes", "anotar", "nota", "notas"}
            )
        )
        explicit_open_requirements = _explicit_open_app_requirements(self.objective)
        if len(explicit_open_requirements) != explicit_open:
            raise ValueError(
                "decomposição não cobre alvo explícito de open_capability: "
                "ferramenta fora do vocabulário local suportado"
            )
        explicit_text_surface = any(
            capability_ids.intersection({"text.edit", "code.edit"})
            for capability_ids, _accepted_hints, _label in explicit_open_requirements
        )
        implicit_text_surface = bool(
            (required_write or note_need) and not explicit_text_surface
        )
        required_open = explicit_open + int(implicit_text_surface)
        expected_counts = {
            "navigate": required_navigate,
            "write_text": required_write,
            "capture_screen": required_capture,
            "open_capability": required_open,
            "observe_active_window": 0,
        }
        mismatches = {
            operation: (expected, operation_counts[operation])
            for operation, expected in expected_counts.items()
            if operation_counts[operation] != expected
        }
        if mismatches:
            operation = sorted(mismatches)[0]
            expected, actual = mismatches[operation]
            raise ValueError(
                "decomposição não cobre os efeitos do objetivo 1:1: "
                f"operation={operation}, esperado={expected}, recebido={actual}"
            )

        open_clauses = iter(_explicit_open_clauses(self.objective))
        expected_operation_order: list[GoalStepOperation] = []
        implicit_open_inserted = False
        for event in coverage.events:
            if event == "open":
                clause = next(open_clauses, "")
                expected_operation_order.append(
                    "navigate" if _objective_urls(clause) else "open_capability"
                )
            elif event in {"navigate", "search"}:
                expected_operation_order.append("navigate")
            elif event == "write":
                if implicit_text_surface and not implicit_open_inserted:
                    expected_operation_order.append("open_capability")
                    implicit_open_inserted = True
                expected_operation_order.append("write_text")
            elif event == "capture":
                expected_operation_order.append("capture_screen")
        if note_need and implicit_text_surface and not implicit_open_inserted:
            expected_operation_order.append("open_capability")
        actual_operation_order = [step.operation for step in self.steps]
        if actual_operation_order != expected_operation_order:
            raise ValueError(
                "ordem dos steps não preserva a sequência material do objetivo: "
                f"esperado={expected_operation_order}, recebido={actual_operation_order}"
            )

        explicit_navigation_steps = [
            step
            for step in self.steps
            if step.operation == "navigate"
            and step.capability_id != "web.search"
            and not _ARTIFACT_REFERENCE.fullmatch(step.target or "")
        ]
        if len(explicit_navigation_steps) != len(explicit_urls):
            raise ValueError(
                "URLs explícitas do objetivo não estão pareadas 1:1 com steps navigate"
            )
        for requested_url, navigation_step in zip(
            explicit_urls,
            explicit_navigation_steps,
            strict=True,
        ):
            if not _navigation_matches(requested_url, str(navigation_step.target)):
                raise ValueError(
                    f"navigate {navigation_step.id} possui destino sem proveniência "
                    "exata no objetivo"
                )

        open_requirements = _open_app_requirements(self.objective)
        if len(open_requirements) != required_open:
            raise ValueError(
                "alvo de open_capability não foi ancorado em uma ferramenta "
                "reconhecida do objetivo"
            )
        open_steps = [
            step for step in self.steps if step.operation == "open_capability"
        ]
        unused_open_steps = list(open_steps)
        for accepted_capabilities, accepted_hints, requested_app in open_requirements:
            matching_step = next(
                (
                    step
                    for step in unused_open_steps
                    if step.capability_id in accepted_capabilities
                ),
                None,
            )
            if matching_step is None:
                raise ValueError(
                    f"aplicativo explícito {requested_app!r} exige capability "
                    f"em {sorted(accepted_capabilities)}"
                )
            unused_open_steps.remove(matching_step)
            capability = capabilities[matching_step.capability_id]
            canonical_hint = canonical_app_id(capability.hint or "")
            if accepted_hints is not None and canonical_hint not in accepted_hints:
                raise ValueError(
                    f"hint {capability.hint!r} não corresponde ao aplicativo "
                    f"explicitamente solicitado {requested_app!r}"
                )

        # A provider may decompose an objective, but it may not invent the
        # concrete effect and then define a matching criterion for its own
        # invention. Literal write targets must come from the human objective;
        # generated values must flow from an independently observed artifact.
        for step in self.steps:
            reference = _ARTIFACT_REFERENCE.fullmatch(step.target or "")
            if step.operation == "write_text" and not reference:
                literal = _fold_text(step.target or "")
                requested_text = _objective_write_target(self.objective)
                if (
                    not literal
                    or requested_text is None
                    or literal != _fold_text(requested_text)
                ):
                    raise ValueError(
                        f"write_text {step.id} possui target sem proveniência "
                        "no objetivo"
                    )

            if step.operation != "navigate" or reference:
                continue
            target = str(step.target)
            parsed = urlparse(target)
            target_host = _normalized_host(target)
            if step.capability_id == "web.search":
                query = _search_query_from_url(target)
                requested_query = _objective_search_query(self.objective)
                expected_path = {
                    "bing.com": "/search",
                    "google.com": "/search",
                    "duckduckgo.com": "/",
                }.get(target_host)
                actual_path = (parsed.path or "/").rstrip("/") or "/"
                query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
                if (
                    parsed.scheme.casefold() != "https"
                    or target_host not in _SEARCH_HOSTS
                    or actual_path != expected_path
                    or len(query_pairs) != 1
                    or query_pairs[0][0] != "q"
                    or requested_query is None
                    or _fold_text(query) != _fold_text(requested_query)
                ):
                    raise ValueError(
                        f"navigate {step.id} não está ancorado em busca local segura"
                    )
            elif not target_host or not any(
                _navigation_matches(requested, target)
                for requested in explicit_urls
            ):
                raise ValueError(
                    f"navigate {step.id} possui destino sem proveniência no objetivo"
                )

        words = _objective_words(self.objective)
        operations = {step.operation for step in self.steps}
        search_markers = {
            "busca",
            "buscar",
            "busque",
            "encontre",
            "pesquisa",
            "pesquisar",
            "pesquise",
            "procure",
            "search",
        }
        write_markers = {
            "anote",
            "digite",
            "escreva",
            "escrever",
            "redija",
            "registre",
        }
        capture_markers = {"capture", "screenshot", "tela"}
        note_markers = {"anotacao", "anotacoes", "anotar", "nota", "notas"}
        requirements: set[str] = set()
        if words.intersection(search_markers):
            requirements.add("navigate")
            if not any(
                criteria[criterion_id].observable
                == "browser.search_results"
                for step in self.steps
                if step.operation == "navigate"
                for criterion_id in step.criterion_ids
            ):
                raise ValueError("objetivo de busca não possui evidência de conteúdo")
        if words.intersection(write_markers):
            requirements.add("write_text")
        if words.intersection(capture_markers):
            requirements.add("capture_screen")
        if words.intersection(note_markers):
            requirements.add("open_capability")
            if "text.edit" not in capabilities:
                raise ValueError("objetivo de anotação exige capability text.edit")

        named_browsers = {"brave", "chrome", "chromium", "firefox", "opera"}
        if words.intersection(named_browsers) and "navigate" in operations:
            raise ValueError(
                "navegação em browser nomeado exige ponte observável específica"
            )

        creative_markers = {
            "analise",
            "documento",
            "elabore",
            "plano",
            "produza",
            "relatorio",
            "resumo",
        }
        quoted_values = [
            next(group for group in match.groups() if group is not None)
            for match in re.finditer(r'"([^"\n]+)"|“([^”\n]+)”|\'([^\'\n]+)\'', self.objective)
        ]
        if words.intersection(creative_markers) and not quoted_values:
            raise ValueError(
                "objetivo criativo não define conteúdo final verificável; "
                "a decomposição não pode inventar seu próprio critério"
            )
        if quoted_values:
            write_targets = {
                step.target for step in self.steps if step.operation == "write_text"
            }
            missing_quote = next(
                (value for value in quoted_values if value not in write_targets),
                None,
            )
            if missing_quote is not None:
                raise ValueError(
                    "texto explícito do objetivo não aparece em nenhum write_text"
                )

        if not requirements:
            raise ValueError(
                "não foi possível derivar requisito atômico observável do objetivo"
            )
        missing_operations = requirements - operations
        if missing_operations:
            raise ValueError(
                "decomposição omitiu efeito obrigatório do objetivo: "
                f"{sorted(missing_operations)[0]}"
            )
        return self


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


class StructuredGoalProvider(Protocol):
    def generate_goal_decomposition(self, objective: str) -> Mapping[str, Any]: ...


class GoalDecomposer(Protocol):
    def decompose(self, objective: str) -> StructuredGoalDecomposition: ...


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


def decomposition_from_structured(
    payload: Mapping[str, Any],
    *,
    expected_objective: str | None = None,
) -> StructuredGoalDecomposition:
    """Validate a complete provider decomposition before it reaches an executor.

    When ``expected_objective`` is supplied, the provider must copy it verbatim
    (apart from surrounding whitespace). This closes a subtle authority gap in
    which a model could silently weaken or replace the user's objective while
    still returning a formally valid contract.
    """

    if expected_objective is not None:
        expected = expected_objective.strip()
        if not expected:
            raise ValueError("O objetivo esperado não pode ser vazio.")
        supplied = payload.get("objective")
        if isinstance(supplied, str) and supplied.strip() != expected:
            raise ValueError("A decomposição alterou o objetivo original.")
    parsed = StructuredGoalDecomposition.model_validate(payload)
    return parsed


def _resolved_step_target(
    step: StructuredGoalStep,
    *,
    resolved_capability_target: str | None,
    artifacts: Mapping[str, Any] | None,
) -> str:
    if step.operation == "open_capability":
        target = (resolved_capability_target or "").strip()
        if not target:
            raise ValueError(
                f"step {step.id} requer target resolvido para capability "
                f"{step.capability_id}"
            )
        return target

    target = step.target
    if target is None:
        if step.operation == "observe_active_window":
            return "active"
        if step.operation == "capture_screen":
            return "screen"
        raise ValueError(f"step {step.id} não possui target")

    resolved_value = resolve_goal_value(target, artifacts=artifacts)
    resolved = str(resolved_value)
    if not resolved:
        raise ValueError(f"target materializado está vazio para step {step.id}")
    return resolved


def resolve_goal_value(
    value: GoalScalar,
    *,
    artifacts: Mapping[str, Any] | None,
) -> GoalScalar:
    """Resolve a whole-value ``{{artifact_id}}`` reference without interpolation.

    Whole-value substitution avoids constructing commands/URLs by concatenating
    untrusted fragments. Callers may use this same helper for a criterion's
    ``expected_value`` before recording the GoalContract.
    """

    reference = _ARTIFACT_REFERENCE.fullmatch(value if isinstance(value, str) else "")
    if not reference:
        return value
    artifact_id = reference.group(1)
    if artifacts is None or artifact_id not in artifacts:
        raise ValueError(f"artifact ainda indisponível: {artifact_id}")
    resolved = artifacts[artifact_id]
    if not isinstance(resolved, (str, int, float, bool)):
        raise ValueError(f"artifact {artifact_id} não é escalar/materializável")
    if isinstance(resolved, str) and not resolved:
        raise ValueError(f"artifact {artifact_id} está vazio")
    return resolved


def plan_from_goal_step(
    step: StructuredGoalStep,
    *,
    resolved_capability_target: str | None = None,
    artifacts: Mapping[str, Any] | None = None,
    desktop_enabled: bool,
) -> Plan:
    """Materialize one predeclared step and reapply the existing Policy Layer.

    Capability resolution is deliberately external: only the local Capability
    Resolver may turn ``open_capability`` into a concrete executable/app target.
    The returned Plan is safe to hand to the existing executor *after* the caller
    has recorded the complete decomposition as the Goal contract.
    """

    target = _resolved_step_target(
        step,
        resolved_capability_target=resolved_capability_target,
        artifacts=artifacts,
    )
    action_by_operation: dict[GoalStepOperation, ActionName] = {
        "open_capability": "open_app",
        "navigate": "open_url",
        "write_text": "type_text",
        "observe_active_window": "active_window",
        "capture_screen": "capture_screen",
    }
    plan = Plan(action=action_by_operation[step.operation], target=target)
    decision = evaluate_plan(plan, desktop_enabled=desktop_enabled)
    if not decision.allowed:
        raise ValueError(
            f"Policy recusou step {step.id} ({step.operation}): {decision.reason}"
        )
    return plan


class ProviderPlanner:
    """Adapts one model provider to the same Plan used by the executor."""

    def __init__(self, provider: StructuredPlanProvider) -> None:
        self.provider = provider

    def plan(self, objective: str) -> Plan:
        payload = self.provider.generate_plan(objective)
        return plan_from_structured(payload)

    def decompose(self, objective: str) -> StructuredGoalDecomposition:
        generator = getattr(self.provider, "generate_goal_decomposition", None)
        if not callable(generator):
            provider_name = str(getattr(self.provider, "name", "provider"))
            raise ProviderGenerationError(
                provider_name,
                "provider não implementa decomposição estruturada de Goal; "
                "ação livre não será usada como fallback",
            )
        payload = generator(objective)
        return decomposition_from_structured(payload, expected_objective=objective)


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
                if is_safety_interrupt(exc):
                    raise
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

    def decompose(self, objective: str) -> StructuredGoalDecomposition:
        """Generate one complete Goal contract with pre-execution fallback.

        Unlike :meth:`plan`, this method intentionally has no single-action or
        deterministic fallback. A caller uses it only after its semantic local
        paths could not form an unambiguous contract. Providers that expose only
        ``generate_plan`` are skipped as failures: accepting one of their free
        actions would recreate the receipt-defined-contract bug this API closes.
        """

        if not objective.strip():
            raise ValueError("O objetivo não pode ser vazio.")

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
                generator = getattr(candidate.provider, "generate_goal_decomposition", None)
                if not callable(generator):
                    raise ProviderGenerationError(
                        name,
                        "provider não suporta decomposição estruturada de Goal",
                    )
                payload = generator(objective)
                decomposition = decomposition_from_structured(
                    payload,
                    expected_objective=objective,
                )
            except Exception as exc:
                if is_safety_interrupt(exc):
                    raise
                finished = time.monotonic()
                self._record_failure(name, exc, finished, (finished - started) * 1000.0)
                continue

            finished = time.monotonic()
            health.successes += 1
            health.consecutive_failures = 0
            health.last_latency_ms = (finished - started) * 1000.0
            health.cooldown_until = 0.0
            self.last_provider = name
            return decomposition

        detail = "; ".join(f"{name}={error}" for name, error in self.last_errors.items())
        raise ProviderGenerationError(
            "router",
            "nenhum provedor conseguiu decompor o Goal com contrato válido"
            + (f" ({detail})" if detail else ""),
        )
