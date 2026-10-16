# -*- coding: utf-8 -*-
"""
Credenciais dos bots: nome das variáveis no .env e gravação segura dos valores.

O set_key do python-dotenv muda de versão para versão (o 1.2.2 só escapa aspas simples, e aí um
valor terminado em "\\" corromperia a linha seguinte; o 1.2.4 escapa também a barra). Por isso a
forma gravada é montada aqui (sem aspas quando é seguro; senão entre aspas simples, com "\\" e "'"
escapadas), o set_key só grava o texto, e a ida e volta é conferida depois de gravar.
Mensagens de erro nunca mostram o valor.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from dotenv import dotenv_values, set_key


class ErroCredencial(Exception):
    """Valor que não pode ser guardado no .env sem ser alterado."""


def nome_variavel(nome_bot: str, rotulo: str, usados: set[str]) -> str:
    """<BOT>_<ROTULO> em maiúsculas ASCII (RELATORIO_SP_SENHA). Registra o nome escolhido em `usados`."""
    prefixo = nome_bot.upper()
    base = _maiusculas_ascii(rotulo)
    if base:
        nome, n = f"{prefixo}_{base}", 2
        while nome in usados:
            nome, n = f"{prefixo}_{base}_{n}", n + 1
    else:
        n = 1
        while f"{prefixo}_CREDENCIAL_{n}" in usados:
            n += 1
        nome = f"{prefixo}_CREDENCIAL_{n}"
    usados.add(nome)
    return nome


def salvar_no_env(caminho_env: Path, valores: dict[str, str]) -> None:
    """Cria ou atualiza as chaves no .env, preservando as outras. Valida tudo antes de gravar."""
    formas = {chave: _forma_no_env(chave, valor) for chave, valor in valores.items()}
    caminho_env.parent.mkdir(parents=True, exist_ok=True)
    for chave, (escrito, modo) in formas.items():
        set_key(caminho_env, chave, escrito, quote_mode=modo)
    lidos = dotenv_values(caminho_env, interpolate=False)
    for chave, valor in valores.items():
        if lidos.get(chave) != valor:
            raise ErroCredencial(f"A credencial {chave} não ficou idêntica em {caminho_env}; corrija-a à mão.")


def _forma_no_env(chave: str, valor: str) -> tuple[str, str]:
    """(texto a gravar, quote_mode do set_key) que o parser do python-dotenv lê de volta igual."""
    if "\n" in valor or "\r" in valor:
        raise ErroCredencial(f"A credencial {chave} tem quebra de linha e não cabe no .env.")
    seguro_sem_aspas = (
        valor == valor.strip()
        and not re.search(r"\s#", valor)  # " #..." seria lido como comentário
        and not valor.startswith(("'", '"'))
    )
    if seguro_sem_aspas:
        return valor, "never"  # lido literalmente: sem escapes, sem interpolação (interpolate=False)
    if valor.endswith("\\"):
        raise ErroCredencial(
            f"A credencial {chave} precisa de aspas e termina com barra invertida: o .env não consegue "
            "guardá-la sem alterar. Cadastre-a à mão como variável de ambiente do Windows."
        )
    # As aspas são montadas aqui e o set_key só grava: o 1.2.2 escapa só "'" e o 1.2.4 escapa também
    # "\\". Os dois parsers decodificam "\\\\" e "\\'" dentro de aspas simples.
    escapado = valor.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escapado}'", "never"


def _maiusculas_ascii(texto: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]+", "_", ascii_.upper()).strip("_")
