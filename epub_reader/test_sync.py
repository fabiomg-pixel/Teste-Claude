"""Testes da mescla de sincronização e dos endpoints.

Rode com:  python -m unittest test_sync  (dentro de epub_reader/)
"""

from __future__ import annotations

import atexit
import io
import os
import time
import shutil
import tempfile
import unittest

AGORA = time.time()
_CRIOU = "EPUB_DATA_DIR" not in os.environ
TMP = os.environ.setdefault("EPUB_DATA_DIR", tempfile.mkdtemp(prefix="leitor-sync-"))
if _CRIOU:
    atexit.register(shutil.rmtree, TMP, True)
os.environ["EPUB_SYNC_TOKEN"] = "token-de-teste"
os.environ.pop("ANTHROPIC_API_KEY", None)

import app as flask_app  # noqa: E402
import pagina  # noqa: E402
import sync  # noqa: E402
from test_leitor import build_epub  # noqa: E402


def marca(id_, bloco, texto, em, apagado=None):
    item = {"id": id_, "bloco": bloco, "capitulo": 0, "texto": texto,
            "cor": "manteiga", "em": AGORA + em}
    if apagado:
        item["apagadoEm"] = AGORA + apagado
    return item


class MesclaTests(unittest.TestCase):

    def test_fronteira_so_cresce(self):
        a = {"fronteira": 120, "posicao": {"bloco": 120, "em": 10}}
        b = {"fronteira": 40, "posicao": {"bloco": 40, "em": 99}}
        # o aparelho atrasado não pode puxar a fronteira para trás
        self.assertEqual(sync.mesclar(a, b)["fronteira"], 120)
        self.assertEqual(sync.mesclar(b, a)["fronteira"], 120)

    def test_posicao_mais_recente_vence(self):
        antigo = {"fronteira": 10, "posicao": {"bloco": 5, "em": 100}}
        novo = {"fronteira": 10, "posicao": {"bloco": 8, "em": 200}}
        self.assertEqual(sync.mesclar(antigo, novo)["posicao"]["bloco"], 8)
        self.assertEqual(sync.mesclar(novo, antigo)["posicao"]["bloco"], 8)

    def test_marcas_de_aparelhos_diferentes_se_somam(self):
        celular = {"marcas": [marca("a", 3, "trecho do celular", 100)]}
        mac = {"marcas": [marca("b", 9, "trecho do mac", 110)]}
        ids = {m["id"] for m in sync.mesclar(celular, mac)["marcas"]}
        self.assertEqual(ids, {"a", "b"})

    def test_apagar_num_aparelho_nao_ressuscita(self):
        tinha = {"marcas": [marca("a", 3, "destaque", 100)]}
        apagou = {"marcas": [marca("a", 3, "destaque", 100, apagado=200)]}
        mesclado = sync.mesclar(tinha, apagou)
        self.assertEqual(len(mesclado["marcas"]), 1)
        self.assertTrue(mesclado["marcas"][0].get("apagadoEm"))
        # e a lápide sobrevive a uma segunda rodada, em qualquer ordem
        de_novo = sync.mesclar(mesclado, tinha)
        self.assertTrue(de_novo["marcas"][0].get("apagadoEm"))

    def test_edicao_posterior_vence_a_lapide(self):
        apagou = {"marcas": [marca("a", 3, "destaque", 100, apagado=200)]}
        reescreveu = {"marcas": [marca("a", 3, "destaque com nota", 300)]}
        mesclado = sync.mesclar(apagou, reescreveu)
        self.assertIsNone(mesclado["marcas"][0].get("apagadoEm"))
        self.assertEqual(mesclado["marcas"][0]["texto"], "destaque com nota")

    def test_lapide_velha_e_recolhida(self):
        agora = AGORA
        velha = {"marcas": [marca("a", 1, "x", -1, apagado=-sync.PRAZO_LAPIDE - 10)]}
        self.assertEqual(sync.mesclar(velha, {}, agora=agora)["marcas"], [])

    def test_mescla_e_comutativa(self):
        a = {"fronteira": 10, "posicao": {"bloco": 10, "em": 5},
             "marcas": [marca("a", 1, "um", 10), marca("c", 5, "três", 30)]}
        b = {"fronteira": 25, "posicao": {"bloco": 25, "em": 50},
             "marcas": [marca("b", 2, "dois", 20), marca("a", 1, "um editado", 40)]}
        ab = sync.mesclar(a, b, agora=AGORA)
        ba = sync.mesclar(b, a, agora=AGORA)
        self.assertEqual(ab, ba)
        self.assertEqual(ab["fronteira"], 25)
        self.assertEqual({m["id"] for m in ab["marcas"]}, {"a", "b", "c"})
        self.assertEqual(next(m for m in ab["marcas"] if m["id"] == "a")["texto"], "um editado")


class EndpointTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cliente = flask_app.app.test_client()
        cls.epub = os.path.join(TMP, "livro.epub")
        build_epub(cls.epub)
        with open(cls.epub, "rb") as fh:
            cls.dados = fh.read()
        cls.impressao = sync.impressao_digital(cls.dados)
        cls.cabecalho = {"Authorization": "Bearer token-de-teste"}

    def test_exige_token(self):
        self.assertEqual(self.cliente.get("/api/sync/hello").status_code, 401)
        errado = {"Authorization": "Bearer nao-e-o-token"}
        self.assertEqual(self.cliente.get("/api/sync/hello", headers=errado).status_code, 401)
        self.assertEqual(
            self.cliente.get("/api/sync/hello", headers=self.cabecalho).status_code, 200)

    def test_impressao_digital_e_estavel_e_distingue(self):
        self.assertEqual(sync.impressao_digital(self.dados), self.impressao)
        self.assertNotEqual(sync.impressao_digital(self.dados + b"x"), self.impressao)

    def test_ida_e_volta_do_estado(self):
        corpo = {"titulo": "Livro", "estado": {
            "fronteira": 12, "posicao": {"bloco": 12, "em": 1000},
            "marcas": [marca("a", 3, "um destaque", 900)]}}
        primeiro = self.cliente.post(f"/api/sync/estado/{self.impressao}",
                                     json=corpo, headers=self.cabecalho).get_json()
        self.assertEqual(primeiro["estado"]["fronteira"], 12)

        # outro aparelho, mais atrás, com um destaque próprio
        outro = {"estado": {"fronteira": 5, "posicao": {"bloco": 5, "em": 500},
                            "marcas": [marca("b", 1, "outro destaque", 950)]}}
        segundo = self.cliente.post(f"/api/sync/estado/{self.impressao}",
                                    json=outro, headers=self.cabecalho).get_json()
        self.assertEqual(segundo["estado"]["fronteira"], 12)          # não retrocedeu
        self.assertEqual(segundo["estado"]["posicao"]["bloco"], 12)   # a mais recente
        self.assertEqual({m["id"] for m in segundo["estado"]["marcas"]}, {"a", "b"})

    def test_arquivo_sobe_e_desce(self):
        envio = self.cliente.post(
            f"/api/sync/arquivo/{self.impressao}?titulo=Livro",
            data={"file": (io.BytesIO(self.dados), "livro.epub")},
            content_type="multipart/form-data", headers=self.cabecalho)
        self.assertEqual(envio.status_code, 201)

        baixado = self.cliente.get(f"/api/sync/arquivo/{self.impressao}",
                                   headers=self.cabecalho)
        self.assertEqual(baixado.status_code, 200)
        self.assertEqual(baixado.data, self.dados)
        self.assertEqual(sync.impressao_digital(baixado.data), self.impressao)

        listagem = self.cliente.get("/api/sync/hello", headers=self.cabecalho).get_json()
        item = next(l for l in listagem["livros"] if l["impressao"] == self.impressao)
        self.assertTrue(item["tem_arquivo"])

    def test_arquivo_trocado_e_recusado(self):
        resposta = self.cliente.post(
            f"/api/sync/arquivo/{self.impressao}",
            data={"file": (io.BytesIO(b"nao sou o mesmo arquivo"), "outro.epub")},
            content_type="multipart/form-data", headers=self.cabecalho)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("impressão digital", resposta.get_json()["error"])

    def test_cors_para_o_aplicativo(self):
        resposta = self.cliente.options(
            f"/api/sync/estado/{self.impressao}",
            headers={"Origin": "https://appassets.androidplatform.net"})
        self.assertLess(resposta.status_code, 300)
        self.assertEqual(resposta.headers["Access-Control-Allow-Origin"],
                         "https://appassets.androidplatform.net")

    def test_pagina_do_celular_e_servida(self):
        resposta = self.cliente.get("/celular")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn(b"Leitor sem spoiler", resposta.data)

    def test_pagina_vem_com_a_moldura(self):
        """Sem doctype, charset e viewport a página chega errada ao celular."""
        html = self.cliente.get("/celular").get_data(as_text=True)
        self.assertTrue(html.lstrip().lower().startswith("<!doctype html>"))
        self.assertIn('<meta charset="utf-8">', html)
        self.assertIn("width=device-width", html)
        self.assertIn('name="apple-mobile-web-app-capable"', html)
        self.assertIn('rel="apple-touch-icon"', html)
        self.assertNotIn(pagina.MARCA, html)       # o fragmento entrou no lugar
        self.assertEqual(html.lower().count("<body"), 1)
        self.assertIn("Abrir um EPUB", html)

    def test_arquivo_para_guardar(self):
        """O mesmo documento, servido como download — é o que vai para o iPhone."""
        resposta = self.cliente.get("/leitor-iphone.html")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("attachment", resposta.headers["Content-Disposition"])
        self.assertEqual(resposta.get_data(as_text=True),
                         self.cliente.get("/celular").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
