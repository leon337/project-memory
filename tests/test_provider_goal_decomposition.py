from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from google import genai

from context_anchor.emergency_stop import EmergencyStopTriggered
from context_anchor.planner import ProviderGenerationError
from context_anchor.providers import (
    GOAL_DECOMPOSITION_SCHEMA,
    CloudflareWorkersAIProvider,
    GeminiProvider,
    ZAIProvider,
)


OBJECTIVE = "Quero fazer uma anotação."


def goal_payload(*, objective: str = OBJECTIVE) -> dict:
    return {
        "schema_version": "1.0",
        "objective": objective,
        "capabilities": [
            {
                "id": "text.edit",
                "description": "Abrir uma superfície de edição de texto",
                "hint": "editor de texto",
            }
        ],
        "criteria": [
            {
                "id": "editor_open",
                "description": "A superfície de edição foi observada",
                "observable": "desktop.application",
                "evidence_kind": "observation",
                "check": "truthy",
                "expected_value": None,
                "required": True,
            }
        ],
        "subgoals": [
            {
                "id": "prepare_editor",
                "description": "Preparar uma superfície para anotação",
                "capability_ids": ["text.edit"],
                "criterion_ids": ["editor_open"],
                "depends_on": [],
            }
        ],
        "steps": [
            {
                "id": "open_editor",
                "subgoal_id": "prepare_editor",
                "capability_id": "text.edit",
                "operation": "open_capability",
                "target": None,
                "criterion_ids": ["editor_open"],
                "depends_on": [],
                "consumes": [],
                "produces": [],
            }
        ],
    }


def _response(url: str, payload: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json=payload,
        request=httpx.Request("POST", url),
    )


def test_zai_requests_complete_goal_document_and_validates_it_locally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    def fake_post(url: str, **kwargs):
        captured["body"] = kwargs["json"]
        return _response(
            url,
            {
                "choices": [
                    {"message": {"content": json.dumps(goal_payload(), ensure_ascii=False)}}
                ]
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = ZAIProvider("secret")

    result = provider.generate_goal_decomposition(OBJECTIVE)

    assert result["objective"] == OBJECTIVE
    assert result["steps"][0]["operation"] == "open_capability"
    body = captured["body"]
    assert body["response_format"] == {"type": "json_object"}
    assert body["max_tokens"] >= 2000
    assert "ANTES de qualquer ação física" in body["messages"][0]["content"]


def test_cloudflare_supplies_goal_json_schema_and_validates_object_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    def fake_post(url: str, **kwargs):
        captured["body"] = kwargs["json"]
        return _response(
            url,
            {"success": True, "result": {"response": goal_payload()}},
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = CloudflareWorkersAIProvider("token", "account")

    result = provider.generate_goal_decomposition(OBJECTIVE)

    assert result["criteria"][0]["required"] is True
    response_format = captured["body"]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"] == GOAL_DECOMPOSITION_SCHEMA
    assert set(GOAL_DECOMPOSITION_SCHEMA["properties"]) >= {
        "objective",
        "capabilities",
        "criteria",
        "subgoals",
        "steps",
    }


def test_gemini_uses_distinct_complete_goal_schema_and_local_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured["request"] = kwargs
            return SimpleNamespace(parsed=goal_payload(), text=None)

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = FakeModels()

    monkeypatch.setattr(genai, "Client", FakeClient)
    provider = GeminiProvider("secret")

    result = provider.generate_goal_decomposition(OBJECTIVE)

    assert result["objective"] == OBJECTIVE
    config = captured["request"]["config"]
    assert config.response_json_schema == GOAL_DECOMPOSITION_SCHEMA
    assert config.max_output_tokens == 4096
    assert "decompositor de objetivos" in config.system_instruction


def test_gemini_adapter_never_wraps_a_safety_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StopModels:
        def generate_content(self, **_: object) -> object:
            raise EmergencyStopTriggered("stop no SDK")

    class StopClient:
        def __init__(self, **_: object) -> None:
            self.models = StopModels()

    monkeypatch.setattr(genai, "Client", StopClient)

    with pytest.raises(EmergencyStopTriggered, match="stop no SDK"):
        GeminiProvider("secret").generate_goal_decomposition(OBJECTIVE)


@pytest.mark.parametrize(
    "invalid_response",
    [
        {"action": "finish", "target": "feito"},
        goal_payload(objective="Objetivo silenciosamente reduzido"),
    ],
)
def test_real_provider_adapter_fails_closed_on_free_action_or_objective_drift(
    monkeypatch: pytest.MonkeyPatch,
    invalid_response: dict,
) -> None:
    def fake_post(url: str, **kwargs):
        return _response(
            url,
            {
                "choices": [
                    {"message": {"content": json.dumps(invalid_response, ensure_ascii=False)}}
                ]
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(ProviderGenerationError, match="StructuredGoalDecomposition"):
        ZAIProvider("secret").generate_goal_decomposition(OBJECTIVE)
