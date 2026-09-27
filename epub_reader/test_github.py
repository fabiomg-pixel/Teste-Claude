"""A camada do GitHub contra uma API falsa.

O falso implementa só o que o leitor usa — blobs, árvores, commits — e,
principalmente, recusa o PATCH da referência quando o ramo andou. É essa
recusa que prova o controle de concorrência: sem ela, dois aparelhos
gravando quase ao mesmo tempo perdem o trabalho um do outro em silêncio.
"""
import json
import os
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright

AQUI = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(tempfile.gettempdir(), "leitor-github")
CHROME = os.environ.get("CHROME_PATH") or None
GANCHO = "window.__leitorTestes = (api) => { window.api = api; };\n"

os.makedirs(TMP, exist_ok=True)
PAGINA = os.path.join(TMP, "leitor.html")
subprocess.run([sys.executable, os.path.join(AQUI, "pagina.py"), PAGINA],
               check=True, stdout=subprocess.DEVNULL)

from test_como_artifact import montar_epub          # noqa: E402

montar_epub(os.path.join(TMP, "semente.epub"))

falhas = []
with sync_playwright() as p:
    nav = p.chromium.launch(executable_path=CHROME) if CHROME else p.chromium.launch()
    ctx = nav.new_context(viewport={"width": 820, "height": 1180})
    ctx.add_init_script(GANCHO + open(os.path.join(AQUI, "github-falso.js"), encoding="utf-8").read())
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: falhas.append("erro de JS: " + str(e)))
    pg.goto("file://" + PAGINA)
    pg.wait_for_timeout(2000)

    print("1. conectar")
    for token, repo, espero in [("ficha-errada", "biblioteca", "expirado"),
                                ("ficha-valida", "nao-existe", "não encontrado")]:
        r = pg.evaluate("""async ([t, r]) => { try {
              await api.github.conectar('fabio', r, t); return 'conectou (ruim)';
            } catch (e) { return e.message; } }""", [token, repo])
        print(f"   {token}/{repo} → {r[:60]}")
        if espero not in r:
            falhas.append(f"mensagem pouco clara para {token}/{repo}")
    r = pg.evaluate("async () => await api.github.conectar('fabio','biblioteca','ficha-valida')")
    print("   válido →", r)
    if not r.get("privado"):
        falhas.append("não reconheceu o repositório privado")

    print("1b. um repositório criado sem README — sem commit nenhum")
    # É o caso de quem clica «New repository» e não marca «Add a README»: o
    # repositório existe, e toda leitura da cabeça responde 409. O leitor tem de
    # resolver isso sozinho; mandar a pessoa ao site fazer um commit à mão foi o
    # que ele fazia, e é trabalho nosso.
    pg.evaluate("() => window.__GH.esvaziar()")
    r = pg.evaluate("async () => await api.github.conectar('fabio','biblioteca','ficha-valida')")
    print("   conectar num repositório vazio →", r)
    if not r.get("semeado"):
        falhas.append("não percebeu que o repositório estava vazio")
    if not pg.evaluate("() => window.__GH.temCabeca()"):
        falhas.append("o repositório continuou sem commit depois de conectar")
    print("   agora tem:", pg.evaluate("() => window.__GH.arquivos()"))
    # e daí para frente é um repositório normal: a gravação tem de funcionar
    r = pg.evaluate("""async () => {
      await api.biblioteca.sincronizarEstado('zz00',
        {fronteira: 3, posicao: {bloco: 3, em: 10}, marcas: []}, 'Semente');
      return window.__GH.arquivos();
    }""")
    print("   grava depois de semear:", r)
    if "estado/zz00.json" not in r:
        falhas.append("não consegui gravar no repositório recém-semeado")
    # conectar de novo não semeia duas vezes
    r = pg.evaluate("async () => await api.github.conectar('fabio','biblioteca','ficha-valida')")
    if r.get("semeado"):
        falhas.append("semeou de novo um repositório que já tinha commits")

    print("2. enviar um livro de 2 MB (caminho de blobs)")
    pg.evaluate("""async () => {
      const bytes = new Uint8Array(2*1024*1024);
      for (let i = 0; i < bytes.length; i++) bytes[i] = i & 255;
      return await api.biblioteca.enviarLivro(
        {impressao:'aa11', titulo:'A Travessia', autor:'Marta',
         bytes: bytes.buffer, totalBlocos:900},
        {fronteira:40, posicao:{bloco:40, em:1000},
         marcas:[{id:'m1', bloco:3, texto:'trecho', em:900}]});
    }""")
    arquivos = pg.evaluate("() => window.__GH.arquivos()")
    tam = pg.evaluate("() => window.__GH.tamanho('livros/aa11.epub')")
    print("   repositório:", arquivos, "| EPUB:", tam, "bytes")
    if tam != 2 * 1024 * 1024:
        falhas.append(f"o EPUB foi gravado com {tam} bytes")
    if "indice.json" not in arquivos:
        falhas.append("o índice não foi gravado junto")

    print("3. a estante de outro aparelho, sem baixar livro nenhum")
    r = pg.evaluate("async () => (await api.biblioteca.listar()).livros")
    print("   →", json.dumps(r, ensure_ascii=False)[:100])
    if not r or r[0]["titulo"] != "A Travessia":
        falhas.append("a estante não veria o título sem baixar o EPUB")

    print("4. a corrida: outro aparelho grava entre a nossa leitura e a escrita")
    r = pg.evaluate("""async () => {
      const original = api.github.commitar.bind(api.github);
      let primeira = true, recusas = 0;
      api.github.commitar = async (m, msg, base) => {
        if (primeira) { primeira = false;
          window.__GH.gravarPorFora('estado/aa11.json', JSON.stringify(
            {fronteira:120, posicao:{bloco:120, em:2000},
             marcas:[{id:'m2', bloco:9, texto:'do outro', em:1900}]})); }
        const ok = await original(m, msg, base);
        if (!ok) recusas++;
        return ok;
      };
      // o que um aparelho real manda: o próprio estado, com a própria marca
      const saida = await api.biblioteca.sincronizarEstado('aa11',
        {fronteira:45, posicao:{bloco:45, em:1500},
         marcas:[{id:'m1', bloco:3, texto:'trecho', em:900}]}, 'A Travessia');
      api.github.commitar = original;
      return {saida, recusas};
    }""")
    e = r["saida"]
    print("   recusas do GitHub:", r["recusas"])
    print("   resultado:", json.dumps(e, ensure_ascii=False)[:130])
    if r["recusas"] != 1:
        falhas.append(f"o GitHub deveria recusar uma vez; recusou {r['recusas']}")
    if e["fronteira"] != 120:
        falhas.append(f"a fronteira do outro aparelho se perdeu: {e['fronteira']}")
    if e["posicao"]["bloco"] != 120:
        falhas.append("a posição mais recente não venceu")
    if {m["id"] for m in e["marcas"]} != {"m1", "m2"}:
        falhas.append(f"as marcas não se somaram: {[m['id'] for m in e['marcas']]}")

    gravado = json.loads(pg.evaluate("() => window.__GH.ler('estado/aa11.json')"))
    if gravado["fronteira"] != 120 or len(gravado["marcas"]) != 2:
        falhas.append("o repositório não ficou com a mescla")

    print("4b. a memória de capítulos atravessa, e o mais adiantado ganha")
    r = pg.evaluate("""async () => {
      // outro aparelho já deixou resumos dos capítulos 0 e 1
      await api.biblioteca.sincronizarResumos('aa11', {
        0: {ate: 9, texto: 'resumo do outro aparelho', em: 100},
        1: {ate: 19, texto: 'cap 1 pelo outro', em: 100}});
      // este aparelho tem o 1 mais adiantado (leu até mais longe) e um 2 novo
      return await api.biblioteca.sincronizarResumos('aa11', {
        1: {ate: 25, texto: 'cap 1 mais completo', em: 200},
        2: {ate: 39, texto: 'cap 2 só daqui', em: 200}});
    }""")
    print("   capítulos na memória:", sorted(r.keys()))
    print("   cap 1 ficou com:", r["1"]["texto"])
    if sorted(r.keys()) != ["0", "1", "2"]:
        falhas.append(f"a memória não se somou entre aparelhos: {sorted(r.keys())}")
    if r["1"]["texto"] != "cap 1 mais completo":
        falhas.append("o resumo menos adiantado sobrescreveu o mais adiantado")
    if r["0"]["texto"] != "resumo do outro aparelho":
        falhas.append("perdeu o resumo que só o outro aparelho tinha")
    if "resumos/aa11.json" not in pg.evaluate("() => window.__GH.arquivos()"):
        falhas.append("a memória não foi gravada no repositório")

    print("5. baixar o livro de volta, byte a byte")
    r = pg.evaluate("""async () => {
      const {livros} = await api.biblioteca.listar();
      const bytes = await api.biblioteca.baixar(livros[0].sha);
      let ok = bytes.length === 2*1024*1024;
      for (let i = 0; ok && i < bytes.length; i += 9973) ok = bytes[i] === (i & 255);
      return ok;
    }""")
    print("   intacto:", r)
    if not r:
        falhas.append("o EPUB voltou corrompido")

    print("6. a tela de conexão, tocada como a pessoa toca")
    # Um contexto novo: localStorage limpo e um GitHub falso limpo, como um
    # aparelho que nunca viu o repositório. É o caminho que a pessoa percorre,
    # e não a camada por baixo — um botão desligado do seu tratador passaria
    # por todos os testes acima sem que nada disso aparecesse.
    ctx2 = nav.new_context(viewport={"width": 420, "height": 900}, has_touch=True)
    ctx2.add_init_script(GANCHO + open(os.path.join(AQUI, "github-falso.js"),
                                       encoding="utf-8").read())
    pg2 = ctx2.new_page()
    avisos = []
    pg2.on("pageerror", lambda e: falhas.append("erro de JS na tela: " + str(e)))
    pg2.on("console", lambda m: avisos.append(m.text) if m.type == "warning" else None)
    pg2.goto("file://" + PAGINA)
    pg2.wait_for_timeout(1500)

    sumidos = [a for a in avisos if "não existe" in a]
    if sumidos:
        falhas.append("elemento destruído na tela de conexão — " + sumidos[0])

    # na primeira execução o convite aparece sem ninguém ir procurá-lo
    if pg2.locator("#painel-sync.oculto").count():
        falhas.append("na primeira execução o painel de conexão não se abriu")

    # Semeia o repositório com um livro de verdade, como outro aparelho teria
    # deixado, e depois esquece a configuração: daqui para frente é só a tela.
    with open(os.path.join(TMP, "semente.epub"), "rb") as fh:
        semente = list(fh.read())
    pg2.evaluate("""async (bytes) => {
      const cru = new Uint8Array(bytes);
      await api.github.conectar('fabio', 'biblioteca', 'ficha-valida');
      const imp = await api.impressaoDigital(cru.buffer);
      await api.biblioteca.enviarLivro(
        {impressao: imp, titulo: 'Livro de teste', autor: 'Ninguém',
         bytes: cru.buffer, totalBlocos: 54},
        {fronteira: 12, posicao: {bloco: 12, em: 1000}, marcas: []});
      api.github.config = {dono: '', repo: '', token: '', ramo: ''};
    }""", semente)
    antes = pg2.evaluate("() => window.__GH.arquivos()")

    def ligar(repo, token):
        pg2.fill("#campo-repo", repo)
        pg2.fill("#campo-gh-token", token)
        pg2.click("#salvar-gh")
        pg2.wait_for_timeout(700)
        return pg2.locator("#aviso").text_content().strip()

    for repo, token, espero, porque in [
        ("fabio", "ficha-valida", "usuario/nome", "formato errado do repositório"),
        ("fabio/biblioteca", "", "token", "token em branco"),
        ("fabio/biblioteca", "ficha-errada", "expirado", "token recusado"),
        ("fabio/nao-existe", "ficha-valida", "não encontrado", "repositório inexistente"),
    ]:
        dito = ligar(repo, token)
        print(f"   {porque:32} → {dito[:56]}")
        if espero not in dito:
            falhas.append(f"{porque}: a tela disse «{dito[:60]}»")
        if pg2.evaluate("() => api.github.ligado"):
            falhas.append(f"{porque}: a tela guardou uma configuração que não funciona")

    # a URL inteira, colada da barra de endereço, tem de servir
    dito = ligar("https://github.com/fabio/biblioteca.git", "ficha-valida")
    print("   URL colada do navegador          →", dito[:56])
    if not pg2.evaluate("() => api.github.ligado"):
        falhas.append("não aceitou a URL colada do navegador")
    if pg2.evaluate("() => api.sincronia.modo") != "github":
        falhas.append("ligar ao repositório não mudou o modo de sincronia")
    if pg2.locator("#desligar-gh.oculto").count():
        falhas.append("o botão de desligar não apareceu depois de ligar")

    # o livro do outro aparelho desce sozinho: a estante nasce cheia
    pg2.wait_for_timeout(4000)
    livros = pg2.locator("#prateleira .livro").count()
    pct = pg2.locator("#prateleira .livro .pct").first.text_content().strip()
    print(f"   estante depois de ligar: {livros} livro(s), andamento {pct}")
    if livros != 1:
        falhas.append(f"a estante deveria ter o livro do repositório; tem {livros}")
    if pct in ("—", "0%"):
        falhas.append("o livro desceu sem a fronteira de leitura do outro aparelho")

    # e o mesmo livro não volta para o repositório como se fosse outro
    depois = pg2.evaluate("() => window.__GH.arquivos()")
    if [a for a in depois if a.endswith(".epub")] != [a for a in antes if a.endswith(".epub")]:
        falhas.append(f"o livro baixado foi reenviado como outro: {depois}")

    # o token sobrevive a um recarregamento — senão religar seria diário
    pg2.reload()
    pg2.wait_for_timeout(1500)
    if not pg2.evaluate("() => api.github.ligado"):
        falhas.append("o repositório não foi lembrado depois de recarregar")

    pg2.evaluate("""() => {
      if (document.getElementById('painel-sync').classList.contains('oculto'))
        document.getElementById('abrir-sync').click();
    }""")
    pg2.wait_for_timeout(300)
    if pg2.input_value("#campo-repo") != "fabio/biblioteca":
        falhas.append("o painel não mostra o repositório já ligado")

    # token que expirou depois de ligado: a sincronia de fundo não pode calar
    pg2.evaluate("""() => {
      const c = api.github.config;
      api.github.config = {dono: c.dono, repo: c.repo, token: 'ficha-expirada', ramo: c.ramo};
    }""")
    pg2.evaluate("() => { document.getElementById('aviso').textContent = ''; }")
    pg2.evaluate("async () => await api.sincronizarTudo(true)")
    pg2.wait_for_timeout(1200)
    dito = pg2.locator("#aviso").text_content().strip()
    marca = pg2.locator("#estado-sync").text_content().strip()
    print("   token expirado em segundo plano  →", (dito or "(calado)")[:56], "|", marca)
    if "expirado" not in dito:
        falhas.append(f"o token expirado falhou em silêncio: «{dito[:60]}»")
    if "token" not in marca:
        falhas.append(f"a estante não mostra que a sincronia parou: «{marca}»")

    pg2.click("#desligar-gh")
    pg2.wait_for_timeout(300)
    if pg2.evaluate("() => api.github.ligado"):
        falhas.append("desligar não desligou")
    print("   desligar                         →",
          pg2.locator("#aviso").text_content().strip()[:56])
    ctx2.close()

    nav.close()

print()
print("FALHAS:", falhas if falhas else "nenhuma — a camada do GitHub está redonda")
sys.exit(1 if falhas else 0)
