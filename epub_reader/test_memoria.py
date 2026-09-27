"""A memória do livro: um resumo por capítulo, e o que ela não pode deixar entrar.

Rode com:  python3 test_memoria.py   (precisa do Playwright)

O resumo resolve um problema real — sem ele o modelo conhece um romance de trinta
capítulos pelos três últimos — e cria um risco novo: ele é texto gerado que entra
no contexto sem passar pelo mesmo caminho do recorte. Se um capítulo não lido
fosse resumido, o spoiler entraria pela porta da memória, e o recorte continuaria
impecável enquanto a promessa já estaria quebrada.

Então o primeiro caso é: só capítulo inteiramente lido é resumido.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright

from test_como_artifact import montar_epub

AQUI = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(tempfile.gettempdir(), "leitor-memoria")
CHROME = os.environ.get("CHROME_PATH") or None
GANCHO = "window.__leitorTestes = (api) => { window.api = api; };\n"
CHAVE = "sk-ant-api03-chave-de-teste"

os.makedirs(TMP, exist_ok=True)
PAGINA = os.path.join(TMP, "leitor.html")
subprocess.run([sys.executable, os.path.join(AQUI, "pagina.py"), PAGINA],
               check=True, stdout=subprocess.DEVNULL)
LIVRO = os.path.join(TMP, "livro.epub")
montar_epub(LIVRO, capitulos=8, paragrafos=6)

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
    pg.set_input_files("#arquivo", LIVRO)
    pg.wait_for_timeout(2500)

    capitulos = pg.evaluate("""() => api.app.livro.capitulos
        .map(c => ({i: c.indice, t: c.titulo, de: c.primeiro, ate: c.ultimo}))""")
    print("capítulos do livro:", len(capitulos))

    print("1. a leitura para no meio do capítulo 4: resume 1 a 3, não o 4")
    # a fronteira dentro do capítulo 4 (índice 4 no spine, por causa da capa)
    alvo = [c for c in capitulos if c["ate"] >= c["de"]][3]
    pg.evaluate("""(b) => {
      api.app.fronteira = b;
      api.app.bloco = b;
      api.memoria.enfileirar();
    }""", (alvo["de"] + alvo["ate"]) // 2)
    pg.wait_for_timeout(2500)

    resumidos = pg.evaluate("() => Object.keys(api.app.resumos).map(Number).sort((a,b)=>a-b)")
    inteiros = pg.evaluate("() => api.memoria.lidosPorInteiro().map(c => c.indice)")
    print("   capítulos inteiramente lidos:", inteiros)
    print("   capítulos resumidos:", resumidos)
    if resumidos != sorted(inteiros):
        falhas.append(f"resumiu {resumidos} para os lidos {sorted(inteiros)}")
    if alvo["i"] in resumidos:
        falhas.append("VAZOU: resumiu o capítulo em que a leitura está, lido pela metade")

    print("2. O QUE IMPORTA: cada resumo foi feito do texto do próprio capítulo")
    # o falso devolve RESUMO[<começo do que recebeu>]; dá para ver qual capítulo
    marcas = pg.evaluate("() => Object.entries(api.app.resumos).map(([i, r]) => [i, r.texto])")
    errados = []
    for indice, texto in marcas:
        # o corpo de cada capítulo do EPUB de teste começa por «Capítulo N», e o
        # capítulo N mora no índice N do spine (o 0 é a capa). Se o resumo
        # guardado sob o índice i cita outro número, o texto veio do lugar errado.
        achado = re.search(r"Capítulo (\d+)", texto)
        if not achado or achado.group(1) != str(indice):
            errados.append((indice, texto[:70]))
    print("   resumos conferidos:", len(marcas), "| com o capítulo errado:", len(errados))
    if errados:
        falhas.append(f"resumo de outro capítulo: {errados[0]}")

    print("3. os resumos entram no contexto, e nada além deles")
    pg.evaluate("() => document.getElementById('btn-perguntar').click()")
    pg.wait_for_timeout(400)
    dados = pg.evaluate("""() => {
      const p = api.montarPedido();
      return {mensagem: p.mensagem,
              naoLidos: api.app.livro.blocos.filter(b => b.i > api.app.fronteira).map(b => b.t)};
    }""")
    msg = dados["mensagem"]
    print("   tem a seção de resumos:", "O que aconteceu em cada capítulo" in msg)
    if "O que aconteceu em cada capítulo" not in msg:
        falhas.append("os resumos não entraram no contexto")
    if msg.count("RESUMO[") != len(marcas):
        falhas.append(f"entraram {msg.count('RESUMO[')} resumos, havia {len(marcas)}")
    vazados = [t for t in dados["naoLidos"] if t and len(t) > 40 and t[:40] in msg]
    print("   blocos não lidos no contexto:", len(vazados))
    if vazados:
        falhas.append(f"VAZOU {len(vazados)} blocos não lidos no contexto com resumos")

    print("4. avançar a leitura resume só o capítulo novo")
    pg.evaluate("() => window.__API.limpar()")
    proximo = [c for c in capitulos if c["ate"] >= c["de"]][4]
    pg.evaluate("(b) => { api.app.bloco = b; api.app.fronteira = b; api.memoria.enfileirar(); }",
                proximo["ate"])
    pg.wait_for_timeout(2500)
    novos = pg.evaluate("() => window.__API.pedidos.filter(p => !p.corpo.stream).length")
    agora = pg.evaluate("() => Object.keys(api.app.resumos).length")
    print("   chamadas de resumo nesta rodada:", novos, "| total de resumos:", agora)
    if novos != 2:
        falhas.append(f"deveria resumir os 2 capítulos novos; fez {novos} chamadas")

    print("5. o resumo usa um modelo mais barato, de propósito")
    modelos = pg.evaluate("""() => [...new Set(window.__API.pedidos
        .filter(p => !p.corpo.stream).map(p => p.corpo.model))]""")
    print("   modelo dos resumos:", modelos)
    if modelos != ["claude-sonnet-5"]:
        falhas.append(f"os resumos não usaram o modelo barato: {modelos}")

    print("6. a conta aparece, e sem inventar precisão")
    custo = pg.evaluate("() => { api.desenharCusto(); return document.getElementById('estado-custo').textContent; }")
    conta = pg.evaluate("() => api.contaDoMes()")
    print("   →", custo)
    if not custo or "este mês" not in custo:
        falhas.append(f"o custo não apareceu: «{custo}»")
    if conta["pedidos"] != agora:
        falhas.append(f"contou {conta['pedidos']} pedidos para {agora} resumos")
    # 1200 entrada + 90 saída no Sonnet 5 = 1200*2 + 90*10 por milhão
    esperado = agora * (1200 * 2 + 90 * 10) / 1e6
    if abs(conta["total"] - esperado) > 1e-9:
        falhas.append(f"conta errada: {conta['total']} em vez de {esperado}")

    print("7. uma falha ao resumir não trava nem vira laço quente")
    pg.evaluate("""() => {
      window.__API.limpar();
      window.__API.roteiro('resumoRuim');
      api.app.resumos = {};
      api.memoria.enfileirar();
    }""")
    pg.wait_for_timeout(2500)
    tentativas = pg.evaluate("() => window.__API.pedidos.filter(p => !p.corpo.stream).length")
    travou = pg.evaluate("() => api.memoria.moendo")
    aviso = pg.evaluate("() => document.getElementById('estado-memoria').textContent")
    print("   tentativas:", tentativas, "| ainda moendo:", travou)
    print("   diz na tela:", aviso[:70])
    if travou:
        falhas.append("a fila de resumos travou moendo")
    if tentativas > len([c for c in capitulos if c["ate"] >= c["de"]]):
        falhas.append(f"tentou demais depois da falha: {tentativas} chamadas")
    if "Parei de resumir" not in aviso:
        falhas.append(f"não disse que parou de resumir: «{aviso[:60]}»")

    ctx.close()
    nav.close()

print()
print("FALHAS:", falhas if falhas else "nenhuma — a memória é longa e para na fronteira")
sys.exit(1 if falhas else 0)
