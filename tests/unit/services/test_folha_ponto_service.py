"""
Unit tests for FolhaDePontoService

Comprehensive tests covering:
- Initialization and MongoDB connection
- Buscar folha existente
- Salvar ou atualizar (insert, update, duplicidade)
- Listar por funcionário
- Buscar por período
- Buscar por empresa
- Buscar por status
- Obter estatísticas
- Deletar folha
- Listar todos com paginação
- MongoDB indisponível

Target coverage: 50% (~342 lines of 683)
"""

import pytest
from unittest.mock import MagicMock, patch
from bson import ObjectId
from datetime import datetime, date, timezone
from typing import Dict, Any, List
from src.services.folha_ponto_service import FolhaDePontoService


# ==================== Test Constants ====================

SAMPLE_OBJECT_ID = ObjectId("507f1f77bcf86cd799439011")
SAMPLE_OBJECT_ID_2 = ObjectId("507f1f77bcf86cd799439012")
SAMPLE_OBJECT_ID_3 = ObjectId("507f1f77bcf86cd799439013")


# ==================== Helper Functions ====================

def create_mock_cursor(results: List[Dict[str, Any]]):
    """Create a mock MongoDB cursor with chainable methods."""
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.__iter__ = MagicMock(return_value=iter(results))
    cursor.__list__ = results
    return cursor


def create_folha_doc(
    funcionario_id: str = None,
    empresa_id: str = None,
    mes_referencia: str = "2025-01",
    status: str = "preenchida",
    lotacao: str = "TI",
    funcao: str = "Analista",
    **kwargs
) -> Dict[str, Any]:
    """Factory for creating folha de ponto documents."""
    doc = {
        "_id": ObjectId(),
        "funcionario_id": funcionario_id or str(SAMPLE_OBJECT_ID),
        "empresa_id": empresa_id or str(SAMPLE_OBJECT_ID_2),
        "mes_referencia": mes_referencia,
        "lotacao": lotacao,
        "funcao": funcao,
        "status": status,
        "data_criacao": datetime.now(timezone.utc),
        "data_atualizacao": datetime.now(timezone.utc),
        "folha_data": {
            "mes_referencia": mes_referencia,
            "dias": [],
            "funcionario": {"nome": "Test User"},
            "empresa": {"nome": "Test Company"}
        },
        "versao": 1,
        "historico_alteracoes": []
    }
    doc.update(kwargs)
    return doc


# ==================== Fixtures ====================

@pytest.fixture
def mock_mongo_client():
    """Mock do Singleton MongoDBConnectionPool e da flag de disponibilidade."""
    
    # 1. Criamos os mocks para o Cliente e o Banco
    mock_db = MagicMock()
    mock_client = MagicMock()
    
    # Configura o comportamento do 'admin.command' para o teste de init passar
    mock_client.admin.command.return_value = {'ok': 1}
    
    # 2. Criamos o Mock para a classe Singleton em si
    mock_pool_instance = MagicMock()
    mock_pool_instance.get_database.return_value = mock_db
    mock_pool_instance.get_client.return_value = mock_client
    mock_pool_instance.disponivel = True
    
    # 3. Aplicamos os patches nos lugares certos
    # Patch 1: Força a flag de disponibilidade no serviço de empresas
    # Patch 2: Intercepta a classe Singleton no serviço de empresas
    # Patch 3: Intercepta a flag no arquivo de conexão (opcional, mas recomendado)
    with patch('src.services.funcionario_service.MONGODB_DISPONIVEL', True), \
         patch('src.services.funcionario_service.MongoDBConnectionPool') as mock_class:
        
        # Faz com que qualquer chamada a MongoDBConnectionPool() retorne nossa instância mockada
        mock_class.return_value = mock_pool_instance
        
        yield mock_pool_instance




@pytest.fixture
def mock_colecao():
    """Mock MongoDB collection with all operations."""
    colecao = MagicMock()
    colecao.find_one = MagicMock(return_value=None)
    colecao.find = MagicMock(return_value=create_mock_cursor([]))
    colecao.insert_one = MagicMock(return_value=MagicMock(inserted_id=ObjectId()))
    colecao.update_one = MagicMock(return_value=MagicMock(modified_count=1, matched_count=1))
    colecao.replace_one = MagicMock(return_value=MagicMock(modified_count=1))
    colecao.delete_one = MagicMock(return_value=MagicMock(deleted_count=1))
    colecao.aggregate = MagicMock(return_value=iter([]))
    colecao.count_documents = MagicMock(return_value=0)
    colecao.create_index = MagicMock()
    colecao.drop_index = MagicMock()
    return colecao


@pytest.fixture
def mock_db(mock_colecao):
    """Mock MongoDB database."""
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=mock_colecao)
    db["folha_de_ponto"] = mock_colecao
    db["funcionarios"] = MagicMock()
    db["funcoes"] = MagicMock()
    return db


@pytest.fixture
def folha_service_mock(mock_mongo_client, mock_db, mock_colecao, mocker):
    """Create FolhaDePontoService with mocked dependencies."""
    # Mock dotenv to return test values
    mocker.patch("dotenv.get_key", side_effect=lambda path, key: {
        "MONGO_URI": "mongodb://localhost:27017",
        "MONGO_DATABASE_NAME": "test_db"
    }.get(key))


    # Import after mocking
    from src.services.folha_ponto_service import FolhaDePontoService

    service = FolhaDePontoService()
    service.db = mock_db
    service.colecao = mock_colecao
    service._disponivel = True

    return service


# ==================== Test Classes ====================

@pytest.mark.unit
class TestFolhaDePontoServiceInit:
    """Tests for FolhaDePontoService initialization."""

    def test_init_success(self, mocker):
        """Test successful MongoDB connection."""
        mock_client = MagicMock()
        mock_client.admin.command = MagicMock(return_value={"ismaster": True})

        mocker.patch("dotenv.get_key", side_effect=lambda path, key: {
            "MONGO_URI": "mongodb://localhost:27017",
            "MONGO_DATABASE_NAME": "test_db"
        }.get(key))


        from src.services.folha_ponto_service import FolhaDePontoService

        service = FolhaDePontoService()

        assert service.disponivel is True
        assert service.db is not None


    def test_disponivel_property(self, folha_service_mock):
        """Test disponivel property returns correct value."""
        assert folha_service_mock.disponivel is True

        folha_service_mock._disponivel = False
        assert folha_service_mock.disponivel is False


@pytest.mark.unit
class TestBuscarFolhaExistente:
    """Tests for buscar_folha_existente method."""

    def test_buscar_folha_existente_found(self, folha_service_mock, mock_colecao):
        """Test buscar_folha_existente returns folha when found."""
        expected_doc = create_folha_doc(
            funcionario_id="func123",
            empresa_id="emp456",
            mes_referencia="2025-01"
        )
        mock_colecao.find_one.return_value = expected_doc

        result = folha_service_mock.buscar_folha_existente(
            funcionario_id="func123",
            empresa_id="emp456",
            mes_referencia="2025-01"
        )

        assert result is not None
        assert result["funcionario_id"] == "func123"
        assert "_id" not in result  # Should be removed

    def test_buscar_folha_existente_not_found(self, folha_service_mock, mock_colecao):
        """Test buscar_folha_existente returns None when not found."""
        mock_colecao.find_one.return_value = None

        result = folha_service_mock.buscar_folha_existente(
            funcionario_id="nonexistent",
            empresa_id="emp456",
            mes_referencia="2025-01"
        )

        assert result is None

    def test_buscar_folha_existente_not_available(self, folha_service_mock):
        """Test buscar_folha_existente when service not available."""
        folha_service_mock._disponivel = False

        result = folha_service_mock.buscar_folha_existente(
            funcionario_id="func123",
            empresa_id="emp456",
            mes_referencia="2025-01"
        )

        assert result is None


@pytest.mark.unit
class TestSalvarOuAtualizar:
    """Tests for salvar_ou_atualizar method."""

    def test_salvar_ou_atualizar_insert_success(self, folha_service_mock, mock_colecao, mock_db):
        """Test salvar_ou_atualizar inserts new folha."""
        from src.services.folha_ponto_service import ResultadoSalvamento

        folha_data = create_folha_doc(
            funcionario_id=str(SAMPLE_OBJECT_ID),
            empresa_id=str(SAMPLE_OBJECT_ID_2)
        )

        # No existing folha
        mock_colecao.find_one.return_value = None

        # Mock funcionario lookup
        mock_funcionarios = MagicMock()
        mock_funcionarios.find_one.return_value = {
            "_id": SAMPLE_OBJECT_ID,
            "lotacao": "TI",
            "funcao_id": SAMPLE_OBJECT_ID_3
        }

        # Mock funcao lookup
        mock_funcoes = MagicMock()
        mock_funcoes.find_one.return_value = {
            "_id": SAMPLE_OBJECT_ID_3,
            "nome": "Analista"
        }

        mock_db["funcionarios"] = mock_funcionarios
        mock_db["funcoes"] = mock_funcoes

        inserted_id = ObjectId()
        mock_colecao.insert_one.return_value = MagicMock(inserted_id=inserted_id)

        # CORREÇÃO: Desempacotando os 3 valores de retorno
        status, folha_existente, id_salvo = folha_service_mock.salvar_ou_atualizar(folha_data)

        assert status == ResultadoSalvamento.SUCESSO_INSERIDO
        assert folha_existente is None
        assert id_salvo == inserted_id
        mock_colecao.insert_one.assert_called_once()

    def test_salvar_ou_atualizar_duplicidade_detected(self, folha_service_mock, mock_colecao, mock_db):
        """Test salvar_ou_atualizar detects duplicidade."""
        from src.services.folha_ponto_service import ResultadoSalvamento

        folha_data = create_folha_doc(
            funcionario_id=str(SAMPLE_OBJECT_ID),
            empresa_id=str(SAMPLE_OBJECT_ID_2),
            mes_referencia="2025-01"
        )

        existing_doc = create_folha_doc(
            funcionario_id=str(SAMPLE_OBJECT_ID),
            empresa_id=str(SAMPLE_OBJECT_ID_2),
            mes_referencia="2025-01",
            lotacao="TI",
            funcao="Analista"
        )
        existing_doc["_id"] = ObjectId()

        mock_funcionarios = MagicMock()
        mock_funcionarios.find_one.return_value = {
            "_id": SAMPLE_OBJECT_ID,
            "lotacao": "TI",
            "funcao_id": SAMPLE_OBJECT_ID_3
        }

        mock_funcoes = MagicMock()
        mock_funcoes.find_one.return_value = {"_id": SAMPLE_OBJECT_ID_3, "nome": "Analista"}

        mock_db["funcionarios"] = mock_funcionarios
        mock_db["funcoes"] = mock_funcoes
        mock_colecao.find_one.return_value = existing_doc

        # CORREÇÃO: Desempacotando os 3 valores
        status, folha_ret, id_retornado = folha_service_mock.salvar_ou_atualizar(
            folha_data,
            forcar_sobrescrita=False
        )

        assert status == ResultadoSalvamento.DUPLICIDADE
        assert folha_ret == existing_doc
        assert id_retornado == existing_doc["_id"]

    def test_salvar_ou_atualizar_forcar_sobrescrita(self, folha_service_mock, mock_colecao, mock_db):
        """Test salvar_ou_atualizar with forcar_sobrescrita=True."""
        from src.services.folha_ponto_service import ResultadoSalvamento

        folha_data = create_folha_doc(
            funcionario_id=str(SAMPLE_OBJECT_ID),
            empresa_id=str(SAMPLE_OBJECT_ID_2),
            mes_referencia="2025-01"
        )

        existing_id = ObjectId()
        existing_doc = create_folha_doc()
        existing_doc["_id"] = existing_id

        mock_funcionarios = MagicMock()
        mock_funcionarios.find_one.return_value = {"_id": SAMPLE_OBJECT_ID, "lotacao": "TI", "funcao_id": SAMPLE_OBJECT_ID_3}
        mock_funcoes = MagicMock()
        mock_funcoes.find_one.return_value = {"_id": SAMPLE_OBJECT_ID_3, "nome": "Analista"}

        mock_db["funcionarios"] = mock_funcionarios
        mock_db["funcoes"] = mock_funcoes

        mock_colecao.find_one.return_value = existing_doc
        mock_colecao.replace_one.return_value = MagicMock(modified_count=1)

        # CORREÇÃO: Desempacotando os 3 valores
        status, folha_existente, id_retornado = folha_service_mock.salvar_ou_atualizar(
            folha_data,
            forcar_sobrescrita=True
        )

        assert status == ResultadoSalvamento.SUCESSO_ATUALIZADO
        assert id_retornado == existing_id
        mock_colecao.replace_one.assert_called_once()

    def test_salvar_ou_atualizar_sobrescrita_inalterado(self, folha_service_mock, mock_colecao, mock_db):
        """Test salvar_ou_atualizar with sobrescrita but no changes."""
        from src.services.folha_ponto_service import ResultadoSalvamento

        folha_data = create_folha_doc()
        existing_id = ObjectId()
        existing_doc = {"_id": existing_id}

        mock_funcionarios = MagicMock()
        mock_funcionarios.find_one.return_value = {"_id": SAMPLE_OBJECT_ID, "lotacao": "TI", "funcao_id": SAMPLE_OBJECT_ID_3}
        mock_funcoes = MagicMock()
        mock_funcoes.find_one.return_value = {"_id": SAMPLE_OBJECT_ID_3, "nome": "Analista"}

        mock_db["funcionarios"] = mock_funcionarios
        mock_db["funcoes"] = mock_funcoes

        mock_colecao.find_one.return_value = existing_doc
        mock_colecao.replace_one.return_value = MagicMock(modified_count=0)

        # CORREÇÃO: Ignorando o segundo valor com _
        status, _, id_retornado = folha_service_mock.salvar_ou_atualizar(
            folha_data,
            forcar_sobrescrita=True
        )

        assert status == ResultadoSalvamento.SUCESSO_INALTERADO
        assert id_retornado == existing_id

    def test_salvar_ou_atualizar_not_available(self, folha_service_mock):
        """Test salvar_ou_atualizar when service not available."""
        from src.services.folha_ponto_service import ResultadoSalvamento

        folha_service_mock._disponivel = False

        # CORREÇÃO: Ajuste para receber a tupla
        status, folha_existente, id_retornado = folha_service_mock.salvar_ou_atualizar({"mes_referencia": "2025-01"})

        assert status == ResultadoSalvamento.INDISPONIVEL
        assert folha_existente is None
        assert id_retornado is None

    def test_salvar_ou_atualizar_with_pydantic_model(self, folha_service_mock, mock_colecao, mock_db):
        """Test salvar_ou_atualizar with Pydantic model."""
        from src.services.folha_ponto_service import ResultadoSalvamento

        mock_model = MagicMock()
        folha_dict = create_folha_doc()
        mock_model.dict.return_value = folha_dict

        mock_funcionarios = MagicMock()
        mock_funcionarios.find_one.return_value = {"_id": SAMPLE_OBJECT_ID, "lotacao": "TI", "funcao_id": SAMPLE_OBJECT_ID_3}
        mock_funcoes = MagicMock()
        mock_funcoes.find_one.return_value = {"_id": SAMPLE_OBJECT_ID_3, "nome": "Analista"}

        mock_db["funcionarios"] = mock_funcionarios
        mock_db["funcoes"] = mock_funcoes

        mock_colecao.find_one.return_value = None
        inserted_id = ObjectId()
        mock_colecao.insert_one.return_value = MagicMock(inserted_id=inserted_id)

        # CORREÇÃO: Ajuste para receber a tupla
        status, _, id_retornado = folha_service_mock.salvar_ou_atualizar(mock_model)

        assert status == ResultadoSalvamento.SUCESSO_INSERIDO
        assert id_retornado == inserted_id
        mock_model.dict.assert_called_once()
        
@pytest.mark.unit
class TestListarPorFuncionario:
    """Tests for listar_por_funcionario method."""

    def test_listar_por_funcionario_success(self, folha_service_mock, mock_colecao):
        """Test listar_por_funcionario returns list of folhas."""
        docs = [
            create_folha_doc(funcionario_id=123, mes_referencia="2025-01"),
            create_folha_doc(funcionario_id=123, mes_referencia="2024-12"),
        ]
        cursor = create_mock_cursor(docs)
        mock_colecao.find.return_value = cursor

        result = folha_service_mock.listar_por_funcionario(funcionario_id=123)

        assert len(result) == 2
        cursor.sort.assert_called_with("mes_referencia", -1)

    def test_listar_por_funcionario_empty(self, folha_service_mock, mock_colecao):
        """Test listar_por_funcionario returns empty list when none found."""
        mock_colecao.find.return_value = create_mock_cursor([])

        result = folha_service_mock.listar_por_funcionario(funcionario_id=999)

        assert result == []

    def test_listar_por_funcionario_not_available(self, folha_service_mock):
        """Test listar_por_funcionario when service not available."""
        folha_service_mock._disponivel = False

        result = folha_service_mock.listar_por_funcionario(funcionario_id=123)

        assert result == []


@pytest.mark.unit
class TestBuscarPorPeriodo:
    """Tests for buscar_por_periodo method."""

    def test_buscar_por_periodo_success(self, folha_service_mock, mock_colecao):
        """Test buscar_por_periodo returns folhas in range."""
        docs = [
            create_folha_doc(mes_referencia="2025-01"),
            create_folha_doc(mes_referencia="2025-02"),
            create_folha_doc(mes_referencia="2025-03"),
        ]
        cursor = create_mock_cursor(docs)
        mock_colecao.find.return_value = cursor

        result = folha_service_mock.buscar_por_periodo(
            data_inicio="2025-01",
            data_fim="2025-03"
        )

        assert len(result) == 3

        # Verify filter was correct
        call_args = mock_colecao.find.call_args
        filtro = call_args[0][0]
        assert "$gte" in filtro["mes_referencia"]
        assert "$lte" in filtro["mes_referencia"]

    def test_buscar_por_periodo_empty(self, folha_service_mock, mock_colecao):
        """Test buscar_por_periodo returns empty list."""
        mock_colecao.find.return_value = create_mock_cursor([])

        result = folha_service_mock.buscar_por_periodo(
            data_inicio="2030-01",
            data_fim="2030-12"
        )

        assert result == []

    def test_buscar_por_periodo_not_available(self, folha_service_mock):
        """Test buscar_por_periodo when service not available."""
        folha_service_mock._disponivel = False

        result = folha_service_mock.buscar_por_periodo("2025-01", "2025-12")

        assert result == []


@pytest.mark.unit
class TestBuscarPorEmpresa:
    """Tests for buscar_por_empresa method."""

    def test_buscar_por_empresa_success(self, folha_service_mock, mock_colecao):
        """Test buscar_por_empresa returns folhas."""
        docs = [
            create_folha_doc(),
            create_folha_doc(),
        ]
        cursor = create_mock_cursor(docs)
        mock_colecao.find.return_value = cursor

        result = folha_service_mock.buscar_por_empresa(empresa="Moraes & Santos")

        assert len(result) == 2

    def test_buscar_por_empresa_empty(self, folha_service_mock, mock_colecao):
        """Test buscar_por_empresa returns empty list."""
        mock_colecao.find.return_value = create_mock_cursor([])

        result = folha_service_mock.buscar_por_empresa(empresa="Empresa Inexistente")

        assert result == []

    def test_buscar_por_empresa_not_available(self, folha_service_mock):
        """Test buscar_por_empresa when service not available."""
        folha_service_mock._disponivel = False

        result = folha_service_mock.buscar_por_empresa(empresa="Test")

        assert result == []


@pytest.mark.unit
class TestBuscarPorStatus:
    """Tests for buscar_por_status method."""

    def test_buscar_por_status_success(self, folha_service_mock, mock_colecao):
        """Test buscar_por_status returns folhas with status."""
        docs = [
            create_folha_doc(status="preenchida"),
            create_folha_doc(status="preenchida"),
        ]
        cursor = create_mock_cursor(docs)
        mock_colecao.find.return_value = cursor

        result = folha_service_mock.buscar_por_status(status="preenchida")

        assert len(result) == 2

    def test_buscar_por_status_empty(self, folha_service_mock, mock_colecao):
        """Test buscar_por_status returns empty list."""
        mock_colecao.find.return_value = create_mock_cursor([])

        result = folha_service_mock.buscar_por_status(status="analise_concluida")

        assert result == []

    def test_buscar_por_status_not_available(self, folha_service_mock):
        """Test buscar_por_status when service not available."""
        folha_service_mock._disponivel = False

        result = folha_service_mock.buscar_por_status(status="criada")

        assert result == []


@pytest.mark.unit
class TestObterEstatisticas:
    """Tests for obter_estatisticas method."""

    def test_obter_estatisticas_success(self, folha_service_mock, mock_colecao):
        """Test obter_estatisticas returns aggregated statistics."""
        mock_colecao.count_documents.return_value = 100

        # Mock aggregation pipelines for status and empresa
        def aggregate_side_effect(pipeline):
            first_stage = pipeline[0]
            if "$group" in first_stage:
                group_by = first_stage["$group"]["_id"]
                if group_by == "$status":
                    return iter([
                        {"_id": "preenchida", "count": 60},
                        {"_id": "criada", "count": 40}
                    ])
                elif group_by == "$empresa":
                    return iter([
                        {"_id": "Empresa A", "count": 70},
                        {"_id": "Empresa B", "count": 30}
                    ])
            return iter([])

        mock_colecao.aggregate.side_effect = aggregate_side_effect

        result = folha_service_mock.obter_estatisticas()

        assert result["status"] == "OK"
        assert result["total_folhas"] == 100
        assert result["status_distribuicao"]["preenchida"] == 60
        assert result["empresa_distribuicao"]["Empresa A"] == 70

    def test_obter_estatisticas_empty(self, folha_service_mock, mock_colecao):
        """Test obter_estatisticas with empty collection."""
        mock_colecao.count_documents.return_value = 0
        mock_colecao.aggregate.return_value = iter([])

        result = folha_service_mock.obter_estatisticas()

        assert result["total_folhas"] == 0
        assert result["status_distribuicao"] == {}

    def test_obter_estatisticas_not_available(self, folha_service_mock):
        """Test obter_estatisticas when service not available."""
        folha_service_mock._disponivel = False

        result = folha_service_mock.obter_estatisticas()

        assert result["status"] == "MongoDB indisponível"
        assert result["total_folhas"] == 0


@pytest.mark.unit
class TestDeletarFolha:
    """Tests for deletar_folha method."""

    def test_deletar_folha_success(self, folha_service_mock, mock_colecao):
        """Test deletar_folha deletes successfully."""
        mock_colecao.delete_one.return_value = MagicMock(deleted_count=1)

        result = folha_service_mock.deletar_folha(
            funcionario_id=123,
            mes_referencia="2025-01",
            lotacao="TI",
            funcao="Analista"
        )

        assert result is True
        mock_colecao.delete_one.assert_called_once()

    def test_deletar_folha_not_found(self, folha_service_mock, mock_colecao):
        """Test deletar_folha returns False when not found."""
        mock_colecao.delete_one.return_value = MagicMock(deleted_count=0)

        result = folha_service_mock.deletar_folha(
            funcionario_id=999,
            mes_referencia="2025-01",
            lotacao="TI",
            funcao="Analista"
        )

        assert result is False

    def test_deletar_folha_not_available(self, folha_service_mock):
        """Test deletar_folha when service not available."""
        folha_service_mock._disponivel = False

        result = folha_service_mock.deletar_folha(
            funcionario_id=123,
            mes_referencia="2025-01",
            lotacao="TI",
            funcao="Analista"
        )

        assert result is False


@pytest.mark.unit
class TestListarTodos:
    """Tests for listar_todos method with pagination."""

    def test_listar_todos_success(self, folha_service_mock, mock_colecao):
        """Test listar_todos returns paginated results."""
        docs = [
            create_folha_doc(mes_referencia="2025-01"),
            create_folha_doc(mes_referencia="2024-12"),
        ]
        cursor = create_mock_cursor(docs)
        mock_colecao.find.return_value = cursor
        mock_colecao.count_documents.return_value = 100

        result = folha_service_mock.listar_todos(skip=0, limit=10)

        assert "dados" in result
        assert result["total"] == 100
        assert result["paginas"] == 10
        assert result["pagina_atual"] == 1
        cursor.skip.assert_called_with(0)
        cursor.limit.assert_called_with(10)

    def test_listar_todos_pagination_calc(self, folha_service_mock, mock_colecao):
        """Test listar_todos pagination calculations."""
        cursor = create_mock_cursor([])
        mock_colecao.find.return_value = cursor
        mock_colecao.count_documents.return_value = 55

        result = folha_service_mock.listar_todos(skip=20, limit=10)

        assert result["paginas"] == 6  # ceil(55/10)
        assert result["pagina_atual"] == 3  # (20/10) + 1

    def test_listar_todos_empty(self, folha_service_mock, mock_colecao):
        """Test listar_todos with no results."""
        cursor = create_mock_cursor([])
        mock_colecao.find.return_value = cursor
        mock_colecao.count_documents.return_value = 0

        result = folha_service_mock.listar_todos()

        assert result["dados"] == []
        assert result["total"] == 0

    def test_listar_todos_not_available(self, folha_service_mock):
        """Test listar_todos when service not available."""
        folha_service_mock._disponivel = False

        result = folha_service_mock.listar_todos()

        assert result["dados"] == []
        assert result["total"] == 0


@pytest.mark.unit
class TestMongoDBIndisponivel:
    """Tests for behavior when MongoDB is not available."""

    def test_init_without_pymongo(self, mocker):
        """Test initialization when pymongo is not installed."""
        # Mock MONGODB_DISPONIVEL as False
        mocker.patch("src.services.folha_ponto_service.MONGODB_DISPONIVEL", False)

        from src.services.folha_ponto_service import FolhaDePontoService

        service = FolhaDePontoService()

        assert service.disponivel is False
        assert service.colecao is None

    def test_operations_when_not_available(self, folha_service_mock):
        """Test all operations return safe defaults when not available."""
        folha_service_mock._disponivel = False

        # All read operations should return empty/None
        assert folha_service_mock.buscar_folha_existente("f", "e", "2025-01") is None
        assert folha_service_mock.listar_por_funcionario(123) == []
        assert folha_service_mock.buscar_por_periodo("2025-01", "2025-12") == []
        assert folha_service_mock.buscar_por_empresa("Test") == []
        assert folha_service_mock.buscar_por_status("criada") == []

        # Write operations should return False/error status
        assert folha_service_mock.deletar_folha(1, "2025-01", "TI", "Dev") is False

        # Estatisticas should return indisponível
        stats = folha_service_mock.obter_estatisticas()
        assert stats["status"] == "MongoDB indisponível"


