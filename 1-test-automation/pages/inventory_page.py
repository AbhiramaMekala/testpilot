from .base_page import BasePage


class InventoryPage(BasePage):
    """Selectors follow the real saucedemo.com DOM, not the local fixture.

    The fixture copies the real site; the tests are written against the real
    site. Getting that the wrong way round is how a suite ends up passing
    against a mock and failing against production.
    """
    url_path = "/inventory.html"

    ITEM = ".inventory_item"
    NAME = ".inventory_item_name"
    PRICE = ".inventory_item_price"
    CART_LINK = ".shopping_cart_link"
    CART_BADGE = ".shopping_cart_badge"

    def wait_ready(self) -> "InventoryPage":
        """Wait until the product grid has actually rendered."""
        if not self.wait_for(self.ITEM):
            raise AssertionError("product grid never appeared: " + self.missing(self.ITEM))
        return self

    def item_count(self) -> int:
        return self.count(self.ITEM)

    def item_names(self) -> list[str]:
        return [t.strip() for t in self.page.locator(self.NAME).all_text_contents()]

    def prices(self) -> list[float]:
        self.wait_ready()
        return [float(t.strip().lstrip("$"))
                for t in self.page.locator(self.PRICE).all_text_contents()]

    def add_item_by_index(self, index: int) -> str:
        """Click the add button inside the nth product tile.

        Scoped to the tile rather than using the per-product id, so the test
        does not break when the catalogue changes.
        """
        self.wait_ready()
        names = self.item_names()
        if index >= len(names):
            raise AssertionError(
                f"asked for product {index} but the page shows {len(names)}")
        name = names[index]
        self.page.locator(self.ITEM).nth(index).locator("button").click()
        # The badge appearing is the signal the cart actually changed. Reading
        # it immediately after the click races the update on a real network.
        self.wait_for(self.CART_BADGE, timeout=5000)
        return name

    def add_first_item(self) -> str:
        return self.add_item_by_index(0)

    def cart_badge_count(self) -> int:
        """The badge element is absent when the cart is empty, which is not an
        error - it is zero."""
        if not self.count(self.CART_BADGE):
            return 0
        text = self.text_of(self.CART_BADGE, timeout=2000)
        return int(text) if text.isdigit() else 0

    def go_to_cart(self) -> None:
        self.click(self.CART_LINK)
        self.page.wait_for_load_state("domcontentloaded")
