"""
Unit tests for WhatsAppService (src.services.whatsapp_service)

Covers (requests mockado):
- _get_headers (sem auth, Basic Auth, Bearer, device_id)
- verificar_status (disponivel/indisponivel, sem dispositivos, conectado, desconectado,
  ConnectionError, exceção genérica)
- obter_qr_code (v9 login, v9 qr_code, v8 legacy, indisponivel)
- listar_grupos (disponivel/indisponivel, sem device/device default, v8+, v8 antigo, erro)
- listar_dispositivos (sucesso, formato inesperado, erro HTTP, exceção, indisponivel)
- obter_id_dispositivo_por_jid (jid vazio, número curto, por jid exato, por número,
  não encontrado)
- verificar_status_dispositivo (indisponivel, id inválido, sem dispositivos, conectado,
  não encontrado, exceção)
- enviar_arquivo (indisponivel, não conectado, arquivo não existe, telefone inválido,
  sucesso, erro HTTP, exceção, grupo)
- enviar_texto (indisponivel, não conectado, telefone inválido, sucesso, erro)
- enviar_multiplos_arquivos (sem arquivos, com msg + sucesso, parcial, falha total)
"""

import os
import base64
import pytest
from unittest.mock import MagicMock, patch

from src.services.whatsapp_service import WhatsAppService, whatsapp_service


@pytest.fixture
def svc(mocker):
    """WhatsAppService isolado, sem rede, requests mockado."""
    s = WhatsAppService.__new__(WhatsAppService)
    s.api_url = "http://localhost:3000"
    s.api_key = None
    s.basic_auth = ""
    s._disponivel = True
    mocker.patch("src.services.whatsapp_service.requests.get")
    mocker.patch("src.services.whatsapp_service.requests.post")
    return s


def mock_response(status_code=200, json_data=None, text=""):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data or {}
    r.text = text if text != "" else "{}"
    return r


# ==================== Singleton ====================

class TestSingleton:
    def test_singleton(self):
        assert isinstance(whatsapp_service, WhatsAppService)


# ==================== _get_headers ====================

class TestGetHeaders:
    def test_sem_auth(self, svc):
        h = svc._get_headers()
        assert h["Accept"] == "application/json"
        assert "Authorization" not in h

    def test_bearer(self, svc):
        svc.api_key = "token123"
        h = svc._get_headers()
        assert h["Authorization"] == "Bearer token123"

    def test_basic_auth_explicito(self, svc):
        svc.basic_auth = "user:pass"
        h = svc._get_headers()
        esperado = "Basic " + base64.b64encode(b"user:pass").decode("ascii")
        assert h["Authorization"] == esperado

    def test_api_key_com_dois_pontos_vira_basic(self, svc):
        svc.api_key = "user:secret"
        h = svc._get_headers()
        esperado = "Basic " + base64.b64encode(b"user:secret").decode("ascii")
        assert h["Authorization"] == esperado

    def test_basic_prioridade_sobre_bearer(self, svc):
        svc.basic_auth = "u:p"
        svc.api_key = "token"
        h = svc._get_headers()
        assert h["Authorization"].startswith("Basic ")

    def test_device_id(self, svc):
        h = svc._get_headers(device_id="d1")
        assert h["X-Device-Id"] == "d1"


# ==================== verificar_status ====================

class TestVerificarStatus:
    def test_indisponivel(self, svc):
        svc._disponivel = False
        assert svc.verificar_status()["conectado"] is False

    def test_sem_dispositivos(self, svc, mocker):
        mocker.patch.object(svc, "listar_dispositivos", return_value=[])
        res = svc.verificar_status()
        assert res["conectado"] is False

    def test_conectado(self, svc, mocker):
        mocker.patch.object(svc, "listar_dispositivos", return_value=[
            {"state": "logged_in", "jid": "5569@s.whatsapp.net", "display_name": "Alef"}
        ])
        res = svc.verificar_status()
        assert res["conectado"] is True
        assert res["numero"] == "5569"

    def test_desconectado(self, svc, mocker):
        mocker.patch.object(svc, "listar_dispositivos", return_value=[
            {"state": "disconnected", "jid": "5569@s.whatsapp.net"}
        ])
        res = svc.verificar_status()
        assert res["conectado"] is False

    def test_connection_error(self, svc, mocker):
        import requests as req_lib
        exc = req_lib.exceptions.ConnectionError("down")
        mocker.patch.object(svc, "listar_dispositivos", side_effect=exc)
        res = svc.verificar_status()
        assert res["conectado"] is False
        assert "Container Docker" in res["mensagem"]

    def test_excecao_generica(self, svc, mocker):
        mocker.patch.object(svc, "listar_dispositivos", side_effect=Exception("boom"))
        res = svc.verificar_status()
        assert res["conectado"] is False
        assert "Erro" in res["mensagem"]


# ==================== obter_qr_code ====================

class TestObterQrCode:
    def test_indisponivel(self, svc):
        svc._disponivel = False
        assert svc.obter_qr_code() is None

    def test_v9_login(self, svc, mocker):
        mocker.patch("src.services.whatsapp_service.requests.get",
                     return_value=mock_response(200, {"results": {"qr_link": "http://qr/x.png"}}))
        assert svc.obter_qr_code() == "http://qr/x.png"

    def test_v9_qr_code_base64(self, svc, mocker):
        mocker.patch("src.services.whatsapp_service.requests.get",
                     return_value=mock_response(200, {"results": {"qr_code": "base64data"}}))
        assert svc.obter_qr_code() == "base64data"

    def test_v8_legacy_fallback(self, svc, mocker):
        # login sem qr -> v8 legacy
        resp_login = mock_response(200, {"results": {}})
        resp_legacy = mock_response(200, {"data": {"qr_code": "legacy64"}})
        mocker.patch("src.services.whatsapp_service.requests.get",
                     side_effect=[resp_login, resp_legacy])
        assert svc.obter_qr_code() == "legacy64"

    def test_sem_qr_nenhuma(self, svc, mocker):
        mocker.patch("src.services.whatsapp_service.requests.get",
                     return_value=mock_response(200, {}))
        assert svc.obter_qr_code() is None


# ==================== listar_grupos ====================

class TestListarGrupos:
    def test_indisponivel(self, svc):
        svc._disponivel = False
        assert svc.listar_grupos() == []

    def test_sem_dispositivos_configurados(self, svc, mocker):
        mocker.patch.object(svc, "listar_dispositivos", return_value=[])
        assert svc.listar_grupos() == []

    def test_usa_primeiro_logado(self, svc, mocker):
        mocker.patch.object(svc, "listar_dispositivos", return_value=[
            {"id": "WhatsApp-Alefe", "state": "logged_in"}
        ])
        mocker.patch("src.services.whatsapp_service.requests.get",
                     return_value=mock_response(200, {"results": {"data": [{"nome": "G1"}]}}))
        assert svc.listar_grupos() == [{"nome": "G1"}]

    def test_v8_antigo_formato(self, svc, mocker):
        mocker.patch("src.services.whatsapp_service.requests.get",
                     return_value=mock_response(200, {"data": [{"nome": "G1"}]}))
        assert svc.listar_grupos(device_id="d1") == [{"nome": "G1"}]

    def test_erro_http(self, svc, mocker):
        mocker.patch("src.services.whatsapp_service.requests.get",
                     return_value=mock_response(500, {}, "erro"))
        assert svc.listar_grupos(device_id="d1") == []

    def test_excecao(self, svc, mocker):
        mocker.patch("src.services.whatsapp_service.requests.get",
                     side_effect=Exception("boom"))
        assert svc.listar_grupos(device_id="d1") == []


# ==================== listar_dispositivos ====================

class TestListarDispositivos:
    def test_indisponivel(self, svc):
        svc._disponivel = False
        assert svc.listar_dispositivos() == []

    def test_sucesso(self, svc, mocker):
        devs = [{"id": "WhatsApp-Alefe", "state": "logged_in"}]
        mocker.patch("src.services.whatsapp_service.requests.get",
                     return_value=mock_response(200, {"results": devs}))
        assert svc.listar_dispositivos() == devs

    def test_results_nao_lista(self, svc, mocker):
        mocker.patch("src.services.whatsapp_service.requests.get",
                     return_value=mock_response(200, {"results": {"nope": 1}}))
        assert svc.listar_dispositivos() == []

    def test_erro_http(self, svc, mocker):
        mocker.patch("src.services.whatsapp_service.requests.get",
                     return_value=mock_response(500))
        assert svc.listar_dispositivos() == []

    def test_excecao(self, svc, mocker):
        mocker.patch("src.services.whatsapp_service.requests.get",
                     side_effect=Exception("boom"))
        assert svc.listar_dispositivos() == []


# ==================== obter_id_dispositivo_por_jid ====================

class TestObterIdPorJid:
    def test_jid_vazio(self, svc):
        assert svc.obter_id_dispositivo_por_jid("") is None

    def test_numero_curto(self, svc):
        assert svc.obter_id_dispositivo_por_jid("12345") is None

    def test_por_jid_exato(self, svc, mocker):
        mocker.patch.object(svc, "listar_dispositivos", return_value=[
            {"jid": "5569@s.whatsapp.net", "id": "WhatsApp-Alefe"}
        ])
        assert svc.obter_id_dispositivo_por_jid("5569@s.whatsapp.net") == "WhatsApp-Alefe"

    def test_por_numero_sem_arroba(self, svc, mocker):
        # Número completo (>=10 dígitos) sem arroba vira JID
        mocker.patch.object(svc, "listar_dispositivos", return_value=[
            {"jid": "556993451333@s.whatsapp.net", "id": "WhatsApp-Alefe"}
        ])
        assert svc.obter_id_dispositivo_por_jid("556993451333") == "WhatsApp-Alefe"

    def test_nao_encontrado(self, svc, mocker):
        mocker.patch.object(svc, "listar_dispositivos", return_value=[
            {"jid": "999@s.whatsapp.net", "id": "X"}
        ])
        assert svc.obter_id_dispositivo_por_jid("0000000000") is None

    def test_sem_dispositivos(self, svc, mocker):
        mocker.patch.object(svc, "listar_dispositivos", return_value=[])
        assert svc.obter_id_dispositivo_por_jid("5569") is None


# ==================== verificar_status_dispositivo ====================

class TestVerificarStatusDispositivo:
    def test_indisponivel(self, svc):
        svc._disponivel = False
        assert svc.verificar_status_dispositivo("d1")["sucesso"] is False

    def test_id_invalido(self, svc):
        res = svc.verificar_status_dispositivo("curto")
        assert res["sucesso"] is False

    def test_conectado(self, svc, mocker):
        mocker.patch.object(svc, "listar_dispositivos", return_value=[
            {"jid": "556993451333@s.whatsapp.net", "state": "logged_in",
             "display_name": "Alef"}
        ])
        res = svc.verificar_status_dispositivo("556993451333")
        assert res["sucesso"] is True
        assert res["is_logged_in"] is True
        assert res["numero"] == "556993451333"

    def test_nao_conectado(self, svc, mocker):
        mocker.patch.object(svc, "listar_dispositivos", return_value=[
            {"jid": "5569@s.whatsapp.net", "state": "disconnected"}
        ])
        res = svc.verificar_status_dispositivo("5569@s.whatsapp.net")
        assert res["sucesso"] is True
        assert res["is_logged_in"] is False

    def test_dispositivo_nao_encontrado(self, svc, mocker):
        mocker.patch.object(svc, "listar_dispositivos", return_value=[
            {"jid": "99999999999@s.whatsapp.net"}
        ])
        res = svc.verificar_status_dispositivo("556993451333")
        assert res["sucesso"] is False

    def test_excecao(self, svc, mocker):
        mocker.patch.object(svc, "listar_dispositivos", side_effect=Exception("boom"))
        res = svc.verificar_status_dispositivo("556993451333")
        assert res["sucesso"] is False


# ==================== enviar_arquivo ====================

class TestEnviarArquivo:
    def test_indisponivel(self, svc):
        svc._disponivel = False
        assert svc.enviar_arquivo("5569", "/tmp/x.pdf")["sucesso"] is False

    def test_nao_conectado(self, svc, mocker):
        mocker.patch.object(svc, "verificar_status", return_value={"conectado": False})
        res = svc.enviar_arquivo("5569", "/tmp/x.pdf")
        assert res["sucesso"] is False
        assert "não conectado" in res["mensagem"]

    def test_arquivo_nao_existe(self, svc, mocker):
        mocker.patch.object(svc, "verificar_status", return_value={"conectado": True})
        mocker.patch("os.path.exists", return_value=False)
        res = svc.enviar_arquivo("5569", "/tmp/nao_existe.pdf")
        assert res["sucesso"] is False
        assert "não encontrado" in res["mensagem"]

    def test_telefone_invalido(self, svc, mocker):
        mocker.patch.object(svc, "verificar_status", return_value={"conectado": True})
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("src.services.whatsapp_service.normalizar_telefone", return_value="")
        res = svc.enviar_arquivo("inválido", "/tmp/x.pdf")
        assert res["sucesso"] is False

    def test_sucesso(self, svc, mocker, tmp_path):
        mocker.patch.object(svc, "verificar_status", return_value={"conectado": True})
        arquivo = tmp_path / "doc.pdf"
        arquivo.write_bytes(b"%PDF")
        mocker.patch("src.services.whatsapp_service.normalizar_telefone", return_value="5569")
        mocker.patch("src.services.whatsapp_service.requests.post",
                     return_value=mock_response(200, {"results": {"message_id": "m1"}}))
        res = svc.enviar_arquivo("5569", str(arquivo))
        assert res["sucesso"] is True
        assert res["detalhes"]["message_id"] == "m1"

    def test_grupo_jid(self, svc, mocker, tmp_path):
        mocker.patch.object(svc, "verificar_status", return_value={"conectado": True})
        arquivo = tmp_path / "doc.pdf"
        arquivo.write_bytes(b"%PDF")
        mocker.patch("src.services.whatsapp_service.requests.post",
                     return_value=mock_response(200, {"data": {}}))
        res = svc.enviar_arquivo("123@g.us", str(arquivo), is_grupo=True)
        assert res["sucesso"] is True
        assert res["detalhes"]["destinatario"] == "123@g.us"

    def test_erro_http(self, svc, mocker, tmp_path):
        mocker.patch.object(svc, "verificar_status", return_value={"conectado": True})
        arquivo = tmp_path / "doc.pdf"
        arquivo.write_bytes(b"%PDF")
        mocker.patch("src.services.whatsapp_service.normalizar_telefone", return_value="5569")
        mocker.patch("src.services.whatsapp_service.requests.post",
                     return_value=mock_response(500, {}, "erro http"))
        res = svc.enviar_arquivo("5569", str(arquivo))
        assert res["sucesso"] is False

    def test_excecao(self, svc, mocker, tmp_path):
        mocker.patch.object(svc, "verificar_status", return_value={"conectado": True})
        arquivo = tmp_path / "doc.pdf"
        arquivo.write_bytes(b"%PDF")
        mocker.patch("src.services.whatsapp_service.normalizar_telefone", return_value="5569")
        mocker.patch("src.services.whatsapp_service.requests.post",
                     side_effect=Exception("boom"))
        res = svc.enviar_arquivo("5569", str(arquivo))
        assert res["sucesso"] is False


# ==================== enviar_texto ====================

class TestEnviarTexto:
    def test_indisponivel(self, svc):
        svc._disponivel = False
        assert svc.enviar_texto("5569", "oi")["sucesso"] is False

    def test_nao_conectado(self, svc, mocker):
        mocker.patch.object(svc, "verificar_status", return_value={"conectado": False})
        assert svc.enviar_texto("5569", "oi")["sucesso"] is False

    def test_telefone_invalido(self, svc, mocker):
        mocker.patch.object(svc, "verificar_status", return_value={"conectado": True})
        mocker.patch("src.services.whatsapp_service.normalizar_telefone", return_value="")
        assert svc.enviar_texto("inválido", "oi")["sucesso"] is False

    def test_sucesso(self, svc, mocker):
        mocker.patch.object(svc, "verificar_status", return_value={"conectado": True})
        mocker.patch("src.services.whatsapp_service.normalizar_telefone", return_value="5569")
        mocker.patch("src.services.whatsapp_service.requests.post",
                     return_value=mock_response(200, {"results": {"message_id": "m1"}}))
        res = svc.enviar_texto("5569", "oi")
        assert res["sucesso"] is True

    def test_erro_http(self, svc, mocker):
        mocker.patch.object(svc, "verificar_status", return_value={"conectado": True})
        mocker.patch("src.services.whatsapp_service.normalizar_telefone", return_value="5569")
        mocker.patch("src.services.whatsapp_service.requests.post",
                     return_value=mock_response(400, {}, "erro"))
        assert svc.enviar_texto("5569", "oi")["sucesso"] is False


# ==================== enviar_multiplos_arquivos ====================

class TestEnviarMultiplosArquivos:
    def test_sem_arquivos(self, svc):
        res = svc.enviar_multiplos_arquivos("5569", [])
        assert res["sucesso"] is False

    def test_sucesso_com_mensagem(self, svc, mocker):
        ok = {"sucesso": True, "mensagem": "ok"}
        mocker.patch.object(svc, "enviar_texto", return_value=ok)
        mocker.patch.object(svc, "enviar_arquivo", return_value=ok)
        mocker.patch("time.sleep")
        res = svc.enviar_multiplos_arquivos("5569", ["a.pdf", "b.pdf"], mensagem="oi")
        assert res["sucesso"] is True
        assert len(res["detalhes"]["arquivos_enviados"]) == 2

    def test_parcial(self, svc, mocker):
        mocker.patch.object(svc, "enviar_texto",
                            return_value={"sucesso": True, "mensagem": "ok"})
        mocker.patch.object(svc, "enviar_arquivo",
                            side_effect=[
                                {"sucesso": True, "mensagem": "ok"},
                                {"sucesso": False, "mensagem": "erro"},
                            ])
        mocker.patch("time.sleep")
        res = svc.enviar_multiplos_arquivos("5569", ["a.pdf", "b.pdf"], mensagem="oi")
        assert res["parcial"] is True

    def test_falha_total(self, svc, mocker):
        mocker.patch.object(svc, "enviar_texto",
                            return_value={"sucesso": False, "mensagem": "erro"})
        mocker.patch.object(svc, "enviar_arquivo",
                            return_value={"sucesso": False, "mensagem": "erro"})
        mocker.patch("time.sleep")
        res = svc.enviar_multiplos_arquivos("5569", ["a.pdf"], mensagem="oi")
        assert res["sucesso"] is False
