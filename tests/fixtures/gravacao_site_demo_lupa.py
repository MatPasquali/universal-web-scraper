import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(channel="msedge", headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("http://127.0.0.1:PORTA/")
    page.get_by_label("Usuário").click()
    page.get_by_label("Usuário").fill("demo")
    page.get_by_label("Senha").click()
    page.get_by_label("Senha").fill("demo123")
    page.get_by_role("button", name="Entrar").click()
    with page.expect_popup() as page1_info:
        page.get_by_role("button", name="Escolher local").click()
    page1 = page1_info.value
    page1.get_by_role("button", name="SP").click()
    page.once("dialog", lambda dialog: dialog.dismiss())
    with page.expect_download() as download_info:
        page.get_by_role("button", name="Exportar CSV").click()
    download = download_info.value

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
