from pathlib import Path

from context_anchor.conversation import ProjectConversationService


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
        lambda system, message: (_ for _ in ()).throw(
            AssertionError("não deveria chegar ao Gemini")
        ),
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
