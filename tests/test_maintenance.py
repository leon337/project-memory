from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import context_anchor.maintenance as maintenance
from context_anchor.maintenance import MaintenanceStop, update_repository


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def _prepare_repositories(tmp_path: Path) -> tuple[Path, Path, Path]:
    remote = tmp_path / "remote.git"
    upstream = tmp_path / "upstream"
    local = tmp_path / "local"

    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "init", "-b", "main", str(upstream)], check=True, capture_output=True)
    _git(upstream, "config", "user.email", "tests@example.com")
    _git(upstream, "config", "user.name", "Tests")
    (upstream / "state.txt").write_text("v1\n", encoding="utf-8")
    _git(upstream, "add", "state.txt")
    _git(upstream, "commit", "-m", "initial")
    _git(upstream, "remote", "add", "origin", str(remote))
    _git(upstream, "push", "-u", "origin", "main")

    subprocess.run(
        ["git", "clone", "--branch", "main", str(remote), str(local)],
        check=True,
        capture_output=True,
    )
    _git(local, "config", "user.email", "tests@example.com")
    _git(local, "config", "user.name", "Tests")
    return remote, upstream, local


def test_updater_fast_forwards_clean_main_without_rewriting_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, upstream, local = _prepare_repositories(tmp_path)
    monkeypatch.setattr(maintenance, "EXPECTED_REPOSITORY_FRAGMENT", "remote.git")

    (upstream / "state.txt").write_text("v2\n", encoding="utf-8")
    _git(upstream, "add", "state.txt")
    _git(upstream, "commit", "-m", "remote update")
    _git(upstream, "push", "origin", "main")
    remote_head = _git(upstream, "rev-parse", "HEAD")

    lines: list[str] = []
    result = update_repository(
        local,
        sync_environment=False,
        output=lines.append,
    )

    assert result["commit"] == remote_head
    assert _git(local, "rev-parse", "HEAD") == remote_head
    assert (local / "state.txt").read_text(encoding="utf-8") == "v2\n"
    assert any("ATUALIZADO COM SEGURANÇA" in line for line in lines)


def test_updater_stops_before_touching_dirty_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, local = _prepare_repositories(tmp_path)
    monkeypatch.setattr(maintenance, "EXPECTED_REPOSITORY_FRAGMENT", "remote.git")
    original_head = _git(local, "rev-parse", "HEAD")
    (local / "state.txt").write_text("alteração local\n", encoding="utf-8")

    with pytest.raises(MaintenanceStop, match="alterações locais"):
        update_repository(local, sync_environment=False, output=lambda _: None)

    assert _git(local, "rev-parse", "HEAD") == original_head
    assert (local / "state.txt").read_text(encoding="utf-8") == "alteração local\n"


def test_updater_stops_when_local_main_has_unpublished_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, local = _prepare_repositories(tmp_path)
    monkeypatch.setattr(maintenance, "EXPECTED_REPOSITORY_FRAGMENT", "remote.git")

    (local / "local-only.txt").write_text("não descartar\n", encoding="utf-8")
    _git(local, "add", "local-only.txt")
    _git(local, "commit", "-m", "local only")
    local_head = _git(local, "rev-parse", "HEAD")

    with pytest.raises(MaintenanceStop, match="não existem em origin/main"):
        update_repository(local, sync_environment=False, output=lambda _: None)

    assert _git(local, "rev-parse", "HEAD") == local_head
    assert (local / "local-only.txt").exists()
