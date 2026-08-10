from pathlib import Path

import context_anchor.desktop as desktop_module
from context_anchor.conversation import ProjectConversationService
from context_anchor.desktop import PyAutoGuiDesktopBackend


def test_focus_wait_settles_on_final_window_after_transient(monkeypatch) -> None:
    backend = PyAutoGuiDesktopBackend(
        app_ready_timeout_seconds=2.0,
        focus_settle_seconds=0.15,
    )
    windows = ["200", "300", "300", "300", "300"]
    index = {"value": 0}

    def active_window() -> str:
        position = min(index["value"], len(windows) - 1)
        index["value"] += 1
        return windows[position]

    clock = {"value": 0.0}

    def monotonic() -> float:
        clock["value"] += 0.1
        return clock["value"]

    monkeypatch.setattr(backend, "_xdotool_path", lambda: "/usr/bin/xdotool")
    monkeypatch.setattr(backend, "_active_window_id", active_window)
    monkeypatch.setattr(backend, "_window_title", lambda window_id=None: f"window-{window_id}")
    monkeypatch.setattr(desktop_module.time, "monotonic", monotonic)
    monkeypatch.setattr(desktop_module.time, "sleep", lambda _seconds: None)

    result = backend._wait_for_active_window_change("100")

    assert result["window_changed"] is True
    assert result["window_id"] == "300"
    assert result["window_title"] == "window-300"


def test_conversation_rejects_project_identity_drift_and_falls_back(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "README.md").write_text(
        "# Robô Operador — MVP 0.3\nRepositório canônico: project-memory\n",
        encoding="utf-8",
    )
    service = ProjectConversationService(project_root=tmp_path)
    calls: list[str] = []

    def wrong_provider(system: str, message: str):
        calls.append("cloudflare")
        return "Robô Operador — MVP 0.3", "cloudflare", "fake-cf"

    def grounded_provider(system: str, message: str):
        calls.append("zai")
        return "project-memory", "zai", "fake-zai"

    monkeypatch.setattr(service, "_cloudflare", wrong_provider)
    monkeypatch.setattr(service, "_zai", grounded_provider)
    monkeypatch.setattr(
        service,
        "_gemini",
        lambda system, message: (_ for _ in ()).throw(AssertionError("não deveria chegar ao Gemini")),
    )

    response = service.reply(
        "Em qual projeto você está? Responda apenas o nome do projeto."
    )

    assert calls == ["cloudflare", "zai"]
    assert response["reply"] == "project-memory"
    assert response["provider"] == "zai"


def test_conversation_reasserts_canonical_project_identity_after_context(
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text(
        "# Robô Operador — MVP 0.3\n",
        encoding="utf-8",
    )
    service = ProjectConversationService(project_root=tmp_path)

    system, _version = service._messages()

    assert "IDENTIDADE CANÔNICA" in system
    assert "nome do projeto é exatamente `project-memory`" in system
    assert system.rfind("project-memory") > system.rfind("Robô Operador — MVP 0.3")
