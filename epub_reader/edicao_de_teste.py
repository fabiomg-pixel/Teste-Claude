"""Gera uma edição de jornal em PDF para os testes, sem biblioteca nenhuma.

Rode com:  python3 edicao_de_teste.py saida.pdf

Quatro páginas com a forma que importa para o leitor: mais de uma matéria por
página, um anúncio no meio, e uma reportagem que começa na página 2 e continua
na 4 («continua na página 4»). Cada página traz uma marca, MARCA-PAGINA-N, para
o teste conferir quais páginas foram de fato enviadas ao modelo.

PDF escrito à mão: catálogo, páginas, uma fonte Helvetica com WinAnsiEncoding
(que cobre os acentos do português) e um fluxo de conteúdo por página. A tabela
xref é calculada com os deslocamentos reais — sem ela, o pdf.js até abre, mas o
pdf-lib recusa.
"""

from __future__ import annotations

import sys

PAGINAS = {
    1: [("Chuvas fecham estradas no interior", 40, 740, 16),
        ("Três rodovias estaduais seguem interditadas.", 40, 715, 10),
        ("Prefeitura anuncia nova linha de ônibus", 320, 740, 16),
        ("A linha 42 liga o centro ao porto.", 320, 715, 10),
        ("ANÚNCIO: Colchões Sono Bom, 50% de desconto", 40, 400, 12)],
    2: [("O porto que mudou a cidade", 40, 740, 20),
        ("Por Ana Lima", 40, 712, 10),
        ("O porto abriu em 1990 e hoje movimenta 3 milhões de toneladas.", 40, 690, 10),
        ("Moradores contam que o bairro mudou de cara em duas décadas.", 40, 674, 10),
        ("Continua na página 4", 40, 640, 9)],
    3: [("Esportes: time vence clássico por 2 a 1", 40, 740, 16),
        ("O gol da vitória saiu aos 44 do segundo tempo.", 40, 715, 10)],
    4: [("Continuação de O porto que mudou a cidade", 40, 740, 12),
        ("A prefeitura estuda ampliar o cais até 2030.", 40, 715, 10),
        ("Legenda: navios atracados no cais norte", 40, 690, 9)],
}


def _texto_pdf(s: str) -> bytes:
    bruto = s.encode("cp1252")
    return bruto.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def gerar(caminho: str) -> None:
    objetos: list[bytes] = []

    def novo(corpo: bytes) -> int:
        objetos.append(corpo)
        return len(objetos)

    catalogo = novo(b"")          # preenchido depois que se sabe o id de Pages
    paginas_id = novo(b"")
    fonte = novo(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                 b"/Encoding /WinAnsiEncoding >>")
    filhos = []
    for n in sorted(PAGINAS):
        linhas = [(f"MARCA-PAGINA-{n}", 40, 30, 7)] + PAGINAS[n]
        fluxo = b"".join(b"BT /F1 %d Tf %d %d Td (%s) Tj ET\n" % (tam, x, y, _texto_pdf(t))
                         for t, x, y, tam in linhas)
        conteudo = novo(b"<< /Length %d >>\nstream\n" % len(fluxo) + fluxo + b"endstream")
        filhos.append(novo(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595 842] "
                           b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
                           % (paginas_id, fonte, conteudo)))
    objetos[paginas_id - 1] = (b"<< /Type /Pages /Count %d /Kids [%s] >>"
                               % (len(filhos), b" ".join(b"%d 0 R" % f for f in filhos)))
    objetos[catalogo - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % paginas_id

    saida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    deslocamentos = []
    for i, corpo in enumerate(objetos, start=1):
        deslocamentos.append(len(saida))
        saida += b"%d 0 obj\n" % i + corpo + b"\nendobj\n"
    xref = len(saida)
    saida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    for d in deslocamentos:
        saida += b"%010d 00000 n \n" % d
    saida += (b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
              % (len(objetos) + 1, catalogo, xref))
    with open(caminho, "wb") as fh:
        fh.write(saida)


if __name__ == "__main__":
    gerar(sys.argv[1] if len(sys.argv) > 1 else "edicao.pdf")
