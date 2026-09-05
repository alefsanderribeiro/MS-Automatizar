"""
Service para gerenciar Contratos em MongoDB
Responsabilidades:
- CRUD completo de contratos
- Cache em memória permanente (até reiniciar app)
- Soft delete (verificar referências antes de inativar)
- Busca por nome/ID
- Auto-cadastro de contratos durante importação de funcionários
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import dotenv

from src.utils.dotenv_path import caminho_dotenv
from src.models.contrato_models import StatusContrato
from src.services.historico_decorators import registrar_historico, HistoricoMixin
from src.services.cache_service import cache_service
from src.services.mongodb_connection import MongoDBConnectionPool
from src.utils.logger_config_v2 import get_logger

logger = get_logger("contrato")


# Tentativa de importação do MongoDB
try:
    from pymongo import ASCENDING
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, DuplicateKeyError
    from bson.objectid import ObjectId
    MONGODB_DISPONIVEL = True
except ImportError:
    MONGODB_DISPONIVEL = False
    logger.warning("PyMongo não instalado - ContratoService ficará limitado")


class ContratoService(HistoricoMixin):
    """
    Gerencia armazenamento de Contratos em MongoDB
    
    Responsabilidades:
    - Salvar/atualizar contratos (upsert)
    - Buscar contratos por nome/ID
    - Auto-cadastro de contratos incompletos
    - Gerenciar índices para performance
    - Cache em memória para evitar buscas repetidas
    - Soft delete (marcar como inativo se referenciado)
    - Histórico de alterações via HistoricoMixin
    
    Coleção: "contratos"
    """
    
    def __init__(self, mongo_uri: str = None, 
                 db_name: str = None,
                 collection_name: str = "contratos"):
        """
        Inicializa conexão com MongoDB para Contratos
        
        Args:
            mongo_uri: String de conexão MongoDB (usa .env se não fornecido)
            db_name: Nome do banco de dados (usa .env se não fornecido)
            collection_name: Nome da coleção
        """
        # Usar valores do .env se não fornecidos
        mongo_uri = mongo_uri or dotenv.get_key(caminho_dotenv(), "MONGO_URI")
        db_name = db_name or dotenv.get_key(caminho_dotenv(), "MONGO_DATABASE_NAME")
        
        # Cache em memória para contratos (chave: ObjectId string, valor: documento)
        self._cache_contratos: Dict[str, Dict[str, Any]] = {}
        
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
                f"✓ MongoDB conectado para Contratos (via pool): {mongo_uri}/{db_name}.{collection_name}"
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
        - status para filtrar ativos/inativos
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
            
            logger.debug("✓ Índices criados para Contratos em MongoDB")
        except Exception as e:
            logger.warning(f"Erro ao criar índices: {e}")
    
    def _carregar_cache_completo(self) -> None:
        """
        Pré-carrega TODOS os contratos em cache (memória + Redis).
        
        Contratos são uma tabela de referência pequena (~50-200 registros),
        então é viável carregar tudo para otimizar lookups O(1).
        
        Cache híbrido:
        - Cache local em memória (_cache_contratos) para acesso ultra-rápido
        - Cache Redis (cache_service) para persistência entre restarts
        """
        try:
            import os
            # Buscar TODOS os contratos do MongoDB
            todos_contratos = list(self.colecao.find({}))
            
            if not todos_contratos:
                logger.warning("⚠️ Nenhum contrato encontrado para carregar cache")
                return
            
            # Poplar cache em memória (dict local)
            cache_data_redis = {}
            for contrato in todos_contratos:
                contrato_id = str(contrato["_id"])
                # Cache local
                self._cache_contratos[contrato_id] = contrato
                # Preparar para cache Redis
                cache_data_redis[f"contratos:{contrato_id}"] = contrato
            
            # Poplar cache Redis em batch (uma operação)
            ttl = int(os.getenv("CACHE_TTL", "300"))  # 5 minutos padrão
            self.cache.set_many(cache_data_redis, ttl=ttl)
            
            logger.info(f"✅ Cache de contratos carregado: {len(todos_contratos)} registros (memória + Redis)")
            
        except Exception as e:
            logger.error(f"Erro ao carregar cache de contratos: {e}")
    
    def _invalidar_cache(self) -> None:
        """
        Invalida TODO o cache de contratos (memória + Redis).
        
        Deve ser chamado após operações de CREATE, UPDATE ou DELETE
        para garantir que próximas leituras busquem dados atualizados.
        
        Após invalidação, próxima busca recarregará o cache automaticamente.
        """
        try:
            # Limpar cache local
            self._cache_contratos.clear()
            
            # Limpar cache Redis (todas as chaves contratos:*)
            deleted_count = self.cache.invalidate("contratos:*")
            
            logger.debug(f"🗑️ Cache de contratos invalidado: {deleted_count} chaves removidas do Redis")
            
            # Recarregar cache imediatamente para próximas buscas
            self._carregar_cache_completo()
            
        except Exception as e:
            logger.error(f"Erro ao invalidar cache de contratos: {e}")
    
    def _carregar_cache(self) -> None:
        """
        Carrega todos os contratos ativos no cache
        Chamado na primeira busca ou após invalidação
        """
        if not self.disponivel:
            return
        
        try:
            # Buscar todos os contratos ativos
            contratos = self.colecao.find({"status": StatusContrato.ATIVO.value})
            
            for contrato in contratos:
                contrato_id = str(contrato.get("_id"))
                self._cache_contratos[contrato_id] = contrato
            
            logger.debug(f"✓ Cache carregado com {len(self._cache_contratos)} contratos")
        except Exception as e:
            logger.error(f"Erro ao carregar cache de contratos: {e}")
    
    def buscar_por_nome(self, nome_contrato: str, exato: bool = True) -> Optional[Dict[str, Any]]:
        """
        Busca um contrato pelo nome
        
        Args:
            nome_contrato: Nome do contrato
            exato: Se True, busca exata; se False, busca parcial
        
        Returns:
            Dicionário com os dados do contrato ou None
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para busca")
            return None
        
        try:
            import unicodedata
            
            # Normalizar nome para busca
            nfkd = unicodedata.normalize('NFKD', nome_contrato)
            nome_normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)])
            nome_normalizado = nome_normalizado.lower()
            
            if exato:
                filtro = {"nome_normalizado": nome_normalizado}
            else:
                filtro = {"nome_normalizado": {"$regex": nome_normalizado, "$options": "i"}}
            
            documento = self.colecao.find_one(filtro)
            
            if documento:
                # Adicionar ao cache
                contrato_id = str(documento.get("_id"))
                self._cache_contratos[contrato_id] = documento
                logger.debug(f"✓ Contrato encontrado: {documento.get('nome')}")
                return documento
            else:
                logger.debug(f"✗ Contrato não encontrado: {nome_contrato}")
                return None
        
        except Exception as e:
            logger.error(f"Erro ao buscar contrato por nome: {e}")
            return None
    
    def buscar_por_id(self, contrato_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca um contrato por ObjectId
        Usa cache em memória
        
        Args:
            contrato_id: ID do contrato (ObjectId em formato string)
        
        Returns:
            Dicionário com os dados do contrato ou None
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para busca")
            return None
        
        # Verificar cache primeiro
        if contrato_id in self._cache_contratos:
            logger.debug(f"✓ Contrato encontrado no cache: {contrato_id}")
            return self._cache_contratos[contrato_id]
        
        try:
            # Converter string para ObjectId
            try:
                obj_id = ObjectId(contrato_id)
            except Exception:
                logger.warning(f"ID inválido para conversão: {contrato_id}")
                return None
            
            documento = self.colecao.find_one({"_id": obj_id})
            
            if documento:
                # Adicionar ao cache
                self._cache_contratos[contrato_id] = documento
                logger.debug(f"✓ Contrato encontrado por ID: {documento.get('nome')}")
                return documento
            else:
                logger.debug(f"✗ Contrato não encontrado pelo ID: {contrato_id}")
                return None
        
        except Exception as e:
            logger.error(f"Erro ao buscar contrato por ID: {e}")
            return None
    
    def listar_todos(self) -> List[Dict[str, Any]]:
        """
        Lista todos os contratos (ativos e inativos)
        
        Returns:
            Lista de contratos
        """
        if not self.disponivel:
            return []
        
        try:
            contratos = list(self.colecao.find().sort("ordem", ASCENDING))
            logger.debug(f"✓ {len(contratos)} contratos encontrados")
            return contratos
        except Exception as e:
            logger.error(f"Erro ao listar contratos: {e}")
            return []
    
    def listar_ativos(self) -> List[Dict[str, Any]]:
        """
        Lista apenas contratos ativos
        
        Returns:
            Lista de contratos ativos
        """
        if not self.disponivel:
            return []
        
        try:
            contratos = list(self.colecao.find({"status": StatusContrato.ATIVO.value}).sort("ordem", ASCENDING))
            logger.debug(f"✓ {len(contratos)} contratos ativos encontrados")
            return contratos
        except Exception as e:
            logger.error(f"Erro ao listar contratos ativos: {e}")
            return []
    
    def criar(self, contrato_modelo) -> Optional[str]:
        """
        Cria um novo contrato
        
        Args:
            contrato_modelo: Instância de ContratoMongoDB
        
        Returns:
            ID do contrato criado (string) ou None se erro
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para criar contrato")
            return None
        
        try:
            # Converter para dict
            doc = contrato_modelo.to_mongo_insert()
            
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
            
            logger.info(f"✓ Contrato criado: {contrato_modelo.nome} - ID: {resultado.inserted_id}")
            return str(resultado.inserted_id)
        
        except DuplicateKeyError:
            logger.error(f"✗ Contrato duplicado: {contrato_modelo.nome}")
            return None
        except Exception as e:
            logger.error(f"Erro ao criar contrato: {e}")
            return None
    
    @registrar_historico(campos_rastrear=None, origem_padrao="interface_cli")
    def atualizar_campos(
        self, 
        object_id: str, 
        alteracoes: Dict[str, Any],
        **kwargs
    ) -> bool:
        """
        Atualiza campos específicos de um contrato usando ObjectId.
        
        O histórico é registrado AUTOMATICAMENTE pelo decorador @registrar_historico.
        
        Args:
            object_id: ObjectId do contrato em formato string
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

            
            if resultado and resultado.modified_count > 0:

            
                self.logger.audit(

            
                    action="REGISTRO_ATUALIZADO",

            
                    target=f"{self.collection_name}",

            
                    changes={'operacao': 'update'}

            
                )
            
            if resultado.modified_count > 0:
                # Invalidar cache
                self._invalidar_cache()
                campos = ", ".join([k for k in alteracoes.keys() if k not in ['atualizado_em', 'nome_normalizado']])
                logger.info(f"✓ Contrato {object_id} atualizado - campos: {campos}")
                return True
            else:
                logger.debug(f"Contrato {object_id} sem alterações")
                return False
        except Exception as e:
            logger.error(f"Erro ao atualizar contrato: {e}")
            return False
    
    def atualizar(self, contrato_id: str, contrato_modelo) -> bool:
        """
        Atualiza um contrato existente
        
        Args:
            contrato_id: ID do contrato
            contrato_modelo: Instância de ContratoMongoDB atualizada
        
        Returns:
            True se sucesso, False caso contrário
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para atualizar")
            return False
        
        try:
            # Converter para ObjectId
            obj_id = ObjectId(contrato_id)
            
            # Converter modelo para dict de atualização
            update_doc = contrato_modelo.to_mongo_update()
            
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
                logger.info(f"✓ Contrato atualizado: {contrato_modelo.nome}")
                return True
            else:
                logger.warning(f"Nenhum contrato modificado com ID: {contrato_id}")
                return False
        
        except Exception as e:
            logger.error(f"Erro ao atualizar contrato: {e}")
            return False
    
    def marcar_inativo(self, contrato_id: str) -> bool:
        """
        Marca um contrato como inativo (soft delete)
        Verifica se há funcionários usando antes de inativar
        
        Args:
            contrato_id: ID do contrato
        
        Returns:
            True se sucesso, False se há referências ou erro
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível")
            return False
        
        try:
            # Verificar se há funcionários usando este contrato
            if self._verificar_referencias_funcionarios(contrato_id):
                logger.warning(
                    f"✗ Não é possível inativar contrato {contrato_id}: "
                    "existem funcionários vinculados"
                )
                return False
            
            # Converter para ObjectId
            obj_id = ObjectId(contrato_id)
            
            # Marcar como inativo
            resultado = self.colecao.update_one(
                {"_id": obj_id},
                {
                    "$set": {
                        "status": StatusContrato.INATIVO.value,
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
                logger.info(f"✓ Contrato marcado como inativo: {contrato_id}")
                return True
            else:
                logger.warning(f"Contrato não encontrado: {contrato_id}")
                return False
        
        except Exception as e:
            logger.error(f"Erro ao marcar contrato como inativo: {e}")
            return False
    
    def _verificar_referencias_funcionarios(self, contrato_id: str) -> bool:
        """
        Verifica se existem funcionários usando este contrato
        
        Args:
            contrato_id: ID do contrato
        
        Returns:
            True se há funcionários usando, False caso contrário
        """
        try:
            # Converter para ObjectId
            obj_id = ObjectId(contrato_id)
            
            # Buscar na coleção de funcionários
            funcionarios_colecao = self.db["funcionarios"]
            count = funcionarios_colecao.count_documents({"contrato_empresa_id": obj_id})
            
            return count > 0
        
        except Exception as e:
            logger.error(f"Erro ao verificar referências: {e}")
            return False
    
    def obter_ou_criar_auto(self, nome_contrato: str) -> Optional[Dict[str, Any]]:
        """
        Busca um contrato existente ou cria um novo com flag auto_criado
        Usado durante importação de funcionários
        
        Args:
            nome_contrato: Nome do contrato
        
        Returns:
            Dicionário com os dados do contrato (existente ou novo)
        """
        if not self.disponivel:
            logger.error("MongoDB não disponível para auto-cadastro")
            return None
        
        try:
            # Verificar se contrato já existe
            contrato_existente = self.buscar_por_nome(nome_contrato, exato=True)
            
            if contrato_existente and contrato_existente.get("_id"):
                logger.debug(f"✓ Contrato reutilizado: {nome_contrato}")
                return contrato_existente
            
            # Criar contrato auto
            from src.models.contrato_models import ContratoBuilder
            
            contrato = (ContratoBuilder()
                .set_nome(nome_contrato)
                .marcar_como_auto_criado()
                .build()
            )
            
            doc_contrato = contrato.to_mongo_insert()
            resultado = self.colecao.insert_one(doc_contrato)

            if resultado and resultado.inserted_id:

                self.logger.audit(

                    action="REGISTRO_CRIADO",

                    target=f"{self.collection_name}:{resultado.inserted_id}",

                    changes={'dados': str(doc_contrato)[:200]}

                )
            
            # Adicionar o ID gerado
            doc_contrato['_id'] = resultado.inserted_id
            
            # Invalidar cache
            self._invalidar_cache()
            
            logger.info(f"✓ Contrato auto-criado: {nome_contrato} - ID: {resultado.inserted_id}")
            return doc_contrato
        
        except DuplicateKeyError:
            # Se erro de duplicata, tentar buscar novamente
            logger.debug(f"Erro de duplicata ao criar contrato, buscando novamente")
            contrato_retry = self.buscar_por_nome(nome_contrato, exato=True)
            if contrato_retry and contrato_retry.get("_id"):
                logger.info(f"✓ Contrato encontrado após erro de duplicata: {nome_contrato}")
                return contrato_retry
            logger.error(f"Erro de duplicata mas contrato não encontrado: {nome_contrato}")
            return None
        
        except Exception as e:
            logger.error(f"Erro ao criar contrato auto: {e}")
            return None
