from __future__ import annotations

from pathlib import Path
from time import time_ns
from typing import Any

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from .desktop import DesktopBackend, PyAutoGuiDesktopBackend
from .emergency_stop import EmergencyStop
from .policy import Plan


class ActionExecutor:
    def __init__(
        self,
        *,
        headless: bool = False,
        desktop_enabled: bool = False,
        desktop_backend: DesktopBackend | None = None,
        screenshot_dir: Path = Path("runtime/screenshots"),
        emergency_stop: EmergencyStop | None = None,
    ) -> None:
        self.headless = headless
        self.desktop_enabled = desktop_enabled
        self.screenshot_dir = Path(screenshot_dir)
        self.emergency_stop = emergency_stop
        self._desktop = desktop_backend
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    def _check_stop(self) -> None:
        if self.emergency_stop is not None:
            self.emergency_stop.assert_not_triggered()

    def _desktop_backend(self) -> DesktopBackend:
        if not self.desktop_enabled:
            raise PermissionError("Controle de desktop está desativado localmente.")
        if self._desktop is None:
            self._desktop = PyAutoGuiDesktopBackend()
        return self._desktop

    def start(self) -> None:
        if self._playwright is not None:
            return
        self._check_stop()
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self._page = self._browser.new_page()

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._page = None
        self._browser = None
        self._playwright = None

    def execute(self, plan: Plan) -> dict[str, Any]:
        self._check_stop()

        if plan.action == "open_url":
            self.start()
            result = self._open_url(plan.target)
        elif plan.action == "capture_screen":
            path = self.screenshot_dir / f"screen-{time_ns()}.png"
            result = self._desktop_backend().capture_screen(path)
        elif plan.action == "active_window":
            result = self._desktop_backend().active_window()
        elif plan.action == "move_mouse":
            x, y = (int(part) for part in plan.target.split(",", maxsplit=1))
            result = self._desktop_backend().move_mouse(x, y)
        elif plan.action == "click_mouse":
            result = self._desktop_backend().click_mouse(plan.target)
        elif plan.action == "type_text":
            result = self._desktop_backend().type_text(plan.target)
        elif plan.action == "press_key":
            key = "esc" if plan.target == "escape" else plan.target
            result = self._desktop_backend().press_key(key)
        elif plan.action == "open_app":
            result = self._desktop_backend().open_application(plan.target)
        else:
            raise RuntimeError(f"Ação não implementada: {plan.action}")

        self._check_stop()
        return result

    def _open_url(self, url: str) -> dict[str, Any]:
        if self._page is None:
            raise RuntimeError("Navegador não inicializado.")
        response = self._page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        final_url = self._page.url
        title = self._page.title()
        return {
            "action": "open_url",
            "requested_url": url,
            "final_url": final_url,
            "title": title,
            "http_status": response.status if response else None,
            "verified": bool(final_url),
        }
