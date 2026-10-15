# -*- coding: utf-8 -*-
"""Gravador: roda o codegen do Playwright no Edge e devolve o script gravado."""
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import gravador

FIXTURE = (Path(__file__).parent / "fixtures" / "gravacao_login_download.py").read_text(encoding="utf-8")


def test_comando_codegen(tmp_path):
    saida = tmp_path / "gravacao.py"
    assert gravador.comando_codegen(saida) == [
        sys.executable, "-m", "playwright", "codegen",
        "--channel", "msedge", "--target", "python", "-o", str(saida),
    ]


def falso_popen(escrever: str | None, codigo_saida: int = 0, erros: str = "", interromper: bool = False):
    """Imita o codegen: ao terminar, escreve (ou não) o script no -o e o stderr no arquivo recebido."""
    criados = []

    class Processo:
        pid = 4242

        def __init__(self, comando, stdout=None, stderr=None):
            self.saida = Path(comando[comando.index("-o") + 1])
            self.stderr = stderr
            self.returncode = None
            criados.append(self)

        def poll(self):
            if interromper:
                return None
            if escrever is not None:
                self.saida.write_text(escrever, encoding="utf-8")
            self.stderr.write(erros)
            self.returncode = codigo_saida
            return codigo_saida

    return Processo, criados


def test_gravar_devolve_texto_e_apaga_tmp(monkeypatch):
    processo, criados = falso_popen(FIXTURE)
    monkeypatch.setattr(gravador.subprocess, "Popen", processo)

    assert gravador.gravar() == FIXTURE
    assert not criados[0].saida.parent.exists()  # o script bruto tem a senha: não pode sobrar


def test_gravar_sem_arquivo_e_erro(monkeypatch):
    processo, _ = falso_popen(None, codigo_saida=1, erros="browserType.launch: Edge não encontrado")
    monkeypatch.setattr(gravador.subprocess, "Popen", processo)

    with pytest.raises(gravador.ErroGravador, match="Edge não encontrado"):
        gravador.gravar()


def test_gravar_sem_arquivo_e_sucesso(monkeypatch):
    processo, _ = falso_popen(None)
    monkeypatch.setattr(gravador.subprocess, "Popen", processo)

    assert gravador.gravar() == ""


def test_pasta_temporaria_apagada_mesmo_com_arquivo_preso(monkeypatch):
    """Logo após o taskkill o Windows ainda pode segurar o arquivo: insiste antes de desistir."""
    processo, criados = falso_popen(FIXTURE)
    falhas = []

    def rmtree_teimoso(caminho):
        if len(falhas) < 2:
            falhas.append(caminho)
            raise PermissionError("arquivo em uso")
        shutil.rmtree(caminho)

    monkeypatch.setattr(gravador.subprocess, "Popen", processo)
    monkeypatch.setattr(gravador, "shutil", SimpleNamespace(rmtree=rmtree_teimoso))
    monkeypatch.setattr(gravador.time, "sleep", lambda _segundos: None)

    assert gravador.gravar() == FIXTURE
    assert len(falhas) == 2
    assert not criados[0].saida.parent.exists()


def test_avisa_quando_nao_consegue_apagar(monkeypatch, capsys):
    processo, criados = falso_popen(FIXTURE)

    def rmtree_sempre_falha(caminho):
        raise PermissionError("arquivo em uso")

    monkeypatch.setattr(gravador.subprocess, "Popen", processo)
    monkeypatch.setattr(gravador, "shutil", SimpleNamespace(rmtree=rmtree_sempre_falha))
    monkeypatch.setattr(gravador.time, "sleep", lambda _segundos: None)
    try:
        assert gravador.gravar() == FIXTURE
        aviso = capsys.readouterr().err
        assert str(criados[0].saida.parent) in aviso and "senha" in aviso
    finally:
        shutil.rmtree(criados[0].saida.parent, ignore_errors=True)


def test_ctrl_c_encerra_a_arvore_de_processos(monkeypatch):
    """O python -m playwright só embrulha o node: matar só ele deixaria o node e o Edge abertos."""
    processo, criados = falso_popen(None, interromper=True)
    comandos = []

    def ctrl_c(_segundos):
        raise KeyboardInterrupt

    monkeypatch.setattr(gravador.subprocess, "Popen", processo)
    monkeypatch.setattr(gravador.subprocess, "run", lambda comando, **kw: comandos.append(comando))
    monkeypatch.setattr(gravador.time, "sleep", ctrl_c)

    with pytest.raises(KeyboardInterrupt):
        gravador.gravar()
    assert comandos == [["taskkill", "/PID", "4242", "/T", "/F"]]
    assert not criados[0].saida.parent.exists()
