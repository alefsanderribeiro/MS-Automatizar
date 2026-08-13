"""Redis-specific test fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Optional, Dict, Any
import json


# ==================== Redis Connection Mock ====================

@pytest.fixture
def mock_redis_connection():
    """
    Detailed Redis connection mock with full operation support.

    Returns:
        Mock Redis client with get, set, delete, keys, scan_iter, etc.
    """
    redis = AsyncMock()

    # Storage dict for simulating Redis behavior
    storage: Dict[str, str] = {}

    # GET operation
    async def mock_get(key: str) -> Optional[str]:
        return storage.get(key)

    # SET operation
    async def mock_set(key: str, value: str, ex: Optional[int] = None) -> bool:
        storage[key] = value
        return True

    # DELETE operation
    async def mock_delete(*keys: str) -> int:
        count = 0
        for key in keys:
            if key in storage:
                del storage[key]
                count += 1
        return count

    # EXISTS operation
    async def mock_exists(*keys: str) -> int:
        return sum(1 for key in keys if key in storage)

    # KEYS operation
    async def mock_keys(pattern: str = "*") -> list:
        return list(storage.keys())

    # SCAN_ITER operation
    async def mock_scan_iter(match: str = "*", count: int = 100):
        for key in storage.keys():
            yield key

    # EXPIRE operation
    async def mock_expire(key: str, seconds: int) -> bool:
        return key in storage

    # PING operation
    async def mock_ping() -> bool:
        return True

    # Assign mocks
    redis.get = mock_get
    redis.set = mock_set
    redis.delete = mock_delete
    redis.exists = mock_exists
    redis.keys = mock_keys
    redis.scan_iter = mock_scan_iter
    redis.expire = mock_expire
    redis.ping = mock_ping

    # Add storage reference for test inspection
    redis._storage = storage

    return redis


@pytest.fixture
def mock_redis_unavailable():
    """
    Mock Redis connection failure scenario.

    Returns:
        Mock Redis that raises ConnectionError on all operations
    """
    redis = AsyncMock()

    async def raise_connection_error(*args, **kwargs):
        raise ConnectionError("Redis server not available")

    redis.get = raise_connection_error
    redis.set = raise_connection_error
    redis.delete = raise_connection_error
    redis.keys = raise_connection_error
    redis.scan_iter = raise_connection_error
    redis.ping = raise_connection_error

    return redis


# ==================== Cache Key Builders ====================

@pytest.fixture
def cache_key_builder():
    """
    Helper for building consistent cache keys.

    Usage:
        def test_example(cache_key_builder):
            key = cache_key_builder("funcionario", id=123)
            # Returns: "funcionario:123"
    """
    def _build_key(prefix: str, **kwargs) -> str:
        parts = [prefix]
        for key, value in sorted(kwargs.items()):
            parts.append(f"{key}:{value}")
        return ":".join(parts)

    return _build_key


# ==================== Cache Data Helpers ====================

@pytest.fixture
def cached_funcionario_factory():
    """
    Factory for creating cached funcionario data.

    Usage:
        def test_example(cached_funcionario_factory):
            cached = cached_funcionario_factory(nome="João", pis="12345")
    """
    def _create_cached(
        _id: str = "507f1f77bcf86cd799439011",
        nome: str = "João Silva",
        **kwargs
    ) -> str:
        from datetime import datetime, timezone

        data = {
            "_id": _id,
            "nome": nome,
            "pis": kwargs.get("pis", "12345678901"),
            "cpf": kwargs.get("cpf", "123.456.789-00"),
            "lotacao": kwargs.get("lotacao", "TI"),
            "status": kwargs.get("status", "ativo"),
            "status_cadastro": kwargs.get("status_cadastro", "completo"),
            "cached_at": datetime.now(timezone.utc).isoformat()
        }

        return json.dumps(data)

    return _create_cached


@pytest.fixture
def cached_empresa_factory():
    """
    Factory for creating cached empresa data.

    Usage:
        def test_example(cached_empresa_factory):
            cached = cached_empresa_factory(nome="Empresa XYZ")
    """
    def _create_cached(
        _id: str = "507f1f77bcf86cd799439011",
        nome: str = "Empresa Teste",
        **kwargs
    ) -> str:
        from datetime import datetime, timezone

        data = {
            "_id": _id,
            "nome": nome,
            "cnpj": kwargs.get("cnpj"),
            "status": kwargs.get("status", "ativa"),
            "incompleto": kwargs.get("incompleto", False),
            "cached_at": datetime.now(timezone.utc).isoformat()
        }

        return json.dumps(data)

    return _create_cached


# ==================== Redis Service Mock ====================

@pytest.fixture
def mock_cache_service(mock_redis_connection):
    """
    Mock CacheService with Redis backend.

    Returns:
        Tuple of (cache_service, redis_mock)
    """
    from src.services.cache_service import CacheService

    # Create service instance
    service = CacheService()

    # Inject mock Redis
    service.redis = mock_redis_connection
    service._enabled = True

    return service, mock_redis_connection


@pytest.fixture
def mock_cache_service_disabled():
    """
    Mock CacheService with caching disabled.

    Returns:
        CacheService with caching disabled
    """
    from src.services.cache_service import CacheService

    # Create service instance
    service = CacheService()
    service._enabled = False
    service.redis = None

    return service
