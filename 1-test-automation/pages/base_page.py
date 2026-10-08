"""Page Object Model base class.

Every page of the application gets one class. Tests call methods on those
classes and never touch a CSS selector, so when the UI changes you edit one
page object instead of every test that walks through that screen.
"""
from __future__ import annotations

from playwright.sync_api import Page, TimeoutError as PWTimeout


class BasePage:
    url_path = "/"

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url.rstrip("/")

    def open(self) -> "BasePage":
        self.page.goto(self.base_url + self.url_path, wait_until="domcontentloaded")
        return self

    def fill(self, selector: str, value: str) -> None:
        self.page.fill(selector, value)

    def click(self, selector: str) -> None:
        self.page.click(selector)

    def text_of(self, selector: str, timeout: int = 4000) -> str:
        try:
            return (self.page.text_content(selector, timeout=timeout) or "").strip()
        except PWTimeout:
            return ""

    def is_visible(self, selector: str, timeout: int = 2000) -> bool:
        try:
            self.page.wait_for_selector(selector, timeout=timeout, state="visible")
            return True
        except PWTimeout:
            return False

    def count(self, selector: str) -> int:
        return self.page.locator(selector).count()

    def wait_for(self, selector: str, timeout: int | None = None) -> bool:
        """Block until the element exists, or give up.

        Localhost answers in microseconds, so a suite written against a local
        fixture can read the DOM before the next page has rendered and still
        pass every time. Point it at a real site over a real network and the
        same code finds an empty page. Never assume navigation is instant.
        """
        try:
            self.page.wait_for_selector(selector, timeout=timeout, state="attached")
            return True
        except PWTimeout:
            return False

    def missing(self, selector: str) -> str:
        """A failure message that explains itself without opening the code."""
        return (f"nothing on the page matched {selector!r}. The element is gone "
                f"or renamed - check the selector in the page object before "
                f"assuming the application is broken.")

    def screenshot(self, path: str) -> None:
        self.page.screenshot(path=path, full_page=True)
