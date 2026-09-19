"""O servidor perde o disco inteiro. Os aparelhos o reconstroem?

Rode com:  python test_disco_efemero.py  (precisa do Playwright)

É a pergunta que decide se uma hospedagem gratuita de disco efêmero serve:
lá o disco some a cada deploy e a cada vez que o serviço acorda. Aqui isso é
simulado da forma mais brutal possível — apaga-se a pasta de dados inteira e
sobe-se o servidor de novo, do zero.
"""
import os
import shutil
import tempfile
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

CHROME = os.environ.get("CHROME_PATH") or None    # None = o do Playwright
SP = os.path.join(tempfile.gettempdir(), "leitor-efemero") + os.sep
BASE = "http://127.0.0.1:5096"
TOKEN = "token-que-sobrevive"          # vem do ambiente, não do disco
DADOS = SP + "dados-efemero"
EPUB = SP + "livro-do-teste.epub"


def montar_epub(caminho: str, capitulos: int = 12, paragrafos: int = 9) -> None:
    """Um livro comprido o bastante para haver o que sincronizar.

    Palavras sorteadas de uma lista pequena: o conteúdo não importa, o que
    importa é o número de blocos e o fato de o arquivo ser sempre o mesmo —
    daí a semente fixa, para a impressão digital não mudar entre execuções.
    """
    import random
    import zipfile

    sorte = random.Random(20260919)
    palavras = ("cinza corda névoa relógio telegrama carta farol chuva torre "
                "maré vento trem âncora silêncio bruma sal lanterna pedra "
                "cais vigia porto janela").split()

    def corpo(i):
        ps = "".join(
            "<p>" + " ".join(sorte.choice(palavras) for _ in range(70)).capitalize() + ".</p>"
            for _ in range(paragrafos))
        return f"<h1>Capítulo {i + 1}</h1>{ps}"

    def pagina(titulo, conteudo):
        return ('<?xml version="1.0" encoding="utf-8"?>'
                '<html xmlns="http://www.w3.org/1999/xhtml" '
                'xmlns:epub="http://www.idpf.org/2007/ops">'
                f'<head><title>{titulo}</title></head><body>{conteudo}</body></html>')

    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("mimetype", "application/epub+zip", zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml",
                   '<?xml version="1.0"?><container version="1.0" '
                   'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                   '<rootfile full-path="OEBPS/content.opf" '
                   'media-type="application/oebps-package+xml"/></rootfiles></container>')
        for i in range(capitulos):
            z.writestr(f"OEBPS/c{i}.xhtml", pagina(f"Capítulo {i + 1}", corpo(i)))
        itens = "".join(f'<li><a href="c{i}.xhtml">Capítulo {i + 1}</a></li>'
                        for i in range(capitulos))
        z.writestr("OEBPS/nav.xhtml",
                   pagina("Sumário", f'<nav epub:type="toc"><ol>{itens}</ol></nav>'))
        manifesto = "".join(f'<item id="c{i}" href="c{i}.xhtml" '
                            f'media-type="application/xhtml+xml"/>' for i in range(capitulos))
        lombada = "".join(f'<itemref idref="c{i}"/>' for i in range(capitulos))
        z.writestr("OEBPS/content.opf",
                   '<?xml version="1.0" encoding="utf-8"?>'
                   '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
                   'unique-identifier="id"><metadata '
                   'xmlns:dc="http://purl.org/dc/elements/1.1/">'
                   '<dc:title>A Travessia de Ostende</dc:title>'
                   '<dc:creator>Marta Vilela</dc:creator>'
                   '<dc:language>pt-BR</dc:language>'
                   '<dc:identifier id="id">urn:uuid:efemero</dc:identifier></metadata>'
                   '<manifest><item id="nav" href="nav.xhtml" '
                   'media-type="application/xhtml+xml" properties="nav"/>'
                   f'{manifesto}</manifest><spine>{lombada}</spine></package>')


def subir_servidor():
    p = subprocess.Popen(
        [sys.executable, "app.py"], cwd=os.path.dirname(os.path.abspath(__file__)),
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": "/root", "PORT": "5096",
             "EPUB_SYNC_TOKEN": TOKEN, "EPUB_DATA_DIR": DADOS},
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    for _ in range(40):
        try:
            urllib.request.urlopen(BASE + "/saude", timeout=1).read()
            return p
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("o servidor não subiu")


def no_servidor():
    pedido = urllib.request.Request(BASE + "/api/sync/hello",
                                    headers={"Authorization": "Bearer " + TOKEN})
    import json
    return json.load(urllib.request.urlopen(pedido, timeout=5))


def aparelho(nav):
    ctx = nav.new_context(viewport={"width": 412, "height": 900}, is_mobile=True, has_touch=True)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: print("   ERRO JS:", e))
    pg.goto(BASE + "/celular", wait_until="networkidle")
    pg.wait_for_timeout(300)
    return pg


def ligar_sync(pg):
    pg.click("#abrir-sync"); pg.wait_for_timeout(200)
    pg.fill("#campo-servidor", BASE)
    pg.fill("#campo-token", TOKEN)
    pg.click("#salvar-sync"); pg.wait_for_timeout(3000)


def virar(pg, vezes):
    caixa = pg.locator("#palco").bounding_box()
    for _ in range(vezes):
        pg.mouse.click(caixa["x"] + caixa["width"] * .85, caixa["y"] + caixa["height"] / 2)
        pg.wait_for_timeout(250)


def destacar(pg):
    pg.evaluate("""() => {
      const el = document.querySelector('#fluxo p[data-b]');
      const r = document.createRange(); const t = el.firstChild;
      r.setStart(t, 0); r.setEnd(t, Math.min(40, t.length));
      const s = getSelection(); s.removeAllRanges(); s.addRange(r);
      document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
    }""")
    pg.wait_for_timeout(300)
    pg.locator("#selecao .cor[data-cor='mare']").dispatch_event("mousedown")
    pg.wait_for_timeout(400)


shutil.rmtree(DADOS, ignore_errors=True)
montar_epub(EPUB)
servidor = subir_servidor()
falhas = []
try:
    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path=CHROME) if CHROME else p.chromium.launch()

        print("1. APARELHO A lê, destaca e sincroniza")
        a = aparelho(nav)
        a.set_input_files("#arquivo", EPUB); a.wait_for_timeout(2500)
        virar(a, 7); destacar(a)
        a.click("#voltar"); a.wait_for_timeout(600)
        ligar_sync(a)
        antes = no_servidor()
        livro = antes["livros"][0] if antes["livros"] else None
        print("   no servidor:", len(antes["livros"]), "livro(s);",
              "arquivo:", livro and livro["tem_arquivo"])
        if not livro or not livro["tem_arquivo"]:
            falhas.append("o livro não chegou ao servidor na primeira sincronia")
        impressao = livro["impressao"]

        print("2. O DISCO DO SERVIDOR SOME (deploy numa hospedagem efêmera)")
        servidor.terminate(); servidor.wait(timeout=10)
        shutil.rmtree(DADOS, ignore_errors=True)
        servidor = subir_servidor()
        vazio = no_servidor()
        print("   depois do reset:", len(vazio["livros"]), "livro(s) — esperado 0")
        if vazio["livros"]:
            falhas.append("o reset não foi de verdade")

        print("3. APARELHO A volta (só recarrega a página)")
        a.reload(wait_until="networkidle")
        a.wait_for_timeout(6000)
        depois = no_servidor()
        voltou = next((l for l in depois["livros"] if l["impressao"] == impressao), None)
        print("   no servidor:", len(depois["livros"]), "livro(s);",
              "arquivo:", voltou and voltou["tem_arquivo"])
        if not voltou:
            falhas.append("o livro NÃO voltou ao servidor")
        elif not voltou["tem_arquivo"]:
            falhas.append("o registro voltou, mas sem o arquivo")

        print("4. APARELHO B, novo em folha, só com endereço e token")
        b = aparelho(nav)
        ligar_sync(b)
        b.wait_for_timeout(3000)
        livros_b = b.locator(".livro").count()
        estado_b = b.evaluate("""() => {
          const k = Object.keys(localStorage).find(k => k.startsWith('leitor.estado'));
          return k ? JSON.parse(localStorage.getItem(k)) : null;
        }""")
        print("   livros em B:", livros_b, "| fronteira:", estado_b and estado_b["fronteira"],
              "| marcas:", estado_b and len(estado_b["marcas"]))
        if livros_b != 1:
            falhas.append("B não recebeu o livro depois do reset")
        if not estado_b or not estado_b["fronteira"]:
            falhas.append("a fronteira não sobreviveu ao reset")
        if not estado_b or len(estado_b["marcas"]) != 1:
            falhas.append("o destaque não sobreviveu ao reset")

        nav.close()
finally:
    servidor.terminate()

print()
print("FALHAS:", falhas if falhas else "nenhuma — os aparelhos reconstroem o servidor")
sys.exit(1 if falhas else 0)
