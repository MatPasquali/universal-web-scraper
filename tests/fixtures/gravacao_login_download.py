import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(channel="msedge", headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://cotacao.exemplo.com.br/login")
    page.get_by_role("textbox", name="Usuário").click()
    page.get_by_role("textbox", name="Usuário").fill("matheus.p")
    page.get_by_role("textbox", name="Senha").click()
    page.get_by_role("textbox", name="Senha").fill("S3gr3d0!")
    page.get_by_role("button", name="Entrar").click()
    page.get_by_label("Local").select_option("SP")
    page.get_by_placeholder("Buscar produto").fill("auto")
    page.get_by_role("button", name="Aplicar filtro").click()
    page.once("dialog", lambda dialog: dialog.dismiss())
    with page.expect_download() as download_info:
        page.get_by_role("button", name="Exportar CSV").click()
    download = download_info.value

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
