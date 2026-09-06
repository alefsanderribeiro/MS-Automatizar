"""
Service para gerenciar Cache de Grupos WhatsApp em MongoDB
Responsabilidades:
- Sincronizar grupos com API do WhatsApp
- Cache local para mapeamento nome → JID
- Busca fuzzy por nome
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import unicodedata
import dotenv

from src.utils.dotenv_path import caminho_dotenv
from src.models.grupo_whatsapp_models import (
    StatusGrupo,
    GrupoWhatsAppMongoDB,
    GrupoWhatsAppBuilder,
)
from src.utils.logger_config_v2 import get_logger
from src.services.historico_decorators import HistoricoMixin
from src.services.mongodb_connection import MongoDBConnectionPool

# Tentativa de importação do MongoDB
try:
    from pymongo import ASCENDING
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, DuplicateKeyError
    from bson.objectid import ObjectId
    MONGODB_DISPONIVEL = True
except ImportError:
    MONGODB_DISPONIVEL = False

logger = get_logger("whatsapp")
if not MONGODB_DISPONIVEL:
    logger.warning("PyMongo não instalado - GrupoWhatsAppService ficará limitado")


class GrupoWhatsAppService(HistoricoMixin):
    """
    Gerencia Cache de Grupos WhatsApp em MongoDB
    Permite busca por nome para obter JID automaticamente
    
    Coleção: "grupos_whatsapp"
    """
    
    def __init__(self, mongo_uri: str = None, 
                 db_name: str = None,
                 collection_name: str = "grupos_whatsapp"):
        """
        Inicializa conexão com MongoDB para Grupos WhatsApp
        """
        mongo_uri = mongo_uri or dotenv.get_key(caminho_dotenv(), "MONGO_URI")
        db_name = db_name or dotenv.get_key(caminho_dotenv(), "MONGO_DATABASE_NAME")
        
        self.logger = get_logger("whatsapp")
        
        # Cache em memória (chave: nome_normalizado, valor: JID)
        self._cache_nome_jid: Dict[str, str] = {}
        self._cache_carregado = False
        
        if not MONGODB_DISPONIVEL:
            logger.error("MongoDB não disponível para Grupos WhatsApp")
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
            logger.debug(f"✓ MongoDB conectado para Grupos WhatsApp (via pool): {db_name}.{collection_name}")
        
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
            # Remover índice antigo se existir (idx_jid_unico)
            try:
                self.colecao.drop_index("idx_jid_unico")
                logger.debug("Indice antigo idx_jid_unico removido")
            except Exception:
                pass  # Índice não existe, ok

            # Índice único composto: jid + device_id
            # Permite grupos com mesmo JID em dispositivos diferentes (caso raro)
            # e garante unicidade dentro de cada dispositivo
            self.colecao.create_index(
                [("jid", ASCENDING), ("whatsapp_device_id", ASCENDING)],
                unique=True,
                name="idx_jid_device_unico"
            )

            # Índice composto: nome_normalizado + device_id para buscas por nome
            self.colecao.create_index(
                [("nome_normalizado", ASCENDING), ("whatsapp_device_id", ASCENDING)],
                name="idx_nome_device"
            )

            self.colecao.create_index([("status", ASCENDING)], name="idx_status")
            self.colecao.create_index([("data_sincronizacao", ASCENDING)], name="idx_sincronizacao")
            logger.debug("Indices criados para Grupos WhatsApp (multidevice)")
        except Exception as e:
            logger.warning(f"Erro ao criar índices: {e}")
    
    def _invalidar_cache(self) -> None:
        """Limpa cache"""
        self._cache_nome_jid.clear()
        self._cache_carregado = False
    
    def _carregar_cache(self) -> None:
        """
        Carrega todos os grupos no cache.
        Chave do cache: {device_id}:{nome_normalizado}
        Isso permite grupos com mesmo nome em dispositivos diferentes.
        """
        if self._cache_carregado or not self._disponivel:
            return

        try:
            grupos = self.colecao.find({"status": StatusGrupo.ATIVO.value})
            for grupo in grupos:
                nome_norm = grupo.get("nome_normalizado", "")
                jid = grupo.get("jid", "")
                device_id = grupo.get("whatsapp_device_id", "")

                if nome_norm and jid:
                    # Chave composta: device_id:nome_normalizado
                    cache_key = f"{device_id}:{nome_norm}"
                    self._cache_nome_jid[cache_key] = jid

            self._cache_carregado = True
            logger.debug(f"Cache carregado com {len(self._cache_nome_jid)} grupos (multidevice)")
        except Exception as e:
            logger.error(f"Erro ao carregar cache: {e}")
    
    @staticmethod
    def normalizar_texto(texto: str) -> str:
        """Normaliza texto para comparação"""
        if not texto:
            return ""
        nfkd = unicodedata.normalize('NFKD', texto)
        normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)])
        return normalizado.lower().strip()
    
    # ==================== CRUD ====================
    
    def criar_ou_atualizar(self, dados: Dict[str, Any]) -> Optional[str]:
        """
        Cria ou atualiza grupo (upsert por JID)
        
        Returns:
            ID do grupo ou None se erro
        """
        if not self._disponivel:
            return None
        
        try:
            # Criar modelo para validação
            grupo = GrupoWhatsAppMongoDB(**dados)
            doc = grupo.model_dump()
            
            # Remover criado_em do $set para usar em $setOnInsert
            criado_em = doc.pop("criado_em", None)
            
            # Upsert por JID
            resultado = self.colecao.update_one(
                {"jid": doc["jid"]},
                {
                    "$set": doc,
                    "$setOnInsert": {"criado_em": criado_em or datetime.now(timezone.utc)}
                },
                upsert=True
            )
            
            if resultado and resultado.modified_count > 0:
                self.logger.audit(
                    action="REGISTRO_ATUALIZADO",
                    target=f"{self.collection_name}",
                    changes={'operacao': 'update'}
                )
            
            self._invalidar_cache()
            
            if resultado.upserted_id:
                logger.debug(f"✓ Grupo criado: {dados.get('nome')} (JID: {dados.get('jid')})")
                return str(resultado.upserted_id)
            else:
                logger.debug(f"✓ Grupo atualizado: {dados.get('nome')} (JID: {dados.get('jid')})")
                # Buscar ID existente
                existente = self.colecao.find_one({"jid": doc["jid"]})
                return str(existente["_id"]) if existente else None
        
        except Exception as e:
            logger.error(f"Erro ao criar/atualizar grupo: {e}")
            return None
    
    def buscar_por_jid(self, jid: str) -> Optional[Dict[str, Any]]:
        """Busca grupo por JID"""
        if not self._disponivel:
            return None
        
        try:
            with self.logger.performance("buscar_por_jid"):
                return self.colecao.find_one({"jid": jid})
        except Exception as e:
            logger.error(f"Erro ao buscar grupo por JID: {e}")
            return None
    
    def buscar_por_nome(self, nome: str, device_id: str, match_parcial: bool = True) -> Optional[Dict[str, Any]]:
        """
        Busca grupo por nome para um dispositivo específico

        Args:
            nome: Nome do grupo
            device_id: Device ID do WhatsApp (ex: WhatsApp-Alefe)
            match_parcial: Se True, faz busca parcial se exato não encontrar

        Returns:
            Documento do grupo ou None
        """
        if not self._disponivel:
            return None

        try:
            nome_norm = self.normalizar_texto(nome)

            # Busca exata primeiro - filtrar por device_id
            with self.logger.performance("buscar_por_nome_exato"):
                grupo = self.colecao.find_one({
                    "nome_normalizado": nome_norm,
                    "whatsapp_device_id": device_id,
                    "status": StatusGrupo.ATIVO.value
                })

            if grupo:
                return grupo

            # Busca parcial se habilitado
            if match_parcial:
                # Buscar grupos que contenham o nome ou vice-versa (filtrado por device)
                with self.logger.performance("buscar_por_nome_parcial"):
                    grupos = list(self.colecao.find({
                        "whatsapp_device_id": device_id,
                        "status": StatusGrupo.ATIVO.value
                    }))

                for g in grupos:
                    g_nome_norm = g.get("nome_normalizado", "")
                    # Match se um contém o outro
                    if nome_norm in g_nome_norm or g_nome_norm in nome_norm:
                        logger.debug(f"Match parcial: '{nome}' -> '{g.get('nome')}' (device: {device_id})")
                        return g

            return None
        except Exception as e:
            logger.error(f"Erro ao buscar grupo por nome: {e}")
            return None
    
    def obter_jid_por_nome(self, nome: str, device_id: str) -> Optional[str]:
        """
        Obtém JID do grupo pelo nome para um dispositivo específico

        Args:
            nome: Nome do grupo
            device_id: Device ID do WhatsApp (ex: WhatsApp-Alefe)

        Returns:
            JID do grupo ou None se não encontrado
        """
        if not device_id:
            logger.warning(f"Device ID nao fornecido para buscar grupo: {nome}")
            return None

        # Verificar cache primeiro
        self._carregar_cache()
        nome_norm = self.normalizar_texto(nome)

        # Chave do cache: device_id:nome_normalizado
        cache_key = f"{device_id}:{nome_norm}"

        # Busca exata no cache
        if cache_key in self._cache_nome_jid:
            return self._cache_nome_jid[cache_key]

        # Busca parcial no cache (apenas para o mesmo device)
        for chave_cache, jid in self._cache_nome_jid.items():
            # Extrair device_id e nome da chave
            if ":" in chave_cache:
                cache_device, cache_nome = chave_cache.split(":", 1)
                if cache_device == device_id:
                    if nome_norm in cache_nome or cache_nome in nome_norm:
                        logger.debug(f"Match parcial (cache): '{nome}' -> JID encontrado (device: {device_id})")
                        return jid

        # Buscar no banco
        grupo = self.buscar_por_nome(nome, device_id)
        if grupo:
            jid = grupo.get("jid")
            # Adicionar ao cache
            if nome_norm and jid:
                self._cache_nome_jid[cache_key] = jid
            return jid

        logger.warning(f"Grupo nao encontrado: {nome} (device: {device_id})")
        return None
    
    def listar_todos(self, apenas_ativos: bool = True, device_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lista todos os grupos, opcionalmente filtrados por dispositivo

        Args:
            apenas_ativos: Se True, retorna apenas grupos ativos
            device_id: Se fornecido, filtra por dispositivo específico

        Returns:
            Lista de grupos
        """
        if not self._disponivel:
            return []

        try:
            filtro = {}
            if apenas_ativos:
                filtro["status"] = StatusGrupo.ATIVO.value
            if device_id:
                filtro["whatsapp_device_id"] = device_id

            with self.logger.performance("listar_todos"):
                return list(self.colecao.find(filtro).sort("nome", 1))
        except Exception as e:
            logger.error(f"Erro ao listar grupos: {e}")
            return []
    
    def contar_grupos(self, apenas_ativos: bool = True) -> int:
        """Conta total de grupos"""
        if not self._disponivel:
            return 0
        
        try:
            filtro = {}
            if apenas_ativos:
                filtro["status"] = StatusGrupo.ATIVO.value
            
            with self.logger.performance("contar_grupos"):
                return self.colecao.count_documents(filtro)
        except Exception as e:
            logger.error(f"Erro ao contar grupos: {e}")
            return 0
    
    # ==================== SINCRONIZAÇÃO ====================
    
    def sincronizar_com_api(self, grupos_api: List[Dict[str, Any]], device_id: str) -> Dict[str, int]:
        """
        Sincroniza grupos da API com o cache local para um dispositivo específico

        Args:
            grupos_api: Lista de grupos retornados pela API do WhatsApp
                Formato esperado (go-whatsapp-web-multidevice):
                {
                    "JID": "123456@g.us",
                    "Name": "Nome do Grupo",
                    "OwnerJID": "...",
                    "Participants": [...]
                }
            device_id: Device ID do WhatsApp (ex: WhatsApp-Alefe)

        Returns:
            Dict com contagem: {"criados": X, "atualizados": Y, "inativos": Z}
        """
        if not self._disponivel:
            return {"criados": 0, "atualizados": 0, "inativos": 0}

        if not device_id:
            logger.error("Device ID obrigatorio para sincronizar grupos")
            return {"criados": 0, "atualizados": 0, "inativos": 0}

        resultados = {"criados": 0, "atualizados": 0, "inativos": 0}
        jids_atuais = set()

        try:
            logger.info(f"Sincronizando {len(grupos_api)} grupos da API (device: {device_id})...")

            for grupo_api in grupos_api:
                # Mapear campos da API
                jid = grupo_api.get("JID", "")
                if not jid or not jid.endswith("@g.us"):
                    continue

                jids_atuais.add(jid)

                dados = {
                    "jid": jid,
                    "whatsapp_device_id": device_id,
                    "nome": grupo_api.get("Name", "Sem Nome"),
                    "owner_jid": grupo_api.get("OwnerJID"),
                    "descricao": grupo_api.get("Topic"),
                    "participantes_count": len(grupo_api.get("Participants", [])),
                    "status": StatusGrupo.ATIVO.value,
                    "data_sincronizacao": datetime.now(timezone.utc)
                }

                # Verificar se existe (com filtro por jid E device_id)
                existente = self.colecao.find_one({
                    "jid": jid,
                    "whatsapp_device_id": device_id
                })

                if existente:
                    resultados["atualizados"] += 1
                else:
                    resultados["criados"] += 1

                self._criar_ou_atualizar_com_device(dados)

            # Marcar como inativos os grupos deste device que não estão mais na API
            grupos_banco = self.colecao.find({
                "status": StatusGrupo.ATIVO.value,
                "whatsapp_device_id": device_id
            })
            for grupo in grupos_banco:
                if grupo["jid"] not in jids_atuais:
                    self.colecao.update_one(
                        {"_id": grupo["_id"]},
                        {
                            "$set": {
                                "status": StatusGrupo.INATIVO.value,
                                "atualizado_em": datetime.now(timezone.utc)
                            }
                        }
                    )
                    resultados["inativos"] += 1
                    logger.debug(f"Grupo marcado como inativo: {grupo.get('nome')} (device: {device_id})")

            self._invalidar_cache()

            logger.info(
                f"Sincronizacao concluida (device: {device_id}): "
                f"{resultados['criados']} criados, "
                f"{resultados['atualizados']} atualizados, "
                f"{resultados['inativos']} inativos"
            )

            return resultados

        except Exception as e:
            logger.error(f"Erro na sincronizacao: {e}")
            return resultados

    def _criar_ou_atualizar_com_device(self, dados: Dict[str, Any]) -> Optional[str]:
        """
        Cria ou atualiza grupo (upsert por JID + device_id)

        Args:
            dados: Dicionario com dados do grupo (deve incluir whatsapp_device_id)

        Returns:
            ID do grupo ou None se erro
        """
        if not self._disponivel:
            return None

        try:
            # Criar modelo para validação
            grupo = GrupoWhatsAppMongoDB(**dados)
            doc = grupo.model_dump()

            # Remover criado_em do $set para usar em $setOnInsert
            criado_em = doc.pop("criado_em", None)

            jid = doc["jid"]
            device_id = doc.get("whatsapp_device_id", "")

            # Upsert por JID + device_id
            resultado = self.colecao.update_one(
                {"jid": jid, "whatsapp_device_id": device_id},
                {
                    "$set": doc,
                    "$setOnInsert": {"criado_em": criado_em or datetime.now(timezone.utc)}
                },
                upsert=True
            )
            
            if resultado and resultado.modified_count > 0:
                self.logger.audit(
                    action="REGISTRO_ATUALIZADO",
                    target=f"{self.collection_name}",
                    changes={'operacao': 'update'}
                )
            if resultado.upserted_id:
                logger.debug(f"Grupo criado: {dados.get('nome')} (JID: {jid}, device: {device_id})")
                return str(resultado.upserted_id)
            else:
                logger.debug(f"Grupo atualizado: {dados.get('nome')} (JID: {jid}, device: {device_id})")
                # Buscar ID existente
                existente = self.colecao.find_one({"jid": jid, "whatsapp_device_id": device_id})
                return str(existente["_id"]) if existente else None

        except Exception as e:
            logger.error(f"Erro ao criar/atualizar grupo: {e}")
            return None
    
    def listar_para_exibicao(self, device_id: str) -> List[Dict[str, str]]:
        """
        Lista grupos formatados para exibicao (tabela nome -> JID) filtrados por dispositivo.

        IMPORTANTE: device_id e OBRIGATORIO. Para listar grupos de um dispositivo especifico,
        o usuario deve selecionar a empresa/device primeiro.

        Args:
            device_id: Device ID do WhatsApp (OBRIGATORIO, ex: WhatsApp-Alefe)

        Returns:
            Lista de dicts com 'nome', 'jid', 'participantes' e 'device_id'

        Raises:
            ValueError: Se device_id nao for fornecido ou for vazio
        """
        if not device_id or not device_id.strip():
            raise ValueError(
                "device_id e obrigatorio para listar grupos. "
                "Selecione a empresa/dispositivo primeiro."
            )

        grupos = self.listar_todos(apenas_ativos=True, device_id=device_id)
        return [
            {
                "nome": g.get("nome", ""),
                "jid": g.get("jid", ""),
                "participantes": g.get("participantes_count", 0),
                "device_id": g.get("whatsapp_device_id", "")
            }
            for g in grupos
        ]

    def listar_para_exibicao_sem_filtro(self) -> List[Dict[str, str]]:
        """
        Lista TODOS os grupos formatados para exibicao (tabela nome -> JID).

        ATENCAO: Este metodo retorna grupos de TODOS os dispositivos.
        Use apenas para fins administrativos (debug, auditoria).
        Para uso normal, use listar_para_exibicao(device_id).

        Returns:
            Lista de dicts com 'nome', 'jid', 'participantes' e 'device_id'
        """
        grupos = self.listar_todos(apenas_ativos=True, device_id=None)
        return [
            {
                "nome": g.get("nome", ""),
                "jid": g.get("jid", ""),
                "participantes": g.get("participantes_count", 0),
                "device_id": g.get("whatsapp_device_id", "")
            }
            for g in grupos
        ]


# Instância singleton
grupo_whatsapp_service = GrupoWhatsAppService()
