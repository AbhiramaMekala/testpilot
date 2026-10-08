"""Checkout: three pages on saucedemo, not one form."""
import pytest

from pages import CartPage, CheckoutPage, InventoryPage, LoginPage

VALID = ("standard_user", "secret_sauce")


@pytest.fixture
def checkout(page, base_url):
    LoginPage(page, base_url).open().login(*VALID)
    inventory = InventoryPage(page, base_url).wait_ready()
    inventory.add_first_item()
    inventory.go_to_cart()
    CartPage(page, base_url).start_checkout()
    return CheckoutPage(page, base_url)


@pytest.mark.smoke
def test_full_purchase_journey_completes(checkout, page):
    assert checkout.complete_purchase("Abhi", "Mekala", "560064"), \
        f"checkout did not reach the confirmation (stopped at {page.url})"


@pytest.mark.regression
@pytest.mark.parametrize("first,last,postcode,expected", [
    ("", "Mekala", "560064", "First Name is required"),
    ("Abhi", "", "560064", "Last Name is required"),
    ("Abhi", "Mekala", "", "Postal Code is required"),
])
def test_checkout_validates_required_fields(checkout, first, last, postcode, expected):
    checkout.fill_details(first, last, postcode)
    assert not checkout.reached_summary(), "incomplete form was accepted"
    assert expected in checkout.error_message(), f"got: {checkout.error_message()!r}"


@pytest.mark.regression
def test_cart_is_emptied_after_a_successful_order(checkout, page, base_url):
    """A cart that still holds the items after purchase lets the customer buy
    them a second time by refreshing."""
    assert checkout.complete_purchase("Abhi", "Mekala", "560064")
    assert InventoryPage(page, base_url).open().cart_badge_count() == 0
