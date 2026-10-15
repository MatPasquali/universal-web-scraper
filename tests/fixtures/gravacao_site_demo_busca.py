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
    page.get_by_placeholder("Buscar produto").click()
    page.get_by_placeholder("Buscar produto").fill("Auto")
    page.once("dialog", lambda dialog: dialog.dismiss())
    with page.expect_download() as download_info:
        page.get_by_role("button", name="Exportar CSV").click()
    download = download_info.value

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
