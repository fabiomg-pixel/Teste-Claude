"""Persistência: biblioteca, progresso, destaques, notas, conversa e memória.

SQLite para os dados estruturados; um JSON por livro (gerado no import) para
o conteúdo em si, mantido em cache na memória do processo.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from collections import OrderedDict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("EPUB_DATA_DIR", os.path.join(BASE_DIR, "data"))
BOOKS_DIR = os.path.join(DATA_DIR, "books")
DB_PATH = os.path.join(DATA_DIR, "library.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    author        TEXT,
    language      TEXT,
    description   TEXT,
    epub_path     TEXT NOT NULL,
    data_path     TEXT NOT NULL,
    cover_path    TEXT,
    total_blocks  INTEGER NOT NULL DEFAULT 0,
    total_words   INTEGER NOT NULL DEFAULT 0,
    total_chapters INTEGER NOT NULL DEFAULT 0,
    added_at      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS progress (
    book_id        TEXT PRIMARY KEY REFERENCES books(id) ON DELETE CASCADE,
    cur_block      INTEGER NOT NULL DEFAULT 0,
    furthest_block INTEGER NOT NULL DEFAULT 0,
    seconds_read   INTEGER NOT NULL DEFAULT 0,
    words_read     INTEGER NOT NULL DEFAULT 0,
    updated_at     REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS bookmarks (
    id         TEXT PRIMARY KEY,
    book_id    TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    block      INTEGER NOT NULL,
    chapter    INTEGER NOT NULL,
    label      TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS highlights (
    id         TEXT PRIMARY KEY,
    book_id    TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    block      INTEGER NOT NULL,
    chapter    INTEGER NOT NULL,
    text       TEXT NOT NULL,
    color      TEXT NOT NULL DEFAULT 'amarelo',
    note       TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         TEXT PRIMARY KEY,
    book_id    TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    mode       TEXT,
    boundary   INTEGER,
    sources    TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS summaries (
    book_id    TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    chapter    INTEGER NOT NULL,
    end_block  INTEGER NOT NULL,
    content    TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (book_id, chapter, end_block)
);

CREATE INDEX IF NOT EXISTS idx_hl_book ON highlights(book_id, block);
CREATE INDEX IF NOT EXISTS idx_bm_book ON bookmarks(book_id, block);
CREATE INDEX IF NOT EXISTS idx_chat_book ON chat_messages(book_id, created_at);
"""

_init_lock = threading.Lock()
_initialized = False


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init() -> None:
    global _initialized
    with _init_lock:
        if _initialized:
            return
        os.makedirs(BOOKS_DIR, exist_ok=True)
        with _connect() as conn:
            conn.executescript(SCHEMA)
        _initialized = True


class connection:
    """Context manager curto para uma conexão SQLite (thread-safe)."""

    def __enter__(self) -> sqlite3.Connection:
        init()
        self.conn = _connect()
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.conn.commit()
        self.conn.close()
        return False


def new_id() -> str:
    return uuid.uuid4().hex[:16]


# --------------------------------------------------------------------------
# conteúdo do livro (JSON em disco + cache LRU)

_cache: "OrderedDict[str, dict]" = OrderedDict()
_cache_lock = threading.Lock()
_CACHE_MAX = 3


def save_content(book_id: str, content: dict) -> str:
    os.makedirs(BOOKS_DIR, exist_ok=True)
    path = os.path.join(BOOKS_DIR, f"{book_id}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(content, fh, ensure_ascii=False)
    return path


def load_content(book: sqlite3.Row | dict) -> dict:
    book_id = book["id"]
    with _cache_lock:
        cached = _cache.get(book_id)
        if cached is not None:
            _cache.move_to_end(book_id)
            return cached
    with open(book["data_path"], encoding="utf-8") as fh:
        content = json.load(fh)
    with _cache_lock:
        _cache[book_id] = content
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
    return content


def drop_cache(book_id: str) -> None:
    with _cache_lock:
        _cache.pop(book_id, None)


# --------------------------------------------------------------------------
# livros


def create_book(meta: dict, epub_path: str, data_path: str, cover_path: str | None,
                totals: dict) -> str:
    book_id = totals.get("id") or new_id()
    with connection() as conn:
        conn.execute(
            """INSERT INTO books (id, title, author, language, description,
                                  epub_path, data_path, cover_path, total_blocks,
                                  total_words, total_chapters, added_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (book_id, meta.get("title") or "Sem título", meta.get("creator") or "",
             meta.get("language") or "", meta.get("description") or "",
             epub_path, data_path, cover_path, totals["blocks"], totals["words"],
             totals["chapters"], time.time()),
        )
        conn.execute(
            "INSERT INTO progress (book_id, updated_at) VALUES (?, ?)",
            (book_id, time.time()),
        )
    return book_id


def list_books() -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            """SELECT b.*, p.cur_block, p.furthest_block, p.seconds_read, p.updated_at
                 FROM books b LEFT JOIN progress p ON p.book_id = b.id
                ORDER BY COALESCE(p.updated_at, b.added_at) DESC"""
        ).fetchall()
    books = []
    for row in rows:
        item = dict(row)
        total = max(item["total_blocks"], 1)
        item["percent"] = round(100 * (item["furthest_block"] or 0) / total, 1)
        item.pop("epub_path", None)
        item.pop("data_path", None)
        item["has_cover"] = bool(item.pop("cover_path", None))
        books.append(item)
    return books


def get_book(book_id: str) -> sqlite3.Row | None:
    with connection() as conn:
        return conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()


def delete_book(book_id: str) -> None:
    book = get_book(book_id)
    if book is None:
        return
    with connection() as conn:
        conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
    drop_cache(book_id)
    for path in (book["epub_path"], book["data_path"], book["cover_path"]):
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


# --------------------------------------------------------------------------
# progresso


def get_progress(book_id: str) -> dict:
    with connection() as conn:
        row = conn.execute("SELECT * FROM progress WHERE book_id = ?", (book_id,)).fetchone()
    if row is None:
        return {"cur_block": 0, "furthest_block": 0, "seconds_read": 0,
                "words_read": 0, "updated_at": 0}
    return dict(row)


def update_progress(book_id: str, block: int, seconds: int = 0, words: int = 0) -> dict:
    block = max(0, int(block))
    with connection() as conn:
        conn.execute(
            """UPDATE progress
                  SET cur_block = ?,
                      furthest_block = MAX(furthest_block, ?),
                      seconds_read = seconds_read + ?,
                      words_read = words_read + ?,
                      updated_at = ?
                WHERE book_id = ?""",
            (block, block, max(0, int(seconds)), max(0, int(words)), time.time(), book_id),
        )
    return get_progress(book_id)


def set_boundary(book_id: str, block: int) -> dict:
    """Ajusta manualmente a fronteira anti-spoiler (o "já li até aqui")."""
    with connection() as conn:
        conn.execute(
            "UPDATE progress SET furthest_block = ?, updated_at = ? WHERE book_id = ?",
            (max(0, int(block)), time.time(), book_id),
        )
    return get_progress(book_id)


# --------------------------------------------------------------------------
# marcadores e destaques


def list_bookmarks(book_id: str) -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM bookmarks WHERE book_id = ? ORDER BY block", (book_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def add_bookmark(book_id: str, block: int, chapter: int, label: str) -> dict:
    item = {"id": new_id(), "book_id": book_id, "block": int(block),
            "chapter": int(chapter), "label": label or "", "created_at": time.time()}
    with connection() as conn:
        conn.execute(
            "INSERT INTO bookmarks (id, book_id, block, chapter, label, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (item["id"], book_id, item["block"], item["chapter"], item["label"],
             item["created_at"]),
        )
    return item


def delete_bookmark(book_id: str, bookmark_id: str) -> None:
    with connection() as conn:
        conn.execute("DELETE FROM bookmarks WHERE id = ? AND book_id = ?",
                     (bookmark_id, book_id))


def list_highlights(book_id: str) -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM highlights WHERE book_id = ? ORDER BY block, created_at",
            (book_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def add_highlight(book_id: str, block: int, chapter: int, text: str,
                  color: str, note: str) -> dict:
    item = {"id": new_id(), "book_id": book_id, "block": int(block),
            "chapter": int(chapter), "text": text, "color": color or "amarelo",
            "note": note or "", "created_at": time.time()}
    with connection() as conn:
        conn.execute(
            "INSERT INTO highlights (id, book_id, block, chapter, text, color, note,"
            " created_at) VALUES (?,?,?,?,?,?,?,?)",
            (item["id"], book_id, item["block"], item["chapter"], item["text"],
             item["color"], item["note"], item["created_at"]),
        )
    return item


def update_highlight(book_id: str, highlight_id: str, **fields) -> None:
    allowed = {k: v for k, v in fields.items() if k in {"color", "note"}}
    if not allowed:
        return
    sets = ", ".join(f"{k} = ?" for k in allowed)
    with connection() as conn:
        conn.execute(
            f"UPDATE highlights SET {sets} WHERE id = ? AND book_id = ?",
            (*allowed.values(), highlight_id, book_id),
        )


def delete_highlight(book_id: str, highlight_id: str) -> None:
    with connection() as conn:
        conn.execute("DELETE FROM highlights WHERE id = ? AND book_id = ?",
                     (highlight_id, book_id))


# --------------------------------------------------------------------------
# conversa


def list_messages(book_id: str, limit: int = 200) -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE book_id = ? ORDER BY created_at LIMIT ?",
            (book_id, limit),
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["sources"] = json.loads(item["sources"]) if item["sources"] else []
        out.append(item)
    return out


def add_message(book_id: str, role: str, content: str, mode: str = "",
                boundary: int = 0, sources: list | None = None) -> dict:
    item = {"id": new_id(), "book_id": book_id, "role": role, "content": content,
            "mode": mode, "boundary": int(boundary), "sources": sources or [],
            "created_at": time.time()}
    with connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages (id, book_id, role, content, mode, boundary,"
            " sources, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (item["id"], book_id, role, content, mode, item["boundary"],
             json.dumps(item["sources"], ensure_ascii=False), item["created_at"]),
        )
    return item


def clear_messages(book_id: str) -> None:
    with connection() as conn:
        conn.execute("DELETE FROM chat_messages WHERE book_id = ?", (book_id,))


# --------------------------------------------------------------------------
# memória (resumos por capítulo)


def get_summary(book_id: str, chapter: int, end_block: int) -> str | None:
    with connection() as conn:
        row = conn.execute(
            "SELECT content FROM summaries WHERE book_id = ? AND chapter = ?"
            " AND end_block = ?", (book_id, chapter, end_block),
        ).fetchone()
    return row["content"] if row else None


def save_summary(book_id: str, chapter: int, end_block: int, content: str) -> None:
    with connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO summaries (book_id, chapter, end_block, content,"
            " created_at) VALUES (?,?,?,?,?)",
            (book_id, chapter, end_block, content, time.time()),
        )


def count_summaries(book_id: str) -> int:
    with connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM summaries WHERE book_id = ?", (book_id,)
        ).fetchone()
    return row["n"] if row else 0
