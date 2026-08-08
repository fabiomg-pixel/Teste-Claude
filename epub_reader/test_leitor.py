"""Testes de fumaça: parser, API de leitura e a fronteira anti-spoiler.

Rode com:  python -m unittest test_leitor  (dentro de epub_reader/)

Não é preciso chave de API: a conversa é testada com um cliente falso, que
também serve para conferir que nenhum trecho não lido chega ao modelo.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
import zipfile

TMP = tempfile.mkdtemp(prefix="leitor-teste-")
os.environ["EPUB_DATA_DIR"] = TMP
os.environ.pop("ANTHROPIC_API_KEY", None)

import app as flask_app  # noqa: E402
import assistant  # noqa: E402
import epub_parser  # noqa: E402
import store  # noqa: E402

CHAPTERS = [
    ("c1", "Capítulo 1 — A partida",
     "<h1>Capítulo 1 — A partida</h1>"
     "<p>Era uma manhã fria quando Helena deixou a casa de pedra.</p>"
     "<blockquote><p>“Não confie no relógio da torre”, dizia a carta.</p></blockquote>"
     "<p>O trem para Ostende saía às seis. <a href='c2.xhtml#nota'>nota</a>.</p>"),
    ("c2", "Capítulo 2 — Ostende",
     "<h1>Capítulo 2 — Ostende</h1>"
     "<p id='nota'>Em Ostende o mar tinha a cor do chumbo.</p>"
     "<p>Helena procurou a rua dos Tanoeiros, 14.</p>"),
    ("c3", "Capítulo 3 — O relógio",
     "<h1>Capítulo 3 — O relógio</h1>"
     "<p>Sabotaram o mecanismo da torre durante a guerra, revelou Simão.</p>"
     "<p>Helena entendeu enfim o aviso do pai e queimou o caderno.</p>"),
]


def build_epub(path: str) -> None:
    def xhtml(title, body):
        return ('<?xml version="1.0" encoding="utf-8"?>'
                '<html xmlns="http://www.w3.org/1999/xhtml" '
                'xmlns:epub="http://www.idpf.org/2007/ops">'
                f'<head><title>{title}</title><style>p{{color:red}}</style></head>'
                f'<body>{body}<script>alert(1)</script></body></html>')

    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml",
                   '<?xml version="1.0"?><container version="1.0" '
                   'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                   '<rootfile full-path="OEBPS/content.opf" '
                   'media-type="application/oebps-package+xml"/></rootfiles></container>')
        for cid, title, body in CHAPTERS:
            z.writestr(f"OEBPS/{cid}.xhtml", xhtml(title, body))
        items = "".join(f'<li><a href="{c}.xhtml">{t}</a></li>' for c, t, _ in CHAPTERS)
        z.writestr("OEBPS/nav.xhtml",
                   xhtml("Sumário", f'<nav epub:type="toc"><ol>{items}</ol></nav>'))
        manifest = "".join(f'<item id="{c}" href="{c}.xhtml" '
                           f'media-type="application/xhtml+xml"/>' for c, _, _ in CHAPTERS)
        spine = "".join(f'<itemref idref="{c}"/>' for c, _, _ in CHAPTERS)
        z.writestr("OEBPS/content.opf",
                   '<?xml version="1.0" encoding="utf-8"?>'
                   '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
                   'unique-identifier="id"><metadata '
                   'xmlns:dc="http://purl.org/dc/elements/1.1/">'
                   '<dc:title>O Relógio de Ostende</dc:title>'
                   '<dc:creator>Marta Vilela</dc:creator>'
                   '<dc:language>pt-BR</dc:language>'
                   '<dc:identifier id="id">urn:uuid:teste</dc:identifier></metadata>'
                   '<manifest><item id="nav" href="nav.xhtml" '
                   'media-type="application/xhtml+xml" properties="nav"/>'
                   f'{manifest}</manifest><spine>{spine}</spine></package>')


class FakeStream:
    """Imita o context manager de streaming do SDK da Anthropic."""

    captured: list = []

    def __init__(self, **kwargs):
        FakeStream.captured.append(kwargs)
        self.text_stream = iter(["Helena ", "está em Ostende."])

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return type("Msg", (), {"stop_reason": "end_turn"})()


class FakeMessages:
    def stream(self, **kwargs):
        return FakeStream(**kwargs)

    def create(self, **kwargs):
        FakeStream.captured.append(kwargs)
        block = type("B", (), {"type": "text", "text": "resumo falso"})()
        return type("M", (), {"content": [block], "stop_reason": "end_turn"})()


class FakeClient:
    def __init__(self):
        self.messages = FakeMessages()


class LeitorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.epub_path = os.path.join(TMP, "teste.epub")
        build_epub(cls.epub_path)
        cls.client = flask_app.app.test_client()
        with open(cls.epub_path, "rb") as fh:
            res = cls.client.post(
                "/api/books",
                data={"file": (io.BytesIO(fh.read()), "teste.epub")},
                content_type="multipart/form-data",
            )
        cls.book_id = res.get_json()["id"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TMP, ignore_errors=True)

    # -------------------------------------------------------------- parser

    def test_parser_limpa_e_indexa(self):
        parsed = epub_parser.parse_epub(self.epub_path)
        html = parsed["chapters"][0]["html"]
        self.assertNotIn("<script", html.lower())
        self.assertNotIn("<style", html.lower())
        self.assertIn('data-b="0"', html)
        self.assertEqual(parsed["meta"]["title"], "O Relógio de Ostende")
        self.assertEqual(len(parsed["chapters"]), 3)
        # o parágrafo dentro do blockquote vira um bloco; o blockquote não
        self.assertEqual([b["c"] for b in parsed["blocks"]].count(0), 4)
        # link interno reescrito para navegação no leitor
        self.assertIn('data-chapter="1"', html)
        self.assertIn('data-anchor="nota"', html)

    def test_toc(self):
        book = self.client.get(f"/api/books/{self.book_id}").get_json()
        self.assertEqual(len(book["toc"]), 3)
        self.assertEqual(book["toc"][1]["chapter"], 1)

    # ------------------------------------------------------------- leitura

    def test_progresso_e_anotacoes(self):
        res = self.client.post(f"/api/books/{self.book_id}/progress",
                               json={"block": 5, "seconds": 60, "words": 30})
        self.assertEqual(res.get_json()["progress"]["furthest_block"], 5)
        # voltar não reduz a fronteira
        res = self.client.post(f"/api/books/{self.book_id}/progress", json={"block": 2})
        self.assertEqual(res.get_json()["progress"]["furthest_block"], 5)

        hl = self.client.post(f"/api/books/{self.book_id}/highlights",
                              json={"block": 4, "chapter": 1, "text": "cor do chumbo",
                                    "color": "azul"}).get_json()
        self.client.patch(f"/api/books/{self.book_id}/highlights/{hl['id']}",
                          json={"note": "boa imagem"})
        book = self.client.get(f"/api/books/{self.book_id}").get_json()
        self.assertEqual(book["highlights"][0]["note"], "boa imagem")

        self.client.post(f"/api/books/{self.book_id}/bookmarks",
                         json={"block": 4, "chapter": 1, "label": "aqui"})
        book = self.client.get(f"/api/books/{self.book_id}").get_json()
        self.assertEqual(len(book["bookmarks"]), 1)

    def test_busca_respeita_o_lido(self):
        self.client.post(f"/api/books/{self.book_id}/progress", json={"block": 5})
        lido = self.client.get(
            f"/api/books/{self.book_id}/search?q=Simão&scope=read").get_json()
        self.assertEqual(lido["results"], [])
        tudo = self.client.get(
            f"/api/books/{self.book_id}/search?q=Simão&scope=all").get_json()
        self.assertTrue(tudo["results"])

    def test_asset_nao_escapa_do_epub(self):
        res = self.client.get(f"/api/books/{self.book_id}/asset?p=../../../etc/passwd")
        self.assertEqual(res.status_code, 404)

    # ------------------------------------------------- fronteira anti-spoiler

    def test_contexto_nao_passa_da_fronteira(self):
        self.client.post(f"/api/books/{self.book_id}/progress", json={"block": 5})
        book = store.get_book(self.book_id)
        content = store.load_content(book)
        for chapter, end in assistant._chapters_up_to(content, 5):
            store.save_summary(self.book_id, chapter["index"], end, "resumo de teste")
        context, _ = assistant.build_context(book, content, 5, "quem sabotou o relógio")
        for block in content["blocks"]:
            if block["i"] > 5:
                self.assertNotIn(block["t"][:30], context, f"vazou o bloco {block['i']}")
        self.assertIn("Ostende", context)

    def test_fronteira_e_limitada_pelo_servidor(self):
        self.client.post(f"/api/books/{self.book_id}/progress", json={"block": 5})
        book = store.get_book(self.book_id)
        self.assertEqual(flask_app._boundary(book, 9999), 5)
        self.assertEqual(flask_app._boundary(book, 3), 3)

    def test_conversa_com_cliente_falso(self):
        assistant._client = FakeClient()
        FakeStream.captured.clear()
        self.client.post(f"/api/books/{self.book_id}/progress", json={"block": 5})
        res = self.client.post(f"/api/books/{self.book_id}/chat",
                               json={"question": "Onde Helena está?", "boundary": 9999})
        body = res.get_data(as_text=True)
        self.assertIn("Helena ", body)
        self.assertIn('"type": "done"', body)

        # o pedido enviado ao modelo não pode conter texto não lido
        pedido = json.dumps(FakeStream.captured[-1], ensure_ascii=False, default=str)
        content = store.load_content(store.get_book(self.book_id))
        for block in content["blocks"]:
            if block["i"] > 5:
                self.assertNotIn(block["t"][:30], pedido)

        # a resposta fica no histórico
        historico = self.client.get(f"/api/books/{self.book_id}/chat").get_json()
        self.assertEqual(historico["messages"][-1]["role"], "assistant")
        self.assertIn("Ostende", historico["messages"][-1]["content"])
        assistant._client = None

    def test_conversa_sem_chave_avisa(self):
        assistant._client = None
        res = self.client.post(f"/api/books/{self.book_id}/chat",
                               json={"question": "e agora?"})
        self.assertIn("ANTHROPIC_API_KEY", res.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
