"""
Unit tests for DiretorioService cache-aside + invalidação por escrita.
"""
import os
import pytest
from unittest.mock import MagicMock, patch
from bson import ObjectId

from src.services.diretorio_service import DiretorioService
from src.services import cache_keys


class _FakeCache:
    def __init__(self):
        self.store = {}
    def get(self, key): return self.store.get(key)
    def set(self, key, value, ttl=300): self.store[key] = value
    def set_many(self, data, ttl=300): self.store.update(data)
    def invalidate(self, pattern):
        import re
        regex = re.compile(f"^{pattern.replace('*', '.*')}$")
        keys = [k for k in self.store if regex.match(k)]
        for k in keys: del self.store[k]
        return len(keys)


def _doc(nome="CACOAL"):
    return {"_id": ObjectId(), "nome": nome, "nome_normalizado": cache_keys.normalizar_nome(nome), "status": "ativo", "versao": 1}


def _make_service(collection, cache):
    with patch('src.services.diretorio_service.MONGODB_DISPONIVEL', True), \
         patch.dict(os.environ, {'CACHE_TTL': '300'}), \
         patch('src.services.diretorio_service.cache_service', cache), \
         patch('src.services.diretorio_service.dotenv.get_key') as md, \
         patch('src.services.diretorio_service.MongoDBConnectionPool') as mpc:
        md.side_effect = lambda p, k: os.environ.get(k)
        mock_db = MagicMock()
        mock_db.__getitem__.return_value = collection
        mock_pi = MagicMock(); mock_pi.get_database.return_value = mock_db
        mock_pi.get_client.return_value = MagicMock()
        mpc.return_value = mock_pi
        svc = DiretorioService(collection_name="diretorios")
        svc._cache_diretorios = {}
        svc._cache_por_contrato = {}
        return svc


class TestDiretorioCacheAside:
    def test_buscar_por_id_cache_miss_popula_redis(self):
        cache = _FakeCache()
        doc = _doc()
        collection = MagicMock()
        collection.find.return_value = []
        collection.find_one.return_value = doc
        collection.create_index.return_value = "idx"

        svc = _make_service(collection, cache)
        assert svc.buscar_por_id(str(doc["_id"])) == doc
        assert cache_keys.diretorio_key(str(doc["_id"])) in cache.store

    def test_buscar_por_id_redis_hit_evita_mongo(self):
        cache = _FakeCache()
        doc = _doc()
        collection = MagicMock()
        collection.find.return_value = []
        collection.create_index.return_value = "idx"
        cache.store[cache_keys.diretorio_key(str(doc["_id"]))] = doc

        svc = _make_service(collection, cache)
        svc.buscar_por_id(str(doc["_id"]))
        collection.find_one.assert_not_called()


class TestDiretorioInvalidacaoAntiStale:
    def test_atualizar_invalida_e_relê_do_banco(self):
        cache = _FakeCache()
        did = str(ObjectId())
        old = {"_id": ObjectId(did), "nome": "A", "status": "ativo"}
        new = dict(old); new["status"] = "inativo"

        collection = MagicMock()
        collection.find.return_value = []
        collection.find_one.return_value = old
        collection.create_index.return_value = "idx"
        collection.update_one.return_value = MagicMock(modified_count=1, matched_count=1)

        svc = _make_service(collection, cache)
        svc.buscar_por_id(did)

        collection.find_one.return_value = new
        assert svc.atualizar(did, {"status": "inativo"}) is True
        assert cache_keys.diretorio_key(did) not in cache.store
        assert svc.buscar_por_id(did)["status"] == "inativo"

    def test_invalidar_cache_direcionada_remove_so_a_chave(self):
        cache = _FakeCache()
        a, b = str(ObjectId()), str(ObjectId())
        cache.store[cache_keys.diretorio_key(a)] = _doc()
        cache.store[cache_keys.diretorio_key(b)] = _doc()

        svc = _make_service(MagicMock(), cache)
        svc._invalidar_cache(registro_id=a)
        assert cache_keys.diretorio_key(a) not in cache.store
        assert cache_keys.diretorio_key(b) in cache.store

    def test_invalidar_cache_nao_recarrega_colecao(self):
        cache = _FakeCache()
        svc = _make_service(MagicMock(), cache)
        with patch.object(svc, '_carregar_cache_completo') as mock_reload:
            svc._invalidar_cache(registro_id="x")
            mock_reload.assert_not_called()

    def test_invalidacao_por_diretorio_id_limpa_cache_por_contrato_anti_stale(self):
        """
        Anti-stale (bug crítico): `_cache_por_contrato` é indexado por
        `contrato_id`, mas a invalidação por ID recebe o `diretorio_id`.
        Usar `pop(diretorio_id)` nesse dict não remove a entrada (chaves
        diferentes), deixando dado velho. O fix usa `clear()` no dict
        secundário (pequeno), então um `marcar_inativo` deve fazer
        `buscar_por_contrato_id` retornar o dado NOVO.
        """
        cache = _FakeCache()
        cid = str(ObjectId())          # contrato_id (chave do dict secundário)
        did = str(ObjectId())          # diretorio_id (chave do dict primário)

        # Diretório ativo indexado sob o contrato_id no cache secundário
        doc_stale = {"_id": ObjectId(did), "nome": "CACOAL", "status": "ativo", "contrato_id": ObjectId(cid)}
        doc_novo = dict(doc_stale); doc_novo["status"] = "inativo"

        collection = MagicMock()
        collection.find.return_value = []
        collection.find_one.return_value = None          # buscar_por_contrato_id irá ao Mongo
        collection.create_index.return_value = "idx"
        collection.update_one.return_value = MagicMock(modified_count=1, matched_count=1)
        collection.count_documents.return_value = 0  # sem funcionários vinculados → pode inativar

        svc = _make_service(collection, cache)
        # Pré-popula o cache secundário com dado STALE (como se um hit anterior tivesse gravado)
        svc._cache_por_contrato[cid] = doc_stale
        svc._cache_diretorios[did] = doc_stale

        # Mongo retorna o dado novo (já inativado) para buscar_por_contrato_id
        collection.find_one.return_value = doc_novo

        # marcar_inativo(diretorio_id) → deve invalidar o secundário
        assert svc.marcar_inativo(did) is True
        # Após a invalidação, o dict secundário não pode entregar o stale
        assert cid not in svc._cache_por_contrato

        # buscar_por_contrato_id deve reler do Mongo e devolver o dado NOVO
        assert svc.buscar_por_contrato_id(cid)["status"] == "inativo"
        assert svc._cache_por_contrato[cid]["status"] == "inativo"
