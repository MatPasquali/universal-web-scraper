import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(channel="msedge", headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://portal.exemplo.com/")
    with page.expect_popup() as page1_info:
        page.get_by_role("link", name="Relatórios").click()
    page1 = page1_info.value
    page1.locator("#frame-relatorio").content_frame.get_by_label("E-mail").fill("eu@exemplo.com")
    page1.locator("#frame-relatorio").content_frame.locator("#pwd").fill("abc12345")
    page1.locator("#frame-relatorio").content_frame.get_by_role("button", name="Gerar").click()
    page1.close()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
