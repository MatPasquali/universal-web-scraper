import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(channel="msedge", headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://dados.exemplo.com/")
    with page.expect_download() as download_info:
        page.get_by_role("link", name="Base completa").click()
    download = download_info.value
    page.get_by_role("combobox").select_option("2026")
    with page.expect_download() as download1_info:
        page.get_by_text("Resumo mensal").click()
    download1 = download1_info.value

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
