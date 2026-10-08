"""Adding to the cart, and the counter the user actually looks at."""
import pytest

from pages import CartPage, InventoryPage, LoginPage

VALID = ("standard_user", "secret_sauce")


@pytest.fixture
def inventory(page, base_url):
    LoginPage(page, base_url).open().login(*VALID)
    return InventoryPage(page, base_url).wait_ready()


@pytest.mark.smoke
def test_adding_an_item_updates_the_cart_badge(inventory):
    assert inventory.cart_badge_count() == 0
    inventory.add_first_item()
    assert inventory.cart_badge_count() == 1


@pytest.mark.regression
def test_badge_counts_every_item_added(inventory):
    for expected in (1, 2, 3):
        inventory.add_item_by_index(expected - 1)
        assert inventory.cart_badge_count() == expected


@pytest.mark.regression
def test_the_item_in_the_cart_is_the_item_that_was_added(page, base_url, inventory):
    """The badge going up is not proof the right product went in."""
    added = inventory.add_item_by_index(2)
    inventory.go_to_cart()
    names = CartPage(page, base_url).item_names()
    assert added in names, f"added {added!r}, cart holds {names}"


@pytest.mark.regression
def test_prices_are_well_formed(inventory):
    prices = inventory.prices()
    assert prices, "no prices rendered"
    assert all(p > 0 for p in prices), f"non-positive price in {prices}"
    assert all(round(p, 2) == p for p in prices), "price with more than two decimals"
