from __future__ import annotations

import context_anchor.desktop as desktop_module
from context_anchor.desktop import PyAutoGuiDesktopBackend, canonical_app_id


class FakeProcess:
    pid = 4321

    def poll(self):
        return None


def test_brave_natural_name_resolves_to_executable_alias() -> None:
    assert canonical_app_id("navegador brave") == "brave-browser"
    assert canonical_app_id("Brave") == "brave-browser"


def test_unregistered_executable_can_be_opened_when_installed(monkeypatch) -> None:
    backend = PyAutoGuiDesktopBackend(app_ready_timeout_seconds=0.1)

    monkeypatch.setattr(
        desktop_module.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name == "meu-app" else None,
    )
    monkeypatch.setattr(backend, "_active_window_id", lambda: "100")
    monkeypatch.setattr(
        backend,
        "_wait_for_active_window_change",
        lambda previous: {
            "window_changed": True,
            "window_id": "200",
            "window_title": "Meu App",
        },
    )
    monkeypatch.setattr(desktop_module.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    result = backend.open_application("meu-app")

    assert result["executable"] == "/usr/bin/meu-app"
    assert result["verified"] is True
    assert result["window_title"] == "Meu App"


def test_application_arguments_are_preserved_without_shell(monkeypatch) -> None:
    backend = PyAutoGuiDesktopBackend(app_ready_timeout_seconds=0.1)
    captured: dict = {}

    monkeypatch.setattr(
        desktop_module.shutil,
        "which",
        lambda name: "/usr/bin/meu-app" if name == "meu-app" else None,
    )
    monkeypatch.setattr(backend, "_active_window_id", lambda: "100")
    monkeypatch.setattr(
        backend,
        "_wait_for_active_window_change",
        lambda previous: {
            "window_changed": True,
            "window_id": "200",
            "window_title": "Meu App",
        },
    )

    def fake_popen(argv, **kwargs):
        captured["argv"] = argv
        captured["shell"] = kwargs["shell"]
        return FakeProcess()

    monkeypatch.setattr(desktop_module.subprocess, "Popen", fake_popen)

    result = backend.open_application("meu-app --modo teste")

    assert captured["argv"] == ("/usr/bin/meu-app", "--modo", "teste")
    assert captured["shell"] is False
    assert result["argv"] == ["--modo", "teste"]
