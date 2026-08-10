from pathlib import Path

from context_anchor.conversation import ProjectConversationService


def test_conversation_sanitizes_project_context_and_user_secrets(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text(
        "Projeto project-memory\napi_key=super-secret-value\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "STATUS.md").write_text("Goal Runtime integrado", encoding="utf-8")
    (tmp_path / ".env").write_text("PASSWORD=must-never-enter-prompt", encoding="utf-8")

    service = ProjectConversationService(project_root=tmp_path)
    captured: dict[str, str] = {}

    def fake_cloudflare(system: str, message: str):
        captured["system"] = system
        captured["message"] = message
        return "Resposta segura", "cloudflare", "fake-model"

    monkeypatch.setattr(service, "_cloudflare", fake_cloudflare)

    response = service.reply("token abcdefghijklmnopqrstuvwxyz")

    assert response["reply"] == "Resposta segura"
    assert response["provider"] == "cloudflare"
    assert "super-secret-value" not in captured["system"]
    assert "must-never-enter-prompt" not in captured["system"]
    assert "[redacted]" in captured["system"]
    assert "abcdefghijklmnopqrstuvwxyz" not in captured["message"]
    assert "[redacted]" in captured["message"]


def test_context_version_is_stable_sha256_prefix(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "README.md").write_text("project-memory", encoding="utf-8")
    service = ProjectConversationService(project_root=tmp_path)

    monkeypatch.setattr(
        service,
        "_cloudflare",
        lambda system, message: ("ok", "cloudflare", "fake-model"),
    )

    first = service.reply("qual projeto?")["context_version"]
    second = service.reply("qual projeto?")["context_version"]

    assert first == second
    assert len(first) == 16
    assert all(character in "0123456789abcdef" for character in first)
