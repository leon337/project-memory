from __future__ import annotations

from pathlib import Path
from time import time_ns
from typing import Any

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from .desktop import DesktopBackend, PyAutoGuiDesktopBackend
from .emergency_stop import EmergencyStop
from .policy import Plan


_BROWSER_SNAPSHOT_SCRIPT = r"""
([maxTextChars, maxLinks, maxResults]) => {
  const compact = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const isVisible = (element) => {
    if (!element || element.hidden || element.getAttribute("aria-hidden") === "true") {
      return false;
    }
    for (let current = element; current; current = current.parentElement) {
      if (current.hidden || current.getAttribute("aria-hidden") === "true") return false;
      const style = window.getComputedStyle(current);
      if (style.display === "none" || style.visibility === "hidden" || style.visibility === "collapse") {
        return false;
      }
    }
    return element.getClientRects().length > 0;
  };
  const isAdvertisement = (element) => {
    const container = element.closest([
      "[data-text-ad]",
      "[data-ad]",
      "[data-testid*='ad']",
      "[aria-label*='Sponsored' i]",
      "[aria-label*='Patrocinado' i]",
      "[aria-label*='Anúncio' i]",
      ".ads-ad",
      ".ad",
      ".b_ad",
      ".result--ad",
      ".sponsored",
      ".commercial-unit-desktop-top"
    ].join(","));
    if (container) return true;
    const surroundingText = compact(element.closest("article, li, .result, .g")?.innerText);
    return /^(sponsored|patrocinado|anúncio|ad)\b/i.test(surroundingText);
  };
  const navigationLabels = new Set([
    "all", "tudo", "images", "imagens", "videos", "vídeos", "news", "notícias",
    "maps", "mapas", "shopping", "more", "mais", "next", "próxima", "previous",
    "anterior", "sign in", "login", "entrar", "settings", "configurações", "cached"
  ]);
  const isNavigation = (anchor, text, rawHref) => {
    if (anchor.closest("nav, header, footer, [role='navigation']")) return true;
    if (!rawHref || /^(#|javascript:|mailto:|tel:)/i.test(rawHref)) return true;
    return navigationLabels.has(text.toLocaleLowerCase());
  };
  const decodeBingRedirect = (url) => {
    if (!/(^|\.)bing\.com$/i.test(url.hostname) || url.pathname !== "/ck/a") return null;
    const encoded = url.searchParams.get("u");
    if (!encoded || !encoded.startsWith("a1")) return null;
    try {
      const base64 = encoded.slice(2).replace(/-/g, "+").replace(/_/g, "/");
      const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
      return decodeURIComponent(Array.from(atob(padded), c =>
        "%" + c.charCodeAt(0).toString(16).padStart(2, "0")
      ).join(""));
    } catch (_) {
      return null;
    }
  };
  const normalizedUrl = (anchor) => {
    const raw = anchor.getAttribute("href") || "";
    try {
      const url = new URL(raw, document.baseURI);
      if (/(^|\.)google\.[a-z.]+$/i.test(url.hostname) && url.pathname === "/url") {
        return url.searchParams.get("q") || url.searchParams.get("url") || url.href;
      }
      if (/(^|\.)duckduckgo\.com$/i.test(url.hostname) && url.pathname.startsWith("/l/")) {
        return url.searchParams.get("uddg") || url.href;
      }
      return decodeBingRedirect(url) || url.href;
    } catch (_) {
      return raw;
    }
  };
  const usefulRoot = document.querySelector(
    "main, [role='main'], #search, #content, #main, .results, article"
  ) || document.body || document.documentElement;
  const rootText = compact(usefulRoot.innerText || usefulRoot.textContent).slice(0, maxTextChars);

  const headings = Array.from(document.querySelectorAll("h1, h2, h3"))
    .filter(element =>
      isVisible(element) &&
      !isAdvertisement(element) &&
      !element.closest("nav, header, footer, [role='navigation']")
    )
    .map(element => ({
      level: Number(element.tagName.slice(1)),
      text: compact(element.innerText || element.textContent)
    }))
    .filter(item => item.text)
    .slice(0, 30);

  const links = [];
  const seenLinks = new Set();
  for (const anchor of usefulRoot.querySelectorAll("a[href]")) {
    const text = compact(anchor.innerText || anchor.textContent || anchor.getAttribute("aria-label"));
    const rawHref = anchor.getAttribute("href") || "";
    if (!text || !isVisible(anchor) || isAdvertisement(anchor) || isNavigation(anchor, text, rawHref)) {
      continue;
    }
    const url = normalizedUrl(anchor);
    if (!url || seenLinks.has(url)) continue;
    seenLinks.add(url);
    links.push({text, url});
    if (links.length >= maxLinks) break;
  }

  // RSS/Atom search feeds are already structured result documents. Their
  // item nodes do not have HTML layout boxes, so treat them as data only when
  // the document root itself proves that this is a feed.
  const feedResults = [];
  const feedRoot = document.querySelector(
    "#webkit-xml-viewer-source-xml > rss, #webkit-xml-viewer-source-xml > feed, rss, feed"
  );
  const documentKind = String(feedRoot?.localName || "").toLocaleLowerCase();
  const feedContentType = /(?:rss\+xml|atom\+xml|application\/xml|text\/xml)/i.test(
    String(document.contentType || "")
  );
  if (feedRoot && feedContentType && (documentKind === "rss" || documentKind === "feed")) {
    const feedItems = documentKind === "rss"
      ? feedRoot.querySelectorAll("channel > item")
      : feedRoot.querySelectorAll("entry");
    for (const item of feedItems) {
      const title = compact(item.querySelector("title")?.textContent);
      const itemLinks = Array.from(item.querySelectorAll("link"));
      const link = documentKind === "rss"
        ? itemLinks[0]
        : itemLinks.find(candidate => compact(candidate.getAttribute("rel")).toLocaleLowerCase() === "alternate")
          || itemLinks.find(candidate => !compact(candidate.getAttribute("rel")));
      const url = compact(link?.getAttribute("href") || link?.textContent);
      if (!title || !/^https?:\/\//i.test(url)) continue;
      feedResults.push({title, url});
      if (feedResults.length >= maxResults) break;
    }
  }

  const resultSelectors = [
    "#search a:has(h3)",
    "div.g a:has(h3)",
    "a[data-testid='result-title-a']",
    "article[data-testid='result'] h2 a",
    ".result__title a",
    "a.result__a",
    "li.b_algo h2 a",
    ".search-result h2 a",
    ".search-result h3 a",
    ".result h2 a",
    ".result h3 a",
    "main article h2 a",
    "main article h3 a",
    "[role='main'] article h2 a",
    "[role='main'] article h3 a"
  ];
  const candidates = [];
  const seenElements = new Set();
  for (const selector of resultSelectors) {
    for (const anchor of document.querySelectorAll(selector)) {
      if (!seenElements.has(anchor)) {
        seenElements.add(anchor);
        candidates.push(anchor);
      }
    }
  }
  // Selector groups above encode relevance, but document order defines what is first.
  candidates.sort((left, right) => {
    if (left === right) return 0;
    const position = left.compareDocumentPosition(right);
    return position & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
  });

  const searchResults = [...feedResults];
  const seenResults = new Set(feedResults.map(item => item.url));
  for (const anchor of candidates) {
    const heading = anchor.querySelector("h1, h2, h3") || anchor.closest("h1, h2, h3");
    const title = compact(
      heading?.innerText || heading?.textContent || anchor.innerText || anchor.textContent
    );
    const rawHref = anchor.getAttribute("href") || "";
    if (!title || !isVisible(anchor) || isAdvertisement(anchor) || isNavigation(anchor, title, rawHref)) {
      continue;
    }
    const url = normalizedUrl(anchor);
    if (!url || seenResults.has(url)) continue;
    seenResults.add(url);
    searchResults.push({title, url});
    if (searchResults.length >= maxResults) break;
  }

  return {
    title: compact(document.title),
    text: rootText,
    headings,
    links,
    search_results: searchResults
  };
}
"""


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
        self._document_statuses: dict[str, int] = {}

    def _check_stop(self) -> None:
        if self.emergency_stop is not None:
            self.emergency_stop.assert_not_triggered()

    def _desktop_backend(self) -> DesktopBackend:
        if not self.desktop_enabled:
            raise PermissionError("Controle de desktop está desativado localmente.")
        if self._desktop is None:
            self._desktop = PyAutoGuiDesktopBackend(input_guard=self._check_stop)
        else:
            set_input_guard = getattr(self._desktop, "set_input_guard", None)
            if callable(set_input_guard):
                set_input_guard(self._check_stop)
        return self._desktop

    def start(self) -> None:
        if self._playwright is not None:
            return
        self._check_stop()
        playwright: Playwright | None = None
        browser: Browser | None = None
        try:
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(headless=self.headless)
            page = browser.new_page()
            page.on("response", self._remember_document_status)
        except Exception:
            if browser is not None:
                browser.close()
            if playwright is not None:
                playwright.stop()
            self._playwright = None
            self._browser = None
            self._page = None
            raise
        self._playwright = playwright
        self._browser = browser
        self._page = page

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._page = None
        self._browser = None
        self._playwright = None
        self._document_statuses.clear()

    def _remember_document_status(self, response: Any) -> None:
        """Remember main-frame HTTP status without making navigation its evidence."""

        page = self._page
        if page is None:
            return
        try:
            if response.request.resource_type != "document" or response.frame != page.main_frame:
                return
            self._document_statuses[response.url] = response.status
            # A normal browsing session only needs a small recent status cache.
            while len(self._document_statuses) > 16:
                self._document_statuses.pop(next(iter(self._document_statuses)))
        except Exception:
            # A response can race with page/browser shutdown. Observation remains usable,
            # with an unknown status, in that case.
            return

    def observe_browser(
        self,
        *,
        max_text_chars: int = 4096,
        max_links: int = 25,
        max_results: int = 10,
    ) -> dict[str, Any]:
        """Observe the current Playwright page independently from an action receipt.

        The returned DOM snapshot is intentionally collected after navigation/action
        execution.  It can therefore be turned into evidence by the goal runtime
        without trusting an ``open_url`` receipt as proof of page contents.
        """

        if max_text_chars < 1 or max_links < 1 or max_results < 1:
            raise ValueError("Limites da observação do navegador devem ser positivos.")
        self._check_stop()
        page = self._page
        if page is None:
            raise RuntimeError("Navegador não inicializado.")

        page.wait_for_load_state("domcontentloaded", timeout=30_000)
        content = page.evaluate(
            _BROWSER_SNAPSHOT_SCRIPT,
            [max_text_chars, max_links, max_results],
        )
        current_url = page.url
        first_result = content["search_results"][0] if content["search_results"] else None
        snapshot = {
            "source": "browser",
            "observation_method": "playwright_dom",
            "url": current_url,
            "title": content["title"],
            "http_status": self._document_statuses.get(current_url),
            "text": content["text"],
            "headings": content["headings"],
            "links": content["links"],
            "search_results": content["search_results"],
            "first_result": first_result,
            "first_result_title": first_result["title"] if first_result else None,
            "first_result_url": first_result["url"] if first_result else None,
        }
        self._check_stop()
        return snapshot

    def observe_active_window(self) -> dict[str, Any]:
        """Observe the active desktop window outside the action receipt path."""

        self._check_stop()
        result = self._desktop_backend().active_window()
        self._check_stop()
        return result

    def read_active_text(self, *, max_chars: int = 4096) -> dict[str, Any]:
        """Read back the active editable surface through the desktop backend."""

        self._check_stop()
        result = self._desktop_backend().read_active_text(max_chars=max_chars)
        self._check_stop()
        return result

    def observe_application(
        self,
        app_id: str,
        *,
        pid: int | None = None,
        expected_argument: str | None = None,
    ) -> dict[str, Any]:
        """Observe application identity/process state outside its launch receipt."""

        self._check_stop()
        result = self._desktop_backend().observe_application(
            app_id,
            pid=pid,
            expected_argument=expected_argument,
        )
        self._check_stop()
        return result

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
        if response is not None:
            self._document_statuses[final_url] = response.status
        return {
            "action": "open_url",
            "requested_url": url,
            "final_url": final_url,
            "title": title,
            "http_status": response.status if response else None,
            "verified": bool(final_url),
        }
