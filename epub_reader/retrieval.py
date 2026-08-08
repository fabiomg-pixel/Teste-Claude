"""Busca lexical (BM25) sobre os blocos do livro.

Usada em dois lugares:

* busca dentro do livro, na interface de leitura;
* seleção dos trechos enviados à LLM — sempre restrita aos blocos que ficam
  **antes** da fronteira anti-spoiler.

Implementação em Python puro para não acrescentar dependências pesadas ao
projeto; um livro típico tem alguns milhares de blocos, o que é rápido o
bastante.
"""

from __future__ import annotations

import math
import re
import threading
import unicodedata
from collections import Counter, defaultdict

TOKEN_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = {
    # português
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "dele", "dela",
    "deles", "delas", "do", "dos", "e", "ela", "elas", "ele", "eles", "em",
    "entre", "era", "essa", "esse", "esta", "este", "eu", "foi", "for", "isso",
    "isto", "ja", "la", "lhe", "mais", "mas", "me", "mesmo", "meu", "minha",
    "muito", "na", "nao", "nas", "nem", "no", "nos", "num", "numa", "o", "os",
    "ou", "para", "pela", "pelo", "por", "que", "quem", "se", "sem", "ser",
    "seu", "sua", "so", "sobre", "sao", "tem", "tinha", "um", "uma", "voce",
    # inglês
    "an", "and", "are", "as", "at", "be", "been", "but", "by", "for", "from",
    "had", "has", "have", "he", "her", "him", "his", "i", "in", "is", "it",
    "its", "of", "on", "or", "she", "that", "the", "their", "them", "there",
    "they", "this", "to", "was", "were", "what", "when", "which", "who",
    "will", "with", "you", "your",
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").lower()
    return "".join(c for c in text if not unicodedata.combining(c))


def tokenize(text: str, keep_stopwords: bool = False) -> list[str]:
    tokens = TOKEN_RE.findall(normalize(text))
    if keep_stopwords:
        return [t for t in tokens if len(t) > 1]
    return [t for t in tokens if len(t) > 1 and t not in STOPWORDS]


class Bm25Index:
    """Índice BM25 sobre a lista de blocos de um livro."""

    K1 = 1.5
    B = 0.75

    def __init__(self, blocks: list[dict]):
        self.blocks = blocks
        self.doc_len: list[int] = []
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for pos, block in enumerate(blocks):
            counts = Counter(tokenize(block["t"]))
            self.doc_len.append(sum(counts.values()) or 1)
            for term, freq in counts.items():
                self.postings[term].append((pos, freq))
        self.n_docs = max(len(blocks), 1)
        self.avg_len = sum(self.doc_len) / self.n_docs if self.doc_len else 1.0

    def search(self, query: str, limit: int = 8, max_block: int | None = None,
               min_block: int = 0) -> list[dict]:
        terms = tokenize(query)
        if not terms:
            return []
        scores: dict[int, float] = defaultdict(float)
        for term in set(terms):
            postings = self.postings.get(term)
            if not postings:
                continue
            idf = math.log(1 + (self.n_docs - len(postings) + 0.5) / (len(postings) + 0.5))
            for pos, freq in postings:
                index = self.blocks[pos]["i"]
                if index < min_block or (max_block is not None and index > max_block):
                    continue
                length = self.doc_len[pos]
                denom = freq + self.K1 * (1 - self.B + self.B * length / self.avg_len)
                scores[pos] += idf * (freq * (self.K1 + 1)) / denom
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        return [{"block": self.blocks[pos], "score": round(score, 3)} for pos, score in ranked]


_indexes: dict[str, Bm25Index] = {}
_lock = threading.Lock()


def get_index(book_id: str, blocks: list[dict]) -> Bm25Index:
    with _lock:
        index = _indexes.get(book_id)
        if index is None or len(index.blocks) != len(blocks):
            index = Bm25Index(blocks)
            _indexes[book_id] = index
            while len(_indexes) > 3:
                _indexes.pop(next(iter(_indexes)))
        return index


def drop_index(book_id: str) -> None:
    with _lock:
        _indexes.pop(book_id, None)


def literal_search(blocks: list[dict], query: str, limit: int = 60,
                   max_block: int | None = None) -> list[dict]:
    """Busca por substring (o que o leitor espera de um Ctrl+F)."""
    needle = normalize(query).strip()
    if not needle:
        return []
    results = []
    for block in blocks:
        if max_block is not None and block["i"] > max_block:
            break
        haystack = normalize(block["t"])
        pos = haystack.find(needle)
        if pos < 0:
            continue
        start = max(0, pos - 60)
        excerpt = block["t"][start:pos + len(needle) + 90]
        results.append({
            "block": block["i"],
            "chapter": block["c"],
            "excerpt": ("…" if start else "") + excerpt.strip() + "…",
        })
        if len(results) >= limit:
            break
    return results
