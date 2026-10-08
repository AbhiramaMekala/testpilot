"""Login: the gate everything else depends on."""
import pytest

from pages import InventoryPage, LoginPage

VALID = ("standard_user", "secret_sauce")


@pytest.mark.smoke
def test_valid_credentials_reach_the_inventory(page, base_url):
    login = LoginPage(page, base_url).open()
    login.login(*VALID)
    assert login.is_logged_in(), f"expected /inventory, landed on {page.url}"
    inventory = InventoryPage(page, base_url).wait_ready()
    assert inventory.item_count() > 0, inventory.missing(InventoryPage.ITEM)


@pytest.mark.smoke
@pytest.mark.parametrize("username,password,expected", [
    ("standard_user", "wrong_password", "do not match"),
    ("no_such_user", "secret_sauce", "do not match"),
    ("", "secret_sauce", "Username is required"),
    ("standard_user", "", "Password is required"),
])
def test_bad_credentials_are_refused_with_a_message(page, base_url, username, password, expected):
    login = LoginPage(page, base_url).open()
    login.login(username, password)
    assert not login.is_logged_in(), "a bad login got through"
    assert expected in login.error_message(), f"got: {login.error_message()!r}"


@pytest.mark.regression
def test_locked_out_user_is_told_why(page, base_url):
    """A locked account must say it is locked, not 'wrong password'. Users who
    are told the wrong thing call support instead of their administrator."""
    login = LoginPage(page, base_url).open()
    login.login("locked_out_user", "secret_sauce")
    assert not login.is_logged_in()
    assert "locked out" in login.error_message().lower()


@pytest.mark.regression
def test_inventory_is_not_reachable_without_logging_in(page, base_url):
    """Deep-linking past the login screen must not work."""
    inventory = InventoryPage(page, base_url).open()
    assert inventory.item_count() == 0, "inventory rendered to an anonymous visitor"
