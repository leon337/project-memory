from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import context_anchor.session_context as session_context_module
from context_anchor.session_context import ArtifactKind, SessionContext


class MutableClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def __call__(self) -> datetime:
        return self.current


def test_artifact_persists_with_origin_and_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "session-context.json"
    timestamp = datetime(2026, 8, 9, 12, 30, tzinfo=timezone.utc)
    clock = MutableClock(timestamp)
    context = SessionContext(path, clock=clock)

    artifact = context.remember(
        ArtifactKind.LOCATION,
        "São Lourenço da Mata",
        "task-search-1",
    )

    assert artifact.origin_task_id == "task-search-1"
    assert artifact.timestamp == timestamp
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload[0]) == {"kind", "value", "origin_task_id", "timestamp"}
    assert "history" not in path.read_text(encoding="utf-8").lower()

    restored = SessionContext(path, clock=clock)
    assert restored.last_location == "São Lourenço da Mata"
    restored_artifact = restored.latest(ArtifactKind.LOCATION)
    assert restored_artifact is not None
    assert restored_artifact.origin_task_id == "task-search-1"
    assert restored_artifact.timestamp == timestamp


def test_atomic_writer_replaces_complete_json_document(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "session-context.json"
    clock = MutableClock(datetime(2026, 8, 9, tzinfo=timezone.utc))
    real_replace = session_context_module.os.replace
    replacements: list[tuple[str, str]] = []

    def observed_replace(source, destination) -> None:
        replacements.append((str(source), str(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(session_context_module.os, "replace", observed_replace)
    SessionContext(path, clock=clock).remember(
        "subject", "São Lourenço da Mata", "task-1"
    )

    assert replacements
    assert replacements[0][1] == str(path)
    assert json.loads(path.read_text(encoding="utf-8"))[0]["kind"] == "subject"
    assert list(tmp_path.glob("*.tmp")) == []


def test_context_is_bounded_by_count_and_age(tmp_path: Path) -> None:
    start = datetime(2026, 8, 9, 10, tzinfo=timezone.utc)
    clock = MutableClock(start)
    context = SessionContext(
        tmp_path / "session-context.json",
        max_artifacts=2,
        max_age=timedelta(hours=1),
        clock=clock,
    )

    context.remember("subject", "primeiro", "task-1")
    clock.current += timedelta(minutes=1)
    context.remember("site", "example.com", "task-2")
    clock.current += timedelta(minutes=1)
    context.remember("browser", "Brave", "task-3")

    assert [artifact.value for artifact in context.artifacts] == [
        "example.com",
        "Brave",
    ]
    assert context.last_subject is None

    clock.current += timedelta(hours=2)
    assert context.artifacts == ()
    assert json.loads(context.path.read_text(encoding="utf-8")) == []


def test_recovers_last_typed_operational_values(tmp_path: Path) -> None:
    clock = MutableClock(datetime(2026, 8, 9, tzinfo=timezone.utc))
    context = SessionContext(tmp_path / "session-context.json", clock=clock)
    context.remember_many(
        "task-1",
        {
            "subject": "clima",
            "location": "São Lourenço da Mata",
            "site": "google.com",
            "browser": "Brave",
            "editor": "xed",
        },
    )

    assert context.last_subject == "clima"
    assert context.last_location == "São Lourenço da Mata"
    assert context.last_site == "google.com"
    assert context.last_browser == "Brave"
    assert context.last_editor == "xed"


def test_resolves_la_in_a_new_task_without_raw_history(tmp_path: Path) -> None:
    timestamp = datetime(2026, 8, 9, tzinfo=timezone.utc)
    context = SessionContext(
        tmp_path / "session-context.json", clock=MutableClock(timestamp)
    )
    context.remember(
        "location", "São Lourenço da Mata", "previous-research-task"
    )

    command = "Agora pesquise a previsão do tempo de lá."
    resolution = context.resolve_with_provenance(command)

    assert context.resolve(command) == (
        "Agora pesquise a previsão do tempo de São Lourenço da Mata."
    )
    assert resolution.changed is True
    assert resolution.artifacts[0].kind is ArtifactKind.LOCATION
    assert resolution.artifacts[0].origin_task_id == "previous-research-task"


def test_la_falls_back_to_last_subject_when_location_was_not_classified(
    tmp_path: Path,
) -> None:
    timestamp = datetime(2026, 8, 9, tzinfo=timezone.utc)
    context = SessionContext(
        tmp_path / "session-context.json", clock=MutableClock(timestamp)
    )
    context.remember("subject", "São Lourenço da Mata", "previous-task")

    assert context.resolve("Pesquise a previsão do tempo de lá") == (
        "Pesquise a previsão do tempo de São Lourenço da Mata"
    )


def test_concurrent_instances_merge_instead_of_overwriting(tmp_path: Path) -> None:
    timestamp = datetime(2026, 8, 9, tzinfo=timezone.utc)
    path = tmp_path / "session-context.json"
    first = SessionContext(path, clock=MutableClock(timestamp))
    second = SessionContext(path, clock=MutableClock(timestamp))

    first.remember("subject", "São Lourenço da Mata", "task-1")
    second.remember("site", "example.com", "task-2")

    restored = SessionContext(path, clock=MutableClock(timestamp))
    assert restored.last_subject == "São Lourenço da Mata"
    assert restored.last_site == "example.com"


def test_oversized_or_invalid_utf8_context_is_ignored_without_full_parse(tmp_path: Path) -> None:
    path = tmp_path / "session-context.json"
    path.write_bytes(b"\xff" * 200)
    context = SessionContext(
        path,
        max_bytes=64,
        clock=MutableClock(datetime(2026, 8, 9, tzinfo=timezone.utc)),
    )

    assert context.artifacts == ()
