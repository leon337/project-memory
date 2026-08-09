from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx
from google import genai
from google.genai import types

from .planner import (
    ProviderGenerationError,
    StructuredAction,
    StructuredGoalDecomposition,
    decomposition_from_structured,
)
from .lease import is_safety_interrupt

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
                "finish",
            ],
        },
        "target": {"type": "string"},
    },
    "required": ["action", "target"],
    "additionalProperties": False,
}

# Generated from the same strict Pydantic contract that performs local
# validation. Providers may use this to improve conformance, but the schema is
# never trusted as the sole safety boundary.
GOAL_DECOMPOSITION_SCHEMA: dict[str, Any] = StructuredGoalDecomposition.model_json_schema()

PLANNER_SYSTEM_PROMPT = """Você é o planner de um robô local orientado a objetivo.
Escolha EXATAMENTE UMA próxima ação estruturada por resposta.
O pedido pode exigir várias etapas. Depois de cada etapa você poderá receber um histórico com o resultado observado e deverá decidir a próxima ação.
Use `finish` SOMENTE quando o objetivo original estiver integralmente concluído segundo o histórico verificado. Nunca use `finish` apenas porque uma etapa intermediária teve sucesso.
Ações implementadas: open_url, capture_screen, active_window, move_mouse, click_mouse,
type_text, press_key, open_app e finish.
Para `open_app`, use no target o nome curto do aplicativo/executável ou o comando local necessário. O perfil local é permissivo por padrão; a aplicação e o sistema operacional ainda validarão/executarão a ação.
Para `type_text`, target é exatamente o texto a digitar. Para `press_key`, target é a tecla.
O campo target deve conter apenas o alvo necessário para a ação. Em `finish`, target deve resumir brevemente por que o objetivo está concluído.
A resposta será validada novamente pela aplicação antes de qualquer execução.
"""

GOAL_DECOMPOSITION_SYSTEM_PROMPT = """Você é o decompositor de objetivos de um robô local.
Produza UM documento JSON completo que defina o contrato inteiro ANTES de qualquer ação física.
Copie o objetivo do usuário exatamente para `objective`; não o resuma, não o enfraqueça e não acrescente condições.

O documento deve declarar, de forma coerente e fechada: capabilities, critérios obrigatórios observáveis, subgoals e todos os steps planejados. Nenhum step pode criar critérios depois de ser executado. Não produza `finish`, comandos de shell, executáveis ou nomes de aplicativos inventados.

Operações permitidas:
- open_capability: pede uma capability ao resolver local; target deve ser null;
- navigate: navega para uma URL HTTP/HTTPS explícita;
- write_text: escreve texto literal ou um artifact inteiro no formato {{artifact_id}};
- observe_active_window: observa a janela ativa; target deve ser null;
- capture_screen: captura a tela; target deve ser null.

Observáveis permitidos por operação:
- open_capability -> desktop.application (observation);
- navigate -> browser.url, browser.title, browser.text ou browser.search_results (observation);
- write_text -> desktop.text (readback);
- observe_active_window -> desktop.active_window (observation);
- capture_screen -> filesystem.exists (observation).

Todo critério é required=true e deve pertencer a exatamente um subgoal e a exatamente um step capaz de observar seu efeito. Receipts de execução e afirmações do próprio modelo nunca são evidência. `truthy` não recebe expected_value; `equals` e `contains` recebem expected_value. Todo write_text deve ter readback desktop.text com equals do target.

Use ids curtos, minúsculos e estáveis. Dependências só podem apontar para itens anteriores na lista. Um artifact consumido deve ter produtor anterior, declarado em produces, e o consumidor deve depender explicitamente daquele step. Não repita o mesmo efeito físico.
Artifacts produzíveis são limitados: navigate pode produzir first_result_title, first_result_url, browser_url, browser_title ou browser_text; open_capability pode produzir application_id/application_name; write_text pode produzir written_text; capture_screen pode produzir screenshot_path. observe_active_window não produz artifact.

A aplicação validará novamente todo o documento e reaplicará a Policy Layer ao materializar cada step. Se você não conseguir formar um contrato completo e observável com este vocabulário, não improvise uma ação livre: a resposta será recusada de modo seguro.
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
        if is_safety_interrupt(exc):
            raise
        raise ProviderGenerationError(provider, "resposta não respeita StructuredAction") from exc
    return parsed.model_dump()


def _validated_goal_decomposition_mapping(
    value: Any,
    provider: str,
    objective: str,
) -> Mapping[str, Any]:
    if isinstance(value, str):
        value = _decode_json_text(value, provider)

    if hasattr(value, "model_dump"):
        value = value.model_dump()

    if not isinstance(value, Mapping):
        raise ProviderGenerationError(provider, "decomposição não é um objeto JSON")

    try:
        parsed = decomposition_from_structured(
            dict(value),
            expected_objective=objective,
        )
    except Exception as exc:
        if is_safety_interrupt(exc):
            raise
        raise ProviderGenerationError(
            provider,
            "resposta não respeita StructuredGoalDecomposition",
        ) from exc
    return parsed.model_dump(mode="json")


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _safe_http_error_detail(response: httpx.Response) -> str | None:
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
                "max_tokens": 220,
                "temperature": 0.1,
            },
            timeout_seconds=self.timeout_seconds,
        )
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderGenerationError(self.name, "estrutura de resposta inesperada") from exc
        return _validated_mapping(content, self.name)

    def generate_goal_decomposition(self, objective: str) -> Mapping[str, Any]:
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
                    {"role": "system", "content": GOAL_DECOMPOSITION_SYSTEM_PROMPT},
                    {"role": "user", "content": objective},
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": 2400,
                "temperature": 0.0,
            },
            timeout_seconds=self.timeout_seconds,
        )
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderGenerationError(self.name, "estrutura de resposta inesperada") from exc
        return _validated_goal_decomposition_mapping(content, self.name, objective)


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
                "max_tokens": 220,
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

    def generate_goal_decomposition(self, objective: str) -> Mapping[str, Any]:
        payload = _post_json(
            self.name,
            f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/run/{self.model}",
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            },
            body={
                "messages": [
                    {"role": "system", "content": GOAL_DECOMPOSITION_SYSTEM_PROMPT},
                    {"role": "user", "content": objective},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": GOAL_DECOMPOSITION_SCHEMA,
                },
                "max_tokens": 2400,
                "temperature": 0.0,
            },
            timeout_seconds=self.timeout_seconds,
        )
        if payload.get("success") is False:
            raise ProviderGenerationError(self.name, "Cloudflare retornou success=false")
        try:
            response_value = payload["result"]["response"]
        except (KeyError, TypeError) as exc:
            raise ProviderGenerationError(self.name, "estrutura de resposta inesperada") from exc
        return _validated_goal_decomposition_mapping(
            response_value,
            self.name,
            objective,
        )


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
            max_output_tokens=1024,
        )
        self._goal_decomposition_config = types.GenerateContentConfig(
            system_instruction=GOAL_DECOMPOSITION_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_json_schema=GOAL_DECOMPOSITION_SCHEMA,
            temperature=0.0,
            max_output_tokens=4096,
        )

    def generate_plan(self, objective: str) -> Mapping[str, Any]:
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=objective,
                config=self._config,
            )
        except Exception as exc:
            if is_safety_interrupt(exc):
                raise
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

    def generate_goal_decomposition(self, objective: str) -> Mapping[str, Any]:
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=objective,
                config=self._goal_decomposition_config,
            )
        except Exception as exc:
            if is_safety_interrupt(exc):
                raise
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
            return _validated_goal_decomposition_mapping(parsed, self.name, objective)

        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise ProviderGenerationError(
                self.name,
                "SDK Gemini não retornou decomposição estruturada",
            )
        return _validated_goal_decomposition_mapping(text, self.name, objective)
