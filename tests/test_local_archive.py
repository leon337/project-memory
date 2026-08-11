from __future__ import annotations

import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

import context_anchor.local_archive as local_archive
from context_anchor.local_archive import LocalArchiveStop, archive_untracked_files


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def _prepare_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    _git(repo, "config", "user.email", "tests@example.com")
    _git(repo, "config", "user.name", "Tests")
    (repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "initial")
    _git(
        repo,
        "remote",
        "add",
        "origin",
        "https://github.com/leon337/project-memory.git",
    )
    return repo


def test_archives_only_untracked_files_and_leaves_repo_clean(tmp_path: Path) -> None:
    repo = _prepare_repo(tmp_path)
    desktop = tmp_path / "desktop"
    desktop.mkdir()
    (repo / "imagem.png").write_bytes(b"png-data")
    (repo / "docs").mkdir()
    (repo / "docs" / "pesquisa çã.pdf").write_bytes(b"pdf-data")

    result = archive_untracked_files(
        repo,
        output_dir=desktop,
        now=datetime(2026, 8, 11, 20, 44, 0),
        output=lambda _: None,
    )

    assert result.worktree_clean is True
    assert result.archive_path == (
        desktop / "project-memory-arquivos-locais-2026-08-11_204400.zip"
    )
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "tracked\n"
    assert not (repo / "imagem.png").exists()
    assert not (repo / "docs" / "pesquisa çã.pdf").exists()
    assert _git(repo, "status", "--porcelain") == ""
    assert result.archive_path is not None
    with zipfile.ZipFile(result.archive_path, "r") as archive:
        assert archive.namelist() == ["docs/pesquisa çã.pdf", "imagem.png"]
        assert archive.read("docs/pesquisa çã.pdf") == b"pdf-data"
        assert archive.read("imagem.png") == b"png-data"


def test_stops_when_tracked_files_are_modified(tmp_path: Path) -> None:
    repo = _prepare_repo(tmp_path)
    desktop = tmp_path / "desktop"
    desktop.mkdir()
    (repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
    (repo / "local.png").write_bytes(b"keep-me")

    with pytest.raises(LocalArchiveStop, match="arquivos rastreados"):
        archive_untracked_files(repo, output_dir=desktop, output=lambda _: None)

    assert (repo / "local.png").read_bytes() == b"keep-me"
    assert list(desktop.iterdir()) == []


def test_stops_when_destination_is_inside_repository(tmp_path: Path) -> None:
    repo = _prepare_repo(tmp_path)
    (repo / "local.png").write_bytes(b"keep-me")
    destination = repo / "backup"

    with pytest.raises(LocalArchiveStop, match="fora do repositório"):
        archive_untracked_files(repo, output_dir=destination, output=lambda _: None)

    assert (repo / "local.png").read_bytes() == b"keep-me"


def test_verification_failure_never_deletes_originals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _prepare_repo(tmp_path)
    desktop = tmp_path / "desktop"
    desktop.mkdir()
    local_file = repo / "local.png"
    local_file.write_bytes(b"keep-me")

    def fail_verification(*args: object, **kwargs: object) -> None:
        raise LocalArchiveStop("falha simulada")

    monkeypatch.setattr(local_archive, "_verify_archive", fail_verification)

    with pytest.raises(LocalArchiveStop, match="falha simulada"):
        archive_untracked_files(repo, output_dir=desktop, output=lambda _: None)

    assert local_file.read_bytes() == b"keep-me"
    assert list(desktop.iterdir()) == []
