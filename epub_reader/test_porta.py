"""Testes da porta de entrada — a parte que sustenta pôr isto na nuvem.

Rode com:  python -m unittest test_porta  (dentro de epub_reader/)
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
import unittest

_CRIOU = "EPUB_DATA_DIR" not in os.environ
TMP = os.environ.setdefault("EPUB_DATA_DIR", tempfile.mkdtemp(prefix="leitor-porta-"))
if _CRIOU:
    atexit.register(shutil.rmtree, TMP, True)
os.environ.setdefault("EPUB_SYNC_TOKEN", "token-de-teste")
os.environ.pop("ANTHROPIC_API_KEY", None)

import app as flask_app  # noqa: E402
import porta  # noqa: E402

SENHA = "abre-te sésamo"


class PortaTests(unittest.TestCase):

    def setUp(self):
        porta.SENHA = SENHA
        porta._falhas.clear()
        self.cliente = flask_app.app.test_client()

    def tearDown(self):
        porta.SENHA = ""
        porta._falhas.clear()

    # ------------------------------------------------------------ fechada

    def test_sem_senha_configurada_segue_aberto(self):
        """Na sua máquina não há o que trancar — e nada deve mudar."""
        porta.SENHA = ""
        self.assertEqual(self.cliente.get("/").status_code, 200)
        self.assertEqual(self.cliente.get("/api/books").status_code, 200)

    def test_pagina_manda_para_a_entrada(self):
        resposta = self.cliente.get("/")
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/entrar", resposta.headers["Location"])

    def test_api_responde_401_em_json(self):
        """Quem chama a API é o JavaScript: redirecionar para HTML confundiria."""
        resposta = self.cliente.get("/api/books")
        self.assertEqual(resposta.status_code, 401)
        self.assertIn("senha", resposta.get_json()["error"].lower())

    def test_conversa_tambem_fica_atras_da_porta(self):
        """É a rota que gasta a chave da API; aberta, seria a mais cara."""
        resposta = self.cliente.post("/api/books/qualquer/chat",
                                     json={"question": "e aí?"})
        self.assertEqual(resposta.status_code, 401)

    def test_leitor_do_celular_tambem(self):
        self.assertEqual(self.cliente.get("/celular").status_code, 302)
        self.assertEqual(self.cliente.get("/leitor-iphone.html").status_code, 302)

    # ------------------------------------------------------------- abrindo

    def test_senha_certa_abre_e_continua_aberta(self):
        resposta = self.cliente.post("/entrar", data={"senha": SENHA, "destino": "/"})
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(self.cliente.get("/").status_code, 200)
        self.assertEqual(self.cliente.get("/api/books").status_code, 200)

    def test_senha_errada_nao_abre(self):
        resposta = self.cliente.post("/entrar", data={"senha": "chute", "destino": "/"})
        self.assertEqual(resposta.status_code, 401)
        self.assertEqual(self.cliente.get("/").status_code, 302)

    def test_sair_fecha(self):
        self.cliente.post("/entrar", data={"senha": SENHA})
        self.assertEqual(self.cliente.get("/").status_code, 200)
        self.cliente.get("/sair")
        self.assertEqual(self.cliente.get("/").status_code, 302)

    def test_destino_nao_serve_de_trampolim(self):
        """Um /entrar?destino=//outro.site não pode devolver a pessoa para fora."""
        for ruim in ("//exemplo.invalido", "https://exemplo.invalido", "javascript:1"):
            resposta = self.cliente.post("/entrar", data={"senha": SENHA, "destino": ruim})
            self.assertEqual(resposta.headers["Location"], "/", f"escapou com {ruim}")
            self.cliente.get("/sair")

    # --------------------------------------------------------------- freio

    def test_freio_depois_de_muitas_tentativas(self):
        for _ in range(porta.TENTATIVAS):
            self.cliente.post("/entrar", data={"senha": "chute"})
        travada = self.cliente.post("/entrar", data={"senha": "chute"})
        self.assertEqual(travada.status_code, 429)
        # e o castigo não é contornável acertando a senha
        certa = self.cliente.post("/entrar", data={"senha": SENHA})
        self.assertEqual(certa.status_code, 429)

    def test_acerto_limpa_o_contador(self):
        for _ in range(porta.TENTATIVAS - 1):
            self.cliente.post("/entrar", data={"senha": "chute"})
        self.cliente.post("/entrar", data={"senha": SENHA})
        self.cliente.get("/sair")
        self.assertEqual(porta.travado.__module__, "porta")   # sanidade
        errada = self.cliente.post("/entrar", data={"senha": "chute"})
        self.assertEqual(errada.status_code, 401)             # não 429

    # ------------------------------------------------------------ exceções

    def test_sincronia_passa_com_token_e_sem_cookie(self):
        """O APK não tem navegador nem cookie: ele entra pelo Bearer."""
        cabecalho = {"Authorization": "Bearer " + os.environ["EPUB_SYNC_TOKEN"]}
        self.assertEqual(
            self.cliente.get("/api/sync/hello", headers=cabecalho).status_code, 200)
        # e sem o token continua barrado pelo próprio sync
        self.assertEqual(self.cliente.get("/api/sync/hello").status_code, 401)

    def test_saude_fica_aberta(self):
        """A hospedagem precisa checar o processo sem saber a senha."""
        resposta = self.cliente.get("/saude")
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.get_json()["ok"])

    def test_exigir_senha_sem_senha_derruba_a_subida(self):
        """Na nuvem, esquecer a senha tem de quebrar — não abrir."""
        antes_exigir, antes_senha = porta.EXIGIR, porta.SENHA
        try:
            porta.EXIGIR, porta.SENHA = True, ""
            with self.assertRaises(SystemExit) as caso:
                porta.conferir_configuracao()
            self.assertIn("EPUB_SENHA", str(caso.exception))
        finally:
            porta.EXIGIR, porta.SENHA = antes_exigir, antes_senha


if __name__ == "__main__":
    unittest.main(verbosity=2)
