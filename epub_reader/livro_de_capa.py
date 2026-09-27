"""Gera um EPUB com a forma que quebrava o leitor: capa sem texto no spine.

    python3 livro_de_capa.py

Quase todo livro de editora começa assim — o primeiro item do spine é a capa,
que só tem uma imagem e nenhum bloco de texto. Os EPUBs de teste daqui todos
começavam com texto, e por isso o defeito passou: a capa, ficando com
last_block < first_block, reivindicava o bloco 0 e o leitor abria numa página
em branco. Este arquivo existe para que isso não volte despercebido.
"""
import base64
import os
import random
import zipfile

SP = os.path.dirname(os.path.abspath(__file__)) + os.sep
CAMINHO = SP + "livro-de-capa.epub"

# Um PNG 2x3 de verdade, para a capa ter imagem como a do livro real.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAASwAAAHCCAIAAADaUWPQAAAEBElEQVR42u3TQQ0AIAwAsUnhhQL8a0HAHkiYDJasSRVccrH2AT4KCcCEYELAhGBCwIRgQsCEYELAhGBCwIRgQsCEYELAhGBCwIRgQsCEYELAhGBCwIRgQsCEYELAhGBCwIRgQsCEYELAhGBCwIRgQsCEYELAhGBCwIRgQsCEYELAhGBCwIRgQsCEYELAhGBCwIRgQsCEYELAhGBCwIRgQsCEYELAhGBCMKEKYEIwIWBCMCFgQjAhYEIwIWBCMCFgQjAhYEIwIWBCMCFgQjAhYEIwIWBCMCFgQjAhYEIwIWBCMCFgQjAhYEIwIWBCMCFgQjAhYEIwIWBCMCFgQjAhYEIwIWBCMCFgQjAhYEIwIWBCMCFgQjAh0GrClxf6MCGY0ISY0IRgQhNiQhOCCU2ICU0IJjQhJjQhmNCEmNCEYEITYkITgglNiAlNCCY0ISY0IZjQhJjQhGBCE2JCE4IJTYgJTQgmNCEmNCGY0ISY0IRgQhNiQhOCCU2ICU0IJjQhJjQhmNCEmNCEYEITYkITgglNiAlNCCY0ISY0IZjQhJjQhGBCE2JCE4IJTYgJTQgmNCEmNCGY0ISY0IRgQhNiQhOCCU2ICU0IJjQhJjQhmNCEmNCEYEIwoQnBhGBCE4IJwYQmxIQmBBOaEBOaEExoQkxoQjChCTGhCcGEJsSEJgQTmhATmhBMaEJMaEIwIWBCMCFgQjAhYEIwIWBCMCFgQjAhYEIwIWBCMCFgQjAhYEIwIWBCMCFgQjAhYEIwIWBCMCFgQjAhYEIwIWBCMCFgQjAhYEIwIWBCMCFgQjAhYEIwIWBCMCFgQjAhmFACMCGYEDAhmBAwIZgQMCGYEDAhmBAwIZgQMCGYEDAhmBAwIZgQMCGYEDAhmBAwIZgQMCGYEDAhmBAwIZgQMCGYEDAhmBAwIZgQMCGYEDAhmBAwIZgQMCGYEDAhmBAwIZgQMCGYEDAhmBAwIZgQMCGYEDAhmBAwIZgQMCGYEDAhmBBMqAKYEEwImBBMCJgQTAiYEEwImBBMCJgQTAiYEEwImBBMCJgQTAiYEEwImBBMCJgQTAiYEEwImBBMCJgQTAiYEEwImBBMCJgQTAiYEEwImBBMCJgQTAiYEEwImBBMCJgQTAiYEEwImBBMCJgQTAiYEEwImBBMCJgQTAiYEEwImBBMCCZUAUwIJgRMCCYETAgmBEwIJgRMCCYETAgmBEwIJgRMCCYETAgmBEwIJgRMCCYETAgmBEwIJgRMCCYETAgmBEwIJgRMCCYETAgmBEwIJgRMCCYETAgmBEwIJgRMCCYETAgmBEwIJgRMCCYETAgmBEwIJgRMCCYETAgmBEwIJgRMCCYEEwImBBMCJgQTAiYEEwImhFkKguf9+Mki/yoAAAAASUVORK5CYII=")

sorte = random.Random(4)
PALAVRAS = ("cinza corda névoa relógio telegrama carta farol chuva torre maré "
            "vento trem âncora silêncio bruma sal lanterna pedra cais vigia").split()


def pagina(titulo, corpo):
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<!DOCTYPE html>'
            '<html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:epub="http://www.idpf.org/2007/ops">'
            f'<head><title>{titulo}</title></head><body>{corpo}</body></html>')


def montar(caminho=CAMINHO, capitulos=22):
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mimetype", "application/epub+zip", zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml",
                   '<?xml version="1.0"?><container version="1.0" '
                   'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                   '<rootfile full-path="OEBPS/9780000000000.opf" '
                   'media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr("OEBPS/images/cover.png", PNG)

        # A CAPA: só imagem, zero blocos de texto. É a forma que quebrou.
        z.writestr("OEBPS/xhtml/001_cvi_Cover.xhtml",
                   pagina("Cover", '<div class="cover"><img src="../images/cover.png" '
                                   'alt="Capa" style="width:100%"/></div>'))
        # Uma epígrafe curta, como no livro dele
        z.writestr("OEBPS/xhtml/008_epi_epigraph.xhtml",
                   pagina("Epígrafe", "<blockquote><p>Não confie no relógio da torre.</p></blockquote>"))

        nomes = ["xhtml/001_cvi_Cover.xhtml", "xhtml/008_epi_epigraph.xhtml"]
        for i in range(capitulos):
            arq = f"xhtml/{i + 20:03d}_p{i:03d}_capitulo.xhtml"
            ps = "".join("<p>" + " ".join(sorte.choice(PALAVRAS) for _ in range(60)).capitalize()
                         + ".</p>" for _ in range(8))
            z.writestr("OEBPS/" + arq, pagina(f"Capítulo {i + 1}", f"<h1>Capítulo {i + 1}</h1>{ps}"))
            nomes.append(arq)

        itens = "".join(f'<li><a href="{n}">{n}</a></li>' for n in nomes[1:])
        z.writestr("OEBPS/9780000000000_nav.xhtml",
                   pagina("Sumário", f'<nav epub:type="toc"><ol>{itens}</ol></nav>'))
        pontos = "".join(
            f'<navPoint id="n{i}" playOrder="{i + 1}"><navLabel><text>{n}</text></navLabel>'
            f'<content src="{n}"/></navPoint>' for i, n in enumerate(nomes[1:]))
        z.writestr("OEBPS/9780000000000_ncx.ncx",
                   '<?xml version="1.0" encoding="utf-8"?>'
                   '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
                   f'<head/><docTitle><text>The Disappearers</text></docTitle>'
                   f'<navMap>{pontos}</navMap></ncx>')

        manifesto = ('<item id="nav" href="9780000000000_nav.xhtml" '
                     'media-type="application/xhtml+xml" properties="nav"/>'
                     '<item id="ncx" href="9780000000000_ncx.ncx" '
                     'media-type="application/x-dtbncx+xml"/>'
                     '<item id="capa-img" href="images/cover.png" '
                     'media-type="image/png" properties="cover-image"/>')
        lombada = ""
        for i, n in enumerate(nomes):
            manifesto += (f'<item id="i{i}" href="{n}" media-type="application/xhtml+xml"/>')
            lombada += f'<itemref idref="i{i}"/>'
        z.writestr("OEBPS/9780000000000.opf",
                   '<?xml version="1.0" encoding="utf-8"?>'
                   '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
                   'unique-identifier="id"><metadata '
                   'xmlns:dc="http://purl.org/dc/elements/1.1/">'
                   '<dc:title>The Disappearers</dc:title>'
                   '<dc:creator>Marlon James</dc:creator>'
                   '<dc:language>en</dc:language>'
                   '<dc:identifier id="id">urn:uuid:teste-capa</dc:identifier></metadata>'
                   f'<manifest>{manifesto}</manifest>'
                   f'<spine toc="ncx">{lombada}</spine></package>')


if __name__ == "__main__":
    montar()
    tam = os.path.getsize(CAMINHO)
    with zipfile.ZipFile(CAMINHO) as z:
        print(f"{CAMINHO}: {tam} bytes, {len(z.namelist())} arquivos dentro")
        print("primeiros:", ", ".join(z.namelist()[:6]))
