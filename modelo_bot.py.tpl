# -*- coding: utf-8 -*-
r"""
Bot "$nome_bot" - gerado pelo Universal WebScrapping em $gerado_em.

Repete no Microsoft Edge a tarefa que foi gravada.

Como rodar (a partir da pasta do projeto):
    python bots/$nome_bot.py              -> com a janela do Edge visível
    python bots/$nome_bot.py --headless   -> sem janela (para agendar)

Credenciais lidas do .env na raiz do projeto:
$variaveis_doc

Agendador de Tarefas do Windows:
    Programa:   $python
    Argumentos: bots\$nome_bot.py --headless
    Iniciar em: a pasta do projeto

Saída: 0 = sucesso, 1 = falha em algum passo (detalhes e print da tela em logs/),
2 = credencial ausente no .env.
"""

from __future__ import annotations

import argparse
import logging
import os
import re  # pode ser usado pelos passos gravados
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import BrowserContext, Download, Page, expect, sync_playwright  # noqa: F401
from playwright.sync_api import Error as PlaywrightError

RAIZ = Path(__file__).resolve().parent.parent
NOME_BOT = "$nome_bot"
TIMEOUT_MS = 60_000  # espera máxima por elemento, navegação ou download
ESPERA_REDE_MS = 15_000  # espera máxima pela rede acalmar depois de cada ação
VARIAVEIS_ENV = $variaveis_env
$destinos

log = logging.getLogger(NOME_BOT)
_pendentes: set = set()  # requisições de rede ainda em andamento
_TIPOS_SEM_FIM = {"eventsource", "websocket"}  # conexões que ficam abertas de propósito


def blindar_console() -> None:
    """Print de log nunca pode derrubar o bot (console cp1252 do Windows)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, OSError):
            pass


def configurar_log() -> None:
    pasta = RAIZ / "logs"
    pasta.mkdir(exist_ok=True)
    formato = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%d/%m/%Y %H:%M:%S")
    for handler in (logging.StreamHandler(), logging.FileHandler(pasta / f"{NOME_BOT}.log", encoding="utf-8")):
        handler.setFormatter(formato)
        log.addHandler(handler)
    log.setLevel(logging.INFO)


def credencial(nome: str) -> str:
    """Valor de uma credencial do .env (o main já conferiu que todas existem)."""
    return os.environ[nome]


def rastrear_rede(context: BrowserContext) -> None:
    def comecou(requisicao) -> None:
        if requisicao.resource_type not in _TIPOS_SEM_FIM:
            _pendentes.add(requisicao)

    def terminou(requisicao) -> None:
        _pendentes.discard(requisicao)

    context.on("request", comecou)
    context.on("requestfinished", terminou)
    context.on("requestfailed", terminou)


def aguardar_rede(pagina: Page) -> None:
    """Espera a página parar de buscar dados (ex.: um filtro carregando). Nunca falha."""
    try:
        pagina.wait_for_timeout(250)  # dá tempo das requisições da ação começarem
        limite = time.monotonic() + ESPERA_REDE_MS / 1000
        quieta_desde = None
        while time.monotonic() < limite:
            if _pendentes:
                quieta_desde = None
            elif quieta_desde is None:
                quieta_desde = time.monotonic()
            elif time.monotonic() - quieta_desde >= 0.5:
                return
            pagina.wait_for_timeout(100)  # enquanto espera, o Playwright entrega os eventos de rede
        log.info("A rede não acalmou em %d s; seguindo assim mesmo.", ESPERA_REDE_MS // 1000)
    except PlaywrightError:
        pass  # a própria ação fechou a página


def salvar_download(download: Download, destino: Path) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / download.suggested_filename
    if arquivo.exists():
        log.info("Substituindo o arquivo existente %s", arquivo)
    download.save_as(arquivo)
    log.info("Download salvo em %s", arquivo)
    return arquivo


def executar_passos(context: BrowserContext) -> None:
$passos


def salvar_prints(context: BrowserContext) -> None:
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    for i, pagina in enumerate(context.pages):
        arquivo = RAIZ / "logs" / f"{NOME_BOT}_erro_{carimbo}_{i}.png"
        try:
            pagina.screenshot(path=str(arquivo), full_page=True)
            log.error("Print da tela salvo em %s", arquivo)
        except PlaywrightError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"Bot {NOME_BOT} (Universal WebScrapping)")
    parser.add_argument("--headless", action="store_true", help="roda sem abrir a janela do Edge")
    args = parser.parse_args(argv)
    blindar_console()
    configurar_log()
    load_dotenv(RAIZ / ".env", interpolate=False)
    faltando = [nome for nome in VARIAVEIS_ENV if not os.environ.get(nome)]
    if faltando:
        log.error("Credenciais ausentes em %s: %s", RAIZ / ".env", ", ".join(faltando))
        return 2
    log.info("Iniciando o bot %s", NOME_BOT)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=args.headless)
        context = browser.new_context(accept_downloads=True)
        context.set_default_timeout(TIMEOUT_MS)
        rastrear_rede(context)
        try:
            executar_passos(context)
        except Exception:
            log.exception("O bot falhou.")
            salvar_prints(context)
            return 1
        finally:
            context.close()
            browser.close()
    log.info("Bot %s concluído com sucesso.", NOME_BOT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
