from __future__ import annotations

import re
import time
from typing import Any

from .desktop import PyAutoGuiDesktopBackend, canonical_app_id


_KNOWN_WINDOW_IDENTITIES: dict[str, frozenset[str]] = {
    "editor": frozenset({"xed", "gedit", "pluma", "mousepad"}),
    "vscode": frozenset({"code", "code-oss", "vscode"}),
    "calculadora": frozenset(
        {"calculator", "gnome-calculator", "mate-calc", "kcalc"}
    ),
    "brave-browser": frozenset(
        {"brave", "brave-browser", "brave-browser-stable"}
    ),
    "firefox": frozenset({"firefox"}),
    "chromium": frozenset(
        {"chrome", "chromium", "google-chrome", "google-chrome-stable"}
    ),
    "google-chrome": frozenset(
        {"chrome", "chromium", "google-chrome", "google-chrome-stable"}
    ),
    "google-chrome-stable": frozenset(
        {"chrome", "chromium", "google-chrome", "google-chrome-stable"}
    ),
}


class StableFocusDesktopBackend(PyAutoGuiDesktopBackend):
    """Desktop backend that prepares keyboard focus only after X11 settles.

    Application startup can briefly activate more than one X11 window. The base
    backend intentionally fails closed if the active window changes after
    preparation; this subclass keeps that invariant, but delays preparation until
    the final application window has remained stable for a short interval.

    For applications with known WM_CLASS identities, unrelated transient windows
    are ignored instead of being accepted as the keyboard target. Unknown
    applications retain the previous generic behavior, but still need a stable new
    window before keyboard input is armed.
    """

    def __init__(
        self,
        *,
        focus_settle_seconds: float = 0.40,
        focus_poll_seconds: float = 0.05,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if focus_settle_seconds < 0:
            raise ValueError("focus_settle_seconds não pode ser negativo.")
        if focus_poll_seconds < 0:
            raise ValueError("focus_poll_seconds não pode ser negativo.")
        self.focus_settle_seconds = focus_settle_seconds
        self.focus_poll_seconds = focus_poll_seconds
        self._launch_app_id: str | None = None
        self._last_focus_readiness: dict[str, Any] = {}

    @staticmethod
    def _window_class_tokens(raw_class: str | None) -> set[str]:
        normalized = (raw_class or "").casefold()
        tokens = set(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized))
        tokens.update(
            item.strip('"\' ,')
            for item in normalized.split()
            if item.strip('"\' ,')
        )
        return tokens

    def _window_identity_matches_launch_app(self, window_id: str | None) -> bool | None:
        canonical = self._launch_app_id
        if not canonical or not window_id:
            return None
        expected = _KNOWN_WINDOW_IDENTITIES.get(canonical)
        if expected is None:
            # Generic commands remain usable. Their safety boundary is a stable
            # new X11 window plus the unchanged per-chunk focus guard.
            return None
        return bool(self._window_class_tokens(self._window_class(window_id)) & expected)

    def _trace_event(self, window_id: str | None) -> dict[str, Any]:
        return {
            "window_id": window_id,
            "window_title": self._window_title(window_id),
            "window_class": self._window_class(window_id),
            "app_identity_verified": self._window_identity_matches_launch_app(window_id),
        }

    def _wait_for_active_window_change(
        self,
        previous_window_id: str | None,
    ) -> dict[str, Any]:
        if not self._xdotool_path():
            result = super()._wait_for_active_window_change(previous_window_id)
            result.update(
                {
                    "window_class": self._window_class(result.get("window_id")),
                    "app_identity_verified": None,
                    "stable_for_seconds": None,
                    "focus_trace": [],
                }
            )
            self._last_focus_readiness = result
            return result

        deadline = time.monotonic() + self.app_ready_timeout_seconds
        candidate_id: str | None = None
        candidate_since: float | None = None
        current: str | None = previous_window_id
        trace: list[dict[str, Any]] = []
        last_traced_window: str | None = previous_window_id

        while time.monotonic() < deadline:
            current = self._active_window_id()
            now = time.monotonic()

            if current != last_traced_window:
                trace.append(self._trace_event(current))
                if len(trace) > 16:
                    trace.pop(0)
                last_traced_window = current

            new_target = bool(current) and (
                previous_window_id is None or current != previous_window_id
            )
            if new_target:
                identity_verified = self._window_identity_matches_launch_app(current)
                if identity_verified is False:
                    candidate_id = None
                    candidate_since = None
                elif current != candidate_id:
                    candidate_id = current
                    candidate_since = now
                elif candidate_since is not None:
                    stable_for = max(0.0, now - candidate_since)
                    if stable_for >= self.focus_settle_seconds:
                        result = {
                            "window_changed": True,
                            "window_id": current,
                            "window_title": self._window_title(current),
                            "window_class": self._window_class(current),
                            "app_identity_verified": identity_verified,
                            "stable_for_seconds": stable_for,
                            "focus_trace": trace,
                        }
                        self._last_focus_readiness = result
                        return result
            else:
                candidate_id = None
                candidate_since = None

            time.sleep(self.focus_poll_seconds)

        result = {
            "window_changed": False,
            "window_id": current,
            "window_title": self._window_title(current),
            "window_class": self._window_class(current),
            "app_identity_verified": self._window_identity_matches_launch_app(current),
            "stable_for_seconds": None,
            "focus_trace": trace,
        }
        self._last_focus_readiness = result
        return result

    def open_application(self, app_id: str) -> dict[str, Any]:
        self._launch_app_id = canonical_app_id(app_id)
        self._last_focus_readiness = {}
        try:
            result = super().open_application(app_id)
            readiness = self._last_focus_readiness
            if readiness:
                result.update(
                    {
                        "window_class": readiness.get("window_class"),
                        "app_identity_verified": readiness.get("app_identity_verified"),
                        "focus_stable_for_seconds": readiness.get("stable_for_seconds"),
                        "focus_trace": readiness.get("focus_trace", []),
                    }
                )
            return result
        finally:
            self._launch_app_id = None
