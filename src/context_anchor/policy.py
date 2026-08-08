from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import quote_plus, urlparse

from .desktop import SUPPORTED_APP_IDS, canonical_app_id


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

ALLOWED_KEYS = frozenset(
    {
        "enter",
        "tab",
        "esc",
        "escape",
        "up",
        "down",
        "left",
        "right",
        "home",
        "end",
        "pageup",
        "pagedown",
        "backspace",
        "space",
    }
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
            app_id = canonical_app_id(text[len(prefix):])
            if not app_id:
                raise ValueError("Informe o aplicativo a abrir.")
            return Plan("open_app", app_id)

    for prefix in ("pesquisar ", "buscar ", "search "):
        if lowered.startswith(prefix):
            query = text[len(prefix):].strip()
            if not query:
                raise ValueError("A pesquisa precisa de um termo.")
            return Plan("open_url", f"https://duckduckgo.com/?q={quote_plus(query)}")

    for prefix in ("abrir ", "open "):
        if lowered.startswith(prefix):
            target = text[len(prefix):].strip()
            if not target:
                raise ValueError("Informe o endereço a abrir.")
            if "://" not in target:
                target = f"https://{target}"
            return Plan("open_url", target)

    raise ValueError(
        "Comando ainda não suportado. Use navegador ou uma ação de desktop explicitamente permitida."
    )


def _evaluate_url(target: str) -> PolicyDecision:
    parsed = urlparse(target)
    if parsed.scheme not in {"http", "https"}:
        return PolicyDecision(False, "Somente URLs HTTP/HTTPS são permitidas.")

    hostname = (parsed.hostname or "").casefold()
    if not hostname:
        return PolicyDecision(False, "URL sem hostname válido.")

    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
        return PolicyDecision(False, "Endereços locais estão bloqueados no MVP remoto.")

    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        ip = None

    if ip and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved):
        return PolicyDecision(False, "Endereços IP privados ou locais estão bloqueados.")

    return PolicyDecision(True, "Navegação permitida pela política.")


def evaluate_plan(plan: Plan, *, desktop_enabled: bool = False) -> PolicyDecision:
    if plan.action == "open_url":
        return _evaluate_url(plan.target)

    if plan.action not in DESKTOP_ACTIONS:
        return PolicyDecision(False, "Ação fora da allowlist atual.")

    if not desktop_enabled:
        return PolicyDecision(False, "Controle de desktop está desativado localmente.")

    if plan.action in {"capture_screen", "active_window"}:
        return PolicyDecision(True, "Percepção local permitida.")

    if plan.action == "open_app":
        if canonical_app_id(plan.target) not in SUPPORTED_APP_IDS:
            return PolicyDecision(False, "Aplicativo fora da allowlist local.")
        return PolicyDecision(True, "Aplicativo permitido pela allowlist local.")

    if plan.action == "move_mouse":
        if not re.fullmatch(r"\d+,\d+", plan.target):
            return PolicyDecision(False, "Coordenadas de mouse inválidas.")
        x, y = (int(part) for part in plan.target.split(",", maxsplit=1))
        if x > 9999 or y > 9999:
            return PolicyDecision(False, "Coordenadas excedem o limite de segurança.")
        return PolicyDecision(True, "Movimento de mouse permitido.")

    if plan.action == "click_mouse":
        if plan.target not in {"left", "right"}:
            return PolicyDecision(False, "Botão de mouse inválido.")
        return PolicyDecision(True, "Clique permitido.")

    if plan.action == "type_text":
        if not plan.target or len(plan.target) > 500:
            return PolicyDecision(False, "Texto vazio ou acima do limite de 500 caracteres.")
        if "\n" in plan.target or "\r" in plan.target:
            return PolicyDecision(False, "Quebras de linha exigem ação de tecla separada.")
        if not all(char.isprintable() for char in plan.target):
            return PolicyDecision(False, "Texto contém caracteres de controle.")
        return PolicyDecision(True, "Digitação permitida.")

    if plan.action == "press_key":
        if plan.target not in ALLOWED_KEYS:
            return PolicyDecision(False, "Tecla fora da allowlist atual.")
        return PolicyDecision(True, "Tecla permitida.")

    return PolicyDecision(False, "Ação recusada pela política.")
