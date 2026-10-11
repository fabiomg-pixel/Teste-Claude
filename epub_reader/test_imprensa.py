"""Edições de revista e jornal: do PDF à conversa com busca na web.

Rode com:  python3 test_imprensa.py   (precisa do Playwright e do npm)

O que este teste existe para garantir:

1. Só as páginas escolhidas vão para o modelo. Uma revista inteira mandada para
   ler uma matéria de duas páginas custaria dezenas de vezes mais, e sem erro
   nenhum — só a conta denunciaria. O teste abre o PDF que de fato saiu e confere
   página por página.
2. A transcrição lê o PDF do cache. Listar e transcrever mandam o mesmo PDF, com
   o mesmo system, modelo e esforço; se qualquer um mudar, o cache se perde em
   silêncio.
3. A matéria vira documento do leitor, com as regras de imprensa, e a busca na
   web — que traz links de páginas que ninguém controla — não deixa passar um
   link que não seja http(s).
4. Um turno de busca pausado é retomado devolvendo o turno intacto.
5. Livro continua sem busca na web, mesmo com o botão ligado: lá ela abriria a
   porta do spoiler.

Precisa das bibliotecas de PDF em vendor/, como no GitHub Pages. Se PDF_LIBS
apontar para um node_modules com pdfjs-dist@3.11.174 e pdf-lib@1.17.1, usa ele;
se não, instala com npm numa pasta temporária.
"""

from __future__ import annotations

import http.server
import os
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading

from playwright.sync_api import sync_playwright

import edicao_de_teste
from test_como_artifact import montar_epub

AQUI = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(tempfile.gettempdir(), "leitor-imprensa")
CHROME = os.environ.get("CHROME_PATH") or None
GANCHO = "window.__leitorTestes = (api) => { window.api = api; };\n"
CHAVE = "sk-ant-api03-chave-de-teste"

shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(TMP)
subprocess.run([sys.executable, os.path.join(AQUI, "pagina.py"), os.path.join(TMP, "leitor.html")],
               check=True, stdout=subprocess.DEVNULL)

# --------------------------------------------- as bibliotecas, como no Pages
# As versões vêm do próprio leitor, como no pages.yml: uma fonte só.
_fonte = open(os.path.join(AQUI, "leitor-celular.html"), encoding="utf-8").read()
VERSAO_PDFJS = re.search(r"VERSAO_PDFJS = '([0-9.]+)'", _fonte).group(1)
VERSAO_PDFLIB = re.search(r"VERSAO_PDFLIB = '([0-9.]+)'", _fonte).group(1)

libs = os.environ.get("PDF_LIBS")
if not libs or not os.path.isdir(os.path.join(libs, "pdfjs-dist")):
    destino = os.path.join(TMP, "npm")
    os.makedirs(destino)
    subprocess.run(["npm", "install", "--prefix", destino, "--no-audit", "--no-fund",
                    "pdfjs-dist@" + VERSAO_PDFJS, "pdf-lib@" + VERSAO_PDFLIB], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    libs = os.path.join(destino, "node_modules")
os.makedirs(os.path.join(TMP, "vendor", "pdfjs"))
for nome in ("pdf.min.js", "pdf.worker.min.js"):
    shutil.copy(os.path.join(libs, "pdfjs-dist", "build", nome), os.path.join(TMP, "vendor", "pdfjs", nome))
shutil.copy(os.path.join(libs, "pdf-lib", "dist", "pdf-lib.min.js"), os.path.join(TMP, "vendor", "pdf-lib.min.js"))

EDICAO = os.path.join(TMP, "Jornal de Teste 1234.pdf")
edicao_de_teste.gerar(EDICAO)
LIVRO = os.path.join(TMP, "livro.epub")
montar_epub(LIVRO, capitulos=3, paragrafos=4)


# ------------------------------------------- um servidor, como o do Pages
class Quieto(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=TMP, **k)

    def log_message(self, *a):
        pass


servidor = socketserver.TCPServer(("127.0.0.1", 0), Quieto)
PORTA = servidor.server_address[1]
threading.Thread(target=servidor.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{PORTA}/leitor.html"

falhas = []


def contexto(nav, sem_pdflib=False):
    ctx = nav.new_context(viewport={"width": 420, "height": 900}, has_touch=True)
    ctx.add_init_script(GANCHO + open(os.path.join(AQUI, "anthropic-falso.js"), encoding="utf-8").read())
    if sem_pdflib:
        # sem a biblioteca de recorte, nem a nossa nem a do CDN
        ctx.route("**/pdf-lib*", lambda r: r.fulfill(status=404, body="não"))
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: falhas.append("erro de JS: " + str(e)))
    pg.goto(BASE)
    pg.wait_for_function("() => window.__leitorCarregou === true", timeout=15000)
    pg.evaluate("(c) => api.motorNavegador.salvarChave(c)", CHAVE)
    return ctx, pg


def abrir_edicao(pg):
    pg.set_input_files("#arquivo", EDICAO)
    pg.wait_for_function("() => document.querySelectorAll('#grade-paginas .miniatura').length === 4",
                         timeout=20000)
    # a primeira miniatura desenhada de verdade, e não só o quadro vazio
    pg.wait_for_function("""() => { const c = document.querySelector('#grade-paginas canvas');
                              return c && c.width > 10; }""", timeout=20000)


def escolher(pg, paginas):
    for n in paginas:
        pg.locator(f"#grade-paginas .miniatura[data-p='{n}']").click(position={"x": 10, "y": 60})


def enviar(pg):
    """Toca em perguntar e, se o teto de custo avisar, segue mesmo assim.

    Devolve o texto do aviso, ou None. O aviso em si é comportamento certo: uma
    pergunta com busca passa do teto padrão, e o leitor tem de dizer antes."""
    pg.evaluate("() => document.getElementById('enviar').click()")
    pg.wait_for_timeout(300)
    if pg.locator("#painel-teto:not(.oculto)").count():
        aviso_ = pg.locator("#texto-teto").text_content()
        pg.click("#teto-seguir")
        return aviso_
    return None


def paginas_do_pdf_enviado(pg, indice):
    """Abre com o pdf.js o PDF que saiu no pedido e diz que páginas ele tem."""
    return pg.evaluate("""async (i) => {
      const leituras = window.__API.pedidos.filter(p => !p.corpo.stream
        && Array.isArray(p.corpo.messages[0].content));
      const doc = leituras[i].corpo.messages[0].content.find(b => b.type === 'document');
      if (!doc) return null;
      const bin = atob(doc.source.data);
      const bytes = new Uint8Array(bin.length);
      for (let k = 0; k < bin.length; k++) bytes[k] = bin.charCodeAt(k);
      const pdf = await pdfjsLib.getDocument({data: bytes}).promise;
      const marcas = [];
      for (let n = 1; n <= pdf.numPages; n++) {
        const t = await (await pdf.getPage(n)).getTextContent();
        const texto = t.items.map(x => x.str).join(' ');
        const m = texto.match(/MARCA-PAGINA-(\\d+)/);
        marcas.push(m ? Number(m[1]) : null);
      }
      return marcas;
    }""", indice)


with sync_playwright() as p:
    nav = p.chromium.launch(executable_path=CHROME) if CHROME else p.chromium.launch()
    ctx, pg = contexto(nav)

    print("1. o PDF abre na tela da edição, com uma miniatura por página")
    abrir_edicao(pg)
    print("   miniaturas:", pg.locator("#grade-paginas .miniatura").count(),
          "| título:", pg.locator("#edicao-titulo").text_content())
    if pg.locator("#edicao.oculto").count():
        falhas.append("o PDF não abriu a tela da edição")
    if pg.locator("#edicao-titulo").text_content() != "Jornal de Teste 1234":
        falhas.append("o título da edição não veio do nome do arquivo")

    print("2. escolher as páginas 2 e 4 — a matéria pula a 3")
    escolher(pg, [2, 4])
    contagem = pg.locator("#edicao-contagem").text_content()
    rotulo = pg.locator("#edicao-listar").text_content()
    print("   rodapé:", contagem, "|", rotulo)
    if contagem != "Páginas 2, 4":
        falhas.append(f"a seleção não ficou 2 e 4: «{contagem}»")
    if "US$" not in rotulo:
        falhas.append("o botão não mostra o custo estimado antes de ler")

    print("3. ver as matérias: só as páginas escolhidas vão ao modelo")
    pg.click("#edicao-listar")
    pg.wait_for_selector("#painel-materias:not(.oculto)", timeout=20000)
    enviadas = paginas_do_pdf_enviado(pg, 0)
    print("   páginas no PDF enviado:", enviadas)
    if enviadas != [2, 4]:
        falhas.append(f"O QUE IMPORTA: o PDF enviado não tem só as páginas 2 e 4: {enviadas}")
    leitura = pg.evaluate("() => window.__API.pedidos.filter(p => !p.corpo.stream).slice(-1)[0].corpo")
    print("   modelo:", leitura["model"], "| esforço:", leitura["output_config"]["effort"],
          "| cache no PDF:", "cache_control" in leitura["messages"][0]["content"][0])
    if leitura["model"] != "claude-sonnet-5-5":
        falhas.append(f"a leitura de páginas não usou o Sonnet 5.5: {leitura['model']}")
    if "cache_control" not in leitura["messages"][0]["content"][0]:
        falhas.append("o PDF foi sem marca de cache, e a transcrição pagaria tudo de novo")
    achadas = pg.locator(".materia-achada b").all_text_contents()
    print("   matérias achadas:", achadas)
    if achadas != ["O porto que mudou a cidade"]:
        falhas.append(f"a lista veio embrulhada e o leitor não a desembrulhou: {achadas}")

    print("4. transcrever: o PDF vem do cache, e a matéria abre no leitor")
    pg.locator("[data-transcrever='0']").click()
    pg.wait_for_selector("#leitura:not(.oculto)", timeout=20000)
    leituras = pg.evaluate("() => window.__API.leituras")
    print("   passos:", [(l["passo"], l["doCache"]) for l in leituras])
    if [l["passo"] for l in leituras] != ["listar", "transcrever"]:
        falhas.append(f"esperava listar e depois transcrever: {leituras}")
    elif not leituras[1]["doCache"]:
        falhas.append("O QUE IMPORTA: a transcrição mudou o pedido e perdeu o cache do PDF")
    titulo = pg.locator("#obra-titulo").text_content()
    blocos = pg.evaluate("() => api.app.livro.totalBlocos")
    primeiro = pg.evaluate("() => api.app.livro.blocos[0].t")
    print("   título:", titulo, "| blocos:", blocos, "| primeiro:", primeiro[:40])
    if titulo != "O porto que mudou a cidade" or blocos < 5:
        falhas.append("a matéria não abriu como documento do leitor")
    if "Aqui está" in pg.evaluate("() => api.app.livro.blocos.map(b => b.t).join(' ')"):
        falhas.append("o preâmbulo do modelo entrou no texto da matéria")
    if pg.evaluate("() => api.app.fronteira") != blocos - 1:
        falhas.append("a matéria não ficou inteira disponível para a conversa")

    print("5. a conversa sobre a matéria: regras de imprensa, sem busca por padrão")
    pg.evaluate("() => document.getElementById('btn-perguntar').click()")
    pg.wait_for_selector("#folha-perguntar.aberta", timeout=5000)
    pg.fill("#campo-chave", CHAVE)
    pg.click("#salvar-chave")
    visiveis = pg.evaluate("""() => ({
      modosLivro: !document.getElementById('modos').classList.contains('oculto'),
      modosMateria: !document.getElementById('modos-materia').classList.contains('oculto'),
      critica: !document.getElementById('abertura-livro').classList.contains('oculto'),
      web: !document.getElementById('abertura-materia').classList.contains('oculto')})""")
    print("   controles visíveis:", visiveis)
    if visiveis != {"modosLivro": False, "modosMateria": True, "critica": False, "web": True}:
        falhas.append(f"a folha mostra os controles do tipo errado: {visiveis}")
    pg.evaluate("() => window.__API.limpar()")
    pg.fill("#pergunta", "Quem assina a matéria?")
    pg.evaluate("() => document.getElementById('enviar').click()")
    pg.wait_for_function("() => window.__API.pedidos.length > 0 && !document.querySelector('.fala.pensando')",
                         timeout=15000)
    corpo = pg.evaluate("() => window.__API.ultimo().corpo")
    sistema = " ".join(b["text"] for b in corpo["system"])
    print("   regras de imprensa:", "imprensa" in sistema, "| fronteira de spoiler:", "REGRA ABSOLUTA" in sistema,
          "| ferramentas:", corpo.get("tools"))
    if "imprensa" not in sistema or "REGRA ABSOLUTA" in sistema:
        falhas.append("a matéria foi conversada com as regras de livro")
    if corpo.get("tools"):
        falhas.append("a busca foi junto sem ninguém pedir")
    if "3 milhões de toneladas" not in corpo["system"][-1]["text"]:
        falhas.append("o texto da matéria não foi na parte estável (cacheável) do pedido")

    print("6. outras coberturas: busca na web, fontes com link, custo da busca")
    antes = pg.evaluate("() => api.contaDoMes().total")
    pg.evaluate("() => { window.__API.limpar(); document.querySelector('[data-modo-pergunta=cobertura]').click(); }")
    pg.fill("#pergunta", "")
    # Com busca, a estimativa soma as buscas e o texto que elas trazem, e passa
    # do teto padrão de US$ 0,10 por pergunta. O leitor tem de avisar antes —
    # e «perguntar mesmo assim» tem de seguir com a busca.
    barrou = enviar(pg)
    print("   o teto avisou antes:", bool(barrou), "|", (barrou or "")[:80])
    pg.wait_for_function("() => document.querySelector('#conversa .fala:last-child a')", timeout=15000)
    corpo = pg.evaluate("() => window.__API.ultimo().corpo")
    print("   ferramenta:", corpo.get("tools"))
    if not corpo.get("tools") or corpo["tools"][0].get("name") != "web_search":
        falhas.append("o modo «outras coberturas» não ligou a busca")
    elif corpo["tools"][0].get("max_uses") != 4:
        falhas.append("a busca foi sem teto de usos")
    links = pg.evaluate("""() => [...document.querySelectorAll('#conversa .fala:last-child a')]
        .map(a => a.getAttribute('href'))""")
    print("   links na resposta:", links)
    if "https://exemplo.com.br/porto" not in links:
        falhas.append("a fonte citada não virou link")
    if any(not l.startswith("http") for l in links):
        falhas.append(f"SEGURANÇA: um link que não é http(s) entrou na resposta: {links}")
    depois = pg.evaluate("() => api.contaDoMes().total")
    print(f"   custo desta pergunta: US$ {depois - antes:.4f} (inclui US$ 0,01 da busca)")
    if depois - antes < 0.01:
        falhas.append("a busca na web não entrou na conta")
    historico = pg.evaluate("() => api.lerConversa(api.app.livro.id).falas.slice(-1)[0].texto")
    if "exemplo.com.br/porto" not in historico:
        falhas.append("as fontes não ficaram no histórico da conversa")

    print("7. um turno de busca pausado é retomado, intacto")
    pg.evaluate("() => { window.__API.limpar(); window.__API.roteiro('buscaPausada'); }")
    pg.fill("#pergunta", "E outros jornais?")
    enviar(pg)
    pg.wait_for_function("() => window.__API.buscas.some(b => b.retomada)", timeout=15000)
    pg.wait_for_function("() => !document.querySelector('.fala.pensando')", timeout=15000)
    buscas = pg.evaluate("() => window.__API.buscas.slice(-2)")
    fala = pg.locator("#conversa .fala").last.text_content()
    print("   chamadas:", buscas, "| última fala:", fala[:50])
    if not (len(buscas) == 2 and buscas[1].get("retomada") and buscas[1].get("intacto")):
        falhas.append(f"o turno pausado não voltou intacto: {buscas}")
    if "1990" not in fala or "⚠" in fala:
        falhas.append(f"a resposta retomada não chegou: «{fala[:60]}»")
    pg.evaluate("() => window.__API.roteiro('normal')")

    print("8. a estante sabe o que é edição e o que é matéria")
    pg.evaluate("() => document.querySelector('#folha-perguntar [data-fechar]').click()")
    pg.evaluate("() => document.getElementById('voltar').click()")
    pg.wait_for_selector("#estante:not(.oculto)", timeout=5000)
    linhas = pg.locator("#prateleira .livro").all_text_contents()
    print("   estante:", [l[:70] for l in linhas])
    if not any("📰" in l and "4 páginas" in l for l in linhas):
        falhas.append("a edição não aparece como edição na estante")
    if not any("📄" in l and "p. 2, 4" in l for l in linhas):
        falhas.append("a matéria não aparece com sua origem na estante")

    print("8b. da matéria de volta às páginas originais, para conferir")
    pg.locator("#prateleira .livro.materia").click()
    pg.wait_for_selector("#leitura:not(.oculto)", timeout=10000)
    pg.evaluate("() => document.getElementById('btn-perguntar').click()")
    pg.wait_for_selector("#folha-perguntar.aberta", timeout=5000)
    pg.click("#ver-originais")
    pg.wait_for_selector("#pagina-grande:not(.oculto)", timeout=15000)
    estado_ = pg.evaluate("""() => ({tela: !document.getElementById('edicao').classList.contains('oculto'),
      escolhidas: [...api.edicao.selecionadas].sort(), grande: api.edicao.grande.pagina})""")
    print("   ", estado_)
    if estado_ != {"tela": True, "escolhidas": [2, 4], "grande": 2}:
        falhas.append(f"«ver as páginas originais» não voltou às páginas da matéria: {estado_}")
    pg.click("#grande-fechar")
    pg.click("#edicao-voltar")
    pg.wait_for_selector("#estante:not(.oculto)", timeout=5000)

    print("9. livro continua sem busca na web, mesmo com o botão ligado")
    pg.evaluate("() => { api.estado.gravar('leitor.web', true); api.app.buscarWeb = true; }")
    pg.set_input_files("#arquivo", LIVRO)
    pg.wait_for_selector("#leitura:not(.oculto)", timeout=15000)
    pg.evaluate("() => document.getElementById('btn-perguntar').click()")
    pg.wait_for_selector("#folha-perguntar.aberta", timeout=5000)
    if not pg.evaluate("() => document.getElementById('abertura-materia').classList.contains('oculto')"):
        falhas.append("o botão de busca na web aparece num livro")
    pg.evaluate("() => window.__API.limpar()")
    pg.fill("#pergunta", "Quem é Helena?")
    pg.evaluate("() => document.getElementById('enviar').click()")
    pg.wait_for_function("() => window.__API.pedidos.length > 0", timeout=10000)
    tools = pg.evaluate("() => window.__API.ultimo().corpo.tools")
    print("   ferramentas no pedido do livro:", tools)
    if tools:
        falhas.append("O QUE IMPORTA: um livro mandou busca na web — a porta do spoiler")
    ctx.close()

    print("10. sem a biblioteca de recorte, as páginas vão como imagem")
    ctx, pg = contexto(nav, sem_pdflib=True)
    abrir_edicao(pg)
    escolher(pg, [3])
    pg.click("#edicao-listar")
    pg.wait_for_selector("#painel-materias:not(.oculto)", timeout=20000)
    leitura = pg.evaluate("() => window.__API.pedidos.filter(p => !p.corpo.stream).slice(-1)[0].corpo")
    tipos = [b["type"] for b in leitura["messages"][0]["content"]]
    nota = pg.locator("#nota-materias").text_content()
    paginas_esportes = pg.evaluate("() => api.edicao.listadas.find(m => /Esportes/.test(m.titulo)).paginas")
    print("   blocos enviados:", tipos, "| páginas da nota de esportes:", paginas_esportes)
    if tipos != ["image", "text"]:
        falhas.append(f"esperava uma imagem e o pedido: {tipos}")
    if "imagens" not in nota:
        falhas.append("a tela não avisou que leu pelas imagens")
    if paginas_esportes != [3]:
        falhas.append(f"uma página que não foi enviada (99) entrou na matéria: {paginas_esportes}")
    ctx.close()
    nav.close()

servidor.shutdown()
print()
print("FALHAS:", falhas if falhas else "nenhuma — da edição em PDF à conversa com busca")
sys.exit(1 if falhas else 0)
