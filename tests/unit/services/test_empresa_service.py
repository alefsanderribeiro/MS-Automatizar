"""
Testes unitários para EmpresaService
Testa operações de CRUD, cache híbrido (memória + Redis), e autocadastro
"""

import pytest
from unittest.mock import MagicMock, patch, call
from bson import ObjectId
from datetime import datetime, timezone
from typing import Dict, Any
import json
import os

from src.services.empresa_service import EmpresaService
from src.models.empresa_models import StatusEmpresa


# ==================== FIXTURES ====================

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
    with patch('src.services.empresa_service.MONGODB_DISPONIVEL', True), \
         patch('src.services.empresa_service.MongoDBConnectionPool') as mock_class:
        
        # Faz com que qualquer chamada a MongoDBConnectionPool() retorne nossa instância mockada
        mock_class.return_value = mock_pool_instance
        
        yield mock_pool_instance


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
def mock_collection():
    """Mock MongoDB collection with standard CRUD operations."""
    collection = MagicMock()
    collection.find_one.return_value = None
    collection.find.return_value = []
    collection.insert_one.return_value = MagicMock(inserted_id=ObjectId())
    collection.update_one.return_value = MagicMock(modified_count=1, matched_count=1)
    collection.delete_one.return_value = MagicMock(deleted_count=1)
    collection.count_documents.return_value = 0
    collection.create_index.return_value = "idx_test"
    return collection


@pytest.fixture
def empresa_service_with_mock(mock_mongo_client, mock_cache_service, mock_collection):
    """Cria EmpresaService garantindo que o mock_collection seja usado no __init__."""
    
    # 1. Preparamos o ambiente de patches
    with patch('src.services.empresa_service.MONGODB_DISPONIVEL', True), \
         patch.dict(os.environ, {
             'MONGO_URI': 'mongodb://localhost:27017',
             'MONGO_DATABASE_NAME': 'test_db',
             'CACHE_TTL': '300'
         }), \
         patch('src.services.empresa_service.dotenv.get_key') as mock_dotenv:
        
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
        service = EmpresaService(collection_name='empresas')

        # Opcional: Garantir que o cache comece limpo
        service._cache_empresas = {}

        yield service


@pytest.fixture
def empresa_dict(sample_object_id) -> Dict[str, Any]:
    """Sample empresa data from conftest.py."""
    return {
        "_id": sample_object_id,
        "nome": "Moraes & Santos Consultoria",
        "cnpj": "12345678000190",
        "atividade": "Consultoria em TI",
        "endereco": "Rua A, 123 - São Paulo, SP",
        "telefone": "(11) 9999-9999",
        "email": "contato@moraes.com.br",
        "responsavel": "João Moraes",
        "status": "ativa",
        "incompleto": False,
        "nome_normalizado": "moraes & santos consultoria",
        "nome_sigla": "M&S",
        "nome_simplificado": "Moraes Santos",
        "criado_em": datetime.now(timezone.utc),
        "atualizado_em": datetime.now(timezone.utc),
        "versao": 1,
        "historico_alteracoes": []
    }


@pytest.fixture
def empresa_incompleta_dict() -> Dict[str, Any]:
    """Sample incomplete empresa data."""
    return {
        "_id": ObjectId(),
        "nome": "Empresa Teste Ltda",
        "status": "em_construcao",
        "incompleto": True,
        "nome_normalizado": "empresa teste ltda",
        "criado_em": datetime.now(timezone.utc),
        "atualizado_em": datetime.now(timezone.utc),
        "versao": 1,
        "historico_alteracoes": []
    }


# ==================== TEST CLASSES ====================

class TestEmpresaServiceInit:
    """Testes de inicialização do serviço."""

    def test_init_mongodb_connection_success(self, mock_mongo_client, mock_cache_service):
        """Testa conexão bem-sucedida ao MongoDB."""
        with patch('src.services.empresa_service.MONGODB_DISPONIVEL', True):
            with patch('src.services.empresa_service.dotenv.get_key') as mock_dotenv:
                mock_dotenv.side_effect = lambda path, key: 'mongodb://localhost:27017' if key == 'MONGO_URI' else 'test_db'

                service = EmpresaService(
                )

                assert service.disponivel is True
                assert service.mongo_uri == 'mongodb://localhost:27017'
                assert service.db_name == 'test_db'
                assert service.collection_name == 'empresas'

    def test_init_mongodb_not_available(self):
        """Testa inicialização quando PyMongo não está disponível."""
        with patch('src.services.empresa_service.MONGODB_DISPONIVEL', False):
            service = EmpresaService()

            assert service.disponivel is False


    def test_init_connection_failure(self, mock_mongo_client, mock_cache_service):
        """Testa se o serviço trata corretamente uma falha crítica de conexão."""
        
        # 1. Configuramos o mock para LEVANTAR uma exceção quando o service pedir o banco
        # Isso vai forçar o código a cair direto no 'except Exception as e:'
        from pymongo.errors import ConnectionFailure
        mock_mongo_client.get_database.side_effect = ConnectionFailure("Erro de rede: timeout")

        # 2. Fazemos o patch da flag e do dotenv (para evitar erros externos)
        with patch('src.services.empresa_service.MONGODB_DISPONIVEL', True), \
            patch('src.services.empresa_service.dotenv.get_key', return_value="mock_uri"):
            
            # 3. Executamos a inicialização
            service = EmpresaService()

            # 4. VERIFICAÇÕES:
            # O código deve ter entrado no 'except', logado o erro e limpado os atributos
            assert service._disponivel is False
            assert service.pool is None
            assert service.db is None
            assert service.colecao is None

    def test_init_creates_indexes(self, empresa_service_with_mock):
        """Testa criação de índices ao inicializar."""
        service = empresa_service_with_mock

        # Verify create_index was called for expected indexes
        assert service.colecao.create_index.called

    def test_init_memory_cache_initialized(self, empresa_service_with_mock):
        """Testa inicialização do cache em memória."""
        service = empresa_service_with_mock

        assert isinstance(service._cache_empresas, dict)
        assert service.cache is not None

    def test_carregar_cache_completo(self, empresa_service_with_mock, empresa_dict):
        """Testa carregamento completo do cache na inicialização."""
        service = empresa_service_with_mock
        empresa_id = str(empresa_dict["_id"])

        # Mock MongoDB find to return empresas
        service.colecao.find.return_value = [empresa_dict]

        # Call _carregar_cache_completo manually
        service._carregar_cache_completo()

        # Verify memory cache populated
        assert empresa_id in service._cache_empresas
        assert service._cache_empresas[empresa_id] == empresa_dict

        # Verify Redis cache.set_many called
        service.cache.set_many.assert_called_once()


class TestBuscaEmpresa:
    """Testes de busca com cache híbrido (memória → Redis → MongoDB)."""

    def test_buscar_por_id_cache_hit_memory(self, empresa_service_with_mock, empresa_dict):
        """Testa busca com hit no cache de memória."""
        service = empresa_service_with_mock
        empresa_id = str(empresa_dict["_id"])

        # Preload memory cache
        service._cache_empresas[empresa_id] = empresa_dict

        result = service.buscar_por_id(empresa_id)

        assert result == empresa_dict
        # Verify MongoDB NOT called (cache hit)
        service.colecao.find_one.assert_not_called()
        # Verify Redis NOT called (memory hit)
        service.cache.get.assert_not_called()

    def test_buscar_por_id_cache_miss_memory_hit_redis(self, empresa_service_with_mock, empresa_dict):
        """Testa busca com miss em memória, mas hit no Redis."""
        service = empresa_service_with_mock
        empresa_id = str(empresa_dict["_id"])

        # Miss in memory
        service._cache_empresas = {}

        # Hit in Redis (return JSON string)
        service.cache.get.return_value = empresa_dict

        result = service.buscar_por_id(empresa_id)

        # Verify Redis was called
        service.cache.get.assert_called_once_with(f"empresas:{empresa_id}")

        # Verify result correct
        assert result == empresa_dict

        # Verify memory cache updated
        assert service._cache_empresas[empresa_id] == empresa_dict

        # Verify MongoDB NOT called (Redis hit)
        service.colecao.find_one.assert_not_called()

    def test_buscar_por_id_cache_miss_everywhere_fetch_mongodb(self, empresa_service_with_mock, empresa_dict):
        """Testa busca com miss em todos os caches, fetch do MongoDB."""
        service = empresa_service_with_mock
        empresa_id = str(empresa_dict["_id"])

        # Miss in memory
        service._cache_empresas = {}

        # Miss in Redis
        service.cache.get.return_value = None

        # Hit in MongoDB
        service.colecao.find_one.return_value = empresa_dict

        result = service.buscar_por_id(empresa_id)

        # Verify MongoDB was called
        service.colecao.find_one.assert_called_once()

        # Verify result correct
        assert result == empresa_dict

        # Verify BOTH caches updated
        assert service._cache_empresas[empresa_id] == empresa_dict
        service.cache.set.assert_called_once()

    def test_buscar_por_id_not_found(self, empresa_service_with_mock):
        """Testa busca de empresa inexistente."""
        service = empresa_service_with_mock
        empresa_id = str(ObjectId())

        # Miss everywhere
        service._cache_empresas = {}
        service.cache.get.return_value = None
        service.colecao.find_one.return_value = None

        result = service.buscar_por_id(empresa_id)

        assert result is None

    def test_buscar_por_id_invalid_objectid(self, empresa_service_with_mock):
        """Testa busca com ObjectId inválido."""
        service = empresa_service_with_mock

        result = service.buscar_por_id("invalid_id_format")

        assert result is None

    def test_buscar_por_nome_normalizado_exact(self, empresa_service_with_mock, empresa_dict):
        """Testa busca exata por nome normalizado."""
        service = empresa_service_with_mock

        service.colecao.find_one.return_value = empresa_dict

        result = service.buscar_por_nome("Moraes & Santos Consultoria", exato=True)

        assert result == empresa_dict
        # Verify normalized search used
        call_args = service.colecao.find_one.call_args[0][0]
        assert "nome_normalizado" in call_args
        assert call_args["nome_normalizado"] == "moraes & santos consultoria"

    def test_buscar_por_nome_normalizado_partial(self, empresa_service_with_mock, empresa_dict):
        """Testa busca parcial por nome normalizado (regex)."""
        service = empresa_service_with_mock

        service.colecao.find_one.return_value = empresa_dict

        result = service.buscar_por_nome("Moraes", exato=False)

        assert result == empresa_dict
        # Verify regex search used
        call_args = service.colecao.find_one.call_args[0][0]
        assert "nome_normalizado" in call_args
        assert "$regex" in call_args["nome_normalizado"]

    def test_buscar_todas_por_nome(self, empresa_service_with_mock, empresa_dict):
        """Testa busca de múltiplas empresas por nome."""
        service = empresa_service_with_mock

        # 1. Preparamos os dados do Mock
        empresas = [empresa_dict, empresa_dict.copy()]
        mock_cursor = MagicMock()
        # No MongoDB, find() retorna um cursor que pode ser iterado
        mock_cursor.__iter__.return_value = empresas
        # Se o seu código usa .sort(), o sort deve retornar o cursor ou a lista
        mock_cursor.sort.return_value = empresas
        
        service.colecao.find.return_value = mock_cursor

        # --- O PULO DO GATO ---
        # Limpamos as chamadas feitas pelo __init__ (o find({}) do cache)
        service.colecao.find.reset_mock()
        # ----------------------

        # 2. Executamos a ação
        result = service.buscar_todas_por_nome("Moraes")

        # 3. Asserts
        assert len(result) == 2
        # Agora assert_called_once() vai passar, pois resetamos o contador antes da chamada
        service.colecao.find.assert_called_once()
        
        # Dica: Verifique se os argumentos do find foram os que você esperava
        args, kwargs = service.colecao.find.call_args
        assert "moraes" in args[0]['nome_normalizado']['$regex']

    def test_buscar_por_cnpj(self, empresa_service_with_mock, empresa_dict):
        """Testa busca por CNPJ."""
        service = empresa_service_with_mock

        service.colecao.find_one.return_value = empresa_dict

        result = service.buscar_por_cnpj("12.345.678/0001-90")

        assert result == empresa_dict
        # Verify CNPJ cleaned and regex used
        call_args = service.colecao.find_one.call_args[0][0]
        assert "cnpj" in call_args


class TestAutoCadastroEmpresa:
    """Testes de autocadastro de empresas incompletas."""

    def test_obter_ou_criar_incompleta_empresa_existente(self, empresa_service_with_mock, empresa_dict):
        """Testa que empresa existente é reutilizada."""
        service = empresa_service_with_mock

        # Mock find returns existing empresa
        service.colecao.find_one.return_value = empresa_dict

        result = service.obter_ou_criar_incompleta("Moraes & Santos Consultoria")

        assert result == empresa_dict
        # Verify insert NOT called
        service.colecao.insert_one.assert_not_called()

    def test_obter_ou_criar_incompleta_empresa_nova(self, empresa_service_with_mock):
        """Testa criação de empresa incompleta."""
        service = empresa_service_with_mock
        nome_empresa = "Empresa Teste Ltda"

        # Mock not found
        service.colecao.find_one.return_value = None

        # Mock insert
        inserted_id = ObjectId()
        service.colecao.insert_one.return_value = MagicMock(inserted_id=inserted_id)

        result = service.obter_ou_criar_incompleta(nome_empresa)

        assert result['nome'] == nome_empresa
        assert result['incompleto'] is True
        assert result['status'] == StatusEmpresa.EM_CONSTRUCAO.value
        assert result['_id'] == inserted_id

        # Verify insert called
        service.colecao.insert_one.assert_called_once()

        # Verify cnpj NOT included if None (avoid E11000)
        insert_args = service.colecao.insert_one.call_args[0][0]
        assert 'cnpj' not in insert_args

    def test_obter_ou_criar_incompleta_nome_normalizado(self, empresa_service_with_mock):
        """Testa que nome_normalizado é gerado corretamente."""
        service = empresa_service_with_mock
        nome_empresa = "Açúcar & Café Ltda"

        service.colecao.find_one.return_value = None
        inserted_id = ObjectId()
        service.colecao.insert_one.return_value = MagicMock(inserted_id=inserted_id)

        result = service.obter_ou_criar_incompleta(nome_empresa)

        # Verify insert was called
        insert_args = service.colecao.insert_one.call_args[0][0]

        # nome_normalizado should be lowercase without accents
        assert insert_args['nome_normalizado'] == "acucar & cafe ltda"

    def test_obter_ou_criar_incompleta_duplicata_retry(self, empresa_service_with_mock, empresa_dict):
        """Testa retry após erro de duplicata E11000."""
        service = empresa_service_with_mock
        nome_empresa = "Moraes & Santos Consultoria"

        # First call: not found
        # Second call after insert error: found
        service.colecao.find_one.side_effect = [None, empresa_dict]

        # Mock E11000 duplicate key error
        from pymongo.errors import DuplicateKeyError
        service.colecao.insert_one.side_effect = DuplicateKeyError("E11000 duplicate key error")

        result = service.obter_ou_criar_incompleta(nome_empresa)

        # Should return existing empresa after retry
        assert result == empresa_dict

        # Verify find_one called twice (initial + retry)
        assert service.colecao.find_one.call_count == 2


class TestCacheInvalidacao:
    """Testes de invalidação de cache."""

    def test_invalidar_cache_clears_memory(self, empresa_service_with_mock, empresa_dict):
        """Testa que invalidação limpa cache de memória."""
        service = empresa_service_with_mock
        empresa_id = str(empresa_dict["_id"])

        # Populate cache
        service._cache_empresas[empresa_id] = empresa_dict

        # Mock _carregar_cache_completo to avoid reload
        with patch.object(service, '_carregar_cache_completo'):
            service._invalidar_cache()

        # Verify memory cache cleared
        assert len(service._cache_empresas) == 0

    def test_invalidar_cache_clears_redis(self, empresa_service_with_mock):
        """Testa que invalidação limpa cache Redis."""
        service = empresa_service_with_mock

        service.cache.invalidate.return_value = 5

        # Mock _carregar_cache_completo to avoid reload
        with patch.object(service, '_carregar_cache_completo'):
            service._invalidar_cache()

        # Verify Redis invalidate called
        service.cache.invalidate.assert_called_once_with("empresas:*")

    def test_invalidar_cache_reloads_after_clearing(self, empresa_service_with_mock):
        """Testa que cache é recarregado após invalidação."""
        service = empresa_service_with_mock

        service.cache.invalidate.return_value = 0

        with patch.object(service, '_carregar_cache_completo') as mock_reload:
            service._invalidar_cache()

            # Verify reload called
            mock_reload.assert_called_once()

    def test_atualizar_invalida_cache(self, empresa_service_with_mock):
        """Testa que atualização invalida cache."""
        service = empresa_service_with_mock
        empresa_id = str(ObjectId())

        service.colecao.update_one.return_value = MagicMock(modified_count=1)

        with patch.object(service, '_invalidar_cache') as mock_invalidate:
            service.atualizar(empresa_id, {"nome": "Novo Nome"})

            # Verify invalidation called
            mock_invalidate.assert_called_once()


class TestCRUDOperacoes:
    """Testes de operações CRUD."""

    def test_criar_empresa_sucesso(self, empresa_service_with_mock):
        """Testa criação de empresa completa."""
        service = empresa_service_with_mock

        # Mock not existing
        service.colecao.find_one.return_value = None

        inserted_id = ObjectId()
        service.colecao.insert_one.return_value = MagicMock(inserted_id=inserted_id)

        with patch.object(service, '_invalidar_cache'):
            dados = {
                "nome": "Nova Empresa Ltda",
                "cnpj": "98.765.432/0001-10",
                "atividade": "Comércio"
            }

            result = service.criar_empresa(dados)

            assert result == str(inserted_id)
            service.colecao.insert_one.assert_called_once()

    def test_criar_empresa_ja_existente(self, empresa_service_with_mock, empresa_dict):
        """Testa tentativa de criar empresa que já existe."""
        service = empresa_service_with_mock

        # Mock existing empresa
        service.colecao.find_one.return_value = empresa_dict

        dados = {"nome": "Moraes & Santos Consultoria"}

        result = service.criar_empresa(dados)

        # Should return existing ID
        assert result == str(empresa_dict["_id"])
        # Should NOT insert
        service.colecao.insert_one.assert_not_called()

    def test_criar_empresa_nome_obrigatorio(self, empresa_service_with_mock):
        """Testa que nome é obrigatório para criar empresa."""
        service = empresa_service_with_mock

        dados = {"cnpj": "12.345.678/0001-90"}

        result = service.criar_empresa(dados)

        assert result is None

    def test_atualizar_empresa_sucesso(self, empresa_service_with_mock):
        """Testa atualização de empresa."""
        service = empresa_service_with_mock
        empresa_id = str(ObjectId())

        service.colecao.update_one.return_value = MagicMock(modified_count=1)

        with patch.object(service, '_invalidar_cache'):
            alteracoes = {"telefone": "(11) 8888-8888"}

            result = service.atualizar(empresa_id, alteracoes)

            assert result is True
            service.colecao.update_one.assert_called_once()

    def test_atualizar_empresa_atualiza_nome_normalizado(self, empresa_service_with_mock):
        """Testa que atualizar nome também atualiza nome_normalizado."""
        service = empresa_service_with_mock
        empresa_id = str(ObjectId())

        service.colecao.update_one.return_value = MagicMock(modified_count=1)

        with patch.object(service, '_invalidar_cache'):
            alteracoes = {"nome": "Novo Nome Ltda"}

            service.atualizar(empresa_id, alteracoes)

            # Verify nome_normalizado added
            call_args = service.colecao.update_one.call_args[0][1]
            assert "nome_normalizado" in call_args["$set"]
            assert call_args["$set"]["nome_normalizado"] == "novo nome ltda"

    def test_atualizar_cnpj(self, empresa_service_with_mock):
        """Testa atualização de CNPJ."""
        service = empresa_service_with_mock
        empresa_id = str(ObjectId())

        service.colecao.update_one.return_value = MagicMock(modified_count=1)

        with patch.object(service, '_invalidar_cache'):
            result = service.atualizar_cnpj(empresa_id, "12.345.678/0001-90")

            assert result is True

            # Verify CNPJ cleaned
            call_args = service.colecao.update_one.call_args[0][1]
            assert call_args["$set"]["cnpj"] == "12345678000190"

    def test_salvar_ou_atualizar_upsert(self, empresa_service_with_mock, empresa_dict):
        """Testa upsert de empresa."""
        service = empresa_service_with_mock

        # Mock upsert (inserted)
        service.colecao.update_one.return_value = MagicMock(
            upserted_id=ObjectId(),
            modified_count=0
        )

        with patch.object(service, '_invalidar_cache'):
            result = service.salvar_ou_atualizar(empresa_dict)

            assert result is True
            service.colecao.update_one.assert_called_once()

    def test_listar_todos_paginacao(self, empresa_service_with_mock, empresa_dict):
        """Testa listagem com paginação."""
        service = empresa_service_with_mock

        empresas = [empresa_dict, empresa_dict.copy()]
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = empresas

        service.colecao.find.return_value = mock_cursor
        service.colecao.count_documents.return_value = 10

        result = service.listar_todos(skip=0, limit=2)

        assert len(result["dados"]) == 2
        assert result["total"] == 10
        assert result["pagina_atual"] == 1

    def test_listar_incompletas(self, empresa_service_with_mock, empresa_incompleta_dict):
        """Testa listagem de empresas incompletas."""
        service = empresa_service_with_mock

        empresas = [empresa_incompleta_dict]
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = empresas

        service.colecao.find.return_value = mock_cursor

        result = service.listar_incompletas()

        assert len(result) == 1
        assert result[0]["incompleto"] is True

    def test_listar_por_status(self, empresa_service_with_mock, empresa_dict):
        """Testa listagem por status."""
        service = empresa_service_with_mock

        empresas = [empresa_dict]
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = empresas

        service.colecao.find.return_value = mock_cursor

        result = service.listar_por_status("ativa")

        assert len(result) == 1
        service.colecao.find.assert_any_call({"status": "ativa"})
    def test_listar_ativos(self, empresa_service_with_mock, empresa_dict):
        """Testa listagem de empresas ativas."""
        service = empresa_service_with_mock

        empresas = [empresa_dict]
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = empresas

        service.colecao.find.return_value = mock_cursor

        result = service.listar_ativos()

        assert len(result) == 1
        # Verify filter for both "ativa" and "ativo"
        call_args = service.colecao.find.call_args[0][0]
        assert "$in" in call_args["status"]
        assert "ativa" in call_args["status"]["$in"]
        assert "ativo" in call_args["status"]["$in"]

    def test_alterar_status(self, empresa_service_with_mock):
        """Testa alteração de status."""
        service = empresa_service_with_mock
        empresa_id = str(ObjectId())

        service.colecao.update_one.return_value = MagicMock(modified_count=1)

        with patch.object(service, '_invalidar_cache'):
            result = service.alterar_status(empresa_id, StatusEmpresa.INATIVA.value)

            assert result is True

    def test_alterar_status_para_ativa_marca_completa(self, empresa_service_with_mock):
        """Testa que mudar para 'ativa' marca como completa."""
        service = empresa_service_with_mock
        empresa_id = str(ObjectId())

        service.colecao.update_one.return_value = MagicMock(modified_count=1)

        with patch.object(service, '_invalidar_cache'):
            service.alterar_status(empresa_id, StatusEmpresa.ATIVA.value)

            # Verify incompleto set to False
            call_args = service.colecao.update_one.call_args[0][1]
            assert call_args["$set"]["incompleto"] is False

    def test_obter_estatisticas(self, empresa_service_with_mock):
        """Testa obtenção de estatísticas."""
        service = empresa_service_with_mock

        # Mock counts
        service.colecao.count_documents.side_effect = [100, 80, 20, 90]

        result = service.obter_estatisticas()

        assert result["total_empresas"] == 100
        assert result["empresas_completas"] == 80
        assert result["empresas_incompletas"] == 20
        assert result["empresas_ativas"] == 90

    def test_remover_campo_id_empresa(self, empresa_service_with_mock):
        """Testa remoção de campo legado id_empresa."""
        service = empresa_service_with_mock

        service.colecao.update_many.return_value = MagicMock(modified_count=5)

        result = service.remover_campo_id_empresa()

        assert result == 5
        service.colecao.update_many.assert_called_once()


class TestMongoDB_Indisponivel:
    """Testes quando MongoDB não está disponível."""

    def test_buscar_por_id_mongodb_indisponivel(self):
        """Testa busca quando MongoDB não está disponível."""
        with patch('src.services.empresa_service.MONGODB_DISPONIVEL', False):
            service = EmpresaService()

            result = service.buscar_por_id("507f1f77bcf86cd799439011")

            assert result is None

    def test_criar_empresa_mongodb_indisponivel(self):
        """Testa criação quando MongoDB não está disponível."""
        with patch('src.services.empresa_service.MONGODB_DISPONIVEL', False):
            service = EmpresaService()

            dados = {"nome": "Empresa Teste"}
            result = service.criar_empresa(dados)

            assert result is None

    def test_listar_todos_mongodb_indisponivel(self):
        """Testa listagem quando MongoDB não está disponível."""
        with patch('src.services.empresa_service.MONGODB_DISPONIVEL', False):
            service = EmpresaService()

            result = service.listar_todos()

            assert result["dados"] == []
            assert result["total"] == 0
