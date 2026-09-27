"""Séries: os volumes anteriores entram, e cada um pela fronteira dele.

Rode com:  python3 test_serie.py   (precisa do Playwright)

Uma trilogia é onde a regra anti-spoiler fica mais fácil de errar, porque há mais
de uma fronteira em jogo ao mesmo tempo:

- o volume que estou lendo tem a minha posição atual;
- um volume anterior que eu terminei está inteiro liberado;
- um volume anterior que eu ABANDONEI na metade está liberado até a metade.

O terceiro é o caso que um código descuidado erra: é tentador tratar «volume
anterior» como «volume lido». Este teste monta exatamente essa situação.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright

from test_como_artifact import montar_epub

AQUI = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(tempfile.gettempdir(), "leitor-serie")
CHROME = os.environ.get("CHROME_PATH") or None
GANCHO = "window.__leitorTestes = (api) => { window.api = api; };\n"
CHAVE = "sk-ant-api03-chave-de-teste"

os.makedirs(TMP, exist_ok=True)
PAGINA = os.path.join(TMP, "leitor.html")
subprocess.run([sys.executable, os.path.join(AQUI, "pagina.py"), PAGINA],
               check=True, stdout=subprocess.DEVNULL)

# três volumes distintos: o tamanho diferente basta para dar impressões digitais
# diferentes, que é como o leitor identifica um livro
VOLUMES = []
for n, caps in ((1, 4), (2, 5), (3, 6)):
    caminho = os.path.join(TMP, f"vol{n}.epub")
    montar_epub(caminho, capitulos=caps, paragrafos=4)
    VOLUMES.append(caminho)

falhas = []

with sync_playwright() as p:
    nav = p.chromium.launch(executable_path=CHROME) if CHROME else p.chromium.launch()
    ctx = nav.new_context(viewport={"width": 420, "height": 900}, has_touch=True)
    ctx.add_init_script(GANCHO + open(os.path.join(AQUI, "anthropic-falso.js"),
                                      encoding="utf-8").read())
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: falhas.append("erro de JS: " + str(e)))
    pg.goto("file://" + PAGINA)
    pg.wait_for_timeout(1200)
    pg.evaluate("(c) => api.motorNavegador.salvarChave(c)", CHAVE)

    print("1. três volumes na estante, lidos de formas diferentes")
    ids = []
    for i, caminho in enumerate(VOLUMES):
        pg.set_input_files("#arquivo", caminho)
        pg.wait_for_timeout(2200)
        ids.append(pg.evaluate("() => api.app.livro.id"))
        if i == 0:
            # volume 1 lido até o fim, e resumido
            pg.evaluate("""() => {
              api.app.fronteira = api.app.livro.totalBlocos - 1;
              api.app.bloco = api.app.fronteira;
              api.memoria.enfileirar();
            }""")
        elif i == 1:
            # volume 2 ABANDONADO no meio, e resumido até onde deu
            pg.evaluate("""() => {
              api.app.fronteira = Math.floor(api.app.livro.totalBlocos / 2);
              api.app.bloco = api.app.fronteira;
              api.memoria.enfileirar();
            }""")
        pg.wait_for_timeout(2600)
        pg.evaluate("() => api.app.livro && document.getElementById('voltar').click()")
        pg.wait_for_timeout(500)
    print("   ids:", ids)

    print("2. declarar a série pelos três, pela própria tela")
    for i, livro in enumerate(ids):
        pg.evaluate("(id) => api.__abrir(id)", livro) if False else None
        pg.evaluate("""async (a) => {
          const r = await api.guarda.pegar(a.id);
          api.guardarFichaDaSerie(r.impressao, {nome: 'O Relógio', volume: a.v});
        }""", {"id": livro, "v": i + 1})
    series = pg.evaluate("() => api.estado.ler('leitor.series', {})")
    print("   livros na série:", len(series))
    if len(series) != 3:
        falhas.append(f"declarei 3 volumes, ficaram {len(series)}")

    print("3. abrir o volume 3: os anteriores aparecem, em ordem")
    pg.evaluate("(id) => document.querySelector('.livro') && 0", None)
    pg.set_input_files("#arquivo", VOLUMES[2])
    pg.wait_for_timeout(2500)
    # o volume 3 também é lido um pouco e resumido: sem memória própria, o
    # passo 5 («desligar a série não tira a memória do livro») não provaria nada
    pg.evaluate("""() => {
      api.app.fronteira = 9;
      api.app.bloco = 9;
      api.memoria.enfileirar();
    }""")
    pg.wait_for_timeout(2600)
    pg.evaluate("async () => { await api.prepararSerie(); }")
    pg.wait_for_timeout(400)
    proprios = pg.evaluate("() => Object.keys(api.app.resumos).length")
    print("   capítulos resumidos do próprio volume 3:", proprios)
    if not proprios:
        falhas.append("o volume em uso ficou sem memória própria")
    s = pg.evaluate("() => api.app.serie")
    print("   série:", s["nome"], "| volume:", s["volume"])
    for a in s["anteriores"]:
        print(f"   ← vol {a['volume']}: {len(a['capitulos'])} capítulos, lido até {a['pct']}%")
    if [a["volume"] for a in s["anteriores"]] != [1, 2]:
        falhas.append(f"anteriores errados: {[a['volume'] for a in s['anteriores']]}")
    if s["anteriores"][1]["pct"] > 70:
        falhas.append(f"o volume 2 deveria estar pela metade; está em {s['anteriores'][1]['pct']}%")

    print("4. O QUE IMPORTA: o volume abandonado entra só até onde foi lido")
    dados = pg.evaluate("""() => {
      const p = api.montarPedido();
      // os capítulos do volume 2 que NÃO foram resumidos são os não lidos
      const vol2 = api.app.serie.anteriores.find(a => a.volume === 2);
      return {mensagem: p.mensagem, sistema: p.sistema,
              resumidosNoVol2: vol2.capitulos.map(c => c.i)};
    }""")
    msg = dados["mensagem"]
    print("   capítulos do volume 2 no contexto:", dados["resumidosNoVol2"])
    print("   tem a seção da série:", "Volumes anteriores desta série" in msg)
    if "Volumes anteriores desta série" not in msg:
        falhas.append("a seção dos volumes anteriores não entrou")
    if "eu li só" not in msg:
        falhas.append("o contexto não avisa que o volume 2 foi lido em parte")
    if "SÉRIE:" not in dados["sistema"]:
        falhas.append("as regras não explicam a série ao modelo")
    # a regra do volume em uso continua de pé
    if "REGRA ABSOLUTA" not in dados["sistema"]:
        falhas.append("a regra do volume em uso desapareceu")
    # e o volume 3 (em uso) não vazou
    vazados = pg.evaluate("""() => {
      const m = api.montarPedido().mensagem;
      return api.app.livro.blocos.filter(b => b.i > api.app.fronteira)
        .filter(b => b.t && b.t.length > 40 && m.includes(b.t.slice(0, 40))).length;
    }""")
    print("   blocos não lidos do volume em uso:", vazados)
    if vazados:
        falhas.append(f"a série abriu o texto não lido do volume em uso: {vazados}")

    print("5. desligar o botão tira os anteriores, e só eles")
    if "O que aconteceu em cada capítulo" not in msg:
        falhas.append("a memória do próprio volume não estava no contexto, com a série ligada")
    pg.evaluate("() => document.getElementById('abrir-serie').click()")
    pg.wait_for_timeout(300)
    semSerie = pg.evaluate("() => api.montarPedido()")
    print("   sem a série:", "Volumes anteriores" not in semSerie["mensagem"])
    if "Volumes anteriores" in semSerie["mensagem"]:
        falhas.append("desligar o botão não tirou os volumes anteriores")
    if "SÉRIE:" in semSerie["sistema"]:
        falhas.append("desligado, as regras ainda falam de série")
    if "O que aconteceu em cada capítulo" not in semSerie["mensagem"]:
        falhas.append("desligar a série também tirou a memória do próprio livro")
    pg.evaluate("() => document.getElementById('abrir-serie').click()")

    print("6. um volume anterior sem resumo não entra, e a tela diz por quê")
    pg.evaluate("""() => {
      // apaga a memória do volume 1 como se ele nunca tivesse sido resumido
      const todas = api.estado.ler('leitor.series', {});
      api.estado.gravar('leitor.resumos.' + Object.keys(todas)
        .find(k => todas[k].volume === 1), {});
    }""")
    # o id local é o que indexa os resumos: apaga pelo id conhecido
    pg.evaluate("(id) => api.estado.gravar('leitor.resumos.' + id, {})", ids[0])
    pg.evaluate("async () => { await api.prepararSerie(); api.desenharSerie(); }")
    pg.wait_for_timeout(300)
    s = pg.evaluate("() => api.app.serie.anteriores.map(a => [a.volume, a.capitulos.length])")
    msg = pg.evaluate("() => api.montarPedido().mensagem")
    print("   anteriores e seus capítulos:", s)
    if "Volume 1" in msg:
        falhas.append("um volume sem resumo nenhum entrou no contexto")
    if "Volume 2" not in msg:
        falhas.append("o volume 2, que tem resumos, deixou de entrar")

    ctx.close()
    nav.close()

print()
print("FALHAS:", falhas if falhas else "nenhuma — a série entra, cada volume pela sua fronteira")
sys.exit(1 if falhas else 0)
