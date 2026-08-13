"""
Service para gerenciar Templates de Mensagem em MongoDB
Responsabilidades:
- CRUD completo de templates
- Renderização de templates com placeholders
- Templates padrão por tipo de envio
- Cache em memória
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import dotenv

from src.utils.dotenv_path import caminho_dotenv
from src.utils.logger_config import logger
from src.models.template_mensagem_models import (
    TipoTemplateEnum,
    StatusTemplate,
    TemplateMensagemMongoDB,
    criar_templates_padrao,
)
from src.services.historico_decorators import registrar_historico, HistoricoMixin
from src.services.mongodb_connection import MongoDBConnectionPool
from src.services.cache_service import cache_service
from src.services import cache_keys

# Tentativa de importação do MongoDB
try:
    from pymongo import ASCENDING
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, DuplicateKeyError
    from bson.objectid import ObjectId
    MONGODB_DISPONIVEL = True
except ImportError:
    MONGODB_DISPONIVEL = False
    logger.warning("PyMongo não instalado - TemplateMensagemService ficará limitado")


class TemplateMensagemService(HistoricoMixin):
    """
    Gerencia Templates de Mensagem em MongoDB
    
    Coleção: "templates_mensagens"
    """
    
    def __init__(self, mongo_uri: str = None, 
                 db_name: str = None,
                 collection_name: str = "templates_mensagens"):
        """
        Inicializa conexão com MongoDB para Templates
        """
        mongo_uri = mongo_uri or dotenv.get_key(caminho_dotenv(), "MONGO_URI")
        db_name = db_name or dotenv.get_key(caminho_dotenv(), "MONGO_DATABASE_NAME")
        
        # Cache em memória
        self._cache_templates: Dict[str, Dict[str, Any]] = {}
        
        # Cache service (Redis + memória) para persistência entre processos
        self.cache = cache_service
        
        if not MONGODB_DISPONIVEL:
            logger.error("MongoDB não disponível para Templates")
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
            
            self._criar_indices()
            
            self._disponivel = True
            logger.debug(f"✓ MongoDB conectado para Templates (via pool): {db_name}.{collection_name}")
            
            # Inicializar templates padrão após definir _disponivel
            self._inicializar_templates_padrao()
        
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
        return self._disponivel
    
    def _criar_indices(self) -> None:
        """Cria índices na coleção"""
        try:
            self.colecao.create_index(
                [("nome_normalizado", ASCENDING)],
                unique=True,
                name="idx_nome_normalizado_unico"
            )
            self.colecao.create_index([("tipo", ASCENDING)], name="idx_tipo")
            self.colecao.create_index([("status", ASCENDING)], name="idx_status")
            self.colecao.create_index([("is_padrao", ASCENDING)], name="idx_is_padrao")
            logger.debug("✓ Índices criados para Templates")
        except Exception as e:
            logger.warning(f"Erro ao criar índices: {e}")
    
    def _inicializar_templates_padrao(self) -> None:
        """Inicializa templates padrão se não existirem"""
        try:
            count = self.colecao.count_documents({})
            if count == 0:
                logger.info("Criando templates padrão...")
                templates = criar_templates_padrao()
                for template_data in templates:
                    self.criar(template_data)
                logger.info(f"✓ {len(templates)} templates padrão criados")
            else:
                # Verificar e criar templates faltantes (ex: novos tipos)
                self._criar_templates_faltantes()
        except Exception as e:
            logger.warning(f"Erro ao criar templates padrão: {e}")
    
    def _criar_templates_faltantes(self) -> None:
        """Cria templates padrão que não existem ainda (útil após atualizações)"""
        try:
            templates = criar_templates_padrao()
            criados = 0
            
            for template_data in templates:
                tipo = template_data.get("tipo")
                if isinstance(tipo, str):
                    tipo_value = tipo
                else:
                    tipo_value = tipo.value if hasattr(tipo, 'value') else str(tipo)
                
                # Verificar se já existe um template padrão para este tipo
                existente = self.colecao.find_one({
                    "tipo": tipo_value,
                    "is_padrao": True
                })
                
                if not existente:
                    self.criar(template_data)
                    criados += 1
                    logger.info(f"  ✓ Template criado: {template_data.get('nome')}")
            
            if criados > 0:
                logger.info(f"✓ {criados} novos templates padrão criados")
        except Exception as e:
            logger.warning(f"Erro ao criar templates faltantes: {e}")
        except Exception as e:
            logger.warning(f"Erro ao criar templates padrão: {e}")
    
    def _invalidar_cache(self) -> None:
        """Limpa cache (memória local + Redis).

        Templates são pequenos e escritos de forma rara → invalidar o prefixo
        ``templates:*`` é barato e garante consistência entre processos.
        """
        self._cache_templates.clear()
        try:
            self.cache.invalidate(cache_keys.templates_prefix())
        except Exception as e:
            logger.warning(f"Erro ao invalidar cache Redis de templates: {e}")
    
    # ==================== CRUD ====================
    
    def criar(self, dados: Dict[str, Any]) -> Optional[str]:
        """
        Cria novo template
        
        Returns:
            ID do template criado ou None se erro
        """
        if not self._disponivel:
            return None
        
        try:
            # Criar modelo para validação e normalização
            template = TemplateMensagemMongoDB(**dados)
            doc = template.model_dump()
            
            resultado = self.colecao.insert_one(doc)
            self._invalidar_cache()
            
            logger.info(f"✓ Template criado: {dados.get('nome')} (ID: {resultado.inserted_id})")
            return str(resultado.inserted_id)
        
        except DuplicateKeyError:
            logger.warning(f"Template já existe: {dados.get('nome')}")
            return None
        except Exception as e:
            logger.error(f"Erro ao criar template: {e}")
            return None
    
    def buscar_por_id(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Busca template por ID"""
        if not self._disponivel:
            return None
        
        # Verificar cache (memória local)
        if template_id in self._cache_templates:
            return self._cache_templates[template_id]
        
        # Verificar cache Redis (cache-aside)
        cache_key = cache_keys.template_key(template_id)
        try:
            cached = self.cache.get(cache_key)
            if cached is not None:
                self._cache_templates[template_id] = cached
                return cached
        except Exception:
            pass
        
        try:
            doc = self.colecao.find_one({"_id": ObjectId(template_id)})
            if doc:
                self._cache_templates[template_id] = doc
                ttl = cache_keys.ttl_padrao()
                self.cache.set(cache_key, doc, ttl=ttl)
            return doc
        except Exception as e:
            logger.error(f"Erro ao buscar template: {e}")
            return None
    
    def buscar_por_nome(self, nome: str) -> Optional[Dict[str, Any]]:
        """Busca template por nome"""
        if not self._disponivel:
            return None
        
        try:
            import unicodedata
            nfkd = unicodedata.normalize('NFKD', nome)
            nome_norm = ''.join([c for c in nfkd if not unicodedata.combining(c)]).lower()
            
            # Cache-aside por nome
            cache_key = cache_keys.template_nome_key(nome_norm)
            try:
                cached = self.cache.get(cache_key)
                if cached is not None:
                    return cached or None
            except Exception:
                pass
            
            doc = self.colecao.find_one({"nome_normalizado": nome_norm})
            # Apenas cacheia hit; não grava sentinela None (get trata None como miss).
            if doc:
                ttl = cache_keys.ttl_padrao()
                self.cache.set(cache_key, doc, ttl=ttl)
            return doc
        except Exception as e:
            logger.error(f"Erro ao buscar template por nome: {e}")
            return None
    
    def buscar_por_tipo(self, tipo: TipoTemplateEnum, apenas_ativos: bool = True) -> List[Dict[str, Any]]:
        """
        Busca templates por tipo de envio
        
        Args:
            tipo: Tipo do template (email, whatsapp_grupo, whatsapp_individual)
            apenas_ativos: Se True, retorna apenas templates ativos
        
        Returns:
            Lista de templates
        """
        if not self._disponivel:
            return []
        
        try:
            filtro = {"tipo": tipo.value if isinstance(tipo, TipoTemplateEnum) else tipo}
            if apenas_ativos:
                filtro["status"] = StatusTemplate.ATIVO.value
            
            return list(self.colecao.find(filtro).sort("is_padrao", -1))
        except Exception as e:
            logger.error(f"Erro ao buscar templates por tipo: {e}")
            return []
    
    def buscar_padrao_por_tipo(self, tipo: TipoTemplateEnum) -> Optional[Dict[str, Any]]:
        """
        Busca template padrão para um tipo de envio
        
        Args:
            tipo: Tipo do template
        
        Returns:
            Template padrão ou None
        """
        if not self._disponivel:
            return None
        
        try:
            tipo_value = tipo.value if isinstance(tipo, TipoTemplateEnum) else tipo
            
            # Cache-aside por tipo
            cache_key = cache_keys.template_tipo_key(str(tipo_value))
            try:
                cached = self.cache.get(cache_key)
                if cached is not None:
                    return cached or None
            except Exception:
                pass
            
            doc = self.colecao.find_one({
                "tipo": tipo_value,
                "is_padrao": True,
                "status": StatusTemplate.ATIVO.value
            })
            # Apenas cacheia hit; não grava sentinela None (get trata None como miss).
            if doc:
                ttl = cache_keys.ttl_padrao()
                self.cache.set(cache_key, doc, ttl=ttl)
            return doc
        except Exception as e:
            logger.error(f"Erro ao buscar template padrão: {e}")
            return None
    
    def listar_todos(self, apenas_ativos: bool = True) -> List[Dict[str, Any]]:
        """Lista todos os templates"""
        if not self._disponivel:
            return []
        
        try:
            filtro = {}
            if apenas_ativos:
                filtro["status"] = StatusTemplate.ATIVO.value
            
            return list(self.colecao.find(filtro).sort([("tipo", 1), ("nome", 1)]))
        except Exception as e:
            logger.error(f"Erro ao listar templates: {e}")
            return []
    
    @registrar_historico(campos_rastrear=["nome", "corpo_mensagem", "assunto", "is_padrao"])
    def atualizar(self, template_id: str, alteracoes: Dict[str, Any], **kwargs) -> bool:
        """
        Atualiza template
        
        Returns:
            True se atualizado com sucesso
        """
        if not self._disponivel:
            return False
        
        try:
            alteracoes["atualizado_em"] = datetime.now(timezone.utc)
            alteracoes["$inc"] = {"versao": 1}
            
            # Separar operadores do $set
            set_fields = {k: v for k, v in alteracoes.items() if not k.startswith("$")}
            operadores = {k: v for k, v in alteracoes.items() if k.startswith("$")}
            
            update_doc = {"$set": set_fields}
            update_doc.update(operadores)
            
            resultado = self.colecao.update_one(
                {"_id": ObjectId(template_id)},
                update_doc
            )
            
            self._invalidar_cache()
            return resultado.modified_count > 0
        except Exception as e:
            logger.error(f"Erro ao atualizar template: {e}")
            return False
    
    def definir_como_padrao(self, template_id: str) -> bool:
        """
        Define um template como padrão para seu tipo
        Remove flag is_padrao de outros templates do mesmo tipo
        """
        if not self._disponivel:
            return False
        
        try:
            # Buscar template para obter tipo
            template = self.buscar_por_id(template_id)
            if not template:
                return False
            
            tipo = template.get("tipo")
            
            # Remover is_padrao de outros do mesmo tipo
            self.colecao.update_many(
                {"tipo": tipo, "_id": {"$ne": ObjectId(template_id)}},
                {"$set": {"is_padrao": False}}
            )
            
            # Definir como padrão
            self.colecao.update_one(
                {"_id": ObjectId(template_id)},
                {"$set": {"is_padrao": True, "atualizado_em": datetime.now(timezone.utc)}}
            )
            
            self._invalidar_cache()
            logger.info(f"✓ Template {template_id} definido como padrão para {tipo}")
            return True
        except Exception as e:
            logger.error(f"Erro ao definir template como padrão: {e}")
            return False
    
    def inativar(self, template_id: str) -> bool:
        """Inativa um template"""
        if not self._disponivel:
            return False
        
        try:
            resultado = self.colecao.update_one(
                {"_id": ObjectId(template_id)},
                {
                    "$set": {
                        "status": StatusTemplate.INATIVO.value,
                        "is_padrao": False,
                        "atualizado_em": datetime.now(timezone.utc)
                    },
                    "$inc": {"versao": 1}
                }
            )
            
            self._invalidar_cache()
            return resultado.modified_count > 0
        except Exception as e:
            logger.error(f"Erro ao inativar template: {e}")
            return False
    
    # ==================== RENDERIZAÇÃO ====================
    
    def renderizar(self, template_id: str, contexto: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Renderiza template substituindo placeholders
        
        Args:
            template_id: ID do template
            contexto: Dicionário com valores para os placeholders
                - nome: Nome do destinatário
                - mes: Número do mês
                - ano: Ano
                - mes_extenso: Nome do mês por extenso (opcional, será gerado se não fornecido)
                - local: Local/Contrato/Polo
                - empresa: Nome da empresa
        
        Returns:
            Dict com 'assunto' (se email) e 'mensagem' renderizados
        """
        template = self.buscar_por_id(template_id)
        if not template:
            logger.error(f"Template não encontrado: {template_id}")
            return None
        
        try:
            # Criar modelo para usar método de renderização
            modelo = TemplateMensagemMongoDB(**template)
            return modelo.renderizar(contexto)
        except Exception as e:
            logger.error(f"Erro ao renderizar template: {e}")
            return None
    
    def renderizar_por_tipo(self, tipo: TipoTemplateEnum, contexto: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Renderiza template padrão de um tipo
        
        Args:
            tipo: Tipo do template
            contexto: Dicionário com valores para os placeholders
        
        Returns:
            Dict com 'assunto' e 'mensagem' renderizados
        """
        template = self.buscar_padrao_por_tipo(tipo)
        if not template:
            logger.error(f"Template padrão não encontrado para tipo: {tipo}")
            return None
        
        return self.renderizar(str(template["_id"]), contexto)


# Instância singleton
template_mensagem_service = TemplateMensagemService()
