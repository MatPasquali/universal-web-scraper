# -*- coding: utf-8 -*-
"""
Conversa com a pessoa no terminal, mais o seletor de pasta do Windows.

Isolado aqui para os outros módulos não dependerem de input()/print() e para os testes
roteirizarem as respostas. Valores que parecem senha nunca aparecem na tela.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

from analisador import CampoDigitado, NavegacaoGravada

NOME_VALIDO = re.compile(r"^[a-z][a-z0-9_]*$")


def blindar_console() -> None:
    """Print nunca pode derrubar o programa no console cp1252 (lição do BOT_LAT_LONG/ETL_SUSEP)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, OSError):
            pass


def slug(texto: str) -> str:
    """Minúsculas, sem acento, só [a-z0-9_]: 'Cotação SP!' -> 'cotacao_sp'."""
    ascii_ = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_.lower()).strip("_")


def perguntar_nome_bot(pasta_bots: Path) -> str:
    while True:
        bruto = input("Nome do novo bot (ex.: cotacao_sp): ")
        nome = slug(bruto)
        if not NOME_VALIDO.match(nome):
            print("  Use letras, números e _, começando com uma letra.")
            continue
        if nome != bruto.strip():
            print(f"  Nome ajustado para: {nome}")
        existente = pasta_bots / f"{nome}.py"
        if existente.exists() and not perguntar_sim_nao(f"  Já existe bots/{nome}.py. Sobrescrever?", False):
            continue
        return nome


def escolher_credenciais(campos: list[CampoDigitado]) -> list[CampoDigitado]:
    """Pergunta quais campos digitados vão para o .env. Enter aceita os que parecem usuário/senha."""
    if not campos:
        return []
    print("\nCampos digitados durante a gravação:")
    for i, campo in enumerate(campos, 1):
        valor = f"(oculto, {len(campo.valor)} caracteres)" if campo.parece_senha else campo.valor
        dica = "   <- parece credencial" if campo.parece_credencial else ""
        print(f"  [{i}] {campo.rotulo}: {valor}{dica}")
    padrao = [i for i, campo in enumerate(campos, 1) if campo.parece_credencial]
    texto_padrao = ",".join(map(str, padrao)) or "0"
    while True:
        resposta = input(
            "Quais são credenciais (vão para o .env, fora do código)? "
            f"Números separados por vírgula, 0 = nenhum [Enter = {texto_padrao}]: "
        ).strip()
        if not resposta:
            escolhidos = padrao
        else:
            try:
                escolhidos = [int(parte) for parte in resposta.replace(";", ",").split(",") if parte.strip()]
            except ValueError:
                print("  Digite números, como 1,2.")
                continue
            if escolhidos == [0]:
                escolhidos = []
            elif not all(1 <= n <= len(campos) for n in escolhidos):
                print(f"  Use números de 1 a {len(campos)}.")
                continue
        return [campos[n - 1] for n in dict.fromkeys(escolhidos)]


def confirmar_navegacoes(navegacoes: list[NavegacaoGravada]) -> set[tuple[int, int]]:
    """
    Para cada endereço gravado logo depois de uma ação, pergunta se a pessoa o digitou.
    Devolve as posições dos que NÃO foram digitados: o bot troca esses por esperar a página.
    """
    automaticas = set()
    for navegacao in navegacoes:
        print(f"\nA gravação abre {navegacao.url}")
        print(f"  logo depois de {navegacao.acao_anterior} na mesma página.")
        print("  Normalmente é o próprio sistema recarregando a página, não algo que você digitou.")
        if not perguntar_sim_nao("  Você digitou esse endereço na barra do Edge?", False):
            automaticas.add(navegacao.posicao)
    return automaticas


def escolher_pasta(titulo: str, padrao: Path) -> Path:
    """Seletor de pasta do Windows; se cancelado (ou sem tkinter), pergunta no terminal."""
    escolhida = _seletor_de_pasta(titulo, padrao)
    if escolhida:
        print(f"  {titulo}: {escolhida}")
        return Path(escolhida)
    resposta = input(f"{titulo} [Enter = {padrao}]: ").strip().strip('"')
    return Path(resposta) if resposta else padrao


def perguntar_sim_nao(pergunta: str, padrao: bool) -> bool:
    sufixo = "[S/n]" if padrao else "[s/N]"
    while True:
        resposta = input(f"{pergunta} {sufixo} ").strip().lower()
        if not resposta:
            return padrao
        if resposta in ("s", "sim", "y", "yes"):
            return True
        if resposta in ("n", "nao", "não", "no"):
            return False
        print("  Responda s ou n.")


def _seletor_de_pasta(titulo: str, inicial: Path) -> str:
    """Janela 'Selecionar pasta' por cima do Edge. '' se a pessoa cancelar ou não houver tkinter."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        raiz = tk.Tk()
        raiz.withdraw()
        raiz.attributes("-topmost", True)
        try:
            existente = next((p for p in (inicial, *inicial.parents) if p.exists()), Path.home())
            return filedialog.askdirectory(parent=raiz, title=titulo, initialdir=str(existente), mustexist=False) or ""
        finally:
            raiz.destroy()
    except Exception:
        return ""
