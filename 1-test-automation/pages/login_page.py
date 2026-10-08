from .base_page import BasePage


class LoginPage(BasePage):
    url_path = "/"

    USERNAME = "#user-name"
    PASSWORD = "#password"
    SUBMIT = "#login-button"
    ERROR = '[data-test="error"]'

    def login(self, username: str, password: str) -> None:
        self.fill(self.USERNAME, username)
        self.fill(self.PASSWORD, password)
        self.click(self.SUBMIT)
        self.page.wait_for_load_state("domcontentloaded")

    def error_message(self) -> str:
        return self.text_of(self.ERROR)

    def is_logged_in(self) -> bool:
        return "/inventory" in self.page.url
