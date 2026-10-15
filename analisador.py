# -*- coding: utf-8 -*-
"""
Analisador da gravação: lê o script Python gerado pelo codegen do Playwright 1.61 e
extrai os passos, os campos digitados e os downloads.

O script bruto tem as senhas em texto puro: este módulo só lê, nunca grava nem imprime
valores digitados (nem nas mensagens de erro).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

PARECE_SENHA = re.compile(r"senha|password|passwd|\bpass\b|pwd", re.IGNORECASE)
PARECE_CREDENCIAL = re.compile(r"usu[aá]rio|\buser|login|e-?mail|cpf|token", re.IGNORECASE)

# Localizadores cujo 1º argumento descreve o alvo (get_by_role é tratado à parte: usa name=).
_LOCALIZADORES_TEXTO = {
    "get_by_label", "get_by_placeholder", "get_by_text", "get_by_test_id",
    "get_by_alt_text", "get_by_title", "locator",
}


class ErroGravacao(Exception):
    """A gravação não está no formato que o codegen do Playwright gera."""


@dataclass(frozen=True)
class CampoDigitado:
    """Um `.fill("...")` da gravação. `posicao` = (linha, coluna) da chamada no script gravado."""

    posicao: tuple[int, int]
    rotulo: str
    valor: str
    parece_credencial: bool
    parece_senha: bool


@dataclass(frozen=True)
class DownloadGravado:
    """Um bloco `with page.expect_download() as <variavel>_info:` e o rótulo da ação que o disparou."""

    variavel: str
    gatilho: str


@dataclass(frozen=True)
class NavegacaoGravada:
    """
    `page.goto()` gravado logo depois de uma ação na mesma página. Pode ter sido digitado na barra,
    mas o codegen também grava assim o próprio sistema recarregando a página (postback depois de
    check/select, ou navegação que demorou mais de 5 s) — e repetir o goto desfaz o que a ação fez.
    """

    posicao: tuple[int, int]
    pagina: str
    url: str
    acao_anterior: str


@dataclass(frozen=True)
class Gravacao:
    passos: list[ast.stmt]
    campos: list[CampoDigitado]
    downloads: list[DownloadGravado]
    navegacoes_apos_acao: list[NavegacaoGravada] = field(default_factory=list)

    @property
    def vazia(self) -> bool:
        """True quando a pessoa fechou o Edge sem fazer nada (só abriu/fechou páginas)."""
        return all(_abre_ou_fecha_pagina(p) for p in self.passos)


def analisar(codigo: str) -> Gravacao:
    try:
        arvore = ast.parse(codigo)
    except SyntaxError as erro:
        # Sem erro.text: a linha com problema pode conter uma senha.
        raise ErroGravacao(f"A gravação não é um script Python válido ({erro.msg}, linha {erro.lineno}).") from None
    run = next((n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == "run"), None)
    if run is None:
        raise ErroGravacao("Não encontrei a função run() que o gravador do Playwright gera.")
    passos = [p for p in run.body if not _eh_boilerplate(p)]
    return Gravacao(
        passos=passos,
        campos=_campos(passos),
        downloads=_downloads(passos),
        navegacoes_apos_acao=_navegacoes_apos_acao(passos),
    )


def pagina_da_acao(chamada: ast.Call) -> str:
    """Variável da página em que a ação acontece (page, page1, ...); '' se a chamada não é de página."""
    no: ast.AST = chamada.func
    while isinstance(no, (ast.Attribute, ast.Call)):
        no = no.value if isinstance(no, ast.Attribute) else no.func
    return no.id if isinstance(no, ast.Name) and no.id.startswith("page") else ""


def rotulo_do_alvo(chamada: ast.Call) -> str:
    """
    Descreve o alvo de uma ação a partir do localizador mais próximo dela:
    name= do get_by_role (ou o papel), 1º argumento de get_by_label/placeholder/text/...,
    seletor do locator(). Vazio se nada for reconhecido.
    """
    no = chamada.func.value if isinstance(chamada.func, ast.Attribute) else None
    while no is not None:
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
            metodo = no.func.attr
            if metodo == "get_by_role":
                nome = next((k.value for k in no.keywords if k.arg == "name"), None)
                texto = _texto(nome) or (_texto(no.args[0]) if no.args else "")
                if texto:
                    return texto
            elif metodo in _LOCALIZADORES_TEXTO and no.args:
                texto = _texto(no.args[0])
                if texto:
                    return texto
            no = no.func.value
        elif isinstance(no, ast.Attribute):
            no = no.value
        else:
            no = None
    return ""


def _texto(no: ast.AST | None) -> str:
    """Texto literal de um argumento: "..." ou re.compile("...")."""
    if isinstance(no, ast.Constant) and isinstance(no.value, str):
        return no.value
    if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute) and no.func.attr == "compile" and no.args:
        return _texto(no.args[0])
    return ""


def _eh_boilerplate(passo: ast.stmt) -> bool:
    """Linhas de abrir/fechar o navegador, que o bot gerado faz por conta própria."""
    if isinstance(passo, ast.Assign) and len(passo.targets) == 1:
        alvo = passo.targets[0]
        return isinstance(alvo, ast.Name) and alvo.id in ("browser", "context")
    if isinstance(passo, ast.Expr) and isinstance(passo.value, ast.Call):
        func = passo.value.func
        return (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id in ("browser", "context")
            and func.attr in ("close", "storage_state")
        )
    return False


def _abre_ou_fecha_pagina(passo: ast.stmt) -> bool:
    if isinstance(passo, ast.Assign) and isinstance(passo.value, ast.Call):
        func = passo.value.func
        return isinstance(func, ast.Attribute) and func.attr == "new_page"
    if isinstance(passo, ast.Expr) and isinstance(passo.value, ast.Call):
        func = passo.value.func
        return isinstance(func, ast.Attribute) and func.attr == "close" and isinstance(func.value, ast.Name)
    return False


def _eh_fill_com_texto(no: ast.AST) -> bool:
    return (
        isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and no.func.attr == "fill"
        and len(no.args) == 1
        and isinstance(no.args[0], ast.Constant)
        and isinstance(no.args[0].value, str)
    )


def _campos(passos: list[ast.stmt]) -> list[CampoDigitado]:
    chamadas = sorted(
        (no for passo in passos for no in ast.walk(passo) if _eh_fill_com_texto(no)),
        key=lambda no: (no.lineno, no.col_offset),
    )
    campos = []
    for i, chamada in enumerate(chamadas, 1):
        rotulo = rotulo_do_alvo(chamada) or f"campo {i}"
        senha = bool(PARECE_SENHA.search(rotulo))
        campos.append(
            CampoDigitado(
                posicao=(chamada.lineno, chamada.col_offset),
                rotulo=rotulo,
                valor=chamada.args[0].value,
                parece_credencial=senha or bool(PARECE_CREDENCIAL.search(rotulo)),
                parece_senha=senha,
            )
        )
    return campos


def _downloads(passos: list[ast.stmt]) -> list[DownloadGravado]:
    achados = []
    for passo in passos:
        if not isinstance(passo, ast.With):
            continue
        for item in passo.items:
            contexto = item.context_expr
            if (
                isinstance(contexto, ast.Call)
                and isinstance(contexto.func, ast.Attribute)
                and contexto.func.attr == "expect_download"
                and isinstance(item.optional_vars, ast.Name)
            ):
                acao = _primeira_acao(passo.body)
                gatilho = rotulo_do_alvo(acao) if acao is not None else ""
                achados.append(
                    DownloadGravado(
                        variavel=item.optional_vars.id.removesuffix("_info"),
                        gatilho=gatilho or "ação sem rótulo",
                    )
                )
    return achados


def _navegacoes_apos_acao(passos: list[ast.stmt]) -> list[NavegacaoGravada]:
    """Gotos de topo cuja página teve, por último, uma ação que não foi navegação."""
    ultima_acao: dict[str, str] = {}  # página -> descrição da última ação (sem valores digitados)
    achadas = []
    for passo in passos:
        acao = _acao_do_passo(passo)
        pagina = pagina_da_acao(acao) if acao is not None else ""
        if not pagina:
            continue
        metodo = acao.func.attr if isinstance(acao.func, ast.Attribute) else ""
        if metodo == "goto":
            url = _texto(acao.args[0]) if acao.args else ""
            if isinstance(passo, ast.Expr) and url and pagina in ultima_acao:
                achadas.append(NavegacaoGravada((acao.lineno, acao.col_offset), pagina, url, ultima_acao[pagina]))
            ultima_acao.pop(pagina, None)
        elif metodo not in ("once", "on"):
            rotulo = rotulo_do_alvo(acao)
            ultima_acao[pagina] = f"{metodo} em '{rotulo}'" if rotulo else metodo
    return achadas


def _acao_do_passo(passo: ast.stmt) -> ast.Call | None:
    if isinstance(passo, ast.Expr) and isinstance(passo.value, ast.Call):
        return passo.value
    if isinstance(passo, ast.With):
        return _primeira_acao(passo.body)
    return None


def _primeira_acao(corpo: list[ast.stmt]) -> ast.Call | None:
    """1ª chamada do corpo de um with (desce em with aninhado, ex.: pop-up dentro de download)."""
    for passo in corpo:
        if isinstance(passo, ast.Expr) and isinstance(passo.value, ast.Call):
            return passo.value
        if isinstance(passo, ast.With):
            acao = _primeira_acao(passo.body)
            if acao is not None:
                return acao
    return None
