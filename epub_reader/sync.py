"""Sincronização entre aparelhos.

O servidor guarda, por livro, o estado de leitura e (opcionalmente) o próprio
arquivo EPUB. Cada aparelho manda o que tem e recebe de volta o resultado da
mescla — nunca uma substituição.

A regra de mescla é por campo, e é o que evita perder trabalho:

* ``fronteira`` fica com o **maior** valor. Ela só cresce, então não há
  conflito real; e é justamente a que não pode retroceder, senão a barreira
  anti-spoiler afrouxaria sozinha.
* ``posicao`` fica com a mais recente pelo relógio de quem escreveu.
* ``marcas`` são unidas por id, com lápides: apagar num aparelho apaga em
  todos, sem ressuscitar o destaque na próxima sincronização.

O livro é identificado pela impressão digital do arquivo, então o mesmo EPUB
baixado em dois aparelhos casa sozinho.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time

import store

TOKEN_PATH = os.path.join(store.DATA_DIR, "token-sync.txt")
PRAZO_LAPIDE = 90 * 24 * 3600      # lápides somem depois de 90 dias

ESQUEMA = """
CREATE TABLE IF NOT EXISTS sync_livros (
    impressao   TEXT PRIMARY KEY,
    titulo      TEXT,
    autor       TEXT,
    estado      TEXT NOT NULL,
    arquivo     TEXT,
    tamanho     INTEGER NOT NULL DEFAULT 0,
    atualizado  REAL NOT NULL
);
"""


def preparar() -> None:
    store.init()
    with store.connection() as conn:
        conn.executescript(ESQUEMA)


# --------------------------------------------------------------------------
# token


def token() -> str:
    """Token de acesso; criado na primeira execução e guardado em disco."""
    do_ambiente = os.environ.get("EPUB_SYNC_TOKEN")
    if do_ambiente:
        return do_ambiente.strip()
    os.makedirs(store.DATA_DIR, exist_ok=True)
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH) as fh:
            guardado = fh.read().strip()
        if guardado:
            return guardado
    novo = secrets.token_urlsafe(18)
    with open(TOKEN_PATH, "w") as fh:
        fh.write(novo)
    os.chmod(TOKEN_PATH, 0o600)
    return novo


def token_confere(cabecalho: str | None) -> bool:
    if not cabecalho:
        return False
    partes = cabecalho.split(None, 1)
    enviado = partes[1].strip() if len(partes) == 2 and partes[0].lower() == "bearer" else cabecalho.strip()
    return secrets.compare_digest(enviado, token())


# --------------------------------------------------------------------------
# impressão digital


def impressao_digital(dados: bytes) -> str:
    """Identidade do livro: tamanho + hash. O mesmo arquivo em dois aparelhos
    dá a mesma impressão, sem depender de metadados que variam."""
    resumo = hashlib.sha256()
    resumo.update(str(len(dados)).encode())
    resumo.update(dados[:262144])
    resumo.update(dados[-262144:] if len(dados) > 262144 else b"")
    return resumo.hexdigest()[:32]


# --------------------------------------------------------------------------
# mescla


def estado_vazio() -> dict:
    return {"posicao": {"bloco": 0, "em": 0.0}, "fronteira": 0, "marcas": [],
            "atualizado": 0.0}


def _limpar_lapides(marcas: list[dict], agora: float) -> list[dict]:
    return [m for m in marcas
            if not (m.get("apagadoEm") and agora - float(m["apagadoEm"]) > PRAZO_LAPIDE)]


def mesclar(a: dict, b: dict, agora: float | None = None) -> dict:
    """Mescla dois estados do mesmo livro. Comutativa: a ordem não importa."""
    agora = time.time() if agora is None else agora
    a = a or estado_vazio()
    b = b or estado_vazio()

    pos_a = a.get("posicao") or {"bloco": 0, "em": 0.0}
    pos_b = b.get("posicao") or {"bloco": 0, "em": 0.0}
    posicao = pos_a if float(pos_a.get("em", 0)) >= float(pos_b.get("em", 0)) else pos_b

    marcas: dict[str, dict] = {}
    for marca in list(a.get("marcas") or []) + list(b.get("marcas") or []):
        chave = marca.get("id")
        if not chave:
            continue
        atual = marcas.get(chave)
        if atual is None:
            marcas[chave] = dict(marca)
            continue
        # entre duas versões da mesma marca vence a mais recente; entre uma
        # edição e uma exclusão, vence quem aconteceu depois
        quando_novo = max(float(marca.get("apagadoEm") or 0), float(marca.get("em") or 0))
        quando_atual = max(float(atual.get("apagadoEm") or 0), float(atual.get("em") or 0))
        if quando_novo > quando_atual:
            marcas[chave] = dict(marca)

    return {
        "posicao": {"bloco": int(posicao.get("bloco", 0)), "em": float(posicao.get("em", 0))},
        "fronteira": max(int(a.get("fronteira", 0) or 0), int(b.get("fronteira", 0) or 0)),
        "marcas": _limpar_lapides(sorted(marcas.values(), key=lambda m: m.get("bloco", 0)), agora),
        "atualizado": agora,
    }


# --------------------------------------------------------------------------
# armazenamento


def listar() -> list[dict]:
    preparar()
    with store.connection() as conn:
        linhas = conn.execute(
            "SELECT impressao, titulo, autor, tamanho, atualizado,"
            " arquivo IS NOT NULL AS tem_arquivo FROM sync_livros ORDER BY atualizado DESC"
        ).fetchall()
    saida = []
    for linha in linhas:
        item = dict(linha)
        item["tem_arquivo"] = bool(item["tem_arquivo"])
        saida.append(item)
    return saida


def ler(impressao: str) -> dict | None:
    preparar()
    with store.connection() as conn:
        linha = conn.execute(
            "SELECT * FROM sync_livros WHERE impressao = ?", (impressao,)
        ).fetchone()
    if linha is None:
        return None
    item = dict(linha)
    item["estado"] = json.loads(item["estado"])
    item["tem_arquivo"] = bool(item.pop("arquivo", None))
    return item


def gravar(impressao: str, estado: dict, titulo: str = "", autor: str = "") -> dict:
    """Grava o estado já mesclado com o que havia no servidor."""
    preparar()
    anterior = ler(impressao)
    mesclado = mesclar(anterior["estado"] if anterior else estado_vazio(), estado)
    with store.connection() as conn:
        conn.execute(
            """INSERT INTO sync_livros (impressao, titulo, autor, estado, tamanho, atualizado)
                    VALUES (?,?,?,?,0,?)
               ON CONFLICT(impressao) DO UPDATE SET
                    estado = excluded.estado,
                    titulo = COALESCE(NULLIF(excluded.titulo, ''), sync_livros.titulo),
                    autor  = COALESCE(NULLIF(excluded.autor, ''), sync_livros.autor),
                    atualizado = excluded.atualizado""",
            (impressao, titulo or "", autor or "",
             json.dumps(mesclado, ensure_ascii=False), mesclado["atualizado"]),
        )
    return mesclado


def caminho_do_arquivo(impressao: str) -> str | None:
    preparar()
    with store.connection() as conn:
        linha = conn.execute(
            "SELECT arquivo FROM sync_livros WHERE impressao = ?", (impressao,)
        ).fetchone()
    if linha is None or not linha["arquivo"]:
        return None
    return linha["arquivo"] if os.path.exists(linha["arquivo"]) else None


def guardar_arquivo(impressao: str, dados: bytes, titulo: str = "", autor: str = "") -> dict:
    preparar()
    pasta = os.path.join(store.DATA_DIR, "sync")
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, f"{impressao}.epub")
    with open(caminho, "wb") as fh:
        fh.write(dados)
    agora = time.time()
    with store.connection() as conn:
        conn.execute(
            """INSERT INTO sync_livros (impressao, titulo, autor, estado, arquivo, tamanho, atualizado)
                    VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(impressao) DO UPDATE SET
                    arquivo = excluded.arquivo,
                    tamanho = excluded.tamanho,
                    titulo = COALESCE(NULLIF(excluded.titulo, ''), sync_livros.titulo),
                    autor  = COALESCE(NULLIF(excluded.autor, ''), sync_livros.autor),
                    atualizado = excluded.atualizado""",
            (impressao, titulo or "", autor or "",
             json.dumps(estado_vazio(), ensure_ascii=False), caminho, len(dados), agora),
        )
    return {"impressao": impressao, "tamanho": len(dados)}


def apagar(impressao: str) -> None:
    caminho = caminho_do_arquivo(impressao)
    with store.connection() as conn:
        conn.execute("DELETE FROM sync_livros WHERE impressao = ?", (impressao,))
    if caminho and os.path.exists(caminho):
        try:
            os.remove(caminho)
        except OSError:
            pass
