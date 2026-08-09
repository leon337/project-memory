from __future__ import annotations

import httpx
import pytest

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


def test_gemini_provider_uses_interactions_structured_output(
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
                "status": "completed",
                "steps": [
                    {
                        "type": "model_output",
                        "content": [
                            {"type": "text", "text": '{"action":"active_window","target":"active"}'}
                        ],
                    }
                ],
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = GeminiProvider("secret", model="gemini-3.5-flash")

    result = provider.generate_plan("qual janela está ativa?")

    assert result == {"action": "active_window", "target": "active"}
    assert captured["url"].endswith("/v1beta/interactions")
    assert captured["json"]["model"] == "gemini-3.5-flash"
    assert captured["json"]["response_format"]["type"] == "text"
    assert captured["json"]["response_format"]["mime_type"] == "application/json"
    assert captured["json"]["response_format"]["schema"]["type"] == "object"


def test_gemini_provider_accepts_fenced_json_without_skipping_structured_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url: str, **kwargs):
        return _response(
            url,
            200,
            {
                "status": "completed",
                "steps": [
                    {
                        "type": "model_output",
                        "content": [
                            {
                                "type": "text",
                                "text": "```json\n{\"action\":\"open_app\",\"target\":\"editor\"}\n```",
                            }
                        ],
                    }
                ],
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
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
