# -*- coding: utf-8 -*-
"""
Gravador: abre o Microsoft Edge vazio com o codegen do Playwright e devolve o script
Python que ele gravou quando a pessoa fecha a janela.

O script bruto tem as senhas em texto puro: ele só existe numa pasta temporária,
apagada assim que é lido.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

LINHAS_DE_ERRO = 15  # fim do stderr mostrado quando o codegen falha
INTERVALO_S = 0.2  # time.sleep pode ser interrompido pelo Ctrl+C; esperar o processo direto não


class ErroGravador(Exception):
    """O codegen do Playwright não conseguiu abrir ou gravar."""


def comando_codegen(saida: Path) -> list[str]:
    return [
        sys.executable, "-m", "playwright", "codegen",
        "--channel", "msedge", "--target", "python", "-o", str(saida),
    ]


def gravar() -> str:
    """Bloqueia até a pessoa fechar o Edge. Devolve o script gravado ('' se nada foi gravado)."""
    with tempfile.TemporaryDirectory(prefix="webscraper_", ignore_cleanup_errors=True) as pasta:
        saida = Path(pasta) / "gravacao.py"
        caminho_erros = Path(pasta) / "erros.txt"
        with open(caminho_erros, "w", encoding="utf-8") as erros:
            processo = subprocess.Popen(comando_codegen(saida), stdout=subprocess.DEVNULL, stderr=erros)
            try:
                while processo.poll() is None:
                    time.sleep(INTERVALO_S)
            except BaseException:  # Ctrl+C: não deixar o Edge aberto sem dono
                _encerrar_arvore(processo.pid)
                raise
        if saida.exists():
            return saida.read_text(encoding="utf-8")
        if processo.returncode != 0:
            linhas = caminho_erros.read_text(encoding="utf-8", errors="replace").strip().splitlines()
            fim = "\n".join(linhas[-LINHAS_DE_ERRO:])
            raise ErroGravador(f"O gravador do Playwright falhou (código {processo.returncode}):\n{fim}")
        return ""


def _encerrar_arvore(pid: int) -> None:
    """No Windows, matar o `python -m playwright` não mata o node nem o Edge que ele abriu."""
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
