from fastapi.testclient import TestClient

from context_anchor.dashboard import create_app


class FakeController:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.desktop_enabled = True

    def status(self):
        return {
            "central": {"online": True, "managed": True},
            "robot": {"online": True},
            "desktop": {"enabled": self.desktop_enabled},
            "emergency": {"active": False},
            "ai": {"available": True},
            "tasks": [
                {
                    "id": "task-1",
                    "command": "Abra um editor",
                    "status": "succeeded",
                    "created_at": "2026-08-10T06:00:00+00:00",
                    "updated_at": "2026-08-10T06:00:03+00:00",
                    "agent_id": "desktop-principal",
                    "attempts": 1,
                    "result": {
                        "status": "succeeded",
                        "goal_completed": True,
                        "verified": True,
                        "planner_provider": "deterministic",
                        "planner_route": "deterministic",
                    },
                    "error": None,
                }
            ],
            "logs": {"panel": [], "central": [], "robot": []},
            "log_events": [],
        }

    def diagnostics(self):
        return {
            "python": {"supported": True},
            "desktop": {
                "x11_detected": True,
                "pyautogui_installed": True,
                "xdotool": "/usr/bin/xdotool",
                "scrot": "/usr/bin/scrot",
                "enabled": self.desktop_enabled,
            },
        }

    def _ok(self, name: str):
        self.calls.append(name)
        return {"ok": True, "message": name}

    def start_central(self): return self._ok("central/start")
    def stop_central(self): return self._ok("central/stop")
    def start_robot(self): return self._ok("robot/start")
    def stop_robot(self): return self._ok("robot/stop")
    def restart_robot(self): return self._ok("robot/restart")
    def trigger_emergency(self): return self._ok("emergency/trigger")
    def clear_emergency(self): return self._ok("emergency/clear")

    def set_desktop_enabled(self, enabled: bool):
        self.desktop_enabled = enabled
        return {"ok": True, "enabled": enabled, "restart_required": False, "message": "desktop"}

    def submit_task(self, command: str):
        self.calls.append(f"task:{command}")
        return {"id": "task-new", "command": command, "status": "queued"}

    def explain_guided_command(self, command: str):
        return {"known": False, "command": command, "what": "", "why": "", "expected": "", "where": ""}


class FakeConversation:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def reply(self, message: str):
        self.messages.append(message)
        return {
            "reply": "Você está no projeto project-memory. Posso conversar sem executar ações.",
            "provider": "fake-ai",
            "model": "fake-model",
            "context_version": "test-context-v1",
        }


def build_client():
    controller = FakeController()
    conversation = FakeConversation()
    client = TestClient(create_app(controller, conversation=conversation))
    return client, controller, conversation


def test_home_v4_1_is_conversation_first_and_exposes_real_execution_boundary():
    client, _, _ = build_client()

    page = client.get("/")

    assert page.status_code == 200
    assert "Painel do Robô" in page.text
    assert "Conversar com a IA" in page.text
    assert 'id="conversationSend"' in page.text
    assert 'id="executeGoal"' in page.text
    assert "Executar objetivo" in page.text
    assert "Agente agora" in page.text
    assert "GoalVerifier" in page.text
    assert "Tarefas" in page.text
    assert "Histórico" in page.text
    assert "Diagnóstico" in page.text
    assert "Configurações" in page.text


def test_conversation_endpoint_never_submits_a_task():
    client, controller, conversation = build_client()

    before = list(controller.calls)
    response = client.post(
        "/api/conversation",
        json={"message": "Em qual projeto você está?"},
        headers={"Origin": "http://testserver"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "fake-ai"
    assert "project-memory" in body["reply"]
    assert conversation.messages == ["Em qual projeto você está?"]
    assert controller.calls == before
    assert not any(call.startswith("task:") for call in controller.calls)


def test_execute_goal_keeps_using_task_api():
    client, controller, _ = build_client()

    response = client.post(
        "/api/tasks",
        json={"command": "capturar tela"},
        headers={"Origin": "http://testserver"},
    )

    assert response.status_code == 200
    assert "task:capturar tela" in controller.calls


def test_browser_mutation_rejects_foreign_origin_but_allows_same_origin():
    client, controller, _ = build_client()

    rejected = client.post(
        "/api/robot/stop",
        headers={"Origin": "https://evil.example"},
    )
    assert rejected.status_code == 403
    assert "robot/stop" not in controller.calls

    allowed = client.post(
        "/api/robot/stop",
        headers={"Origin": "http://testserver"},
    )
    assert allowed.status_code == 200
    assert "robot/stop" in controller.calls


def test_untrusted_host_is_rejected():
    client, _, _ = build_client()

    response = client.get("/", headers={"Host": "evil.example"})

    assert response.status_code == 400
