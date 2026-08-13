"""
Unit tests for GrupoWhatsAppService — migração do cache nome→JID para Redis.
"""
import os
import pytest
from unittest.mock import MagicMock, patch

from src.services.grupo_whatsapp_service import GrupoWhatsAppService
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


def _make_service(collection, cache):
    with patch('src.services.grupo_whatsapp_service.MONGODB_DISPONIVEL', True), \
         patch.dict(os.environ, {'CACHE_TTL': '300'}), \
         patch('src.services.grupo_whatsapp_service.cache_service', cache), \
         patch('src.services.grupo_whatsapp_service.dotenv.get_key') as md, \
         patch('src.services.grupo_whatsapp_service.MongoDBConnectionPool') as mpc:
        md.side_effect = lambda p, k: os.environ.get(k)
        mock_db = MagicMock()
        mock_db.__getitem__.return_value = collection
        mock_pi = MagicMock(); mock_pi.get_database.return_value = mock_db
        mpc.return_value = mock_pi
        return GrupoWhatsAppService(collection_name="grupos_whatsapp")


class TestGrupoWhatsAppRedisCache:
    def test_obter_jid_por_nome_redis_hit_pula_cache_local_e_mongo(self):
        cache = _FakeCache()
        device = "WhatsApp-Alefe"
        nome = "Grupo A"
        redis_key = cache_keys.grupo_wa_key(device, cache_keys.normalizar_nome(nome))
        cache.store[redis_key] = "123456@g.us"

        collection = MagicMock()
        collection.find.return_value = []  # cache local vazio
        collection.create_index.return_value = "idx"

        svc = _make_service(collection, cache)
        jid = svc.obter_jid_por_nome(nome, device)

        assert jid == "123456@g.us"
        # Hit no Redis não precisou consultar o banco
        collection.find_one.assert_not_called()

    def test_obter_jid_por_nome_cache_miss_popula_redis(self):
        cache = _FakeCache()
        device = "WhatsApp-Alefe"

        grupo = {"nome": "Grupo A", "nome_normalizado": "grupo a", "jid": "999@g.us", "whatsapp_device_id": device, "status": "ativo"}
        collection = MagicMock()
        collection.find.return_value = [grupo]  # cache local
        collection.find_one.return_value = grupo
        collection.create_index.return_value = "idx"

        svc = _make_service(collection, cache)
        jid = svc.obter_jid_por_nome("Grupo A", device)
        assert jid == "999@g.us"

        redis_key = cache_keys.grupo_wa_key(device, "grupo a")
        assert cache.store[redis_key] == "999@g.us"

    def test_invalidar_cache_invalida_redis(self):
        cache = _FakeCache()
        cache.store["grupos_wa:WhatsApp-Alefe:grupo a"] = "123@g.us"
        cache.store["grupos_wa:WhatsApp-B:outro"] = "456@g.us"
        collection = MagicMock()
        collection.create_index.return_value = "idx"

        svc = _make_service(collection, cache)
        svc._invalidar_cache()

        assert cache.store == {}  # prefixo grupos_wa:* invalidado
