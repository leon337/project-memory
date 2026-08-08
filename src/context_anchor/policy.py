from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import quote_plus, urlparse


@dataclass(frozen=True)
class Plan:
    action: str
    target: str


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str


def plan_command(command: str) -> Plan:
    text = command.strip()
    lowered = text.casefold()

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
        "Comando ainda não suportado no MVP. Use 'abrir <site>' ou 'pesquisar <termo>'."
    )


def evaluate_plan(plan: Plan) -> PolicyDecision:
    if plan.action != "open_url":
        return PolicyDecision(False, "Ação fora da allowlist do MVP.")

    parsed = urlparse(plan.target)
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

    return PolicyDecision(True, "Ação permitida pela política do MVP.")
