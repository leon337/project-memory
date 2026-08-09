from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from google import genai

from context_anchor.planner import ProviderGenerationError
from context_anchor.providers import CloudflareWorkersAIProvider, GeminiProvider, ZAIProvider


def _response(url: str, status: int, payload: dict, *, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status,
        json=payload,
        headers=headers,
        request=httpx.Request("POST", url),
    )


def test_zai_provider_requests_json_and_parses_structured_action(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_post(url: str, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return _response(
            url,
            200,
            {
                "choices": [
                    {"message": {"content": '{"action":"open_app","target":"editor"}'}}
                ]
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = ZAIProvider("secret", model="glm-4.7-flash")

    result = provider.generate_plan("abra o editor")

    assert result == {"action": "open_app", "target": "editor"}
    assert captured["url"].endswith("/chat/completions")
    assert captured["json"]["response_format"] == {"type": "json_object"}


def test_cloudflare_provider_uses_json_schema_and_accepts_object_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    def fake_post(url: str, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return _response(
            url,
            200,
            {
                "success": True,
                "result": {"response": {"action": "open_url", "target": "https://example.com"}},
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = CloudflareWorkersAIProvider("token", "account-id")

    result = provider.generate_plan("visite o site de exemplo")

    assert result["action"] == "open_url"
    assert "/accounts/account-id/ai/run/" in captured["url"]
    assert captured["json"]["response_format"]["type"] == "json_schema"


def test_gemini_provider_uses_official_sdk_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured["request"] = kwargs
            return SimpleNamespace(
                parsed=None,
                text='{"action":"active_window","target":"active"}',
            )

    class FakeClient:
        def __init__(self, *, api_key, http_options):
            captured["api_key"] = api_key
            captured["http_options"] = http_options
            self.models = FakeModels()

    monkeypatch.setattr(genai, "Client", FakeClient)
    provider = GeminiProvider("secret", model="gemini-3.6-flash")

    result = provider.generate_plan("qual janela está ativa?")

    assert result == {"action": "active_window", "target": "active"}
    assert captured["api_key"] == "secret"
    request = captured["request"]
    assert request["model"] == "gemini-3.6-flash"
    assert request["contents"] == "qual janela está ativa?"
    config = request["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema["type"] == "object"


def test_gemini_provider_accepts_fenced_json_without_skipping_structured_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeModels:
        def generate_content(self, **kwargs):
            return SimpleNamespace(
                parsed=None,
                text="```json\n{\"action\":\"open_app\",\"target\":\"editor\"}\n```",
            )

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = FakeModels()

    monkeypatch.setattr(genai, "Client", FakeClient)
    provider = GeminiProvider("secret")

    result = provider.generate_plan("abra o editor")

    assert result == {"action": "open_app", "target": "editor"}


def test_gemini_provider_accepts_sdk_parsed_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeModels:
        def generate_content(self, **kwargs):
            return SimpleNamespace(
                parsed={"action": "open_app", "target": "editor"},
                text=None,
            )

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = FakeModels()

    monkeypatch.setattr(genai, "Client", FakeClient)
    provider = GeminiProvider("secret")

    result = provider.generate_plan("abra o editor")

    assert result == {"action": "open_app", "target": "editor"}


def test_provider_429_preserves_retry_after_and_safe_error_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url: str, **kwargs):
        return _response(
            url,
            429,
            {"error": {"code": "RATE_LIMIT", "message": "Too many requests"}},
            headers={"retry-after": "7"},
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = ZAIProvider("secret")

    with pytest.raises(ProviderGenerationError) as exc_info:
        provider.generate_plan("abra o editor")

    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after_seconds == 7.0
    assert "RATE_LIMIT" in str(exc_info.value)
    assert "Too many requests" in str(exc_info.value)
    assert "secret" not in str(exc_info.value)
