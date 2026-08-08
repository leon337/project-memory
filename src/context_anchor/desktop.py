from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Protocol


APP_COMMANDS: dict[str, tuple[tuple[str, ...], ...]] = {
    "firefox": (("firefox",),),
    "chromium": (("chromium",), ("chromium-browser",), ("google-chrome",)),
    "arquivos": (("nemo",), ("nautilus",)),
    "editor": (("xed",), ("gedit",)),
    "vscode": (("code",),),
    "calculadora": (("gnome-calculator",), ("mate-calc",)),
    "libreoffice": (("libreoffice",),),
}

SUPPORTED_APP_IDS = frozenset(APP_COMMANDS)

APP_ALIASES = {
    "browser": "firefox",
    "navegador": "firefox",
    "files": "arquivos",
    "file manager": "arquivos",
    "gerenciador de arquivos": "arquivos",
    "text editor": "editor",
    "code": "vscode",
    "visual studio code": "vscode",
    "calculator": "calculadora",
}


def canonical_app_id(value: str) -> str:
    normalized = " ".join(value.strip().casefold().split())
    return APP_ALIASES.get(normalized, normalized)


class DesktopBackend(Protocol):
    def capture_screen(self, output_path: Path) -> dict[str, Any]: ...

    def active_window(self) -> dict[str, Any]: ...

    def move_mouse(self, x: int, y: int) -> dict[str, Any]: ...

    def click_mouse(self, button: str) -> dict[str, Any]: ...

    def type_text(self, text: str) -> dict[str, Any]: ...

    def press_key(self, key: str) -> dict[str, Any]: ...

    def open_application(self, app_id: str) -> dict[str, Any]: ...


class PyAutoGuiDesktopBackend:
    """Desktop Linux backend.

    PyAutoGUI is imported lazily so CI and server-only processes do not require
    an active graphical display merely to import the package.
    """

    def __init__(self, *, pause_seconds: float = 0.05) -> None:
        self.pause_seconds = pause_seconds
        self._gui: Any | None = None

    def _pyautogui(self) -> Any:
        if self._gui is None:
            import pyautogui

            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = self.pause_seconds
            self._gui = pyautogui
        return self._gui

    def capture_screen(self, output_path: Path) -> dict[str, Any]:
        gui = self._pyautogui()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image = gui.screenshot()
        image.save(output_path)
        return {
            "action": "capture_screen",
            "path": str(output_path),
            "width": int(image.width),
            "height": int(image.height),
            "verified": output_path.exists(),
        }

    def active_window(self) -> dict[str, Any]:
        xdotool = shutil.which("xdotool")
        if not xdotool:
            return {
                "action": "active_window",
                "title": None,
                "verified": False,
                "reason": "xdotool não encontrado no sistema.",
            }

        completed = subprocess.run(
            [xdotool, "getactivewindow", "getwindowname"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        title = completed.stdout.strip() if completed.returncode == 0 else ""
        return {
            "action": "active_window",
            "title": title or None,
            "verified": bool(title),
        }

    def move_mouse(self, x: int, y: int) -> dict[str, Any]:
        gui = self._pyautogui()
        width, height = gui.size()
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError(
                f"Coordenada ({x}, {y}) fora da tela atual de {width}x{height}."
            )
        gui.moveTo(x, y, duration=0.15)
        current_x, current_y = gui.position()
        return {
            "action": "move_mouse",
            "x": int(current_x),
            "y": int(current_y),
            "verified": int(current_x) == x and int(current_y) == y,
        }

    def click_mouse(self, button: str) -> dict[str, Any]:
        gui = self._pyautogui()
        gui.click(button=button)
        x, y = gui.position()
        return {
            "action": "click_mouse",
            "button": button,
            "x": int(x),
            "y": int(y),
            "verified": True,
        }

    def type_text(self, text: str) -> dict[str, Any]:
        gui = self._pyautogui()
        gui.write(text, interval=0.01)
        return {
            "action": "type_text",
            "characters": len(text),
            "verified": True,
        }

    def press_key(self, key: str) -> dict[str, Any]:
        gui = self._pyautogui()
        gui.press(key)
        return {
            "action": "press_key",
            "key": key,
            "verified": True,
        }

    def open_application(self, app_id: str) -> dict[str, Any]:
        canonical = canonical_app_id(app_id)
        candidates = APP_COMMANDS.get(canonical)
        if not candidates:
            raise PermissionError(f"Aplicativo fora da allowlist: {app_id}")

        for candidate in candidates:
            executable = shutil.which(candidate[0])
            if not executable:
                continue
            argv = (executable, *candidate[1:])
            process = subprocess.Popen(
                argv,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            time.sleep(0.15)
            return {
                "action": "open_app",
                "app": canonical,
                "executable": executable,
                "pid": process.pid,
                "verified": process.poll() is None,
            }

        raise FileNotFoundError(
            f"Nenhum executável instalado foi encontrado para o aplicativo '{canonical}'."
        )
