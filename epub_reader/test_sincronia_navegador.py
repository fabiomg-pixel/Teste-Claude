"""Dois aparelhos sincronizando pelo servidor Flask de verdade.

O aparelho B roda sem crypto.subtle de propósito, para exercitar o SHA-256 em
JS puro — é o caso de um servidor caseiro em http://, onde o navegador não
oferece a API de criptografia.
"""
import os
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
SP = "/tmp/claude-0/-home-user-Teste-Claude/93e83018-1bfd-5ee0-a223-09e405c55c20/scratchpad/"
BASE = "http://127.0.0.1:5099"
TOKEN = "token-de-teste-sincronia"
EPUB = os.environ.get("EPUB_TESTE", SP + "longo.epub")

SEM_CRYPTO = ("Object.defineProperty(window.crypto, 'subtle',"
              " {get: () => undefined, configurable: true});")


def aparelho(navegador, sem_crypto=False):
    ctx = navegador.new_context(viewport={"width": 412, "height": 900},
                                is_mobile=True, has_touch=True)
    if sem_crypto:
        ctx.add_init_script(SEM_CRYPTO)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: print("   ERRO JS:", e))
    pg.goto(BASE + "/celular", wait_until="networkidle")
    pg.wait_for_timeout(300)
    return pg


def ligar_sync(pg):
    pg.click("#abrir-sync")
    pg.wait_for_timeout(200)
    pg.fill("#campo-servidor", BASE)
    pg.fill("#campo-token", TOKEN)
    pg.click("#salvar-sync")
    pg.wait_for_timeout(2500)


def marcador(pg):
    return pg.evaluate("""() => {
      const k = Object.keys(localStorage).find(k => k.startsWith('leitor.estado'));
      return k ? JSON.parse(localStorage.getItem(k)) : null;
    }""")


def virar(pg, vezes):
    caixa = pg.locator("#palco").bounding_box()
    for _ in range(vezes):
        pg.mouse.click(caixa["x"] + caixa["width"] * 0.85, caixa["y"] + caixa["height"] / 2)
        pg.wait_for_timeout(260)


def destacar(pg, cor="mare"):
    pg.evaluate("""() => {
      const el = document.querySelector('#fluxo p[data-b]');
      const r = document.createRange(); const t = el.firstChild;
      r.setStart(t, 0); r.setEnd(t, Math.min(45, t.length));
      const s = getSelection(); s.removeAllRanges(); s.addRange(r);
      document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
    }""")
    pg.wait_for_timeout(300)
    pg.locator(f"#selecao .cor[data-cor='{cor}']").dispatch_event("mousedown")
    pg.wait_for_timeout(400)


servidor = subprocess.Popen(
    [sys.executable, "app.py"],
    cwd="/home/user/Teste-Claude/epub_reader",
    env={"PATH": "/usr/bin:/bin", "PORT": "5099", "EPUB_SYNC_TOKEN": TOKEN,
         "EPUB_DATA_DIR": SP + "dados-sync", "HOME": "/root"},
    stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
time.sleep(4)

falhas = []
try:
    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path=CHROME)

        print("APARELHO A — importa o livro, lê e destaca")
        a = aparelho(nav)
        a.set_input_files("#arquivo", EPUB)
        a.wait_for_timeout(2500)
        virar(a, 6)
        destacar(a, "mare")
        estado_a = marcador(a)
        print("   fronteira:", estado_a["fronteira"], "| marcas:", len(estado_a["marcas"]))
        a.click("#voltar"); a.wait_for_timeout(600)
        ligar_sync(a)
        impressao_a = a.evaluate("""async () => {
          const bd = await new Promise(r => { const q = indexedDB.open('leitor-sem-spoiler', 1); q.onsuccess = () => r(q.result); });
          return await new Promise(r => { const q = bd.transaction('livros').objectStore('livros').getAll(); q.onsuccess = () => r(q.result[0].impressao); });
        }""")
        print("   impressão digital (com crypto.subtle):", impressao_a)

        print("APARELHO B — só o endereço e o token; o livro tem de vir sozinho")
        b = aparelho(nav, sem_crypto=True)
        print("   crypto.subtle disponível?", b.evaluate("() => !!(window.crypto && crypto.subtle)"))
        ligar_sync(b)
        b.wait_for_timeout(2500)
        livros_b = b.locator(".livro").count()
        print("   livros na estante de B:", livros_b)
        if livros_b != 1:
            falhas.append("B não recebeu o livro")

        impressao_b = b.evaluate("""async () => {
          const bd = await new Promise(r => { const q = indexedDB.open('leitor-sem-spoiler', 1); q.onsuccess = () => r(q.result); });
          return await new Promise(r => { const q = bd.transaction('livros').objectStore('livros').getAll(); q.onsuccess = () => r(q.result[0] && q.result[0].impressao); });
        }""")
        print("   impressão digital (SHA-256 em JS puro):", impressao_b)
        if impressao_a != impressao_b:
            falhas.append(f"impressões diferentes: {impressao_a} != {impressao_b}")

        estado_b = marcador(b)
        print("   fronteira herdada:", estado_b["fronteira"], "| marcas:", len(estado_b["marcas"]))
        if estado_b["fronteira"] != estado_a["fronteira"]:
            falhas.append("a fronteira não atravessou")
        if len(estado_b["marcas"]) != 1:
            falhas.append("o destaque não atravessou")

        print("APARELHO B — lê mais, destaca e apaga o destaque de A")
        b.locator(".livro").first.click()
        b.wait_for_timeout(2500)
        virar(b, 8)
        destacar(b, "musgo")
        b.evaluate("""() => {
          document.getElementById('btn-sumario').click();
        }""")
        b.wait_for_timeout(400)
        b.click("#ver-anotacoes"); b.wait_for_timeout(400)
        b.locator("[data-apagar]").first.click()   # apaga o mais antigo (o de A)
        b.wait_for_timeout(400)
        b.keyboard.press("Escape")
        b.click("#voltar"); b.wait_for_timeout(1200)
        estado_b2 = marcador(b)
        vivas_b = [m for m in estado_b2["marcas"] if not m.get("apagadoEm")]
        print("   fronteira de B:", estado_b2["fronteira"], "| vivas:", len(vivas_b),
              "| lápides:", len(estado_b2["marcas"]) - len(vivas_b))

        print("APARELHO A — sincroniza de novo")
        a.reload(wait_until="networkidle"); a.wait_for_timeout(3000)
        estado_a2 = marcador(a)
        vivas_a = [m for m in estado_a2["marcas"] if not m.get("apagadoEm")]
        print("   fronteira de A:", estado_a2["fronteira"], "| vivas:", len(vivas_a))

        if estado_a2["fronteira"] != estado_b2["fronteira"]:
            falhas.append(f"fronteira não voltou para A: {estado_a2['fronteira']} != {estado_b2['fronteira']}")
        if len(vivas_a) != 1:
            falhas.append(f"A deveria ter 1 destaque vivo (o de B), tem {len(vivas_a)}")
        if vivas_a and vivas_a[0].get("cor") != "musgo":
            falhas.append("o destaque vivo em A não é o que B criou")

        nav.close()
finally:
    servidor.terminate()

print()
print("FALHAS:", falhas if falhas else "nenhuma — sincronização redonda")
sys.exit(1 if falhas else 0)
