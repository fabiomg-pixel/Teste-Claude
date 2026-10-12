#!/usr/bin/env python3
"""Reconstrói campanha/dashboard/index.html a partir do template e do estado.

Uso: python3 campanha/ferramentas/atualizar_dashboard.py [--check]

Lê  campanha/estado/estado.json  e  campanha/dashboard/template.html,
injeta o JSON no bloco <script id="estado-json"> e escreve index.html.
--check apenas valida o JSON e os campos obrigatórios.
"""
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ESTADO = RAIZ / "estado" / "estado.json"
TEMPLATE = RAIZ / "dashboard" / "template.html"
SAIDA = RAIZ / "dashboard" / "index.html"
MARCADOR_INI = '<script id="estado-json" type="application/json">'
MARCADOR_FIM = "</script>"

OBRIGATORIOS = ["campanha", "tempo", "local", "cena", "missoes", "jornal", "npcs", "lugares", "rolagens", "combate", "companheiros"]


def validar(estado: dict) -> list[str]:
    erros = []
    for k in OBRIGATORIOS:
        if k not in estado:
            erros.append(f"campo obrigatório ausente: {k}")
    if "personagem" not in estado:
        erros.append("campo 'personagem' ausente (pode ser null)")
    ids = [l.get("id") for l in estado.get("lugares", [])]
    if len(ids) != len(set(ids)):
        erros.append("ids de lugares repetidos")
    local = estado.get("local", {}).get("id")
    if local and local not in ids:
        erros.append(f"local atual '{local}' não está em lugares")
    for l in estado.get("lugares", []):
        if l.get("estado") not in ("desconhecido", "conhecido", "visitado", "atual"):
            erros.append(f"lugar '{l.get('id')}' com estado inválido: {l.get('estado')}")
    return erros


def main() -> int:
    estado = json.loads(ESTADO.read_text(encoding="utf-8"))
    erros = validar(estado)
    if erros:
        print("estado.json inválido:")
        for e in erros:
            print("  -", e)
        return 1
    if "--check" in sys.argv:
        print("estado.json válido.")
        return 0

    html = TEMPLATE.read_text(encoding="utf-8")
    ini = html.find(MARCADOR_INI)
    if ini < 0:
        print("template sem o bloco estado-json")
        return 1
    ini_conteudo = ini + len(MARCADOR_INI)
    fim = html.find(MARCADOR_FIM, ini_conteudo)
    dados = json.dumps(estado, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    novo = html[:ini_conteudo] + "\n" + dados + "\n" + html[fim:]
    SAIDA.write_text(novo, encoding="utf-8")
    print(f"dashboard atualizado: {SAIDA.relative_to(RAIZ)} ({len(novo)//1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
