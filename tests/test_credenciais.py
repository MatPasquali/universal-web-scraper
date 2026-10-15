# -*- coding: utf-8 -*-
"""Nomes das variáveis de credencial e gravação no .env."""
import pytest
from dotenv import dotenv_values

from credenciais import ErroCredencial, nome_variavel, salvar_no_env


def test_nome_variavel_basico():
    assert nome_variavel("cotacao_sp", "Senha", set()) == "COTACAO_SP_SENHA"


@pytest.mark.parametrize(
    ("rotulo", "esperado"),
    [("Usuário", "COTACAO_SP_USUARIO"), ("E-mail", "COTACAO_SP_E_MAIL"), ("#pwd", "COTACAO_SP_PWD")],
)
def test_nome_variavel_sem_acento_e_simbolos(rotulo, esperado):
    assert nome_variavel("cotacao_sp", rotulo, set()) == esperado


def test_nome_variavel_colisao():
    usados = {"COTACAO_SP_SENHA"}
    assert nome_variavel("cotacao_sp", "Senha", usados) == "COTACAO_SP_SENHA_2"
    assert "COTACAO_SP_SENHA_2" in usados
    assert nome_variavel("cotacao_sp", "Senha", usados) == "COTACAO_SP_SENHA_3"


def test_nome_variavel_rotulo_vazio():
    usados: set[str] = set()
    assert nome_variavel("cotacao_sp", "", usados) == "COTACAO_SP_CREDENCIAL_1"
    assert nome_variavel("cotacao_sp", "***", usados) == "COTACAO_SP_CREDENCIAL_2"


def test_salvar_cria_arquivo_e_preserva_outras_chaves(tmp_path):
    env = tmp_path / "projeto" / ".env"
    salvar_no_env(env, {"A": "1"})
    salvar_no_env(env, {"B": "2"})
    salvar_no_env(env, {"A": "3"})
    assert dotenv_values(env, interpolate=False) == {"A": "3", "B": "2"}


@pytest.mark.parametrize(
    "valor",
    [
        "p@ss 'w\"$x#1\\",      # termina em barra invertida
        "  espaços #1 ",         # espaços nas pontas e " #" (seria comentário)
        "'aspas' no início",
        " a\\b ",                # barra no meio de um valor que precisa de aspas
        "a\\\\b",                # duas barras seguidas
        "${HOME}",               # não pode ser interpolado
    ],
)
def test_ida_e_volta_pelo_dotenv(tmp_path, valor):
    env = tmp_path / ".env"
    salvar_no_env(env, {"K": valor, "Z": "fim"})
    lido = dotenv_values(env, interpolate=False)
    assert lido["K"] == valor
    assert lido["Z"] == "fim"


def test_valor_impossivel_gera_erro_sem_gravar(tmp_path):
    env = tmp_path / ".env"
    with pytest.raises(ErroCredencial):
        salvar_no_env(env, {"OK": "abc", "K": " x\\"})
    assert not env.exists() or "OK" not in dotenv_values(env)
