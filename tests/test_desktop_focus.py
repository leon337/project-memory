import pytest

import context_anchor.desktop as desktop_module
from context_anchor.desktop import PyAutoGuiDesktopBackend


class FakeGui:
    def __init__(self) -> None:
        self.writes: list[tuple[str, float]] = []
        self.clicks: list[str] = []
        self.presses: list[str] = []

    def write(self, text: str, interval: float = 0.0) -> None:
        self.writes.append((text, interval))

    def press(self, key: str) -> None:
        self.presses.append(key)

    def click(self, button: str) -> None:
        self.clicks.append(button)

    def position(self):
        return (400, 300)

    def size(self):
        return (1920, 1080)


class FakeProcess:
    pid = 12345

    def poll(self):
        return None


def test_open_application_tracks_window_that_received_focus(monkeypatch) -> None:
    backend = PyAutoGuiDesktopBackend(app_ready_timeout_seconds=0.1)

    monkeypatch.setattr(
        desktop_module.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in {"xed", "xdotool"} else None,
    )
    monkeypatch.setattr(backend, "_active_window_id", lambda: "100")
    monkeypatch.setattr(
        backend,
        "_wait_for_active_window_change",
        lambda previous: {
            "window_changed": True,
            "window_id": "200",
            "window_title": "Documento não-salvo 1",
        },
    )
    monkeypatch.setattr(desktop_module.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    result = backend.open_application("editor")

    assert result["verified"] is True
    assert result["window_id"] == "200"
    assert backend._expected_window_id == "200"
    assert backend._focus_guard_error is None


def test_type_text_refuses_when_focus_moved_to_another_window(monkeypatch) -> None:
    backend = PyAutoGuiDesktopBackend()
    gui = FakeGui()
    backend._gui = gui
    backend._expected_window_id = "200"

    monkeypatch.setattr(backend, "_active_window_id", lambda: "300")
    monkeypatch.setattr(backend, "_window_title", lambda window_id=None: "Painel do Robô")

    with pytest.raises(RuntimeError, match="foco mudou"):
        backend.type_text("teste")

    assert gui.writes == []


def test_type_text_records_confirmed_window(monkeypatch) -> None:
    backend = PyAutoGuiDesktopBackend()
    gui = FakeGui()
    backend._gui = gui
    backend._expected_window_id = "200"

    monkeypatch.setattr(backend, "_active_window_id", lambda: "200")
    monkeypatch.setattr(backend, "_window_title", lambda window_id=None: "Documento não-salvo 1")
    monkeypatch.setattr(backend, "_xdotool_path", lambda: "/usr/bin/xdotool")

    result = backend.type_text("teste do robo")

    assert gui.writes == [("teste do robo", 0.01)]
    assert result["window_id"] == "200"
    assert result["window_title"] == "Documento não-salvo 1"
    assert result["verified"] is True


def test_click_refreshes_expected_focus(monkeypatch) -> None:
    backend = PyAutoGuiDesktopBackend()
    gui = FakeGui()
    backend._gui = gui
    backend._focus_guard_error = "aguardando foco"

    monkeypatch.setattr(backend, "_active_window_id", lambda: "400")
    monkeypatch.setattr(backend, "_window_title", lambda window_id=None: "Editor")

    result = backend.click_mouse("left")

    assert gui.clicks == ["left"]
    assert backend._expected_window_id == "400"
    assert backend._focus_guard_error is None
    assert result["window_title"] == "Editor"


def test_click_then_type_text_uses_same_observed_window(monkeypatch) -> None:
    backend = PyAutoGuiDesktopBackend()
    gui = FakeGui()
    backend._gui = gui

    monkeypatch.setattr(backend, "_active_window_id", lambda: "400")
    monkeypatch.setattr(backend, "_window_title", lambda window_id=None: "Arquivos")
    monkeypatch.setattr(backend, "_xdotool_path", lambda: "/usr/bin/xdotool")

    backend.click_mouse("left")
    result = backend.type_text("teste")

    assert gui.writes == [("teste", 0.01)]
    assert result["window_id"] == "400"
    assert result["window_title"] == "Arquivos"
    assert result["verified"] is True


def test_non_editor_app_with_confirmed_focus_can_receive_keyboard(monkeypatch) -> None:
    backend = PyAutoGuiDesktopBackend(app_ready_timeout_seconds=0.1)
    gui = FakeGui()
    backend._gui = gui
    active_windows = iter(("100", "500", "500"))

    monkeypatch.setattr(
        desktop_module.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in {"firefox", "xdotool"} else None,
    )
    monkeypatch.setattr(backend, "_active_window_id", lambda: next(active_windows))
    monkeypatch.setattr(
        backend,
        "_wait_for_active_window_change",
        lambda previous: {
            "window_changed": True,
            "window_id": "500",
            "window_title": "Firefox",
        },
    )
    monkeypatch.setattr(backend, "_window_title", lambda window_id=None: "Firefox")
    monkeypatch.setattr(desktop_module.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    opened = backend.open_application("firefox")
    typed = backend.type_text("consulta")
    pressed = backend.press_key("enter")

    assert opened["verified"] is True
    assert gui.writes == [("consulta", 0.01)]
    assert gui.presses == ["enter"]
    assert typed["window_id"] == "500"
    assert pressed["window_id"] == "500"
