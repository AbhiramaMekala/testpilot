from .base_page import BasePage


class CheckoutPage(BasePage):
    """Checkout on saucedemo is three pages, not one form.

        /checkout-step-one.html    name and postcode  -> Continue
        /checkout-step-two.html    order summary      -> Finish
        /checkout-complete.html    confirmation

    The first version of this project modelled it as a single form, because
    that is how the local fixture happened to work. Against the real site every
    checkout test failed.
    """
    url_path = "/checkout-step-one.html"

    FIRST_NAME = "#first-name"
    LAST_NAME = "#last-name"
    POSTCODE = "#postal-code"
    CONTINUE = "#continue"
    FINISH = "#finish"
    ERROR = '[data-test="error"]'
    COMPLETE = ".complete-header"

    def fill_details(self, first: str = "", last: str = "", postcode: str = "") -> None:
        self.wait_for(self.FIRST_NAME)
        self.fill(self.FIRST_NAME, first)
        self.fill(self.LAST_NAME, last)
        self.fill(self.POSTCODE, postcode)
        self.click(self.CONTINUE)
        self.page.wait_for_load_state("domcontentloaded")

    def finish(self) -> None:
        self.wait_for(self.FINISH)
        self.click(self.FINISH)
        self.page.wait_for_load_state("domcontentloaded")

    def error_message(self) -> str:
        if not self.count(self.ERROR):
            return ""
        return self.text_of(self.ERROR, timeout=2000)

    def reached_summary(self) -> bool:
        return "checkout-step-two" in self.page.url

    def order_complete(self) -> bool:
        if "checkout-complete" in self.page.url:
            return True
        if self.count(self.ERROR) or "step-one" in self.page.url:
            return False
        return self.is_visible(self.COMPLETE, timeout=4000)

    def complete_purchase(self, first: str, last: str, postcode: str) -> bool:
        self.fill_details(first, last, postcode)
        if not self.reached_summary():
            return False
        self.finish()
        return self.order_complete()
