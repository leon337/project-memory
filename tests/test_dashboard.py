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
            "logs": {
                "panel": ["2026-08-09T00:00:00-03:00 INFO Painel iniciado"],
                "central": ["2026-08-09T00:00:01-03:00 INFO Central iniciada"],
                "robot": ["2026-08-09T00:00:02-03:00 INFO Robô iniciado"],
            },
            "log_events": [
                {
                    "component": "panel",
                    "timestamp": "2026-08-09T00:00:00-03:00",
                    "line": "2026-08-09T00:00:00-03:00 INFO Painel iniciado",
                }
            ],
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


def test_dashboard_serves_stateful_ultra_dark_page_and_status():
    fake = FakeController()
    client = TestClient(create_app(fake))

    page = client.get("/")
    assert page.status_code == 200
    assert "Painel de Operação e Controle" in page.text
    assert "Laboratório de comandos guiados" in page.text
    assert 'data-theme="ultra-dark"' in page.text
    assert "--bg:#010308" in page.text
    assert "Controles de estado" in page.text
    assert 'id="centralAction"' in page.text
    assert 'id="robotAction"' in page.text
    assert 'id="emergencyAction"' in page.text
    assert "Ligada fora do Painel" in page.text
    assert "Logs reais da aplicação" in page.text
    assert 'data-log="panel"' in page.text
    assert 'data-log="central"' in page.text
    assert 'data-log="robot"' in page.text
    assert "log_events" in page.text
    assert "Dicas rápidas" in page.text

    status = client.get("/api/status")
    assert status.status_code == 200
    body = status.json()
    assert body["central"]["online"] is True
    assert body["central"]["managed"] is True
    assert body["log_events"][0]["component"] == "panel"


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


def test_dashboard_submits_robot_task():
    fake = FakeController()
    client = TestClient(create_app(fake))

    task = client.post("/api/tasks", json={"command": "capturar tela"})
    assert task.status_code == 200
    assert task.json()["status"] == "queued"
    assert "task:capturar tela" in fake.calls


def test_guided_command_explains_known_and_unknown_lines():
    fake = FakeController()
    client = TestClient(create_app(fake))

    known = client.post("/api/guided/explain", json={"command": "git pull"})
    assert known.status_code == 200
    assert known.json()["known"] is True

    unknown = client.post("/api/guided/explain", json={"command": "algum comando novo"})
    assert unknown.status_code == 200
    assert unknown.json()["known"] is False
