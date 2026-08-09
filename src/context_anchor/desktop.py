from __future__ import annotations

import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Protocol


# Known aliases remain as convenience, not as an authorization boundary.
APP_COMMANDS: dict[str, tuple[tuple[str, ...], ...]] = {
    "firefox": (("firefox",),),
    "chromium": (("chromium",), ("chromium-browser",), ("google-chrome",)),
    "arquivos": (("nemo",), ("nautilus",)),
    "editor": (("xed",), ("gedit",)),
    "vscode": (("code",),),
    "calculadora": (("gnome-calculator",), ("mate-calc",)),
    "libreoffice": (("libreoffice",),),
    "brave-browser": (("brave-browser",), ("brave-browser-stable",), ("brave",)),
}

SUPPORTED_APP_IDS = frozenset(APP_COMMANDS)

APP_ALIASES = {
    "browser": "firefox",
    "navegador": "firefox",
    "files": "arquivos",
    "file manager": "arquivos",
    "gerenciador de arquivos": "arquivos",
    "editor de texto": "editor",
    "text editor": "editor",
    "text_editor": "editor",
    "xed": "editor",
    "gedit": "editor",
    "notepad": "editor",
    "code": "vscode",
    "visual studio code": "vscode",
    "calculator": "calculadora",
    "brave": "brave-browser",
    "brave browser": "brave-browser",
    "navegador brave": "brave-browser",
}


def canonical_app_id(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""

    # Preserve case-sensitive explicit paths/commands. Authorization is no longer
    # based on this canonicalization; it is only a convenience resolver.
    if "/" in raw:
        return raw

    normalized = " ".join(raw.casefold().split())
    for prefix in (
        "o navegador ",
        "navegador ",
        "browser ",
        "o aplicativo ",
        "a aplicação ",
        "aplicativo ",
        "aplicação ",
        "app ",
    ):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):].strip()
            break
    if normalized.startswith("o ") or normalized.startswith("a "):
        normalized = normalized[2:].strip()
    return APP_ALIASES.get(normalized, normalized)


def _application_candidates(value: str) -> tuple[tuple[str, ...], ...]:
    canonical = canonical_app_id(value)
    known = APP_COMMANDS.get(canonical)
    if known:
        return known

    candidates: list[tuple[str, ...]] = []
    for source in (canonical, value.strip()):
        if not source:
            continue
        try:
            argv = tuple(shlex.split(source))
        except ValueError:
            continue
        if argv and argv not in candidates:
            candidates.append(argv)

    if " " in canonical and "/" not in canonical:
        for executable_name in (canonical.replace(" ", "-"), canonical.replace(" ", "")):
            argv = (executable_name,)
            if argv not in candidates:
                candidates.append(argv)

    return tuple(candidates)


class DesktopFailsafeTriggered(RuntimeError):
    """Raised when the pointer is intentionally parked in a safety corner."""


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

    def __init__(
        self,
        *,
        pause_seconds: float = 0.05,
        app_ready_timeout_seconds: float = 3.0,
        failsafe_margin_pixels: int = 20,
    ) -> None:
        if failsafe_margin_pixels < 1:
            raise ValueError("failsafe_margin_pixels deve ser pelo menos 1.")
        self.pause_seconds = pause_seconds
        self.app_ready_timeout_seconds = app_ready_timeout_seconds
        self.failsafe_margin_pixels = failsafe_margin_pixels
        self._gui: Any | None = None
        self._expected_window_id: str | None = None
        self._focus_guard_error: str | None = None

    def _pyautogui(self) -> Any:
        if self._gui is None:
            import pyautogui

            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = self.pause_seconds
            self._gui = pyautogui
        return self._gui

    def _assert_pointer_outside_failsafe_zone(self, gui: Any | None = None) -> None:
        """Block physical input while the pointer is parked in any screen corner.

        This guard is intentionally independent from PyAutoGUI's native FAILSAFE.
        The native mechanism remains enabled as defense in depth, but the Robô
        does not rely on it as the only physical interruption mechanism.
        """

        active_gui = gui or self._pyautogui()
        width, height = active_gui.size()
        x, y = active_gui.position()
        margin = self.failsafe_margin_pixels

        near_left = 0 <= int(x) < margin
        near_right = max(0, int(width) - margin) <= int(x) < int(width)
        near_top = 0 <= int(y) < margin
        near_bottom = max(0, int(height) - margin) <= int(y) < int(height)

        if (near_left or near_right) and (near_top or near_bottom):
            raise DesktopFailsafeTriggered(
                "Ponteiro detectado na zona de segurança de um canto da tela. "
                "A entrada física foi recusada antes da execução."
            )

    @staticmethod
    def _xdotool_path() -> str | None:
        return shutil.which("xdotool")

    def _active_window_id(self) -> str | None:
        xdotool = self._xdotool_path()
        if not xdotool:
            return None
        completed = subprocess.run(
            [xdotool, "getactivewindow"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        value = completed.stdout.strip() if completed.returncode == 0 else ""
        return value or None

    def _window_title(self, window_id: str | None = None) -> str | None:
        xdotool = self._xdotool_path()
        if not xdotool:
            return None
        argv = [xdotool, "getwindowname", window_id] if window_id else [
            xdotool,
            "getactivewindow",
            "getwindowname",
        ]
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        value = completed.stdout.strip() if completed.returncode == 0 else ""
        return value or None

    def _wait_for_active_window_change(self, previous_window_id: str | None) -> dict[str, Any]:
        if not self._xdotool_path() or previous_window_id is None:
            time.sleep(min(self.app_ready_timeout_seconds, 0.8))
            current = self._active_window_id()
            return {
                "window_changed": None,
                "window_id": current,
                "window_title": self._window_title(current),
            }

        deadline = time.monotonic() + self.app_ready_timeout_seconds
        current: str | None = previous_window_id
        while time.monotonic() < deadline:
            current = self._active_window_id()
            if current and current != previous_window_id:
                time.sleep(0.15)
                return {
                    "window_changed": True,
                    "window_id": current,
                    "window_title": self._window_title(current),
                }
            time.sleep(0.05)

        return {
            "window_changed": False,
            "window_id": current,
            "window_title": self._window_title(current),
        }

    def _focused_window_for_input(self) -> tuple[str | None, str | None]:
        if self._focus_guard_error:
            raise RuntimeError(self._focus_guard_error)

        current = self._active_window_id()
        if self._expected_window_id and current and current != self._expected_window_id:
            raise RuntimeError(
                "O foco mudou para outra janela desde a última ação preparada. "
                "O Robô recusou enviar teclado para evitar digitar no lugar errado."
            )
        return current, self._window_title(current)

    @staticmethod
    def _type_text_with_unicode(gui: Any, text: str) -> str:
        """Type printable text while preserving Unicode on Linux/X11.

        PyAutoGUI's write() handles ordinary keyboard characters well but can
        silently lose characters such as á/ç. Non-ASCII code points therefore use
        Linux Unicode input (Ctrl+Shift+U, hexadecimal code point, Enter). ASCII
        chunks still use write() for speed and predictable keyboard behavior.
        """

        ascii_buffer: list[str] = []
        used_unicode = False

        def flush_ascii() -> None:
            if ascii_buffer:
                gui.write("".join(ascii_buffer), interval=0.01)
                ascii_buffer.clear()

        for char in text:
            if ord(char) < 128:
                ascii_buffer.append(char)
                continue

            flush_ascii()
            gui.hotkey("ctrl", "shift", "u")
            gui.write(f"{ord(char):x}", interval=0.01)
            gui.press("enter")
            used_unicode = True

        flush_ascii()
        return "linux-unicode-input" if used_unicode else "pyautogui-write"

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
        title = self._window_title()
        return {
            "action": "active_window",
            "title": title,
            "verified": bool(title),
        }

    def move_mouse(self, x: int, y: int) -> dict[str, Any]:
        gui = self._pyautogui()
        self._assert_pointer_outside_failsafe_zone(gui)
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
        self._assert_pointer_outside_failsafe_zone(gui)
        gui.click(button=button)
        x, y = gui.position()
        current_window = self._active_window_id()
        if current_window:
            self._expected_window_id = current_window
            self._focus_guard_error = None
        return {
            "action": "click_mouse",
            "button": button,
            "x": int(x),
            "y": int(y),
            "window_id": current_window,
            "window_title": self._window_title(current_window),
            "verified": True,
        }

    def type_text(self, text: str) -> dict[str, Any]:
        gui = self._pyautogui()
        self._assert_pointer_outside_failsafe_zone(gui)
        window_id, window_title = self._focused_window_for_input()
        input_method = self._type_text_with_unicode(gui, text)
        return {
            "action": "type_text",
            "characters": len(text),
            "input_method": input_method,
            "window_id": window_id,
            "window_title": window_title,
            "verified": window_id is not None if self._xdotool_path() else True,
        }

    def press_key(self, key: str) -> dict[str, Any]:
        gui = self._pyautogui()
        self._assert_pointer_outside_failsafe_zone(gui)
        window_id, window_title = self._focused_window_for_input()
        gui.press(key)
        return {
            "action": "press_key",
            "key": key,
            "window_id": window_id,
            "window_title": window_title,
            "verified": window_id is not None if self._xdotool_path() else True,
        }

    def open_application(self, app_id: str) -> dict[str, Any]:
        canonical = canonical_app_id(app_id)
        candidates = _application_candidates(app_id)
        if not candidates:
            raise FileNotFoundError(f"Não foi possível resolver o aplicativo/comando '{app_id}'.")

        previous_window = self._active_window_id()

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
            readiness = self._wait_for_active_window_change(previous_window)
            window_id = readiness["window_id"]
            window_changed = readiness["window_changed"]

            if window_id and window_changed is not False:
                self._expected_window_id = window_id
                self._focus_guard_error = None
            elif self._xdotool_path() and previous_window is not None:
                self._expected_window_id = None
                self._focus_guard_error = (
                    f"O aplicativo '{canonical}' foi iniciado, mas não assumiu o foco dentro de "
                    f"{self.app_ready_timeout_seconds:.1f}s. O Robô não enviará teclado até o foco ser confirmado por um clique."
                )
            else:
                self._expected_window_id = window_id
                self._focus_guard_error = None

            launched = process.poll() is None or window_changed is True
            return {
                "action": "open_app",
                "app": canonical,
                "executable": executable,
                "argv": list(argv[1:]),
                "pid": process.pid,
                "window_changed": window_changed,
                "window_id": window_id,
                "window_title": readiness["window_title"],
                "verified": bool(launched and window_changed is not False),
            }

        raise FileNotFoundError(
            f"Nenhum executável instalado foi encontrado para o aplicativo/comando '{app_id}'."
        )
