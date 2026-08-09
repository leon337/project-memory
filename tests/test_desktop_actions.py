from pathlib import Path

import pytest

from context_anchor.actions import ActionExecutor
from context_anchor.emergency_stop import EmergencyStop, EmergencyStopTriggered
from context_anchor.policy import Plan


class FakeDesktop:
    def capture_screen(self, output_path: Path) -> dict:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-png")
        return {"action": "capture_screen", "path": str(output_path), "verified": True}

    def active_window(self) -> dict:
        return {"action": "active_window", "title": "Fake Window", "verified": True}

    def move_mouse(self, x: int, y: int) -> dict:
        return {"action": "move_mouse", "x": x, "y": y, "verified": True}

    def click_mouse(self, button: str) -> dict:
        return {"action": "click_mouse", "button": button, "verified": True}

    def type_text(self, text: str) -> dict:
        return {"action": "type_text", "characters": len(text), "verified": True}

    def press_key(self, key: str) -> dict:
        return {"action": "press_key", "key": key, "verified": True}

    def open_application(self, app_id: str) -> dict:
        return {"action": "open_app", "app": app_id, "pid": 123, "verified": True}

    def read_active_text(self, *, max_chars: int = 4096) -> dict:
        return {
            "action": "read_active_text",
            "text": "hello"[:max_chars],
            "verified": True,
        }

    def observe_application(
        self,
        app_id: str,
        *,
        pid: int | None = None,
        expected_argument: str | None = None,
    ) -> dict:
        return {
            "action": "observe_application",
            "app": app_id,
            "pid": pid,
            "argument_observed": expected_argument is not None,
            "verified": True,
        }


def test_executor_runs_typed_desktop_actions(tmp_path: Path) -> None:
    executor = ActionExecutor(
        desktop_enabled=True,
        desktop_backend=FakeDesktop(),
        screenshot_dir=tmp_path / "screens",
    )

    assert executor.execute(Plan("capture_screen", "screen"))["verified"] is True
    assert executor.execute(Plan("active_window", "active"))["title"] == "Fake Window"
    assert executor.execute(Plan("move_mouse", "100,200"))["x"] == 100
    assert executor.execute(Plan("click_mouse", "left"))["button"] == "left"
    assert executor.execute(Plan("type_text", "hello"))["characters"] == 5
    assert executor.execute(Plan("press_key", "enter"))["key"] == "enter"
    assert executor.execute(Plan("open_app", "firefox"))["app"] == "firefox"
    assert executor.read_active_text()["text"] == "hello"
    assert executor.observe_application("firefox", pid=123)["verified"] is True


def test_executor_refuses_desktop_when_disabled() -> None:
    executor = ActionExecutor(desktop_enabled=False, desktop_backend=FakeDesktop())
    with pytest.raises(PermissionError):
        executor.execute(Plan("capture_screen", "screen"))


def test_executor_obeys_emergency_stop(tmp_path: Path) -> None:
    stop = EmergencyStop(tmp_path / "STOP", tmp_path / "agent.pid")
    stop.trigger(terminate_process=False)
    executor = ActionExecutor(
        desktop_enabled=True,
        desktop_backend=FakeDesktop(),
        emergency_stop=stop,
    )

    with pytest.raises(EmergencyStopTriggered):
        executor.execute(Plan("click_mouse", "left"))
