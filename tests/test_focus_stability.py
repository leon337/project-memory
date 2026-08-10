from __future__ import annotations

import pytest

import context_anchor.reliable_desktop as reliable_module
from context_anchor.reliable_desktop import StableFocusDesktopBackend


class FakeGui:
    def __init__(self) -> None:
        self.writes: list[tuple[str, float]] = []

    def write(self, text: str, interval: float = 0.0) -> None:
        self.writes.append((text, interval))

    def hotkey(self, *keys: str) -> None:
        pass

    def press(self, key: str) -> None:
        pass

    def position(self):
        return (400, 300)

    def size(self):
        return (1920, 1080)


def _clock(values: list[float]):
    iterator = iter(values)
    last = values[-1]

    def monotonic() -> float:
        nonlocal last
        try:
            last = next(iterator)
        except StopIteration:
            last += 0.05
        return last

    return monotonic


def test_waits_for_final_same_app_window_after_transient_focus(monkeypatch) -> None:
    backend = StableFocusDesktopBackend(
        app_ready_timeout_seconds=2.0,
        focus_settle_seconds=0.40,
        focus_poll_seconds=0.0,
    )
    backend._launch_app_id = "editor"
    windows = iter(("200", "201", "201"))

    monkeypatch.setattr(backend, "_xdotool_path", lambda: "/usr/bin/xdotool")
    monkeypatch.setattr(backend, "_active_window_id", lambda: next(windows, "201"))
    monkeypatch.setattr(
        backend,
        "_window_class",
        lambda window_id=None: "Xed" if window_id in {"200", "201"} else "Terminal",
    )
    monkeypatch.setattr(
        backend,
        "_window_title",
        lambda window_id=None: f"window-{window_id}",
    )
    monkeypatch.setattr(
        reliable_module.time,
        "monotonic",
        _clock([0.0, 0.05, 0.10, 0.55]),
    )
    monkeypatch.setattr(reliable_module.time, "sleep", lambda _: None)

    result = backend._wait_for_active_window_change("100")

    assert result["window_changed"] is True
    assert result["window_id"] == "201"
    assert result["app_identity_verified"] is True
    assert result["stable_for_seconds"] >= 0.40
    assert [event["window_id"] for event in result["focus_trace"]] == ["200", "201"]


def test_ignores_unrelated_window_during_application_startup(monkeypatch) -> None:
    backend = StableFocusDesktopBackend(
        app_ready_timeout_seconds=2.0,
        focus_settle_seconds=0.30,
        focus_poll_seconds=0.0,
    )
    backend._launch_app_id = "editor"
    windows = iter(("300", "200", "200"))

    monkeypatch.setattr(backend, "_xdotool_path", lambda: "/usr/bin/xdotool")
    monkeypatch.setattr(backend, "_active_window_id", lambda: next(windows, "200"))
    monkeypatch.setattr(
        backend,
        "_window_class",
        lambda window_id=None: "Firefox" if window_id == "300" else "Xed",
    )
    monkeypatch.setattr(backend, "_window_title", lambda window_id=None: str(window_id))
    monkeypatch.setattr(
        reliable_module.time,
        "monotonic",
        _clock([0.0, 0.05, 0.10, 0.45]),
    )
    monkeypatch.setattr(reliable_module.time, "sleep", lambda _: None)

    result = backend._wait_for_active_window_change("100")

    assert result["window_id"] == "200"
    assert result["app_identity_verified"] is True
    assert result["focus_trace"][0]["app_identity_verified"] is False


def test_unknown_application_keeps_stable_window_behavior(monkeypatch) -> None:
    backend = StableFocusDesktopBackend(
        app_ready_timeout_seconds=2.0,
        focus_settle_seconds=0.25,
        focus_poll_seconds=0.0,
    )
    backend._launch_app_id = "custom-tool"
    windows = iter(("500", "500"))

    monkeypatch.setattr(backend, "_xdotool_path", lambda: "/usr/bin/xdotool")
    monkeypatch.setattr(backend, "_active_window_id", lambda: next(windows, "500"))
    monkeypatch.setattr(backend, "_window_class", lambda window_id=None: "CustomTool")
    monkeypatch.setattr(backend, "_window_title", lambda window_id=None: "Custom Tool")
    monkeypatch.setattr(
        reliable_module.time,
        "monotonic",
        _clock([0.0, 0.05, 0.35]),
    )
    monkeypatch.setattr(reliable_module.time, "sleep", lambda _: None)

    result = backend._wait_for_active_window_change("100")

    assert result["window_changed"] is True
    assert result["window_id"] == "500"
    assert result["app_identity_verified"] is None


def test_focus_guard_still_refuses_real_focus_loss(monkeypatch) -> None:
    backend = StableFocusDesktopBackend()
    gui = FakeGui()
    backend._gui = gui
    backend._expected_window_id = "200"

    monkeypatch.setattr(backend, "_active_window_id", lambda: "300")
    monkeypatch.setattr(backend, "_window_title", lambda window_id=None: "Painel do Robô")
    monkeypatch.setattr(backend, "_xdotool_path", lambda: "/usr/bin/xdotool")

    with pytest.raises(RuntimeError, match="foco mudou"):
        backend.type_text("não pode digitar")

    assert gui.writes == []
