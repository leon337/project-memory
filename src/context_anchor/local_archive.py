from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

EXPECTED_REPOSITORY_FRAGMENT = "leon337/project-memory"
ARCHIVE_PREFIX = "project-memory-arquivos-locais"


class LocalArchiveStop(RuntimeError):
    """Raised when local files cannot be archived without risking data loss."""


@dataclass(frozen=True)
class ArchiveResult:
    archive_path: Path | None
    archived_files: tuple[str, ...]
    worktree_clean: bool


def _run(args: list[str], *, cwd: Path, check: bool = True, text: bool = True):
    completed = subprocess.run(args, cwd=cwd, text=text, capture_output=True, check=False)
    if check and completed.returncode != 0:
        raw = completed.stderr or completed.stdout or ("falha sem saída" if text else b"failure without output")
        detail = str(raw).strip() if text else os.fsdecode(raw).strip()
        raise LocalArchiveStop(f"Comando falhou: {' '.join(args)}\n{detail}")
    return completed


def _git_text(repo_root: Path, *args: str) -> str:
    return str(_run(["git", *args], cwd=repo_root, text=True).stdout).strip()


def _discover_repo_root(candidate: Path) -> Path:
    if shutil.which("git") is None:
        raise LocalArchiveStop("Git não está disponível no PATH.")
    discovered = str(_run(["git", "rev-parse", "--show-toplevel"], cwd=candidate, text=True).stdout).strip()
    if not discovered:
        raise LocalArchiveStop("Não foi possível localizar a raiz do repositório.")
    return Path(discovered).resolve()


def _assert_expected_repository(repo_root: Path) -> str:
    origin = _git_text(repo_root, "remote", "get-url", "origin")
    if EXPECTED_REPOSITORY_FRAGMENT not in origin:
        raise LocalArchiveStop(
            "O remote origin não corresponde a leon337/project-memory. "
            "Nenhum arquivo foi movido ou removido."
        )
    return origin


def _assert_no_tracked_changes(repo_root: Path) -> None:
    status = _git_text(repo_root, "status", "--porcelain=v1", "--untracked-files=no")
    if status:
        raise LocalArchiveStop(
            "Existem alterações em arquivos rastreados pelo Git. "
            "O empacotamento foi interrompido para não misturar trabalho do projeto "
            "com arquivos locais."
        )


def _untracked_paths(repo_root: Path) -> tuple[Path, ...]:
    completed = _run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=repo_root,
        text=False,
    )
    raw = bytes(completed.stdout)
    paths = tuple(Path(os.fsdecode(item)) for item in raw.split(b"\0") if item)
    return tuple(sorted(paths, key=lambda path: os.fsencode(path.as_posix())))


def _desktop_dir() -> Path:
    if shutil.which("xdg-user-dir") is not None:
        completed = subprocess.run(["xdg-user-dir", "DESKTOP"], text=True, capture_output=True, check=False)
        raw = (completed.stdout or "").strip()
        if completed.returncode == 0 and raw:
            candidate = Path(raw).expanduser()
            if candidate.is_dir():
                return candidate.resolve()
    for candidate in (Path.home() / "Área de Trabalho", Path.home() / "Desktop"):
        if candidate.is_dir():
            return candidate.resolve()
    raise LocalArchiveStop(
        "Não foi possível localizar a Área de Trabalho. "
        "Use --output-dir para informar a pasta de destino."
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_zip_member(archive: zipfile.ZipFile, member: str) -> str:
    digest = hashlib.sha256()
    with archive.open(member, "r") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validated_sources(repo_root: Path, relative_paths: tuple[Path, ...]) -> dict[str, tuple[Path, str]]:
    root = repo_root.resolve()
    sources: dict[str, tuple[Path, str]] = {}
    for relative in relative_paths:
        if relative.is_absolute() or ".." in relative.parts:
            raise LocalArchiveStop(f"Caminho inseguro retornado pelo Git: {relative}")
        source = root / relative
        if source.is_symlink():
            raise LocalArchiveStop(
                f"Link simbólico não é arquivado automaticamente: {relative}. "
                "Nenhum arquivo foi removido."
            )
        if not source.exists() or not source.is_file():
            raise LocalArchiveStop(
                f"O item não é um arquivo regular disponível: {relative}. "
                "Nenhum arquivo foi removido."
            )
        resolved = source.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise LocalArchiveStop(
                f"O caminho sai da raiz do repositório: {relative}. "
                "Nenhum arquivo foi removido."
            )
        archive_name = relative.as_posix()
        sources[archive_name] = (source, _sha256_file(source))
    return sources


def _next_archive_path(output_dir: Path, now: datetime) -> Path:
    stamp = now.strftime("%Y-%m-%d_%H%M%S")
    base = output_dir / f"{ARCHIVE_PREFIX}-{stamp}.zip"
    if not base.exists():
        return base
    counter = 1
    while True:
        candidate = output_dir / f"{ARCHIVE_PREFIX}-{stamp}-{counter}.zip"
        if not candidate.exists():
            return candidate
        counter += 1


def _verify_archive(archive_path: Path, sources: dict[str, tuple[Path, str]]) -> None:
    expected_names = tuple(sources)
    with zipfile.ZipFile(archive_path, "r") as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise LocalArchiveStop(f"Falha de integridade no ZIP: {bad_member}")
        if tuple(archive.namelist()) != expected_names:
            raise LocalArchiveStop("O conteúdo do ZIP não corresponde exatamente aos arquivos selecionados.")
        for archive_name, (_, expected_hash) in sources.items():
            if _sha256_zip_member(archive, archive_name) != expected_hash:
                raise LocalArchiveStop(f"O conteúdo arquivado não corresponde ao original: {archive_name}")
    for archive_name, (source, expected_hash) in sources.items():
        if not source.exists() or _sha256_file(source) != expected_hash:
            raise LocalArchiveStop(
                f"O arquivo mudou durante o empacotamento: {archive_name}. "
                "Nenhum original será removido."
            )


def _remove_archived_sources(repo_root: Path, sources: dict[str, tuple[Path, str]]) -> None:
    parents: set[Path] = set()
    for source, _ in sources.values():
        source.unlink()
        parent = source.parent
        while parent != repo_root:
            parents.add(parent)
            parent = parent.parent
    for directory in sorted(parents, key=lambda path: len(path.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass


def archive_untracked_files(
    repo_root: Path | None = None,
    *,
    output_dir: Path | None = None,
    now: datetime | None = None,
    output: Callable[[str], None] = print,
) -> ArchiveResult:
    candidate = (repo_root or Path.cwd()).expanduser().resolve()
    root = _discover_repo_root(candidate)
    destination = (output_dir or _desktop_dir()).expanduser().resolve()
    output("\n=== EMPACOTAMENTO SEGURO DE ARQUIVOS LOCAIS ===")
    origin = _assert_expected_repository(root)
    _assert_no_tracked_changes(root)
    relative_paths = _untracked_paths(root)
    if not relative_paths:
        output("Nenhum arquivo não rastreado pelo Git foi encontrado.")
        output("\nRESULTADO: NADA A EMPACOTAR")
        return ArchiveResult(None, (), True)
    if destination.is_relative_to(root):
        raise LocalArchiveStop(
            "A pasta de destino precisa ficar fora do repositório. "
            "Nenhum arquivo foi movido ou removido."
        )
    destination.mkdir(parents=True, exist_ok=True)
    sources = _validated_sources(root, relative_paths)
    archive_path = _next_archive_path(destination, now or datetime.now())
    output(f"Repositório ............ {root}")
    output(f"Origin ................. {origin}")
    output(f"Arquivos locais ........ {len(sources)}")
    output(f"Destino ................ {archive_path}")
    try:
        with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for archive_name, (source, _) in sources.items():
                archive.write(source, arcname=archive_name)
        _verify_archive(archive_path, sources)
    except Exception:
        try:
            archive_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    output("Integridade do ZIP ...... PASS")
    try:
        _remove_archived_sources(root, sources)
    except OSError as exc:
        raise LocalArchiveStop(
            f"O ZIP foi verificado e preservado em {archive_path}, mas não foi possível "
            f"remover todos os originais: {exc}"
        ) from exc
    final_status = _git_text(root, "status", "--porcelain=v1", "--untracked-files=normal")
    clean = not bool(final_status)
    output("Originais arquivados ... PASS")
    output(f"Working tree ........... {'LIMPA' if clean else 'AINDA POSSUI ALTERAÇÕES'}")
    if clean:
        output("\nRESULTADO: ARQUIVOS LOCAIS PRESERVADOS E REPOSITÓRIO LIMPO")
    else:
        output("\nRESULTADO: ZIP PRESERVADO, MAS AINDA EXISTEM ALTERAÇÕES LOCAIS")
        output(final_status)
    return ArchiveResult(archive_path, tuple(sources), clean)


def main() -> None:
    parser = argparse.ArgumentParser(description=(
        "Empacota somente arquivos não rastreados pelo Git em um ZIP verificado "
        "fora do repositório e remove os originais apenas depois da verificação."
    ))
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Caminho dentro do repositório (padrão: diretório atual).")
    parser.add_argument("--output-dir", type=Path, default=None, help="Pasta de destino do ZIP (padrão: Área de Trabalho via xdg-user-dir).")
    args = parser.parse_args()
    try:
        result = archive_untracked_files(args.repo, output_dir=args.output_dir)
    except LocalArchiveStop as exc:
        print(f"\nRESULTADO: STOP\n{exc}")
        raise SystemExit(2) from exc
    except (OSError, zipfile.BadZipFile) as exc:
        print(f"\nRESULTADO: STOP\nFalha ao criar/verificar o ZIP: {exc}")
        raise SystemExit(2) from exc
    if not result.worktree_clean:
        raise SystemExit(1)


__all__ = ["ArchiveResult", "LocalArchiveStop", "archive_untracked_files", "main"]


if __name__ == "__main__":
    main()
