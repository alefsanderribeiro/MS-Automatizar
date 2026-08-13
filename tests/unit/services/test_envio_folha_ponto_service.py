"""
Unit tests for EnvioFolhaPontoService

Covers:
- Initialization (available / unavailable / exceptions)
- Index creation
- registrar_envio
- buscar_por_id / buscar_por_periodo / buscar_por_tipo / buscar_por_status
- buscar_pendentes_retry / listar_historico
- incrementar_tentativa / marcar_enviado / marcar_erro / marcar_parcial
- contar_por_status / contar_por_tipo / obter_resumo_periodo
"""

import pytest
from unittest.mock import MagicMock, patch
from bson import ObjectId
from datetime import datetime, timezone
from typing import Dict, Any, List

from src.services.envio_folha_ponto_service import (
    EnvioFolhaPontoService,
    envio_folha_ponto_service,
)
from src.models.envio_folha_ponto_models import TipoEnvioEnum, StatusEnvioEnum


def create_mock_cursor(results: List[Dict[str, Any]]):
    """Create a mock MongoDB cursor with chainable methods."""
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.__iter__ = MagicMock(return_value=iter(results))
    cursor.__list__ = results
    return cursor


def make_envio_dados(**kwargs):
    """Factory for valid envio data dict."""
    dados = {
        "tipo_envio": "email",
        "status": "pendente",
        "destinatarios": ["joao@teste.com"],
        "local_contrato_polo": "DSEI AMAPÁ",
        "diretorio_completo": "/tmp/folhas",
        "arquivos_enviados": [],
        "arquivos_com_erro": [],
        "mes_referencia": 1,
        "ano_referencia": 2025,
        "tentativas": 1,
        "max_tentativas": 3,
        "erro_detalhes": None,
        "data_envio_sucesso": None,
    }
    dados.update(kwargs)
    return dados


@pytest.fixture
def mock_pool_e_db():
    """Mock MongoDBConnectionPool and the availability flag."""
    mock_db = MagicMock()
    mock_client = MagicMock()
    mock_client.admin.command.return_value = {"ok": 1}

    mock_pool_instance = MagicMock()
    mock_pool_instance.get_database.return_value = mock_db
    mock_pool_instance.get_client.return_value = mock_client
    mock_pool_instance.disponivel = True

    mock_colecao = MagicMock()
    mock_colecao.find_one = MagicMock(return_value=None)
    mock_colecao.find = MagicMock(return_value=create_mock_cursor([]))
    mock_colecao.insert_one = MagicMock(return_value=MagicMock(inserted_id=ObjectId()))
    mock_colecao.update_one = MagicMock(return_value=MagicMock(modified_count=1, matched_count=1))
    mock_colecao.aggregate = MagicMock(return_value=iter([]))
    mock_colecao.create_index = MagicMock()

    mock_db.__getitem__ = MagicMock(return_value=mock_colecao)
    mock_db["envios_folhas_de_ponto"] = mock_colecao

    with patch("src.services.envio_folha_ponto_service.MONGODB_DISPONIVEL", True), \
         patch("src.services.envio_folha_ponto_service.MongoDBConnectionPool") as mock_class:
        mock_class.return_value = mock_pool_instance
        yield {
            "pool": mock_pool_instance,
            "db": mock_db,
            "colecao": mock_colecao,
        }


# ==================== Inicialização ====================

class TestInicializacao:
    def test_init_disponivel(self, mock_pool_e_db, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = EnvioFolhaPontoService()
        assert service.disponivel is True
        assert service.colecao is mock_pool_e_db["colecao"]

    def test_init_mongodb_indisponivel(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        with patch("src.services.envio_folha_ponto_service.MONGODB_DISPONIVEL", False):
            service = EnvioFolhaPontoService()
            assert service.disponivel is False
            assert service.db is None
            assert service.colecao is None

    def test_init_pool_sem_banco(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        with patch("src.services.envio_folha_ponto_service.MONGODB_DISPONIVEL", True), \
             patch("src.services.envio_folha_ponto_service.MongoDBConnectionPool") as mock_class:
            pool = MagicMock()
            pool.get_database.return_value = None
            mock_class.return_value = pool
            service = EnvioFolhaPontoService()
            assert service.disponivel is False

    def test_init_erro_conexao(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        from pymongo.errors import ConnectionFailure
        with patch("src.services.envio_folha_ponto_service.MONGODB_DISPONIVEL", True), \
             patch("src.services.envio_folha_ponto_service.MongoDBConnectionPool",
                   side_effect=ConnectionFailure("down")):
            service = EnvioFolhaPontoService()
            assert service.disponivel is False


# ==================== CRUD ====================

class TestRegistro:
    def test_registrar_envio_sucesso(self, mock_pool_e_db, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = EnvioFolhaPontoService()
        service.colecao = mock_pool_e_db["colecao"]
        service._disponivel = True

        returned_id = ObjectId()
        mock_pool_e_db["colecao"].insert_one.return_value = MagicMock(inserted_id=returned_id)

        result = service.registrar_envio(make_envio_dados())
        assert result == str(returned_id)
        mock_pool_e_db["colecao"].insert_one.assert_called_once()

    def test_registrar_envio_indisponivel(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = EnvioFolhaPontoService()
        service._disponivel = False
        assert service.registrar_envio(make_envio_dados()) is None

    def test_registrar_envio_erro_validacao(self, mock_pool_e_db, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = EnvioFolhaPontoService()
        service.colecao = mock_pool_e_db["colecao"]
        service._disponivel = True
        # dados inválidos -> exception dentro do try -> retorna None
        assert service.registrar_envio({"tipo_envio": ""}) is None


class TestBuscas:
    def test_buscar_por_id(self, mock_pool_e_db, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = EnvioFolhaPontoService()
        service.colecao = mock_pool_e_db["colecao"]
        service._disponivel = True

        doc = {"_id": ObjectId(), "tipo_envio": "EMAIL"}
        mock_pool_e_db["colecao"].find_one.return_value = doc

        out = service.buscar_por_id("507f1f77bcf86cd799439011")
        assert out == doc

    def test_buscar_por_id_indisponivel(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = EnvioFolhaPontoService()
        service._disponivel = False
        assert service.buscar_por_id("507f1f77bcf86cd799439011") is None

    def test_buscar_por_periodo_com_tipo(self, mock_pool_e_db, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = EnvioFolhaPontoService()
        service.colecao = mock_pool_e_db["colecao"]
        service._disponivel = True

        doc = {"_id": ObjectId(), "mes_referencia": 1, "ano_referencia": 2025}
        mock_pool_e_db["colecao"].find.return_value = create_mock_cursor([doc])

        out = service.buscar_por_periodo(1, 2025, TipoEnvioEnum.EMAIL)
        assert out == [doc]

    def test_buscar_por_periodo_sem_tipo(self, mock_pool_e_db, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = EnvioFolhaPontoService()
        service.colecao = mock_pool_e_db["colecao"]
        service._disponivel = True
        mock_pool_e_db["colecao"].find.return_value = create_mock_cursor([])
        assert service.buscar_por_periodo(2, 2025) == []

    def test_buscar_por_periodo_indisponivel(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = EnvioFolhaPontoService()
        service._disponivel = False
        assert service.buscar_por_periodo(1, 2025) == []

    def test_buscar_por_tipo(self, mock_pool_e_db, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = EnvioFolhaPontoService()
        service.colecao = mock_pool_e_db["colecao"]
        service._disponivel = True
        doc = {"_id": ObjectId(), "tipo_envio": "WHATSAPP_INDIVIDUAL"}
        mock_pool_e_db["colecao"].find.return_value = create_mock_cursor([doc])
        assert service.buscar_por_tipo(TipoEnvioEnum.WHATSAPP_INDIVIDUAL, limit=5) == [doc]

    def test_buscar_por_status(self, mock_pool_e_db, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = EnvioFolhaPontoService()
        service.colecao = mock_pool_e_db["colecao"]
        service._disponivel = True
        doc = {"_id": ObjectId(), "status": "erro"}
        mock_pool_e_db["colecao"].find.return_value = create_mock_cursor([doc])
        assert service.buscar_por_status(StatusEnvioEnum.ERRO) == [doc]

    def test_buscar_pendentes_retry(self, mock_pool_e_db, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = EnvioFolhaPontoService()
        service.colecao = mock_pool_e_db["colecao"]
        service._disponivel = True
        doc = {"_id": ObjectId(), "status": "erro", "tentativas": 1}
        mock_pool_e_db["colecao"].find.return_value = create_mock_cursor([doc])
        assert service.buscar_pendentes_retry(3) == [doc]

    def test_listar_historico(self, mock_pool_e_db, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = EnvioFolhaPontoService()
        service.colecao = mock_pool_e_db["colecao"]
        service._disponivel = True
        doc = {"_id": ObjectId()}
        mock_pool_e_db["colecao"].find.return_value = create_mock_cursor([doc])
        assert service.listar_historico(limit=10, skip=0) == [doc]


# ==================== Atualizações ====================

class TestAtualizacoes:
    @pytest.fixture
    def service(self, mock_pool_e_db, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        s = EnvioFolhaPontoService()
        s.colecao = mock_pool_e_db["colecao"]
        s._disponivel = True
        return s

    def test_incrementar_tentativa(self, service, mock_pool_e_db):
        mock_pool_e_db["colecao"].update_one.return_value = MagicMock(modified_count=1)
        assert service.incrementar_tentativa("507f1f77bcf86cd799439011") is True

    def test_incrementar_tentativa_nao_modificado(self, service, mock_pool_e_db):
        mock_pool_e_db["colecao"].update_one.return_value = MagicMock(modified_count=0)
        assert service.incrementar_tentativa("507f1f77bcf86cd799439011") is False

    def test_incrementar_tentativa_indisponivel(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        s = EnvioFolhaPontoService()
        s._disponivel = False
        assert s.incrementar_tentativa("x") is False

    def test_marcar_enviado(self, service, mock_pool_e_db):
        mock_pool_e_db["colecao"].update_one.return_value = MagicMock(modified_count=1)
        assert service.marcar_enviado("507f1f77bcf86cd799439011", ["a.pdf"]) is True

    def test_marcar_erro(self, service, mock_pool_e_db):
        mock_pool_e_db["colecao"].update_one.return_value = MagicMock(modified_count=1)
        assert service.marcar_erro("507f1f77bcf86cd799439011", "falhou") is True

    def test_marcar_parcial(self, service, mock_pool_e_db):
        mock_pool_e_db["colecao"].update_one.return_value = MagicMock(modified_count=1)
        assert service.marcar_parcial("507f1f77bcf86cd799439011", ["a.pdf"], ["b.pdf"]) is True

    def test_marcar_erro_exception(self, service, mock_pool_e_db):
        mock_pool_e_db["colecao"].update_one.side_effect = Exception("boom")
        assert service.marcar_erro("507f1f77bcf86cd799439011", "x") is False


# ==================== Estatísticas ====================

class TestEstatisticas:
    @pytest.fixture
    def service(self, mock_pool_e_db, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        s = EnvioFolhaPontoService()
        s.colecao = mock_pool_e_db["colecao"]
        s._disponivel = True
        return s

    def test_contar_por_status(self, service, mock_pool_e_db):
        mock_pool_e_db["colecao"].aggregate.return_value = mock_cursor_aggr = [{"_id": "envia", "count": 3}]
        mock_pool_e_db["colecao"].aggregate.return_value = iter([{"_id": "enviado", "count": 3}])
        assert service.contar_por_status(1, 2025) == {"enviado": 3}

    def test_contar_por_tipo(self, service, mock_pool_e_db):
        mock_pool_e_db["colecao"].aggregate.return_value = iter([{"_id": "EMAIL", "count": 2}])
        assert service.contar_por_tipo(1, 2025) == {"EMAIL": 2}

    def test_obter_resumo_periodo(self, service, mock_pool_e_db):
        envio = {
            "status": "enviado",
            "tipo_envio": "EMAIL",
            "arquivos_enviados": ["a.pdf", "b.pdf"],
        }
        mock_pool_e_db["colecao"].find.return_value = create_mock_cursor([envio])
        resumo = service.obter_resumo_periodo(1, 2025)
        assert resumo["periodo"] == "01/2025"
        assert resumo["total_envios"] == 1
        assert resumo["por_status"] == {"enviado": 1}
        assert resumo["total_arquivos_enviados"] == 2

    def test_contar_por_status_indisponivel(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        s = EnvioFolhaPontoService()
        s._disponivel = False
        assert s.contar_por_status() == {}
