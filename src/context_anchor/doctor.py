from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import sys
from typing import Any

from .config import DesktopSettings
from .desktop import APP_COMMANDS


def collect_diagnostics() -> dict[str, Any]:
    cfg = DesktopSettings()

    apps: dict[str, dict[str, Any]] = {}
    for app_id, candidates in APP_COMMANDS.items():
        executable = None
        for candidate in candidates:
            found = shutil.which(candidate[0])
            if found:
                executable = found
                break
        apps[app_id] = {
            "available": executable is not None,
            "executable": executable,
        }

    session_type = os.getenv("XDG_SESSION_TYPE", "").strip().casefold() or None
    display = os.getenv("DISPLAY")
    wayland_display = os.getenv("WAYLAND_DISPLAY")

    return {
        "python": {
            "version": platform.python_version(),
            "supported": sys.version_info >= (3, 11),
        },
        "system": {
            "platform": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "desktop": {
            "enabled": cfg.desktop_enabled,
            "session_type": session_type,
            "display": display,
            "wayland_display": wayland_display,
            "x11_detected": bool(display) and session_type != "wayland",
            "pyautogui_installed": importlib.util.find_spec("pyautogui") is not None,
            "xdotool": shutil.which("xdotool"),
            "scrot": shutil.which("scrot"),
            "screenshot_dir": str(cfg.screenshot_dir),
        },
        "applications": apps,
        "notes": [
            "O backend físico inicial foi projetado para Linux/X11.",
            "Wayland ainda exige validação antes de habilitar controle real.",
            "O diagnóstico não executa cliques, teclas nem abre aplicativos.",
        ],
    }


def main() -> None:
    print(json.dumps(collect_diagnostics(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
