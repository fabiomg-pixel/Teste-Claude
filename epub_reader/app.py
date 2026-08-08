"""Leitor de EPUB com companheiro de leitura (Claude) sem spoilers.

Servidor Flask: biblioteca, leitura paginada, destaques/notas/marcadores e a
conversa com a LLM restrita ao que já foi lido.
"""

from __future__ import annotations

import json
import os

from flask import (Flask, Response, abort, jsonify, render_template, request,
                   send_file, stream_with_context)
from werkzeug.utils import secure_filename

import assistant
import epub_parser
import retrieval
import store

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 80 * 1024 * 1024  # 80 MB
app.config["JSON_SORT_KEYS"] = False


# --------------------------------------------------------------------------
# helpers


def _book_or_404(book_id: str):
    book = store.get_book(book_id)
    if book is None:
        abort(404, description="Livro não encontrado")
    return book


def _boundary(book, requested=None) -> int:
    """Fronteira anti-spoiler efetiva.

    Nunca ultrapassa o ponto mais avançado que o leitor já alcançou — mesmo
    que o cliente peça um valor maior.
    """
    progress = store.get_progress(book["id"])
    ceiling = max(progress["furthest_block"], progress["cur_block"])
    ceiling = min(ceiling, max(book["total_blocks"] - 1, 0))
    if requested is None:
        return ceiling
    try:
        return max(0, min(int(requested), ceiling))
    except (TypeError, ValueError):
        return ceiling


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _sse_response(generator):
    return Response(
        stream_with_context(generator),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "Connection": "keep-alive"},
    )


@app.errorhandler(404)
def _not_found(err):
    if request.path.startswith("/api/"):
        return jsonify({"error": getattr(err, "description", "não encontrado")}), 404
    return render_template("error.html", code=404,
                           message="Página não encontrada"), 404


@app.errorhandler(413)
def _too_large(err):
    return jsonify({"error": "Arquivo maior que o limite de 80 MB"}), 413


# --------------------------------------------------------------------------
# páginas


@app.route("/")
def index():
    return render_template("library.html")


@app.route("/livro/<book_id>")
def reader(book_id: str):
    book = _book_or_404(book_id)
    return render_template("reader.html", book_id=book_id, book_title=book["title"],
                           book_author=book["author"])


# --------------------------------------------------------------------------
# biblioteca


@app.route("/api/books", methods=["GET"])
def api_list_books():
    return jsonify({"books": store.list_books(), "llm": assistant.available()})


@app.route("/api/books", methods=["POST"])
def api_upload_book():
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400
    if not file.filename.lower().endswith(".epub"):
        return jsonify({"error": "Envie um arquivo .epub"}), 400

    store.init()
    book_id = store.new_id()
    filename = secure_filename(file.filename) or "livro.epub"
    epub_path = os.path.join(store.BOOKS_DIR, f"{book_id}.epub")
    file.save(epub_path)

    try:
        content = epub_parser.parse_epub(epub_path, asset_url=f"/api/books/{book_id}/asset?p=")
    except Exception as exc:
        os.remove(epub_path)
        return jsonify({"error": f"Não consegui ler este EPUB: {exc}"}), 400

    if content["total_blocks"] == 0:
        os.remove(epub_path)
        return jsonify({"error": "O EPUB não tem texto legível"}), 400

    cover_path = None
    if content.get("cover_bytes"):
        ext = os.path.splitext(content["cover_path"] or "")[1].lower() or ".jpg"
        cover_path = os.path.join(store.BOOKS_DIR, f"{book_id}-cover{ext}")
        with open(cover_path, "wb") as fh:
            fh.write(content["cover_bytes"])

    meta = dict(content["meta"])
    if not meta.get("title"):
        meta["title"] = os.path.splitext(filename)[0]

    payload = {k: content[k] for k in ("meta", "chapters", "blocks", "toc",
                                       "total_blocks", "total_words")}
    data_path = store.save_content(book_id, payload)
    store.create_book(
        meta, epub_path, data_path, cover_path,
        {"id": book_id, "blocks": content["total_blocks"],
         "words": content["total_words"], "chapters": len(content["chapters"])},
    )
    return jsonify({"id": book_id, "title": meta["title"], "author": meta.get("creator", "")}), 201


@app.route("/api/books/<book_id>", methods=["DELETE"])
def api_delete_book(book_id: str):
    _book_or_404(book_id)
    retrieval.drop_index(book_id)
    store.delete_book(book_id)
    return jsonify({"ok": True})


@app.route("/api/books/<book_id>/cover")
def api_cover(book_id: str):
    book = _book_or_404(book_id)
    if not book["cover_path"] or not os.path.exists(book["cover_path"]):
        abort(404)
    return send_file(book["cover_path"], max_age=86400)


# --------------------------------------------------------------------------
# leitura


@app.route("/api/books/<book_id>")
def api_book(book_id: str):
    book = _book_or_404(book_id)
    content = store.load_content(book)
    progress = store.get_progress(book_id)
    chapters = [{k: ch[k] for k in ("index", "title", "first_block", "last_block", "words")}
                for ch in content["chapters"]]
    return jsonify({
        "id": book_id,
        "title": book["title"],
        "author": book["author"],
        "language": book["language"],
        "total_blocks": book["total_blocks"],
        "total_words": book["total_words"],
        "chapters": chapters,
        "toc": content["toc"],
        "progress": progress,
        "bookmarks": store.list_bookmarks(book_id),
        "highlights": store.list_highlights(book_id),
        "llm": assistant.available(),
    })


@app.route("/api/books/<book_id>/chapters/<int:index>")
def api_chapter(book_id: str, index: int):
    book = _book_or_404(book_id)
    content = store.load_content(book)
    if index < 0 or index >= len(content["chapters"]):
        abort(404, description="Capítulo inexistente")
    chapter = content["chapters"][index]
    return jsonify({
        "index": index,
        "title": chapter["title"],
        "html": chapter["html"],
        "first_block": chapter["first_block"],
        "last_block": chapter["last_block"],
        "words": chapter["words"],
    })


@app.route("/api/books/<book_id>/asset")
def api_asset(book_id: str):
    book = _book_or_404(book_id)
    path = request.args.get("p", "")
    try:
        data, mime = epub_parser.read_asset(book["epub_path"], path)
    except Exception:
        abort(404)
    return Response(data, mimetype=mime, headers={"Cache-Control": "max-age=86400"})


@app.route("/api/books/<book_id>/progress", methods=["POST"])
def api_progress(book_id: str):
    book = _book_or_404(book_id)
    body = request.get_json(silent=True) or {}
    block = max(0, min(int(body.get("block", 0)), max(book["total_blocks"] - 1, 0)))
    progress = store.update_progress(
        book_id, block,
        seconds=int(body.get("seconds", 0) or 0),
        words=int(body.get("words", 0) or 0),
    )
    return jsonify({"progress": progress})


@app.route("/api/books/<book_id>/boundary", methods=["POST"])
def api_boundary(book_id: str):
    book = _book_or_404(book_id)
    body = request.get_json(silent=True) or {}
    block = max(0, min(int(body.get("block", 0)), max(book["total_blocks"] - 1, 0)))
    return jsonify({"progress": store.set_boundary(book_id, block)})


@app.route("/api/books/<book_id>/search")
def api_search(book_id: str):
    book = _book_or_404(book_id)
    content = store.load_content(book)
    query = request.args.get("q", "")
    scope = request.args.get("scope", "read")
    max_block = None if scope == "all" else _boundary(book)
    results = retrieval.literal_search(content["blocks"], query, max_block=max_block)
    if not results:
        index = retrieval.get_index(book_id, content["blocks"])
        titles = {c["index"]: c["title"] for c in content["chapters"]}
        results = [{
            "block": hit["block"]["i"],
            "chapter": hit["block"]["c"],
            "excerpt": hit["block"]["t"][:200] + "…",
            "chapter_title": titles.get(hit["block"]["c"], ""),
        } for hit in index.search(query, limit=30, max_block=max_block)]
    titles = {c["index"]: c["title"] for c in content["chapters"]}
    for item in results:
        item.setdefault("chapter_title", titles.get(item["chapter"], ""))
    return jsonify({"results": results, "scope": scope})


# --------------------------------------------------------------------------
# marcadores, destaques e notas


@app.route("/api/books/<book_id>/bookmarks", methods=["POST"])
def api_add_bookmark(book_id: str):
    _book_or_404(book_id)
    body = request.get_json(silent=True) or {}
    item = store.add_bookmark(book_id, body.get("block", 0), body.get("chapter", 0),
                              body.get("label", ""))
    return jsonify(item), 201


@app.route("/api/books/<book_id>/bookmarks/<bookmark_id>", methods=["DELETE"])
def api_delete_bookmark(book_id: str, bookmark_id: str):
    _book_or_404(book_id)
    store.delete_bookmark(book_id, bookmark_id)
    return jsonify({"ok": True})


@app.route("/api/books/<book_id>/highlights", methods=["POST"])
def api_add_highlight(book_id: str):
    _book_or_404(book_id)
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Nada selecionado"}), 400
    item = store.add_highlight(book_id, body.get("block", 0), body.get("chapter", 0),
                               text, body.get("color", "amarelo"), body.get("note", ""))
    return jsonify(item), 201


@app.route("/api/books/<book_id>/highlights/<highlight_id>", methods=["PATCH", "DELETE"])
def api_highlight(book_id: str, highlight_id: str):
    _book_or_404(book_id)
    if request.method == "DELETE":
        store.delete_highlight(book_id, highlight_id)
        return jsonify({"ok": True})
    body = request.get_json(silent=True) or {}
    store.update_highlight(book_id, highlight_id, **body)
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# companheiro de leitura


@app.route("/api/books/<book_id>/memory", methods=["GET"])
def api_memory_status(book_id: str):
    book = _book_or_404(book_id)
    content = store.load_content(book)
    boundary = _boundary(book)
    status = assistant.memory_status(book_id, content, boundary)
    status["llm"] = assistant.available()
    status["position"] = assistant.position_label(content, boundary)
    return jsonify(status)


@app.route("/api/books/<book_id>/memory", methods=["POST"])
def api_memory_build(book_id: str):
    book = _book_or_404(book_id)
    content = store.load_content(book)
    boundary = _boundary(book, (request.get_json(silent=True) or {}).get("boundary"))

    def generate():
        try:
            pending = assistant.pending_summaries(book_id, content, boundary)
        except assistant.AssistantError as exc:
            yield _sse({"type": "error", "message": str(exc)})
            return
        yield _sse({"type": "status", "message": f"{len(pending)} capítulo(s) a preparar",
                    "total": len(pending)})
        for n, (chapter, end) in enumerate(pending, 1):
            yield _sse({"type": "status", "message": chapter["title"], "done": n,
                        "total": len(pending)})
            try:
                assistant.summarize_chapter(book_id, content, chapter, end)
            except Exception as exc:
                yield _sse({"type": "error", "message": str(exc)})
                return
        yield _sse({"type": "done", "ready": len(pending)})

    return _sse_response(generate())


@app.route("/api/books/<book_id>/chat", methods=["GET"])
def api_chat_history(book_id: str):
    _book_or_404(book_id)
    return jsonify({"messages": store.list_messages(book_id), "modes": list(assistant.MODES)})


@app.route("/api/books/<book_id>/chat", methods=["DELETE"])
def api_chat_clear(book_id: str):
    _book_or_404(book_id)
    store.clear_messages(book_id)
    return jsonify({"ok": True})


@app.route("/api/books/<book_id>/chat", methods=["POST"])
def api_chat(book_id: str):
    book = _book_or_404(book_id)
    content = store.load_content(book)
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    selection = (body.get("selection") or "").strip()
    mode = body.get("mode") if body.get("mode") in assistant.MODES else "perguntar"
    strict = bool(body.get("strict"))
    boundary = _boundary(book, body.get("boundary"))

    if not question and mode == "perguntar" and not selection:
        return jsonify({"error": "Escreva uma pergunta"}), 400
    if book["total_blocks"] and boundary <= 0 and mode != "perguntar":
        return jsonify({"error": "Comece a leitura para eu ter sobre o que conversar."}), 400

    history = store.list_messages(book_id)
    user_text = question or (f"[{mode}] {selection}" if selection else f"[{mode}]")

    def generate():
        answer_parts: list[str] = []
        sources: list[dict] = []
        failed = False
        yield _sse({"type": "position",
                    "position": assistant.position_label(content, boundary)})
        for event in assistant.stream_answer(book, content, boundary, question, mode,
                                             history, selection=selection, strict=strict):
            if event["type"] == "delta":
                answer_parts.append(event["text"])
            elif event["type"] == "sources":
                sources = event["sources"]
            elif event["type"] == "error":
                failed = True
            yield _sse(event)
        # a pergunta só entra no histórico junto com a resposta: assim uma
        # falha não deixa perguntas órfãs na conversa
        text = "".join(answer_parts).strip()
        if text and not failed:
            store.add_message(book_id, "user", user_text, mode=mode, boundary=boundary)
            store.add_message(book_id, "assistant", text, mode=mode, boundary=boundary,
                              sources=sources)

    return _sse_response(generate())


if __name__ == "__main__":
    store.init()
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=bool(os.environ.get("EPUB_DEBUG")),
            threaded=True)
