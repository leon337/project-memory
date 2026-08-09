from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx
from google import genai
from google.genai import types

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


def _decode_json_text(value: str, provider: str) -> Any:
    text = value.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderGenerationError(provider, "resposta não contém JSON válido") from exc


def _validated_mapping(value: Any, provider: str) -> Mapping[str, Any]:
    if isinstance(value, str):
        value = _decode_json_text(value, provider)

    if hasattr(value, "model_dump"):
        value = value.model_dump()

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


def _safe_sdk_error_detail(exc: Exception, secret: str) -> str:
    status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    text = str(exc).replace("\r", " ").replace("\n", " ").strip()
    if secret:
        text = text.replace(secret, "[redacted]")
    if status_code is not None and str(status_code) not in text:
        text = f"{status_code}: {text}"
    return text[:300] or exc.__class__.__name__


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
    _minimum_timeout_ms = 10_500

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gemini-3.6-flash",
        timeout_seconds: float = 25.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        timeout_ms = max(int(timeout_seconds * 1000), self._minimum_timeout_ms)
        retry_options = types.HttpRetryOptions(
            attempts=1,
            initial_delay=0.5,
            max_delay=1.0,
            exp_base=2.0,
            jitter=0.5,
            http_status_codes=[408, 429, 500, 502, 503, 504],
        )
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=timeout_ms,
                retry_options=retry_options,
            ),
        )
        self._config = types.GenerateContentConfig(
            system_instruction=PLANNER_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_json_schema=ACTION_SCHEMA,
            temperature=0.1,
            max_output_tokens=160,
        )

    def generate_plan(self, objective: str) -> Mapping[str, Any]:
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=objective,
                config=self._config,
            )
        except Exception as exc:
            status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if not isinstance(status_code, int):
                status_code = None
            raise ProviderGenerationError(
                self.name,
                _safe_sdk_error_detail(exc, self.api_key),
                status_code=status_code,
            ) from exc

        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            return _validated_mapping(parsed, self.name)

        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise ProviderGenerationError(self.name, "SDK Gemini não retornou conteúdo estruturado")
        return _validated_mapping(text, self.name)
