"""
Requirements document -> executable Playwright tests.

The important word is *executable*. Generating prose that looks like a test is
easy and worth nothing; the generated file has to import, run, and either pass
or fail for a real reason.

So generation is constrained. The model does not write free-form Python - it
picks an action from a fixed vocabulary that maps onto the page objects in
1-test-automation, and fills in the data. Free-form code generation produces
something that does not compile perhaps one time in five, and a test suite that
will not import is worse than no suite at all.

With no API key the same vocabulary is driven by keyword rules, so the tool
still produces runnable tests offline and in CI.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from . import llm

REQ_LINE = re.compile(r"^\s*(?P<id>REQ-[A-Z]+-\d+)\s*:\s*(?P<text>.+?)\s*$", re.M)

# The vocabulary. Each action is a template that expands into real test code.
ACTIONS = {
    "login_valid":        "a successful login reaching the inventory page",
    "login_bad_password": "a login with the wrong password being refused",
    "login_empty_field":  "a login with a blank username or password being refused",
    "login_locked_out":   "a locked-out account being told it is locked",
    "cart_add":           "adding a product and checking the cart badge",
    "cart_contents":      "checking the cart holds the product that was added",
    "checkout_success":   "a complete purchase reaching the confirmation",
    "checkout_missing":   "checkout being refused when a required field is blank",
}

TEMPLATES = {
    "login_valid": '''
@pytest.mark.{marker}
@pytest.mark.requirement("{req}")
def test_{slug}(page, base_url):
    """{text}"""
    login = LoginPage(page, base_url).open()
    login.login("standard_user", "secret_sauce")
    assert login.is_logged_in(), f"expected the inventory page, got {{page.url}}"
    assert InventoryPage(page, base_url).wait_ready().item_count() > 0
''',
    "login_bad_password": '''
@pytest.mark.{marker}
@pytest.mark.requirement("{req}")
def test_{slug}(page, base_url):
    """{text}"""
    login = LoginPage(page, base_url).open()
    login.login("standard_user", "definitely_not_the_password")
    assert not login.is_logged_in(), "a wrong password got through"
    assert "do not match" in login.error_message(), login.error_message()
''',
    "login_empty_field": '''
@pytest.mark.{marker}
@pytest.mark.requirement("{req}")
def test_{slug}(page, base_url):
    """{text}"""
    login = LoginPage(page, base_url).open()
    login.login("", "secret_sauce")
    assert not login.is_logged_in(), "an empty username got through"
    assert "Username is required" in login.error_message(), login.error_message()
''',
    "login_locked_out": '''
@pytest.mark.{marker}
@pytest.mark.requirement("{req}")
def test_{slug}(page, base_url):
    """{text}"""
    login = LoginPage(page, base_url).open()
    login.login("locked_out_user", "secret_sauce")
    assert not login.is_logged_in()
    assert "locked out" in login.error_message().lower(), login.error_message()
''',
    "cart_add": '''
@pytest.mark.{marker}
@pytest.mark.requirement("{req}")
def test_{slug}(page, base_url):
    """{text}"""
    LoginPage(page, base_url).open().login("standard_user", "secret_sauce")
    inventory = InventoryPage(page, base_url).wait_ready()
    assert inventory.cart_badge_count() == 0
    inventory.add_first_item()
    assert inventory.cart_badge_count() == 1
''',
    "cart_contents": '''
@pytest.mark.{marker}
@pytest.mark.requirement("{req}")
def test_{slug}(page, base_url):
    """{text}"""
    LoginPage(page, base_url).open().login("standard_user", "secret_sauce")
    inventory = InventoryPage(page, base_url).wait_ready()
    added = inventory.add_item_by_index(1)
    inventory.go_to_cart()
    names = CartPage(page, base_url).item_names()
    assert added in names, f"added {{added!r}}, cart holds {{names}}"
''',
    "checkout_success": '''
@pytest.mark.{marker}
@pytest.mark.requirement("{req}")
def test_{slug}(page, base_url):
    """{text}"""
    LoginPage(page, base_url).open().login("standard_user", "secret_sauce")
    inventory = InventoryPage(page, base_url).wait_ready()
    inventory.add_first_item()
    inventory.go_to_cart()
    CartPage(page, base_url).start_checkout()
    checkout = CheckoutPage(page, base_url)
    assert checkout.complete_purchase("Abhi", "Mekala", "560064"), \\
        f"checkout stopped at {{page.url}}"
''',
    "checkout_missing": '''
@pytest.mark.{marker}
@pytest.mark.requirement("{req}")
def test_{slug}(page, base_url):
    """{text}"""
    LoginPage(page, base_url).open().login("standard_user", "secret_sauce")
    inventory = InventoryPage(page, base_url).wait_ready()
    inventory.add_first_item()
    inventory.go_to_cart()
    CartPage(page, base_url).start_checkout()
    checkout = CheckoutPage(page, base_url)
    checkout.fill_details("Abhi", "Mekala", "")
    assert not checkout.reached_summary(), "checkout accepted a blank postcode"
    assert "Postal Code is required" in checkout.error_message(), checkout.error_message()
''',
}

# Keyword rules for the offline path, grouped by the area in the requirement id.
#
# Scoping by area matters. A flat keyword list sent REQ-CHECKOUT-02 ("checkout
# shall be refused when the postcode is missing") to the login rule, because
# "refused" appeared in a login pattern first. The id already says which part
# of the product the requirement is about, so use it instead of hoping the
# wording disambiguates.
RULES = {
    "LOGIN": [
        (re.compile(r"locked[- ]out", re.I), "login_locked_out"),
        (re.compile(r"empty|blank|required", re.I), "login_empty_field"),
        (re.compile(r"incorrect|wrong password|refused", re.I), "login_bad_password"),
        (re.compile(r"valid credentials|reach the inventory", re.I), "login_valid"),
    ],
    "CART": [
        (re.compile(r"badge|increase", re.I), "cart_add"),
        (re.compile(r"shown in the cart|product that was added", re.I), "cart_contents"),
    ],
    "CHECKOUT": [
        (re.compile(r"missing|blank|refused|without", re.I), "checkout_missing"),
        (re.compile(r"confirmation|complete|supplies", re.I), "checkout_success"),
    ],
}


def _area(requirement_id: str) -> str:
    parts = requirement_id.split("-")
    return parts[1] if len(parts) > 2 else ""

SYSTEM = (
    "You map software requirements onto a fixed vocabulary of test actions. "
    "Reply with ONLY a JSON array of objects, each {\"requirement\": \"<the id "
    "given to you>\", \"action\": \"<one key from the vocabulary>\"}. Never "
    "invent a requirement id. Never invent an action name. One object per "
    "requirement."
)


@dataclass
class Generated:
    requirement: str
    action: str
    text: str
    source: str
    code: str = field(default="", repr=False)


def parse_requirements(document: str) -> dict[str, str]:
    return {m.group("id"): m.group("text").strip() for m in REQ_LINE.finditer(document)}


def _slug(req: str, action: str) -> str:
    return f"{req.lower().replace('-', '_')}_{action}"


def _marker(action: str) -> str:
    return "smoke" if action in ("login_valid", "cart_add", "checkout_success") else "regression"


def _render(req: str, action: str, text: str, source: str) -> Generated:
    code = TEMPLATES[action].format(
        marker=_marker(action), req=req, slug=_slug(req, action),
        text=text.rstrip("."))
    return Generated(req, action, text, source, code)


def by_rules(requirements: dict[str, str]) -> list[Generated]:
    out = []
    for req, text in requirements.items():
        for pattern, action in RULES.get(_area(req), []):
            if pattern.search(text):
                out.append(_render(req, action, text, "rule"))
                break
    return out


def by_model(requirements: dict[str, str]) -> list[Generated]:
    listing = "\n".join(f"{k}: {v}" for k, v in requirements.items())
    vocabulary = "\n".join(f"  {k}: {v}" for k, v in ACTIONS.items())
    raw = llm.complete_json(
        f"Vocabulary of available actions:\n{vocabulary}\n\n"
        f"Requirements:\n{listing}",
        system=SYSTEM, max_tokens=1500)
    out = []
    for item in raw if isinstance(raw, list) else []:
        req, action = item.get("requirement"), item.get("action")
        # Grounding: the model may not invent either side of the mapping.
        if req in requirements and action in TEMPLATES:
            out.append(_render(req, action, requirements[req], "llm"))
    return out


def generate(document: str) -> tuple[list[Generated], str, list[str]]:
    requirements = parse_requirements(document)
    if not requirements:
        return [], "none", ["no REQ-AREA-nn lines found in the document"]

    notes: list[str] = []
    if llm.available():
        try:
            cases = by_model(requirements)
            covered = {c.requirement for c in cases}
            gap = {k: v for k, v in requirements.items() if k not in covered}
            if gap:
                cases += by_rules(gap)
                notes.append(f"rules covered {len(gap)} requirement(s) the model skipped")
            if cases:
                return cases, "llm+rules", notes
            notes.append("the model returned nothing usable")
        except (llm.ModelUnavailable, ValueError, json.JSONDecodeError) as exc:
            notes.append(f"model unavailable ({type(exc).__name__}) - using rules")
    else:
        notes.append("no API key set - deterministic rules only")
    return by_rules(requirements), "rules", notes


HEADER = '''"""
GENERATED FILE - do not edit by hand.

Produced by 3-ai-test-generator from requirements.md. Every test below is real,
executable Playwright code built from a fixed vocabulary of page-object
actions, so this file always imports and always runs.

Regenerate with:  python3 cli.py --out <dir>
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "1-test-automation"))

from pages import CartPage, CheckoutPage, InventoryPage, LoginPage   # noqa: E402

BASE_URL = "https://www.saucedemo.com"


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL
'''


CONFTEST = '''"""Fixtures for the generated suite.

Written alongside the generated tests on purpose. The tests live in their own
directory, so pytest will not find project 1\'s conftest - and a generated
suite that cannot find its fixtures is a generated suite that does not run.
"""
import pytest
from playwright.sync_api import sync_playwright


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
def page(browser):
    """A fresh context per test - no cookies or cart carried over."""
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    yield page
    context.close()
'''


def to_module(cases: list[Generated]) -> str:
    return HEADER + "\n" + "\n".join(c.code for c in cases)
