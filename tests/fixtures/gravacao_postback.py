import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(channel="msedge", headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://legado.exemplo.com/cotacao.aspx")
    page.get_by_role("checkbox", name="Somente SP").check()
    page.goto("https://legado.exemplo.com/cotacao.aspx")
    page.get_by_label("Local").select_option("RJ")
    page.goto("https://legado.exemplo.com/cotacao.aspx")
    with page.expect_download() as download_info:
        page.get_by_role("button", name="Exportar").click()
    download = download_info.value

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
