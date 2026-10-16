# -*- coding: utf-8 -*-
"""
Ponta a ponta: gravação -> bot gerado -> bot rodando no Edge (headless) contra o site demo.

O site demo demora 1,5 s para filtrar e deixa "Exportar CSV" sempre habilitado, com um confirm():
só um bot que espera a rede e aceita o diálogo baixa a base filtrada.
"""
import importlib.util
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from analisador import analisar
from credenciais import nome_variavel, salvar_no_env
from gerador_bot import gerar_bot

PASTA_TESTES = Path(__file__).parent
EDGE = (
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
)
pytestmark = pytest.mark.skipif(not any(p.exists() for p in EDGE), reason="Microsoft Edge não instalado")


def _modulo_servidor():
    caminho = PASTA_TESTES / "site_demo" / "servidor.py"
    spec = importlib.util.spec_from_file_location("servidor_demo", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def servidor_demo():
    servidor = _modulo_servidor().iniciar()
    yield f"http://127.0.0.1:{servidor.server_address[1]}/"
    servidor.shutdown()
    servidor.server_close()


def preparar_bot(
    raiz: Path, url: str, destino: Path, gravar_env: bool = True, fixture: str = "gravacao_site_demo.py"
) -> Path:
    texto = (PASTA_TESTES / "fixtures" / fixture).read_text(encoding="utf-8")
    gravacao = analisar(texto.replace("http://127.0.0.1:PORTA/", url))
    marcados = [c for c in gravacao.campos if c.parece_credencial]
    usados: set[str] = set()
    variaveis = {c.posicao: nome_variavel("demo", c.rotulo, usados) for c in marcados}
    if gravar_env:
        salvar_no_env(raiz / ".env", {variaveis[c.posicao]: c.valor for c in marcados})
    destinos = {d.variavel: destino for d in gravacao.downloads}
    bot = raiz / "bots" / "demo.py"
    bot.parent.mkdir(parents=True)
    bot.write_text(gerar_bot(gravacao, "demo", variaveis, destinos, datetime.now()), encoding="utf-8")
    return bot


def rapido(bot: Path) -> None:
    """Timeout curto para os testes em que um passo precisa falhar."""
    codigo = bot.read_text(encoding="utf-8").replace("TIMEOUT_MS = 60_000", "TIMEOUT_MS = 3_000")
    bot.write_text(codigo, encoding="utf-8")


def linhas_csv(arquivo: Path) -> list[list[str]]:
    linhas = arquivo.read_text(encoding="utf-8").splitlines()
    assert linhas[0] == "local;produto;premio"
    return [linha.split(";") for linha in linhas[1:]]


def rodar(bot: Path, cwd: Path) -> subprocess.CompletedProcess:
    cwd.mkdir(exist_ok=True)
    return subprocess.run(
        [sys.executable, str(bot), "--headless"],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )


def test_bot_gerado_baixa_base_filtrada(tmp_path, servidor_demo):
    raiz = tmp_path / "Projetos para Portfólio"
    destino = tmp_path / "pasta com espaço" / "Relatórios"
    bot = preparar_bot(raiz, servidor_demo, destino)

    r = rodar(bot, tmp_path / "outro")  # roda de outro cwd: .env e logs vêm de Path(__file__)

    assert r.returncode == 0, r.stdout + r.stderr
    linhas = (destino / "registros.csv").read_text(encoding="utf-8").splitlines()
    assert linhas[0] == "local;produto;premio"
    assert len(linhas) > 1
    assert all(linha.startswith("SP;") for linha in linhas[1:])
    assert (raiz / "logs" / "demo.log").exists()


def test_sem_espera_a_base_sai_errada(tmp_path, servidor_demo):
    """Garante que o site demo tem a corrida: sem aguardar_rede o bot exporta antes do filtro."""
    destino = tmp_path / "destino"
    bot = preparar_bot(tmp_path / "projeto", servidor_demo, destino)
    codigo = bot.read_text(encoding="utf-8").splitlines()
    bot.write_text("\n".join(l for l in codigo if l.strip() != "aguardar_rede(page)"), encoding="utf-8")

    r = rodar(bot, tmp_path / "outro")

    assert r.returncode == 0, r.stdout + r.stderr
    linhas = (destino / "registros.csv").read_text(encoding="utf-8").splitlines()
    assert linhas[1:] == [] or any(not linha.startswith("SP;") for linha in linhas[1:])


def test_senha_nunca_aparece_no_log_quando_o_bot_falha(tmp_path, servidor_demo):
    """O Playwright põe o texto digitado no erro do fill: o log tem que trocar a senha por ***."""
    raiz = tmp_path / "projeto"
    bot = preparar_bot(raiz, servidor_demo + "?bloqueado=1", tmp_path / "destino")  # senha somente leitura
    rapido(bot)

    r = rodar(bot, raiz)

    assert r.returncode == 1, r.stdout + r.stderr
    log = (raiz / "logs" / "demo.log").read_text(encoding="utf-8")
    assert 'fill("***")' in log  # o erro do Playwright foi registrado, já sem a senha
    assert "demo123" not in log
    assert "demo123" not in r.stdout + r.stderr


def test_busca_enquanto_digita_espera_o_filtro(tmp_path, servidor_demo):
    destino = tmp_path / "destino"
    bot = preparar_bot(tmp_path / "projeto", servidor_demo, destino, fixture="gravacao_site_demo_busca.py")

    r = rodar(bot, tmp_path / "outro")

    assert r.returncode == 0, r.stdout + r.stderr
    linhas = linhas_csv(destino / "registros.csv")
    assert linhas and all(produto == "Auto" for _, produto, _ in linhas)


def test_janela_de_escolha_que_se_fecha(tmp_path, servidor_demo):
    destino = tmp_path / "destino"
    bot = preparar_bot(tmp_path / "projeto", servidor_demo, destino, fixture="gravacao_site_demo_lupa.py")

    r = rodar(bot, tmp_path / "outro")

    assert r.returncode == 0, r.stdout + r.stderr
    linhas = linhas_csv(destino / "registros.csv")
    assert linhas and all(local == "SP" for local, _, _ in linhas)


def test_espera_continua_quando_a_janela_fecha(tmp_path, servidor_demo):
    """Sem a espera antes do download, só o aguardar_rede(page1) — com a lupa já fechada — segura o bot."""
    destino = tmp_path / "destino"
    bot = preparar_bot(tmp_path / "projeto", servidor_demo, destino, fixture="gravacao_site_demo_lupa.py")
    linhas = bot.read_text(encoding="utf-8").splitlines()
    i = next(i for i, l in enumerate(linhas) if l.strip().startswith("with page.expect_download()"))
    if linhas[i - 1].strip() == "aguardar_rede(page)":
        del linhas[i - 1]
    bot.write_text("\n".join(linhas), encoding="utf-8")

    r = rodar(bot, tmp_path / "outro")

    assert r.returncode == 0, r.stdout + r.stderr
    linhas = linhas_csv(destino / "registros.csv")
    assert linhas and all(local == "SP" for local, _, _ in linhas)


def test_download_em_janela_nova_nao_se_perde(tmp_path, servidor_demo):
    """O codegen não liga esse download a nenhuma ação: o bot salva assim mesmo, em downloads/<nome>."""
    raiz = tmp_path / "projeto"
    bot = preparar_bot(raiz, servidor_demo, tmp_path / "destino", fixture="gravacao_site_demo_janela.py")

    r = rodar(bot, tmp_path / "outro")

    assert r.returncode == 0, r.stdout + r.stderr
    arquivo = raiz / "downloads" / "demo" / "registros_servidor.csv"
    linhas = linhas_csv(arquivo)
    assert linhas and all(local == "SP" for local, _, _ in linhas)
    assert "não estava na gravação" in (raiz / "logs" / "demo.log").read_text(encoding="utf-8")


def test_bot_sem_credencial_sai_com_2(tmp_path, servidor_demo):
    raiz = tmp_path / "projeto"
    bot = preparar_bot(raiz, servidor_demo, tmp_path / "destino", gravar_env=False)

    r = rodar(bot, raiz)

    assert r.returncode == 2, r.stdout + r.stderr
    assert "DEMO_USUARIO" in r.stderr and "DEMO_SENHA" in r.stderr
    assert not (tmp_path / "destino").exists()
