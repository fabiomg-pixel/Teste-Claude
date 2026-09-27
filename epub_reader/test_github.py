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

    nav.close()

print()
print("FALHAS:", falhas if falhas else "nenhuma — a camada do GitHub está redonda")
sys.exit(1 if falhas else 0)
