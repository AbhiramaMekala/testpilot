import os
import sys
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE_URL = "https://www.saucedemo.com"


def pytest_addoption(parser):
    # dest= is set explicitly, and getoption() is called with that dest name.
    # pytest turns "--slow-mo" into the dest "slow_mo", but getoption("--slow_mo")
    # looks for an option literally spelled --slow_mo, which does not exist, and
    # raises ValueError at fixture setup - before the browser is ever launched.
    parser.addoption("--headed", action="store_true", dest="headed",
                     help="show the browser instead of running it hidden")
    parser.addoption("--slow-mo", action="store", type=int, default=0,
                     dest="slow_mo", metavar="MS",
                     help="pause this many milliseconds between actions so a "
                          "human can follow along. 0 for CI.")


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def browser(request):
    """Hidden and instant by default, which is what CI wants.

    --headed --slow-mo 700 makes every click and keystroke visible, which is
    what a person watching a demo wants. Same tests either way; only the
    launch options change.
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=not request.config.getoption("headed"),
            slow_mo=request.config.getoption("slow_mo"),
        )
        yield browser
        browser.close()


@pytest.fixture
def page(browser, request):
    """A fresh browser context per test - no cookies, no cart carried over.
    Shared state between UI tests is the main cause of flaky suites."""
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    # Two different budgets, because they are two different waits.
    #
    # Finding an element on a page that has already loaded should take
    # milliseconds, so a short timeout here makes a genuine failure fail fast.
    # Playwright's 30s default means nine failures cost four and a half
    # minutes of waiting for things that are never going to appear.
    #
    # Fetching a page over the internet is a different matter - it depends on
    # someone else's server and the user's connection. Holding navigation to
    # the same tight budget produces timeouts that say nothing about the
    # product, which is exactly the noise this suite is meant to avoid.
    page.set_default_timeout(int(os.environ.get("PW_TIMEOUT_MS", "8000")))
    page.set_default_navigation_timeout(int(os.environ.get("PW_NAV_TIMEOUT_MS", "20000")))
    yield page
    failed = getattr(request.node, "rep_call", None)
    if failed is not None and failed.failed:
        shot = ROOT / "screenshots" / f"FAILED-{request.node.name}.png"
        shot.parent.mkdir(exist_ok=True)
        page.screenshot(path=str(shot), full_page=True)
    context.close()


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    """Attach the result to the item so the page fixture can screenshot failures."""
    outcome = yield
    setattr(item, f"rep_{call.when}", outcome.get_result())
