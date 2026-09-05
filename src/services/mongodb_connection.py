"""
Gerenciador de Conexões MongoDB com Pool de Conexões

Este módulo implementa um singleton thread-safe para gerenciar conexões MongoDB,
evitando múltiplas conexões e melhorando a performance.

Características:
- Singleton pattern com thread safety
- Connection pooling configurável
- Health check integrado
- Retry automático para operações
- Métricas de tempo de execução
"""

import os
import time
from threading import Lock
from typing import Optional, Dict, Any
from functools import wraps
from contextlib import contextmanager
from datetime import datetime

import dotenv
from src.utils.dotenv_path import caminho_dotenv
from src.utils.logger_config_v2 import get_logger

# Inicializar logger
logger = get_logger("mongodb")

# Tentativa de importação do MongoDB
try:
    from pymongo import MongoClient
    from pymongo.errors import (
        ConnectionFailure, 
        ServerSelectionTimeoutError,
        AutoReconnect,
        NetworkTimeout
    )
    from pymongo.database import Database
    MONGODB_DISPONIVEL = True
except ImportError:
    MONGODB_DISPONIVEL = False
    logger.warning("PyMongo não instalado - MongoDBConnectionPool ficará limitado")


class MongoDBConnectionPool:
    """
    Singleton thread-safe para gerenciar conexões MongoDB.
    
    Uso:
        pool = MongoDBConnectionPool()
        db = pool.get_database()
        collection = db["minha_colecao"]
    
    Configuração via .env:
        MONGO_URI=mongodb://localhost:27017
        MONGO_DATABASE_NAME=MS_Automatizar
        MONGO_MAX_POOL_SIZE=10
        MONGO_MIN_POOL_SIZE=2
    """
    
    _instance: Optional['MongoDBConnectionPool'] = None
    _lock: Lock = Lock()
    _initialized: bool = False
    
    def __new__(cls) -> 'MongoDBConnectionPool':
        """Implementa singleton thread-safe"""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):

        self.logger = get_logger("mongodb")
        """Inicializa o pool de conexões (apenas uma vez)"""
        # Evitar reinicialização
        if MongoDBConnectionPool._initialized:
            return
        
        with MongoDBConnectionPool._lock:
            if MongoDBConnectionPool._initialized:
                return
            
            self._init_pool()
            MongoDBConnectionPool._initialized = True
    
    def _init_pool(self) -> None:
        """Inicializa a conexão com MongoDB"""
        if not MONGODB_DISPONIVEL:
            logger.error("PyMongo não disponível - instale com: pip install pymongo")
            self.client: Optional[MongoClient] = None
            self.db: Optional[Database] = None
            self._disponivel = False
            self._metricas: Dict[str, Any] = {}
            return
        
        try:
            # Carregar configurações do .env
            env_path = caminho_dotenv()
            self.mongo_uri = dotenv.get_key(env_path, "MONGO_URI") or "mongodb://localhost:27017"
            self.db_name = dotenv.get_key(env_path, "MONGO_DATABASE_NAME") or "MS_Automatizar"
            
            # Configurações do pool
            max_pool_size = int(dotenv.get_key(env_path, "MONGO_MAX_POOL_SIZE") or "10")
            min_pool_size = int(dotenv.get_key(env_path, "MONGO_MIN_POOL_SIZE") or "2")
            
            # Criar cliente com pool de conexões
            self.client = MongoClient(
                self.mongo_uri,
                maxPoolSize=max_pool_size,
                minPoolSize=min_pool_size,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=30000,
                retryWrites=True,
                retryReads=True
            )
            
            # Verificar conexão
            self.client.admin.command('ping')
            
            # Obter referência ao banco
            self.db = self.client[self.db_name]
            
            self._disponivel = True
            self._metricas = {
                "conexoes_criadas": 1,
                "ultima_conexao": datetime.now(),
                "operacoes_executadas": 0,
                "erros": 0,
                "tempo_total_operacoes_ms": 0
            }
            
            logger.debug(
                f"✓ MongoDB Connection Pool inicializado: "
                f"{self.mongo_uri}/{self.db_name} "
                f"(pool: {min_pool_size}-{max_pool_size})"
            )
        
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"✗ Falha ao conectar MongoDB: {e}")
            self.client = None
            self.db = None
            self._disponivel = False
            self._metricas = {}
        
        except Exception as e:
            logger.error(f"✗ Erro ao inicializar MongoDB: {e}")
            self.client = None
            self.db = None
            self._disponivel = False
            self._metricas = {}
    
    @property
    def disponivel(self) -> bool:
        """Verifica se a conexão está disponível"""
        return self._disponivel
    
    def _garantir_conexao_locked(self) -> bool:
        """
        Garante que a conexão esteja disponível, reconectando se necessário.
        Deve ser chamada COM o lock `MongoDBConnectionPool._lock` já adquirido.
        
        Reconecta automaticamente quando:
        - `_disponivel` ainda é False (queda anterior não recuperada);
        - o cliente é None;
        - a conexão subjacente está fechada/quebrada (valida via ping).
        
        Returns:
            True se a conexão está disponível após a verificação/reconexão.
        """
        if not MONGODB_DISPONIVEL:
            return False

        # Se não está marcado como disponível ou não há cliente, tentar (re)conectar
        if not self._disponivel or self.client is None:
            if self._tentar_reconectar_locked():
                return True
            return False

        # Se está marcado como disponível, mas a conexão quebrou, reconectar também
        if self.client is not None:
            try:
                self.client.admin.command('ping')
                return True
            except Exception:
                logger.warning("Conexão MongoDB quebrada durante uso - tentando reconectar...")
                self._disponivel = False
                if self._tentar_reconectar_locked():
                    return True
                return False

        return False

    def _tentar_reconectar_locked(self) -> bool:
        """Tenta (re)conectar ao MongoDB com backoff. Deve ser chamada COM o lock."""
        tentativas = 3
        delay_base = 1.0
        ultimo_erro = None

        for tentativa in range(tentativas):
            try:
                # Fecha conexão antiga/quebrada se existir
                if self.client is not None:
                    try:
                        self.client.close()
                    except Exception:
                        pass
                    self.client = None
                    self.db = None

                self._init_pool()
                if self._disponivel and self.client is not None:
                    logger.info("✓ Conexão MongoDB restabelecida com sucesso")
                    return True

            except Exception as e:
                ultimo_erro = e

            if tentativa < tentativas - 1:
                delay = delay_base * (2 ** tentativa)
                logger.warning(
                    f"Falha ao reconectar MongoDB (tentativa {tentativa + 1}/{tentativas}): "
                    f"{ultimo_erro}. Tentando novamente em {delay:.1f}s..."
                )
                time.sleep(delay)

        logger.error(
            f"✗ Falha ao reconectar MongoDB após {tentativas} tentativas: {ultimo_erro}"
        )
        # Garantir estado consistente
        self._disponivel = False
        self.client = None
        self.db = None
        return False

    def _garantir_conexao(self) -> bool:
        """
        Versão thread-safe de `_garantir_conexao_locked`, adquirindo o lock.
        
        Returns:
            True se a conexão está disponível após verificação/reconexão.
        """
        with MongoDBConnectionPool._lock:
            return self._garantir_conexao_locked()

    def get_client(self) -> Optional[MongoClient]:
        """Retorna o cliente MongoDB, reconectando automaticamente se necessário"""
        if not self._garantir_conexao():
            return None
        return self.client
    
    def get_database(self) -> Optional[Database]:
        """Retorna a referência ao banco de dados, reconectando automaticamente se necessário"""
        if not self._garantir_conexao():
            return None
        return self.db
    
    def get_collection(self, collection_name: str):
        """
        Retorna uma coleção do banco de dados, reconectando automaticamente se necessário
        
        Args:
            collection_name: Nome da coleção
            
        Returns:
            Collection ou None se não disponível
        """
        if not self._garantir_conexao():
            return None
        if self.db is None:
            return None
        return self.db[collection_name]
    
    def ping(self) -> bool:
        """
        Verifica se MongoDB está acessível via ping.
        Tenta reconectar automaticamente se a conexão estiver indisponível.
        
        Returns:
            True se MongoDB respondeu ao ping
        """
        if not MONGODB_DISPONIVEL:
            return False
        
        # Garantir conexão (reconectando se necessário)
        if not self._garantir_conexao():
            return False
        
        try:
            self.client.admin.command('ping')
            return True
        except Exception:
            return False
    
    def _health_check_locked(self) -> Dict[str, Any]:
        """Executa o health check assumindo o lock já adquirido."""
        resultado = {
            "disponivel": False,
            "latencia_ms": None,
            "versao_servidor": None,
            "pool_size": None,
            "erro": None
        }
        
        if not MONGODB_DISPONIVEL:
            resultado["erro"] = "PyMongo não instalado"
            return resultado
        
        # Tentar reconectar se a conexão estiver indisponível/quebrada
        if not self._garantir_conexao_locked():
            resultado["erro"] = "MongoDB indisponível após tentativa de reconexão"
            return resultado
        
        try:
            inicio = time.time()
            self.client.admin.command('ping')
            latencia = (time.time() - inicio) * 1000
            
            server_info = self.client.server_info()
            
            resultado.update({
                "disponivel": True,
                "latencia_ms": round(latencia, 2),
                "versao_servidor": server_info.get("version"),
                "pool_size": self.client.options.pool_options.max_pool_size
            })
        except Exception as e:
            resultado["erro"] = str(e)
            self._disponivel = False
        
        return resultado
    
    def health_check(self) -> Dict[str, Any]:
        """
        Verifica a saúde da conexão MongoDB (thread-safe)
        
        Returns:
            Dicionário com status da conexão
        """
        resultado = {
            "disponivel": False,
            "latencia_ms": None,
            "versao_servidor": None,
            "pool_size": None,
            "erro": None
        }
        
        if not MONGODB_DISPONIVEL:
            resultado["erro"] = "PyMongo não instalado"
            return resultado
        
        with MongoDBConnectionPool._lock:
            return self._health_check_locked()
    
    def reconectar(self) -> bool:
        """
        Tenta reconectar ao MongoDB (thread-safe)
        
        Returns:
            True se reconectou com sucesso
        """
        logger.info("Tentando reconectar ao MongoDB...")
        
        with MongoDBConnectionPool._lock:
            return self._tentar_reconectar_locked()
    
    def registrar_operacao(self, tempo_ms: float, erro: bool = False) -> None:
        """
        Registra métricas de uma operação
        
        Args:
            tempo_ms: Tempo da operação em milissegundos
            erro: Se a operação teve erro
        """
        if not self._metricas:
            return
        
        self._metricas["operacoes_executadas"] += 1
        self._metricas["tempo_total_operacoes_ms"] += tempo_ms
        
        if erro:
            self._metricas["erros"] += 1
    
    def obter_metricas(self) -> Dict[str, Any]:
        """
        Retorna métricas do pool de conexões
        
        Returns:
            Dicionário com métricas
        """
        if not self._metricas:
            return {"erro": "Métricas não disponíveis"}
        
        metricas = self._metricas.copy()
        
        # Calcular médias
        if metricas.get("operacoes_executadas", 0) > 0:
            metricas["tempo_medio_operacao_ms"] = round(
                metricas["tempo_total_operacoes_ms"] / metricas["operacoes_executadas"],
                2
            )
        
        # Adicionar health check
        metricas["health"] = self.health_check()
        
        return metricas
    
    def __del__(self):
        """Fecha a conexão ao destruir o objeto"""
        if hasattr(self, 'client') and self.client:
            try:
                self.client.close()
                logger.debug("Conexão MongoDB fechada")
            except Exception:
                pass


# =============================================================================
# Funções auxiliares
# =============================================================================

def verificar_conexao_mongodb() -> bool:
    """
    Verifica se MongoDB está acessível.
    Função de conveniência para uso externo.
    
    Returns:
        True se MongoDB está disponível
    """
    try:
        pool = MongoDBConnectionPool()
        health = pool.health_check()
        return health.get("disponivel", False)
    except Exception:
        return False


def obter_database():
    """
    Retorna a referência ao banco de dados.
    Função de conveniência para uso externo.
    
    Returns:
        Database ou None
    """
    pool = MongoDBConnectionPool()
    return pool.get_database()


def obter_collection(collection_name: str):
    """
    Retorna uma coleção do banco de dados.
    Função de conveniência para uso externo.
    
    Args:
        collection_name: Nome da coleção
        
    Returns:
        Collection ou None
    """
    pool = MongoDBConnectionPool()
    return pool.get_collection(collection_name)


# =============================================================================
# Decoradores
# =============================================================================

def retry_mongodb(max_tentativas: int = 3, delay_base: float = 1.0):
    """
    Decorador para retry automático em operações MongoDB.
    
    Usa backoff exponencial: delay = delay_base * (2 ** tentativa)
    
    Args:
        max_tentativas: Número máximo de tentativas (padrão: 3)
        delay_base: Delay base em segundos (padrão: 1.0)
    
    Uso:
        @retry_mongodb(max_tentativas=3, delay_base=1.0)
        def minha_operacao():
            return collection.find_one({"_id": id})
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            ultima_excecao = None
            
            for tentativa in range(max_tentativas):
                try:
                    return func(*args, **kwargs)
                
                except (ConnectionFailure, AutoReconnect, NetworkTimeout) as e:
                    ultima_excecao = e
                    
                    if tentativa < max_tentativas - 1:
                        delay = delay_base * (2 ** tentativa)
                        logger.warning(
                            f"Erro MongoDB (tentativa {tentativa + 1}/{max_tentativas}): {e}. "
                            f"Retentando em {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        
                        # Tentar reconectar
                        pool = MongoDBConnectionPool()
                        pool.reconectar()
                    else:
                        logger.error(
                            f"Erro MongoDB após {max_tentativas} tentativas: {e}"
                        )
                
                except Exception as e:
                    # Outros erros não fazem retry
                    logger.error(f"Erro não recuperável: {e}")
                    raise
            
            # Se chegou aqui, todas as tentativas falharam
            if ultima_excecao:
                raise ultima_excecao
        
        return wrapper
    return decorator


@contextmanager
def medir_tempo(operacao: str, registrar: bool = True):
    """
    Context manager para medir tempo de execução de operações.
    
    Args:
        operacao: Nome/descrição da operação
        registrar: Se deve registrar nas métricas do pool
    
    Uso:
        with medir_tempo("buscar_funcionario"):
            resultado = collection.find_one({"_id": id})
    """
    inicio = time.time()
    erro = False
    
    try:
        yield
    except Exception as e:
        erro = True
        raise
    finally:
        duracao_ms = (time.time() - inicio) * 1000
        
        if erro:
            logger.warning(f"⏱️ {operacao}: {duracao_ms:.2f}ms (ERRO)")
        else:
            logger.debug(f"⏱️ {operacao}: {duracao_ms:.2f}ms")
        
        # Registrar métricas
        if registrar:
            try:
                pool = MongoDBConnectionPool()
                pool.registrar_operacao(duracao_ms, erro)
            except Exception:
                pass


# =============================================================================
# Instância global (singleton)
# =============================================================================

# Criar instância global para acesso fácil
mongodb_pool = MongoDBConnectionPool()
