"""Pytest configuration and shared fixtures."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from bson import ObjectId
from datetime import datetime, date, timezone, timedelta
from typing import List, Dict, Any
import os

# Register pytest plugins for specialized fixtures
pytest_plugins = [
    "tests.fixtures.mongodb_fixtures",
    "tests.fixtures.redis_fixtures",
    "tests.fixtures.model_fixtures",
    "tests.fixtures.gemini_fixtures",
    "tests.fixtures.file_fixtures",
]


# ==================== ObjectId Fixtures ====================

@pytest.fixture
def sample_object_id() -> ObjectId:
    """Returns a valid ObjectId for testing."""
    return ObjectId("507f1f77bcf86cd799439011")


@pytest.fixture
def sample_object_ids() -> callable:
    """
    Factory fixture that returns a list of valid ObjectIds.

    Usage:
        def test_example(sample_object_ids):
            ids = sample_object_ids(5)  # Get 5 ObjectIds
    """
    def _generate_ids(count: int = 3) -> List[ObjectId]:
        return [ObjectId() for _ in range(count)]
    return _generate_ids


# ==================== MongoDB Mocks ====================

def mock_cursor(results: List[Dict[str, Any]]):
    """
    Factory for creating mock MongoDB cursors with chainable methods.

    Args:
        results: List of documents to return when iterating

    Returns:
        Mock cursor with sort, skip, limit chaining support
    """
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=results)
    cursor.__aiter__ = MagicMock(return_value=iter(results))
    return cursor


@pytest.fixture
def mock_collection():
    """
    Mock MongoDB collection with standard CRUD operations.

    Returns:
        Mock collection with find_one, find, insert_one, update_one, delete_one, aggregate
    """
    collection = MagicMock()
    collection.find_one = AsyncMock(return_value=None)
    collection.find = MagicMock(return_value=mock_cursor([]))
    collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1, matched_count=1))
    collection.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
    collection.aggregate = MagicMock(return_value=mock_cursor([]))
    collection.count_documents = AsyncMock(return_value=0)
    return collection


@pytest.fixture
def mock_database(mock_collection):
    """
    Mock MongoDB database with collection access.

    Returns:
        Mock database that returns mock_collection for any collection name
    """
    database = MagicMock()
    database.__getitem__ = MagicMock(return_value=mock_collection)
    return database


@pytest.fixture
def mock_mongo_client(mock_database):
    """
    Mock Motor (async MongoDB) client.

    Returns:
        Mock client that returns mock_database for any database name
    """
    client = MagicMock()
    client.__getitem__ = MagicMock(return_value=mock_database)
    return client


# ==================== Redis Mocks ====================

@pytest.fixture
def mock_redis():
    """
    Mock Redis client with standard operations.

    Returns:
        Mock Redis with get, set, delete, keys, scan_iter methods
    """
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.keys = AsyncMock(return_value=[])
    redis.scan_iter = AsyncMock(return_value=iter([]))
    redis.exists = AsyncMock(return_value=0)
    redis.expire = AsyncMock(return_value=True)
    redis.ping = AsyncMock(return_value=True)
    return redis


# ==================== Environment Mocks ====================

@pytest.fixture
def mock_env_vars(monkeypatch):
    """
    Mock environment variables for testing.

    Usage:
        def test_example(mock_env_vars):
            mock_env_vars({
                "MONGO_URI": "mongodb://localhost:27017",
                "REDIS_ENABLED": "true"
            })
    """
    def _set_env_vars(env_dict: Dict[str, str]):
        for key, value in env_dict.items():
            monkeypatch.setenv(key, value)

    # Set default test environment variables
    default_env = {
        "MONGO_URI": "mongodb://localhost:27017test_db",
        "REDIS_ENABLED": "false",
        "GEMINI_API_KEY": "test_api_key_12345",
        "ENV": "test",
        "LOG_LEVEL": "DEBUG"
    }
    _set_env_vars(default_env)

    return _set_env_vars


# ==================== Pydantic Model Fixtures ====================

@pytest.fixture
def funcionario_dict(sample_object_id) -> Dict[str, Any]:
    """
    Sample funcionario data as dictionary.

    Returns:
        Complete funcionario dictionary with all required fields
    """
    return {
        "nome": "João Silva",
        "pis": "12345678901",
        "cpf": "123.456.789-00",
        "lotacao": "TI",
        "contrato": "CLT",
        "contrato_empresa_id": sample_object_id,
        "horario_id": sample_object_id,
        "funcao_id": sample_object_id,
        "diretorio_id": sample_object_id,
        "empresas_ids": [sample_object_id],
        "data_nascimento": date(1990, 1, 15),
        "data_admissao": date(2020, 1, 15),
        "status": "ativo",
        "status_cadastro": "completo",
        "nome_normalizado": "joao silva",
        "criado_em": datetime.now(timezone.utc),
        "atualizado_em": datetime.now(timezone.utc),
        "versao": 1,
        "historico_alteracoes": []
    }


@pytest.fixture
def funcionario_incompleto_dict() -> Dict[str, Any]:
    """
    Sample funcionario data for incomplete registration (autocreate scenario).

    Returns:
        Minimal funcionario dictionary with only required fields
    """
    return {
        "nome": "Maria Santos",
        "pis": "98765432109",
        "cpf": "987.654.321-00",
        "status": "ativo",
        "status_cadastro": "incompleto",
        "nome_normalizado": "maria santos",
        "criado_em": datetime.now(timezone.utc),
        "atualizado_em": datetime.now(timezone.utc),
        "versao": 1,
        "historico_alteracoes": [],
        "empresas_ids": []
    }


@pytest.fixture
def empresa_dict(sample_object_id) -> Dict[str, Any]:
    """
    Sample empresa data as dictionary.

    Returns:
        Complete empresa dictionary
    """
    return {
        "nome": "Solucoes Dinamicas Consultoria",
        "cnpj": "12.345.678/0001-90",
        "atividade": "Consultoria em TI",
        "endereco": "Rua A, 123 - São Paulo, SP",
        "telefone": "(11) 9999-9999",
        "email": "contato@solucoesdinamicas.com.br",
        "responsavel": "João Pereira",
        "status": "ativa",
        "incompleto": False,
        "nome_normalizado": "solucoes dinamicas consultoria",
        "nome_sigla": "M&S",
        "nome_simplificado": "Solucoes Dinamicas",
        "criado_em": datetime.now(timezone.utc),
        "atualizado_em": datetime.now(timezone.utc),
        "versao": 1,
        "historico_alteracoes": []
    }


@pytest.fixture
def empresa_incompleta_dict() -> Dict[str, Any]:
    """
    Sample empresa data for incomplete registration.

    Returns:
        Minimal empresa dictionary (autocreate scenario)
    """
    return {
        "nome": "Empresa Teste Ltda",
        "status": "em_construcao",
        "incompleto": True,
        "nome_normalizado": "empresa teste ltda",
        "criado_em": datetime.now(timezone.utc),
        "atualizado_em": datetime.now(timezone.utc),
        "versao": 1,
        "historico_alteracoes": []
    }


@pytest.fixture
def folha_ponto_dict(sample_object_id) -> Dict[str, Any]:
    """
    Sample folha de ponto data as dictionary.

    Returns:
        Complete folha de ponto dictionary with sample dias
    """
    return {
        "funcionario_id": sample_object_id,
        "empresa_id": sample_object_id,
        "mes_referencia": "2025-01",
        "folha_data": {
            "mes_referencia": "2025-01",
            "data_inicio": date(2025, 1, 1),
            "data_fim": date(2025, 1, 31),
            "dias": [
                {
                    "numero_dia": 1,
                    "data": datetime(2025, 1, 1),
                    "dia_semana": "Quarta",
                    "hora_entrada": "08:00",
                    "hora_intervalo_inicio": "12:00",
                    "hora_intervalo_fim": "13:00",
                    "hora_saida": "17:00",
                    "total_horas_trabalhadas": "08:00",
                    "observacoes": None,
                    "tipo_dia": "NORMAL",
                    "preenchido_manualmente": True,
                    "analise_ia_processada": False
                }
            ],
            "total_horas_mes": "160:00",
            "total_faltas": 0,
            "total_feriados": 2,
            "total_finais_semana": 8,
            "analise_ia": None,
            "preenchimento_concluido": True,
            "analise_ia_concluida": False
        },
        "caminho_arquivo_gerado": r"C:\output\folha_2025_01.pdf",
        "caminho_arquivo_analisado": None,
        "data_criacao": datetime.now(timezone.utc),
        "data_atualizacao": datetime.now(timezone.utc),
        "status": "preenchida",
        "versao": 1,
        "historico_alteracoes": []
    }


# ==================== Temporary File Fixtures ====================

@pytest.fixture
def temp_directory(tmp_path):
    """
    Temporary directory fixture for file operations.

    Returns:
        Path to temporary directory (auto-cleanup)
    """
    return tmp_path


@pytest.fixture
def temp_pdf_file(temp_directory):
    """
    Creates a temporary PDF file for testing.

    Returns:
        Path to temporary PDF file
    """
    pdf_path = temp_directory / "test_file.pdf"
    # Create minimal valid PDF
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")
    return pdf_path
