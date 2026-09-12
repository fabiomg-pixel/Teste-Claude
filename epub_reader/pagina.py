"""Monta o leitor de arquivo único como um documento HTML completo.

`leitor-celular.html` é um fragmento de propósito: é ele que vai publicado como
artifact, e lá o `<head>` quem põe é o publicador. Para as outras três bocas —
o `/celular` do servidor, o asset do APK e o arquivo solto que você abre no
iPhone — falta a moldura: doctype (sem ele o navegador entra em modo quirks, que
não é o modo em que o leitor foi desenhado), `charset` (num `file://` não há
cabeçalho HTTP para dizer que é UTF-8), `viewport` (sem ele o Safari desenha a
página com 980px e encolhe tudo) e as metas de «Adicionar à Tela de Início».

A moldura vive em `moldura-celular.html` para que o Gradle possa usar a mesma,
sem passar por aqui.

    python pagina.py leitor-iphone.html
"""

from __future__ import annotations

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MARCA = "<!--LEITOR-->"


def montar(base_dir: str = BASE_DIR) -> str:
    with open(os.path.join(base_dir, "moldura-celular.html"), encoding="utf-8") as fh:
        moldura = fh.read()
    with open(os.path.join(base_dir, "leitor-celular.html"), encoding="utf-8") as fh:
        leitor = fh.read()
    if MARCA not in moldura:
        raise RuntimeError(f"moldura-celular.html sem {MARCA}")
    return moldura.replace(MARCA, leitor)


if __name__ == "__main__":
    saida = sys.argv[1] if len(sys.argv) > 1 else "leitor-completo.html"
    pagina = montar()
    with open(saida, "w", encoding="utf-8") as fh:
        fh.write(pagina)
    print(f"{saida}: {len(pagina.encode('utf-8')) / 1024:.0f} KB")
