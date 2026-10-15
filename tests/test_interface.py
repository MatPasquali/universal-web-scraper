# -*- coding: utf-8 -*-
"""Conversa no terminal e seletor de pasta."""
from pathlib import Path

import pytest

import interface
from analisador import CampoDigitado

CAMPOS = [
    CampoDigitado((10, 4), "Usuário", "matheus.p", True, False),
    CampoDigitado((12, 4), "Senha", "S3gr3d0!", True, True),
    CampoDigitado((15, 4), "Buscar produto", "auto", False, False),
]


def roteiro(monkeypatch, respostas):
    """Responde os input() na ordem; uma pergunta a mais vira erro (StopIteration)."""
    fila = iter(respostas)
    perguntas = []

    def falso_input(pergunta=""):
        perguntas.append(pergunta)
        return next(fila)

    monkeypatch.setattr("builtins.input", falso_input)
    return perguntas


def test_slug():
    assert interface.slug("Cotação SP!") == "cotacao_sp"
    assert interface.slug("  Base--Mensal ") == "base_mensal"
    assert interface.slug("") == ""


def test_nome_invalido_pergunta_de_novo(monkeypatch, tmp_path):
    roteiro(monkeypatch, ["123", "", "cotacao sp"])
    assert interface.perguntar_nome_bot(tmp_path) == "cotacao_sp"


def test_nome_existente_sem_sobrescrever(monkeypatch, tmp_path):
    (tmp_path / "a.py").touch()
    roteiro(monkeypatch, ["a", "n", "b"])
    assert interface.perguntar_nome_bot(tmp_path) == "b"


def test_nome_existente_sobrescrevendo(monkeypatch, tmp_path):
    (tmp_path / "a.py").touch()
    roteiro(monkeypatch, ["a", "s"])
    assert interface.perguntar_nome_bot(tmp_path) == "a"


def test_credenciais_enter_usa_padrao(monkeypatch):
    roteiro(monkeypatch, [""])
    assert interface.escolher_credenciais(CAMPOS) == CAMPOS[:2]


@pytest.mark.parametrize(("resposta", "indices"), [("3", [2]), ("0", []), ("1, 3", [0, 2])])
def test_credenciais_lista_e_zero(monkeypatch, resposta, indices):
    roteiro(monkeypatch, [resposta])
    assert interface.escolher_credenciais(CAMPOS) == [CAMPOS[i] for i in indices]


def test_credenciais_entrada_invalida(monkeypatch):
    roteiro(monkeypatch, ["9", "x", "1"])
    assert interface.escolher_credenciais(CAMPOS) == [CAMPOS[0]]


def test_senha_mascarada(monkeypatch, capsys):
    perguntas = roteiro(monkeypatch, [""])
    interface.escolher_credenciais(CAMPOS)
    tela = capsys.readouterr().out + "".join(perguntas)
    assert "S3gr3d0!" not in tela
    assert "matheus.p" in tela


def test_sem_campos_nao_pergunta(monkeypatch):
    roteiro(monkeypatch, [])
    assert interface.escolher_credenciais([]) == []


@pytest.mark.parametrize(
    ("resposta", "padrao", "esperado"),
    [("", True, True), ("", False, False), ("s", False, True), ("Sim", False, True), ("N", True, False), ("não", True, False)],
)
def test_sim_nao(monkeypatch, resposta, padrao, esperado):
    roteiro(monkeypatch, [resposta])
    assert interface.perguntar_sim_nao("Continuar?", padrao) is esperado


def test_sim_nao_resposta_invalida(monkeypatch):
    roteiro(monkeypatch, ["talvez", "s"])
    assert interface.perguntar_sim_nao("Continuar?", False) is True


def test_pasta_pelo_seletor(monkeypatch):
    roteiro(monkeypatch, [])
    monkeypatch.setattr(interface, "_seletor_de_pasta", lambda titulo, inicial: "C:/dados")
    assert interface.escolher_pasta("Destino", Path("X")) == Path("C:/dados")


@pytest.mark.parametrize(("digitado", "esperado"), [("", Path("X")), ('"D:\\pasta com espaço"', Path("D:\\pasta com espaço"))])
def test_pasta_seletor_cancelado(monkeypatch, digitado, esperado):
    roteiro(monkeypatch, [digitado])
    monkeypatch.setattr(interface, "_seletor_de_pasta", lambda titulo, inicial: "")
    assert interface.escolher_pasta("Destino", Path("X")) == esperado


def test_blindar_console_nao_falha():
    interface.blindar_console()
