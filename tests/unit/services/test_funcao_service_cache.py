"""
Unit tests for FuncaoService cache-aside + invalidação por escrita.

Cobre o comportamento anti-*stale* (escreve → invalida → relê do banco) e o
cache-aside real (hit no Redis evita query no MongoDB).
"""
import os
import pytest
from unittest.mock import MagicMock, patch
from bson import ObjectId

from src.services.funcao_service import FuncaoService
from src.services import cache_keys


def _funcao_doc(nome="Analista", funcao_id=None):
    return {
        "_id": funcao_id or ObjectId(),
        "nome": nome,
        "nome_normalizado": cache_keys.normalizar_nome(nome),
        "status": "ativo",
        "versao": 1,
    }


@pytest.fixture
def cache_store():
    """Cache Redis/memória mockado com armazenamento real (in-memory dict)."""
    store = {}
    hits = {"count": 0}

    class FakeCache:
        def get(self, key):
            hits["count"] += 1
            self.last_get = key
            return store.get(key)

        def set(self, key, value, ttl=300):
            store[key] = value

        def set_many(self, data, ttl=300):
            store.update(data)

        def invalidate(self, pattern):
            import re
            regex = re.compile(f"^{pattern.replace('*', '.*')}$")
            keys = [k for k in store if regex.match(k)]
            for k in keys:
                del store[k]
            return len(keys)

        def get_store(self):
            return store

    return FakeCache()


@pytest.fixture
def cache_store_as_attr(cache_store):
    """Exibe a store para inspeção."""
    return cache_store.get_store()


def _make_service(collection, cache):
    """Builds FuncaoService with mocked Mongo + injected cache."""
    with patch('src.services.funcao_service.MONGODB_DISPONIVEL', True), \
         patch.dict(os.environ, {'CACHE_TTL': '300'}), \
         patch('src.services.funcao_service.cache_service', cache), \
         patch('src.services.funcao_service.dotenv.get_key') as mock_dotenv, \
         patch('src.services.funcao_service.MongoDBConnectionPool') as mock_pool_class:

        mock_dotenv.side_effect = lambda path, key: os.environ.get(key)

        mock_db = MagicMock()
        mock_db.__getitem__.return_value = collection
        mock_db.get_collection.return_value = collection
        mock_pool_instance = MagicMock()
        mock_pool_instance.get_database.return_value = mock_db
        mock_pool_instance.get_client.return_value = MagicMock()
        mock_pool_class.return_value = mock_pool_instance

        service = FuncaoService(collection_name="funcoes")
        service._cache_funcoes = {}
        return service


class TestFuncaoCacheAside:
    def test_buscar_por_id_cache_miss_popula_redis(self, cache_store):
        funcao = _funcao_doc(nome="Analista")
        collection = MagicMock()
        collection.find.return_value = []
        collection.find_one.return_value = funcao
        collection.insert_one.return_value = MagicMock(inserted_id=ObjectId())
        collection.create_index.return_value = "idx"

        service = _make_service(collection, cache_store)
        result = service.buscar_por_id(str(funcao["_id"]))

        assert result == funcao
        # Populou Redis com a chave centralizada
        store = cache_store.get_store()
        assert cache_keys.funcao_key(str(funcao["_id"])) in store

    def test_buscar_por_id_redis_hit_evita_mongo(self, cache_store):
        funcao = _funcao_doc(nome="Analista")
        collection = MagicMock()
        collection.find.return_value = []
        # Pré-popular cache com dados atualizados (simula outro processo)
        cache_store.get_store()[cache_keys.funcao_key(str(funcao["_id"]))] = funcao

        service = _make_service(collection, cache_store)
        service.buscar_por_id(str(funcao["_id"]))

        # Hit no Redis → NÃO deve consultar o Mongo
        collection.find_one.assert_not_called()


class TestFuncaoInvalidacaoAntiStale:
    def test_atualizar_campos_invalida_e_relê_do_banco(self, cache_store):
        """Escreve → invalida → relê do banco (NÃO retorna dado velho do cache)."""
        funcao_id = str(ObjectId())
        doc_old = _funcao_doc(nome="Analista", funcao_id=ObjectId(funcao_id))
        doc_new = dict(doc_old)
        doc_new["status"] = "inativo"

        collection = MagicMock()
        collection.find.return_value = []
        # cache miss via Redis (nada), mas Mongo retorna o doc
        collection.find_one.return_value = doc_old
        collection.update_one.return_value = MagicMock(modified_count=1, matched_count=1)
        collection.create_index.return_value = "idx"

        service = _make_service(collection, cache_store)

        # 1) Primeira leitura populates cache com o documento antigo
        service.buscar_por_id(funcao_id)

        # 2) Atualização escreve no Mongo e INVALIDA a chave por ID
        collection.find_one.return_value = doc_new  # próxima leitura vê o novo
        assert service.atualizar_campos(funcao_id, {"status": "inativo"}) is True

        # Chave específica invalidada (destruída do cache)
        assert cache_keys.funcao_key(funcao_id) not in cache_store.get_store()

        # 3) Relê → cache miss → busca no Mongo → retorna dado NOVO
        result = service.buscar_por_id(funcao_id)
        assert result["status"] == "inativo"  # NÃO o status antigo do cache

    def test_invalidar_cache_direcionada_remove_so_a_chave(self, cache_store):
        fid_a = str(ObjectId())
        fid_b = str(ObjectId())
        store = cache_store.get_store()
        store[cache_keys.funcao_key(fid_a)] = _funcao_doc(funcao_id=ObjectId(fid_a))
        store[cache_keys.funcao_key(fid_b)] = _funcao_doc(nome="Outra", funcao_id=ObjectId(fid_b))

        collection = MagicMock()
        service = _make_service(collection, cache_store)

        service._invalidar_cache(registro_id=fid_a)

        # Só a chave de A sumiu; B permanece
        assert cache_keys.funcao_key(fid_a) not in store
        assert cache_keys.funcao_key(fid_b) in store

    def test_invalidar_cache_nao_recarrega_colecao_do_mongo(self, cache_store):
        """Etapa 3: invalidação NÃO faz mais full-reload da coleção."""
        collection = MagicMock()
        service = _make_service(collection, cache_store)

        with patch.object(service, '_carregar_cache_completo') as mock_reload:
            service._invalidar_cache(registro_id="xyz")
            mock_reload.assert_not_called()
