from .base_page import BasePage


class CartPage(BasePage):
    url_path = "/cart.html"

    ITEM = ".cart_item"
    NAME = ".inventory_item_name"
    CHECKOUT = "#checkout"

    def item_names(self) -> list[str]:
        return [t.strip() for t in self.page.locator(self.NAME).all_text_contents()]

    def item_count(self) -> int:
        return self.count(self.ITEM)

    def wait_ready(self) -> "CartPage":
        self.wait_for(self.CHECKOUT)
        return self

    def start_checkout(self) -> None:
        self.wait_ready()
        self.click(self.CHECKOUT)
        self.page.wait_for_load_state("domcontentloaded")
