"""O leitor de pé nos dois ambientes — publicado e solto.

Rode com:  python3 test_como_artifact.py  (precisa do Playwright)

Este teste existe por um defeito que sobreviveu a várias rodadas de conserto:
dentro do artifact, `window.claude` existe, e o leitor trocava o conteúdo do
painel de sincronização por um aviso — destruindo o botão #salvar-sync. A
ligação de evento nesse botão, logo abaixo, lançava um TypeError que
interrompia a ligação de TODOS os eventos seguintes. A página ficava inteira
inerte: tocar em «Abrir um EPUB» não fazia nada, sem erro visível.

Nenhum teste via isso porque todos abriam o arquivo local, onde `window.claude`
não existe e o painel nunca era destruído. O ambiente em que o defeito mora
precisa ser um ambiente testado.
"""

from __future__ import annotations

import base64
import os
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib

from playwright.sync_api import sync_playwright

AQUI = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(tempfile.gettempdir(), "leitor-artifact")
CHROME = os.environ.get("CHROME_PATH") or None

# O que o publicador injeta na página: é a presença disto que muda o caminho.
COMO_ARTIFACT = """
  window.claude = {
    complete: async () => '',
    downloads: { download: async () => {} },
  };
"""


def montar_epub(caminho: str, capitulos: int = 6, paragrafos: int = 9) -> None:
    """Um livro com a forma que os de editora têm: capa sem texto no spine.

    Os tamanhos são parâmetros porque outro teste precisa de um livro longo o
    bastante para virar dezenas de páginas sem chegar ao fim.
    """
    def png():
        linhas = b"".join(b"\x00" + bytes((30, 40, 60)) * 20 for _ in range(30))
        def bloco(tipo, dados):
            corpo = tipo + dados
            return struct.pack(">I", len(dados)) + corpo + struct.pack(">I", zlib.crc32(corpo))
        return (b"\x89PNG\r\n\x1a\n"
                + bloco(b"IHDR", struct.pack(">IIBBBBB", 20, 30, 8, 2, 0, 0, 0))
                + bloco(b"IDAT", zlib.compress(linhas, 9)) + bloco(b"IEND", b""))

    def pagina(titulo, corpo):
        return ('<?xml version="1.0" encoding="utf-8"?><html '
                'xmlns="http://www.w3.org/1999/xhtml" '
                'xmlns:epub="http://www.idpf.org/2007/ops">'
                f'<head><title>{titulo}</title></head><body>{corpo}</body></html>')

    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mimetype", "application/epub+zip", zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml",
                   '<?xml version="1.0"?><container version="1.0" '
                   'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                   '<rootfile full-path="OEBPS/livro.opf" '
                   'media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr("OEBPS/capa.png", png())
        z.writestr("OEBPS/000_capa.xhtml", pagina("Capa", '<img src="capa.png" alt="Capa"/>'))
        for i in range(capitulos):
            ps = "".join(f"<p>Parágrafo {j} do capítulo {i + 1}, com texto de sobra "
                         f"para render algumas páginas de leitura.</p>"
                         for j in range(paragrafos))
            z.writestr(f"OEBPS/{i + 1:03d}_cap.xhtml", pagina(f"Capítulo {i + 1}",
                                                              f"<h1>Capítulo {i + 1}</h1>{ps}"))
        nomes = ["000_capa.xhtml"] + [f"{i + 1:03d}_cap.xhtml" for i in range(capitulos)]
        z.writestr("OEBPS/nav.xhtml", pagina("Sumário", '<nav epub:type="toc"><ol>'
                   + "".join(f'<li><a href="{n}">{n}</a></li>' for n in nomes[1:])
                   + "</ol></nav>"))
        manifesto = ('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
                     'properties="nav"/><item id="img" href="capa.png" media-type="image/png"/>')
        lombada = ""
        for i, n in enumerate(nomes):
            manifesto += f'<item id="i{i}" href="{n}" media-type="application/xhtml+xml"/>'
            lombada += f'<itemref idref="i{i}"/>'
        z.writestr("OEBPS/livro.opf",
                   '<?xml version="1.0" encoding="utf-8"?><package '
                   'xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">'
                   '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
                   '<dc:title>Livro de teste</dc:title><dc:language>pt-BR</dc:language>'
                   '<dc:identifier id="id">urn:uuid:artifact</dc:identifier></metadata>'
                   f'<manifest>{manifesto}</manifest><spine>{lombada}</spine></package>')


def conferir(pg, rotulo: str, falhas: list, avisos: list) -> None:
    # O ajudante `ao()` tolera um elemento ausente, mas avisa. Esse aviso é o
    # sintoma da causa original — nós sendo destruídos — e não pode aparecer:
    # sem ele, um innerHTML destrutivo voltaria sem ninguém notar.
    sumidos = [a for a in avisos if "não existe" in a]
    if sumidos:
        falhas.append(f"{rotulo}: elemento destruído — {sumidos[0]}")

    faixa = pg.locator("#falha-leitor")
    if faixa.count():
        falhas.append(f"{rotulo}: faixa de erro — {faixa.text_content()[:120]}")
    if not pg.evaluate("() => window.__leitorCarregou === true"):
        falhas.append(f"{rotulo}: o leitor não terminou de carregar")

    # o botão de abrir tem de chegar ao seletor de arquivos
    chegou = pg.evaluate("""() => new Promise(r => {
      const i = document.getElementById('arquivo');
      if (!i) return r(false);
      i.addEventListener('click', () => r(true), {once: true});
      const b = document.getElementById('abrir');
      if (!b) return r(false);
      b.click();
      setTimeout(() => r(false), 400);
    })""")
    if not chegou:
        falhas.append(f"{rotulo}: tocar em «Abrir um EPUB» não aciona o seletor")

    pg.set_input_files("#arquivo", os.path.join(TMP, "livro.epub"))
    pg.wait_for_timeout(3000)
    blocos = pg.locator("#fluxo [data-b]").count()
    if blocos == 0:
        falhas.append(f"{rotulo}: o livro abriu sem nenhum bloco de texto "
                      "(o leitor caiu na capa?)")
    print(f"  {rotulo:20} carregou, abriu o seletor, e leu {blocos} blocos")


def main() -> int:
    os.makedirs(TMP, exist_ok=True)
    pagina = os.path.join(TMP, "leitor.html")
    subprocess.run([sys.executable, os.path.join(AQUI, "pagina.py"), pagina],
                   check=True, stdout=subprocess.DEVNULL)
    montar_epub(os.path.join(TMP, "livro.epub"))

    falhas: list = []
    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path=CHROME) if CHROME else p.chromium.launch()
        for rotulo, artifact in (("dentro do artifact", True), ("página solta", False)):
            ctx = nav.new_context(viewport={"width": 820, "height": 1180}, has_touch=True)
            if artifact:
                ctx.add_init_script(COMO_ARTIFACT)
            pg = ctx.new_page()
            avisos: list = []
            pg.on("pageerror", lambda e: falhas.append(f"{rotulo}: erro de JS — {e}"))
            pg.on("console", lambda m: avisos.append(m.text) if m.type == "warning" else None)
            pg.goto("file://" + pagina)
            pg.wait_for_timeout(5000)
            conferir(pg, rotulo, falhas, avisos)
            ctx.close()
        nav.close()

    print()
    print("FALHAS:", falhas if falhas else "nenhuma — o leitor está de pé nos dois ambientes")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
