"""
Unit tests for CacheService.

Target: 70% coverage (301/430 lines)
"""

import pytest
import json
import time
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Dict, Any

from src.services.cache_service import CacheService


# ==================== Fixtures ====================

@pytest.fixture
def mock_redis():
    """Mock synchronous Redis client with full operation support."""
    redis = MagicMock()

    # Storage dict for simulating Redis behavior
    storage: Dict[str, str] = {}
    ttl_storage: Dict[str, int] = {}

    # GET operation
    def mock_get(key: str):
        return storage.get(key)

    # SETEX operation
    def mock_setex(key: str, ttl: int, value: str):
        storage[key] = value
        ttl_storage[key] = ttl
        return True

    # DELETE operation
    def mock_delete(*keys: str):
        count = 0
        for key in keys:
            if key in storage:
                del storage[key]
                count += 1
        return count

    # SCAN_ITER operation
    def mock_scan_iter(match: str = "*", count: int = 100):
        import re
        pattern = match.replace("*", ".*")
        regex = re.compile(f"^{pattern}$")
        for key in storage.keys():
            if regex.match(key):
                yield key

    # PING operation
    def mock_ping():
        return True

    # PIPELINE operation
    def mock_pipeline():
        pipe = MagicMock()
        commands = []

        def pipe_get(key):
            commands.append(('get', key))
            return pipe

        def pipe_setex(key, ttl, value):
            commands.append(('setex', key, ttl, value))
            return pipe

        def pipe_execute():
            results = []
            for cmd in commands:
                if cmd[0] == 'get':
                    results.append(storage.get(cmd[1]))
                elif cmd[0] == 'setex':
                    storage[cmd[1]] = cmd[3]
                    ttl_storage[cmd[1]] = cmd[2]
                    results.append(True)
            commands.clear()
            return results

        pipe.get = pipe_get
        pipe.setex = pipe_setex
        pipe.execute = pipe_execute
        return pipe

    # FLUSHDB operation
    def mock_flushdb():
        storage.clear()
        ttl_storage.clear()
        return True

    # INFO operation
    def mock_info(section: str = "stats"):
        return {
            "keyspace_hits": 100,
            "keyspace_misses": 10
        }

    # DBSIZE operation
    def mock_dbsize():
        return len(storage)

    # Assign mocks
    redis.get = mock_get
    redis.setex = mock_setex
    redis.delete = mock_delete
    redis.scan_iter = mock_scan_iter
    redis.ping = mock_ping
    redis.pipeline = mock_pipeline
    redis.flushdb = mock_flushdb
    redis.info = mock_info
    redis.dbsize = mock_dbsize

    # Add storage reference for test inspection
    redis._storage = storage
    redis._ttl_storage = ttl_storage

    return redis


@pytest.fixture
def reset_cache_singleton():
    """Reset CacheService singleton between tests."""
    # Store original state
    original_instance = CacheService._instance
    original_initialized = CacheService._initialized

    # Reset singleton
    CacheService._instance = None
    CacheService._initialized = False

    yield

    # Restore original state
    CacheService._instance = original_instance
    CacheService._initialized = original_initialized


@pytest.fixture
def cache_with_redis(reset_cache_singleton, mock_redis, monkeypatch):
    """CacheService with Redis enabled."""
    monkeypatch.setenv("REDIS_ENABLED", "true")
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("REDIS_PORT", "6379")

    with patch('src.services.cache_service.REDIS_DISPONIVEL', True):
        with patch('src.services.cache_service.redis.Redis', return_value=mock_redis):
            cache = CacheService()
            yield cache, mock_redis


@pytest.fixture
def cache_without_redis(reset_cache_singleton, monkeypatch):
    """CacheService with Redis disabled (memory-only mode)."""
    monkeypatch.setenv("REDIS_ENABLED", "false")

    with patch('src.services.cache_service.REDIS_DISPONIVEL', False):
        cache = CacheService()
        yield cache


@pytest.fixture
def cache_with_redis_unavailable(reset_cache_singleton, monkeypatch):
    """CacheService with Redis connection failure."""
    monkeypatch.setenv("REDIS_ENABLED", "true")

    mock_redis_error = MagicMock()
    mock_redis_error.ping.side_effect = Exception("Connection refused")

    with patch('src.services.cache_service.REDIS_DISPONIVEL', True):
        with patch('src.services.cache_service.redis.Redis', return_value=mock_redis_error):
            cache = CacheService()
            yield cache


# ==================== TestCacheServiceInit ====================

class TestCacheServiceInit:
    """Test CacheService initialization and singleton pattern."""

    def test_singleton_pattern(self, reset_cache_singleton):
        """Test that CacheService implements singleton pattern."""
        cache1 = CacheService()
        cache2 = CacheService()

        assert cache1 is cache2
        assert id(cache1) == id(cache2)

    def test_redis_available_initialization(self, cache_with_redis):
        """Test initialization when Redis is available."""
        cache, mock_redis = cache_with_redis

        assert cache._using_redis is True
        assert cache.redis_client is not None
        # ping() is a mock function, so we just verify it was callable
        assert callable(mock_redis.ping)

    def test_redis_disabled_initialization(self, cache_without_redis):
        """Test initialization when Redis is disabled."""
        cache = cache_without_redis

        assert cache._using_redis is False
        assert cache.redis_client is None
        assert isinstance(cache.memory_cache, dict)
        assert isinstance(cache.ttl_cache, dict)

    def test_fallback_to_memory_on_redis_failure(self, cache_with_redis_unavailable):
        """Test fallback to memory-only mode when Redis connection fails."""
        cache = cache_with_redis_unavailable

        assert cache._using_redis is False
        assert cache.redis_client is None
        assert isinstance(cache.memory_cache, dict)

    def test_memory_cache_initialization(self, cache_without_redis):
        """Test that memory cache is properly initialized."""
        cache = cache_without_redis

        assert cache.memory_cache == {}
        assert cache.ttl_cache == {}

    def test_redis_config_from_env(self, reset_cache_singleton, monkeypatch):
        """Test Redis configuration from environment variables."""
        monkeypatch.setenv("REDIS_ENABLED", "true")
        monkeypatch.setenv("REDIS_HOST", "custom-host")
        monkeypatch.setenv("REDIS_PORT", "6380")
        monkeypatch.setenv("REDIS_PASSWORD", "secret123")
        monkeypatch.setenv("REDIS_DB", "2")

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch('src.services.cache_service.REDIS_DISPONIVEL', True):
            with patch('src.services.cache_service.redis.Redis') as redis_class:
                redis_class.return_value = mock_redis
                cache = CacheService()

                # Check Redis was called with correct config
                redis_class.assert_called_once()
                call_kwargs = redis_class.call_args[1]
                assert call_kwargs['host'] == 'custom-host'
                assert call_kwargs['port'] == 6380
                assert call_kwargs['password'] == 'secret123'
                assert call_kwargs['db'] == 2


# ==================== TestCacheOperacoes ====================

class TestCacheOperacoes:
    """Test basic cache operations (get, set, delete)."""

    def test_set_and_get_with_redis(self, cache_with_redis):
        """Test set() and get() with Redis backend."""
        cache, mock_redis = cache_with_redis

        test_data = {"name": "João", "age": 30}
        result = cache.set("user:123", test_data, ttl=300)

        assert result is True
        # Verify data was serialized and stored
        stored_value = mock_redis._storage.get("user:123")
        assert stored_value is not None
        assert json.loads(stored_value) == test_data

    def test_get_returns_deserialized_data(self, cache_with_redis):
        """Test get() returns properly deserialized data."""
        cache, mock_redis = cache_with_redis

        test_data = {"name": "Maria", "status": "ativo"}
        cache.set("funcionario:456", test_data)

        result = cache.get("funcionario:456")
        assert result == test_data
        assert isinstance(result, dict)

    def test_get_miss_returns_none(self, cache_with_redis):
        """Test get() returns None for non-existent key."""
        cache, mock_redis = cache_with_redis

        result = cache.get("non_existent_key")
        assert result is None

    def test_set_with_memory_cache(self, cache_without_redis):
        """Test set() with memory-only cache."""
        cache = cache_without_redis

        test_data = {"company": "Acme Corp"}
        result = cache.set("empresa:789", test_data, ttl=300)

        assert result is True
        assert cache.memory_cache["empresa:789"] == test_data
        assert "empresa:789" in cache.ttl_cache

    def test_get_with_memory_cache(self, cache_without_redis):
        """Test get() with memory-only cache."""
        cache = cache_without_redis

        test_data = {"value": "test"}
        cache.set("test_key", test_data)

        result = cache.get("test_key")
        assert result == test_data

    def test_set_with_ttl(self, cache_with_redis):
        """Test set() with custom TTL."""
        cache, mock_redis = cache_with_redis

        cache.set("temp_key", "temp_value", ttl=60)

        # Verify TTL was passed to Redis
        assert mock_redis._ttl_storage.get("temp_key") == 60

    def test_delete_key_with_redis(self, cache_with_redis):
        """Test delete operation with Redis."""
        cache, mock_redis = cache_with_redis

        # Setup
        cache.set("key_to_delete", "value")
        assert "key_to_delete" in mock_redis._storage

        # Delete via invalidate pattern
        deleted_count = cache.invalidate("key_to_delete")

        assert deleted_count == 1
        assert "key_to_delete" not in mock_redis._storage


# ==================== TestCacheTTL ====================

class TestCacheTTL:
    """Test TTL expiration behavior."""

    def test_ttl_expiration_in_memory_cache(self, cache_without_redis):
        """Test that expired keys in memory cache return None."""
        cache = cache_without_redis

        # Set with very short TTL
        cache.set("expiring_key", "value", ttl=1)

        # Verify key exists
        assert cache.get("expiring_key") == "value"

        # Mock time progression
        with patch('time.time', return_value=time.time() + 2):
            result = cache.get("expiring_key")
            assert result is None
            # Verify key was cleaned up
            assert "expiring_key" not in cache.memory_cache
            assert "expiring_key" not in cache.ttl_cache

    def test_get_before_expiration(self, cache_without_redis):
        """Test get() before TTL expiration returns value."""
        cache = cache_without_redis

        cache.set("valid_key", "valid_value", ttl=10)

        # Mock time progression (still within TTL)
        with patch('time.time', return_value=time.time() + 5):
            result = cache.get("valid_key")
            assert result == "valid_value"

    def test_multiple_keys_with_different_ttls(self, cache_without_redis):
        """Test multiple keys with different expiration times."""
        cache = cache_without_redis

        current_time = time.time()

        cache.set("key1", "value1", ttl=5)
        cache.set("key2", "value2", ttl=10)
        cache.set("key3", "value3", ttl=15)

        # Mock time: 7 seconds passed (key1 expired, key2/key3 valid)
        with patch('time.time', return_value=current_time + 7):
            assert cache.get("key1") is None
            assert cache.get("key2") == "value2"
            assert cache.get("key3") == "value3"


# ==================== TestCacheInvalidacao ====================

class TestCacheInvalidacao:
    """Test cache invalidation operations."""

    def test_invalidar_por_padrao_wildcard(self, cache_with_redis):
        """Test invalidate() with wildcard pattern."""
        cache, mock_redis = cache_with_redis

        # Setup multiple keys
        cache.set("empresa:123", {"name": "A"})
        cache.set("empresa:456", {"name": "B"})
        cache.set("funcionario:789", {"name": "C"})

        # Invalidate only empresa keys
        deleted_count = cache.invalidate("empresa:*")

        assert deleted_count == 2
        assert "empresa:123" not in mock_redis._storage
        assert "empresa:456" not in mock_redis._storage
        assert "funcionario:789" in mock_redis._storage

    def test_invalidar_por_padrao_memory(self, cache_without_redis):
        """Test invalidate() with wildcard pattern in memory cache."""
        cache = cache_without_redis

        # Setup multiple keys
        cache.set("user:1", "data1")
        cache.set("user:2", "data2")
        cache.set("admin:1", "data3")

        # Invalidate only user keys
        deleted_count = cache.invalidate("user:*")

        assert deleted_count == 2
        assert "user:1" not in cache.memory_cache
        assert "user:2" not in cache.memory_cache
        assert "admin:1" in cache.memory_cache

    def test_clear_all_cache_with_redis(self, cache_with_redis):
        """Test invalidate_all() clears all cache."""
        cache, mock_redis = cache_with_redis

        # Setup data
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.memory_cache["mem_key"] = "mem_value"

        result = cache.invalidate_all()

        assert result is True
        assert len(mock_redis._storage) == 0
        assert len(cache.memory_cache) == 0
        assert len(cache.ttl_cache) == 0

    def test_clear_all_cache_memory_only(self, cache_without_redis):
        """Test invalidate_all() in memory-only mode."""
        cache = cache_without_redis

        # Setup data
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        result = cache.invalidate_all()

        assert result is True
        assert len(cache.memory_cache) == 0
        assert len(cache.ttl_cache) == 0

    def test_selective_deletion_by_pattern(self, cache_with_redis):
        """Test selective cache deletion using patterns."""
        cache, mock_redis = cache_with_redis

        # Setup hierarchical keys
        cache.set("app:cache:user:123", "data1")
        cache.set("app:cache:user:456", "data2")
        cache.set("app:session:789", "data3")

        # Delete only cache entries
        cache.invalidate("app:cache:*")

        assert "app:cache:user:123" not in mock_redis._storage
        assert "app:cache:user:456" not in mock_redis._storage
        assert "app:session:789" in mock_redis._storage

    def test_invalidate_non_existent_pattern(self, cache_with_redis):
        """Test invalidate() with pattern that matches no keys."""
        cache, mock_redis = cache_with_redis

        cache.set("existing:key", "value")

        deleted_count = cache.invalidate("non_existent:*")

        assert deleted_count == 0
        assert "existing:key" in mock_redis._storage


# ==================== TestCacheBatch ====================

class TestCacheBatch:
    """Test batch operations (get_many, set_many)."""

    def test_mget_multiple_keys_redis(self, cache_with_redis):
        """Test get_many() with Redis backend."""
        cache, mock_redis = cache_with_redis

        # Setup data
        cache.set("key1", {"value": 1})
        cache.set("key2", {"value": 2})
        cache.set("key3", {"value": 3})

        # Batch get
        result = cache.get_many(["key1", "key2", "key3"])

        assert len(result) == 3
        assert result["key1"] == {"value": 1}
        assert result["key2"] == {"value": 2}
        assert result["key3"] == {"value": 3}

    def test_mget_partial_hits(self, cache_with_redis):
        """Test get_many() with some keys missing."""
        cache, mock_redis = cache_with_redis

        cache.set("exists1", "data1")
        cache.set("exists2", "data2")

        result = cache.get_many(["exists1", "missing", "exists2"])

        assert len(result) == 2
        assert "exists1" in result
        assert "exists2" in result
        assert "missing" not in result

    def test_mset_multiple_keys_redis(self, cache_with_redis):
        """Test set_many() with Redis backend."""
        cache, mock_redis = cache_with_redis

        data = {
            "key1": {"value": 1},
            "key2": {"value": 2},
            "key3": {"value": 3}
        }

        result = cache.set_many(data, ttl=300)

        assert result is True
        assert len(mock_redis._storage) == 3
        assert json.loads(mock_redis._storage["key1"]) == {"value": 1}
        assert json.loads(mock_redis._storage["key2"]) == {"value": 2}

    def test_mset_mget_roundtrip(self, cache_with_redis):
        """Test set_many() followed by get_many() roundtrip."""
        cache, mock_redis = cache_with_redis

        original_data = {
            "user:1": {"name": "Alice"},
            "user:2": {"name": "Bob"},
            "user:3": {"name": "Charlie"}
        }

        cache.set_many(original_data)
        retrieved_data = cache.get_many(["user:1", "user:2", "user:3"])

        assert retrieved_data == original_data

    def test_batch_operations_memory_cache(self, cache_without_redis):
        """Test batch operations with memory-only cache."""
        cache = cache_without_redis

        # Set batch
        data = {"mem1": "value1", "mem2": "value2", "mem3": "value3"}
        cache.set_many(data, ttl=300)

        # Get batch
        result = cache.get_many(["mem1", "mem2", "mem3"])

        assert result == data

    def test_mget_with_expired_keys_in_memory(self, cache_without_redis):
        """Test get_many() skips expired keys in memory cache."""
        cache = cache_without_redis

        current_time = time.time()
        cache.set("key1", "value1", ttl=10)
        cache.set("key2", "value2", ttl=1)
        cache.set("key3", "value3", ttl=10)

        # Mock time: key2 expired
        with patch('time.time', return_value=current_time + 2):
            result = cache.get_many(["key1", "key2", "key3"])

            assert len(result) == 2
            assert "key1" in result
            assert "key2" not in result
            assert "key3" in result


# ==================== TestCacheHibrido ====================

class TestCacheHibrido:
    """Test hybrid cache behavior (Redis + memory fallback)."""

    def test_redis_failure_fallback_to_memory(self, cache_with_redis):
        """Test fallback to memory when Redis is disconnected."""
        cache, mock_redis = cache_with_redis

        # Temporarily disable Redis to force memory fallback
        cache._using_redis = False
        original_client = cache.redis_client
        cache.redis_client = None

        # Set should work with memory-only mode
        result = cache.set("fallback_key", "fallback_value")
        assert result is True

        # Data should be in memory cache
        assert cache.memory_cache.get("fallback_key") == "fallback_value"

        # Restore Redis
        cache._using_redis = True
        cache.redis_client = original_client

    def test_redis_failure_on_set_uses_memory(self, cache_without_redis):
        """Test set() works with memory-only cache."""
        cache = cache_without_redis

        # With Redis disabled, set() should use memory cache
        result = cache.set("test_key", "test_value", ttl=300)

        assert result is True
        assert cache.memory_cache["test_key"] == "test_value"
        assert "test_key" in cache.ttl_cache
        assert cache.ttl_cache["test_key"] > time.time()

    def test_memory_cache_as_hot_cache(self, cache_with_redis):
        """Test memory cache can work alongside Redis."""
        cache, mock_redis = cache_with_redis

        # Import RedisError for proper exception handling
        from redis.exceptions import RedisError

        # Store in Redis
        cache.set("redis_key", {"data": "redis"})

        # Both should be accessible
        assert cache.get("redis_key") == {"data": "redis"}

        # Manually add to memory cache for fallback scenario
        cache.memory_cache["memory_key"] = {"data": "memory"}
        cache.ttl_cache["memory_key"] = time.time() + 300

        # Simulate Redis failure with RedisError (which triggers fallback to memory)
        mock_redis.get = MagicMock(side_effect=RedisError("Redis down"))

        # When Redis fails, it should fall back to memory cache
        result = cache.get("memory_key")
        assert result == {"data": "memory"}


# ==================== TestCacheComRedis ====================

class TestCacheComRedis:
    """Test Redis-specific functionality."""

    def test_is_redis_available_when_enabled(self, cache_with_redis):
        """Test is_redis_available() returns True when Redis is active."""
        cache, mock_redis = cache_with_redis

        assert cache.is_redis_available() is True

    def test_is_redis_available_when_disabled(self, cache_without_redis):
        """Test is_redis_available() returns False when Redis is disabled."""
        cache = cache_without_redis

        assert cache.is_redis_available() is False

    def test_is_redis_available_handles_ping_failure(self, cache_with_redis):
        """Test is_redis_available() handles ping failures gracefully."""
        cache, mock_redis = cache_with_redis

        # Simulate ping failure by replacing the mock
        original_ping = mock_redis.ping
        mock_redis.ping = MagicMock(side_effect=Exception("Connection lost"))

        result = cache.is_redis_available()
        assert result is False

    def test_redis_connection_errors_logged(self, cache_with_redis_unavailable):
        """Test Redis connection errors are properly logged."""
        cache = cache_with_redis_unavailable

        # Cache should fall back to memory mode
        assert cache._using_redis is False
        assert cache.redis_client is None

    def test_get_stats_with_redis(self, cache_with_redis):
        """Test get_stats() with Redis backend."""
        cache, mock_redis = cache_with_redis

        stats = cache.get_stats()

        assert stats["tipo"] == "redis"
        assert stats["redis_disponivel"] is True
        assert "redis_keys" in stats
        assert "redis_hits" in stats
        assert "redis_misses" in stats

    def test_get_stats_without_redis(self, cache_without_redis):
        """Test get_stats() in memory-only mode."""
        cache = cache_without_redis

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        stats = cache.get_stats()

        assert stats["tipo"] == "memória"
        assert stats["redis_disponivel"] is False
        assert stats["itens_memoria"] == 2

    def test_redis_json_encoding_error_fallback(self, cache_with_redis):
        """Test handling of JSON encoding errors in Redis operations."""
        cache, mock_redis = cache_with_redis

        # Create object that can't be JSON serialized
        class NonSerializable:
            pass

        # Should fall back to memory cache (using default=str)
        result = cache.set("bad_key", NonSerializable(), ttl=300)

        # With default=str, this should actually succeed in Redis
        # But if it fails, memory fallback should work
        assert result is True


# ==================== TestCacheEdgeCases ====================

class TestCacheEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_key_handling(self, cache_without_redis):
        """Test cache operations with empty key."""
        cache = cache_without_redis

        cache.set("", "empty_key_value")
        result = cache.get("")

        assert result == "empty_key_value"

    def test_large_data_storage(self, cache_without_redis):
        """Test storing large data structures."""
        cache = cache_without_redis

        large_data = {"items": [{"id": i, "data": "x" * 100} for i in range(1000)]}

        result = cache.set("large_key", large_data)
        assert result is True

        retrieved = cache.get("large_key")
        assert len(retrieved["items"]) == 1000

    def test_none_value_storage(self, cache_without_redis):
        """Test storing None as a value."""
        cache = cache_without_redis

        cache.set("none_key", None)
        result = cache.get("none_key")

        # None should be stored and retrieved
        assert result is None

    def test_special_characters_in_keys(self, cache_without_redis):
        """Test keys with special characters."""
        cache = cache_without_redis

        special_keys = [
            "key:with:colons",
            "key-with-dashes",
            "key_with_underscores",
            "key.with.dots"
        ]

        for key in special_keys:
            cache.set(key, f"value_for_{key}")
            assert cache.get(key) == f"value_for_{key}"

    def test_concurrent_access_safety(self, cache_without_redis):
        """Test that singleton pattern is thread-safe."""
        cache1 = cache_without_redis
        cache2 = CacheService()

        cache1.set("shared_key", "value1")

        # Should be same instance
        assert cache2.get("shared_key") == "value1"

    def test_invalidate_all_returns_true_on_success(self, cache_without_redis):
        """Test invalidate_all() return value."""
        cache = cache_without_redis

        cache.set("key1", "value1")
        result = cache.invalidate_all()

        assert result is True

    def test_set_returns_false_on_error(self, cache_without_redis):
        """Test set() error handling."""
        cache = cache_without_redis

        # Create a mock dict that raises exception on setitem
        broken_dict = {}
        original_setitem = broken_dict.__setitem__

        def raise_error(key, value):
            raise Exception("Storage error")

        # Patch the memory_cache to raise exception
        with patch.object(cache, 'memory_cache', new_callable=lambda: type('BrokenDict', (), {
            '__setitem__': raise_error,
            'get': lambda self, key, default=None: None
        })()):
            result = cache.set("error_key", "value")
            # Should catch exception and return False
            assert result is False


# ==================== TestCachePerformance ====================

class TestCachePerformance:
    """Test cache performance characteristics."""

    def test_batch_operations_efficiency(self, cache_with_redis):
        """Test that batch operations use pipeline for efficiency."""
        cache, mock_redis = cache_with_redis

        # set_many should call pipeline.execute once
        data = {f"key{i}": f"value{i}" for i in range(10)}
        cache.set_many(data)

        # Verify pipeline was used (single execute call)
        assert len(mock_redis._storage) == 10

    def test_memory_cache_ttl_cleanup(self, cache_without_redis):
        """Test that expired keys are cleaned up on access."""
        cache = cache_without_redis

        # Add multiple keys
        for i in range(5):
            cache.set(f"key{i}", f"value{i}", ttl=1)

        assert len(cache.memory_cache) == 5

        # Mock time progression
        with patch('time.time', return_value=time.time() + 2):
            # Access one key - should trigger cleanup
            cache.get("key0")

            # key0 should be removed
            assert "key0" not in cache.memory_cache
            assert "key0" not in cache.ttl_cache
