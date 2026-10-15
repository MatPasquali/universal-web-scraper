# -*- coding: utf-8 -*-
"""Geração do código do bot a partir da gravação."""
import sys
import warnings
from datetime import datetime
from pathlib import Path

import pytest

from analisador import analisar
from credenciais import nome_variavel
from gerador_bot import CredencialVazada, gerar_bot

FIXTURES = Path(__file__).parent / "fixtures"
DESTINO = Path(r"C:\Users\x\Pasta com espaço\Ação")


def ler(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


def gerar(texto: str | None = None, marcar=("Usuário", "Senha"), fixture="gravacao_login_download.py") -> str:
    gravacao = analisar(texto if texto is not None else ler(fixture))
    usados: set[str] = set()
    variaveis = {
        c.posicao: nome_variavel("cotacao_sp", c.rotulo, usados) for c in gravacao.campos if c.rotulo in marcar
    }
    destinos = {d.variavel: DESTINO for d in gravacao.downloads}
    return gerar_bot(gravacao, "cotacao_sp", variaveis, destinos, datetime(2026, 10, 14, 9, 30))


def linha_apos(codigo: str, trecho: str) -> str:
    """Linha seguinte ao passo que contém `trecho` (ignora o log.info, cuja descrição repete o passo)."""
    linhas = [l.strip() for l in codigo.splitlines() if l.strip()]
    i = next(i for i, l in enumerate(linhas) if trecho in l and not l.startswith("log.info("))
    return linhas[i + 1]


def test_bot_compila_sem_avisos():
    codigo = gerar()
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # escape inválido (ex.: C:\Users na docstring) vira erro
        compile(codigo, "bot.py", "exec")


def test_nenhuma_credencial_no_texto():
    codigo = gerar()
    assert "S3gr3d0!" not in codigo
    assert "joao.silva" not in codigo


def test_usa_credencial_do_env():
    codigo = gerar()
    assert ".fill(credencial('COTACAO_SP_SENHA'))" in codigo
    assert ".fill(credencial('COTACAO_SP_USUARIO'))" in codigo
    assert "VARIAVEIS_ENV = ('COTACAO_SP_USUARIO', 'COTACAO_SP_SENHA')" in codigo


def test_campo_nao_marcado_fica_no_codigo():
    assert ".fill('auto')" in gerar()


def test_mesmo_valor_em_outro_campo_tambem_vira_credencial():
    texto = ler("gravacao_login_download.py").replace(
        '    page.get_by_role("button", name="Entrar").click()\n',
        '    page.get_by_label("Confirmar senha").fill("S3gr3d0!")\n'
        '    page.get_by_role("button", name="Entrar").click()\n',
    )
    codigo = gerar(texto)
    assert "S3gr3d0!" not in codigo
    assert "get_by_label('Confirmar senha').fill(credencial('COTACAO_SP_SENHA'))" in codigo


def test_salva_download_logo_apos_value():
    assert linha_apos(gerar(), "download = download_info.value") == "salvar_download(download, DESTINO_DOWNLOAD_1)"


def test_destino_renderizado():
    codigo = gerar()
    linha = next(l for l in codigo.splitlines() if l.startswith("DESTINO_DOWNLOAD_1 = "))
    ns = {"Path": Path}
    exec(linha, ns)
    assert ns["DESTINO_DOWNLOAD_1"] == DESTINO


def test_aguardar_rede_apos_clique_e_nao_apos_fill():
    codigo = gerar()
    assert linha_apos(codigo, "name='Entrar').click()") == "aguardar_rede(page)"
    assert linha_apos(codigo, "select_option('SP')") == "aguardar_rede(page)"
    assert linha_apos(codigo, "page.goto(") == "aguardar_rede(page)"
    assert not linha_apos(codigo, "fill(credencial('COTACAO_SP_SENHA'))").startswith("aguardar_rede")


def test_aguardar_rede_na_pagina_do_popup():
    codigo = gerar(fixture="gravacao_popup_iframe.py")
    assert linha_apos(codigo, "page1 = page1_info.value") == "aguardar_rede(page1)"
    assert linha_apos(codigo, "name='Gerar').click()") == "aguardar_rede(page1)"
    assert not linha_apos(codigo, "page1.close()").startswith("aguardar_rede")


def test_dialogo_aceito():
    codigo = gerar()
    assert "dialog.accept()" in codigo
    assert "dismiss" not in codigo


def test_headless_e_canal_edge():
    codigo = gerar()
    assert '"--headless"' in codigo
    assert 'channel="msedge"' in codigo


def test_log_de_passos():
    codigo = gerar()
    assert "log.info('Passo %d/%d: %s', 1, 13, 'page = context.new_page()')" in codigo
    assert "Passo %d/%d: %s', 13, 13, 'download = download_info.value')" in codigo


def test_docstring_com_variaveis_e_agendador():
    codigo = gerar()
    cabecalho = codigo.split('"""')[1]
    assert "COTACAO_SP_USUARIO" in cabecalho and "COTACAO_SP_SENHA" in cabecalho
    assert sys.executable in cabecalho
    assert "14/10/2026 09:30" in cabecalho


def test_sem_credenciais_e_sem_downloads():
    codigo = gerar(marcar=(), fixture="gravacao_popup_iframe.py")
    compile(codigo, "bot.py", "exec")
    assert "VARIAVEIS_ENV = ()" in codigo
    assert "DESTINO_DOWNLOAD" not in codigo


def test_senha_em_url_gera_erro():
    texto = ler("gravacao_login_download.py").replace(
        "https://cotacao.exemplo.com.br/login", "https://joao.silva:S3gr3d0!@cotacao.exemplo.com.br/login"
    )
    with pytest.raises(CredencialVazada) as erro:
        gerar(texto)
    assert "S3gr3d0!" not in str(erro.value)
