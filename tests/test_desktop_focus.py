import pytest

import context_anchor.desktop as desktop_module
from context_anchor.desktop import PyAutoGuiDesktopBackend


class FakeGui:
    def __init__(self) -> None:
        self.writes: list[tuple[str, float]] = []
        self.clicks: list[str] = []
        self.presses: list[str] = []
        self.hotkeys: list[tuple[str, ...]] = []

    def write(self, text: str, interval: float = 0.0) -> None:
        self.writes.append((text, interval))

    def press(self, key: str) -> None:
        self.presses.append(key)

    def hotkey(self, *keys: str) -> None:
        self.hotkeys.append(tuple(keys))

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


def test_type_text_fails_closed_when_expected_window_becomes_unobservable(monkeypatch) -> None:
    backend = PyAutoGuiDesktopBackend()
    gui = FakeGui()
    backend._gui = gui
    backend._expected_window_id = "200"

    monkeypatch.setattr(backend, "_active_window_id", lambda: None)
    monkeypatch.setattr(backend, "_xdotool_path", lambda: "/usr/bin/xdotool")

    with pytest.raises(RuntimeError, match="deixou de ser observável"):
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
    assert result["input_method"] == "pyautogui-write"
    assert result["window_id"] == "200"
    assert result["window_title"] == "Documento não-salvo 1"
    assert result["verified"] is True


def test_type_text_revalidates_focus_between_chunks(monkeypatch) -> None:
    backend = PyAutoGuiDesktopBackend()
    gui = FakeGui()
    backend._gui = gui
    backend._expected_window_id = "200"
    active_windows = iter(("200", "200", "300"))

    monkeypatch.setattr(backend, "_active_window_id", lambda: next(active_windows))
    monkeypatch.setattr(backend, "_window_title", lambda window_id=None: "Editor")
    monkeypatch.setattr(backend, "_xdotool_path", lambda: "/usr/bin/xdotool")

    with pytest.raises(RuntimeError, match="foco mudou"):
        backend.type_text("a" * 64)

    assert gui.writes == [("a" * 32, 0.01)]


def test_type_text_preserves_unicode_with_linux_codepoint_input(monkeypatch) -> None:
    backend = PyAutoGuiDesktopBackend()
    gui = FakeGui()
    backend._gui = gui
    backend._expected_window_id = "200"

    monkeypatch.setattr(backend, "_active_window_id", lambda: "200")
    monkeypatch.setattr(backend, "_window_title", lambda window_id=None: "Documento não-salvo 1")
    monkeypatch.setattr(backend, "_xdotool_path", lambda: "/usr/bin/xdotool")

    result = backend.type_text("Olá mundo")

    assert gui.writes == [("Ol", 0.01), ("e1", 0.01), (" mundo", 0.01)]
    assert gui.hotkeys == [("ctrl", "shift", "u")]
    assert gui.presses == ["enter"]
    assert result["characters"] == len("Olá mundo")
    assert result["input_method"] == "linux-unicode-input"
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
    active_windows = iter(("100", "500", "500", "500"))

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


def test_read_active_text_uses_atspi_without_touching_clipboard(monkeypatch) -> None:
    backend = PyAutoGuiDesktopBackend()
    gui = FakeGui()
    backend._gui = gui
    backend._expected_window_id = "200"

    monkeypatch.setattr(backend, "_active_window_id", lambda: "200")
    monkeypatch.setattr(backend, "_window_title", lambda window_id=None: "Documento não-salvo 1")
    monkeypatch.setattr(
        desktop_module.subprocess,
        "run",
        lambda *args, **kwargs: type(
            "Completed",
            (),
            {
                "returncode": 0,
                "stdout": '{"text":"Olá mundo","app":"xed","frame":"Documento não-salvo 1"}\n',
            },
        )(),
    )

    result = backend.read_active_text()

    assert gui.hotkeys == []
    assert gui.presses == []
    assert result["text"] == "Olá mundo"
    assert result["source"] == "at-spi"
    assert result["clipboard_untouched"] is True
    assert result["verified"] is True


def test_read_active_text_fails_closed_without_focused_accessible_text(monkeypatch) -> None:
    backend = PyAutoGuiDesktopBackend()
    gui = FakeGui()
    backend._gui = gui
    backend._expected_window_id = "200"

    monkeypatch.setattr(backend, "_active_window_id", lambda: "200")
    monkeypatch.setattr(backend, "_window_title", lambda window_id=None: "Editor")
    monkeypatch.setattr(
        desktop_module.subprocess,
        "run",
        lambda *args, **kwargs: type(
            "Completed", (), {"returncode": 0, "stdout": "null\n"}
        )(),
    )

    result = backend.read_active_text()

    assert result["verified"] is False
    assert result["text"] is None
    assert gui.hotkeys == []


def test_read_active_text_rejects_focus_change_during_observation(monkeypatch) -> None:
    backend = PyAutoGuiDesktopBackend()
    backend._expected_window_id = "200"
    windows = iter(("200", "300"))

    monkeypatch.setattr(backend, "_xdotool_path", lambda: "/usr/bin/xdotool")
    monkeypatch.setattr(backend, "_active_window_id", lambda: next(windows))
    monkeypatch.setattr(backend, "_window_title", lambda window_id=None: "Editor")
    monkeypatch.setattr(
        desktop_module.subprocess,
        "run",
        lambda *args, **kwargs: type(
            "Completed",
            (),
            {"returncode": 0, "stdout": '{"text":"novo texto","app":"xed","frame":"Editor"}\n'},
        )(),
    )

    result = backend.read_active_text()

    assert result["verified"] is False
    assert result["observed_window_id"] == "300"


def test_observe_application_uses_independent_window_identity(monkeypatch) -> None:
    backend = PyAutoGuiDesktopBackend()

    monkeypatch.setattr(backend, "_active_window_id", lambda: "700")
    monkeypatch.setattr(backend, "_window_title", lambda window_id=None: "Untitled Document 1 - Xed")
    monkeypatch.setattr(backend, "_window_class", lambda window_id=None: "Xed")

    result = backend.observe_application("editor")

    assert result["source"] == "x11-proc"
    assert result["identity_observed"] is True
    assert result["verified"] is True


def test_observe_application_rejects_unrelated_active_window(monkeypatch) -> None:
    backend = PyAutoGuiDesktopBackend()

    monkeypatch.setattr(backend, "_active_window_id", lambda: "701")
    monkeypatch.setattr(backend, "_window_title", lambda window_id=None: "Painel do Robô")
    monkeypatch.setattr(backend, "_window_class", lambda window_id=None: "Firefox")

    result = backend.observe_application("calculadora")

    assert result["identity_observed"] is False
    assert result["verified"] is False


@pytest.mark.parametrize("spoofed_class", ["Decoder", "code-helper-evil"])
def test_observe_application_uses_exact_window_class_tokens(
    monkeypatch,
    spoofed_class: str,
) -> None:
    backend = PyAutoGuiDesktopBackend()

    monkeypatch.setattr(backend, "_active_window_id", lambda: "702")
    monkeypatch.setattr(backend, "_window_title", lambda window_id=None: "Visual Studio Code")
    monkeypatch.setattr(backend, "_window_class", lambda window_id=None: spoofed_class)

    result = backend.observe_application("vscode")

    assert result["title_identity_observed"] is True
    assert result["class_identity_observed"] is False
    assert result["verified"] is False


def test_observe_application_accepts_exact_xdg_startup_wm_class(monkeypatch) -> None:
    backend = PyAutoGuiDesktopBackend()

    monkeypatch.setattr(backend, "_active_window_id", lambda: "703")
    monkeypatch.setattr(backend, "_window_title", lambda window_id=None: "Text Editor")
    monkeypatch.setattr(
        backend,
        "_window_class",
        lambda window_id=None: "org.gnome.TextEditor org.gnome.TextEditor",
    )

    result = backend.observe_application("org.gnome.TextEditor")

    assert result["class_identity_observed"] is True
    assert result["verified"] is True


def test_observe_application_reads_browser_location_through_at_spi(monkeypatch) -> None:
    backend = PyAutoGuiDesktopBackend()

    monkeypatch.setattr(backend, "_active_window_id", lambda: "704")
    monkeypatch.setattr(
        backend,
        "_window_title",
        lambda window_id=None: "gatos - Search - Brave",
    )
    monkeypatch.setattr(
        backend,
        "_window_class",
        lambda window_id=None: "brave-browser Brave-browser",
    )
    monkeypatch.setattr(
        backend,
        "_observe_browser_location",
        lambda window_title: {
            "location": "bing.com/search?q=gatos",
            "app": "Brave Browser",
            "frame": window_title,
        },
    )
    monkeypatch.setattr(backend, "_window_process_id", lambda window_id: 2461)
    monkeypatch.setattr(
        backend,
        "_process_executable",
        lambda pid: "/usr/bin/brave-browser",
    )

    result = backend.observe_application(
        "brave-browser",
        expected_argument="https://www.bing.com/search?q=gatos",
    )

    assert result["identity_observed"] is True
    assert result["browser_location"] == "bing.com/search?q=gatos"
    assert result["browser_location_source"] == "at-spi"
    assert result["browser_location_verified"] is True
    assert result["window_process_identity_observed"] is True


def test_observe_application_discards_browser_location_after_focus_change(
    monkeypatch,
) -> None:
    backend = PyAutoGuiDesktopBackend()
    active_windows = iter(("704", "different-window"))

    monkeypatch.setattr(backend, "_active_window_id", lambda: next(active_windows))
    monkeypatch.setattr(
        backend,
        "_window_title",
        lambda window_id=None: "gatos - Search - Brave",
    )
    monkeypatch.setattr(
        backend,
        "_window_class",
        lambda window_id=None: "brave-browser Brave-browser",
    )
    monkeypatch.setattr(
        backend,
        "_observe_browser_location",
        lambda window_title: {
            "location": "bing.com/search?q=gatos",
            "app": "Brave Browser",
            "frame": window_title,
        },
    )
    monkeypatch.setattr(backend, "_window_process_id", lambda window_id: 2461)
    monkeypatch.setattr(
        backend,
        "_process_executable",
        lambda pid: "/usr/bin/brave-browser",
    )

    result = backend.observe_application(
        "brave-browser",
        expected_argument="https://www.bing.com/search?q=gatos",
    )

    assert result["browser_location"] is None
    assert result["browser_location_verified"] is False
