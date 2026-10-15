# -*- coding: utf-8 -*-
"""Loop principal: nome -> gravação -> perguntas -> bot salvo -> 'ensinar outro?'."""
from pathlib import Path

import pytest
from dotenv import dotenv_values

import interface
import webscraper_universal as app
from gravador import ErroGravador

FIXTURES = Path(__file__).parent / "fixtures"
GRAVACAO = (FIXTURES / "gravacao_login_download.py").read_text(encoding="utf-8")
GRAVACAO_VAZIA = (FIXTURES / "gravacao_vazia.py").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def sem_janela(monkeypatch):
    monkeypatch.setattr(interface, "_seletor_de_pasta", lambda titulo, inicial: "")


def roteiro(monkeypatch, respostas):
    fila = iter(respostas)
    monkeypatch.setattr("builtins.input", lambda pergunta="": next(fila))


def bots(raiz: Path) -> list[str]:
    return sorted(p.name for p in (raiz / "bots").glob("*.py"))


def test_um_bot_e_encerra(monkeypatch, tmp_path):
    # nome, credenciais (Enter = Usuário e Senha), pasta do download (Enter = padrão), ensinar outro? não
    roteiro(monkeypatch, ["cotacao_sp", "", "", "n"])

    assert app.main(raiz=tmp_path, gravar=lambda: GRAVACAO) == 0

    assert bots(tmp_path) == ["cotacao_sp.py"]
    codigo = (tmp_path / "bots" / "cotacao_sp.py").read_text(encoding="utf-8")
    assert "S3gr3d0!" not in codigo
    assert f"Path({str(tmp_path / 'downloads' / 'cotacao_sp')!r})" in codigo
    assert dotenv_values(tmp_path / ".env", interpolate=False) == {
        "COTACAO_SP_USUARIO": "matheus.p",
        "COTACAO_SP_SENHA": "S3gr3d0!",
    }


def test_dois_bots(monkeypatch, tmp_path):
    chamadas = []

    def gravar():
        chamadas.append(1)
        return GRAVACAO

    roteiro(monkeypatch, ["a", "", "", "s", "b", "", "", "n"])

    assert app.main(raiz=tmp_path, gravar=gravar) == 0

    assert len(chamadas) == 2
    assert bots(tmp_path) == ["a.py", "b.py"]
    assert set(dotenv_values(tmp_path / ".env")) == {"A_USUARIO", "A_SENHA", "B_USUARIO", "B_SENHA"}


@pytest.mark.parametrize("gravado", [GRAVACAO_VAZIA, ""])
def test_gravacao_vazia_nao_gera_arquivo(monkeypatch, tmp_path, capsys, gravado):
    roteiro(monkeypatch, ["x", "n"])

    assert app.main(raiz=tmp_path, gravar=lambda: gravado) == 0

    assert bots(tmp_path) == []
    assert "Nada foi gravado" in capsys.readouterr().out


def test_ctrl_c(monkeypatch, tmp_path):
    def gravar():
        raise KeyboardInterrupt

    roteiro(monkeypatch, ["x"])

    assert app.main(raiz=tmp_path, gravar=gravar) == 130


@pytest.mark.parametrize(
    ("falha", "mensagem"),
    [(ErroGravador("Edge não encontrado"), "Edge não encontrado"), (None, "não é um script Python válido")],
)
def test_erros_nao_derrubam_o_loop(monkeypatch, tmp_path, capsys, falha, mensagem):
    def gravar():
        if falha:
            raise falha
        return "isto não é python ("

    roteiro(monkeypatch, ["x", "n"])

    assert app.main(raiz=tmp_path, gravar=gravar) == 0

    assert mensagem in capsys.readouterr().out
    assert bots(tmp_path) == []


def test_credencial_vazada_pergunta_de_novo(monkeypatch, tmp_path, capsys):
    gravacao = GRAVACAO.replace("/login", "/login?senha=S3gr3d0!")
    # credenciais padrão -> vaza na URL -> escolher de novo? sim -> só o campo 1 (Usuário) -> gera
    roteiro(monkeypatch, ["cotacao_sp", "", "", "s", "1", "n"])

    assert app.main(raiz=tmp_path, gravar=lambda: gravacao) == 0

    assert "também aparece em outro ponto" in capsys.readouterr().out
    assert bots(tmp_path) == ["cotacao_sp.py"]
    assert dotenv_values(tmp_path / ".env") == {"COTACAO_SP_USUARIO": "matheus.p"}


def test_credencial_vazada_desistindo(monkeypatch, tmp_path):
    gravacao = GRAVACAO.replace("/login", "/login?senha=S3gr3d0!")
    roteiro(monkeypatch, ["cotacao_sp", "", "", "n", "n"])

    assert app.main(raiz=tmp_path, gravar=lambda: gravacao) == 0

    assert bots(tmp_path) == []
    assert not (tmp_path / ".env").exists()
