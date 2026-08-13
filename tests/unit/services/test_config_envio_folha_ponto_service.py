"""
Unit tests for ConfigEnvioFolhaPontoService.

Covers:
- Inicialização (disponível / indisponível / sem banco / erro conexão)
- Criação de índices
- CRUD: criar, buscar_por_id, listar, atualizar, excluir (soft delete), reativar
- Consultas: buscar_por_nome, buscar_por_identificador, buscar_por_empresa,
  buscar_por_local, listar_ativos_para_envio
- Validação e contagem
- Importação da planilha (criar, atualizar/pular, marcar_removidos)
"""

import pytest
from unittest.mock import MagicMock, patch
from bson import ObjectId
from datetime import datetime, timezone
from typing import Dict, Any, List

from src.services.config_envio_folha_ponto_service import (
    ConfigEnvioFolhaPontoService,
    config_envio_folha_ponto_service,
)
from src.models.config_envio_folha_ponto_models import (
    SimNaoEnum,
    OrigemConfigEnum,
)


def create_mock_cursor(results: List[Dict[str, Any]]):
    """Create a mock MongoDB cursor with chainable methods."""
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.__iter__ = MagicMock(return_value=iter(results))
    cursor.__list__ = results
    return cursor


def make_config_dados(**kwargs):
    """Factory for valid config data dict."""
    dados = {
        "identificador": "1",
        "nome": "João da Silva",
        "emails": ["joao@x.com"],
        "telefones": ["96999999999"],
        "grupos_whatsapp": ["Administrativo"],
        "enviar_email": "S",
        "enviar_whatsapp": "N",
        "enviar_grupo_whatsapp": "S",
        "enviar_impresso": "N",
        "empresa": "MS Servicos",
        "local_contrato_polo": "DSEI AMAPÁ",
        "diretorio_geral": "Z:\\04. PESSOAL\\FOLHA PONTO",
        "diretorio_especifico": "01. MS SERVIÇOS\\ADMINISTRATIVO",
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
    mock_colecao.count_documents = MagicMock(return_value=0)
    mock_colecao.create_index = MagicMock()

    mock_db.__getitem__ = MagicMock(return_value=mock_colecao)
    mock_db["configs_envio_folha_ponto"] = mock_colecao

    with patch("src.services.config_envio_folha_ponto_service.MONGODB_DISPONIVEL", True), \
         patch("src.services.config_envio_folha_ponto_service.MongoDBConnectionPool") as mock_class:
        mock_class.return_value = mock_pool_instance
        yield {
            "pool": mock_pool_instance,
            "db": mock_db,
            "colecao": mock_colecao,
        }


def make_service(mock_pool_e_db, monkeypatch):
    """Cria um service conectado ao mock, com disponível=True."""
    monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
    service = ConfigEnvioFolhaPontoService()
    service.colecao = mock_pool_e_db["colecao"]
    service._disponivel = True
    return service


# ==================== Inicialização ====================

class TestInicializacao:
    def test_init_disponivel(self, mock_pool_e_db, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = ConfigEnvioFolhaPontoService()
        assert service.disponivel is True
        assert service.colecao is mock_pool_e_db["colecao"]

    def test_init_mongodb_indisponivel(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        with patch("src.services.config_envio_folha_ponto_service.MONGODB_DISPONIVEL", False):
            service = ConfigEnvioFolhaPontoService()
            assert service.disponivel is False
            assert service.colecao is None

    def test_init_pool_sem_banco(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        with patch("src.services.config_envio_folha_ponto_service.MONGODB_DISPONIVEL", True), \
             patch("src.services.config_envio_folha_ponto_service.MongoDBConnectionPool") as mock_class:
            pool = MagicMock()
            pool.get_database.return_value = None
            mock_class.return_value = pool
            service = ConfigEnvioFolhaPontoService()
            assert service.disponivel is False
            assert service.colecao is None

    def test_init_erro_conexao(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        from pymongo.errors import ConnectionFailure
        with patch("src.services.config_envio_folha_ponto_service.MONGODB_DISPONIVEL", True), \
             patch("src.services.config_envio_folha_ponto_service.MongoDBConnectionPool",
                   side_effect=ConnectionFailure("down")):
            service = ConfigEnvioFolhaPontoService()
            assert service.disponivel is False


# ==================== CRUD ====================

class TestCriar:
    def test_criar_sucesso(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        returned_id = ObjectId()
        mock_pool_e_db["colecao"].insert_one.return_value = MagicMock(inserted_id=returned_id)
        result = service.criar(make_config_dados())
        assert result == str(returned_id)
        mock_pool_e_db["colecao"].insert_one.assert_called_once()

    def test_criar_normaliza_flags(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        service.criar(make_config_dados(enviar_email="SIM", enviar_whatsapp=True, enviar_grupo_whatsapp="nao"))
        doc_inserido = mock_pool_e_db["colecao"].insert_one.call_args[0][0]
        assert doc_inserido["enviar_email"] == "S"
        assert doc_inserido["enviar_whatsapp"] == "S"
        assert doc_inserido["enviar_grupo_whatsapp"] == "N"

    def test_criar_indisponivel(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = ConfigEnvioFolhaPontoService()
        service._disponivel = False
        assert service.criar(make_config_dados()) is None

    def test_criar_validacao_erro(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        assert service.criar({"identificador": "", "nome": ""}) is None


class TestBuscar:
    def test_buscar_por_id(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        doc = {"_id": ObjectId(), "nome": "João"}
        mock_pool_e_db["colecao"].find_one.return_value = doc
        assert service.buscar_por_id("507f1f77bcf86cd799439011") == doc
        # filtro inclui excluida=False
        filtro = mock_pool_e_db["colecao"].find_one.call_args[0][0]
        assert filtro["excluida"] is False

    def test_buscar_por_id_incluir_excluidas(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        service.buscar_por_id("507f1f77bcf86cd799439011", incluir_excluidas=True)
        filtro = mock_pool_e_db["colecao"].find_one.call_args[0][0]
        assert "excluida" not in filtro

    def test_buscar_por_id_indisponivel(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = ConfigEnvioFolhaPontoService()
        service._disponivel = False
        assert service.buscar_por_id("x") is None

    def test_listar_ativas(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        doc = {"_id": ObjectId(), "nome": "João"}
        mock_pool_e_db["colecao"].find.return_value = create_mock_cursor([doc])
        out = service.listar(apenas_ativas=True)
        assert out == [doc]
        filtro = mock_pool_e_db["colecao"].find.call_args[0][0]
        assert filtro == {"excluida": False, "ativo": True}

    def test_listar_todos(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        mock_pool_e_db["colecao"].find.return_value = create_mock_cursor([])
        assert service.listar(apenas_ativas=False) == []
        filtro = mock_pool_e_db["colecao"].find.call_args[0][0]
        assert filtro == {"excluida": False}

    def test_listar_incluir_excluidas(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        mock_pool_e_db["colecao"].find.return_value = create_mock_cursor([])
        service.listar(apenas_ativas=False, incluir_excluidas=True)
        filtro = mock_pool_e_db["colecao"].find.call_args[0][0]
        assert filtro == {}

    def test_listar_indisponivel(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = ConfigEnvioFolhaPontoService()
        service._disponivel = False
        assert service.listar() == []


class TestAtualizar:
    def test_atualizar_sucesso(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        # buscar_por_id retorna doc existente para validação
        mock_pool_e_db["colecao"].find_one.return_value = make_config_dados()
        mock_pool_e_db["colecao"].update_one.return_value = MagicMock(modified_count=1)
        assert service.atualizar("507f1f77bcf86cd799439011", {"enviar_email": "SIM"}) is True

    def test_atualizar_indisponivel(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = ConfigEnvioFolhaPontoService()
        service._disponivel = False
        assert service.atualizar("x", {"nome": "y"}) is False


class TestExcluirReativar:
    def test_excluir_soft_delete(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        mock_pool_e_db["colecao"].update_one.return_value = MagicMock(modified_count=1)
        assert service.excluir("507f1f77bcf86cd799439011") is True
        op = mock_pool_e_db["colecao"].update_one.call_args[0][1]
        assert op["$set"]["excluida"] is True
        assert op["$set"]["ativo"] is False

    def test_excluir_indisponivel(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = ConfigEnvioFolhaPontoService()
        service._disponivel = False
        assert service.excluir("x") is False

    def test_reativar(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        mock_pool_e_db["colecao"].update_one.return_value = MagicMock(modified_count=1)
        assert service.reativar("507f1f77bcf86cd799439011") is True
        op = mock_pool_e_db["colecao"].update_one.call_args[0][1]
        assert op["$set"]["excluida"] is False
        assert op["$set"]["ativo"] is True

    def test_reativar_indisponivel(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = ConfigEnvioFolhaPontoService()
        service._disponivel = False
        assert service.reativar("x") is False


# ==================== Consultas ====================

class TestConsultas:
    def test_buscar_por_nome_parcial(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        doc = {"_id": ObjectId(), "nome": "João"}
        mock_pool_e_db["colecao"].find.return_value = create_mock_cursor([doc])
        out = service.buscar_por_nome("joao")
        assert out == [doc]
        filtro = mock_pool_e_db["colecao"].find.call_args[0][0]
        assert "nome_normalizado" in filtro

    def test_buscar_por_nome_exato(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        mock_pool_e_db["colecao"].find.return_value = create_mock_cursor([])
        service.buscar_por_nome("JOÃO DA SILVA", exato=True)
        filtro = mock_pool_e_db["colecao"].find.call_args[0][0]
        assert filtro["nome_normalizado"] == "joao da silva"

    def test_buscar_por_identificador(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        doc = {"_id": ObjectId(), "identificador": "1"}
        mock_pool_e_db["colecao"].find_one.return_value = doc
        assert service.buscar_por_identificador("1") == doc
        filtro = mock_pool_e_db["colecao"].find_one.call_args[0][0]
        assert filtro["identificador"] == "1"

    def test_buscar_por_empresa(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        mock_pool_e_db["colecao"].find.return_value = create_mock_cursor([])
        service.buscar_por_empresa("MS Servicos")
        filtro = mock_pool_e_db["colecao"].find.call_args[0][0]
        assert filtro["excluida"] is False
        assert filtro["ativo"] is True

    def test_buscar_por_local(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        mock_pool_e_db["colecao"].find.return_value = create_mock_cursor([])
        service.buscar_por_local("DSEI")
        filtro = mock_pool_e_db["colecao"].find.call_args[0][0]
        assert filtro["excluida"] is False
        assert "local_contrato_polo" in filtro


class TestListarParaEnvio:
    def test_monta_contatos(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        doc = make_config_dados()
        doc["_id"] = ObjectId()
        mock_pool_e_db["colecao"].find.return_value = create_mock_cursor([doc])

        with patch("src.services.config_envio_folha_ponto_service.planilha_contatos_service") as planilha_mock:
            planilha_mock.montar_diretorio_completo.return_value = "/tmp/folhas"
            planilha_mock.listar_arquivos_pdf.return_value = ["/tmp/folhas/a.pdf"]
            out = service.listar_ativos_para_envio(1, 2025)

        assert len(out) == 1
        c = out[0]
        assert c["id"] == "1"
        assert c["nome"] == "João da Silva"
        assert c["diretorio_completo"] == "/tmp/folhas"
        assert c["arquivos_pdf"] == ["/tmp/folhas/a.pdf"]
        assert c["enviar_email"] is True
        assert c["enviar_whatsapp"] is False
        assert c["enviar_grupo_whatsapp"] is True
        assert c["mes_referencia"] == 1
        assert c["ano_referencia"] == 2025

    def test_indisponivel(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = ConfigEnvioFolhaPontoService()
        service._disponivel = False
        assert service.listar_ativos_para_envio(1, 2025) == []


# ==================== Validação e Contagem ====================

class TestValidacao:
    def test_valida_ok(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        doc = make_config_dados()
        doc["_id"] = ObjectId()
        mock_pool_e_db["colecao"].find.return_value = create_mock_cursor([doc])
        resultado = service.validar()
        assert resultado["valida"] is True
        assert resultado["total_configs"] == 1

    def test_valida_problemas(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        doc = make_config_dados(emails=[], enviar_email="S")
        doc["_id"] = ObjectId()
        mock_pool_e_db["colecao"].find.return_value = create_mock_cursor([doc])
        resultado = service.validar()
        assert resultado["valida"] is False
        assert any("EMAIL" in p for p in resultado["problemas"])

    def test_valida_indisponivel(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = ConfigEnvioFolhaPontoService()
        service._disponivel = False
        assert service.validar()["valida"] is False


class TestContar:
    def test_contar(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        mock_pool_e_db["colecao"].count_documents.side_effect = [5, 3, 2]
        resultado = service.contar()
        assert resultado["total"] == 5
        assert resultado["ativas"] == 3
        assert resultado["inativas"] == 2
        assert resultado["excluidas"] == 2

    def test_contar_indisponivel(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = ConfigEnvioFolhaPontoService()
        service._disponivel = False
        assert service.contar() == {}


# ==================== Importação da Planilha ====================

def make_contato_planilha(**kwargs):
    c = {
        "id": "1",
        "nome": "João da Silva",
        "empresa": "MS Servicos",
        "local_contrato_polo": "DSEI AMAPÁ",
        "diretorio_geral": "Z:\\04. PESSOAL\\FOLHA PONTO",
        "diretorio_especifico": "01. MS SERVIÇOS\\ADMINISTRATIVO",
        "emails": ["joao@x.com"],
        "telefones": ["96999999999"],
        "grupos_whatsapp": ["Administrativo"],
        "enviar_email": True,
        "enviar_whatsapp": False,
        "enviar_grupo_whatsapp": True,
        "enviar_impresso": False,
    }
    c.update(kwargs)
    return c


class TestImportarDaPlanilha:
    def test_importar_cria_configs(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        # Sem config existente com esse identificador
        mock_pool_e_db["colecao"].find_one.return_value = None
        mock_pool_e_db["colecao"].insert_one.return_value = MagicMock(inserted_id=ObjectId())

        with patch("src.services.config_envio_folha_ponto_service.PlanilhaContatosService") as planilha_cls:
            inst = MagicMock()
            inst.carregar.return_value = True
            inst.iterar_contatos.return_value = iter([make_contato_planilha()])
            planilha_cls.return_value = inst

            resumo = service.importar_da_planilha(planilha_path="/fake.xlsx")

        assert resumo["criados"] == 1
        assert resumo["erros"] == 0
        doc = mock_pool_e_db["colecao"].insert_one.call_args[0][0]
        assert doc["identificador"] == "1"
        assert doc["enviar_email"] == "S"
        assert doc["enviar_grupo_whatsapp"] == "S"

    def test_importar_sem_sobrescrever_pula(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        existente = make_config_dados()
        existente["_id"] = ObjectId()
        mock_pool_e_db["colecao"].find_one.return_value = existente

        with patch("src.services.config_envio_folha_ponto_service.PlanilhaContatosService") as planilha_cls:
            inst = MagicMock()
            inst.carregar.return_value = True
            inst.iterar_contatos.return_value = iter([make_contato_planilha()])
            planilha_cls.return_value = inst

            resumo = service.importar_da_planilha(planilha_path="/fake.xlsx")

        assert resumo["pulados"] == 1
        assert resumo["criados"] == 0
        mock_pool_e_db["colecao"].insert_one.assert_not_called()

    def test_importar_sobrescrever_atualiza(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        existente = make_config_dados()
        existente["_id"] = ObjectId()
        mock_pool_e_db["colecao"].find_one.return_value = existente
        mock_pool_e_db["colecao"].update_one.return_value = MagicMock(modified_count=1)

        # mock do atualizar_com_historico (HistoricoMixin)
        with patch.object(service, "atualizar_com_historico", return_value=True) as mock_upd:
            with patch("src.services.config_envio_folha_ponto_service.PlanilhaContatosService") as planilha_cls:
                inst = MagicMock()
                inst.carregar.return_value = True
                inst.iterar_contatos.return_value = iter([make_contato_planilha()])
                planilha_cls.return_value = inst

                resumo = service.importar_da_planilha(planilha_path="/fake.xlsx", sobrescrever=True)

        assert resumo["atualizados"] == 1
        assert resumo["criados"] == 0
        mock_upd.assert_called_once()

    def test_importar_falha_planilha(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        with patch("src.services.config_envio_folha_ponto_service.PlanilhaContatosService") as planilha_cls:
            inst = MagicMock()
            inst.carregar.return_value = False
            planilha_cls.return_value = inst
            resumo = service.importar_da_planilha(planilha_path="/fake.xlsx")
        assert resumo["erros"] >= 1
        assert resumo["criados"] == 0

    def test_importar_indisponivel(self, monkeypatch):
        monkeypatch.setattr("dotenv.get_key", lambda *a, **k: "mongodb://localhost")
        service = ConfigEnvioFolhaPontoService()
        service._disponivel = False
        resumo = service.importar_da_planilha()
        assert resumo["erros"] >= 1

    def test_importar_marcar_removidos(self, mock_pool_e_db, monkeypatch):
        service = make_service(mock_pool_e_db, monkeypatch)
        # Nenhum existente pelo identificador da planilha, mas existe config órfã
        mock_pool_e_db["colecao"].find_one.return_value = None
        mock_pool_e_db["colecao"].insert_one.return_value = MagicMock(inserted_id=ObjectId())
        orfa = make_config_dados(identificador="999")  # não está na planilha
        orfa["_id"] = ObjectId()
        mock_pool_e_db["colecao"].find.return_value = create_mock_cursor([orfa])
        mock_pool_e_db["colecao"].update_one.return_value = MagicMock(modified_count=1)

        with patch("src.services.config_envio_folha_ponto_service.PlanilhaContatosService") as planilha_cls:
            inst = MagicMock()
            inst.carregar.return_value = True
            inst.iterar_contatos.return_value = iter([make_contato_planilha()])
            planilha_cls.return_value = inst

            resumo = service.importar_da_planilha(planilha_path="/fake.xlsx", marcar_removidos=True)

        assert resumo.get("removidos") == 1
