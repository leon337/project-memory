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


def test_gemini_provider_uses_structured_response_format(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_post(url: str, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return _response(
            url,
            200,
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": '{"action":"active_window","target":"active"}'}
                            ]
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = GeminiProvider("secret", model="gemini-3.5-flash")

    result = provider.generate_plan("qual janela está ativa?")

    assert result == {"action": "active_window", "target": "active"}
    response_format = captured["json"]["generationConfig"]["responseFormat"]
    assert response_format["text"]["mimeType"] == "application/json"
    assert captured["url"].endswith("gemini-3.5-flash:generateContent")


def test_provider_429_preserves_retry_after_for_router(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, **kwargs):
        return _response(url, 429, {"error": "limited"}, headers={"retry-after": "7"})

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = ZAIProvider("secret")

    with pytest.raises(ProviderGenerationError) as exc_info:
        provider.generate_plan("abra o editor")

    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after_seconds == 7.0
