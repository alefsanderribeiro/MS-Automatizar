"""
Service para gerenciar Funções em MongoDB
Responsabilidades:
- CRUD completo de funções
- Cache em memória permanente (até reiniciar app)
- Soft delete (verificar referências antes de inativar)
- Busca por nome/ID
- Auto-cadastro de funções durante importação de funcionários
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import dotenv

from src.utils.dotenv_path import caminho_dotenv
from src.utils.logger_config import logger
from src.models.funcao_models import StatusFuncao
from src.services.historico_decorators import registrar_historico, HistoricoMixin
from src.services.cache_service import cache_service
from src.services import cache_keys
from src.services.mongodb_connection import MongoDBConnectionPool

# Tentativa de importação do MongoDB
try:
    from pymongo import ASCENDING
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, DuplicateKeyError
    from bson.objectid import ObjectId
    MONGODB_DISPONIVEL = True
except ImportError:
    MONGODB_DISPONIVEL = False
    logger.warning("PyMongo não instalado - FuncaoService ficará limitado")


class FuncaoService(HistoricoMixin):
    """
    Gerencia armazenamento de Funções em MongoDB
    
    Responsabilidades:
    - Salvar/atualizar funções (upsert)
    - Buscar funções por nome/ID
    - Auto-cadastro de funções incompletas
    - Gerenciar índices para performance
    - Cache em memória para evitar buscas repetidas
    - Soft delete (marcar como inativo se referenciado)
    - Histórico de alterações via HistoricoMixin
    
    Coleção: "funcoes"
    """
    
    def __init__(self, mongo_uri: str = None, 
                 db_name: str = None,
                 collection_name: str = "funcoes"):
        """
        Inicializa conexão com MongoDB para Funções
        
        Args:
            mongo_uri: String de conexão MongoDB (usa .env se não fornecido)
            db_name: Nome do banco de dados (usa .env se não fornecido)
            collection_name: Nome da coleção
        """
        # Usar valores do .env se não fornecidos
        mongo_uri = mongo_uri or dotenv.get_key(caminho_dotenv(), "MONGO_URI")
        db_name = db_name or dotenv.get_key(caminho_dotenv(), "MONGO_DATABASE_NAME")
        
        # Cache em memória para funções (chave: ObjectId string, valor: documento)
        self._cache_funcoes: Dict[str, Dict[str, Any]] = {}
        
        # Cache service (Redis + memória) para otimização
        self.cache = cache_service
        
        if not MONGODB_DISPONIVEL:
            logger.error(
                "MongoDB não disponível. "
                "Instale PyMongo com: pip install pymongo"
            )
            self.db = None
            self.colecao = None
            self.pool = None
            self._disponivel = False
            return
        
        try:
            self.mongo_uri = mongo_uri
            self.db_name = db_name
            self.collection_name = collection_name
            
            # Usar pool centralizado em vez de criar novo MongoClient
            self.pool = MongoDBConnectionPool()
            self.db = self.pool.get_database()

            if self.db is None:
                logger.error("Banco de dados não disponível no pool MongoDB")
                self.pool = None
                self.db = None
                self.colecao = None
                self._disponivel = False
                return

            # Obter banco e coleção
            self.colecao = self.db[collection_name]
            
            # Criar índices para melhor performance
            self._criar_indices()
            
            # Carregar cache completo para otimização
            self._carregar_cache_completo()
            
            self._disponivel = True
            logger.debug(
                f"✓ MongoDB conectado para Funções (via pool): {mongo_uri}/{db_name}.{collection_name}"
            )
        
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"✗ Erro ao conectar MongoDB: {e}")
            self.pool = None
            self.db = None
            self.colecao = None
            self._disponivel = False
        except Exception as e:
            logger.error(f"✗ Erro ao inicializar MongoDB: {e}")
            self.pool = None
            self.db = None
            self.colecao = None
            self._disponivel = False
    
    @property
    def disponivel(self) -> bool:
        """Verifica se MongoDB está disponível"""
        return self._disponivel
    
    def _criar_indices(self) -> None:
        """
        Cria índices na coleção para melhor performance
        Índices criados:
        - nome_normalizado (único) para evitar duplicatas
        - ativo para filtrar ativos/inativos
        - funcao_geral para agrupar por categoria
        """
        try:
            # Índice único em nome_normalizado
            self.colecao.create_index(
                [("nome_normalizado", ASCENDING)],
                unique=True,
                name="idx_nome_normalizado_unico"
            )
            
            # Índices simples para buscas frequentes
            self.colecao.create_index([("status", ASCENDING)], name="idx_status")
            self.colecao.create_index([("auto_criado", ASCENDING)], name="idx_auto_criado")
            self.colecao.create_index([("funcao_geral", ASCENDING)], name="idx_funcao_geral")
            self.colecao.create_index([("criado_em", ASCENDING)], name="idx_criado_em")
            
            logger.debug("✓ Índices criados para Funções em MongoDB")
        except Exception as e:
            logger.warning(f"Erro ao criar índices: {e}")
    
    def _carregar_cache_completo(self) -> None:
        """
        Pré-carrega TODAS as funções em cache (memória + Redis).
        
        Funções são uma tabela de referência pequena (~30-100 registros),
        então é viável carregar tudo para otimizar lookups O(1).
        
        Cache híbrido:
        - Cache local em memória (_cache_funcoes) para acesso ultra-rápido
        - Cache Redis (cache_service) para persistência entre restarts
        """
        try:
            import os
            # Buscar TODAS as funções do MongoDB
            todas_funcoes = list(self.colecao.find({}))
            
            if not todas_funcoes:
                logger.warning("⚠️ Nenhuma função encontrada para carregar cache")
                return
            
            # Poplar cache em memória (dict local)
            cache_data_redis = {}
            for funcao in todas_funcoes:
                funcao_id = str(funcao["_id"])
                # Cache local
                self._cache_funcoes[funcao_id] = funcao
                # Preparar para cache Redis
                cache_data_redis[f"funcoes:{funcao_id}"] = funcao
            
            # Poplar cache Redis em batch (uma operação)
            ttl = int(os.getenv("CACHE_TTL", "300"))  # 5 minutos padrão
            self.cache.set_many(cache_data_redis, ttl=ttl)
            
            logger.info(f"✅ Cache de funções carregado: {len(todas_funcoes)} registros (memória + Redis)")
            
        except Exception as e:
            logger.error(f"Erro ao carregar cache de funções: {e}")
    
    def _invalidar_cache(self, registro_id=None) -> None:
        """
        Invalida o cache de funções (memória + Redis) de forma direcionada.

        - ``registro_id`` informado: invalida apenas a chave do registro. A
          próxima leitura usa cache-aside e repopula SEM recarregar a coleção
          inteira.
        - ``registro_id`` None (ex: criação): invalida o prefixo ``funcoes:*``
          (barato, pois a coleção é pequena e a escrita rara).

        Obs: não há invalidação indexada por nome aqui — a busca por nome lê
        direto do Mongo, portanto não há cache a invalidar.
        """
        try:
            if registro_id is not None:
                # Remover entrada do cache local
                self._cache_funcoes.pop(str(registro_id), None)
                # Invalidação direcionada por ID (sem full-reload do Mongo)
                self.cache.invalidate(cache_keys.funcao_key(registro_id))
            else:
                # Limpar cache local
                self._cache_funcoes.clear()
                # Limpar cache Redis (todas as chaves funcoes:*)
                deleted_count = self.cache.invalidate(cache_keys.funcoes_prefix())
                logger.debug(f"🗑️ Cache de funções invalidado: {deleted_count} chaves removidas do Redis")
        except Exception as e:
            logger.error(f"Erro ao invalidar cache de funções: {e}")
    
    def _carregar_cache(self) -> None:
        """
        Carrega todas as funções ativas no cache
        Chamado na primeira busca ou após invalidação
        """
        if not self.disponivel:
            return
        
        try:
            # Buscar todas as funções ativas
            funcoes = self.colecao.find({"status": StatusFuncao.ATIVO.value})
            
            for funcao in funcoes:
                funcao_id = str(funcao.get("_id"))
                self._cache_funcoes[funcao_id] = funcao
            
            logger.debug(f"✓ Cache carregado com {len(self._cache_funcoes)} funções")
        except Exception as e:
            logger.error(f"Erro ao carregar cache de funções: {e}")
    
    def buscar_por_nome(self, nome_funcao: str, exato: bool = True) -> Optional[Dict[str, Any]]:
        """
        Busca uma função pelo nome
        
        Args:
            nome_funcao: Nome da função
            exato: Se True, busca exata; se False, busca parcial
        
        Returns:
            Dicionário com os dados da função ou None
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para busca")
            return None
        
        try:
            import unicodedata
            
            # Normalizar nome para busca
            nfkd = unicodedata.normalize('NFKD', nome_funcao)
            nome_normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)])
            nome_normalizado = nome_normalizado.lower()
            
            if exato:
                filtro = {"nome_normalizado": nome_normalizado}
            else:
                filtro = {"nome_normalizado": {"$regex": nome_normalizado, "$options": "i"}}
            
            documento = self.colecao.find_one(filtro)
            
            if documento:
                # Adicionar ao cache
                funcao_id = str(documento.get("_id"))
                self._cache_funcoes[funcao_id] = documento
                logger.debug(f"✓ Função encontrada: {documento.get('nome')}")
                return documento
            else:
                logger.debug(f"✗ Função não encontrada: {nome_funcao}")
                return None
        
        except Exception as e:
            logger.error(f"Erro ao buscar função por nome: {e}")
            return None
    
    def buscar_por_id(self, funcao_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca uma função por ObjectId
        Usa cache em memória
        
        Args:
            funcao_id: ID da função (ObjectId em formato string)
        
        Returns:
            Dicionário com os dados da função ou None
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para busca")
            return None
        
        cache_key = cache_keys.funcao_key(funcao_id)
        
        # Verificar cache local primeiro (mais rápido - O(1))
        if funcao_id in self._cache_funcoes:
            logger.debug(f"✓ Função encontrada no cache local: {funcao_id}")
            return self._cache_funcoes[funcao_id]
        
        # Verificar cache Redis (cache-aside: hit evita query no Mongo)
        try:
            funcao_redis = self.cache.get(cache_key)
            if funcao_redis:
                self._cache_funcoes[funcao_id] = funcao_redis
                logger.debug(f"✓ Função encontrada no cache Redis: {funcao_id}")
                return funcao_redis
        except Exception:
            pass
        
        try:
            # Converter string para ObjectId
            try:
                obj_id = ObjectId(funcao_id)
            except Exception:
                logger.warning(f"ID inválido para conversão: {funcao_id}")
                return None
            
            documento = self.colecao.find_one({"_id": obj_id})
            
            if documento:
                # Cache-aside: popular cache local + Redis (com TTL)
                self._cache_funcoes[funcao_id] = documento
                ttl = cache_keys.ttl_padrao()
                self.cache.set(cache_key, documento, ttl=ttl)
                logger.debug(f"✓ Função encontrada por ID (cache miss): {documento.get('nome')}")
                return documento
            else:
                logger.debug(f"✗ Função não encontrada pelo ID: {funcao_id}")
                return None
        
        except Exception as e:
            logger.error(f"Erro ao buscar função por ID: {e}")
            return None
    
    def listar_todos(self) -> List[Dict[str, Any]]:
        """
        Lista todas as funções (ativas e inativas)
        
        Returns:
            Lista de funções
        """
        if not self.disponivel:
            return []
        
        try:
            funcoes = list(self.colecao.find().sort("ordem", ASCENDING))
            logger.debug(f"✓ {len(funcoes)} funções encontradas")
            return funcoes
        except Exception as e:
            logger.error(f"Erro ao listar funções: {e}")
            return []
    
    def listar_ativos(self) -> List[Dict[str, Any]]:
        """
        Lista apenas funções ativas
        
        Returns:
            Lista de funções ativas
        """
        if not self.disponivel:
            return []
        
        try:
            funcoes = list(self.colecao.find({"status": StatusFuncao.ATIVO.value}).sort("ordem", ASCENDING))
            logger.debug(f"✓ {len(funcoes)} funções ativas encontradas")
            return funcoes
        except Exception as e:
            logger.error(f"Erro ao listar funções ativas: {e}")
            return []
    
    def listar_por_categoria(self, funcao_geral: str) -> List[Dict[str, Any]]:
        """
        Lista funções de uma categoria específica
        
        Args:
            funcao_geral: Categoria da função (ex: ADMINISTRATIVO, MOTORISTA)
        
        Returns:
            Lista de funções da categoria
        """
        if not self.disponivel:
            return []
        
        try:
            funcoes = list(self.colecao.find({
                "funcao_geral": funcao_geral,
                "status": StatusFuncao.ATIVO.value
            }).sort("ordem", ASCENDING))
            logger.debug(f"✓ {len(funcoes)} funções encontradas na categoria {funcao_geral}")
            return funcoes
        except Exception as e:
            logger.error(f"Erro ao listar funções por categoria: {e}")
            return []
    
    def criar(self, funcao_modelo) -> Optional[str]:
        """
        Cria uma nova função
        
        Args:
            funcao_modelo: Instância de FuncaoMongoDB
        
        Returns:
            ID da função criada (string) ou None se erro
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para criar função")
            return None
        
        try:
            # Converter para dict
            doc = funcao_modelo.to_mongo_insert()
            
            # Inserir no MongoDB
            resultado = self.colecao.insert_one(doc)
            
            # Invalidar cache (nova função pode afetar nome/lista → prefixo todo)
            self._invalidar_cache()
            
            logger.info(f"✓ Função criada: {funcao_modelo.nome} - ID: {resultado.inserted_id}")
            return str(resultado.inserted_id)
        
        except DuplicateKeyError:
            logger.error(f"✗ Função duplicada: {funcao_modelo.nome}")
            return None
        except Exception as e:
            logger.error(f"Erro ao criar função: {e}")
            return None
    
    @registrar_historico(campos_rastrear=None, origem_padrao="interface_cli")
    def atualizar_campos(
        self, 
        object_id: str, 
        alteracoes: Dict[str, Any],
        **kwargs
    ) -> bool:
        """
        Atualiza campos específicos de uma função usando ObjectId.
        
        O histórico é registrado AUTOMATICAMENTE pelo decorador @registrar_historico.
        
        Args:
            object_id: ObjectId da função em formato string
            alteracoes: Dicionário com campos a atualizar
            **kwargs: 
                - registrar_historico (bool): Se False, não registra histórico
                - origem (str): Origem da alteração
        
        Returns:
            True se sucesso, False caso contrário
        """
        if not self.disponivel:
            return False
        
        try:
            try:
                obj_id = ObjectId(object_id)
            except Exception as e:
                logger.warning(f"ObjectId inválido: {object_id}. Erro: {e}")
                return False
            
            # Atualizar timestamp
            alteracoes['atualizado_em'] = datetime.now(timezone.utc)
            
            # Se nome foi alterado, atualizar nome_normalizado
            if 'nome' in alteracoes:
                import unicodedata
                nome = alteracoes['nome']
                nfkd = unicodedata.normalize('NFKD', nome)
                alteracoes['nome_normalizado'] = ''.join([c for c in nfkd if not unicodedata.combining(c)]).lower()
            
            resultado = self.colecao.update_one(
                {"_id": obj_id},
                {"$set": alteracoes}
            )
            
            if resultado.modified_count > 0:
                # Invalidação direcionada por ID; renome limpa todo o prefixo (raro)
                if "nome" in alteracoes:
                    self._invalidar_cache()
                else:
                    self._invalidar_cache(registro_id=object_id)
                campos = ", ".join([k for k in alteracoes.keys() if k not in ['atualizado_em', 'nome_normalizado']])
                logger.info(f"✓ Função {object_id} atualizada - campos: {campos}")
                return True
            else:
                logger.debug(f"Função {object_id} sem alterações")
                return False
        except Exception as e:
            logger.error(f"Erro ao atualizar função: {e}")
            return False
    
    def atualizar(self, funcao_id: str, funcao_modelo) -> bool:
        """
        Atualiza uma função existente
        
        Args:
            funcao_id: ID da função
            funcao_modelo: Instância de FuncaoMongoDB atualizada
        
        Returns:
            True se sucesso, False caso contrário
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para atualizar")
            return False
        
        try:
            # Converter para ObjectId
            obj_id = ObjectId(funcao_id)
            
            # Converter modelo para dict de atualização
            update_doc = funcao_modelo.to_mongo_update()
            
            # Atualizar no MongoDB
            resultado = self.colecao.update_one(
                {"_id": obj_id},
                update_doc
            )
            
            if resultado.modified_count > 0:
                # Invalidação direcionada por ID
                self._invalidar_cache(registro_id=funcao_id)
                logger.info(f"✓ Função atualizada: {funcao_modelo.nome}")
                return True
            else:
                logger.warning(f"Nenhuma função modificada com ID: {funcao_id}")
                return False
        
        except Exception as e:
            logger.error(f"Erro ao atualizar função: {e}")
            return False
    
    def marcar_inativo(self, funcao_id: str) -> bool:
        """
        Marca uma função como inativa (soft delete)
        Verifica se há funcionários usando antes de inativar
        
        Args:
            funcao_id: ID da função
        
        Returns:
            True se sucesso, False se há referências ou erro
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível")
            return False
        
        try:
            # Verificar se há funcionários usando esta função
            if self._verificar_referencias_funcionarios(funcao_id):
                logger.warning(
                    f"✗ Não é possível inativar função {funcao_id}: "
                    "existem funcionários vinculados"
                )
                return False
            
            # Converter para ObjectId
            obj_id = ObjectId(funcao_id)
            
            # Marcar como inativo
            resultado = self.colecao.update_one(
                {"_id": obj_id},
                {
                    "$set": {
                        "status": StatusFuncao.INATIVO.value,
                        "atualizado_em": datetime.now(timezone.utc)
                    },
                    "$inc": {"versao": 1}
                }
            )
            
            if resultado.modified_count > 0:
                # Invalidação direcionada por ID
                self._invalidar_cache(registro_id=funcao_id)
                logger.info(f"✓ Função marcada como inativa: {funcao_id}")
                return True
            else:
                logger.warning(f"Função não encontrada: {funcao_id}")
                return False
        
        except Exception as e:
            logger.error(f"Erro ao marcar função como inativa: {e}")
            return False
    
    def _verificar_referencias_funcionarios(self, funcao_id: str) -> bool:
        """
        Verifica se existem funcionários usando esta função
        
        Args:
            funcao_id: ID da função
        
        Returns:
            True se há funcionários usando, False caso contrário
        """
        try:
            # Converter para ObjectId
            obj_id = ObjectId(funcao_id)
            
            # Buscar na coleção de funcionários
            funcionarios_colecao = self.db["funcionarios"]
            count = funcionarios_colecao.count_documents({"funcao_id": obj_id})
            
            return count > 0
        
        except Exception as e:
            logger.error(f"Erro ao verificar referências: {e}")
            return False
    
    def obter_ou_criar_auto(self, nome_funcao: str, funcao_geral: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Busca uma função existente ou cria uma nova com flag auto_criado
        Usado durante importação de funcionários
        
        Args:
            nome_funcao: Nome da função
            funcao_geral: Categoria geral (opcional)
        
        Returns:
            Dicionário com os dados da função (existente ou nova)
        """
        if not self.disponivel:
            logger.error("MongoDB não disponível para auto-cadastro")
            return None
        
        try:
            # Verificar se função já existe
            funcao_existente = self.buscar_por_nome(nome_funcao, exato=True)
            
            if funcao_existente and funcao_existente.get("_id"):
                logger.debug(f"✓ Função reutilizada: {nome_funcao}")
                return funcao_existente
            
            # Criar função auto
            from src.models.funcao_models import FuncaoBuilder
            
            builder = (FuncaoBuilder()
                .set_nome(nome_funcao)
                .marcar_como_auto_criado()
            )
            
            # Adicionar categoria se fornecida
            if funcao_geral:
                builder.set_funcao_geral(funcao_geral)
            
            funcao = builder.build()
            
            doc_funcao = funcao.to_mongo_insert()
            resultado = self.colecao.insert_one(doc_funcao)
            
            # Adicionar o ID gerado
            doc_funcao['_id'] = resultado.inserted_id
            
            # Invalidar cache (nova função auto-criada; prefixo todo é seguro)
            self._invalidar_cache()
            
            logger.info(f"✓ Função auto-criada: {nome_funcao} - ID: {resultado.inserted_id}")
            return doc_funcao
        
        except DuplicateKeyError:
            # Se erro de duplicata, tentar buscar novamente
            logger.debug(f"Erro de duplicata ao criar função, buscando novamente")
            funcao_retry = self.buscar_por_nome(nome_funcao, exato=True)
            if funcao_retry and funcao_retry.get("_id"):
                logger.info(f"✓ Função encontrada após erro de duplicata: {nome_funcao}")
                return funcao_retry
            logger.error(f"Erro de duplicata mas função não encontrada: {nome_funcao}")
            return None
        
        except Exception as e:
            logger.error(f"Erro ao criar função auto: {e}")
            return None
