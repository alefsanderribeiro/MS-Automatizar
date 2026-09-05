"""
Serviço de Cache com suporte Redis e fallback para memória.

Este módulo implementa uma camada de cache híbrida que tenta usar Redis primeiro,
e faz fallback para cache em memória caso Redis não esteja disponível.

Features:
- Cache Redis com TTL configurável
- Fallback automático para cache em memória
- Métodos batch (get_many, set_many)
- Invalidação por padrão (wildcards)
- Singleton pattern para economia de conexões

Example:
    >>> cache = CacheService()
    >>> cache.set("user:123", {"name": "João"}, ttl=300)
    >>> user = cache.get("user:123")
    >>> cache.invalidate("user:*")
"""

import os
import json
import time
from typing import Any, Dict, List, Optional
from threading import Lock
from src.utils.logger_config_v2 import get_logger

# Inicializar logger
logger = get_logger("cache")

# Tentativa de importar Redis
try:
    import redis
    from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
    REDIS_DISPONIVEL = True
except ImportError:
    logger.warning("Redis não instalado - usando cache em memória apenas")
    REDIS_DISPONIVEL = False


class CacheService:
    """
    Serviço de cache com Redis e fallback para memória.
    
    Implementa padrão Singleton thread-safe para economia de recursos.
    Tenta conectar ao Redis, se falhar usa cache em memória.
    
    Attributes:
        redis_client: Cliente Redis (None se não disponível)
        memory_cache: Dict para fallback em memória
        ttl_cache: Dict com timestamp de expiração para memória
        
    Methods:
        get(key) -> Optional[Any]: Busca valor no cache
        set(key, value, ttl=300): Salva valor no cache
        get_many(keys) -> Dict: Busca múltiplos valores
        set_many(dict, ttl=300): Salva múltiplos valores
        invalidate(pattern): Remove chaves que correspondem ao padrão
        invalidate_all(): Limpa todo o cache
        is_redis_available() -> bool: Verifica se Redis está ativo
    """
    
    _instance: Optional['CacheService'] = None
    _lock: Lock = Lock()
    _initialized: bool = False
    
    def __new__(cls) -> 'CacheService':
        """Implementa singleton thread-safe"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):

        self.logger = get_logger("cache")
        """Inicializa o serviço de cache (apenas uma vez)"""
        if self._initialized:
            return
        
        with self._lock:
            if self._initialized:
                return
            
            self.redis_client = None
            self.memory_cache: Dict[str, Any] = {}
            self.ttl_cache: Dict[str, float] = {}
            self._using_redis = False
            
            # Configuração do Redis via variáveis de ambiente
            redis_enabled = os.getenv("REDIS_ENABLED", "true").lower() == "true"
            
            if REDIS_DISPONIVEL and redis_enabled:
                try:
                    redis_host = os.getenv("REDIS_HOST", "localhost")
                    redis_port = int(os.getenv("REDIS_PORT", "6379"))
                    redis_password = os.getenv("REDIS_PASSWORD", "")
                    redis_db = int(os.getenv("REDIS_DB", "0"))
                    
                    # Configuração de conexão
                    redis_config = {
                        "host": redis_host,
                        "port": redis_port,
                        "db": redis_db,
                        "decode_responses": True,
                        "socket_connect_timeout": 2,
                        "socket_timeout": 2,
                        "retry_on_timeout": True,
                        "health_check_interval": 30
                    }
                    
                    if redis_password:
                        redis_config["password"] = redis_password
                    
                    self.redis_client = redis.Redis(**redis_config)
                    
                    # Testar conexão
                    self.redis_client.ping()
                    self._using_redis = True
                    logger.info(f"✅ Cache Redis conectado em {redis_host}:{redis_port}")
                    
                except (RedisError, RedisConnectionError, Exception) as e:
                    logger.warning(f"⚠️ Redis não disponível: {e}")
                    logger.info("📝 Usando cache em memória como fallback")
                    self.redis_client = None
                    self._using_redis = False
            else:
                logger.info("📝 Cache em memória ativado (Redis desabilitado)")
            
            self._initialized = True
    
    def is_redis_available(self) -> bool:
        """
        Verifica se Redis está disponível e respondendo.
        
        Returns:
            bool: True se Redis está ativo
        """
        if not self._using_redis or self.redis_client is None:
            return False
        
        try:
            self.redis_client.ping()
            return True
        except (RedisError, Exception):
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """
        Busca valor no cache (Redis ou memória).
        
        Args:
            key: Chave do cache
            
        Returns:
            Valor deserializado ou None se não encontrado
            
        Example:
            >>> cache.get("empresa:123")
            {"_id": "123", "nome": "Empresa XYZ"}
        """
        try:
            # Tentar Redis primeiro
            if self._using_redis and self.redis_client:
                try:
                    value = self.redis_client.get(key)
                    if value:
                        return json.loads(value)
                    return None
                except (RedisError, json.JSONDecodeError) as e:
                    logger.warning(f"Erro ao buscar '{key}' no Redis: {e}")
                    # Continua para fallback em memória
            
            # Fallback para memória
            if key in self.ttl_cache:
                # Verificar se expirou
                if time.time() > self.ttl_cache[key]:
                    del self.memory_cache[key]
                    del self.ttl_cache[key]
                    return None
            
            return self.memory_cache.get(key)
            
        except Exception as e:
            logger.error(f"Erro ao buscar cache '{key}': {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """
        Salva valor no cache (Redis ou memória).
        
        Args:
            key: Chave do cache
            value: Valor a ser armazenado (será serializado para JSON)
            ttl: Tempo de vida em segundos (padrão: 300s = 5min)
            
        Returns:
            bool: True se salvou com sucesso
            
        Example:
            >>> cache.set("empresa:123", {"nome": "XYZ"}, ttl=600)
            True
        """
        try:
            # Tentar Redis primeiro
            if self._using_redis and self.redis_client:
                try:
                    json_value = json.dumps(value, default=str)
                    self.redis_client.setex(key, ttl, json_value)
                    return True
                except (RedisError, json.JSONEncodeError, TypeError) as e:
                    logger.warning(f"Erro ao salvar '{key}' no Redis: {e}")
                    # Continua para fallback em memória
            
            # Fallback para memória
            self.memory_cache[key] = value
            self.ttl_cache[key] = time.time() + ttl
            return True
            
        except Exception as e:
            logger.error(f"Erro ao salvar cache '{key}': {e}")
            return False
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Busca múltiplos valores do cache em batch.
        
        Args:
            keys: Lista de chaves
            
        Returns:
            Dict com {key: value} apenas para chaves encontradas
            
        Example:
            >>> cache.get_many(["empresa:1", "empresa:2", "empresa:3"])
            {"empresa:1": {...}, "empresa:2": {...}}
        """
        result = {}
        
        try:
            # Tentar Redis primeiro (pipeline para eficiência)
            if self._using_redis and self.redis_client:
                try:
                    pipeline = self.redis_client.pipeline()
                    for key in keys:
                        pipeline.get(key)
                    
                    values = pipeline.execute()
                    
                    for key, value in zip(keys, values):
                        if value:
                            try:
                                result[key] = json.loads(value)
                            except json.JSONDecodeError:
                                pass
                    
                    return result
                    
                except RedisError as e:
                    logger.warning(f"Erro ao buscar batch no Redis: {e}")
                    # Continua para fallback em memória
            
            # Fallback para memória
            current_time = time.time()
            for key in keys:
                # Verificar TTL
                if key in self.ttl_cache and current_time > self.ttl_cache[key]:
                    self.memory_cache.pop(key, None)
                    self.ttl_cache.pop(key, None)
                    continue
                
                if key in self.memory_cache:
                    result[key] = self.memory_cache[key]
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao buscar batch de cache: {e}")
            return result
    
    def set_many(self, data: Dict[str, Any], ttl: int = 300) -> bool:
        """
        Salva múltiplos valores no cache em batch.
        
        Args:
            data: Dict com {key: value}
            ttl: Tempo de vida em segundos
            
        Returns:
            bool: True se salvou com sucesso
            
        Example:
            >>> cache.set_many({"empresa:1": {...}, "empresa:2": {...}}, ttl=600)
            True
        """
        try:
            # Tentar Redis primeiro (pipeline para eficiência)
            if self._using_redis and self.redis_client:
                try:
                    pipeline = self.redis_client.pipeline()
                    for key, value in data.items():
                        json_value = json.dumps(value, default=str)
                        pipeline.setex(key, ttl, json_value)
                    
                    pipeline.execute()
                    return True
                    
                except (RedisError, json.JSONEncodeError, TypeError) as e:
                    logger.warning(f"Erro ao salvar batch no Redis: {e}")
                    # Continua para fallback em memória
            
            # Fallback para memória
            expiry_time = time.time() + ttl
            for key, value in data.items():
                self.memory_cache[key] = value
                self.ttl_cache[key] = expiry_time
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao salvar batch de cache: {e}")
            return False
    
    def invalidate(self, pattern: str) -> int:
        """
        Remove chaves que correspondem ao padrão (wildcards suportados).
        
        Args:
            pattern: Padrão de chave (ex: "empresas:*", "funcionario:123:*")
            
        Returns:
            int: Número de chaves removidas
            
        Example:
            >>> cache.invalidate("empresas:*")  # Remove todas empresas
            15
        """
        try:
            deleted_count = 0
            
            # Redis
            if self._using_redis and self.redis_client:
                try:
                    # Buscar chaves que correspondem ao padrão
                    keys = list(self.redis_client.scan_iter(match=pattern, count=100))
                    if keys:
                        deleted_count = self.redis_client.delete(*keys)
                    
                    logger.debug(f"Redis: {deleted_count} chaves deletadas para padrão '{pattern}'")
                    return deleted_count
                    
                except RedisError as e:
                    logger.warning(f"Erro ao invalidar padrão '{pattern}' no Redis: {e}")
                    # Continua para fallback em memória
            
            # Fallback para memória (simular wildcards)
            import re
            regex_pattern = pattern.replace("*", ".*")
            regex = re.compile(f"^{regex_pattern}$")
            
            keys_to_delete = [key for key in self.memory_cache.keys() if regex.match(key)]
            
            for key in keys_to_delete:
                self.memory_cache.pop(key, None)
                self.ttl_cache.pop(key, None)
                deleted_count += 1
            
            logger.debug(f"Memória: {deleted_count} chaves deletadas para padrão '{pattern}'")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Erro ao invalidar cache com padrão '{pattern}': {e}")
            return 0
    
    def invalidate_all(self) -> bool:
        """
        Limpa todo o cache (Redis e memória).
        
        Returns:
            bool: True se limpou com sucesso
            
        Example:
            >>> cache.invalidate_all()
            True
        """
        try:
            # Redis
            if self._using_redis and self.redis_client:
                try:
                    self.redis_client.flushdb()
                    logger.info("✅ Cache Redis limpo completamente")
                except RedisError as e:
                    logger.warning(f"Erro ao limpar Redis: {e}")
            
            # Memória
            self.memory_cache.clear()
            self.ttl_cache.clear()
            logger.info("✅ Cache em memória limpo completamente")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao limpar cache: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas do cache.
        
        Returns:
            Dict com estatísticas
        """
        stats = {
            "tipo": "redis" if self._using_redis else "memória",
            "redis_disponivel": self.is_redis_available(),
            "itens_memoria": len(self.memory_cache)
        }
        
        if self._using_redis and self.redis_client:
            try:
                info = self.redis_client.info("stats")
                stats["redis_keys"] = self.redis_client.dbsize()
                stats["redis_hits"] = info.get("keyspace_hits", 0)
                stats["redis_misses"] = info.get("keyspace_misses", 0)
            except RedisError:
                pass
        
        return stats


# Instância global singleton
cache_service = CacheService()
