# -*- coding: utf-8 -*-
"""
Gerador do bot: transforma os passos gravados e preenche o modelo_bot.py.tpl.

Transformações nos passos (ver spec):
  - fill("<valor marcado como credencial>")  ->  fill(credencial("<VARIAVEL_DO_ENV>"))
  - dialog.dismiss()  ->  dialog.accept()  (o codegen sempre escreve dismiss)
  - log.info("Passo i/n") antes de cada passo
  - salvar_download(...) depois de cada download e aguardar_rede(...) depois de cada ação interativa
"""

from __future__ import annotations

import ast
import copy
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from string import Template

from analisador import Gravacao

MODELO = Path(__file__).resolve().parent / "modelo_bot.py.tpl"
ACOES_INTERATIVAS = {"click", "dblclick", "press", "select_option", "check", "uncheck", "goto", "set_input_files"}
TAMANHO_MINIMO_VAZAMENTO = 4  # valores menores dariam falso positivo em qualquer texto
TAMANHO_MAXIMO_DESCRICAO = 120


class ErroGeracao(Exception):
    """O código do bot não pôde ser gerado."""


class CredencialVazada(ErroGeracao):
    """Um valor marcado como credencial aparece em outro ponto da gravação (ex.: numa URL)."""


def gerar_bot(
    gravacao: Gravacao,
    nome_bot: str,
    variaveis: dict[tuple[int, int], str],
    destinos: dict[str, Path],
    gerado_em: datetime,
) -> str:
    """Código-fonte completo de bots/<nome_bot>.py. `variaveis`: posição do campo -> variável do .env."""
    marcados = [c for c in gravacao.campos if c.posicao in variaveis]
    valor_para_variavel = {c.valor: variaveis[c.posicao] for c in marcados}
    passos = [_TrocaCredenciais(valor_para_variavel).visit(copy.deepcopy(p)) for p in gravacao.passos]
    _checar_vazamento(passos, marcados)

    constantes = {d.variavel: f"DESTINO_DOWNLOAD_{i}" for i, d in enumerate(gravacao.downloads, 1)}
    nomes_env = list(dict.fromkeys(variaveis[c.posicao] for c in marcados))
    codigo = Template(MODELO.read_text(encoding="utf-8")).substitute(
        nome_bot=nome_bot,
        gerado_em=gerado_em.strftime("%d/%m/%Y %H:%M"),
        variaveis_doc="\n".join(f"    {nome}" for nome in nomes_env) or "    (nenhuma)",
        python=sys.executable,
        variaveis_env=repr(tuple(nomes_env)),
        destinos=_constantes_destino(destinos, constantes),
        passos=textwrap.indent(_montar_corpo(passos, constantes), "    "),
    )
    try:
        compile(codigo, f"{nome_bot}.py", "exec")
    except SyntaxError as erro:
        raise ErroGeracao(f"O código gerado para o bot não é válido ({erro.msg}, linha {erro.lineno}).") from None
    return codigo


class _TrocaCredenciais(ast.NodeTransformer):
    def __init__(self, valor_para_variavel: dict[str, str]) -> None:
        self.valor_para_variavel = valor_para_variavel

    def visit_Call(self, no: ast.Call) -> ast.Call:
        self.generic_visit(no)
        if (
            isinstance(no.func, ast.Attribute)
            and no.func.attr == "fill"
            and len(no.args) == 1
            and isinstance(no.args[0], ast.Constant)
            and no.args[0].value in self.valor_para_variavel
        ):
            variavel = self.valor_para_variavel[no.args[0].value]
            no.args[0] = ast.Call(func=ast.Name("credencial", ast.Load()), args=[ast.Constant(variavel)], keywords=[])
        return no

    def visit_Attribute(self, no: ast.Attribute) -> ast.Attribute:
        self.generic_visit(no)
        if no.attr == "dismiss" and isinstance(no.value, ast.Name) and no.value.id == "dialog":
            no.attr = "accept"
        return no


def _checar_vazamento(passos: list[ast.stmt], marcados: list) -> None:
    """Nenhum valor marcado como credencial pode sobrar em texto dos passos (ex.: https://usuario:senha@...)."""
    argumentos_credencial = {
        id(no.args[0])
        for passo in passos
        for no in ast.walk(passo)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id == "credencial"
    }
    textos = [
        no.value
        for passo in passos
        for no in ast.walk(passo)
        if isinstance(no, ast.Constant) and isinstance(no.value, str) and id(no) not in argumentos_credencial
    ]
    for campo in marcados:
        if len(campo.valor) >= TAMANHO_MINIMO_VAZAMENTO and any(campo.valor in texto for texto in textos):
            raise CredencialVazada(
                f'O valor do campo "{campo.rotulo}" também aparece em outro ponto da gravação '
                "(por exemplo, dentro de um endereço). Para não deixar a credencial no código, "
                "o bot não foi gerado. Se esse campo não for secreto, não o marque como credencial."
            )


def _montar_corpo(passos: list[ast.stmt], constantes: dict[str, str]) -> str:
    total = len(passos)
    linhas = []
    for i, passo in enumerate(passos, 1):
        codigo = ast.unparse(passo)
        descricao = codigo.splitlines()[0]
        if len(descricao) > TAMANHO_MAXIMO_DESCRICAO:
            descricao = descricao[: TAMANHO_MAXIMO_DESCRICAO - 3] + "..."
        linhas.append(f"log.info('Passo %d/%d: %s', {i}, {total}, {descricao!r})")
        linhas.append(codigo)
        depois = _depois_do_passo(passo, constantes)
        if depois:
            linhas.append(depois)
    return "\n".join(linhas) or "pass"


def _depois_do_passo(passo: ast.stmt, constantes: dict[str, str]) -> str:
    """salvar_download após `downloadN = downloadN_info.value`; aguardar_rede após pop-up e ações interativas."""
    if isinstance(passo, ast.Assign) and len(passo.targets) == 1 and isinstance(passo.targets[0], ast.Name):
        alvo, valor = passo.targets[0].id, passo.value
        if (
            isinstance(valor, ast.Attribute)
            and valor.attr == "value"
            and isinstance(valor.value, ast.Name)
            and valor.value.id.endswith("_info")
        ):
            if alvo in constantes:
                return f"salvar_download({alvo}, {constantes[alvo]})"
            if alvo.startswith("page"):
                return f"aguardar_rede({alvo})"
        return ""
    if isinstance(passo, ast.Expr) and isinstance(passo.value, ast.Call):
        func = passo.value.func
        if isinstance(func, ast.Attribute) and func.attr in ACOES_INTERATIVAS:
            raiz = _raiz(passo.value)
            if raiz.startswith("page"):
                return f"aguardar_rede({raiz})"
    return ""


def _raiz(chamada: ast.Call) -> str:
    """Nome da variável da página em que a ação acontece (page, page1, ...)."""
    no: ast.AST = chamada.func
    while isinstance(no, (ast.Attribute, ast.Call)):
        no = no.value if isinstance(no, ast.Attribute) else no.func
    return no.id if isinstance(no, ast.Name) else ""


def _constantes_destino(destinos: dict[str, Path], constantes: dict[str, str]) -> str:
    linhas = []
    for variavel, constante in constantes.items():
        if variavel not in destinos:
            raise ErroGeracao(f"Falta a pasta de destino do download '{variavel}'.")
        linhas.append(f"{constante} = Path({str(destinos[variavel])!r})")
    return "\n".join(linhas) or "# (nenhum download gravado)"
