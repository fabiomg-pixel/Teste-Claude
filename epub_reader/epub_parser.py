"""Leitura e normalização de arquivos EPUB (2 e 3).

O parser converte um EPUB em uma estrutura canônica usada por todo o
aplicativo:

* ``chapters``  – um item por documento do *spine*, com HTML já sanitizado
* ``blocks``    – lista linear de blocos de texto (parágrafos, títulos,
                  itens de lista...) numerados globalmente de 0 a N-1
* ``toc``       – sumário hierárquico apontando para capítulo + âncora

O índice global de blocos é a espinha dorsal do leitor: ele identifica a
posição de leitura, os destaques, os marcadores e — o mais importante — a
fronteira anti-spoiler usada na conversa com a LLM.
"""

from __future__ import annotations

import codecs
import posixpath
import re
import warnings
import zipfile
from urllib.parse import unquote, urldefrag
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup, Tag
from bs4 import XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

CONTAINER_PATH = "META-INF/container.xml"

# Tags removidas com todo o conteúdo.
DROP_TAGS = {
    "script", "style", "link", "meta", "iframe", "object", "embed", "video",
    "audio", "form", "input", "button", "select", "textarea", "noscript",
    "base", "head", "title", "nav",
}

# Tags preservadas na renderização; qualquer outra é "desembrulhada".
ALLOWED_TAGS = {
    "a", "abbr", "article", "aside", "b", "blockquote", "br", "caption",
    "cite", "code", "dd", "del", "div", "dl", "dt", "em", "figcaption",
    "figure", "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr",
    "i", "img", "ins", "kbd", "li", "main", "mark", "ol", "p", "pre", "q",
    "rp", "rt", "ruby", "s", "samp", "section", "small", "span", "strong",
    "sub", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "time",
    "tr", "u", "ul", "var",
}

ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}
GLOBAL_ATTRS = {"id"}

# Candidatos a "bloco". Só os que não contêm outro candidato recebem índice,
# de modo que um <blockquote><p>… gera um bloco (o <p>), não dois.
BLOCK_TAGS = {
    "p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "pre",
    "figcaption", "dd", "dt", "td", "th", "caption", "div", "section",
    "article", "header", "footer", "aside",
}

TEXT_MEDIA = ("application/xhtml+xml", "text/html")

# O leitor do navegador numera os blocos a partir da árvore que o próprio
# navegador monta. Para o servidor chegar exatamente à mesma numeração — o que
# a sincronização entre aparelhos exige — é preciso o mesmo algoritmo de
# análise: o html5lib implementa o do HTML5. Sem ele, um <p> sem fechar (comum
# em EPUBs) desloca todos os blocos seguintes.
try:
    import html5lib  # noqa: F401
    _ANALISADOR = "html5lib"
except ImportError:  # pragma: no cover
    import warnings
    warnings.warn(
        "html5lib não instalado: a numeração de blocos pode divergir da do "
        "leitor no navegador, o que quebra a sincronização entre aparelhos. "
        "Instale com: pip install html5lib",
        RuntimeWarning,
    )
    _ANALISADOR = "html.parser"


class EpubError(Exception):
    """Erro de leitura/estrutura do arquivo EPUB."""


# --------------------------------------------------------------------------
# utilidades


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _strip_ns(elem: ET.Element) -> ET.Element:
    """Remove namespaces XML da árvore inteira (facilita as buscas)."""
    for node in elem.iter():
        if isinstance(node.tag, str) and "}" in node.tag:
            node.tag = node.tag.split("}", 1)[1]
        for key in list(node.attrib):
            if "}" in key:
                node.attrib[key.split("}", 1)[1]] = node.attrib.pop(key)
    return elem


def _resolve(base_dir: str, href: str) -> str:
    """Resolve um href relativo dentro do zip do EPUB."""
    href = unquote(href or "").replace("\\", "/")
    if base_dir:
        href = posixpath.join(base_dir, href)
    return posixpath.normpath(href).lstrip("/")


def _is_external(href: str) -> bool:
    return bool(re.match(r"^(https?:|mailto:|tel:|data:|ftp:)", href or "", re.I))


def _decodificar(dados: bytes) -> str:
    """Bytes de um documento do EPUB para texto.

    O html5lib não lê a declaração XML (<?xml encoding=...?>) ao adivinhar a
    codificação, e erra para latin-1 em arquivos UTF-8 sem <meta charset>. Como
    praticamente todo EPUB é UTF-8, a decisão é tomada aqui.
    """
    if dados.startswith(codecs.BOM_UTF8):
        return dados[len(codecs.BOM_UTF8):].decode("utf-8", "replace")
    if dados.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return dados.decode("utf-16", "replace")
    cabeca = dados[:1024].lower()
    declarada = re.search(rb'(?:encoding|charset)\s*=\s*["\']?([\w-]+)', cabeca)
    for tentativa in ([declarada.group(1).decode("ascii", "ignore")] if declarada else []) + ["utf-8"]:
        try:
            return dados.decode(tentativa)
        except (LookupError, UnicodeDecodeError):
            continue
    return dados.decode("latin-1", "replace")


class _Zip:
    """Acesso tolerante a maiúsculas/minúsculas ao conteúdo do EPUB."""

    def __init__(self, zf: zipfile.ZipFile):
        self.zf = zf
        self.index = {name.lower(): name for name in zf.namelist()}

    def resolve(self, path: str) -> str | None:
        return self.index.get((path or "").lower())

    def read(self, path: str) -> bytes:
        real = self.resolve(path)
        if real is None:
            raise EpubError(f"Arquivo ausente no EPUB: {path}")
        return self.zf.read(real)

    def exists(self, path: str) -> bool:
        return self.resolve(path) is not None


# --------------------------------------------------------------------------
# metadados / manifesto


def _read_package(z: _Zip) -> tuple[ET.Element, str]:
    container = _strip_ns(ET.fromstring(z.read(CONTAINER_PATH)))
    rootfile = container.find(".//rootfile")
    if rootfile is None or not rootfile.get("full-path"):
        raise EpubError("container.xml sem rootfile válido")
    opf_path = _resolve("", rootfile.get("full-path"))
    package = _strip_ns(ET.fromstring(z.read(opf_path)))
    return package, posixpath.dirname(opf_path)


def _read_metadata(package: ET.Element) -> dict:
    md = package.find("metadata")
    out = {
        "title": "", "creator": "", "language": "", "publisher": "",
        "description": "", "identifier": "", "date": "",
    }
    if md is None:
        return out
    for key in list(out):
        node = md.find(key)
        if node is not None and node.text:
            out[key] = _norm_ws(node.text)
    # vários autores
    creators = [_norm_ws(n.text) for n in md.findall("creator") if n.text]
    if creators:
        out["creator"] = ", ".join(dict.fromkeys(creators))
    return out


def _read_manifest(package: ET.Element, opf_dir: str) -> dict:
    manifest = {}
    node = package.find("manifest")
    if node is None:
        raise EpubError("OPF sem manifest")
    for item in node.findall("item"):
        item_id = item.get("id")
        href = item.get("href")
        if not item_id or not href:
            continue
        manifest[item_id] = {
            "id": item_id,
            "path": _resolve(opf_dir, href),
            "media_type": (item.get("media-type") or "").lower(),
            "properties": (item.get("properties") or "").split(),
        }
    return manifest


def _read_spine(package: ET.Element, manifest: dict) -> tuple[list[dict], str | None]:
    spine_node = package.find("spine")
    if spine_node is None:
        raise EpubError("OPF sem spine")
    docs = []
    # Itens marcados linear="no" (notas, apêndices) entram do mesmo jeito: em
    # muitos livros são capítulos legítimos marcados por engano, e deixá-los
    # de fora abriria buracos na numeração de blocos.
    for ref in spine_node.findall("itemref"):
        item = manifest.get(ref.get("idref") or "")
        if not item:
            continue
        if item["media_type"] in TEXT_MEDIA or item["path"].endswith((".xhtml", ".html", ".htm")):
            docs.append(item)
    if not docs:
        raise EpubError("Nenhum documento de texto encontrado no spine")
    return docs, spine_node.get("toc")


def _find_cover(package: ET.Element, manifest: dict) -> str | None:
    for item in manifest.values():
        if "cover-image" in item["properties"]:
            return item["path"]
    md = package.find("metadata")
    if md is not None:
        for meta in md.findall("meta"):
            if (meta.get("name") or "").lower() == "cover":
                item = manifest.get(meta.get("content") or "")
                if item:
                    return item["path"]
    for item in manifest.values():
        if item["media_type"].startswith("image/") and "cover" in item["path"].lower():
            return item["path"]
    return None


# --------------------------------------------------------------------------
# sumário


def _toc_from_nav(z: _Zip, nav_path: str, spine_map: dict) -> list[dict]:
    soup = BeautifulSoup(_decodificar(z.read(nav_path)), _ANALISADOR)
    nav = None
    for candidate in soup.find_all("nav"):
        if (candidate.get("epub:type") or candidate.get("type") or "") == "toc":
            nav = candidate
            break
    nav = nav or soup.find("nav")
    if nav is None:
        return []
    base = posixpath.dirname(nav_path)

    def walk(ol: Tag) -> list[dict]:
        entries = []
        for li in ol.find_all("li", recursive=False):
            anchor = li.find(["a", "span"], recursive=False)
            if anchor is None:
                anchor = li.find(["a", "span"])
            title = _norm_ws(anchor.get_text()) if anchor else ""
            href = anchor.get("href") if anchor and anchor.name == "a" else None
            entry = _toc_entry(title, href, base, spine_map)
            child_ol = li.find("ol", recursive=False)
            if child_ol is not None:
                entry["children"] = walk(child_ol)
            entries.append(entry)
        return entries

    root_ol = nav.find("ol")
    return walk(root_ol) if root_ol else []


def _toc_from_ncx(z: _Zip, ncx_path: str, spine_map: dict) -> list[dict]:
    root = _strip_ns(ET.fromstring(z.read(ncx_path)))
    base = posixpath.dirname(ncx_path)

    def walk(parent: ET.Element) -> list[dict]:
        entries = []
        for point in parent.findall("navPoint"):
            label = point.find("navLabel/text")
            content = point.find("content")
            entry = _toc_entry(
                _norm_ws(label.text if label is not None else ""),
                content.get("src") if content is not None else None,
                base, spine_map,
            )
            children = walk(point)
            if children:
                entry["children"] = children
            entries.append(entry)
        return entries

    nav_map = root.find("navMap")
    return walk(nav_map) if nav_map is not None else []


def _toc_entry(title: str, href: str | None, base: str, spine_map: dict) -> dict:
    entry = {"title": title or "(sem título)", "chapter": None, "anchor": None}
    if href and not _is_external(href):
        path, frag = urldefrag(href)
        target = _resolve(base, path) if path else None
        if target is not None and target in spine_map:
            entry["chapter"] = spine_map[target]
        entry["anchor"] = frag or None
    return entry


# --------------------------------------------------------------------------
# conteúdo dos capítulos


def _sanitize(node: Tag) -> None:
    for tag in node.find_all(True):
        if getattr(tag, "decomposed", False) or tag.parent is None:
            continue  # já removido junto com um ancestral
        name = tag.name.lower()
        if name in DROP_TAGS:
            tag.decompose()
            continue
        if name in {"svg", "image"}:
            # capas costumam vir como <svg><image xlink:href="..."/></svg>
            src = tag.get("xlink:href") or tag.get("href") or tag.get("src")
            if name == "image" and src:
                tag.name = "img"
                tag.attrs = {"src": src, "alt": tag.get("alt", "")}
                continue
            if name == "svg":
                tag.unwrap()
                continue
        if name not in ALLOWED_TAGS:
            tag.unwrap()
            continue
        allowed = ALLOWED_ATTRS.get(name, set()) | GLOBAL_ATTRS
        tag.attrs = {k: v for k, v in tag.attrs.items() if k in allowed}


def _rewrite_links(node: Tag, doc_dir: str, spine_map: dict, asset_url: str) -> None:
    for img in node.find_all("img"):
        src = img.get("src")
        if not src or _is_external(src):
            img.decompose()
            continue
        img["src"] = asset_url + _resolve(doc_dir, src)
        img["loading"] = "lazy"
    for a in node.find_all("a"):
        href = a.get("href")
        if not href:
            a.unwrap()
            continue
        if _is_external(href):
            a["target"] = "_blank"
            a["rel"] = "noopener noreferrer"
            continue
        path, frag = urldefrag(href)
        target = _resolve(doc_dir, path) if path else None
        chapter = spine_map.get(target) if target else None
        if chapter is None and not frag:
            a.unwrap()
            continue
        a["href"] = "#"
        a["class"] = "epub-link"
        if chapter is not None:
            a["data-chapter"] = str(chapter)
        if frag:
            a["data-anchor"] = frag


def _index_blocks(node: Tag, chapter_index: int, start: int) -> list[dict]:
    blocks: list[dict] = []
    counter = start
    for tag in node.find_all(BLOCK_TAGS):
        if tag.find(BLOCK_TAGS):  # não é folha: os filhos serão indexados
            continue
        text = _norm_ws(tag.get_text(""))
        if not text:
            continue
        tag["data-b"] = str(counter)
        blocks.append({
            "i": counter,
            "c": chapter_index,
            "t": text,
            "w": len(text.split()),
        })
        counter += 1
    return blocks


def _chapter_title(node: Tag, fallback: str) -> str:
    for level in ("h1", "h2", "h3", "h4"):
        heading = node.find(level)
        if heading:
            title = _norm_ws(heading.get_text(""))
            if title:
                return title[:120]
    return fallback


def parse_epub(path: str, asset_url: str = "asset?p=") -> dict:
    """Lê um EPUB e devolve a estrutura canônica do livro."""
    with zipfile.ZipFile(path) as zf:
        z = _Zip(zf)
        package, opf_dir = _read_package(z)
        metadata = _read_metadata(package)
        manifest = _read_manifest(package, opf_dir)
        spine, ncx_id = _read_spine(package, manifest)
        spine_map = {item["path"]: idx for idx, item in enumerate(spine)}

        # sumário: primeiro EPUB 3 (nav), depois EPUB 2 (NCX)
        toc: list[dict] = []
        nav_item = next((i for i in manifest.values() if "nav" in i["properties"]), None)
        if nav_item and z.exists(nav_item["path"]):
            try:
                toc = _toc_from_nav(z, nav_item["path"], spine_map)
            except Exception:
                toc = []
        if not toc:
            ncx = manifest.get(ncx_id or "") or next(
                (i for i in manifest.values() if i["media_type"] == "application/x-dtbncx+xml"),
                None,
            )
            if ncx and z.exists(ncx["path"]):
                try:
                    toc = _toc_from_ncx(z, ncx["path"], spine_map)
                except Exception:
                    toc = []

        toc_titles: dict[int, str] = {}
        def collect(entries):
            for e in entries:
                if e["chapter"] is not None and e["chapter"] not in toc_titles:
                    toc_titles[e["chapter"]] = e["title"]
                collect(e.get("children", []))
        collect(toc)

        chapters = []
        blocks: list[dict] = []
        cursor = 0
        for idx, item in enumerate(spine):
            try:
                raw = z.read(item["path"])
            except EpubError:
                continue
            soup = BeautifulSoup(_decodificar(raw), _ANALISADOR)
            body = soup.body or soup
            _sanitize(body)
            _rewrite_links(body, posixpath.dirname(item["path"]), spine_map, asset_url)
            chapter_blocks = _index_blocks(body, idx, cursor)
            if not chapter_blocks and not body.find("img"):
                # documento vazio (páginas de separação) — mantém para não
                # quebrar os índices do spine, mas sem custo de texto.
                pass
            blocks.extend(chapter_blocks)
            html = "".join(str(child) for child in body.children)
            words = sum(b["w"] for b in chapter_blocks)
            chapters.append({
                "index": idx,
                "title": toc_titles.get(idx) or _chapter_title(body, f"Parte {idx + 1}"),
                "path": item["path"],
                "html": html,
                "first_block": chapter_blocks[0]["i"] if chapter_blocks else cursor,
                "last_block": chapter_blocks[-1]["i"] if chapter_blocks else cursor - 1,
                "words": words,
            })
            cursor += len(chapter_blocks)

        cover_path = _find_cover(package, manifest)
        cover_bytes = None
        if cover_path and z.exists(cover_path):
            cover_bytes = z.read(cover_path)

    return {
        "meta": metadata,
        "chapters": chapters,
        "blocks": blocks,
        "toc": toc,
        "total_blocks": len(blocks),
        "total_words": sum(b["w"] for b in blocks),
        "cover_path": cover_path,
        "cover_bytes": cover_bytes,
    }


def read_asset(epub_path: str, internal_path: str) -> tuple[bytes, str]:
    """Lê uma imagem/recurso de dentro do EPUB (para servir ao navegador)."""
    safe = posixpath.normpath(unquote(internal_path or "")).lstrip("/")
    if safe.startswith("..") or not safe:
        raise EpubError("Caminho inválido")
    with zipfile.ZipFile(epub_path) as zf:
        z = _Zip(zf)
        data = z.read(safe)
    ext = posixpath.splitext(safe)[1].lower()
    mime = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".svg": "image/svg+xml", ".webp": "image/webp",
        ".ttf": "font/ttf", ".otf": "font/otf", ".woff": "font/woff",
        ".woff2": "font/woff2",
    }.get(ext, "application/octet-stream")
    return data, mime
