from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


_WINDOW_LIST_PROPERTIES = ("_NET_CLIENT_LIST_STACKING", "_NET_CLIENT_LIST")


def _xprop_path() -> str | None:
    return shutil.which("xprop")


def _xdotool_path() -> str | None:
    return shutil.which("xdotool")


def _run(argv: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _managed_window_ids() -> tuple[str, ...]:
    """Return managed X11 client windows from top-most to bottom-most."""

    xprop = _xprop_path()
    if not xprop:
        return ()
    for property_name in _WINDOW_LIST_PROPERTIES:
        completed = _run([xprop, "-root", property_name])
        if completed is None or completed.returncode != 0:
            continue
        window_ids = re.findall(r"0x[0-9a-fA-F]+", completed.stdout)
        if window_ids:
            # EWMH stacking order is bottom-to-top; inspect the most visible
            # candidate first without activating or changing focus.
            return tuple(reversed(window_ids))
    return ()


def _window_class(window_id: str) -> str | None:
    xprop = _xprop_path()
    if not xprop:
        return None
    completed = _run([xprop, "-id", window_id, "WM_CLASS"])
    if completed is None or completed.returncode != 0:
        return None
    values = [
        item
        for item in re.findall(r'"([^"]+)"', completed.stdout)
        if item.strip()
    ]
    return " ".join(values) or None


def _window_title(window_id: str) -> str | None:
    xdotool = _xdotool_path()
    if not xdotool:
        return None
    completed = _run([xdotool, "getwindowname", window_id])
    if completed is None or completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def _window_process_id(window_id: str) -> int | None:
    xprop = _xprop_path()
    if not xprop:
        return None
    completed = _run([xprop, "-id", window_id, "_NET_WM_PID"])
    if completed is None or completed.returncode != 0:
        return None
    match = re.search(r"=\s*(\d+)\s*$", completed.stdout)
    return int(match.group(1)) if match else None


def _active_window_id() -> str | None:
    xdotool = _xdotool_path()
    if not xdotool:
        return None
    completed = _run([xdotool, "getactivewindow"])
    if completed is None or completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    if not value:
        return None
    try:
        return hex(int(value))
    except ValueError:
        return value.casefold()


def _process_executable(pid: int | None) -> str | None:
    if not isinstance(pid, int) or pid <= 0:
        return None
    try:
        return str((Path("/proc") / str(pid) / "exe").resolve(strict=True))
    except OSError:
        return None


def _class_tokens(value: str | None) -> set[str]:
    raw = (value or "").casefold()
    tokens = set(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", raw))
    tokens.update(
        item.strip('"\' ,')
        for item in raw.split()
        if item.strip('"\' ,')
    )
    return tokens


def _expected_identities(app_id: str) -> set[str]:
    raw = app_id.strip().casefold()
    basename = Path(raw.split(maxsplit=1)[0]).name if raw else ""
    expected = {item for item in (raw, basename) if item}

    aliases: dict[str, tuple[str, ...]] = {
        "editor": ("xed", "gedit", "pluma", "mousepad", "gnome-text-editor"),
        "editor de texto": ("xed", "gedit", "pluma", "mousepad", "gnome-text-editor"),
        "text editor": ("xed", "gedit", "pluma", "mousepad", "gnome-text-editor"),
        "calculadora": ("gnome-calculator", "mate-calc", "kcalc", "galculator"),
        "calculator": ("gnome-calculator", "mate-calc", "kcalc", "galculator"),
        "vscode": ("code", "code-oss", "vscode", "codium"),
        "code": ("code", "code-oss", "vscode", "codium"),
        "brave-browser": ("brave", "brave-browser", "brave-browser-stable"),
        "firefox": ("firefox",),
        "chromium": ("chromium", "chrome", "google-chrome", "google-chrome-stable"),
    }
    expected.update(aliases.get(raw, ()))
    expected.update(aliases.get(basename, ()))
    return {item for item in expected if item}


def observe_existing_application(app_id: str) -> dict[str, Any]:
    """Passively locate an already-existing X11 application window.

    This observation exists only for recovery after a durable ``executed``
    action. It never launches, focuses, raises, clicks, types into, or otherwise
    mutates a window. The result is therefore independent of the recovered
    ExecutionReceipt and cannot itself create the effect it is trying to prove.
    """

    expected = _expected_identities(app_id)
    active_window = _active_window_id()

    for window_id in _managed_window_ids():
        window_class = _window_class(window_id)
        if not _class_tokens(window_class).intersection(expected):
            continue

        pid = _window_process_id(window_id)
        executable = _process_executable(pid)
        process_name = Path(executable).name.casefold() if executable else ""
        return {
            "action": "observe_application",
            "app": app_id,
            "window_id": window_id,
            "window_title": _window_title(window_id),
            "window_class": window_class,
            "window_process_id": pid,
            "window_process_executable": executable,
            "process_alive": bool(pid and (Path("/proc") / str(pid)).exists()),
            "process_identity_observed": bool(process_name and process_name in expected),
            "class_identity_observed": True,
            "identity_observed": True,
            "active_window": bool(
                active_window
                and window_id.casefold()
                in {active_window.casefold(), active_window.removeprefix("0x").casefold()}
            ),
            "recovery_existing_window": True,
            "observation_method": "x11-managed-window-class",
            "source": "x11-recovery",
            "verified": True,
        }

    return {
        "action": "observe_application",
        "app": app_id,
        "window_id": None,
        "window_title": None,
        "window_class": None,
        "class_identity_observed": False,
        "identity_observed": False,
        "recovery_existing_window": False,
        "observation_method": "x11-managed-window-class",
        "source": "x11-recovery",
        "verified": False,
    }


__all__ = ["observe_existing_application"]
