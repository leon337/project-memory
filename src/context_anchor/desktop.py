from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Protocol


_ATSPI_READ_SCRIPT = r"""
import json
import sys
import pyatspi

expected_title = sys.argv[1].casefold().strip()
focused = []
editable = []

def has_state(obj, state):
    try:
        return obj.getState().contains(state)
    except Exception:
        return False

def walk(obj, app_name, frame_name, depth=0):
    if depth > 24:
        return
    try:
        current_frame = frame_name
        if obj.getRoleName() in {"frame", "window", "dialog"}:
            current_frame = obj.name or frame_name
        if has_state(obj, pyatspi.STATE_EDITABLE):
            try:
                text = obj.queryText()
                value = text.getText(0, text.characterCount)
                item = {
                    "text": value,
                    "role": obj.getRoleName(),
                    "name": obj.name or "",
                    "app": app_name,
                    "frame": current_frame or "",
                    "focused": has_state(obj, pyatspi.STATE_FOCUSED),
                }
                editable.append(item)
                if item["focused"]:
                    focused.append(item)
            except Exception:
                pass
        for child in obj:
            walk(child, app_name, current_frame, depth + 1)
    except Exception:
        return

for desktop_index in range(pyatspi.Registry.getDesktopCount()):
    desktop = pyatspi.Registry.getDesktop(desktop_index)
    for app in desktop:
        try:
            app_name = app.name or ""
            for child in app:
                active = has_state(child, pyatspi.STATE_ACTIVE) or has_state(child, pyatspi.STATE_FOCUSED)
                title = (child.name or "").casefold()
                title_matches = not expected_title or title in expected_title or expected_title in title
                if active and title_matches:
                    walk(child, app_name, child.name or "")
        except Exception:
            continue

candidates = focused or editable
print(json.dumps(candidates[0] if candidates else None, ensure_ascii=False))
"""


_ATSPI_BROWSER_LOCATION_SCRIPT = r"""
import json
import sys
import pyatspi

expected_title = sys.argv[1].casefold().strip()
candidates = []

def has_state(obj, state):
    try:
        return obj.getState().contains(state)
    except Exception:
        return False

def attributes(obj):
    try:
        return {
            item.split(":", 1)[0].casefold(): item.split(":", 1)[1]
            for item in obj.getAttributes()
            if ":" in item
        }
    except Exception:
        return {}

def walk(
    obj,
    app_name,
    frame_name,
    inside_document=False,
    inside_toolbar=False,
    depth=0,
):
    if depth > 16:
        return
    try:
        role = obj.getRoleName().casefold()
        now_inside_document = inside_document or role.startswith("document")
        now_inside_toolbar = inside_toolbar or role in {"tool bar", "toolbar"}
        if role == "entry" and not now_inside_document:
            attrs = attributes(obj)
            marker = " ".join(
                (
                    obj.name or "",
                    attrs.get("class", ""),
                    attrs.get("id", ""),
                )
            ).casefold()
            strong_markers = (
                "omnibox",
                "urlbar",
                "locationbar",
            )
            address_markers = (
                "address",
                "endereço",
                "endereços",
                "adresse",
                "dirección",
                "indirizzo",
            )
            if any(item in marker for item in strong_markers) or (
                now_inside_toolbar
                and any(item in marker for item in address_markers)
            ):
                try:
                    text = obj.queryText()
                    location = text.getText(0, text.characterCount).strip()
                    if location:
                        candidates.append(
                            {
                                "location": location,
                                "app": app_name,
                                "frame": frame_name,
                                "role": role,
                            }
                        )
                except Exception:
                    pass
        for child in obj:
            walk(
                child,
                app_name,
                frame_name,
                inside_document=now_inside_document,
                inside_toolbar=now_inside_toolbar,
                depth=depth + 1,
            )
    except Exception:
        return

for desktop_index in range(pyatspi.Registry.getDesktopCount()):
    desktop = pyatspi.Registry.getDesktop(desktop_index)
    for app in desktop:
        try:
            app_name = app.name or ""
            for child in app:
                title = (child.name or "").casefold()
                title_matches = bool(
                    expected_title
                    and (title in expected_title or expected_title in title)
                )
                active = has_state(child, pyatspi.STATE_ACTIVE) or has_state(
                    child, pyatspi.STATE_FOCUSED
                )
                if title_matches and active:
                    walk(child, app_name, child.name or "")
        except Exception:
            continue

print(json.dumps(candidates[0] if candidates else None, ensure_ascii=False))
"""


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

    def read_active_text(self, *, max_chars: int = 4096) -> dict[str, Any]: ...

    def observe_application(
        self,
        app_id: str,
        *,
        pid: int | None = None,
        expected_argument: str | None = None,
    ) -> dict[str, Any]: ...


class PyAutoGuiDesktopBackend:
    """Desktop Linux backend.

    PyAutoGUI is imported lazily so CI and server-only processes do not require
    an active graphical display merely to import the package.
    """

    def __init__(
        self,
        *,
        pause_seconds: float = 0.05,
        app_ready_timeout_seconds: float = 6.0,
        failsafe_margin_pixels: int = 20,
        input_guard: Callable[[], None] | None = None,
    ) -> None:
        if failsafe_margin_pixels < 1:
            raise ValueError("failsafe_margin_pixels deve ser pelo menos 1.")
        self.pause_seconds = pause_seconds
        self.app_ready_timeout_seconds = app_ready_timeout_seconds
        self.failsafe_margin_pixels = failsafe_margin_pixels
        self._gui: Any | None = None
        self._expected_window_id: str | None = None
        self._focus_guard_error: str | None = None
        self._input_guard = input_guard

    def set_input_guard(self, guard: Callable[[], None] | None) -> None:
        self._input_guard = guard

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

    @staticmethod
    def _process_executable(pid: int | None) -> str | None:
        if not isinstance(pid, int) or pid <= 0:
            return None
        try:
            return str((Path("/proc") / str(pid) / "exe").resolve(strict=True))
        except OSError:
            return None

    def _window_process_id(self, window_id: str | None) -> int | None:
        xprop = shutil.which("xprop")
        if not xprop or not window_id:
            return None
        completed = subprocess.run(
            [xprop, "-id", window_id, "_NET_WM_PID"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if completed.returncode != 0:
            return None
        match = re.search(r"=\s*(\d+)\s*$", completed.stdout)
        return int(match.group(1)) if match else None

    def _window_class(self, window_id: str | None = None) -> str | None:
        xprop = shutil.which("xprop")
        active_id = window_id or self._active_window_id()
        if not xprop or not active_id:
            return None
        completed = subprocess.run(
            [xprop, "-id", active_id, "WM_CLASS"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if completed.returncode != 0:
            return None
        values = [
            item
            for item in re.findall(r'"([^"]+)"', completed.stdout)
            if item.strip()
        ]
        return " ".join(values) or None

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
        if self._expected_window_id:
            if self._xdotool_path() and current is None:
                raise RuntimeError(
                    "A janela ativa deixou de ser observável. O Robô recusou "
                    "enviar teclado para não falhar aberto na proteção de foco."
                )
            if current and current != self._expected_window_id:
                raise RuntimeError(
                    "O foco mudou para outra janela desde a última ação preparada. "
                    "O Robô recusou enviar teclado para evitar digitar no lugar errado."
                )
        return current, self._window_title(current)

    @staticmethod
    def _xclip_path() -> str | None:
        return shutil.which("xclip")

    def _read_clipboard(self) -> str | None:
        xclip = self._xclip_path()
        if not xclip:
            return None
        completed = subprocess.run(
            [xclip, "-selection", "clipboard", "-out"],
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=2,
        )
        if completed.returncode != 0:
            return None
        return completed.stdout

    def _write_clipboard(self, value: str) -> bool:
        xclip = self._xclip_path()
        if not xclip:
            return False
        completed = subprocess.run(
            [xclip, "-selection", "clipboard", "-in"],
            input=value,
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        return completed.returncode == 0

    @staticmethod
    def _type_text_with_unicode(
        gui: Any,
        text: str,
        *,
        before_input: Callable[[], None] | None = None,
    ) -> str:
        """Type printable text while preserving Unicode on Linux/X11.

        PyAutoGUI's write() handles ordinary keyboard characters well but can
        silently lose characters such as á/ç. Non-ASCII code points therefore use
        Linux Unicode input (Ctrl+Shift+U, hexadecimal code point, Enter). ASCII
        chunks still use write() for speed and predictable keyboard behavior.
        """

        ascii_buffer: list[str] = []
        used_unicode = False

        def flush_ascii() -> None:
            while ascii_buffer:
                chunk = "".join(ascii_buffer[:32])
                del ascii_buffer[:32]
                if before_input is not None:
                    before_input()
                gui.write(chunk, interval=0.01)

        for char in text:
            if ord(char) < 128:
                ascii_buffer.append(char)
                continue

            flush_ascii()
            if before_input is not None:
                before_input()
            gui.hotkey("ctrl", "shift", "u")
            if before_input is not None:
                before_input()
            gui.write(f"{ord(char):x}", interval=0.01)
            if before_input is not None:
                before_input()
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

        def guard_each_chunk() -> None:
            if self._input_guard is not None:
                self._input_guard()
            self._assert_pointer_outside_failsafe_zone(gui)
            self._focused_window_for_input()

        input_method = self._type_text_with_unicode(
            gui,
            text,
            before_input=guard_each_chunk,
        )
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

    def read_active_text(self, *, max_chars: int = 4096) -> dict[str, Any]:
        """Read the active editable surface without treating typing as proof.

        AT-SPI exposes the focused editable object's text without selecting
        content, sending keys or touching the user's clipboard.  The system
        Python is used because Linux desktop accessibility bindings are supplied
        by the OS rather than the project's isolated virtual environment.
        """

        if max_chars < 1:
            raise ValueError("max_chars deve ser positivo.")

        window_id, window_title = self._focused_window_for_input()
        system_python = Path("/usr/bin/python3")
        if not system_python.is_file():
            return {
                "action": "read_active_text",
                "window_id": window_id,
                "window_title": window_title,
                "text": None,
                "characters": 0,
                "source": "at-spi",
                "clipboard_untouched": True,
                "verified": False,
                "error": "Python do sistema indisponível para leitura AT-SPI",
            }

        try:
            completed = subprocess.run(
                [str(system_python), "-c", _ATSPI_READ_SCRIPT, window_title or ""],
                check=False,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=8,
            )
            lines = [line for line in completed.stdout.splitlines() if line.strip()]
            observed = json.loads(lines[-1]) if completed.returncode == 0 and lines else None
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            return {
                "action": "read_active_text",
                "window_id": window_id,
                "window_title": window_title,
                "text": None,
                "characters": 0,
                "source": "at-spi",
                "clipboard_untouched": True,
                "verified": False,
                "error": f"{type(exc).__name__}: {exc}",
            }

        current_window_id = self._active_window_id()
        same_focus = (
            True
            if not self._xdotool_path()
            else bool(window_id and current_window_id == window_id)
        )
        text_value = observed.get("text") if isinstance(observed, dict) else None
        verified = isinstance(text_value, str) and same_focus

        return {
            "action": "read_active_text",
            "window_id": window_id,
            "window_title": window_title,
            "observed_window_id": current_window_id,
            "text": text_value[:max_chars] if isinstance(text_value, str) else None,
            "characters": len(text_value) if isinstance(text_value, str) else 0,
            "truncated": bool(isinstance(text_value, str) and len(text_value) > max_chars),
            "source": "at-spi",
            "observation_method": "accessibility-text-interface",
            "accessibility_app": observed.get("app") if isinstance(observed, dict) else None,
            "accessibility_frame": observed.get("frame") if isinstance(observed, dict) else None,
            "clipboard_untouched": True,
            "clipboard_restored": True,
            "verified": verified,
            "error": None if verified else "nenhum texto editável focado foi observado via AT-SPI",
        }

    def observe_application(
        self,
        app_id: str,
        *,
        pid: int | None = None,
        expected_argument: str | None = None,
    ) -> dict[str, Any]:
        """Independently observe a launched application through X11 and /proc."""

        window_id = self._active_window_id()
        window_title = self._window_title(window_id)
        window_class = self._window_class(window_id)
        process_alive = False
        process_executable: str | None = None
        argument_observed: bool | None = None

        if isinstance(pid, int) and pid > 0:
            process_dir = Path("/proc") / str(pid)
            process_alive = process_dir.exists()
            if process_alive:
                process_executable = self._process_executable(pid)
                if expected_argument is not None:
                    try:
                        raw_cmdline = (process_dir / "cmdline").read_bytes()
                        argv = [
                            item.decode("utf-8", errors="replace")
                            for item in raw_cmdline.split(b"\0")
                            if item
                        ]
                    except OSError:
                        argv = []
                    argument_observed = expected_argument in argv

        canonical = canonical_app_id(app_id.split(maxsplit=1)[0])
        identity_hints: dict[str, tuple[str, ...]] = {
            "editor": ("xed", "gedit", "text editor", "editor"),
            "vscode": ("visual studio code", "code", "vscode"),
            "calculadora": ("calculator", "calculadora", "mate-calc", "kcalc"),
            "brave-browser": ("brave",),
            "firefox": ("firefox",),
            "chromium": ("chromium", "chrome"),
        }
        hints = identity_hints.get(canonical, (canonical,))
        exact_identities: dict[str, tuple[str, ...]] = {
            "editor": ("xed", "gedit", "pluma", "mousepad"),
            "vscode": ("code", "code-oss", "vscode"),
            "calculadora": (
                "calculator",
                "gnome-calculator",
                "mate-calc",
                "kcalc",
            ),
            "brave-browser": ("brave", "brave-browser", "brave-browser-stable"),
            "firefox": ("firefox",),
            "chromium": (
                "chrome",
                "chromium",
                "google-chrome",
                "google-chrome-stable",
            ),
            "google-chrome": (
                "chrome",
                "chromium",
                "google-chrome",
                "google-chrome-stable",
            ),
            "google-chrome-stable": (
                "chrome",
                "chromium",
                "google-chrome",
                "google-chrome-stable",
            ),
        }
        expected_identities = set(exact_identities.get(canonical, (canonical,)))
        raw_class = (window_class or "").casefold()
        class_tokens = set(
            re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", raw_class)
        )
        # Preserve complete StartupWMClass/desktop-id atoms (including dots)
        # while also supporting conventional two-token WM_CLASS values.
        class_tokens.update(
            item.strip('"\' ,')
            for item in raw_class.split()
            if item.strip('"\' ,')
        )
        process_name = Path(process_executable).name.casefold() if process_executable else ""
        title_identity = (window_title or "").casefold()
        class_observed = bool(class_tokens.intersection(expected_identities))
        process_observed = process_name in expected_identities
        title_observed = any(hint and hint in title_identity for hint in hints)
        # Completion requires the active X11 window itself to identify the app.
        # A target process plus an unrelated active window must never be merged
        # into one synthetic observation, and page/window titles are spoofable.
        identity_observed = bool(window_id and class_observed)

        browser_location: str | None = None
        browser_location_source: str | None = None
        browser_location_verified = False
        browser_location_app: str | None = None
        browser_location_frame: str | None = None
        window_process_id: int | None = None
        window_process_executable: str | None = None
        window_process_identity_observed = False
        if (
            identity_observed
            and expected_argument
            and canonical
            in {
                "brave-browser",
                "firefox",
                "chromium",
                "chrome",
                "google-chrome",
                "google-chrome-stable",
            }
        ):
            window_process_id = self._window_process_id(window_id)
            window_process_executable = self._process_executable(window_process_id)
            window_process_identity_observed = bool(
                window_process_executable
                and Path(window_process_executable).name.casefold()
                in expected_identities
            )
            location_observation = self._observe_browser_location(window_title)
            location_value = location_observation.get("location")
            location_app = location_observation.get("app")
            location_frame = location_observation.get("frame")
            same_window = self._active_window_id() == window_id
            frame_matches = bool(
                isinstance(location_frame, str)
                and window_title
                and (
                    location_frame.casefold() in window_title.casefold()
                    or window_title.casefold() in location_frame.casefold()
                )
            )
            if (
                isinstance(location_value, str)
                and location_value.strip()
                and same_window
                and frame_matches
            ):
                browser_location = location_value.strip()
                browser_location_source = "at-spi"
                browser_location_verified = True
                browser_location_app = (
                    location_app if isinstance(location_app, str) else None
                )
                browser_location_frame = location_frame

        return {
            "action": "observe_application",
            "app": canonical,
            "window_id": window_id,
            "window_title": window_title,
            "window_class": window_class,
            "process_alive": process_alive,
            "process_executable": process_executable,
            "argument_observed": argument_observed,
            "identity_observed": identity_observed,
            "class_identity_observed": class_observed,
            "process_identity_observed": process_observed,
            "title_identity_observed": title_observed,
            "browser_location": browser_location,
            "browser_location_source": browser_location_source,
            "browser_location_verified": browser_location_verified,
            "browser_location_app": browser_location_app,
            "browser_location_frame": browser_location_frame,
            "window_process_id": window_process_id,
            "window_process_executable": window_process_executable,
            "window_process_identity_observed": window_process_identity_observed,
            "source": "x11-proc",
            "verified": identity_observed,
        }

    @staticmethod
    def _observe_browser_location(window_title: str | None) -> dict[str, Any]:
        """Read an active browser's address field without keyboard or clipboard use."""

        system_python = Path("/usr/bin/python3")
        if not window_title or not system_python.is_file():
            return {}
        try:
            completed = subprocess.run(
                [
                    str(system_python),
                    "-c",
                    _ATSPI_BROWSER_LOCATION_SCRIPT,
                    window_title,
                ],
                check=False,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=8,
            )
            lines = [line for line in completed.stdout.splitlines() if line.strip()]
            observed = json.loads(lines[-1]) if completed.returncode == 0 and lines else None
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            return {}
        return observed if isinstance(observed, dict) else {}

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
