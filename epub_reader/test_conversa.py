"""A conversa dentro do leitor, com a chave no navegador.

Rode com:  python3 test_conversa.py   (precisa do Playwright)

O que este teste existe para garantir, em ordem de importância:

1. Nada além da fronteira de leitura sai do aparelho. É a promessa do leitor
   inteiro, e agora ela atravessa a rede: antes o recorte ia para a área de
   transferência, onde a pessoa podia vê-lo; agora vai direto para a API, onde
   ninguém vê. Um erro aqui estraga o livro de quem confiou na ferramenta, e
   estraga em silêncio.
2. O cabeçalho de acesso direto do navegador vai no pedido. Sem ele a API
   recusa tudo, e a conversa não existe.
3. Cada jeito de falhar diz o que fazer: chave recusada, sem crédito, API
   sobrecarregada, rede fora, recusa do modelo, resposta cortada no teto.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright

from test_como_artifact import montar_epub

AQUI = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(tempfile.gettempdir(), "leitor-conversa")
CHROME = os.environ.get("CHROME_PATH") or None
GANCHO = "window.__leitorTestes = (api) => { window.api = api; };\n"
CHAVE = "sk-ant-api03-chave-de-teste"

os.makedirs(TMP, exist_ok=True)
PAGINA = os.path.join(TMP, "leitor.html")
subprocess.run([sys.executable, os.path.join(AQUI, "pagina.py"), PAGINA],
               check=True, stdout=subprocess.DEVNULL)
LIVRO = os.path.join(TMP, "livro.epub")
montar_epub(LIVRO, capitulos=8, paragrafos=10)

falhas = []


def abrir(pg, chave=None):
    """Abre o livro, para a leitura no meio e abre a folha de perguntar."""
    pg.set_input_files("#arquivo", LIVRO)
    pg.wait_for_timeout(2500)
    # a fronteira no meio do livro: metade lida, metade por ler
    pg.evaluate("""() => {
      const total = api.app.livro.totalBlocos;
      api.app.fronteira = Math.floor(total / 2);
      api.app.bloco = api.app.fronteira;
    }""")
    if chave:
        pg.evaluate("(c) => api.motorNavegador.salvarChave(c)", chave)
    pg.evaluate("() => document.getElementById('btn-perguntar').click()")
    pg.wait_for_timeout(400)


def perguntar(pg, texto, espera=1800):
    pg.fill("#pergunta", texto)
    pg.evaluate("() => document.getElementById('enviar').click()")
    pg.wait_for_timeout(espera)


def ultima_fala(pg):
    falas = pg.locator("#conversa .fala")
    return falas.last.text_content().strip() if falas.count() else ""


with sync_playwright() as p:
    nav = p.chromium.launch(executable_path=CHROME) if CHROME else p.chromium.launch()
    ctx = nav.new_context(viewport={"width": 420, "height": 900}, has_touch=True)
    ctx.add_init_script(GANCHO + open(os.path.join(AQUI, "anthropic-falso.js"),
                                      encoding="utf-8").read())
    pg = ctx.new_page()
    avisos: list = []
    pg.on("pageerror", lambda e: falhas.append("erro de JS: " + str(e)))
    pg.on("console", lambda m: avisos.append(m.text) if m.type == "warning" else None)
    pg.goto("file://" + PAGINA)
    pg.wait_for_timeout(1200)

    print("1. sem chave, o leitor pede a chave de saída")
    abrir(pg)
    # o painel aberto e o botão desativado: a pergunta que não pode ser
    # respondida não fica à espera de um toque que não vai funcionar
    if pg.locator("#painel-chave.oculto").count():
        falhas.append("sem chave, o painel da chave não apareceu")
    if not pg.evaluate("() => document.getElementById('enviar').disabled"):
        falhas.append("sem chave, o botão de perguntar estava ativo")
    print("   painel aberto:", pg.locator("#painel-chave.oculto").count() == 0,
          "| botão desativado:",
          pg.evaluate("() => document.getElementById('enviar').disabled"))

    print("2. uma chave que não é chave é recusada na hora")
    pg.fill("#campo-chave", "minha-senha-do-banco")
    pg.click("#salvar-chave")
    pg.wait_for_timeout(300)
    dito = pg.locator("#aviso").text_content().strip()
    print("   →", dito[:70])
    if "sk-ant-" not in dito:
        falhas.append(f"não avisou sobre o formato da chave: «{dito[:60]}»")
    if pg.evaluate("() => api.motorNavegador.temChave()"):
        falhas.append("guardou uma chave que não é chave")

    print("3. a chave certa, uma pergunta, e a resposta em pedaços")
    pg.fill("#campo-chave", CHAVE)
    pg.click("#salvar-chave")
    pg.wait_for_timeout(300)
    if not pg.evaluate("() => api.motorNavegador.temChave()"):
        falhas.append("não guardou a chave válida")
    perguntar(pg, "Onde Helena está agora?")
    resposta = ultima_fala(pg)
    print("   resposta:", resposta[:70])
    # os pedaços foram cortados no meio do JSON de propósito: se a emenda
    # estivesse errada, faltariam trechos ou nada chegaria
    if "Helena está em Ostende" not in resposta or "sem explicação" not in resposta:
        falhas.append(f"a resposta chegou incompleta: «{resposta[:80]}»")

    print("4. O QUE IMPORTA: nada além da fronteira foi enviado")
    dados = pg.evaluate("""() => {
      const p = window.__API.ultimo();
      const naoLidos = api.app.livro.blocos
        .filter(b => b.i > api.app.fronteira).map(b => b.t);
      const lidos = api.app.livro.blocos
        .filter(b => b.i <= api.app.fronteira).map(b => b.t);
      return {corpo: JSON.stringify(p.corpo), cabecalhos: p.cabecalhos,
              naoLidos, lidos, fronteira: api.app.fronteira,
              total: api.app.livro.totalBlocos};
    }""")
    corpo = dados["corpo"]
    vazados = [t for t in dados["naoLidos"] if t and len(t) > 40 and t[:40] in corpo]
    print(f"   fronteira no bloco {dados['fronteira']} de {dados['total']};"
          f" {len(dados['naoLidos'])} blocos não lidos")
    print("   blocos não lidos que apareceram no pedido:", len(vazados))
    if vazados:
        falhas.append(f"VAZOU {len(vazados)} bloco(s) não lidos para a API: "
                      f"«{vazados[0][:60]}»")
    # e a prova pela outra ponta: o que foi lido chegou, senão o teste acima
    # passaria só porque nada foi enviado
    if not any(t and len(t) > 40 and t[:40] in corpo for t in dados["lidos"]):
        falhas.append("nenhum bloco lido chegou à API — o recorte foi enviado vazio?")
    if "REGRA ABSOLUTA" not in corpo:
        falhas.append("as regras anti-spoiler não foram para o system prompt")

    print("5. o cabeçalho sem o qual a API recusa navegador")
    cab = dados["cabecalhos"]
    print("   anthropic-dangerous-direct-browser-access:",
          cab.get("anthropic-dangerous-direct-browser-access"))
    print("   anthropic-version:", cab.get("anthropic-version"),
          "| modelo:", json.loads(corpo)["model"])
    if cab.get("anthropic-dangerous-direct-browser-access") != "true":
        falhas.append("faltou o cabeçalho de acesso direto do navegador")
    if cab.get("anthropic-version") != "2023-06-01":
        falhas.append("faltou ou errou o anthropic-version")
    if cab.get("x-api-key") != CHAVE:
        falhas.append("a chave não foi no x-api-key")
    if json.loads(corpo)["model"] != "claude-opus-5-5":
        falhas.append("o modelo padrão não é o claude-opus-5-5 (o mais barato)")
    if json.loads(corpo)["max_tokens"] < 8000:
        falhas.append("max_tokens baixo: o raciocínio conta para ele e corta a resposta")
    if not json.loads(corpo).get("stream"):
        falhas.append("o pedido não pediu streaming")

    print("6. a segunda pergunta não reenvia o livro inteiro de novo")
    pg.evaluate("() => window.__API.limpar()")
    perguntar(pg, "E o relógio da torre?")
    n = pg.evaluate("""() => {
      const c = window.__API.ultimo().corpo;
      return {mensagens: c.messages.length,
              primeira: c.messages[0].content.length,
              ultima: c.messages[c.messages.length - 1].content.length};
    }""")
    print("   mensagens:", n["mensagens"], "| 1ª:", n["primeira"],
          "caracteres | última:", n["ultima"])
    if n["mensagens"] < 3:
        falhas.append("o histórico da conversa não foi enviado")
    if n["primeira"] > 400:
        falhas.append("a pergunta antiga foi reenviada com o recorte inteiro colado")

    print("6b. uma conta sem o Opus 5.5 cai no Opus 5 sozinha, e lembra")
    pg.evaluate("() => { window.__API.limpar(); window.__API.roteiro('semOpus55'); }")
    perguntar(pg, "e o mar de chumbo?")
    modelos = pg.evaluate("() => window.__API.pedidos.map(p => p.corpo.model)")
    print("   modelos tentados:", modelos)
    print("   respondeu:", ultima_fala(pg)[:52])
    if modelos != ["claude-opus-5-5", "claude-opus-5"]:
        falhas.append(f"não caiu para o Opus 5 sozinho: {modelos}")
    if "Helena está em Ostende" not in ultima_fala(pg):
        falhas.append("depois de cair para o Opus 5, não respondeu")
    pg.evaluate("() => window.__API.limpar()")
    perguntar(pg, "e depois disso?")
    if pg.evaluate("() => window.__API.pedidos.map(p => p.corpo.model)") != ["claude-opus-5"]:
        falhas.append("não lembrou que esta conta não tem o Opus 5.5")
    pg.evaluate("() => { window.__API.roteiro('normal'); api.motorNavegador.salvarModelo(''); }")

    print("7. um modelo que não aceita o pedido completo: desce e responde")
    pg.evaluate("() => { window.__API.limpar(); window.__API.roteiro('semPensar'); }")
    perguntar(pg, "Recapitule para mim")
    tentativas = pg.evaluate("() => window.__API.pedidos.map(p => !!p.corpo.thinking)")
    print("   pedidos desta pergunta (com thinking?):", tentativas)
    print("   respondeu:", ultima_fala(pg)[:56])
    if tentativas != [True, False]:
        falhas.append(f"não tentou o completo e depois o simples: {tentativas}")
    if "Helena está em Ostende" not in ultima_fala(pg):
        falhas.append("depois de descer para o pedido simples, não respondeu")
    # e lembra: a pergunta seguinte já sai simples, sem gastar uma recusa
    pg.evaluate("() => window.__API.limpar()")
    perguntar(pg, "E depois?")
    if pg.evaluate("() => window.__API.pedidos.map(p => !!p.corpo.thinking)") != [False]:
        falhas.append("não lembrou que este modelo recusa o pedido completo")
    pg.evaluate("() => api.motorNavegador.mudar('pedido', 'completo')")

    print("8. cada falha diz o que fazer")
    casos = [
        ("recusa", "recusou", "o modelo recusou o pedido"),
        ("cortada", "limite de tamanho", "a resposta bateu no teto"),
        ("semCredito", "crédito", "conta sem crédito"),
        ("sobrecarga", "sobrecarregada", "API sobrecarregada"),
        ("redeFora", "conexão", "sem rede"),
    ]
    for roteiro, espero, porque in casos:
        pg.evaluate("(r) => window.__API.roteiro(r)", roteiro)
        perguntar(pg, "e agora?")
        dito = ultima_fala(pg)
        print(f"   {porque:26} → {dito[:52]}")
        if espero not in dito:
            falhas.append(f"{porque}: disse «{dito[:70]}»")
        if roteiro == "semCredito":
            pg.evaluate("() => api.motorNavegador.mudar('pedido', 'completo')")

    print("8b. o portão da crítica muda o acordo, e só ele")
    pg.evaluate("() => { window.__API.roteiro('normal'); window.__API.limpar(); }")
    # desligado: o padrão. Conhecimento externo sobre a obra é vedado.
    perguntar(pg, "o que a crítica diz deste livro?")
    estrito = pg.evaluate("() => window.__API.ultimo().corpo.system")
    pg.evaluate("() => document.getElementById('abrir-critica').click()")
    pg.wait_for_timeout(300)
    pg.evaluate("() => window.__API.limpar()")
    perguntar(pg, "o que a crítica diz deste livro?")
    aberto = pg.evaluate("() => window.__API.ultimo().corpo.system")
    print("   desligado diz «vedado»:", "é vedado" in estrito)
    print("   ligado diz «liberado»:", "liberado" in aberto)
    if "é vedado" not in estrito:
        falhas.append("o padrão deixou de vedar conhecimento externo sobre a obra")
    if "liberado" not in aberto or "recepção" not in aberto:
        falhas.append("ligado, o portão não liberou crítica e contexto")
    # o que NÃO pode mudar: a fronteira do enredo, nos dois estados
    for rotulo, texto in (("estrito", estrito), ("aberto", aberto)):
        if "REGRA ABSOLUTA" not in texto or "é proibido revelar" not in texto:
            falhas.append(f"{rotulo}: a regra da fronteira do enredo desapareceu")
    if "filtre-a" not in aberto:
        falhas.append("aberto: falta mandar o modelo filtrar a crítica que pressupõe o fim")
    # e o recorte do livro continua parando na fronteira com o portão aberto
    vazados = pg.evaluate("""() => {
      const corpo = JSON.stringify(window.__API.ultimo().corpo);
      return api.app.livro.blocos.filter(b => b.i > api.app.fronteira)
        .filter(b => b.t && b.t.length > 40 && corpo.includes(b.t.slice(0, 40))).length;
    }""")
    print("   com o portão aberto, blocos não lidos enviados:", vazados)
    if vazados:
        falhas.append(f"o portão da crítica abriu o texto não lido: {vazados} blocos")
    # e a escolha sobrevive ao recarregamento, porque é um acordo, não um humor
    pg.reload()
    pg.wait_for_timeout(1200)
    if not pg.evaluate("() => api.app.critica"):
        falhas.append("o portão da crítica não foi lembrado depois de recarregar")
    pg.evaluate("() => { api.app.critica = false; api.estado.gravar('leitor.critica', false); }")

    print("9. apagar a chave desliga a conversa")
    pg.evaluate("() => { window.__API.roteiro('normal'); }")
    pg.evaluate("() => document.getElementById('btn-perguntar').click()")
    pg.wait_for_timeout(300)
    pg.evaluate("() => document.getElementById('btn-chave').click()")
    pg.wait_for_timeout(200)
    pg.click("#apagar-chave")
    pg.wait_for_timeout(300)
    if pg.evaluate("() => api.motorNavegador.temChave()"):
        falhas.append("apagar a chave não a apagou")
    if not pg.evaluate("() => document.getElementById('enviar').disabled"):
        falhas.append("sem chave, o botão de perguntar continuou ativo")
    print("   chave apagada e botão desativado:",
          not pg.evaluate("() => api.motorNavegador.temChave()"))

    sumidos = [a for a in avisos if "não existe" in a]
    if sumidos:
        falhas.append("elemento destruído — " + sumidos[0])
    ctx.close()
    nav.close()

print()
print("FALHAS:", falhas if falhas else "nenhuma — a conversa fala com a API e "
      "a fronteira se mantém")
sys.exit(1 if falhas else 0)
