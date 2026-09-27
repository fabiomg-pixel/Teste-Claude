"""As cinco peças que cercam a leitura: histórico, cache, sentido, destaques, notas.

Rode com:  python3 test_extras.py   (precisa do Playwright)

Cada uma tem um jeito próprio de falhar em silêncio, e é esse jeito que este
teste procura:

- o histórico pode ser guardado e nunca lido de volta;
- o cache pode estar «ligado» com algo volátil no prefixo, que o invalida a cada
  pergunta sem erro nenhum — só a conta no fim do mês denuncia;
- o sentido de uma palavra pode mandar o livro inteiro junto;
- a exportação pode incluir o que não foi lido.
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
TMP = os.path.join(tempfile.gettempdir(), "leitor-extras")
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


def perguntar(pg, texto, espera=1600):
    pg.fill("#pergunta", texto)
    pg.evaluate("() => document.getElementById('enviar').click()")
    pg.wait_for_timeout(espera)


with sync_playwright() as p:
    nav = p.chromium.launch(executable_path=CHROME) if CHROME else p.chromium.launch()
    ctx = nav.new_context(viewport={"width": 420, "height": 900}, has_touch=True)
    ctx.add_init_script(GANCHO + open(os.path.join(AQUI, "anthropic-falso.js"),
                                      encoding="utf-8").read())
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: falhas.append("erro de JS: " + str(e)))
    pg.goto("file://" + PAGINA)
    pg.wait_for_timeout(1200)
    pg.set_input_files("#arquivo", LIVRO)
    pg.wait_for_timeout(2500)

    # a chave pela tela, e não por baixo: gravá-la direto no armazenamento deixa
    # o botão de perguntar desativado, porque é a tela que o redesenha
    pg.evaluate("() => document.getElementById('btn-perguntar').click()")
    pg.wait_for_timeout(400)
    pg.fill("#campo-chave", CHAVE)
    pg.click("#salvar-chave")
    pg.wait_for_timeout(300)
    if pg.evaluate("() => document.getElementById('enviar').disabled"):
        falhas.append("o botão de perguntar ficou desativado depois de guardar a chave")
    pg.evaluate("() => document.querySelector('#folha-perguntar [data-fechar]').click()")
    pg.wait_for_timeout(300)

    pg.evaluate("""() => {
      api.app.fronteira = 19;
      api.app.bloco = 19;
      api.memoria.enfileirar();
    }""")
    pg.wait_for_timeout(3000)
    livroId = pg.evaluate("() => api.app.livro.id")

    print("1. o cache: o prefixo é estável entre perguntas")
    pg.evaluate("() => document.getElementById('btn-perguntar').click()")
    pg.wait_for_timeout(400)
    pg.evaluate("() => window.__API.limpar()")
    perguntar(pg, "quem é Helena?")
    perguntar(pg, "e o relógio?")
    sistemas = pg.evaluate("""() => window.__API.pedidos.filter(p => p.corpo.stream)
        .map(p => p.corpo.system)""")
    print("   perguntas enviadas:", len(sistemas))
    if len(sistemas) < 2:
        falhas.append("não consegui duas perguntas para comparar o prefixo")
    else:
        # o system é um vetor de blocos; o último leva a marca de cache
        blocos = sistemas[0]
        print("   blocos do system:", [b.get("type") for b in blocos])
        marcados = [b for b in blocos if b.get("cache_control")]
        print("   blocos com cache_control:", len(marcados))
        if len(marcados) != 1:
            falhas.append(f"esperava 1 bloco marcado para cache, achei {len(marcados)}")
        # O QUE IMPORTA: byte a byte igual entre as duas perguntas
        if json.dumps(sistemas[0], ensure_ascii=False) != json.dumps(sistemas[1], ensure_ascii=False):
            falhas.append("o prefixo mudou entre duas perguntas — o cache nunca vai pegar")
        else:
            print("   prefixo idêntico nas duas perguntas: sim")
        # e o que é volátil ficou FORA dele
        # ensure_ascii=False: com o escape padrão, «capítulo» virava
        # «cap\u00edtulo» e toda busca por acento falhava em silêncio
        prefixo = json.dumps(sistemas[0], ensure_ascii=False)
        if "% do livro" in prefixo:
            falhas.append("a porcentagem de leitura entrou no prefixo e o invalida a cada página")
        if "Onde estou" in prefixo:
            falhas.append("«Onde estou» é volátil e entrou no prefixo")
        # ...e que o que é grande e estável ficou DENTRO
        if "O que aconteceu em cada capítulo" not in prefixo:
            falhas.append("os resumos ficaram fora do prefixo cacheável")

    print("2. virar a página muda a mensagem, não o prefixo")
    pg.evaluate("() => window.__API.limpar()")
    antes = pg.evaluate("() => JSON.stringify(api.montarPedido().blocos)")
    pg.evaluate("() => { api.app.bloco = 15; }")
    depois = pg.evaluate("() => JSON.stringify(api.montarPedido().blocos)")
    print("   prefixo sobreviveu a andar no texto:", antes == depois)
    if antes != depois:
        falhas.append("andar no texto mudou o prefixo cacheável")

    print("3. o histórico da conversa sobrevive a fechar o livro")
    n = pg.evaluate("""() => {
      const g = api.lerConversa(api.app.livro.id);
      return g.falas.length;
    }""")
    print("   falas guardadas:", n)
    if n < 4:
        falhas.append(f"esperava as 4 falas das duas perguntas; há {n}")
    pg.evaluate("() => document.getElementById('voltar').click()")
    pg.wait_for_timeout(600)
    if pg.locator("#conversa .fala").count():
        falhas.append("a conversa do livro anterior ficou na tela depois de sair")
    pg.set_input_files("#arquivo", LIVRO)
    pg.wait_for_timeout(2500)
    voltaram = pg.locator("#conversa .fala").count()
    print("   falas redesenhadas ao reabrir:", voltaram)
    if voltaram != n:
        falhas.append(f"reabrir o livro trouxe {voltaram} falas de {n}")

    print("4. apagar a conversa apaga em todo lugar (lápide)")
    juntas = pg.evaluate("""() => {
      const antiga = {limpoEm: 0, falas: [
        {id: 'a1', papel: 'user', texto: 'velha', em: 100},
        {id: 'a2', papel: 'assistant', texto: 'resposta velha', em: 101}]};
      const limpa = {limpoEm: 200, falas: [
        {id: 'b1', papel: 'user', texto: 'nova', em: 300}]};
      return api.mesclarConversas(antiga, limpa);
    }""")
    print("   depois da mescla:", [f["texto"] for f in juntas["falas"]])
    if [f["texto"] for f in juntas["falas"]] != ["nova"]:
        falhas.append("a lápide não apagou: as falas antigas voltaram na mescla")
    if juntas["limpoEm"] != 200:
        falhas.append("a marca de limpeza não sobreviveu à mescla")

    print("5. o sentido de uma palavra manda a frase, não o livro")
    pg.evaluate("() => { api.app.fronteira = 19; api.app.bloco = 10; window.__API.limpar(); }")
    pg.evaluate("""async () => {
      api.app.selecionado = 'Parágrafo';
      await api.pedirSentido();
    }""")
    pg.wait_for_timeout(1500)
    ped = pg.evaluate("() => window.__API.pedidos.filter(p => !p.corpo.stream).slice(-1)[0]")
    tamanho = len(json.dumps(ped["corpo"]))
    print("   modelo:", ped["corpo"]["model"], "| tamanho do pedido:", tamanho, "bytes")
    print("   cartão:", pg.locator("#sentido-texto").text_content()[:56])
    if ped["corpo"]["model"] != "claude-haiku-4-5":
        falhas.append(f"o sentido não usou o modelo barato: {ped['corpo']['model']}")
    if tamanho > 2000:
        falhas.append(f"o sentido mandou contexto demais: {tamanho} bytes")
    if pg.locator("#cartao-sentido.oculto").count():
        falhas.append("o cartão do sentido não apareceu")

    print("6. as notas em Markdown levam os destaques, e nada não lido")
    pg.evaluate("""() => {
      api.app.marcas = [
        {id: 'm1', bloco: 3, texto: 'um trecho do começo', cor: 'mare', em: 10,
         nota: 'minha observação'},
        {id: 'm2', bloco: 12, texto: 'outro mais adiante', cor: 'musgo', em: 20}];
    }""")
    md = pg.evaluate("() => api.notasEmMarkdown()")
    print("   linhas:", len(md.splitlines()), "| tem a nota:", "minha observação" in md)
    for precisa in ("# ", "> um trecho do começo", "> outro mais adiante",
                    "minha observação", "Conversa sobre o livro"):
        if precisa not in md:
            falhas.append(f"as notas não têm «{precisa}»")
    naoLidos = pg.evaluate("""() => api.app.livro.blocos
        .filter(b => b.i > api.app.fronteira).map(b => b.t)""")
    vazados = [t for t in naoLidos if t and len(t) > 40 and t[:40] in md]
    print("   blocos não lidos nas notas:", len(vazados))
    if vazados:
        falhas.append(f"a exportação levou {len(vazados)} blocos não lidos")

    print("7. cada destaque leva à pergunta")
    pg.evaluate("() => { api.app.selecionado = ''; }")
    pg.evaluate("""() => {
      document.getElementById('btn-sumario').click();
      document.getElementById('ver-anotacoes').click();
    }""")
    pg.wait_for_timeout(400)
    botoes = pg.locator("[data-perguntar]").count()
    print("   botões «perguntar» nos destaques:", botoes)
    if botoes != 2:
        falhas.append(f"esperava 2 botões de perguntar, há {botoes}")
    if pg.locator("#exportar-notas.oculto").count():
        falhas.append("o botão de exportar não aparece na aba de anotações")
    pg.locator("[data-perguntar]").first.click()
    pg.wait_for_timeout(600)
    print("   trecho levado:", pg.evaluate("() => api.app.selecionado")[:40])
    if pg.evaluate("() => api.app.selecionado") != "um trecho do começo":
        falhas.append("o botão do destaque não levou o trecho à pergunta")
    if pg.evaluate("() => api.app.modoPergunta") != "explicar":
        falhas.append("o botão do destaque não pôs o modo «explicar»")

    ctx.close()
    nav.close()

print()
print("FALHAS:", falhas if falhas else "nenhuma — as cinco peças estão de pé")
sys.exit(1 if falhas else 0)
