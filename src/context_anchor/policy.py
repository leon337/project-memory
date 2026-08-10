from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote_plus, urlparse

from .desktop import canonical_app_id
from .text_semantics import strip_exact_write_modifier


@dataclass(frozen=True)
class Plan:
    action: str
    target: str


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str


DESKTOP_ACTIONS = frozenset(
    {
        "capture_screen",
        "active_window",
        "move_mouse",
        "click_mouse",
        "type_text",
        "press_key",
        "open_app",
    }
)


def _looks_like_url_target(target: str) -> bool:
    value = target.strip()
    if not value or any(char.isspace() for char in value):
        return False
    if "://" in value:
        return True
    return bool(
        re.fullmatch(
            r"(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?::\d+)?(?:/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)?",
            value,
        )
    )


def _strip_polite_suffix(value: str) -> str:
    result = value.strip()
    patterns = (
        r"\s+(?:para|pra)\s+mim\s+por\s+favor$",
        r"\s+por\s+favor$",
        r"\s+(?:para|pra)\s+mim$",
    )
    for pattern in patterns:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE).strip()
    return result


def _normalize_url_target(value: str) -> str:
    target = _strip_polite_suffix(value)
    target = re.sub(r"^(?:o\s+)?site\s+", "", target, flags=re.IGNORECASE).strip()
    if not target:
        raise ValueError("Informe o endereço a acessar.")
    if not _looks_like_url_target(target):
        raise ValueError("O destino informado não parece uma URL ou domínio válido.")
    if "://" not in target:
        target = f"https://{target}"
    return target


def _search_engine_url(site_url: str, query: str) -> str | None:
    """Build a deterministic search URL only for search engines we know."""

    parsed = urlparse(site_url)
    hostname = (parsed.hostname or "").casefold()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    encoded = quote_plus(query.strip())
    if not encoded:
        raise ValueError("A pesquisa precisa de um termo.")

    if hostname == "google.com":
        return f"https://www.google.com/search?q={encoded}"
    if hostname == "duckduckgo.com":
        return f"https://duckduckgo.com/?q={encoded}"
    if hostname == "bing.com":
        return f"https://www.bing.com/search?q={encoded}"
    return None


def _browser_site_search_plan(command: str) -> Plan | None:
    """Resolve browser + search-engine + query phrases without provider calls."""

    match = re.fullmatch(
        r"(?:por\s+favor\s+)?(?:abra|abre|abrir|open)\s+"
        r"(?:o\s+)?(?:navegador|browser)"
        r"(?:\s+([A-Za-z0-9._-]+))?\s+e\s+"
        r"(?:acesse|acessa|acessar|visite|visitar|entre\s+em|va\s+para|vá\s+para|ir\s+para)\s+"
        r"(.+?)\s+e\s+"
        r"(?:pesquise|pesquisar|busque|buscar|procure|procurar|search)\s+"
        r"(.+)",
        command.strip(),
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    browser_name = match.group(1)
    site_url = _normalize_url_target(match.group(2))
    query = _strip_polite_suffix(match.group(3))
    search_url = _search_engine_url(site_url, query)
    if search_url is None:
        return None

    if browser_name:
        app = canonical_app_id(browser_name)
        return Plan("open_app", f"{app} {search_url}")
    return Plan("open_url", search_url)


def _browser_navigation_plan(command: str) -> Plan | None:
    """Resolve browser + site phrases without spending provider quota.

    Generic browser requests use the structured Playwright browser. If a concrete
    browser name is supplied, the local application is launched with the URL as
    an argument so requests such as "abra o navegador brave e acesse globo.com"
    still use that browser.
    """

    match = re.fullmatch(
        r"(?:por\s+favor\s+)?(?:abra|abre|abrir|open)\s+"
        r"(?:o\s+)?(?:navegador|browser)"
        r"(?:\s+([A-Za-z0-9._-]+))?\s+e\s+"
        r"(?:acesse|acessa|acessar|visite|visitar|entre\s+em|va\s+para|vá\s+para|ir\s+para)\s+"
        r"(.+)",
        command.strip(),
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    browser_name = match.group(1)
    url = _normalize_url_target(match.group(2))
    if browser_name:
        app = canonical_app_id(browser_name)
        return Plan("open_app", f"{app} {url}")
    return Plan("open_url", url)


def plan_local_sequence(command: str) -> tuple[Plan, ...] | None:
    """Recognize small compound goals that do not need an external model.

    The fast path is intentionally narrow. It preserves the exact user text and
    lets the executor verify each physical step, while avoiding unnecessary
    provider calls for deterministic sequences such as open-app + type-text.
    """

    text = command.strip()
    match = re.fullmatch(
        r"(?:por\s+favor\s+)?(?:abra|abre|abrir|open)\s+(.+?)\s+e\s+"
        r"(?:escreva|escrever|digite|digitar|type)\s+(.+)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    app_target = _strip_polite_suffix(match.group(1))
    typed_text = strip_exact_write_modifier(match.group(2))
    if not app_target or not typed_text or _looks_like_url_target(app_target):
        return None

    return (
        Plan("open_app", canonical_app_id(app_target)),
        Plan("type_text", typed_text),
    )


def plan_command(command: str) -> Plan:
    text = command.strip()
    lowered = text.casefold()

    if lowered in {"capturar tela", "ver tela", "screenshot", "tirar screenshot"}:
        return Plan("capture_screen", "screen")

    if lowered in {"janela ativa", "ver janela ativa", "qual janela ativa"}:
        return Plan("active_window", "active")

    move = re.fullmatch(r"(?:mover mouse|mover cursor)\s+(\d+)\s+(\d+)", lowered)
    if move:
        return Plan("move_mouse", f"{move.group(1)},{move.group(2)}")

    if lowered in {"clicar", "clique", "clique esquerdo", "clicar esquerdo"}:
        return Plan("click_mouse", "left")

    if lowered in {"clique direito", "clicar direito"}:
        return Plan("click_mouse", "right")

    for prefix in ("digitar ", "escrever ", "type "):
        if lowered.startswith(prefix):
            value = text[len(prefix):]
            if not value:
                raise ValueError("Informe o texto a digitar.")
            return Plan("type_text", value)

    for prefix in ("tecla ", "pressionar tecla ", "press "):
        if lowered.startswith(prefix):
            key = text[len(prefix):].strip().casefold()
            if not key:
                raise ValueError("Informe a tecla a pressionar.")
            return Plan("press_key", key)

    for prefix in ("abrir aplicativo ", "abrir app ", "open app "):
        if lowered.startswith(prefix):
            app_id = canonical_app_id(_strip_polite_suffix(text[len(prefix):]))
            if not app_id:
                raise ValueError("Informe o aplicativo a abrir.")
            return Plan("open_app", app_id)

    search_prefixes = (
        "agora pesquise ",
        "agora pesquisar ",
        "agora busque ",
        "agora buscar ",
        "agora procure ",
        "pesquise ",
        "pesquisar ",
        "busque ",
        "buscar ",
        "procure ",
        "procurar ",
        "search ",
    )
    for prefix in search_prefixes:
        if lowered.startswith(prefix):
            query = text[len(prefix):].strip()
            if not query:
                raise ValueError("A pesquisa precisa de um termo.")
            return Plan("open_url", f"https://duckduckgo.com/?q={quote_plus(query)}")

    browser_site_search = _browser_site_search_plan(text)
    if browser_site_search:
        return browser_site_search

    browser_navigation = _browser_navigation_plan(text)
    if browser_navigation:
        return browser_navigation

    for prefix in ("abrir ", "abra ", "abre ", "open "):
        if lowered.startswith(prefix):
            target = _strip_polite_suffix(text[len(prefix):])
            if not target:
                raise ValueError("Informe o alvo a abrir.")
            if _looks_like_url_target(target):
                if "://" not in target:
                    target = f"https://{target}"
                return Plan("open_url", target)
            return Plan("open_app", canonical_app_id(target))

    raise ValueError(
        "Comando ainda não suportado pelo caminho determinístico; encaminhe ao planner de IA."
    )


def _evaluate_url(target: str) -> PolicyDecision:
    parsed = urlparse(target)
    if parsed.scheme not in {"http", "https"}:
        return PolicyDecision(False, "Somente URLs HTTP/HTTPS são suportadas por open_url.")

    hostname = parsed.hostname or ""
    if not hostname:
        return PolicyDecision(False, "URL sem hostname válido.")

    return PolicyDecision(True, "Navegação permitida no perfil local permissivo.")


def evaluate_plan(plan: Plan, *, desktop_enabled: bool = False) -> PolicyDecision:
    if plan.action == "open_url":
        return _evaluate_url(plan.target)

    if plan.action == "finish":
        return PolicyDecision(True, "Finalização interna do objetivo permitida.")

    if plan.action not in DESKTOP_ACTIONS:
        return PolicyDecision(False, "Ação ainda não possui executor implementado.")

    if not desktop_enabled:
        return PolicyDecision(False, "Controle de desktop está desativado localmente.")

    if plan.action in {"capture_screen", "active_window"}:
        return PolicyDecision(True, "Percepção local permitida.")

    if plan.action == "open_app":
        if not plan.target.strip():
            return PolicyDecision(False, "Aplicativo/comando vazio.")
        return PolicyDecision(True, "Aplicativo/processo permitido por padrão no perfil local.")

    if plan.action == "move_mouse":
        if not re.fullmatch(r"\d+,\d+", plan.target):
            return PolicyDecision(False, "Coordenadas de mouse inválidas.")
        return PolicyDecision(True, "Movimento de mouse permitido.")

    if plan.action == "click_mouse":
        if plan.target not in {"left", "right", "middle"}:
            return PolicyDecision(False, "Botão de mouse inválido.")
        return PolicyDecision(True, "Clique permitido.")

    if plan.action == "type_text":
        if not plan.target:
            return PolicyDecision(False, "Texto vazio.")
        if "\n" in plan.target or "\r" in plan.target:
            return PolicyDecision(False, "Quebras de linha exigem ação de tecla separada.")
        if not all(char.isprintable() for char in plan.target):
            return PolicyDecision(False, "Texto contém caracteres de controle.")
        return PolicyDecision(True, "Digitação permitida.")

    if plan.action == "press_key":
        if not plan.target.strip() or len(plan.target) > 64:
            return PolicyDecision(False, "Tecla inválida.")
        if not all(char.isprintable() for char in plan.target):
            return PolicyDecision(False, "Tecla contém caracteres de controle.")
        return PolicyDecision(True, "Tecla permitida.")

    return PolicyDecision(False, "Ação recusada pela política.")
