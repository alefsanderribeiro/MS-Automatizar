"""MongoDB-specific test fixtures for services."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from bson import ObjectId
from typing import List, Dict, Any


# ==================== Aggregation Result Factory ====================

@pytest.fixture
def mock_aggregation_result():
    """
    Factory for creating mock aggregation results.

    Usage:
        def test_example(mock_aggregation_result):
            pipeline = [{"$match": {"status": "ativo"}}]
            results = [{"_id": ObjectId(), "nome": "João"}]
            cursor = mock_aggregation_result(pipeline, results)
    """
    def _create_result(pipeline: List[Dict[str, Any]], results: List[Dict[str, Any]]):
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=results)
        cursor.__aiter__ = MagicMock(return_value=iter(results))
        return cursor
    return _create_result


# ==================== Service Fixtures with Mocked Dependencies ====================

@pytest.fixture
def funcionario_service_with_mock(mock_collection, mock_redis):
    """
    FuncionarioService with injected mocks.

    Returns:
        Tuple of (service, mock_collection, mock_redis)
    """
    from src.services.funcionario_service import FuncionarioService

    # Create service instance
    service = FuncionarioService()

    # Inject mocks
    service.collection = mock_collection

    # Mock MongoDB connection getter
    original_get_db = service._get_database
    async def mock_get_db():
        db = MagicMock()
        db["funcionarios"] = mock_collection
        return db
    service._get_database = mock_get_db

    return service, mock_collection, mock_redis


@pytest.fixture
def empresa_service_with_mock(mock_collection, mock_redis):
    """
    EmpresaService with injected mocks.

    Returns:
        Tuple of (service, mock_collection, mock_redis)
    """
    from src.services.empresa_service import EmpresaService

    # Create service instance
    service = EmpresaService()

    # Inject mocks
    service.collection = mock_collection

    # Mock MongoDB connection getter
    original_get_db = service._get_database
    async def mock_get_db():
        db = MagicMock()
        db["empresas"] = mock_collection
        return db
    service._get_database = mock_get_db

    return service, mock_collection, mock_redis


@pytest.fixture
def folha_ponto_service_with_mock(mock_collection, mock_redis):
    """
    FolhaPontoService with injected mocks.

    Returns:
        Tuple of (service, mock_collection, mock_redis)
    """
    from src.services.folha_ponto_service import FolhaPontoService

    # Create service instance
    service = FolhaPontoService()

    # Inject mocks
    service.collection = mock_collection

    # Mock MongoDB connection getter
    async def mock_get_db():
        db = MagicMock()
        db["folhas_ponto"] = mock_collection
        return db
    service._get_database = mock_get_db

    return service, mock_collection, mock_redis


# ==================== MongoDB Document Factories ====================

@pytest.fixture
def funcionario_document_factory():
    """
    Factory for creating funcionario documents with variations.

    Usage:
        def test_example(funcionario_document_factory):
            func = funcionario_document_factory(nome="João", status="ativo")
    """
    def _create_funcionario(
        _id: ObjectId = None,
        nome: str = "Funcionário Teste",
        status: str = "ativo",
        status_cadastro: str = "completo",
        **kwargs
    ) -> Dict[str, Any]:
        from datetime import datetime, date, timezone

        doc = {
            "_id": _id or ObjectId(),
            "nome": nome,
            "pis": kwargs.get("pis", "12345678901"),
            "cpf": kwargs.get("cpf", "123.456.789-00"),
            "lotacao": kwargs.get("lotacao", "TI"),
            "contrato": kwargs.get("contrato", "CLT"),
            "status": status,
            "status_cadastro": status_cadastro,
            "nome_normalizado": nome.lower(),
            "empresas_ids": kwargs.get("empresas_ids", []),
            "criado_em": datetime.now(timezone.utc),
            "atualizado_em": datetime.now(timezone.utc),
            "versao": 1,
            "historico_alteracoes": []
        }

        # Add optional fields
        if status_cadastro == "completo":
            doc.update({
                "contrato_empresa_id": kwargs.get("contrato_empresa_id", ObjectId()),
                "horario_id": kwargs.get("horario_id", ObjectId()),
                "funcao_id": kwargs.get("funcao_id", ObjectId()),
            })

        return doc

    return _create_funcionario


@pytest.fixture
def empresa_document_factory():
    """
    Factory for creating empresa documents with variations.

    Usage:
        def test_example(empresa_document_factory):
            emp = empresa_document_factory(nome="Teste Corp", status="ativa")
    """
    def _create_empresa(
        _id: ObjectId = None,
        nome: str = "Empresa Teste",
        status: str = "ativa",
        incompleto: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        from datetime import datetime, timezone

        doc = {
            "_id": _id or ObjectId(),
            "nome": nome,
            "cnpj": kwargs.get("cnpj"),
            "atividade": kwargs.get("atividade"),
            "endereco": kwargs.get("endereco"),
            "telefone": kwargs.get("telefone"),
            "email": kwargs.get("email"),
            "responsavel": kwargs.get("responsavel"),
            "status": status,
            "incompleto": incompleto,
            "nome_normalizado": nome.lower(),
            "nome_sigla": kwargs.get("nome_sigla"),
            "nome_simplificado": kwargs.get("nome_simplificado"),
            "criado_em": datetime.now(timezone.utc),
            "atualizado_em": datetime.now(timezone.utc),
            "versao": 1,
            "historico_alteracoes": []
        }

        return doc

    return _create_empresa


@pytest.fixture
def folha_ponto_document_factory():
    """
    Factory for creating folha de ponto documents.

    Usage:
        def test_example(folha_ponto_document_factory):
            folha = folha_ponto_document_factory(
                funcionario_id=ObjectId(),
                mes_referencia="2025-01"
            )
    """
    def _create_folha(
        _id: ObjectId = None,
        funcionario_id: ObjectId = None,
        empresa_id: ObjectId = None,
        mes_referencia: str = "2025-01",
        **kwargs
    ) -> Dict[str, Any]:
        from datetime import datetime, date, timezone

        doc = {
            "_id": _id or ObjectId(),
            "funcionario_id": funcionario_id or ObjectId(),
            "empresa_id": empresa_id or ObjectId(),
            "mes_referencia": mes_referencia,
            "folha_data": {
                "mes_referencia": mes_referencia,
                "data_inicio": date(2025, 1, 1),
                "data_fim": date(2025, 1, 31),
                "dias": kwargs.get("dias", []),
                "total_horas_mes": kwargs.get("total_horas_mes"),
                "total_faltas": kwargs.get("total_faltas", 0),
                "total_feriados": kwargs.get("total_feriados", 0),
                "total_finais_semana": kwargs.get("total_finais_semana", 8),
                "analise_ia": kwargs.get("analise_ia"),
                "preenchimento_concluido": kwargs.get("preenchimento_concluido", False),
                "analise_ia_concluida": kwargs.get("analise_ia_concluida", False)
            },
            "caminho_arquivo_gerado": kwargs.get("caminho_arquivo_gerado"),
            "caminho_arquivo_analisado": kwargs.get("caminho_arquivo_analisado"),
            "data_criacao": datetime.now(timezone.utc),
            "data_atualizacao": datetime.now(timezone.utc),
            "status": kwargs.get("status", "criada"),
            "versao": 1,
            "historico_alteracoes": []
        }

        return doc

    return _create_folha
