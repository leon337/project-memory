from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from context_anchor.action_journal import ActionJournalStore
from context_anchor.config import ControlPlaneSettings
from context_anchor.control_plane import create_app


def _client(tmp_path: Path) -> tuple[TestClient, Path, dict[str, str], dict[str, str]]:
    db_path = tmp_path / "journal-api.db"
    user_token = "u" * 32
    agent_token = "a" * 32
    settings = ControlPlaneSettings(
        db_path=db_path,
        user_token=user_token,
        agent_token=agent_token,
        task_lease_seconds=120,
        task_max_attempts=3,
        action_journal_retention_days=30,
    )
    return (
        TestClient(create_app(settings)),
        db_path,
        {"Authorization": f"Bearer {user_token}"},
        {"Authorization": f"Bearer {agent_token}"},
    )


def _claim(client: TestClient, user_headers: dict[str, str], agent_headers: dict[str, str]) -> dict:
    created = client.post(
        "/api/tasks",
        headers=user_headers,
        json={"command": "abra o editor e digite texto privado"},
    )
    assert created.status_code == 200
    claimed = client.get(
        "/api/agent/next",
        headers=agent_headers,
        params={"agent_id": "journal-test-agent"},
    )
    assert claimed.status_code == 200
    return claimed.json()


def test_central_journal_requires_live_lease_and_sanitizes_receipt(tmp_path: Path) -> None:
    client, db_path, user_headers, agent_headers = _client(tmp_path)
    task = _claim(client, user_headers, agent_headers)
    task_id = task["id"]
    lease_token = task["lease_token"]
    key = "v1:type_text:0001"

    stale = client.post(
        f"/api/agent/tasks/{task_id}/actions/prepare",
        headers=agent_headers,
        json={
            "lease_token": "x" * 24,
            "action_key": key,
            "action_name": "type_text",
            "repeat_safe": False,
        },
    )
    assert stale.status_code == 409

    prepared = client.post(
        f"/api/agent/tasks/{task_id}/actions/prepare",
        headers=agent_headers,
        json={
            "lease_token": lease_token,
            "action_key": key,
            "action_name": "type_text",
            "repeat_safe": False,
        },
    )
    assert prepared.status_code == 200
    assert prepared.json()["state"] == "prepared"

    in_flight = client.post(
        f"/api/agent/tasks/{task_id}/actions/transition",
        headers=agent_headers,
        json={"lease_token": lease_token, "action_key": key, "state": "in_flight"},
    )
    assert in_flight.status_code == 200

    executed = client.post(
        f"/api/agent/tasks/{task_id}/actions/transition",
        headers=agent_headers,
        json={
            "lease_token": lease_token,
            "action_key": key,
            "state": "executed",
            "receipt": {
                "action": "type_text",
                "verified": True,
                "characters": 12,
                "input_method": "unicode",
                "typed_text": "segredo que não pode persistir",
                "final_url": "https://example.com/private?token=abc",
                "screenshot": "/tmp/private.png",
            },
        },
    )
    assert executed.status_code == 200
    assert executed.json()["receipt"] == {
        "action": "type_text",
        "verified": True,
        "characters": 12,
        "input_method": "unicode",
    }

    persisted = ActionJournalStore(db_path).get(task_id, key)
    assert persisted is not None
    serialized = repr(persisted["receipt"])
    assert "segredo" not in serialized
    assert "example.com" not in serialized
    assert "private.png" not in serialized


def test_central_ack_marks_journal_acknowledged(tmp_path: Path) -> None:
    client, db_path, user_headers, agent_headers = _client(tmp_path)
    task = _claim(client, user_headers, agent_headers)
    task_id = task["id"]
    lease_token = task["lease_token"]
    key = "v1:active_window:0001"

    prepared = client.post(
        f"/api/agent/tasks/{task_id}/actions/prepare",
        headers=agent_headers,
        json={
            "lease_token": lease_token,
            "action_key": key,
            "action_name": "active_window",
            "repeat_safe": True,
        },
    )
    assert prepared.status_code == 200

    finished = client.post(
        f"/api/agent/tasks/{task_id}/result",
        headers=agent_headers,
        json={"lease_token": lease_token, "ok": False, "error": "teste concluído"},
    )
    assert finished.status_code == 200
    assert finished.json()["status"] == "failed"

    persisted = ActionJournalStore(db_path).get(task_id, key)
    assert persisted is not None
    assert persisted["state"] == "acknowledged"
    assert persisted["acknowledged_at"] is not None
