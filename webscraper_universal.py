# -*- coding: utf-8 -*-
"""
Universal WebScrapping - ensine uma tarefa no Edge e ganhe um bot Python que a repete.

    python webscraper_universal.py

Fluxo: nome do bot -> Edge vazio (gravação) -> credenciais e pastas -> bots/<nome>.py -> ensinar outro?
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import credenciais
import gravador
import interface
from analisador import ErroGravacao, analisar
from credenciais import ErroCredencial
from gerador_bot import CredencialVazada, ErroGeracao, gerar_bot
from gravador import ErroGravador

RAIZ = Path(__file__).resolve().parent

INSTRUCOES = """
Vou abrir o Microsoft Edge vazio para você ensinar a tarefa:
  1. Digite o endereço do site na barra e faça a tarefa normalmente.
  2. Se baixar arquivos, não precisa movê-los: no fim eu pergunto a pasta de destino.
  3. Quando terminar, FECHE a janela do Edge.
  (A janela "Playwright Inspector" mostra o código sendo gravado; pode ignorá-la.)
"""


def ensinar_um_bot(raiz: Path, gravar=gravador.gravar) -> Path | None:
    """Uma rodada completa. Devolve o caminho do bot salvo, ou None se nada foi gerado."""
    pasta_bots = raiz / "bots"
    pasta_bots.mkdir(parents=True, exist_ok=True)
    nome = interface.perguntar_nome_bot(pasta_bots)
    print(INSTRUCOES)
    codigo = gravar()
    if not codigo.strip():
        print("Nada foi gravado.")
        return None
    gravacao = analisar(codigo)
    if gravacao.vazia:
        print("Nada foi gravado (o Edge foi fechado sem nenhuma ação).")
        return None

    escolhidos = interface.escolher_credenciais(gravacao.campos)
    destinos = {
        download.variavel: interface.escolher_pasta(
            f'Pasta de destino do download #{i} ("{download.gatilho}")', raiz / "downloads" / nome
        )
        for i, download in enumerate(gravacao.downloads, 1)
    }
    if not gravacao.downloads:
        print(
            "\nNenhum download apareceu na gravação. Se o bot baixar algum arquivo mesmo assim, "
            f"ele vai para {raiz / 'downloads' / nome}."
        )
    automaticas = interface.confirmar_navegacoes(gravacao.navegacoes_apos_acao)
    while True:
        usados: set[str] = set()
        variaveis = {c.posicao: credenciais.nome_variavel(nome, c.rotulo, usados) for c in escolhidos}
        try:
            codigo_bot = gerar_bot(gravacao, nome, variaveis, destinos, datetime.now(), automaticas)
            break
        except CredencialVazada as erro:
            print(f"\n{erro}")
            if not interface.perguntar_sim_nao("Escolher as credenciais de novo?", True):
                return None
            escolhidos = interface.escolher_credenciais(gravacao.campos)

    valores = {variaveis[c.posicao]: c.valor for c in escolhidos}
    if valores:
        credenciais.salvar_no_env(raiz / ".env", valores)
    caminho = pasta_bots / f"{nome}.py"
    caminho.write_text(codigo_bot, encoding="utf-8")
    print(f"\nBot pronto: {caminho}")
    print(f"  Rodar: python bots/{nome}.py   (ou: python bots/{nome}.py --headless)")
    if valores:
        print(f"  Credenciais guardadas no .env: {', '.join(valores)}")
    return caminho


def main(raiz: Path = RAIZ, gravar=gravador.gravar) -> int:
    interface.blindar_console()
    print("Universal WebScrapping - ensine uma tarefa no Edge e ganhe um bot que a repete.\n")
    try:
        while True:
            try:
                ensinar_um_bot(raiz, gravar)
            except (ErroGravador, ErroGravacao, ErroGeracao, ErroCredencial) as erro:
                print(f"\nNão foi possível criar o bot: {erro}")
            if not interface.perguntar_sim_nao("\nEnsinar um novo bot?", False):
                print("Até a próxima!")
                return 0
    except KeyboardInterrupt:
        print("\nInterrompido.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
