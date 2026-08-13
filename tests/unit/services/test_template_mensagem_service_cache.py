"""
Unit tests for TemplateMensagemService cache-aside (dict local → Redis).
"""
import os
import pytest
from unittest.mock import MagicMock, patch
from bson import ObjectId

from src.services.template_mensagem_service import TemplateMensagemService
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


def _template(nome="Holerite Email"):
    return {"_id": ObjectId(), "nome": nome, "nome_normalizado": cache_keys.normalizar_nome(nome), "status": "ativo", "tipo": "email", "corpo_mensagem": "Olá {{nome}}", "is_padrao": True, "versao": 1}


def _make_service(collection, cache):
    with patch('src.services.template_mensagem_service.MONGODB_DISPONIVEL', True), \
         patch.dict(os.environ, {'CACHE_TTL': '300'}), \
         patch('src.services.template_mensagem_service.cache_service', cache), \
         patch('src.services.template_mensagem_service.dotenv.get_key') as md, \
         patch('src.services.template_mensagem_service.MongoDBConnectionPool') as mpc:
        md.side_effect = lambda p, k: os.environ.get(k)
        mock_db = MagicMock()
        mock_db.__getitem__.return_value = collection
        mock_db.get_collection.return_value = collection
        mock_pi = MagicMock(); mock_pi.get_database.return_value = mock_db
        mpc.return_value = mock_pi
        svc = TemplateMensagemService(collection_name="templates_mensagens")
        svc._cache_templates = {}
        return svc


class TestTemplateCacheAside:
    def test_buscar_por_id_cache_miss_popula_redis(self):
        cache = _FakeCache()
        template = _template()
        collection = MagicMock()
        collection.find_one.return_value = template
        collection.count_documents.return_value = 1
        collection.create_index.return_value = "idx"

        svc = _make_service(collection, cache)
        assert svc.buscar_por_id(str(template["_id"])) == template
        assert cache_keys.template_key(str(template["_id"])) in cache.store

    def test_buscar_por_id_redis_hit_evita_mongo(self):
        cache = _FakeCache()
        template = _template()
        collection = MagicMock()
        collection.count_documents.return_value = 1
        cache.store[cache_keys.template_key(str(template["_id"]))] = template

        svc = _make_service(collection, cache)
        collection.reset_mock()  # init já consultou find_one p/ templates padrão
        svc.buscar_por_id(str(template["_id"]))
        collection.find_one.assert_not_called()

    def test_buscar_padrao_por_tipo_cache_aside(self):
        cache = _FakeCache()
        template = _template()
        collection = MagicMock()
        collection.find_one.return_value = template
        collection.count_documents.return_value = 1

        svc = _make_service(collection, cache)
        assert svc.buscar_padrao_por_tipo("email") == template
        assert cache_keys.template_tipo_key("email") in cache.store

    def test_atualizar_invalida_redis(self):
        cache = _FakeCache()
        tid = str(ObjectId())
        cache.store[cache_keys.template_key(tid)] = _template()
        cache.store["templates:all"] = [_template()]

        collection = MagicMock()
        collection.count_documents.return_value = 1
        collection.update_one.return_value = MagicMock(modified_count=1, matched_count=1)
        collection.find_one.return_value = _template()

        svc = _make_service(collection, cache)
        assert svc.atualizar(tid, {"nome": "Novo"}) is True
        # Prefixo templates:* invalidado → nada stale
        assert cache_keys.template_key(tid) not in cache.store
        assert "templates:all" not in cache.store
