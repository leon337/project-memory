from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum

from .policy import Plan, plan_command, plan_local_sequence


class IntentKind(str, Enum):
    """Small, provider-independent vocabulary understood by the Goal Runtime."""

    SEARCH_TO_EDITOR = "search_to_editor"
    CONDITIONAL_SITE = "conditional_site"
    OPEN_AND_WRITE = "open_and_write"
    NAMED_BROWSER_SEARCH = "named_browser_search"
    SEARCH = "search"
    INFORMATION = "information"
    OPEN_CAPABILITY = "open_capability"
    DETERMINISTIC = "deterministic"
    GENERIC = "generic"


# More explicit alias for callers that prefer the type name to mirror GoalIntent.
GoalIntentKind = IntentKind


@dataclass(frozen=True, slots=True)
class GoalIntent:
    """Typed semantic result; absent entities remain ``None``, never guessed.

    ``plans`` is only populated when the existing deterministic Policy can
    represent the request without losing part of it.  Compound and conditional
    intents deliberately expose their dataflow instead of pretending that one
    action is a complete plan.
    """

    kind: IntentKind
    original_command: str
    capabilities: tuple[str, ...] = ()
    capability: str | None = None
    app_hint: str | None = None
    browser: str | None = None
    url: str | None = None
    query: str | None = None
    text: str | None = None
    accessible_text: str | None = None
    unavailable_text: str | None = None
    plans: tuple[Plan, ...] = ()

    @property
    def true_text(self) -> str | None:
        return self.accessible_text

    @property
    def false_text(self) -> str | None:
        return self.unavailable_text

    @property
    def local_plans(self) -> tuple[Plan, ...]:
        return self.plans


@dataclass(frozen=True, slots=True)
class SemanticEffectCoverage:
    """Material action events found in a command, plus lossless-parse status."""

    events: tuple[str, ...]
    has_unclassified_clause: bool


@dataclass(frozen=True, slots=True)
class _Token:
    raw: str
    normalized: str
    start: int
    end: int


_WORD_RE = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", re.UNICODE)
_URL_RE = re.compile(
    r"(?<![@\w])(?:"
    r"https?://[^\s<>\"']+|"
    r"localhost(?::\d+)?(?:/[^\s<>\"']*)?|"
    r"(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?::\d+)?(?:/[^\s<>\"']*)?"
    r")",
    re.IGNORECASE,
)
_QUOTED_RE = re.compile(r'"([^"\n]+)"|“([^”\n]+)”|\'([^\'\n]+)\'')

_OPEN_WORDS = {
    "abra",
    "abre",
    "abrir",
    "inicie",
    "iniciar",
    "lance",
    "lancar",
    "execute",
    "executar",
}
_WRITE_WORDS = {
    "anote",
    "copie",
    "digite",
    "digitar",
    "escreva",
    "escrever",
    "insira",
    "coloque",
    "registre",
    "transcreva",
}
_SEARCH_WORDS = {
    "busque",
    "buscar",
    "consulte",
    "encontre",
    "pesquise",
    "pesquisar",
    "procure",
    "procurar",
    "search",
}
_EDITOR_WORDS = {
    "editor",
    "gedit",
    "notepad",
    "pluma",
    "mousepad",
    "xed",
}
_RESULT_WORDS = {"resultado", "resultados", "link", "item"}
_FIRST_WORDS = {"primeiro", "primeira", "inicial"}
_TITLE_WORDS = {"titulo", "cabecalho"}
_ACCESS_WORDS = {
    "acessivel",
    "acessibilidade",
    "alcancavel",
    "disponivel",
    "funcionando",
    "online",
    "responde",
    "respondendo",
}
_NEGATIVE_BRANCH_WORDS = {"contrario", "indisponivel", "negativo", "nao", "senao"}

# Effects outside the deliberately small local Goal Runtime must never disappear
# merely because the same sentence also contains an easy, supported action.  The
# vocabulary is conceptual (inflections/aliases), not a collection of accepted
# full commands.  Unknown goals are handed to the structured decomposer, which
# can then reject them before any physical action.
_UNSUPPORTED_EFFECT_WORDS = {
    "apague",
    "apagar",
    "delete",
    "deletar",
    "envie",
    "enviar",
    "exclua",
    "excluir",
    "instale",
    "instalar",
    "mande",
    "mandar",
    "publique",
    "publicar",
    "role",
    "rolar",
    "scroll",
    "remova",
    "remover",
    "suba",
    "upload",
}
_BACKUP_NOUNS = {"backup", "copia"}
_BACKUP_VERBS = {"crie", "criar", "faca", "fazer", "gere", "gerar"}

_BROWSER_ALIASES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("brave", "browser"), "brave-browser"),
    (("google", "chrome"), "chromium"),
    (("brave",), "brave-browser"),
    (("firefox",), "firefox"),
    (("chromium",), "chromium"),
    (("chrome",), "chromium"),
    (("opera",), "opera"),
)


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def _tokens(command: str) -> tuple[_Token, ...]:
    return tuple(
        _Token(match.group(0), _fold(match.group(0)), match.start(), match.end())
        for match in _WORD_RE.finditer(command)
    )


def _norms(tokens: tuple[_Token, ...]) -> tuple[str, ...]:
    return tuple(token.normalized for token in tokens)


def _has_sequence(tokens: tuple[_Token, ...], sequence: tuple[str, ...]) -> bool:
    values = _norms(tokens)
    size = len(sequence)
    return any(values[index : index + size] == sequence for index in range(len(values) - size + 1))


def _has_any(tokens: tuple[_Token, ...], values: set[str]) -> bool:
    return any(token.normalized in values for token in tokens)


def _has_unsupported_effect(tokens: tuple[_Token, ...]) -> bool:
    """Return true only for requested effects the local runtime cannot prove.

    Nouns such as ``backup`` may legitimately occur inside a research query, so
    they require an action verb.  Imperative/infinitive destructive or external
    communication verbs are independently material and fail closed.
    """

    if _has_any(tokens, _UNSUPPORTED_EFFECT_WORDS):
        return True
    words = set(_norms(tokens))
    return bool(words.intersection(_BACKUP_NOUNS) and words.intersection(_BACKUP_VERBS))


def _protected_intent_ranges(command: str, intent: GoalIntent) -> tuple[tuple[int, int], ...]:
    ranges = [(match.start(), match.end()) for match in _QUOTED_RE.finditer(command)]
    folded_command = command.casefold()
    for value in (
        intent.query,
        intent.text,
        intent.accessible_text,
        intent.unavailable_text,
    ):
        if not value:
            continue
        start = folded_command.rfind(value.casefold())
        if start >= 0:
            ranges.append((start, start + len(value)))
    if intent.kind is IntentKind.DETERMINISTIC:
        for plan in intent.plans:
            if plan.action != "type_text":
                continue
            start = folded_command.rfind(plan.target.casefold())
            if start >= 0:
                ranges.append((start, start + len(plan.target)))
    ranges.extend((match.start(), match.end()) for match in _URL_RE.finditer(command))
    return tuple(ranges)


def _token_is_protected(token: _Token, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= token.start and token.end <= end for start, end in ranges)


def _action_events(
    tokens: tuple[_Token, ...],
    *,
    command: str,
    protected_ranges: tuple[tuple[int, int], ...],
) -> tuple[str, ...]:
    navigation = {"acesse", "acessar", "entre", "ir", "va", "visite", "visitar"}
    capture = {"capture", "capturar"}
    condition = {"cheque", "teste", "testar", "verifique"}
    information = {
        "descubra",
        "explique",
        "explicar",
        "significa",
        "significado",
        "saber",
    }
    calculation = {"calcule", "calcular", "some", "somar"}
    note_actions = {"anotar", "tomar"}
    values = set(_norms(tokens))
    quoted_ranges = tuple(
        (match.start(), match.end()) for match in _QUOTED_RE.finditer(command)
    )
    fillers = {
        "a",
        "agora",
        "as",
        "brave",
        "caso",
        "chrome",
        "chromium",
        "contrario",
        "de",
        "do",
        "em",
        "esta",
        "esteja",
        "estiver",
        "favor",
        "firefox",
        "gostaria",
        "na",
        "nao",
        "navegador",
        "no",
        "o",
        "opera",
        "os",
        "pode",
        "poderia",
        "por",
        "preciso",
        "quero",
        "se",
        "senao",
        "voce",
    }
    events: list[str] = []
    expect_head = True
    for index, token in enumerate(tokens):
        if index:
            between = command[tokens[index - 1].end : token.start]
            if re.search(r"[;.!?]", between):
                expect_head = True
        is_connector = token.normalized in {"depois", "entao", "seguida"} or (
            token.raw.casefold() == "e"
        )
        if is_connector:
            expect_head = True
            continue
        if not expect_head:
            continue
        if token.normalized in fillers:
            continue
        expect_head = False
        if _token_is_protected(token, quoted_ranges):
            continue
        word = token.normalized
        if word in _OPEN_WORDS:
            events.append("open")
        elif word in _WRITE_WORDS:
            events.append("write")
        elif word in _SEARCH_WORDS:
            events.append("search")
        elif word in navigation:
            events.append("navigate")
        elif word in capture:
            events.append("capture")
        elif word in condition:
            events.append("condition")
        elif word in information:
            events.append("information")
        elif word in note_actions and values.intersection(
            {"anotacao", "anotacoes", "ideia", "nota", "notas"}
        ):
            events.append("write")
        elif word in calculation or (
            word in {"faca", "fazer"}
            and values.intersection({"calculo", "calculos", "conta", "contas"})
        ):
            events.append("calculate")
    return tuple(events)


def _has_unknown_material_clause(
    tokens: tuple[_Token, ...],
    command: str,
    *,
    protected_ranges: tuple[tuple[int, int], ...] = (),
) -> bool:
    """Require every clause head to be either mapped or classified content."""

    known = (
        _OPEN_WORDS
        | _WRITE_WORDS
        | _SEARCH_WORDS
        | _UNSUPPORTED_EFFECT_WORDS
        | {
            "acesse",
            "acessar",
            "calcule",
            "calcular",
            "capture",
            "capturar",
            "cheque",
            "descubra",
            "explique",
            "explicar",
            "ir",
            "saber",
            "significa",
            "significado",
            "some",
            "somar",
            "teste",
            "testar",
            "va",
            "verifique",
            "visite",
            "visitar",
        }
    )
    connectors = {"depois", "e", "entao", "seguida"}
    fillers = {
        "a",
        "agora",
        "as",
        "de",
        "do",
        "em",
        "esteja",
        "estiver",
        "favor",
        "gostaria",
        "na",
        "nao",
        "navegador",
        "no",
        "o",
        "os",
        "pode",
        "poderia",
        "por",
        "preciso",
        "quero",
        "se",
        "senao",
        "voce",
        "brave",
        "caso",
        "chrome",
        "chromium",
        "contrario",
        "esta",
        "firefox",
        "opera",
    }
    weak_continuations = {"da", "das", "de", "do", "dos", "e", "em", "para"}
    values = _norms(tokens)
    expect_head = True
    head_from_connector = False
    for index, token in enumerate(tokens):
        if index:
            between = command[tokens[index - 1].end : token.start]
            if re.search(r"[;.!?]", between):
                expect_head = True
                head_from_connector = True
        is_connector = token.normalized in (connectors - {"e"}) or (
            token.raw.casefold() == "e"
        )
        if is_connector:
            expect_head = True
            head_from_connector = True
            continue
        if not expect_head:
            continue
        if token.normalized in fillers:
            continue
        expect_head = False
        if token.normalized in {"faca", "fazer"} and set(values).intersection(
            {
                "anotacao",
                "anotacoes",
                "calculo",
                "calculos",
                "conta",
                "contas",
                "nota",
                "notas",
            }
        ):
            continue
        if token.normalized in {"anotar", "tomar"} and set(values).intersection(
            {"anotacao", "anotacoes", "ideia", "nota", "notas"}
        ):
            continue
        if token.normalized in known:
            continue
        following = values[index + 1] if index + 1 < len(values) else ""
        protected = _token_is_protected(token, protected_ranges)
        action_shaped = (
            token.normalized in {"de", "toque"}
            or token.normalized.endswith(("ar", "er", "ir", "a", "e", "ie"))
        ) and following not in weak_continuations
        if not protected or (head_from_connector and action_shaped):
            return True
    return False


def _lossless_fast_intent(
    command: str,
    tokens: tuple[_Token, ...],
    intent: GoalIntent,
) -> GoalIntent:
    """Keep a fast path only when it accounts for every material action."""

    protected_ranges = _protected_intent_ranges(command, intent)
    maxima: dict[IntentKind, dict[str, int]] = {
        IntentKind.CONDITIONAL_SITE: {
            "condition": 1,
            "navigate": 1,
            "open": 1,
            "write": 2,
        },
        IntentKind.SEARCH_TO_EDITOR: {"search": 1, "open": 1, "write": 1},
        IntentKind.OPEN_AND_WRITE: {"open": 1, "write": 1},
        IntentKind.NAMED_BROWSER_SEARCH: {"open": 1, "navigate": 1, "search": 1},
        IntentKind.SEARCH: {"search": 1},
        IntentKind.INFORMATION: {"information": 2},
    }
    if intent.kind is IntentKind.OPEN_CAPABILITY:
        if intent.capability == "calculate":
            permitted = {"calculate": 1, "open": 1}
        elif intent.capability == "text.edit":
            # A note need may imply opening a writable surface, but an explicit
            # write verb carries a payload/effect that readiness alone cannot
            # satisfy. That must become OPEN_AND_WRITE or fail to GENERIC.
            permitted = {
                "open": 1,
                "write": 0 if _has_any(tokens, _WRITE_WORDS) else 1,
            }
        else:
            permitted = {"open": 1}
    elif intent.kind is IntentKind.DETERMINISTIC:
        action_family = {
            "capture_screen": "capture",
            "open_app": "open",
            "open_url": "navigate",
            "type_text": "write",
        }
        permitted: dict[str, int] = {}
        for plan in intent.plans:
            family = action_family.get(plan.action)
            if family:
                permitted[family] = permitted.get(family, 0) + 1
                if plan.action == "open_url":
                    # Natural-language navigation commonly uses "abra" even
                    # though the locally materialized action is open_url.
                    permitted["open"] = permitted.get("open", 0) + 1
    else:
        permitted = maxima.get(intent.kind, {})
    if _has_unknown_material_clause(
        tokens,
        command,
        protected_ranges=protected_ranges,
    ):
        return GoalIntent(kind=IntentKind.GENERIC, original_command=command)
    counts: dict[str, int] = {}
    for family in _action_events(
        tokens,
        command=command,
        protected_ranges=protected_ranges,
    ):
        counts[family] = counts.get(family, 0) + 1
    if any(count > permitted.get(family, 0) for family, count in counts.items()):
        return GoalIntent(kind=IntentKind.GENERIC, original_command=command)
    return intent


def analyze_semantic_effects(command: str) -> SemanticEffectCoverage:
    """Analyze action cardinality for structured decomposition validation."""

    tokens = _tokens(command)
    probe = GoalIntent(
        kind=IntentKind.GENERIC,
        original_command=command,
        query=_extract_search_query(command, tokens),
    )
    protected_ranges = _protected_intent_ranges(command, probe)
    event_ranges = _protected_intent_ranges(
        command,
        GoalIntent(kind=IntentKind.GENERIC, original_command=command),
    )
    return SemanticEffectCoverage(
        events=_action_events(
            tokens,
            command=command,
            protected_ranges=event_ranges,
        ),
        has_unclassified_clause=_has_unknown_material_clause(
            tokens,
            command,
            protected_ranges=protected_ranges,
        ),
    )


def _trim_value(value: str) -> str:
    result = value.strip(" \t\r\n,;:")
    result = re.sub(
        r"\s+(?:para|pra)\s+mim(?:\s+por\s+favor)?\s*$|\s+por\s+favor\s*$",
        "",
        result,
        flags=re.IGNORECASE,
    ).strip()
    if len(result) >= 2 and (result[0], result[-1]) in {
        ('"', '"'),
        ("'", "'"),
        ("“", "”"),
    }:
        result = result[1:-1].strip()
    return result.rstrip(".,;: ")


def _normalize_url(raw: str) -> str:
    target = raw.rstrip(".,;:!?)]}\"")
    if not target.casefold().startswith(("http://", "https://")):
        target = f"https://{target}"
    return target


def _extract_url(command: str) -> str | None:
    match = _URL_RE.search(command)
    return _normalize_url(match.group(0)) if match else None


def _safe_policy_plans(command: str) -> tuple[Plan, ...]:
    sequence = plan_local_sequence(command)
    if sequence is not None:
        return sequence
    try:
        return (plan_command(command),)
    except (TypeError, ValueError):
        return ()


def _extract_browser(tokens: tuple[_Token, ...]) -> tuple[str | None, str | None]:
    values = _norms(tokens)
    search_positions = [
        index for index, value in enumerate(values) if value in _SEARCH_WORDS
    ]
    first_search = min(search_positions) if search_positions else None
    binding_words = _OPEN_WORDS | {
        "browser",
        "com",
        "na",
        "navegador",
        "no",
        "pela",
        "pelo",
        "use",
        "usar",
        "utilize",
        "utilizar",
    }
    for phrase, canonical in _BROWSER_ALIASES:
        size = len(phrase)
        for index in range(len(values) - size + 1):
            if values[index : index + size] != phrase:
                continue
            # An application name inside the query is subject matter, not a
            # request to run that application ("Pesquise Firefox segurança").
            # A named browser needs an explicit syntactic binding such as
            # "no Brave", "use Firefox" or "navegador Chrome".
            if first_search is not None and index > first_search:
                continue
            left = values[max(0, index - 3) : index]
            if not set(left).intersection(binding_words):
                continue
            raw = " ".join(token.raw for token in tokens[index : index + size])
            return canonical, raw

    stop_words = _OPEN_WORDS | _SEARCH_WORDS | {
        "acesse",
        "acessar",
        "e",
        "em",
        "entre",
        "ir",
        "para",
        "va",
        "visite",
        "visitar",
    }
    for index, token in enumerate(tokens[:-1]):
        if token.normalized not in {"browser", "navegador"}:
            continue
        if first_search is not None and index > first_search:
            continue
        candidate = tokens[index + 1]
        if candidate.normalized not in stop_words:
            return candidate.normalized, candidate.raw
    return None, None


def _search_transition_index(tokens: tuple[_Token, ...], search_index: int) -> int | None:
    """Find the semantic transition from query to a downstream editor step."""

    for index in range(search_index + 1, len(tokens)):
        remaining = tokens[index:]
        if not (_has_any(remaining, _EDITOR_WORDS) and _has_any(remaining, _WRITE_WORDS)):
            continue
        current = tokens[index].normalized
        following = tokens[index + 1].normalized if index + 1 < len(tokens) else ""
        if current in {"depois", "entao"}:
            return index
        if (current, following) in {("e", "depois"), ("em", "seguida"), ("na", "sequencia")}:
            return index
        if current in _OPEN_WORDS:
            return index
    return None


def _extract_search_query(command: str, tokens: tuple[_Token, ...]) -> str | None:
    search_indices = [
        index for index, token in enumerate(tokens) if token.normalized in _SEARCH_WORDS
    ]
    if not search_indices:
        return None
    index = search_indices[-1]
    start = tokens[index].end
    boundary_index = _search_transition_index(tokens, index)
    end = tokens[boundary_index].start if boundary_index is not None else len(command)
    query = command[start:end].strip(" \t\r\n,;:")
    query = re.sub(
        r"^(?:(?:na|pela)\s+(?:web|internet)\s+)?(?:por|sobre)\s+",
        "",
        query,
        flags=re.IGNORECASE,
    )
    return _trim_value(query) or None


def _first_result_requested(tokens: tuple[_Token, ...]) -> bool:
    for index, token in enumerate(tokens):
        if token.normalized not in _FIRST_WORDS:
            continue
        left = max(0, index - 2)
        right = min(len(tokens), index + 4)
        if _has_any(tokens[left:right], _RESULT_WORDS):
            return True
    return False


def _editor_requested(tokens: tuple[_Token, ...]) -> bool:
    if _has_any(tokens, _EDITOR_WORDS) or _has_sequence(tokens, ("bloco", "de", "notas")):
        return True
    return (
        _has_any(tokens, {"aplicativo", "coisa", "ferramenta", "programa"})
        and _has_any(tokens, {"anotar", "escrever", "texto"})
    )


def _extract_written_text(command: str, tokens: tuple[_Token, ...]) -> str | None:
    indices = [index for index, token in enumerate(tokens) if token.normalized in _WRITE_WORDS]
    if not indices:
        return None
    token = tokens[indices[-1]]
    tail = command[token.end :].strip()
    quoted = _QUOTED_RE.match(tail.lstrip(" :"))
    if quoted:
        return next(group for group in quoted.groups() if group is not None).strip()
    tail = re.sub(r"^(?:no|num|em\s+um|em\s+uma)\s+editor(?:\s+de\s+texto)?\s*[,;:]?\s*", "", tail, flags=re.IGNORECASE)
    tail = re.sub(r"^(?:o\s+)?texto\s*[:]?\s*", "", tail, flags=re.IGNORECASE)
    return _trim_value(tail) or None


def _quoted_values(command: str) -> list[tuple[int, str]]:
    values: list[tuple[int, str]] = []
    for match in _QUOTED_RE.finditer(command):
        value = next(group for group in match.groups() if group is not None)
        values.append((match.start(), value.strip()))
    return values


def _negative_branch_offset(command: str) -> int | None:
    folded = _fold(command)
    matches = [
        folded.find(marker)
        for marker in ("se nao", "caso contrario", "do contrario", "senao", "caso nao")
        if folded.find(marker) >= 0
    ]
    return min(matches) if matches else None


def _extract_branch_texts(
    command: str, tokens: tuple[_Token, ...]
) -> tuple[str | None, str | None]:
    quoted = _quoted_values(command)
    if len(quoted) >= 2:
        negative_offset = _negative_branch_offset(command)
        if negative_offset is not None:
            before = [value for offset, value in quoted if offset < negative_offset]
            after = [value for offset, value in quoted if offset > negative_offset]
            if before and after:
                return before[-1], after[0]
        return quoted[0][1], quoted[1][1]

    write_indices = [index for index, token in enumerate(tokens) if token.normalized in _WRITE_WORDS]
    if len(write_indices) < 2:
        return None, None
    values: list[str] = []
    for position, token_index in enumerate(write_indices[:2]):
        start = tokens[token_index].end
        end = tokens[write_indices[position + 1]].start if position + 1 < 2 else len(command)
        value = command[start:end]
        value = re.split(
            r"\b(?:se\s+n[aã]o|caso\s+contr[aá]rio|do\s+contr[aá]rio|sen[aã]o|em\s+caso\s+negativo)\b",
            value,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        value = re.sub(
            r"^(?:no|num|em\s+um|em\s+uma)\s+editor(?:\s+de\s+texto)?\s*[,;:]?\s*",
            "",
            value,
            flags=re.IGNORECASE,
        )
        value = re.sub(r"^(?:o\s+)?texto\s*[:]?\s*", "", value, flags=re.IGNORECASE)
        values.append(_trim_value(value))
    return (values[0] or None), (values[1] or None)


def _informational_query(command: str, tokens: tuple[_Token, ...]) -> str | None:
    sequences = (
        ("o", "que", "significa"),
        ("quem", "e"),
        ("significado",),
        ("informacoes", "sobre"),
    )
    values = _norms(tokens)
    for sequence in sequences:
        size = len(sequence)
        for index in range(len(values) - size + 1):
            if values[index : index + size] == sequence:
                return _trim_value(command[tokens[index].start :]) or None

    for index, token in enumerate(tokens):
        if token.normalized in {"saber", "descubra", "explique", "diga", "conte"}:
            start = token.end
            value = command[start:].strip()
            value = re.sub(r"^(?:para\s+mim\s+)?(?:sobre|acerca\s+de)\s+", "", value, flags=re.IGNORECASE)
            return _trim_value(value) or None
    return None


class SemanticGoalInterpreter:
    """Classify local, unequivocal concepts before invoking a model planner.

    Classification is compositional: accents/case are normalized, concepts are
    detected independently, and entities are extracted from their spans.  No
    complete acceptance sentence is used as a parser rule.
    """

    def interpret(self, command: str) -> GoalIntent:
        if not isinstance(command, str):
            raise TypeError("command must be a string")

        tokens = _tokens(command)
        url = _extract_url(command)
        browser, browser_hint = _extract_browser(tokens)
        query = _extract_search_query(command, tokens)
        plans = _safe_policy_plans(command)

        if _has_unsupported_effect(tokens):
            return GoalIntent(kind=IntentKind.GENERIC, original_command=command)

        def covered(intent: GoalIntent) -> GoalIntent:
            return _lossless_fast_intent(command, tokens, intent)

        is_conditional = (
            url is not None
            and _has_any(tokens, _ACCESS_WORDS)
            and _has_any(tokens, {"caso", "quando", "se"})
            and _has_any(tokens, _NEGATIVE_BRANCH_WORDS)
        )
        if is_conditional:
            accessible_text, unavailable_text = _extract_branch_texts(command, tokens)
            if accessible_text and unavailable_text:
                return covered(GoalIntent(
                    kind=IntentKind.CONDITIONAL_SITE,
                    original_command=command,
                    capabilities=("browser.navigate", "text.edit"),
                    capability="browser.navigate",
                    url=url,
                    accessible_text=accessible_text,
                    unavailable_text=unavailable_text,
                ))

        is_search_to_editor = (
            query is not None
            and _first_result_requested(tokens)
            and _has_any(tokens, _TITLE_WORDS)
            and _editor_requested(tokens)
            and _has_any(tokens, _WRITE_WORDS)
        )
        if is_search_to_editor:
            return covered(GoalIntent(
                kind=IntentKind.SEARCH_TO_EDITOR,
                original_command=command,
                capabilities=("web.search", "web.read", "text.edit"),
                capability="web.search",
                query=query,
                app_hint="editor",
            ))

        written_text = _extract_written_text(command, tokens)
        if written_text and _editor_requested(tokens):
            return covered(GoalIntent(
                kind=IntentKind.OPEN_AND_WRITE,
                original_command=command,
                capabilities=("text.edit",),
                capability="text.edit",
                app_hint="editor",
                text=written_text,
                plans=plans,
            ))

        if browser and query:
            return covered(GoalIntent(
                kind=IntentKind.NAMED_BROWSER_SEARCH,
                original_command=command,
                capabilities=("browser.navigate", "web.search"),
                capability="web.search",
                app_hint=browser_hint,
                browser=browser,
                url=url,
                query=query,
                plans=plans,
            ))

        if _has_any(tokens, _SEARCH_WORDS) and query:
            return covered(GoalIntent(
                kind=IntentKind.SEARCH,
                original_command=command,
                capabilities=("web.search",),
                capability="web.search",
                browser=browser,
                url=url,
                query=query,
                plans=plans,
            ))

        code_hint: str | None = None
        for phrase in (("visual", "studio", "code"), ("vs", "code"), ("vscode",)):
            values = _norms(tokens)
            size = len(phrase)
            for index in range(len(values) - size + 1):
                if values[index : index + size] == phrase:
                    code_hint = " ".join(token.raw for token in tokens[index : index + size])
                    break
            if code_hint:
                break
        if code_hint:
            return covered(GoalIntent(
                kind=IntentKind.OPEN_CAPABILITY,
                original_command=command,
                capabilities=("code.edit",),
                capability="code.edit",
                app_hint=code_hint,
            ))

        calculate_concepts = {"calcular", "calculadora", "calculo", "calculos", "contas", "matematica", "somar"}
        if _has_any(tokens, calculate_concepts):
            if re.search(r"\d|[+*/=]", command):
                return GoalIntent(kind=IntentKind.GENERIC, original_command=command)
            return covered(GoalIntent(
                kind=IntentKind.OPEN_CAPABILITY,
                original_command=command,
                capabilities=("calculate",),
                capability="calculate",
                app_hint="calculadora" if _has_any(tokens, {"calculadora"}) else None,
            ))

        note_concepts = {"anotacao", "anotacoes", "anotar", "nota", "notas"}
        writable_surface = (
            _editor_requested(tokens)
            and _has_any(tokens, _OPEN_WORDS)
            and _has_any(tokens, {"escrever", "texto"})
        )
        if _has_any(tokens, note_concepts) or writable_surface:
            return covered(GoalIntent(
                kind=IntentKind.OPEN_CAPABILITY,
                original_command=command,
                capabilities=("text.edit",),
                capability="text.edit",
                app_hint="editor",
            ))

        information_markers = (
            _has_any(tokens, {"significado", "significa"})
            or _has_sequence(tokens, ("quero", "saber"))
            or _has_sequence(tokens, ("gostaria", "de", "saber"))
            or _has_sequence(tokens, ("quem", "e"))
            or _has_any(tokens, {"descubra", "explique"})
        )
        if information_markers:
            information_query = _informational_query(command, tokens)
            if information_query:
                return covered(GoalIntent(
                    kind=IntentKind.INFORMATION,
                    original_command=command,
                    capabilities=("web.search", "web.read"),
                    capability="web.search",
                    query=information_query,
                ))

        if url:
            # An external named browser is observable through X11, but this
            # runtime has no trustworthy DOM/URL bridge for it.  Process argv is
            # launch intent, not proof that the requested page loaded.  Leave the
            # goal for structured fail-closed handling instead of reporting a
            # partial success.
            if browser:
                return GoalIntent(kind=IntentKind.GENERIC, original_command=command)
            if plans:
                navigation_plans = plans
            elif browser:
                navigation_plans = (Plan("open_app", f"{browser} {url}"),)
            else:
                navigation_plans = (Plan("open_url", url),)
            return covered(GoalIntent(
                kind=IntentKind.DETERMINISTIC,
                original_command=command,
                capabilities=("browser.navigate",),
                capability="browser.navigate",
                app_hint=browser_hint,
                browser=browser,
                url=url,
                plans=navigation_plans,
            ))

        if plans:
            return covered(GoalIntent(
                kind=IntentKind.DETERMINISTIC,
                original_command=command,
                plans=plans,
            ))

        return GoalIntent(kind=IntentKind.GENERIC, original_command=command)


__all__ = [
    "GoalIntent",
    "GoalIntentKind",
    "IntentKind",
    "SemanticEffectCoverage",
    "SemanticGoalInterpreter",
    "analyze_semantic_effects",
]
