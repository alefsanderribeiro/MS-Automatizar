"""
Unit tests for FeriadoService cache (novo — Etapa 2.3) + invalidação agrupada.
"""
import os
from datetime import date, datetime, timezone
import pytest
from unittest.mock import MagicMock, patch
from bson import ObjectId

from src.services.feriado_service import FeriadoService
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


def _feriado(data=date(2025, 1, 1), desc="Confraternização"):
    return {
        "_id": ObjectId(),
        "data": datetime(data.year, data.month, data.day, tzinfo=timezone.utc),
        "descricao": desc,
        "status": "ativo",
        "tipo": "nacional",
    }


def _make_service(collection, cache):
    with patch('src.services.feriado_service.MONGODB_DISPONIVEL', True), \
         patch.dict(os.environ, {'CACHE_TTL': '300'}), \
         patch('src.services.feriado_service.cache_service', cache), \
         patch('src.services.feriado_service.dotenv.get_key') as md, \
         patch('src.services.feriado_service.MongoDBConnectionPool') as mpc:
        md.side_effect = lambda p, k: os.environ.get(k)
        mock_db = MagicMock()
        mock_db.__getitem__.return_value = collection
        mock_pi = MagicMock(); mock_pi.get_database.return_value = mock_db
        mpc.return_value = mock_pi
        return FeriadoService(collection_name="feriados")


class TestFeriadoCache:
    def test_listar_por_periodo_cache_miss_popula_redis(self):
        cache = _FakeCache()
        feriado = _feriado()
        collection = MagicMock()
        # cursor que suporta .sort("data", ASCENDING) e iteração
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.__iter__.return_value = iter([feriado])
        collection.find.return_value = cursor
        collection.create_index.return_value = "idx"

        svc = _make_service(collection, cache)
        key = cache_keys.feriado_periodo_key(date(2025, 1, 1), date(2025, 12, 31))
        result = svc.listar_por_periodo(date(2025, 1, 1), date(2025, 12, 31))

        assert result == [feriado]
        assert key in cache.store  # cacheou o período no Redis

    def test_listar_por_periodo_redis_hit_evita_mongo(self):
        cache = _FakeCache()
        feriado = _feriado()
        collection = MagicMock()
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.__iter__.return_value = iter([feriado])
        collection.find.return_value = cursor
        collection.create_index.return_value = "idx"

        cache_key = cache_keys.feriado_periodo_key(date(2025, 1, 1), date(2025, 12, 31))
        cache.store[cache_key] = [feriado]

        svc = _make_service(collection, cache)
        svc.listar_por_periodo(date(2025, 1, 1), date(2025, 12, 31))
        # Hit no Redis → NÃO consultou o Mongo
        collection.find.assert_not_called()

    def test_criar_invalida_prefixo_feriados(self):
        cache = _FakeCache()
        cache.store["feriados:2025"] = [_feriado()]
        cache.store["feriados:periodo:2025-01-01_2025-12-31"] = [_feriado()]

        collection = MagicMock()
        collection.insert_one.return_value = MagicMock(inserted_id=ObjectId())
        collection.create_index.return_value = "idx"

        svc = _make_service(collection, cache)
        from unittest.mock import MagicMock as MM
        modelo = MM()
        modelo.to_mongo_insert.return_value = {"data": datetime(2025, 2, 1, tzinfo=timezone.utc), "descricao": "Novo", "status": "ativo"}
        modelo.data = date(2025, 2, 1)
        modelo.descricao = "Novo"

        svc.criar(modelo)

        # Prefixo feriados:* invalidado → todas as chaves removidas
        assert "feriados:2025" not in cache.store
        assert "feriados:periodo:2025-01-01_2025-12-31" not in cache.store

    def test_buscar_por_data_cache_aside(self):
        cache = _FakeCache()
        feriado = _feriado(date(2025, 1, 1))
        collection = MagicMock()
        collection.find_one.return_value = feriado
        collection.create_index.return_value = "idx"

        svc = _make_service(collection, cache)
        result = svc.buscar_por_data(date(2025, 1, 1))
        assert result == feriado
        assert f"feriados:data:2025-01-01" in cache.store
