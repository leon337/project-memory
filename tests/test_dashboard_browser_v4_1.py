from __future__ import annotations

import socket
import threading
import time

import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

from context_anchor.dashboard import create_app


class BrowserFakeController:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.desktop_enabled = True

    def status(self):
        return {
            "central": {"online": True, "managed": True},
            "robot": {"online": True},
            "desktop": {"enabled": self.desktop_enabled},
            "emergency": {"active": False},
            "ai": {"available": True, "configured_providers": ["fake-ai"]},
            "tasks": [],
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
        return {"id": "browser-task-1", "command": command, "status": "queued"}

    def explain_guided_command(self, command: str):
        return {"known": False, "command": command, "what": "", "why": "", "expected": "", "where": ""}


class BrowserFakeConversation:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def reply(self, message: str):
        self.messages.append(message)
        return {
            "reply": "project-memory",
            "provider": "fake-ai",
            "model": "fake-model",
            "context_version": "0123456789abcdef",
        }


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def live_dashboard():
    controller = BrowserFakeController()
    conversation = BrowserFakeConversation()
    port = free_port()
    app = create_app(controller, conversation=conversation)
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 8
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=2)
        raise RuntimeError("servidor de teste do Painel não iniciou")
    try:
        yield f"http://127.0.0.1:{port}", controller, conversation
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_home_v4_1_browser_keeps_enter_in_conversation_and_execute_explicit(
    live_dashboard,
) -> None:
    base_url, controller, conversation = live_dashboard

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page_errors: list[str] = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        try:
            page.goto(base_url)
            expect(page.get_by_text("Conversar com a IA", exact=True)).to_be_visible()
            expect(page.locator("#conversationSend")).to_be_visible()
            expect(page.locator("#executeGoal")).to_be_visible()

            page.locator("#messageInput").fill("Em qual projeto você está?")
            page.locator("#messageInput").press("Enter")
            ai_bubble = page.locator("#thread .bubble.ai").last
            expect(ai_bubble).to_contain_text("project-memory")
            expect(ai_bubble).to_contain_text("fake-ai")
            assert conversation.messages == ["Em qual projeto você está?"]
            assert not any(call.startswith("task:") for call in controller.calls)

            expect(page.locator("#agentProvider")).to_have_text("fake-ai")
            expect(page.locator("#agentModel")).to_have_text("fake-model")

            page.locator("#messageInput").fill("capturar tela")
            page.locator("#executeGoal").click()
            system_bubble = page.locator("#thread .bubble.system").last
            expect(system_bubble).to_contain_text("browser-task-1")
            assert "task:capturar tela" in controller.calls
            assert page_errors == []
        finally:
            browser.close()
