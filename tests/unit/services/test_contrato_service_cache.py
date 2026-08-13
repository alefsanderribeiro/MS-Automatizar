"""
Unit tests for ContratoService cache-aside + invalidação por escrita.
"""
import os
import pytest
from unittest.mock import MagicMock, patch
from bson import ObjectId

from src.services.contrato_service import ContratoService
from src.services import cache_keys


class _FakeCache:
    def __init__(self):
        self.store = {}
        self.calls = []
    def get(self, key):
        self.calls.append(("get", key)); return self.store.get(key)
    def set(self, key, value, ttl=300):
        self.calls.append(("set", key)); self.store[key] = value
    def set_many(self, data, ttl=300): self.store.update(data)
    def invalidate(self, pattern):
        import re
        self.calls.append(("invalidate", pattern))
        regex = re.compile(f"^{pattern.replace('*', '.*')}$")
        keys = [k for k in self.store if regex.match(k)]
        for k in keys: del self.store[k]
        return len(keys)


def _doc(nome="MS SERVIÇOS"):
    return {"_id": ObjectId(), "nome": nome, "nome_normalizado": cache_keys.normalizar_nome(nome), "status": "ativo", "versao": 1}


def _make_service(collection, cache):
    with patch('src.services.contrato_service.MONGODB_DISPONIVEL', True), \
         patch.dict(os.environ, {'CACHE_TTL': '300'}), \
         patch('src.services.contrato_service.cache_service', cache), \
         patch('src.services.contrato_service.dotenv.get_key') as md, \
         patch('src.services.contrato_service.MongoDBConnectionPool') as mpc:
        md.side_effect = lambda p, k: os.environ.get(k)
        mock_db = MagicMock()
        mock_db.__getitem__.return_value = collection
        mock_pi = MagicMock(); mock_pi.get_database.return_value = mock_db
        mpc.return_value = mock_pi
        svc = ContratoService(collection_name="contratos")
        svc._cache_contratos = {}
        return svc


class TestContratoCacheAside:
    def test_buscar_por_id_cache_miss_popula_redis(self):
        cache = _FakeCache()
        doc = _doc()
        collection = MagicMock()
        collection.find.return_value = []
        collection.find_one.return_value = doc
        collection.create_index.return_value = "idx"

        svc = _make_service(collection, cache)
        result = svc.buscar_por_id(str(doc["_id"]))
        assert result == doc
        assert cache_keys.contrato_key(str(doc["_id"])) in cache.store

    def test_buscar_por_id_redis_hit_evita_mongo(self):
        cache = _FakeCache()
        doc = _doc()
        collection = MagicMock()
        collection.find.return_value = []
        cache.store[cache_keys.contrato_key(str(doc["_id"]))] = doc

        svc = _make_service(collection, cache)
        svc.buscar_por_id(str(doc["_id"]))
        collection.find_one.assert_not_called()


class TestContratoInvalidacaoAntiStale:
    def test_atualizar_campos_invalida_e_relê_do_banco(self):
        cache = _FakeCache()
        cid = str(ObjectId())
        old = {"_id": ObjectId(cid), "nome": "A", "status": "ativo"}
        new = dict(old); new["status"] = "inativo"

        collection = MagicMock()
        collection.find.return_value = []
        collection.find_one.return_value = old
        collection.create_index.return_value = "idx"
        collection.update_one.return_value = MagicMock(modified_count=1, matched_count=1)

        svc = _make_service(collection, cache)
        svc.buscar_por_id(cid)  # popula cache com old

        collection.find_one.return_value = new
        assert svc.atualizar_campos(cid, {"status": "inativo"}) is True

        assert cache_keys.contrato_key(cid) not in cache.store
        assert svc.buscar_por_id(cid)["status"] == "inativo"

    def test_invalidar_cache_direcionada_remove_so_a_chave(self):
        cache = _FakeCache()
        a, b = str(ObjectId()), str(ObjectId())
        cache.store[cache_keys.contrato_key(a)] = _doc()
        cache.store[cache_keys.contrato_key(b)] = _doc()

        svc = _make_service(MagicMock(), cache)
        svc._invalidar_cache(registro_id=a)
        assert cache_keys.contrato_key(a) not in cache.store
        assert cache_keys.contrato_key(b) in cache.store

    def test_invalidar_cache_nao_recarrega_colecao(self):
        cache = _FakeCache()
        svc = _make_service(MagicMock(), cache)
        with patch.object(svc, '_carregar_cache_completo') as mock_reload:
            svc._invalidar_cache(registro_id="x")
            mock_reload.assert_not_called()
