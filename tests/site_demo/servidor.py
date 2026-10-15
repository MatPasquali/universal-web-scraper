# -*- coding: utf-8 -*-
"""
Site de demonstração (sistema de cotações fictício) para testar e mostrar os bots.

    python tests/site_demo/servidor.py [porta]     # padrão 8000 - usuário demo, senha demo123

A busca de cotações demora ATRASO_S de propósito e o botão "Exportar CSV" fica sempre
habilitado: um bot que não espera a rede acalmar exporta a base errada.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PASTA = Path(__file__).resolve().parent
ATRASO_S = 1.5
COTACOES = [
    {"local": "SP", "produto": "Auto", "premio": "1200.50"},
    {"local": "SP", "produto": "Residencial", "premio": "430.00"},
    {"local": "RJ", "produto": "Auto", "premio": "1350.90"},
    {"local": "RJ", "produto": "Vida", "premio": "220.00"},
]


class Manipulador(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PASTA), **kwargs)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path != "/api/cotacoes":
            super().do_GET()
            return
        local = parse_qs(url.query).get("local", ["Todos"])[0]
        time.sleep(ATRASO_S)
        corpo = json.dumps([c for c in COTACOES if local in ("Todos", c["local"])]).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, formato, *args) -> None:
        pass  # silencioso nos testes


def iniciar(porta: int = 0) -> ThreadingHTTPServer:
    """Sobe o site numa thread daemon (porta 0 = livre). Pare com shutdown() + server_close()."""
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), Manipulador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), Manipulador)
    print(f"Site demo em http://127.0.0.1:{porta}/ (usuário demo, senha demo123). Ctrl+C para parar.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
