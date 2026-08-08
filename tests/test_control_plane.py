from pathlib import Path

from fastapi.testclient import TestClient

from context_anchor.config import ControlPlaneSettings
from context_anchor.control_plane import create_app


def make_client(tmp_path: Path) -> tuple[TestClient, str, str]:
    user_token = "u" * 32
    agent_token = "a" * 32
    settings = ControlPlaneSettings(
        db_path=tmp_path / "control-plane.db",
        user_token=user_token,
        agent_token=agent_token,
    )
    return TestClient(create_app(settings)), user_token, agent_token


def test_health(tmp_path: Path) -> None:
    client, _, _ = make_client(tmp_path)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_authenticated_task_roundtrip(tmp_path: Path) -> None:
    client, user_token, agent_token = make_client(tmp_path)
    user_headers = {"Authorization": f"Bearer {user_token}"}
    agent_headers = {"Authorization": f"Bearer {agent_token}"}

    created = client.post(
        "/api/tasks",
        headers=user_headers,
        json={"command": "abrir example.com"},
    )
    assert created.status_code == 200
    task_id = created.json()["id"]

    claimed = client.get(
        "/api/agent/next",
        headers=agent_headers,
        params={"agent_id": "test-agent"},
    )
    assert claimed.status_code == 200
    assert claimed.json()["id"] == task_id

    finished = client.post(
        f"/api/agent/tasks/{task_id}/result",
        headers=agent_headers,
        json={"ok": True, "result": {"verified": True}},
    )
    assert finished.status_code == 200
    assert finished.json()["status"] == "succeeded"

    fetched = client.get(f"/api/tasks/{task_id}", headers=user_headers)
    assert fetched.status_code == 200
    assert fetched.json()["result"] == {"verified": True}


def test_invalid_user_token_is_rejected(tmp_path: Path) -> None:
    client, _, _ = make_client(tmp_path)
    response = client.post(
        "/api/tasks",
        headers={"Authorization": "Bearer wrong"},
        json={"command": "abrir example.com"},
    )
    assert response.status_code == 401
