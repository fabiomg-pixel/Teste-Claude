"""A porta de entrada: senha única, cookie de sessão, e um freio contra tentativa.

Enquanto o leitor roda na sua máquina, não há o que trancar — quem alcança o
localhost é você. Na nuvem a história inverte: o endereço é público, e sem uma
porta qualquer um que o descubra lê a sua biblioteca, apaga os seus livros e
gasta a sua chave da API conversando com o modelo.

O desenho é o mais simples que resolve:

- uma senha só, sua, em `EPUB_SENHA` (nunca no código, nunca no git);
- um cookie de sessão assinado, que vale 30 dias — o iPhone entra uma vez;
- a sincronização continua entrando pelo token `Bearer`, porque o aplicativo
  do Android fala com `/api/sync/*` sem navegador e sem cookie;
- um freio por IP, para que adivinhar a senha não seja de graça.

Com `EPUB_EXIGIR_SENHA=1` o servidor **se recusa a subir** sem senha. É o que
vai no ambiente da nuvem: esquecer de configurá-la derruba o serviço na hora,
em vez de deixá-lo aberto sem ninguém notar.
"""

from __future__ import annotations

import hmac
import os
import secrets
import time

from flask import (Response, jsonify, redirect, render_template_string,
                   request, session, url_for)

import store

SENHA = os.environ.get("EPUB_SENHA", "")
EXIGIR = os.environ.get("EPUB_EXIGIR_SENHA", "") not in ("", "0", "false", "no")

DIAS = 30
TENTATIVAS = 8              # erros tolerados antes do castigo
CASTIGO = 300               # segundos de espera depois disso
MEMORIA = 3600              # esquece um IP quieto por uma hora

_falhas: dict[str, tuple[int, float]] = {}


def exigida() -> bool:
    """Há porta? Sem senha configurada o leitor segue aberto (uso local)."""
    return bool(SENHA)


def conferir_configuracao() -> None:
    """Chamada na subida: na nuvem, sem senha é melhor não subir."""
    if EXIGIR and not SENHA:
        raise SystemExit(
            "EPUB_EXIGIR_SENHA está ligado e EPUB_SENHA está vazia.\n"
            "Este servidor ficaria aberto a quem descobrisse o endereço: sem\n"
            "contas, sem limite de tentativas, com a sua chave da API à mão.\n"
            "Defina a senha antes de subir  (ex.: fly secrets set EPUB_SENHA=…)."
        )


def chave_de_sessao() -> str:
    """A chave que assina o cookie.

    Guardada junto dos dados: se ela mudasse a cada reinício, toda sessão
    cairia — e no iPhone isso significa pedir senha de novo a cada deploy.
    """
    do_ambiente = os.environ.get("EPUB_SECRET")
    if do_ambiente:
        return do_ambiente
    caminho = os.path.join(store.DATA_DIR, "chave-sessao.txt")
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as fh:
            guardada = fh.read().strip()
        if guardada:
            return guardada
    os.makedirs(store.DATA_DIR, exist_ok=True)
    nova = secrets.token_urlsafe(48)
    with open(caminho, "w", encoding="utf-8") as fh:
        fh.write(nova)
    os.chmod(caminho, 0o600)
    return nova


# ------------------------------------------------------------------ freio

def _quem() -> str:
    """O IP do cliente. Atrás de um proxy, o primeiro do X-Forwarded-For."""
    encadeado = request.headers.get("X-Forwarded-For", "")
    if encadeado:
        return encadeado.split(",")[0].strip()
    return request.remote_addr or "?"


def _limpar(agora: float) -> None:
    for ip in [ip for ip, (_, quando) in _falhas.items() if agora - quando > MEMORIA]:
        _falhas.pop(ip, None)


def travado() -> float:
    """Segundos que ainda faltam de castigo para este IP (0 = pode tentar)."""
    agora = time.time()
    _limpar(agora)
    contadas, ultima = _falhas.get(_quem(), (0, 0.0))
    if contadas < TENTATIVAS:
        return 0.0
    return max(0.0, CASTIGO - (agora - ultima))


def anotar_falha() -> None:
    agora = time.time()
    contadas, ultima = _falhas.get(_quem(), (0, 0.0))
    if contadas >= TENTATIVAS and agora - ultima > CASTIGO:
        contadas = 0                      # cumpriu o castigo, recomeça
    _falhas[_quem()] = (contadas + 1, agora)


def esquecer_falhas() -> None:
    _falhas.pop(_quem(), None)


# ------------------------------------------------------------- a conferência

def senha_confere(tentativa: str) -> bool:
    return bool(SENHA) and hmac.compare_digest(tentativa.encode(), SENHA.encode())


def dentro() -> bool:
    return session.get("entrou") is True


# O aplicativo Android não tem navegador nem cookie: ele se identifica pelo
# token em cada pedido. Por isso /api/sync/* segue por fora desta porta —
# quem manda lá é o sync.token_confere.
LIVRES = ("/entrar", "/sair", "/api/sync", "/saude")


def liberada(caminho: str) -> bool:
    return any(caminho == livre or caminho.startswith(livre + "/")
               for livre in LIVRES)


def barrar():
    """O que responder a quem não entrou: JSON para a API, tela para o resto."""
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({"error": "Entre com a senha para usar o leitor.",
                        "entrar": url_for("entrar")}), 401
    return redirect(url_for("entrar", destino=request.full_path.rstrip("?")))


PAGINA = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Leitor sem spoiler</title>
<style>
  :root { --papel:#f3f2ec; --tinta:#1a1b1f; --meia:#6f7178; --linha:#dedcd3;
          --acento:#2f5175; --erro:#8c2f2f; }
  @media (prefers-color-scheme: dark) {
    :root { --papel:#15171b; --tinta:#c8c5bd; --meia:#7e8189; --linha:#282b31;
            --acento:#93b5d8; --erro:#e08585; }
  }
  * { box-sizing: border-box; }
  body { margin:0; min-height:100vh; display:grid; place-items:center;
         background:var(--papel); color:var(--tinta); padding:1.5rem;
         font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
  main { width:100%; max-width:22rem; }
  h1 { font-family: "Iowan Old Style", Charter, Georgia, serif;
       font-size:1.6rem; font-weight:600; margin:0 0 .3rem; letter-spacing:-.01em; }
  p { color:var(--meia); margin:0 0 1.5rem; font-size:.92rem; line-height:1.5; }
  label { display:block; font-size:.78rem; text-transform:uppercase;
          letter-spacing:.08em; color:var(--meia); margin-bottom:.4rem; }
  input { width:100%; padding:.8rem .9rem; font-size:1rem; border-radius:10px;
          border:1px solid var(--linha); background:transparent; color:inherit; }
  input:focus { outline:2px solid var(--acento); outline-offset:1px; }
  button { width:100%; margin-top:.9rem; padding:.85rem; font-size:1rem;
           font-weight:600; border:none; border-radius:10px; cursor:pointer;
           background:var(--acento); color:var(--papel); }
  .erro { color:var(--erro); font-size:.88rem; margin:.9rem 0 0; }
</style>
</head>
<body>
<main>
  <h1>Leitor sem spoiler</h1>
  <p>Sua biblioteca, e uma conversa que só conhece o livro até onde você leu.</p>
  <form method="post" autocomplete="on">
    <input type="hidden" name="destino" value="{{ destino }}">
    <label for="senha">Senha</label>
    <input id="senha" name="senha" type="password" autofocus required
           autocomplete="current-password" enterkeyhint="go">
    <button type="submit">Entrar</button>
    {% if erro %}<p class="erro">{{ erro }}</p>{% endif %}
  </form>
</main>
</body>
</html>
"""


def pagina(erro: str = "", destino: str = "/", codigo: int = 200) -> Response:
    corpo = render_template_string(PAGINA, erro=erro, destino=destino or "/")
    return Response(corpo, status=codigo, mimetype="text/html")


def instalar(app) -> None:
    """Liga a porta no app do Flask."""
    app.secret_key = chave_de_sessao()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=DIAS * 24 * 3600,
    )

    @app.before_request
    def _porta():
        if not exigida() or liberada(request.path) or dentro():
            return None
        if request.method == "OPTIONS":
            return None            # o preflight não carrega cookie; o CORS cuida
        return barrar()

    @app.route("/entrar", methods=["GET", "POST"])
    def entrar():
        if not exigida():
            return redirect("/")
        destino = (request.form.get("destino") or request.args.get("destino") or "/")
        if not destino.startswith("/") or destino.startswith("//"):
            destino = "/"          # não sirvo de trampolim para fora
        if request.method == "GET":
            return pagina(destino=destino)

        falta = travado()
        if falta:
            return pagina(f"Tentativas demais. Tente de novo em {int(falta) + 1}s.",
                          destino, 429)
        if not senha_confere(request.form.get("senha", "")):
            anotar_falha()
            return pagina("Senha errada.", destino, 401)

        esquecer_falhas()
        session.clear()
        session["entrou"] = True
        session.permanent = True
        return redirect(destino)

    @app.route("/sair")
    def sair():
        session.clear()
        return redirect(url_for("entrar"))

    @app.route("/saude")
    def saude():
        """Para o serviço de hospedagem saber se o processo está vivo."""
        return {"ok": True}
