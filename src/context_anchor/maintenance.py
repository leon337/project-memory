from __future__ import annotations

import compileall
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .doctor import collect_diagnostics


EXPECTED_REPOSITORY_FRAGMENT = "leon337/project-memory"


class MaintenanceStop(RuntimeError):
    """Raised when a local maintenance action must stop without destructive recovery."""


@dataclass(frozen=True)
class ValidationCheck:
    name: str
    ok: bool
    detail: str


def _run(
    args: list[str],
    *,
    cwd: Path,
    check: bool = True,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=capture_output,
        check=False,
    )
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "falha sem saída").strip()
        raise MaintenanceStop(f"Comando falhou: {' '.join(args)}\n{detail}")
    return completed


def _git(repo_root: Path, *args: str) -> str:
    completed = _run(["git", *args], cwd=repo_root)
    return completed.stdout.strip()


def _default_repo_root() -> Path:
    candidate = Path(__file__).resolve().parents[2]
    if shutil.which("git") is None:
        raise MaintenanceStop("Git não está disponível no PATH.")
    discovered = _run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=candidate,
    ).stdout.strip()
    if not discovered:
        raise MaintenanceStop("Não foi possível localizar a raiz do repositório.")
    return Path(discovered).resolve()


def _assert_expected_repository(repo_root: Path) -> str:
    origin = _git(repo_root, "remote", "get-url", "origin")
    if EXPECTED_REPOSITORY_FRAGMENT not in origin:
        raise MaintenanceStop(
            "O remote origin não corresponde a leon337/project-memory. "
            "Nenhuma atualização foi aplicada."
        )
    return origin


def _assert_clean_worktree(repo_root: Path) -> None:
    status = _git(repo_root, "status", "--porcelain", "--untracked-files=normal")
    if status:
        raise MaintenanceStop(
            "Existem alterações locais. Nenhum arquivo será descartado automaticamente.\n"
            "Execute 'git status' e preserve/commite/stashe as alterações antes de atualizar."
        )


def _ahead_behind(repo_root: Path) -> tuple[int, int]:
    raw = _git(repo_root, "rev-list", "--left-right", "--count", "main...origin/main")
    try:
        ahead_text, behind_text = raw.split()
        return int(ahead_text), int(behind_text)
    except (TypeError, ValueError) as exc:
        raise MaintenanceStop(f"Não foi possível comparar main e origin/main: {raw!r}") from exc


def _venv_python(repo_root: Path, *, create_if_missing: bool) -> Path:
    python = repo_root / ".venv" / "bin" / "python"
    if python.exists():
        return python
    if not create_if_missing:
        raise MaintenanceStop(
            "Ambiente .venv não encontrado. Execute 'atualizar-robo' para preparar o ambiente."
        )
    _run([sys.executable, "-m", "venv", ".venv"], cwd=repo_root, capture_output=False)
    if not python.exists():
        raise MaintenanceStop("A criação de .venv terminou sem gerar .venv/bin/python.")
    return python


def update_repository(
    repo_root: Path | None = None,
    *,
    sync_environment: bool = True,
    output: Callable[[str], None] = print,
) -> dict[str, str]:
    """Safely fast-forward the local main branch and synchronize the editable env.

    The function deliberately refuses to reset, clean, force-switch, rewrite history,
    or overwrite local work. Dirty trees and local-only commits stop the operation.
    """

    root = (repo_root or _default_repo_root()).resolve()
    output("\n=== ATUALIZAÇÃO LOCAL DO ROBÔ ===")
    origin = _assert_expected_repository(root)
    _assert_clean_worktree(root)

    output("Git/repositório ........ PASS")
    output(f"Origin ................ {origin}")
    output("Buscando origin/main ...")
    _git(root, "fetch", "origin", "main")

    ahead, behind = _ahead_behind(root)
    if ahead:
        raise MaintenanceStop(
            "A branch main local possui commit(s) que não existem em origin/main. "
            "A atualização foi interrompida para não reescrever histórico."
        )

    current_branch = _git(root, "branch", "--show-current")
    if current_branch != "main":
        _git(root, "switch", "main")

    if behind:
        _git(root, "merge", "--ff-only", "origin/main")

    _assert_clean_worktree(root)
    head = _git(root, "rev-parse", "HEAD")
    output("Main fast-forward ...... PASS")
    output(f"Commit ................ {head}")

    if sync_environment:
        python = _venv_python(root, create_if_missing=True)
        output("Sincronizando ambiente .venv ...")
        _run(
            [str(python), "-m", "pip", "install", "-e", ".[dev]"],
            cwd=root,
            capture_output=False,
        )
        output("Dependências Python .... PASS")
        output("Sincronizando Chromium do Playwright ...")
        _run(
            [str(python), "-m", "playwright", "install", "chromium"],
            cwd=root,
            capture_output=False,
        )
        output("Playwright Chromium .... PASS")

    output("\nRESULTADO: ATUALIZADO COM SEGURANÇA")
    return {"repo_root": str(root), "commit": head, "branch": "main"}


def _playwright_chromium_available() -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            executable = Path(playwright.chromium.executable_path)
        return executable.exists(), str(executable)
    except Exception as exc:  # diagnostic boundary: never hide which check failed
        return False, f"{type(exc).__name__}: {exc}"


def validate_repository(
    repo_root: Path | None = None,
    *,
    run_tests: bool = True,
    output: Callable[[str], None] = print,
) -> list[ValidationCheck]:
    """Validate code, environment and Linux/X11 prerequisites for physical smoke."""

    root = (repo_root or _default_repo_root()).resolve()
    checks: list[ValidationCheck] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append(ValidationCheck(name, ok, detail))

    output("\n=== VALIDAÇÃO LOCAL DO ROBÔ ===")

    try:
        _assert_expected_repository(root)
        add("Repositório", True, str(root))
    except MaintenanceStop as exc:
        add("Repositório", False, str(exc))

    try:
        clean = not bool(_git(root, "status", "--porcelain", "--untracked-files=normal"))
        add("Working tree", clean, "limpa" if clean else "há alterações locais")
    except MaintenanceStop as exc:
        add("Working tree", False, str(exc))

    try:
        branch = _git(root, "branch", "--show-current")
        add("Branch", branch == "main", branch or "detached")
    except MaintenanceStop as exc:
        add("Branch", False, str(exc))

    python = _venv_python(root, create_if_missing=False)
    version = _run(
        [str(python), "-c", "import platform; print(platform.python_version())"],
        cwd=root,
    ).stdout.strip()
    supported = _run(
        [str(python), "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"],
        cwd=root,
        check=False,
    ).returncode == 0
    add("Python", supported, version)

    compiled = compileall.compile_dir(str(root / "src"), quiet=1)
    compiled = compileall.compile_dir(str(root / "tests"), quiet=1) and compiled
    add("Compilação", bool(compiled), "src + tests")

    if run_tests:
        tests = _run([str(python), "-m", "pytest", "-q"], cwd=root, check=False)
        tail = (tests.stdout or tests.stderr or "sem saída").strip().splitlines()
        add("Pytest", tests.returncode == 0, tail[-1] if tail else "sem saída")

    diagnostics = collect_diagnostics()
    desktop = diagnostics["desktop"]
    add("Desktop habilitado", bool(desktop["enabled"]), str(desktop["enabled"]))
    add("Sessão X11", bool(desktop["x11_detected"]), str(desktop.get("display")))
    add("PyAutoGUI", bool(desktop["pyautogui_installed"]), "instalado" if desktop["pyautogui_installed"] else "ausente")
    add("Pillow", bool(desktop["pillow_installed"]), "instalado" if desktop["pillow_installed"] else "ausente")
    add("PyScreeze", bool(desktop["pyscreeze_installed"]), "instalado" if desktop["pyscreeze_installed"] else "ausente")
    add("xdotool", bool(desktop["xdotool"]), str(desktop["xdotool"] or "ausente"))
    add("scrot", bool(desktop["scrot"]), str(desktop["scrot"] or "ausente"))

    chromium_ok, chromium_detail = _playwright_chromium_available()
    add("Chromium Playwright", chromium_ok, chromium_detail)

    for check in checks:
        label = "PASS" if check.ok else "FAIL"
        output(f"{check.name:<22} {label:<4}  {check.detail}")

    if all(check.ok for check in checks):
        output("\nRESULTADO: PRONTO PARA TESTE FÍSICO")
    else:
        output("\nRESULTADO: STOP — CORRIGIR ITENS FAIL ANTES DO TESTE FÍSICO")
    return checks


def main_update() -> None:
    try:
        update_repository()
    except MaintenanceStop as exc:
        print(f"\nRESULTADO: STOP\n{exc}")
        raise SystemExit(2) from exc


def main_validate() -> None:
    try:
        checks = validate_repository()
    except MaintenanceStop as exc:
        print(f"\nRESULTADO: STOP\n{exc}")
        raise SystemExit(2) from exc
    if not all(check.ok for check in checks):
        raise SystemExit(1)


__all__ = [
    "MaintenanceStop",
    "ValidationCheck",
    "main_update",
    "main_validate",
    "update_repository",
    "validate_repository",
]
