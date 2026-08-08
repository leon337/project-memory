from __future__ import annotations

from typing import Any

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from .policy import Plan


class ActionExecutor:
    def __init__(self, *, headless: bool = False) -> None:
        self.headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    def start(self) -> None:
        if self._playwright is not None:
            return
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
        self.start()
        if plan.action == "open_url":
            return self._open_url(plan.target)
        raise RuntimeError(f"Ação não implementada: {plan.action}")

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
