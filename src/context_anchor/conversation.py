from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Protocol

import httpx
from google import genai
from google.genai import types

from .config import LocalAgentSettings
from .redaction import redact_exception, redact_text


CANONICAL_PROJECT_NAME = "project-memory"

PROJECT_CONTEXT_FILES = (
    "README.md",
    "docs/STATUS.md",
    "docs/ARCHITECTURE.md",
    "docs/DECISIONS.md",
    "docs/NEXT.md",
)

CONVERSATION_SYSTEM_PROMPT = """Você é a IA conversacional do Painel do Robô do projeto project-memory.
Sua função nesta rota é conversar, explicar o projeto, esclarecer o estado e orientar o operador.

REGRAS OBRIGATÓRIAS:
- esta conversa NÃO executa ações físicas, NÃO cria tasks e NÃO chama mouse, teclado, navegador ou subprocessos;
- não afirme que uma ação foi executada só porque o usuário pediu;
- diferencie fatos do contexto fornecido de hipóteses ou sugestões;
- não exponha credenciais, segredos, conteúdo de .env ou cadeia privada de raciocínio;
- quando falar de conclusão de objetivos do Robô, respeite que somente GoalVerifier + evidência autorizam succeeded;
- responda em português do Brasil, de forma direta e útil.
"""

CANONICAL_IDENTITY_PROMPT = """IDENTIDADE CANÔNICA — PRIORIDADE MÁXIMA:
- o nome do projeto é exatamente `project-memory`;
- títulos de produto, versão, dashboard ou documentação, como `Robô Operador — MVP 0.3`, NÃO substituem o nome do projeto;
- quando o usuário perguntar em qual projeto você está ou pedir o nome do projeto, responda `project-memory` como identidade canônica e não escolha um título encontrado no contexto.
"""


class ConversationBackend(Protocol):
    def reply(self, message: str) -> dict[str, str]: ...


class ProjectConversationService:
    """Read-only conversational surface isolated from the Task/Goal execution path."""

    def __init__(
        self,
        *,
        project_root: Path | str | None = None,
        settings: LocalAgentSettings | None = None,
    ) -> None:
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self._settings = settings

    @property
    def settings(self) -> LocalAgentSettings:
        if self._settings is None:
            self._settings = LocalAgentSettings()
        return self._settings

    def _context(self) -> tuple[str, str]:
        sections: list[str] = []
        budget = 18_000
        used = 0
        for relative in PROJECT_CONTEXT_FILES:
            path = self.project_root / relative
            if not path.is_file():
                continue
            raw = path.read_text(encoding="utf-8", errors="replace")
            safe = redact_text(raw, max_chars=max(0, min(5_000, budget - used)))
            if not safe:
                continue
            sections.append(f"\n--- {relative} ---\n{safe}")
            used += len(safe)
            if used >= budget:
                break
        context = "".join(sections) or "Projeto: project-memory. Contexto documental local indisponível."
        version = hashlib.sha256(context.encode("utf-8")).hexdigest()[:16]
        return context, version

    def _messages(self) -> tuple[str, str]:
        context, version = self._context()
        system = (
            f"{CONVERSATION_SYSTEM_PROMPT}\n\n"
            f"CONTEXTO SANITIZADO DO PROJETO:\n{context}\n\n"
            f"{CANONICAL_IDENTITY_PROMPT}"
        )
        return system, version

    @staticmethod
    def _requires_project_identity(message: str) -> bool:
        normalized = " ".join(message.casefold().split())
        if "projeto" not in normalized:
            return False
        markers = (
            "qual projeto",
            "em qual projeto",
            "que projeto",
            "nome do projeto",
        )
        return any(marker in normalized for marker in markers)

    @staticmethod
    def _reply_respects_known_facts(message: str, text: str) -> bool:
        if ProjectConversationService._requires_project_identity(message):
            return CANONICAL_PROJECT_NAME in text.casefold()
        return True

    def _zai(self, system: str, message: str) -> tuple[str, str, str]:
        cfg = self.settings
        if not cfg.zai_api_key:
            raise RuntimeError("Z.AI não configurado")
        response = httpx.post(
            "https://api.z.ai/api/paas/v4/chat/completions",
            headers={
                "Authorization": f"Bearer {cfg.zai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": cfg.zai_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": message},
                ],
                "temperature": 0.2,
                "max_tokens": 900,
            },
            timeout=cfg.planner_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        value = payload["choices"][0]["message"]["content"]
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError("Z.AI não retornou texto")
        return value.strip(), "zai", cfg.zai_model

    def _cloudflare(self, system: str, message: str) -> tuple[str, str, str]:
        cfg = self.settings
        if not cfg.cloudflare_api_token or not cfg.cloudflare_account_id:
            raise RuntimeError("Cloudflare Workers AI não configurado")
        response = httpx.post(
            f"https://api.cloudflare.com/client/v4/accounts/{cfg.cloudflare_account_id}/ai/run/{cfg.cloudflare_model}",
            headers={
                "Authorization": f"Bearer {cfg.cloudflare_api_token}",
                "Content-Type": "application/json",
            },
            json={
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": message},
                ],
                "temperature": 0.2,
                "max_tokens": 900,
            },
            timeout=cfg.planner_timeout_seconds,
        )
        response.raise_for_status()
        payload: Any = response.json()
        if isinstance(payload, dict) and payload.get("success") is False:
            raise RuntimeError("Cloudflare Workers AI retornou success=false")
        value = payload.get("result", {}).get("response") if isinstance(payload, dict) else None
        if isinstance(value, dict):
            value = value.get("response") or value.get("text")
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError("Cloudflare Workers AI não retornou texto")
        return value.strip(), "cloudflare", cfg.cloudflare_model

    def _gemini(self, system: str, message: str) -> tuple[str, str, str]:
        cfg = self.settings
        if not cfg.gemini_api_key:
            raise RuntimeError("Gemini não configurado")
        timeout_ms = max(int(cfg.planner_timeout_seconds * 1000), 10_500)
        client = genai.Client(
            api_key=cfg.gemini_api_key,
            http_options=types.HttpOptions(timeout=timeout_ms),
        )
        response = client.models.generate_content(
            model=cfg.gemini_model,
            contents=message,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.2,
                max_output_tokens=900,
            ),
        )
        value = getattr(response, "text", None)
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError("Gemini não retornou texto")
        return value.strip(), "gemini", cfg.gemini_model

    def reply(self, message: str) -> dict[str, str]:
        clean_message = message.strip()
        if not clean_message:
            raise ValueError("Mensagem vazia.")
        if len(clean_message) > 2_000:
            raise ValueError("Mensagem longa demais para a conversa do Painel.")

        safe_message = redact_text(clean_message, max_chars=2_000)
        system, context_version = self._messages()
        errors: list[str] = []
        for call in (self._cloudflare, self._zai, self._gemini):
            try:
                text, provider, model = call(system, safe_message)
            except Exception as exc:
                errors.append(redact_exception(exc))
                continue
            if not self._reply_respects_known_facts(safe_message, text):
                errors.append(
                    f"{provider}: resposta contradiz identidade canônica {CANONICAL_PROJECT_NAME}"
                )
                continue
            return {
                "reply": redact_text(text, max_chars=8_000),
                "provider": provider,
                "model": model,
                "context_version": context_version,
            }

        detail = "; ".join(errors[-3:]) if errors else "nenhum provedor configurado"
        raise RuntimeError(f"Nenhum provedor de conversa disponível: {detail}")


__all__ = ["ConversationBackend", "ProjectConversationService"]