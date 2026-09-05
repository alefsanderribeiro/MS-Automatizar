"""
Service para gerenciar Horários de Trabalho em MongoDB
Responsabilidades:
- CRUD completo de horários
- Cache em memória permanente (até reiniciar app)
- Soft delete (verificar referências antes de inativar)
- Busca por descrição/ID
- Auto-cadastro de horários durante importação de funcionários
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import dotenv

from src.utils.dotenv_path import caminho_dotenv
from src.models.horario_models import StatusHorario
from src.services.historico_decorators import registrar_historico, HistoricoMixin
from src.services.cache_service import cache_service
from src.services.mongodb_connection import MongoDBConnectionPool
from src.utils.logger_config_v2 import get_logger

logger = get_logger("horario")


# Tentativa de importação do MongoDB
try:
    from pymongo import ASCENDING
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, DuplicateKeyError
    from bson.objectid import ObjectId
    MONGODB_DISPONIVEL = True
except ImportError:
    MONGODB_DISPONIVEL = False
    logger.warning("PyMongo não instalado - HorarioService ficará limitado")


class HorarioService(HistoricoMixin):
    """
    Gerencia armazenamento de Horários em MongoDB
    
    Responsabilidades:
    - Salvar/atualizar horários (upsert)
    - Buscar horários por descrição/ID
    - Auto-cadastro de horários incompletos
    - Gerenciar índices para performance
    - Cache em memória para evitar buscas repetidas
    - Soft delete (marcar como inativo se referenciado)
    - Histórico de alterações via HistoricoMixin
    
    Coleção: "horarios"
    """
    
    def __init__(self, mongo_uri: str = None, 
                 db_name: str = None,
                 collection_name: str = "horarios"):
        """
        Inicializa conexão com MongoDB para Horários
        
        Args:
            mongo_uri: String de conexão MongoDB (usa .env se não fornecido)
            db_name: Nome do banco de dados (usa .env se não fornecido)
            collection_name: Nome da coleção
        """
        # Usar valores do .env se não fornecidos
        mongo_uri = mongo_uri or dotenv.get_key(caminho_dotenv(), "MONGO_URI")
        db_name = db_name or dotenv.get_key(caminho_dotenv(), "MONGO_DATABASE_NAME")
        
        # Cache em memória para horários (chave: ObjectId string, valor: documento)
        self._cache_horarios: Dict[str, Dict[str, Any]] = {}
        
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
                f"✓ MongoDB conectado para Horários (via pool): {mongo_uri}/{db_name}.{collection_name}"
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
            self.colecao.create_index([("criado_em", ASCENDING)], name="idx_criado_em")
            
            logger.debug("✓ Índices criados para Horários em MongoDB")
        except Exception as e:
            logger.warning(f"Erro ao criar índices: {e}")
    
    def _carregar_cache_completo(self) -> None:
        """
        Pré-carrega TODOS os horários em cache (memória + Redis).
        
        Horários são uma tabela de referência pequena (~20-50 registros),
        então é viável carregar tudo para otimizar lookups O(1).
        
        Cache híbrido:
        - Cache local em memória (_cache_horarios) para acesso ultra-rápido
        - Cache Redis (cache_service) para persistência entre restarts
        """
        try:
            import os
            # Buscar TODOS os horários do MongoDB
            todos_horarios = list(self.colecao.find({}))
            
            if not todos_horarios:
                logger.warning("⚠️ Nenhum horário encontrado para carregar cache")
                return
            
            # Poplar cache em memória (dict local)
            cache_data_redis = {}
            for horario in todos_horarios:
                horario_id = str(horario["_id"])
                # Cache local
                self._cache_horarios[horario_id] = horario
                # Preparar para cache Redis
                cache_data_redis[f"horarios:{horario_id}"] = horario
            
            # Poplar cache Redis em batch (uma operação)
            ttl = int(os.getenv("CACHE_TTL", "300"))  # 5 minutos padrão
            self.cache.set_many(cache_data_redis, ttl=ttl)
            
            logger.info(f"✅ Cache de horários carregado: {len(todos_horarios)} registros (memória + Redis)")
            
        except Exception as e:
            logger.error(f"Erro ao carregar cache de horários: {e}")
    
    def _invalidar_cache(self) -> None:
        """
        Invalida TODO o cache de horários (memória + Redis).
        
        Deve ser chamado após operações de CREATE, UPDATE ou DELETE
        para garantir que próximas leituras busquem dados atualizados.
        
        Após invalidação, próxima busca recarregará o cache automaticamente.
        """
        try:
            # Limpar cache local
            self._cache_horarios.clear()
            
            # Limpar cache Redis (todas as chaves horarios:*)
            deleted_count = self.cache.invalidate("horarios:*")
            
            logger.debug(f"🗑️ Cache de horários invalidado: {deleted_count} chaves removidas do Redis")
            
            # Recarregar cache imediatamente para próximas buscas
            self._carregar_cache_completo()
            
        except Exception as e:
            logger.error(f"Erro ao invalidar cache de horários: {e}")
    
    def _carregar_cache(self) -> None:
        """
        Carrega todos os horários ativos no cache
        Chamado na primeira busca ou após invalidação
        """
        if not self.disponivel:
            return
        
        try:
            # Buscar todos os horários ativos
            horarios = self.colecao.find({"status": StatusHorario.ATIVO.value})
            
            for horario in horarios:
                horario_id = str(horario.get("_id"))
                self._cache_horarios[horario_id] = horario
            
            logger.debug(f"✓ Cache carregado com {len(self._cache_horarios)} horários")
        except Exception as e:
            logger.error(f"Erro ao carregar cache de horários: {e}")
    
    def buscar_por_descricao(self, descricao: str, exato: bool = True) -> Optional[Dict[str, Any]]:
        """
        Busca um horário pela descrição
        
        Args:
            descricao: Descrição do horário
            exato: Se True, busca exata; se False, busca parcial
        
        Returns:
            Dicionário com os dados do horário ou None
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para busca")
            return None
        
        try:
            import unicodedata
            
            # Normalizar descrição para busca
            nfkd = unicodedata.normalize('NFKD', descricao)
            nome_normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)])
            nome_normalizado = nome_normalizado.lower()
            
            if exato:
                filtro = {"nome_normalizado": nome_normalizado}
            else:
                filtro = {"nome_normalizado": {"$regex": nome_normalizado, "$options": "i"}}
            
            documento = self.colecao.find_one(filtro)
            
            if documento:
                # Adicionar ao cache
                horario_id = str(documento.get("_id"))
                self._cache_horarios[horario_id] = documento
                logger.debug(f"✓ Horário encontrado: {documento.get('descricao')}")
                return documento
            else:
                logger.debug(f"✗ Horário não encontrado: {descricao}")
                return None
        
        except Exception as e:
            logger.error(f"Erro ao buscar horário por descrição: {e}")
            return None
    
    def buscar_por_id(self, horario_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca um horário por ObjectId
        Usa cache em memória
        
        Args:
            horario_id: ID do horário (ObjectId em formato string)
        
        Returns:
            Dicionário com os dados do horário ou None
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para busca")
            return None
        
        # Verificar cache primeiro
        if horario_id in self._cache_horarios:
            logger.debug(f"✓ Horário encontrado no cache: {horario_id}")
            return self._cache_horarios[horario_id]
        
        try:
            # Converter string para ObjectId
            try:
                obj_id = ObjectId(horario_id)
            except Exception:
                logger.warning(f"ID inválido para conversão: {horario_id}")
                return None
            
            documento = self.colecao.find_one({"_id": obj_id})
            
            if documento:
                # Adicionar ao cache
                self._cache_horarios[horario_id] = documento
                logger.debug(f"✓ Horário encontrado por ID: {documento.get('descricao')}")
                return documento
            else:
                logger.debug(f"✗ Horário não encontrado pelo ID: {horario_id}")
                return None
        
        except Exception as e:
            logger.error(f"Erro ao buscar horário por ID: {e}")
            return None
    
    def listar_todos(self) -> List[Dict[str, Any]]:
        """
        Lista todos os horários (ativos e inativos)
        
        Returns:
            Lista de horários
        """
        if not self.disponivel:
            return []
        
        try:
            horarios = list(self.colecao.find().sort("ordem", ASCENDING))
            logger.debug(f"✓ {len(horarios)} horários encontrados")
            return horarios
        except Exception as e:
            logger.error(f"Erro ao listar horários: {e}")
            return []
    
    def listar_ativos(self) -> List[Dict[str, Any]]:
        """
        Lista apenas horários ativos
        
        Returns:
            Lista de horários ativos
        """
        if not self.disponivel:
            return []
        
        try:
            horarios = list(self.colecao.find({"status": StatusHorario.ATIVO.value}).sort("ordem", ASCENDING))
            logger.debug(f"✓ {len(horarios)} horários ativos encontrados")
            return horarios
        except Exception as e:
            logger.error(f"Erro ao listar horários ativos: {e}")
            return []
    
    def criar(self, horario_modelo) -> Optional[str]:
        """
        Cria um novo horário
        
        Args:
            horario_modelo: Instância de HorarioMongoDB
        
        Returns:
            ID do horário criado (string) ou None se erro
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para criar horário")
            return None
        
        try:
            # Converter para dict
            doc = horario_modelo.to_mongo_insert()
            
            # Inserir no MongoDB
            resultado = self.colecao.insert_one(doc)

            if resultado and resultado.inserted_id:

                self.logger.audit(

                    action="REGISTRO_CRIADO",

                    target=f"{self.collection_name}:{resultado.inserted_id}",

                    changes={'dados': str(doc)[:200]}

                )
            
            # Invalidar cache
            self._invalidar_cache()
            
            logger.info(f"✓ Horário criado: {horario_modelo.descricao} - ID: {resultado.inserted_id}")
            return str(resultado.inserted_id)
        
        except DuplicateKeyError:
            logger.error(f"✗ Horário duplicado: {horario_modelo.descricao}")
            return None
        except Exception as e:
            logger.error(f"Erro ao criar horário: {e}")
            return None
    
    @registrar_historico(campos_rastrear=None, origem_padrao="interface_cli")
    def atualizar_campos(
        self, 
        object_id: str, 
        alteracoes: Dict[str, Any],
        **kwargs
    ) -> bool:
        """
        Atualiza campos específicos de um horário usando ObjectId.
        
        O histórico é registrado AUTOMATICAMENTE pelo decorador @registrar_historico.
        
        Args:
            object_id: ObjectId do horário em formato string
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
            
            # Se descrição foi alterada, atualizar descricao_normalizada
            if 'descricao' in alteracoes:
                import unicodedata
                descricao = alteracoes['descricao']
                nfkd = unicodedata.normalize('NFKD', descricao)
                alteracoes['descricao_normalizada'] = ''.join([c for c in nfkd if not unicodedata.combining(c)]).lower()
            
            resultado = self.colecao.update_one(
                {"_id": obj_id},
                {"$set": alteracoes}
            )

            
            if resultado and resultado.modified_count > 0:

            
                self.logger.audit(

            
                    action="REGISTRO_ATUALIZADO",

            
                    target=f"{self.collection_name}",

            
                    changes={'operacao': 'update'}

            
                )
            
            if resultado.modified_count > 0:
                # Invalidar cache
                self._invalidar_cache()
                campos = ", ".join([k for k in alteracoes.keys() if k not in ['atualizado_em', 'descricao_normalizada']])
                logger.info(f"✓ Horário {object_id} atualizado - campos: {campos}")
                return True
            else:
                logger.debug(f"Horário {object_id} sem alterações")
                return False
        except Exception as e:
            logger.error(f"Erro ao atualizar horário: {e}")
            return False
    
    def atualizar(self, horario_id: str, horario_modelo) -> bool:
        """
        Atualiza um horário existente
        
        Args:
            horario_id: ID do horário
            horario_modelo: Instância de HorarioMongoDB atualizada
        
        Returns:
            True se sucesso, False caso contrário
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para atualizar")
            return False
        
        try:
            # Converter para ObjectId
            obj_id = ObjectId(horario_id)
            
            # Converter modelo para dict de atualização
            update_doc = horario_modelo.to_mongo_update()
            
            # Atualizar no MongoDB
            resultado = self.colecao.update_one(
                {"_id": obj_id},
                update_doc
            )

            if resultado and resultado.modified_count > 0:

                self.logger.audit(

                    action="REGISTRO_ATUALIZADO",

                    target=f"{self.collection_name}",

                    changes={'operacao': 'update'}

                )
            
            if resultado.modified_count > 0:
                # Invalidar cache
                self._invalidar_cache()
                logger.info(f"✓ Horário atualizado: {horario_modelo.descricao}")
                return True
            else:
                logger.warning(f"Nenhum horário modificado com ID: {horario_id}")
                return False
        
        except Exception as e:
            logger.error(f"Erro ao atualizar horário: {e}")
            return False
    
    def marcar_inativo(self, horario_id: str) -> bool:
        """
        Marca um horário como inativo (soft delete)
        Verifica se há funcionários usando antes de inativar
        
        Args:
            horario_id: ID do horário
        
        Returns:
            True se sucesso, False se há referências ou erro
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível")
            return False
        
        try:
            # Verificar se há funcionários usando este horário
            if self._verificar_referencias_funcionarios(horario_id):
                logger.warning(
                    f"✗ Não é possível inativar horário {horario_id}: "
                    "existem funcionários vinculados"
                )
                return False
            
            # Converter para ObjectId
            obj_id = ObjectId(horario_id)
            
            # Marcar como inativo
            resultado = self.colecao.update_one(
                {"_id": obj_id},
                {
                    "$set": {
                        "status": StatusHorario.INATIVO.value,
                        "atualizado_em": datetime.now(timezone.utc)
                    },
                    "$inc": {"versao": 1}
                }
            )
            
            if resultado and resultado.modified_count > 0:
                self.logger.audit(
                    action="REGISTRO_ATUALIZADO",
                    target=f"{self.collection_name}",
                    changes={'operacao': 'update'}
                )
            
            if resultado.modified_count > 0:
                # Invalidar cache
                self._invalidar_cache()
                logger.info(f"✓ Horário marcado como inativo: {horario_id}")
                return True
            else:
                logger.warning(f"Horário não encontrado: {horario_id}")
                return False
        
        except Exception as e:
            logger.error(f"Erro ao marcar horário como inativo: {e}")
            return False
    
    def _verificar_referencias_funcionarios(self, horario_id: str) -> bool:
        """
        Verifica se existem funcionários usando este horário
        
        Args:
            horario_id: ID do horário
        
        Returns:
            True se há funcionários usando, False caso contrário
        """
        try:
            # Converter para ObjectId
            obj_id = ObjectId(horario_id)
            
            # Buscar na coleção de funcionários
            funcionarios_colecao = self.db["funcionarios"]
            count = funcionarios_colecao.count_documents({"horario_id": obj_id})
            
            return count > 0
        
        except Exception as e:
            logger.error(f"Erro ao verificar referências: {e}")
            return False
    
    def obter_ou_criar_auto(self, descricao_horario: str) -> Optional[Dict[str, Any]]:
        """
        Busca um horário existente ou cria um novo com flag auto_criado
        Usado durante importação de funcionários
        
        Args:
            descricao_horario: Descrição do horário
        
        Returns:
            Dicionário com os dados do horário (existente ou novo)
        """
        if not self.disponivel:
            logger.error("MongoDB não disponível para auto-cadastro")
            return None
        
        try:
            # Verificar se horário já existe
            horario_existente = self.buscar_por_descricao(descricao_horario, exato=True)
            
            if horario_existente and horario_existente.get("_id"):
                logger.debug(f"✓ Horário reutilizado: {descricao_horario}")
                return horario_existente
            
            # Criar horário auto
            from src.models.horario_models import HorarioBuilder
            
            horario = (HorarioBuilder()
                .set_descricao(descricao_horario)
                .marcar_como_auto_criado()
                .build()
            )
            
            doc_horario = horario.to_mongo_insert()
            resultado = self.colecao.insert_one(doc_horario)

            if resultado and resultado.inserted_id:

                self.logger.audit(

                    action="REGISTRO_CRIADO",

                    target=f"{self.collection_name}:{resultado.inserted_id}",

                    changes={'dados': str(doc_horario)[:200]}

                )
            
            # Adicionar o ID gerado
            doc_horario['_id'] = resultado.inserted_id
            
            # Invalidar cache
            self._invalidar_cache()
            
            logger.info(f"✓ Horário auto-criado: {descricao_horario} - ID: {resultado.inserted_id}")
            return doc_horario
        
        except DuplicateKeyError:
            # Se erro de duplicata, tentar buscar novamente
            logger.debug(f"Erro de duplicata ao criar horário, buscando novamente")
            horario_retry = self.buscar_por_descricao(descricao_horario, exato=True)
            if horario_retry and horario_retry.get("_id"):
                logger.info(f"✓ Horário encontrado após erro de duplicata: {descricao_horario}")
                return horario_retry
            logger.error(f"Erro de duplicata mas horário não encontrado: {descricao_horario}")
            return None
        
        except Exception as e:
            logger.error(f"Erro ao criar horário auto: {e}")
            return None
