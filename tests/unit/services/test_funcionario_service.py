"""
Unit tests for FuncionarioService

Comprehensive tests covering:
- Initialization and MongoDB connection
- CRUD operations (criar, buscar, atualizar, deletar)
- Fuzzy search and similarity matching
- Pagination and statistics
- Batch validation
- Birthday search

Target coverage: 60% (~316 lines of 527)
"""
import os
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from bson import ObjectId
from datetime import datetime, date, timezone, timedelta
from typing import Dict, Any, List


# importar o serviço do Funcionário
from src.services.funcionario_service import FuncionarioService


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


def create_funcionario_doc(
    _id: ObjectId = None,
    nome: str = "Funcionario Teste",
    status: str = "ativo",
    status_cadastro: str = "completo",
    lotacao: str = "TI",
    contrato: str = "CLT",
    documento: str = None,
    data_nascimento: datetime = None,
    **kwargs
) -> Dict[str, Any]:
    """Factory for creating funcionario documents."""
    doc = {
        "_id": _id or ObjectId(),
        "nome": nome,
        "nome_normalizado": nome.lower(),
        "status": status,
        "status_cadastro": status_cadastro,
        "lotacao": lotacao,
        "contrato": contrato,
        "empresas_ids": kwargs.get("empresas_ids", []),
        "criado_em": datetime.now(timezone.utc),
        "atualizado_em": datetime.now(timezone.utc),
        "versao": 1,
        "historico_alteracoes": []
    }
    if documento:
        doc["cpf"] = documento
    if data_nascimento:
        doc["data_nascimento"] = data_nascimento
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
def mock_collection():
    """Mock MongoDB collection with all operations."""
    collection = MagicMock()
    collection.find_one.return_value = MagicMock(return_value=None)
    collection.find.return_value = MagicMock(return_value=create_mock_cursor([]))
    collection.insert_one.return_value = MagicMock(return_value=MagicMock(inserted_id=ObjectId()))
    collection.update_one.return_value = MagicMock(return_value=MagicMock(modified_count=1, matched_count=1))
    collection.delete_one.return_value = MagicMock(return_value=MagicMock(deleted_count=1))
    collection.count_documents.return_value = MagicMock(return_value=0)
    collection.create_index.return_value = MagicMock()
    collection.index_information = MagicMock(return_value={})
    collection.drop_index = MagicMock()
    return collection


@pytest.fixture
def mock_cache_service():
    """Mock cache_service (Redis + memory)."""
    with patch('src.services.empresa_service.cache_service') as mock_cache:
        mock_cache.get.return_value = None
        mock_cache.set.return_value = True
        mock_cache.set_many.return_value = True
        mock_cache.invalidate.return_value = 0
        yield mock_cache


@pytest.fixture
def mock_db(mock_collection):
    """Mock MongoDB database."""
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=mock_collection)
    db["funcionarios"] = mock_collection
    db["contratos"] = MagicMock()
    db["horarios"] = MagicMock()
    db["funcoes"] = MagicMock()
    db["diretorios"] = MagicMock()
    return db


@pytest.fixture
def funcionario_service_mock(mock_mongo_client, mock_db, mock_collection):
    
    """Cria FuncionarioService garantindo que o mock_collection seja usado no __init__."""
    
    # 1. Preparamos o ambiente de patches
    with patch('src.services.funcionario_service.MONGODB_DISPONIVEL', True), \
         patch.dict(os.environ, {
             'MONGO_URI': 'mongodb://localhost:27017',
             'MONGO_DATABASE_NAME': 'test_db',
             'CACHE_TTL': '300'
         }), \
         patch('src.services.funcionario_service.dotenv.get_key') as mock_dotenv:
        
        mock_dotenv.side_effect = lambda path, key: os.environ.get(key)

        # 2. CONFIGURAÇÃO MÁGICA:
        # Pegamos o mock do banco de dados que está dentro do seu mock_mongo_client
        mock_db = mock_mongo_client.get_database.return_value
        
        # Fazemos o banco retornar o mock_collection SEMPRE que for acessado via colchetes
        # Ex: self.db[collection_name] agora retorna o seu mock_collection
        mock_db.__getitem__.return_value = mock_collection
        # Também cobre o caso de self.db.get_collection("...")
        mock_db.get_collection.return_value = mock_collection

        # 3. Criamos o serviço
        # Agora, quando o __init__ rodar e chamar _criar_indices, 
        # ele usará o mock_collection que configuramos acima!
        service = FuncionarioService(collection_name='funcionarios')

        # Opcional: Garantir que o cache comece limpo
        service._cache_funcionarios = {}

        yield service
    
    service = FuncionarioService()
    service.cliente = mock_mongo_client
    service.db = mock_db
    service.colecao = mock_collection
    service._disponivel = True

    return service


# ==================== Test Classes ====================

@pytest.mark.unit
class TestFuncionarioServiceInit:
    """Tests for FuncionarioService initialization."""

    def test_init_success(self, mock_mongo_client, mock_cache_service):
        """Test successful MongoDB connection."""
        
        
        """Testa conexão bem-sucedida ao MongoDB."""
        with patch('src.services.funcionario_service.MONGODB_DISPONIVEL', True):
            with patch('src.services.funcionario_service.dotenv.get_key') as mock_dotenv:
                mock_dotenv.side_effect = lambda path, key: 'mongodb://localhost:27017' if key == 'MONGO_URI' else 'test_db'



        service = FuncionarioService()

        assert service.disponivel is True
        assert service.db is not None
        assert service.collection_name is not None

        
    def test_init_connection_failure(self, mock_mongo_client):
        """Testa se o serviço trata corretamente uma falha crítica de conexão."""
        
        # 1. Configuramos o mock para LEVANTAR uma exceção quando o service pedir o banco
        # Isso vai forçar o código a cair direto no 'except Exception as e:'
        from pymongo.errors import ConnectionFailure
        mock_mongo_client.get_database.side_effect = ConnectionFailure("Erro de rede: timeout")

        # 2. Fazemos o patch da flag e do dotenv (para evitar erros externos)
        with patch('src.services.funcionario_service.MONGODB_DISPONIVEL', True), \
            patch('src.services.funcionario_service.dotenv.get_key', return_value="mock_uri"):
            
            # 3. Executamos a inicialização
            service = FuncionarioService()

            # 4. VERIFICAÇÕES:
            # O código deve ter entrado no 'except', logado o erro e limpado os atributos
            assert service._disponivel is False
            assert service.pool is None
            assert service.db is None
            assert service.colecao is None

    def test_disponivel_property(self, funcionario_service_mock):
        """Test disponivel property returns correct value."""
        assert funcionario_service_mock.disponivel is True

        funcionario_service_mock._disponivel = False
        assert funcionario_service_mock.disponivel is False

    def test_index_creation_called(self, funcionario_service_mock, mock_collection):
        """Test that index creation is attempted on init."""
        
        # Verify create_index was called multiple times
        assert mock_collection.create_index.call_count >= 5


@pytest.mark.unit
class TestCriarFuncionario:
    """Tests for criar_funcionario method."""

    def test_criar_funcionario_success(self, funcionario_service_mock, mock_collection):
        """Test creating funcionario with complete data."""
        func_data = {
            "nome": "Joao Silva",
            "nome_normalizado": "joao silva",
            "lotacao": "TI",
            "contrato": "CLT",
            "status": "ativo"
        }

        inserted_id = ObjectId()
        mock_collection.insert_one.return_value = MagicMock(inserted_id=inserted_id)

        result = funcionario_service_mock.criar_funcionario(func_data)

        assert result == str(inserted_id)
        mock_collection.insert_one.assert_called_once()

    def test_criar_funcionario_not_available(self, funcionario_service_mock):
        """Test creating funcionario when MongoDB is not available."""
        funcionario_service_mock._disponivel = False

        result = funcionario_service_mock.criar_funcionario({"nome": "Test"})

        assert result is None

    def test_criar_funcionario_upsert_on_duplicate(self, funcionario_service_mock, mock_collection):
        """Test upsert behavior when funcionario already exists."""
        func_data = {
            "nome": "Joao Silva",
            "nome_normalizado": "joao silva",
            "lotacao": "TI",
            "contrato": "CLT"
        }

        # Simulate duplicate key error on insert
        mock_collection.insert_one.side_effect = Exception("E11000 duplicate key error")

        existing_id = ObjectId()
        mock_collection.find_one.return_value = {"_id": existing_id, **func_data}
        mock_collection.update_one.return_value = MagicMock(modified_count=1)

        result = funcionario_service_mock.criar_funcionario(func_data)

        assert result == str(existing_id)
        mock_collection.update_one.assert_called_once()

    def test_criar_funcionario_validates_contrato_id(self, funcionario_service_mock, mock_db):
        """Test validation of contrato_empresa_id ObjectId."""
        contrato_id = ObjectId()
        func_data = {
            "nome": "Test",
            "contrato_empresa_id": str(contrato_id)
        }

        # Contrato not found
        mock_db["contratos"].find_one.return_value = None

        result = funcionario_service_mock.criar_funcionario(func_data)

        assert result is None

    def test_criar_funcionario_validates_horario_id(self, funcionario_service_mock, mock_db, mock_collection):
        """Test validation of horario_id ObjectId."""
        horario_id = ObjectId()
        contrato_id = ObjectId()
        func_data = {
            "nome": "Test",
            "contrato_empresa_id": contrato_id,
            "horario_id": str(horario_id)
        }

        # Contrato found but horario not found
        mock_db["contratos"].find_one.return_value = {"_id": contrato_id}
        mock_db["horarios"].find_one.return_value = None

        result = funcionario_service_mock.criar_funcionario(func_data)

        assert result is None

    def test_criar_funcionario_validates_funcao_id(self, funcionario_service_mock, mock_db, mock_collection):
        """Test validation of funcao_id ObjectId."""
        funcao_id = ObjectId()
        contrato_id = ObjectId()
        horario_id = ObjectId()
        func_data = {
            "nome": "Test",
            "contrato_empresa_id": contrato_id,
            "horario_id": horario_id,
            "funcao_id": str(funcao_id)
        }

        mock_db["contratos"].find_one.return_value = {"_id": contrato_id}
        mock_db["horarios"].find_one.return_value = {"_id": horario_id}
        mock_db["funcoes"].find_one.return_value = None

        result = funcionario_service_mock.criar_funcionario(func_data)

        assert result is None

    def test_criar_funcionario_with_pydantic_model(self, funcionario_service_mock, mock_collection, mock_db):
        """Test creating funcionario from Pydantic model."""
        # Mock model with model_dump method
        mock_model = MagicMock()
        mock_model.model_dump.return_value = {
            "nome": "Test User",
            "nome_normalizado": "test user",
            "lotacao": "RH",
            "contrato": "CLT"
        }

        inserted_id = ObjectId()
        mock_collection.insert_one.return_value = MagicMock(inserted_id=inserted_id)

        result = funcionario_service_mock.criar_funcionario(mock_model)

        assert result == str(inserted_id)
        mock_model.model_dump.assert_called_once()

    def test_criar_funcionario_invalid_objectid_string(self, funcionario_service_mock):
        """Test handling of invalid ObjectId string."""
        func_data = {
            "nome": "Test",
            "contrato_empresa_id": "invalid-object-id"
        }

        result = funcionario_service_mock.criar_funcionario(func_data)

        assert result is None


@pytest.mark.unit
class TestBuscaFuncionario:
    """Tests for funcionario search methods."""

    def test_buscar_por_id_success(self, funcionario_service_mock, mock_collection):
        """Test buscar_por_id returns funcionario when found."""
        func_id = ObjectId()
        expected_doc = create_funcionario_doc(_id=func_id)
        mock_collection.find_one.return_value = expected_doc

        result = funcionario_service_mock.buscar_por_id(str(func_id))

        assert result is not None
        assert result["nome"] == expected_doc["nome"]

    def test_buscar_por_id_not_found(self, funcionario_service_mock, mock_collection):
        """Test buscar_por_id returns None when not found."""
        mock_collection.find_one.return_value = None

        result = funcionario_service_mock.buscar_por_id(str(ObjectId()))

        assert result is None

    def test_buscar_por_id_not_available(self, funcionario_service_mock):
        """Test buscar_por_id when service not available."""
        funcionario_service_mock._disponivel = False

        result = funcionario_service_mock.buscar_por_id(str(ObjectId()))

        assert result is None

    def test_buscar_por_nome_lotacao_contrato_success(self, funcionario_service_mock, mock_collection):
        """Test buscar_por_nome_lotacao_contrato returns funcionario."""
        expected_doc = create_funcionario_doc(
            nome="Joao Silva",
            lotacao="TI",
            contrato="CLT"
        )
        mock_collection.find_one.return_value = expected_doc

        result = funcionario_service_mock.buscar_por_nome_lotacao_contrato(
            nome="Joao Silva",
            lotacao="TI",
            contrato="CLT"
        )

        assert result is not None
        assert result["nome"] == "Joao Silva"

    def test_buscar_por_nome_lotacao_contrato_normalizes_name(self, funcionario_service_mock, mock_collection):
        """Test that nome is normalized for search."""
        expected_doc = create_funcionario_doc(nome="Jose Santos")
        mock_collection.find_one.return_value = expected_doc

        # Search with accented name
        funcionario_service_mock.buscar_por_nome_lotacao_contrato(
            nome="Jose Santos",
            lotacao="TI",
            contrato="CLT"
        )

        # Verify search used normalized name
        call_args = mock_collection.find_one.call_args
        assert call_args[0][0]["nome_normalizado"] == "jose santos"

    def test_buscar_por_nome_lotacao_contrato_not_available(self, funcionario_service_mock):
        """Test search when service not available."""
        funcionario_service_mock._disponivel = False

        result = funcionario_service_mock.buscar_por_nome_lotacao_contrato(
            nome="Test", lotacao="TI", contrato="CLT"
        )

        assert result is None

    def test_buscar_por_object_id_success(self, funcionario_service_mock, mock_collection):
        """Test buscar_por_object_id returns funcionario."""
        obj_id = ObjectId()
        expected_doc = create_funcionario_doc(_id=obj_id)
        mock_collection.find_one.return_value = expected_doc

        result = funcionario_service_mock.buscar_por_object_id(str(obj_id))

        assert result is not None
        assert result["_id"] == obj_id

    def test_buscar_por_object_id_with_objectid_input(self, funcionario_service_mock, mock_collection):
        """Test buscar_por_object_id with ObjectId input (not string)."""
        obj_id = ObjectId()
        expected_doc = create_funcionario_doc(_id=obj_id)
        mock_collection.find_one.return_value = expected_doc

        result = funcionario_service_mock.buscar_por_object_id(obj_id)

        assert result is not None

    def test_buscar_todos_por_nome_success(self, funcionario_service_mock, mock_collection):
        """Test buscar_todos_por_nome returns list of funcionarios."""
        docs = [
            create_funcionario_doc(nome="Joao Silva", lotacao="TI"),
            create_funcionario_doc(nome="Joao Silva", lotacao="RH"),
        ]
        mock_collection.find.return_value = create_mock_cursor(docs)

        result = funcionario_service_mock.buscar_todos_por_nome("Joao Silva")

        assert len(result) == 2

    def test_buscar_todos_por_nome_empty(self, funcionario_service_mock, mock_collection):
        """Test buscar_todos_por_nome returns empty list when not found."""
        mock_collection.find.return_value = create_mock_cursor([])

        result = funcionario_service_mock.buscar_todos_por_nome("Nome Inexistente")

        assert result == []


@pytest.mark.unit
class TestBuscarSimilar:
    """Tests for fuzzy search with similarity threshold."""

    def test_buscar_similar_success(self, funcionario_service_mock, mock_collection):
        """Test buscar_similar finds funcionario with high similarity."""
        docs = [
            create_funcionario_doc(
                nome="Joao Silva Santos",
                nome_normalizado="joao silva santos",
                lotacao="TI",
                contrato="CLT"
            )
        ]
        mock_collection.find.return_value = create_mock_cursor(docs)

        result = funcionario_service_mock.buscar_similar(
            nome="Joao Silva",  # Similar but not exact
            lotacao="TI",
            contrato="CLT",
            limiar_similaridade=0.6
        )

        assert result is not None

    def test_buscar_similar_below_threshold(self, funcionario_service_mock, mock_collection):
        """Test buscar_similar returns None when below threshold."""
        docs = [
            create_funcionario_doc(
                nome="Maria Santos",
                nome_normalizado="maria santos",
                lotacao="TI",
                contrato="CLT"
            )
        ]
        mock_collection.find.return_value = create_mock_cursor(docs)

        result = funcionario_service_mock.buscar_similar(
            nome="Joao Silva",  # Very different name
            lotacao="TI",
            contrato="CLT",
            limiar_similaridade=0.8  # High threshold
        )

        assert result is None

    def test_buscar_similar_no_funcionarios(self, funcionario_service_mock, mock_collection):
        """Test buscar_similar returns None when no funcionarios found."""
        mock_collection.find.return_value = create_mock_cursor([])

        result = funcionario_service_mock.buscar_similar(
            nome="Test",
            lotacao="TI",
            contrato="CLT"
        )

        assert result is None

    def test_buscar_similar_not_available(self, funcionario_service_mock):
        """Test buscar_similar when service not available."""
        funcionario_service_mock._disponivel = False

        result = funcionario_service_mock.buscar_similar(
            nome="Test",
            lotacao="TI",
            contrato="CLT"
        )

        assert result is None


@pytest.mark.unit
class TestBuscaPorDocumento:
    """Tests for buscar_por_documento method."""

    def test_buscar_por_documento_success(self, funcionario_service_mock, mock_collection):
        """Test buscar_por_documento finds funcionario by CPF."""
        expected_doc = create_funcionario_doc(documento="12345678901")
        mock_collection.find_one.return_value = expected_doc

        result = funcionario_service_mock.buscar_por_documento("12345678901")

        assert result is not None
        # Verify CPF was normalized (dots/dashes removed)
        call_args = mock_collection.find_one.call_args
        assert call_args[0][0]["cpf"] == "12345678901"

    def test_buscar_por_documento_not_found(self, funcionario_service_mock, mock_collection):
        """Test buscar_por_documento returns None when not found."""
        mock_collection.find_one.return_value = None

        result = funcionario_service_mock.buscar_por_documento("999.999.999-99")

        assert result is None

    def test_buscar_por_documento_not_available(self, funcionario_service_mock):
        """Test buscar_por_documento when service not available."""
        funcionario_service_mock._disponivel = False

        result = funcionario_service_mock.buscar_por_documento("123.456.789-01")

        assert result is None

    def test_criar_ou_buscar_por_documento_existing(self, funcionario_service_mock, mock_collection):
        """Test criar_ou_buscar_por_documento returns existing funcionario."""
        existing_doc = create_funcionario_doc(documento="12345678901", nome="Existente")
        mock_collection.find_one.return_value = existing_doc

        result = funcionario_service_mock.criar_ou_buscar_por_documento(
            documento="123.456.789-01",
            nome="Novo Nome"
        )

        assert result is not None
        assert result["nome"] == "Existente"

    def test_criar_ou_buscar_por_documento_creates_new(self, funcionario_service_mock, mock_collection, mocker):
        """Test criar_ou_buscar_por_documento creates new funcionario."""
        # First call returns None (not found), second returns the created doc
        mock_collection.find_one.side_effect = [
            None,  # buscar_por_documento
            create_funcionario_doc(documento="12345678901", nome="Novo User")  # after insert
        ]

        inserted_id = ObjectId()
        mock_collection.insert_one.return_value = MagicMock(inserted_id=inserted_id)

        # Mock FuncionarioBuilder - it's imported from models inside the method
        mock_builder = MagicMock()
        mock_func = MagicMock()
        mock_func.to_mongo_insert.return_value = {"nome": "Novo User", "documento": "12345678901"}
        mock_builder.set_identificacao.return_value = mock_builder
        mock_builder.set_status_cadastro.return_value = mock_builder
        mock_builder.set_contato.return_value = mock_builder
        mock_builder.build_incompleto.return_value = mock_func

        mocker.patch(
            "src.models.funcionario_models.FuncionarioBuilder",
            return_value=mock_builder
        )

        result = funcionario_service_mock.criar_ou_buscar_por_documento(
            documento="123.456.789-01",
            nome="Novo User"
        )

        assert result is not None


@pytest.mark.unit
class TestAtualizarFuncionario:
    """Tests for atualizar method."""

    def test_atualizar_success(self, funcionario_service_mock, mock_collection):
        """Test atualizar updates funcionario successfully."""
        obj_id = ObjectId()
        existing_doc = create_funcionario_doc(_id=obj_id, nome="Old Name")

        mock_collection.find_one.return_value = existing_doc
        mock_collection.update_one.return_value = MagicMock(modified_count=1)

        result = funcionario_service_mock.atualizar(
            str(obj_id),
            {"nome": "New Name"},
            registrar_historico=False  # Skip historico decorator
        )

        assert result is True

    def test_atualizar_not_found(self, funcionario_service_mock, mock_collection):
        """Test atualizar returns False when not found."""
        mock_collection.find_one.return_value = None
        mock_collection.update_one.return_value = MagicMock(modified_count=0)

        result = funcionario_service_mock.atualizar(
            str(ObjectId()),
            {"nome": "New Name"},
            registrar_historico=False
        )

        assert result is False

    def test_atualizar_invalid_objectid(self, funcionario_service_mock):
        """Test atualizar with invalid ObjectId."""
        result = funcionario_service_mock.atualizar(
            "invalid-id",
            {"nome": "New Name"},
            registrar_historico=False
        )

        assert result is False

    def test_atualizar_not_available(self, funcionario_service_mock):
        """Test atualizar when service not available."""
        funcionario_service_mock._disponivel = False

        result = funcionario_service_mock.atualizar(
            str(ObjectId()),
            {"nome": "New Name"}
        )

        assert result is False

    def test_atualizar_adds_timestamp(self, funcionario_service_mock, mock_collection):
        """Test that atualizar adds atualizado_em timestamp."""
        obj_id = ObjectId()
        existing_doc = create_funcionario_doc(_id=obj_id)

        mock_collection.find_one.return_value = existing_doc
        mock_collection.update_one.return_value = MagicMock(modified_count=1)

        funcionario_service_mock.atualizar(
            str(obj_id),
            {"nome": "New Name"},
            registrar_historico=False
        )

        # Check that update was called with atualizado_em
        call_args = mock_collection.update_one.call_args
        assert "atualizado_em" in call_args[0][1]["$set"]


@pytest.mark.unit
class TestDeletarFuncionario:
    """Tests for deletar method (soft delete)."""

    def test_deletar_success(self, funcionario_service_mock, mock_collection):
        """Test deletar marks funcionario as inativo."""
        obj_id = ObjectId()
        mock_collection.update_one.return_value = MagicMock(modified_count=1)

        result = funcionario_service_mock.deletar(str(obj_id))

        assert result is True

        # Verify update set status to inativo
        call_args = mock_collection.update_one.call_args
        assert call_args[0][1]["$set"]["status"] == "inativo"

    def test_deletar_not_found(self, funcionario_service_mock, mock_collection):
        """Test deletar returns False when not found."""
        mock_collection.update_one.return_value = MagicMock(modified_count=0)

        result = funcionario_service_mock.deletar(str(ObjectId()))

        assert result is False

    def test_deletar_not_available(self, funcionario_service_mock):
        """Test deletar when service not available."""
        funcionario_service_mock._disponivel = False

        result = funcionario_service_mock.deletar(str(ObjectId()))

        assert result is False

    def test_deletar_with_objectid_input(self, funcionario_service_mock, mock_collection):
        """Test deletar works with ObjectId input (not string)."""
        obj_id = ObjectId()
        mock_collection.update_one.return_value = MagicMock(modified_count=1)

        result = funcionario_service_mock.deletar(obj_id)

        assert result is True


@pytest.mark.unit
class TestEstatisticas:
    """Tests for obter_estatisticas method."""

    def test_obter_estatisticas_success(self, funcionario_service_mock, mock_collection):
        """Test obter_estatisticas returns aggregated statistics."""
        mock_collection.aggregate.return_value = iter([{
            "por_status": [
                {"_id": "ativo", "total": 50},
                {"_id": "inativo", "total": 10}
            ],
            "por_contrato": [
                {"_id": "CLT", "total": 40},
                {"_id": "PJ", "total": 20}
            ],
            "por_lotacao": [
                {"lotacao": "TI", "total": 30},
                {"lotacao": "RH", "total": 15}
            ]
        }])

        result = funcionario_service_mock.obter_estatisticas()

        assert "por_status" in result
        assert result["por_status"]["ativo"] == 50
        assert result["por_status"]["inativo"] == 10
        assert "por_contrato" in result
        assert result["por_contrato"]["CLT"] == 40

    def test_obter_estatisticas_empty(self, funcionario_service_mock, mock_collection):
        """Test obter_estatisticas with empty result."""
        mock_collection.aggregate.return_value = iter([])

        result = funcionario_service_mock.obter_estatisticas()

        assert result["por_status"] == {}
        assert result["por_contrato"] == {}
        assert result["por_lotacao"] == []

    def test_obter_estatisticas_not_available(self, funcionario_service_mock):
        """Test obter_estatisticas when service not available."""
        funcionario_service_mock._disponivel = False

        result = funcionario_service_mock.obter_estatisticas()

        assert result["por_status"] == {}


@pytest.mark.unit
class TestListarComPaginacao:
    """Tests for listar_todos method with pagination."""

    def test_listar_todos_success(self, funcionario_service_mock, mock_collection):
        """Test listar_todos returns paginated results."""
        docs = [
            create_funcionario_doc(nome="User 1"),
            create_funcionario_doc(nome="User 2"),
        ]
        cursor = create_mock_cursor(docs)
        mock_collection.find.return_value = cursor
        mock_collection.count_documents.return_value = 100

        result = funcionario_service_mock.listar_todos(skip=0, limit=10)

        assert "dados" in result
        assert result["total"] == 100
        assert result["paginas"] == 10
        assert result["pagina_atual"] == 1

    def test_listar_todos_pagination(self, funcionario_service_mock, mock_collection):
        """Test listar_todos pagination calculations."""
        cursor = create_mock_cursor([])
        mock_collection.find.return_value = cursor
        mock_collection.count_documents.return_value = 55

        result = funcionario_service_mock.listar_todos(skip=20, limit=10)

        assert result["paginas"] == 6  # ceil(55/10)
        assert result["pagina_atual"] == 3  # (20/10) + 1

    def test_listar_todos_empty(self, funcionario_service_mock, mock_collection):
        """Test listar_todos with no results."""
        cursor = create_mock_cursor([])
        mock_collection.find.return_value = cursor
        mock_collection.count_documents.return_value = 0

        result = funcionario_service_mock.listar_todos()

        assert result["dados"] == []
        assert result["total"] == 0

    def test_listar_todos_not_available(self, funcionario_service_mock):
        """Test listar_todos when service not available."""
        funcionario_service_mock._disponivel = False

        result = funcionario_service_mock.listar_todos()

        assert result["dados"] == []
        assert result["total"] == 0

    def test_listar_todos_sorting(self, funcionario_service_mock, mock_collection):
        """Test listar_todos applies sorting."""
        cursor = create_mock_cursor([])
        mock_collection.find.return_value = cursor
        mock_collection.count_documents.return_value = 0

        funcionario_service_mock.listar_todos()

        # Verify sort was called on cursor
        cursor.sort.assert_called_with("nome", 1)


@pytest.mark.unit
class TestBuscarAniversariantes:
    """Tests for buscar_aniversariantes method."""

    def test_buscar_aniversariantes_success(self, funcionario_service_mock, mock_collection):
        """Test buscar_aniversariantes returns funcionarios for month."""
        docs = [
            create_funcionario_doc(
                nome="User 1",
                data_nascimento=datetime(1990, 1, 15)
            ),
            create_funcionario_doc(
                nome="User 2",
                data_nascimento=datetime(1985, 1, 20)
            ),
        ]
        mock_collection.aggregate.return_value = iter(docs)

        result = funcionario_service_mock.buscar_aniversariantes(mes=1)

        assert len(result) == 2

    def test_buscar_aniversariantes_empty(self, funcionario_service_mock, mock_collection):
        """Test buscar_aniversariantes returns empty list when none found."""
        mock_collection.aggregate.return_value = iter([])

        result = funcionario_service_mock.buscar_aniversariantes(mes=12)

        assert result == []

    def test_buscar_aniversariantes_not_available(self, funcionario_service_mock):
        """Test buscar_aniversariantes when service not available."""
        funcionario_service_mock._disponivel = False

        result = funcionario_service_mock.buscar_aniversariantes(mes=1)

        assert result == []

    def test_buscar_aniversariantes_pipeline_structure(self, funcionario_service_mock, mock_collection):
        """Test buscar_aniversariantes uses correct aggregation pipeline."""
        mock_collection.aggregate.return_value = iter([])

        funcionario_service_mock.buscar_aniversariantes(mes=5)

        # Verify aggregate was called
        mock_collection.aggregate.assert_called_once()

        # Check pipeline structure
        call_args = mock_collection.aggregate.call_args
        pipeline = call_args[0][0]

        # Should have $addFields, $match, etc.
        assert any("$addFields" in stage for stage in pipeline)
        assert any("$match" in stage for stage in pipeline)


@pytest.mark.unit
class TestValidarReferenciasBatch:
    """Tests for validar_referencias_batch method."""

    def test_validar_referencias_batch_all_valid(self, funcionario_service_mock):
        """Test validar_referencias_batch with all valid references."""
        contrato_ids = [str(ObjectId()), str(ObjectId())]
        horario_ids = [str(ObjectId())]

        # Create separate mocks for each collection
        mock_contratos = MagicMock()
        mock_contratos.count_documents.return_value = 2
        mock_horarios = MagicMock()
        mock_horarios.count_documents.return_value = 1

        # Set up db to return specific mocks for each collection
        def get_collection(name):
            collections = {
                "contratos": mock_contratos,
                "horarios": mock_horarios,
            }
            return collections.get(name, MagicMock())

        funcionario_service_mock.db.__getitem__ = MagicMock(side_effect=get_collection)

        result = funcionario_service_mock.validar_referencias_batch(
            contratos=contrato_ids,
            horarios=horario_ids
        )

        assert result["contratos_validos"] is True
        assert result["horarios_validos"] is True

    def test_validar_referencias_batch_some_invalid(self, funcionario_service_mock):
        """Test validar_referencias_batch with some invalid references."""
        contrato_ids = [str(ObjectId()), str(ObjectId())]

        # Create mock for contratos that returns 1 (not all found)
        mock_contratos = MagicMock()
        mock_contratos.count_documents.return_value = 1

        funcionario_service_mock.db.__getitem__ = MagicMock(return_value=mock_contratos)

        result = funcionario_service_mock.validar_referencias_batch(
            contratos=contrato_ids
        )

        assert result["contratos_validos"] is False

    def test_validar_referencias_batch_empty_lists(self, funcionario_service_mock):
        """Test validar_referencias_batch with empty lists."""
        result = funcionario_service_mock.validar_referencias_batch(
            contratos=[],
            horarios=[],
            funcoes=[],
            diretorios=[]
        )

        # All should be valid when empty
        assert result["contratos_validos"] is True
        assert result["horarios_validos"] is True
        assert result["funcoes_validos"] is True
        assert result["diretorios_validos"] is True

    def test_validar_referencias_batch_not_available(self, funcionario_service_mock):
        """Test validar_referencias_batch when service not available."""
        funcionario_service_mock._disponivel = False

        result = funcionario_service_mock.validar_referencias_batch(
            contratos=[str(ObjectId())]
        )

        assert result["contratos_validos"] is False


@pytest.mark.unit
class TestListarPorEmpresa:
    """Tests for listar_por_empresa method."""

    def test_listar_por_empresa_success(self, funcionario_service_mock, mock_collection):
        """Test listar_por_empresa returns funcionarios."""
        docs = [
            create_funcionario_doc(nome="User 1"),
            create_funcionario_doc(nome="User 2"),
        ]
        mock_collection.find.return_value = create_mock_cursor(docs)

        result = funcionario_service_mock.listar_por_empresa("Empresa Test")

        assert len(result) == 2

    def test_listar_por_empresa_empty(self, funcionario_service_mock, mock_collection):
        """Test listar_por_empresa returns empty list."""
        mock_collection.find.return_value = create_mock_cursor([])

        result = funcionario_service_mock.listar_por_empresa("Empresa Inexistente")

        assert result == []

    def test_listar_por_empresa_not_available(self, funcionario_service_mock):
        """Test listar_por_empresa when service not available."""
        funcionario_service_mock._disponivel = False

        result = funcionario_service_mock.listar_por_empresa("Empresa Test")

        assert result == []


@pytest.mark.unit
class TestListarPorLotacao:
    """Tests for listar_por_lotacao method."""

    def test_listar_por_lotacao_success(self, funcionario_service_mock, mock_collection):
        """Test listar_por_lotacao returns funcionarios."""
        docs = [
            create_funcionario_doc(nome="User 1", lotacao="TI"),
            create_funcionario_doc(nome="User 2", lotacao="TI"),
        ]
        mock_collection.find.return_value = create_mock_cursor(docs)

        result = funcionario_service_mock.listar_por_lotacao("TI")

        assert len(result) == 2


@pytest.mark.unit
class TestListarIncompletos:
    """Tests for listar_incompletos method."""

    def test_listar_incompletos_success(self, funcionario_service_mock, mock_collection):
        """Test listar_incompletos returns funcionarios with incomplete status."""
        docs = [
            create_funcionario_doc(status_cadastro="incompleto"),
            create_funcionario_doc(status_cadastro="pendente_revisao"),
        ]
        mock_collection.find.return_value = create_mock_cursor(docs)

        result = funcionario_service_mock.listar_incompletos()

        assert len(result) == 2

    def test_listar_incompletos_with_pagination(self, funcionario_service_mock, mock_collection):
        """Test listar_incompletos respects pagination."""
        cursor = create_mock_cursor([])
        mock_collection.find.return_value = cursor

        funcionario_service_mock.listar_incompletos(skip=10, limit=50)

        cursor.skip.assert_called_with(10)
        cursor.limit.assert_called_with(50)


@pytest.mark.unit
class TestAdicionarEmpresaFuncionario:
    """Tests for adicionar_empresa_funcionario method."""

    def test_adicionar_empresa_funcionario_success(self, funcionario_service_mock, mock_collection):
        """Test adicionar_empresa_funcionario adds empresa to list."""
        func_id = str(ObjectId())
        emp_id = str(ObjectId())

        mock_collection.update_one.return_value = MagicMock(modified_count=1)

        result = funcionario_service_mock.adicionar_empresa_funcionario(func_id, emp_id)

        assert result is True

        # Verify $addToSet was used
        call_args = mock_collection.update_one.call_args
        assert "$addToSet" in call_args[0][1]

    def test_adicionar_empresa_funcionario_already_exists(self, funcionario_service_mock, mock_collection):
        """Test adicionar_empresa_funcionario when empresa already in list."""
        func_id = str(ObjectId())
        emp_id = str(ObjectId())

        # modified_count is 0 because $addToSet didn't add (already exists)
        mock_collection.update_one.return_value = MagicMock(modified_count=0)

        result = funcionario_service_mock.adicionar_empresa_funcionario(func_id, emp_id)

        # Should still return True (not an error)
        assert result is True

    def test_adicionar_empresa_funcionario_invalid_ids(self, funcionario_service_mock):
        """Test adicionar_empresa_funcionario with invalid IDs."""
        result = funcionario_service_mock.adicionar_empresa_funcionario(
            "invalid-id",
            "also-invalid"
        )

        assert result is False

    def test_adicionar_empresa_funcionario_not_available(self, funcionario_service_mock):
        """Test adicionar_empresa_funcionario when service not available."""
        funcionario_service_mock._disponivel = False

        result = funcionario_service_mock.adicionar_empresa_funcionario(
            str(ObjectId()),
            str(ObjectId())
        )

        assert result is False



@pytest.mark.unit
class TestBuscarComRelacionamentos:
    """Tests for buscar_com_relacionamentos method."""

    def test_buscar_com_relacionamentos_success(self, funcionario_service_mock, mock_collection, mocker):
        """Test buscar_com_relacionamentos returns populated document."""
        func_id = str(ObjectId())
        expected_doc = create_funcionario_doc(
            nome="Test User",
            contrato_info={"tipo": "CLT"},
            funcao_info={"nome": "Analista"}
        )

        mock_collection.aggregate.return_value = iter([expected_doc])

        # Mock the import of contato_funcionario_service within the method
        # Since it's imported locally, we need to mock the module
        mock_contato_module = MagicMock()
        mock_contato_module.contato_funcionario_service = None
        mocker.patch.dict(
            "sys.modules",
            {"src.services.contato_funcionario_service": mock_contato_module}
        )

        result = funcionario_service_mock.buscar_com_relacionamentos(func_id)

        assert result is not None

    def test_buscar_com_relacionamentos_not_found(self, funcionario_service_mock, mock_collection):
        """Test buscar_com_relacionamentos returns None when not found."""
        mock_collection.aggregate.return_value = iter([])

        result = funcionario_service_mock.buscar_com_relacionamentos(str(ObjectId()))

        assert result is None


@pytest.mark.unit
class TestListarPorEmpresaComContagem:
    """Tests for listar_por_empresa_com_contagem method."""

    def test_listar_por_empresa_com_contagem_success(self, funcionario_service_mock, mock_db, mock_collection):
        """Test listar_por_empresa_com_contagem returns data and count."""
        emp_id = str(ObjectId())
        contrato_id = ObjectId()

        # Mock contratos query
        mock_db["contratos"].find.return_value = [{"_id": contrato_id}]

        # Mock aggregate with $facet
        mock_collection.aggregate.return_value = iter([{
            "dados": [
                create_funcionario_doc(nome="User 1"),
                create_funcionario_doc(nome="User 2"),
            ],
            "total": [{"count": 50}]
        }])

        dados, total = funcionario_service_mock.listar_por_empresa_com_contagem(emp_id)

        assert len(dados) == 2
        assert total == 50

    def test_listar_por_empresa_com_contagem_no_contratos(self, funcionario_service_mock, mock_db):
        """Test listar_por_empresa_com_contagem when no contratos found."""
        mock_db["contratos"].find.return_value = []

        dados, total = funcionario_service_mock.listar_por_empresa_com_contagem(str(ObjectId()))

        assert dados == []
        assert total == 0

    def test_listar_por_empresa_com_contagem_not_available(self, funcionario_service_mock):
        """Test listar_por_empresa_com_contagem when service not available."""
        funcionario_service_mock._disponivel = False

        dados, total = funcionario_service_mock.listar_por_empresa_com_contagem(str(ObjectId()))

        assert dados == []
        assert total == 0


@pytest.mark.unit
class TestExportarComRelacionamentos:
    """Tests for exportar_com_relacionamentos method."""

    def test_exportar_com_relacionamentos_success(self, funcionario_service_mock, mock_collection, mocker):
        """Test exportar_com_relacionamentos returns populated list."""
        docs = [
            create_funcionario_doc(_id=ObjectId(), nome="User 1"),
            create_funcionario_doc(_id=ObjectId(), nome="User 2"),
        ]

        mock_collection.aggregate.return_value = iter(docs)

        # Mock the import of contato_funcionario_service
        mock_contato_service = MagicMock()
        mock_contato_service.obter_contatos_batch.return_value = {}
        mock_contato_module = MagicMock()
        mock_contato_module.contato_funcionario_service = mock_contato_service
        mocker.patch.dict(
            "sys.modules",
            {"src.services.contato_funcionario_service": mock_contato_module}
        )

        result = funcionario_service_mock.exportar_com_relacionamentos(limit=10)

        assert len(result) == 2

    def test_exportar_com_relacionamentos_with_filter(self, funcionario_service_mock, mock_collection, mocker):
        """Test exportar_com_relacionamentos applies filter."""
        mock_collection.aggregate.return_value = iter([])

        # Mock the import of contato_funcionario_service
        mock_contato_module = MagicMock()
        mock_contato_module.contato_funcionario_service = None
        mocker.patch.dict(
            "sys.modules",
            {"src.services.contato_funcionario_service": mock_contato_module}
        )

        funcionario_service_mock.exportar_com_relacionamentos(
            filtro={"status": "ativo"},
            limit=100
        )

        # Verify aggregate was called
        mock_collection.aggregate.assert_called_once()

        # Check pipeline includes filter
        call_args = mock_collection.aggregate.call_args
        pipeline = call_args[0][0]

        # First stage should be $match with filter
        assert pipeline[0] == {"$match": {"status": "ativo"}}

    def test_exportar_com_relacionamentos_empty(self, funcionario_service_mock, mock_collection):
        """Test exportar_com_relacionamentos with no results."""
        mock_collection.aggregate.return_value = iter([])

        result = funcionario_service_mock.exportar_com_relacionamentos()

        assert result == []


@pytest.mark.unit
class TestBuscarPorNomeLotacao:
    """Tests for buscar_por_nome_lotacao method."""

    def test_buscar_por_nome_lotacao_success(self, funcionario_service_mock, mock_collection):
        """Test buscar_por_nome_lotacao finds funcionario."""
        expected_doc = create_funcionario_doc(nome="Joao Silva", lotacao="TI")
        mock_collection.find_one.return_value = expected_doc

        result = funcionario_service_mock.buscar_por_nome_lotacao(
            nome="Joao Silva",
            lotacao="TI"
        )

        assert result is not None
        assert result["nome"] == "Joao Silva"

    def test_buscar_por_nome_lotacao_not_found(self, funcionario_service_mock, mock_collection):
        """Test buscar_por_nome_lotacao returns None when not found."""
        mock_collection.find_one.return_value = None

        result = funcionario_service_mock.buscar_por_nome_lotacao(
            nome="Nome Inexistente",
            lotacao="TI"
        )

        assert result is None

    def test_buscar_por_nome_lotacao_not_available(self, funcionario_service_mock):
        """Test buscar_por_nome_lotacao when service not available."""
        funcionario_service_mock._disponivel = False

        result = funcionario_service_mock.buscar_por_nome_lotacao(
            nome="Test",
            lotacao="TI"
        )

        assert result is None
