from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx

from .planner import ProviderGenerationError, StructuredAction

ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "open_url",
                "capture_screen",
                "active_window",
                "move_mouse",
                "click_mouse",
                "type_text",
                "press_key",
                "open_app",
            ],
        },
        "target": {"type": "string"},
    },
    "required": ["action", "target"],
    "additionalProperties": False,
}

PLANNER_SYSTEM_PROMPT = """Você é o planner de um robô local.
Converta o pedido do usuário em EXATAMENTE UMA ação estruturada conhecida.
Não gere shell, código, caminhos de executável, credenciais ou ferramentas livres.
Ações permitidas: open_url, capture_screen, active_window, move_mouse, click_mouse,
type_text, press_key e open_app.
O campo target deve conter apenas o alvo necessário para a ação.
A resposta será validada novamente pela aplicação e pela Policy Layer antes de qualquer execução.
"""


def _validated_mapping(value: Any, provider: str) -> Mapping[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ProviderGenerationError(provider, "resposta não contém JSON válido") from exc

    if not isinstance(value, Mapping):
        raise ProviderGenerationError(provider, "resposta estruturada não é um objeto JSON")

    try:
        parsed = StructuredAction.model_validate(dict(value))
    except Exception as exc:
        raise ProviderGenerationError(provider, "resposta não respeita StructuredAction") from exc
    return parsed.model_dump()


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _safe_http_error_detail(response: httpx.Response) -> str | None:
    """Extract only compact provider error code/status/message for diagnostics.

    Request headers, API keys and request bodies are never copied into telemetry.
    """

    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, Mapping):
        return None

    error = payload.get("error")
    parts: list[str] = []
    if isinstance(error, Mapping):
        code = error.get("status") or error.get("code")
        message = error.get("message")
        if code is not None:
            parts.append(str(code))
        if isinstance(message, str) and message.strip():
            parts.append(message.strip())
    elif isinstance(error, str) and error.strip():
        parts.append(error.strip())
    else:
        code = payload.get("code")
        message = payload.get("message")
        if code is not None:
            parts.append(str(code))
        if isinstance(message, str) and message.strip():
            parts.append(message.strip())

    if not parts:
        return None
    detail = ": ".join(parts).replace("\r", " ").replace("\n", " ")
    return detail[:300]


def _post_json(
    provider: str,
    url: str,
    *,
    headers: Mapping[str, str],
    body: Mapping[str, Any],
    timeout_seconds: float,
) -> Mapping[str, Any]:
    try:
        response = httpx.post(url, headers=dict(headers), json=dict(body), timeout=timeout_seconds)
    except httpx.HTTPError as exc:
        raise ProviderGenerationError(provider, "falha de rede ao chamar o provedor") from exc

    if response.status_code >= 400:
        detail = _safe_http_error_detail(response)
        message = f"HTTP {response.status_code}"
        if detail:
            message = f"{message}: {detail}"
        raise ProviderGenerationError(
            provider,
            message,
            status_code=response.status_code,
            retry_after_seconds=_retry_after_seconds(response),
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderGenerationError(provider, "resposta HTTP não é JSON") from exc

    if not isinstance(payload, Mapping):
        raise ProviderGenerationError(provider, "resposta HTTP inesperada")
    return payload


class ZAIProvider:
    name = "zai"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "glm-4.7-flash",
        timeout_seconds: float = 25.0,
        base_url: str = "https://api.z.ai/api/paas/v4",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.base_url = base_url.rstrip("/")

    def generate_plan(self, objective: str) -> Mapping[str, Any]:
        payload = _post_json(
            self.name,
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept-Language": "en-US,en",
            },
            body={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                    {"role": "user", "content": objective},
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": 160,
                "temperature": 0.1,
            },
            timeout_seconds=self.timeout_seconds,
        )
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderGenerationError(self.name, "estrutura de resposta inesperada") from exc
        return _validated_mapping(content, self.name)


class CloudflareWorkersAIProvider:
    name = "cloudflare"

    def __init__(
        self,
        api_token: str,
        account_id: str,
        *,
        model: str = "@cf/meta/llama-3.1-8b-instruct-fast",
        timeout_seconds: float = 25.0,
    ) -> None:
        self.api_token = api_token
        self.account_id = account_id
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate_plan(self, objective: str) -> Mapping[str, Any]:
        payload = _post_json(
            self.name,
            f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/run/{self.model}",
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            },
            body={
                "messages": [
                    {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                    {"role": "user", "content": objective},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": ACTION_SCHEMA,
                },
                "max_tokens": 160,
                "temperature": 0.1,
            },
            timeout_seconds=self.timeout_seconds,
        )
        if payload.get("success") is False:
            raise ProviderGenerationError(self.name, "Cloudflare retornou success=false")
        try:
            response_value = payload["result"]["response"]
        except (KeyError, TypeError) as exc:
            raise ProviderGenerationError(self.name, "estrutura de resposta inesperada") from exc
        return _validated_mapping(response_value, self.name)


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gemini-3.5-flash",
        timeout_seconds: float = 25.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate_plan(self, objective: str) -> Mapping[str, Any]:
        prompt = f"{PLANNER_SYSTEM_PROMPT}\nPedido do usuário:\n{objective}"
        payload = _post_json(
            self.name,
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            body={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseJsonSchema": ACTION_SCHEMA,
                    "temperature": 0.1,
                    "maxOutputTokens": 160,
                },
            },
            timeout_seconds=self.timeout_seconds,
        )
        try:
            content = payload["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderGenerationError(self.name, "estrutura de resposta inesperada") from exc
        return _validated_mapping(content, self.name)
