# -*- coding: utf-8 -*-
"""Leitura do script gravado pelo codegen do Playwright (formato 1.61)."""
import ast
from pathlib import Path

import pytest

from analisador import DownloadGravado, ErroGravacao, analisar, rotulo_do_alvo

FIXTURES = Path(__file__).parent / "fixtures"


def ler(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


def test_remove_boilerplate_e_mantem_new_page():
    g = analisar(ler("gravacao_login_download.py"))
    codigo = [ast.unparse(p) for p in g.passos]
    assert codigo[0] == "page = context.new_page()"
    assert codigo[1] == "page.goto('https://cotacao.exemplo.com.br/login')"
    assert not any(c.startswith(("browser =", "context =", "context.close", "browser.close")) for c in codigo)
    assert len(codigo) == 13


def test_campos_digitados_com_rotulo_e_sinais():
    g = analisar(ler("gravacao_login_download.py"))
    assert [(c.rotulo, c.valor, c.parece_credencial, c.parece_senha) for c in g.campos] == [
        ("Usuário", "joao.silva", True, False),
        ("Senha", "S3gr3d0!", True, True),
        ("Buscar produto", "auto", False, False),
    ]


def test_posicao_aponta_para_a_chamada_fill():
    texto = ler("gravacao_login_download.py")
    g = analisar(texto)
    linha, coluna = g.campos[1].posicao
    trecho = texto.splitlines()[linha - 1][coluna:]
    assert trecho == 'page.get_by_role("textbox", name="Senha").fill("S3gr3d0!")'


def test_download_com_gatilho():
    g = analisar(ler("gravacao_login_download.py"))
    assert g.downloads == [DownloadGravado(variavel="download", gatilho="Exportar CSV")]


def test_dois_downloads():
    g = analisar(ler("gravacao_dois_downloads.py"))
    assert [d.variavel for d in g.downloads] == ["download", "download1"]
    assert [d.gatilho for d in g.downloads] == ["Base completa", "Resumo mensal"]


def test_popup_e_iframe_preservados():
    g = analisar(ler("gravacao_popup_iframe.py"))
    codigo = "\n".join(ast.unparse(p) for p in g.passos)
    assert "page1 = page1_info.value" in codigo
    assert ".content_frame.get_by_label('E-mail').fill('eu@exemplo.com')" in codigo
    assert [(c.rotulo, c.parece_credencial, c.parece_senha) for c in g.campos] == [
        ("E-mail", True, False),
        ("#pwd", True, True),
    ]
    assert g.downloads == []


def test_gravacao_vazia():
    assert analisar(ler("gravacao_vazia.py")).vazia
    assert not analisar(ler("gravacao_login_download.py")).vazia


@pytest.mark.parametrize("texto", ["isto não é python (", "x = 1\n"])
def test_texto_invalido_gera_erro(texto):
    with pytest.raises(ErroGravacao):
        analisar(texto)


def test_rotulo_do_alvo_role_sem_nome_usa_papel():
    chamada = ast.parse('page.get_by_role("combobox").select_option("SP")').body[0].value
    assert rotulo_do_alvo(chamada) == "combobox"


def test_rotulo_do_alvo_sem_localizador_reconhecido():
    chamada = ast.parse('page.keyboard.press("Enter")').body[0].value
    assert rotulo_do_alvo(chamada) == ""


def test_campo_sem_rotulo_vira_campo_n():
    texto = ler("gravacao_vazia.py").replace(
        "    page = context.new_page()\n",
        '    page = context.new_page()\n    page.locator("input").nth(2).fill("x")\n'
        '    page.keyboard.type("y")\n    page.frame_locator("f").first.fill("z")\n',
    )
    g = analisar(texto)
    assert [c.rotulo for c in g.campos] == ["input", "campo 2"]
