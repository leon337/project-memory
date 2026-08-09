from fastapi.testclient import TestClient

from context_anchor.dashboard import create_app


class FakeController:
    def __init__(self) -> None:
        self.desktop_enabled = False
        self.calls: list[str] = []

    def status(self):
        return {
            "central": {"online": True, "managed": True},
            "robot": {"online": True},
            "desktop": {"enabled": self.desktop_enabled},
            "emergency": {"active": False},
            "tasks": [],
            "logs": {"central": [], "robot": []},
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
        return {"ok": True, "enabled": enabled, "restart_required": True, "message": "desktop"}

    def submit_task(self, command: str):
        self.calls.append(f"task:{command}")
        return {"id": "task-1", "command": command, "status": "queued"}

    def explain_guided_command(self, command: str):
        known = command.strip() == "git pull"
        return {
            "known": known,
            "command": command.strip(),
            "what": "explicação",
            "why": "motivo",
            "expected": "resultado",
            "where": "terminal",
        }


def test_dashboard_serves_main_page_and_status():
    fake = FakeController()
    client = TestClient(create_app(fake))

    page = client.get("/")
    assert page.status_code == 200
    assert "Painel de Operação e Controle" in page.text
    assert "Laboratório de comandos guiados" in page.text
    assert "color-scheme:dark" in page.text
    assert "--bg:#0a0f16" in page.text
    assert "--card:#111a25" in page.text

    status = client.get("/api/status")
    assert status.status_code == 200
    assert status.json()["central"]["online"] is True


def test_dashboard_controls_are_typed_endpoints():
    fake = FakeController()
    client = TestClient(create_app(fake))

    assert client.post("/api/central/start").status_code == 200
    assert client.post("/api/robot/restart").status_code == 200
    assert client.post("/api/emergency/trigger").status_code == 200

    desktop = client.post("/api/desktop", json={"enabled": True})
    assert desktop.status_code == 200
    assert fake.desktop_enabled is True
    assert "central/start" in fake.calls
    assert "robot/restart" in fake.calls


def test_dashboard_submits_robot_task_but_has_no_generic_shell_endpoint():
    fake = FakeController()
    client = TestClient(create_app(fake))

    task = client.post("/api/tasks", json={"command": "capturar tela"})
    assert task.status_code == 200
    assert task.json()["status"] == "queued"
    assert "task:capturar tela" in fake.calls

    assert client.post("/api/shell", json={"command": "echo teste"}).status_code == 404


def test_guided_command_explains_known_and_unknown_lines():
    fake = FakeController()
    client = TestClient(create_app(fake))

    known = client.post("/api/guided/explain", json={"command": "git pull"})
    assert known.status_code == 200
    assert known.json()["known"] is True

    unknown = client.post("/api/guided/explain", json={"command": "algum comando novo"})
    assert unknown.status_code == 200
    assert unknown.json()["known"] is False
