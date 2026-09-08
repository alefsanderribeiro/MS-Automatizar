"""
Service para gerenciar Envios de Folhas de Ponto em MongoDB
Responsabilidades:
- CRUD completo de registros de envio
- Controle de tentativas e status
- Busca por período, tipo, status
- Histórico de envios
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import dotenv

from src.utils.dotenv_path import caminho_dotenv
from src.models.envio_folha_ponto_models import (
    TipoEnvioEnum,
    StatusEnvioEnum,
    EnvioFolhaPontoMongoDB,
)
from src.utils.logger_config_v2 import get_logger
from src.services.historico_decorators import registrar_historico, HistoricoMixin
from src.services.mongodb_connection import MongoDBConnectionPool

# Tentativa de importação do MongoDB
try:
    from pymongo import ASCENDING, DESCENDING
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    from bson.objectid import ObjectId
    MONGODB_DISPONIVEL = True
except ImportError:
    MONGODB_DISPONIVEL = False

logger = get_logger("envio")
if not MONGODB_DISPONIVEL:
    logger.warning("PyMongo não instalado - EnvioFolhaPontoService ficará limitado")


class EnvioFolhaPontoService(HistoricoMixin):
    """
    Gerencia Envios de Folhas de Ponto em MongoDB
    
    Coleção: "envios_folhas_de_ponto"
    """
    
    def __init__(self, mongo_uri: str = None, 
                 db_name: str = None,
                 collection_name: str = "envios_folhas_de_ponto"):
        """
        Inicializa conexão com MongoDB para Envios
        """
        mongo_uri = mongo_uri or dotenv.get_key(caminho_dotenv(), "MONGO_URI")
        db_name = db_name or dotenv.get_key(caminho_dotenv(), "MONGO_DATABASE_NAME")
        
        self.logger = get_logger("envio_folha_ponto")
        
        if not MONGODB_DISPONIVEL:
            logger.error("MongoDB não disponível para Envios de Folha de Ponto")
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
            logger.debug(f"✓ MongoDB conectado para Envios (via pool): {db_name}.{collection_name}")
        
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
            # Índice composto para período
            self.colecao.create_index(
                [("ano_referencia", ASCENDING), ("mes_referencia", ASCENDING)],
                name="idx_periodo"
            )
            
            # Índices simples
            self.colecao.create_index([("tipo_envio", ASCENDING)], name="idx_tipo_envio")
            self.colecao.create_index([("status", ASCENDING)], name="idx_status")
            self.colecao.create_index([("tentativas", ASCENDING)], name="idx_tentativas")
            self.colecao.create_index([("local_contrato_polo", ASCENDING)], name="idx_local")
            self.colecao.create_index([("criado_em", DESCENDING)], name="idx_criado_em")
            self.colecao.create_index([("data_envio_sucesso", DESCENDING)], name="idx_data_envio")
            
            # Índice composto para busca de pendentes de retry
            self.colecao.create_index(
                [("status", ASCENDING), ("tentativas", ASCENDING)],
                name="idx_pendentes_retry"
            )
            
            logger.debug("✓ Índices criados para Envios de Folha de Ponto")
        except Exception as e:
            logger.warning(f"Erro ao criar índices: {e}")
    
    # ==================== CRUD ====================
    
    def registrar_envio(self, dados: Dict[str, Any]) -> Optional[str]:
        """
        Registra novo envio
        
        Args:
            dados: Dados do envio
        
        Returns:
            ID do registro ou None se erro
        """
        if not self._disponivel:
            return None
        
        try:
            # Criar modelo para validação
            envio = EnvioFolhaPontoMongoDB(**dados)
            doc = envio.model_dump()
            
            resultado = self.colecao.insert_one(doc)

            
            if resultado and resultado.inserted_id:

            
                self.logger.audit(

            
                    action="REGISTRO_CRIADO",

            
                    target=f"{self.collection_name}:{resultado.inserted_id}",

            
                    changes={'dados': str(doc)[:200]}

            
                )
            
            logger.info(
                f"✓ Envio registrado: {dados.get('tipo_envio')} para {dados.get('local_contrato_polo')} "
                f"(ID: {resultado.inserted_id})"
            )
            return str(resultado.inserted_id)
        
        except Exception as e:
            logger.error(f"Erro ao registrar envio: {e}")
            return None
    
    def buscar_por_id(self, envio_id: str) -> Optional[Dict[str, Any]]:
        """Busca envio por ID"""
        if not self._disponivel:
            return None
        
        try:
            return self.colecao.find_one({"_id": ObjectId(envio_id)})
        except Exception as e:
            logger.error(f"Erro ao buscar envio: {e}")
            return None
    
    def buscar_por_periodo(self, mes: int, ano: int, tipo: TipoEnvioEnum = None) -> List[Dict[str, Any]]:
        """
        Busca envios por período
        
        Args:
            mes: Mês de referência
            ano: Ano de referência
            tipo: Filtrar por tipo de envio (opcional)
        
        Returns:
            Lista de envios
        """
        if not self._disponivel:
            return []
        
        try:
            filtro = {
                "mes_referencia": mes,
                "ano_referencia": ano
            }
            
            if tipo:
                filtro["tipo_envio"] = tipo.value if isinstance(tipo, TipoEnvioEnum) else tipo
            
            return list(self.colecao.find(filtro).sort("criado_em", DESCENDING))
        except Exception as e:
            logger.error(f"Erro ao buscar envios por período: {e}")
            return []
    
    def buscar_por_tipo(self, tipo: TipoEnvioEnum, limit: int = 100) -> List[Dict[str, Any]]:
        """Busca envios por tipo"""
        if not self._disponivel:
            return []
        
        try:
            return list(
                self.colecao.find({
                    "tipo_envio": tipo.value if isinstance(tipo, TipoEnvioEnum) else tipo
                })
                .sort("criado_em", DESCENDING)
                .limit(limit)
            )
        except Exception as e:
            logger.error(f"Erro ao buscar envios por tipo: {e}")
            return []
    
    def buscar_por_status(self, status: StatusEnvioEnum, limit: int = 100) -> List[Dict[str, Any]]:
        """Busca envios por status"""
        if not self._disponivel:
            return []
        
        try:
            return list(
                self.colecao.find({
                    "status": status.value if isinstance(status, StatusEnvioEnum) else status
                })
                .sort("criado_em", DESCENDING)
                .limit(limit)
            )
        except Exception as e:
            logger.error(f"Erro ao buscar envios por status: {e}")
            return []
    
    def buscar_pendentes_retry(self, max_tentativas: int = 3) -> List[Dict[str, Any]]:
        """
        Busca envios com erro que ainda podem ser retentados
        
        Args:
            max_tentativas: Número máximo de tentativas permitidas
        
        Returns:
            Lista de envios pendentes de retry
        """
        if not self._disponivel:
            return []
        
        try:
            return list(
                self.colecao.find({
                    "status": StatusEnvioEnum.ERRO.value,
                    "tentativas": {"$lt": max_tentativas}
                })
                .sort("data_ultima_tentativa", ASCENDING)
            )
        except Exception as e:
            logger.error(f"Erro ao buscar pendentes de retry: {e}")
            return []
    
    def listar_historico(self, limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        """Lista histórico de envios com paginação"""
        if not self._disponivel:
            return []
        
        try:
            return list(
                self.colecao.find()
                .sort("criado_em", DESCENDING)
                .skip(skip)
                .limit(limit)
            )
        except Exception as e:
            logger.error(f"Erro ao listar histórico: {e}")
            return []
    
    # ==================== ATUALIZAÇÕES ====================
    
    def incrementar_tentativa(self, envio_id: str) -> bool:
        """
        Incrementa contador de tentativas
        
        Returns:
            True se atualizado com sucesso
        """
        if not self._disponivel:
            return False
        
        try:
            resultado = self.colecao.update_one(
                {"_id": ObjectId(envio_id)},
                {
                    "$inc": {"tentativas": 1, "versao": 1},
                    "$set": {
                        "data_ultima_tentativa": datetime.now(timezone.utc),
                        "atualizado_em": datetime.now(timezone.utc)
                    },
                    "$push": {
                        "historico_alteracoes": {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "acao": "Tentativa incrementada"
                        }
                    }
                }
            )
            
            if resultado and resultado.modified_count > 0:
                self.logger.audit(
                    action="REGISTRO_ATUALIZADO",
                    target=f"{self.collection_name}",
                    changes={'operacao': 'update'}
                )
            return resultado.modified_count > 0
        except Exception as e:
            logger.error(f"Erro ao incrementar tentativa: {e}")
            return False
    
    def marcar_enviado(self, envio_id: str, arquivos_enviados: List[str]) -> bool:
        """
        Marca envio como realizado com sucesso
        
        Args:
            envio_id: ID do envio
            arquivos_enviados: Lista de arquivos que foram enviados
        
        Returns:
            True se atualizado com sucesso
        """
        if not self._disponivel:
            return False
        
        try:
            resultado = self.colecao.update_one(
                {"_id": ObjectId(envio_id)},
                {
                    "$set": {
                        "status": StatusEnvioEnum.ENVIADO.value,
                        "arquivos_enviados": arquivos_enviados,
                        "data_envio_sucesso": datetime.now(timezone.utc),
                        "atualizado_em": datetime.now(timezone.utc)
                    },
                    "$inc": {"versao": 1},
                    "$push": {
                        "historico_alteracoes": {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "acao": "Envio realizado com sucesso",
                            "detalhes": {"arquivos": arquivos_enviados}
                        }
                    }
                }
            )
            
            if resultado and resultado.modified_count > 0:
                self.logger.audit(
                    action="REGISTRO_ATUALIZADO",
                    target=f"{self.collection_name}",
                    changes={'operacao': 'update'}
                )
            if resultado.modified_count > 0:
                logger.info(f"✓ Envio {envio_id} marcado como enviado ({len(arquivos_enviados)} arquivos)")
            
            return resultado.modified_count > 0
        except Exception as e:
            logger.error(f"Erro ao marcar como enviado: {e}")
            return False
    
    def marcar_erro(self, envio_id: str, erro_detalhes: str) -> bool:
        """
        Marca envio com erro
        
        Args:
            envio_id: ID do envio
            erro_detalhes: Descrição do erro
        
        Returns:
            True se atualizado com sucesso
        """
        if not self._disponivel:
            return False
        
        try:
            resultado = self.colecao.update_one(
                {"_id": ObjectId(envio_id)},
                {
                    "$set": {
                        "status": StatusEnvioEnum.ERRO.value,
                        "erro_detalhes": erro_detalhes,
                        "atualizado_em": datetime.now(timezone.utc)
                    },
                    "$inc": {"versao": 1},
                    "$push": {
                        "historico_alteracoes": {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "acao": "Erro no envio",
                            "detalhes": {"erro": erro_detalhes}
                        }
                    }
                }
            )
            
            if resultado and resultado.modified_count > 0:
                self.logger.audit(
                    action="REGISTRO_ATUALIZADO",
                    target=f"{self.collection_name}",
                    changes={'operacao': 'update'}
                )
            if resultado.modified_count > 0:
                logger.warning(f"⚠ Envio {envio_id} marcado com erro: {erro_detalhes}")
            
            return resultado.modified_count > 0
        except Exception as e:
            logger.error(f"Erro ao marcar erro: {e}")
            return False
    
    def marcar_parcial(self, envio_id: str, enviados: List[str], com_erro: List[str]) -> bool:
        """
        Marca envio como parcialmente realizado
        
        Args:
            envio_id: ID do envio
            enviados: Lista de arquivos enviados com sucesso
            com_erro: Lista de arquivos que falharam
        
        Returns:
            True se atualizado com sucesso
        """
        if not self._disponivel:
            return False
        
        try:
            resultado = self.colecao.update_one(
                {"_id": ObjectId(envio_id)},
                {
                    "$set": {
                        "status": StatusEnvioEnum.PARCIAL.value,
                        "arquivos_enviados": enviados,
                        "arquivos_com_erro": com_erro,
                        "atualizado_em": datetime.now(timezone.utc)
                    },
                    "$inc": {"versao": 1},
                    "$push": {
                        "historico_alteracoes": {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "acao": "Envio parcial",
                            "detalhes": {"enviados": enviados, "com_erro": com_erro}
                        }
                    }
                }
            )
            
            if resultado and resultado.modified_count > 0:
                self.logger.audit(
                    action="REGISTRO_ATUALIZADO",
                    target=f"{self.collection_name}",
                    changes={'operacao': 'update'}
                )
            if resultado.modified_count > 0:
                logger.warning(
                    f"⚠ Envio {envio_id} parcial: {len(enviados)} enviados, {len(com_erro)} com erro"
                )
            
            return resultado.modified_count > 0
        except Exception as e:
            logger.error(f"Erro ao marcar parcial: {e}")
            return False
    
    # ==================== ESTATÍSTICAS ====================
    
    def contar_por_status(self, mes: int = None, ano: int = None) -> Dict[str, int]:
        """
        Conta envios por status
        
        Args:
            mes: Filtrar por mês (opcional)
            ano: Filtrar por ano (opcional)
        
        Returns:
            Dict com contagem por status
        """
        if not self._disponivel:
            return {}
        
        try:
            filtro = {}
            if mes and ano:
                filtro["mes_referencia"] = mes
                filtro["ano_referencia"] = ano
            
            pipeline = [
                {"$match": filtro} if filtro else {"$match": {}},
                {"$group": {"_id": "$status", "count": {"$sum": 1}}}
            ]
            
            resultado = self.colecao.aggregate(pipeline)
            
            return {doc["_id"]: doc["count"] for doc in resultado}
        except Exception as e:
            logger.error(f"Erro ao contar por status: {e}")
            return {}
    
    def contar_por_tipo(self, mes: int = None, ano: int = None) -> Dict[str, int]:
        """
        Conta envios por tipo
        
        Args:
            mes: Filtrar por mês (opcional)
            ano: Filtrar por ano (opcional)
        
        Returns:
            Dict com contagem por tipo
        """
        if not self._disponivel:
            return {}
        
        try:
            filtro = {}
            if mes and ano:
                filtro["mes_referencia"] = mes
                filtro["ano_referencia"] = ano
            
            pipeline = [
                {"$match": filtro} if filtro else {"$match": {}},
                {"$group": {"_id": "$tipo_envio", "count": {"$sum": 1}}}
            ]
            
            resultado = self.colecao.aggregate(pipeline)
            
            return {doc["_id"]: doc["count"] for doc in resultado}
        except Exception as e:
            logger.error(f"Erro ao contar por tipo: {e}")
            return {}
    
    def obter_resumo_periodo(self, mes: int, ano: int) -> Dict[str, Any]:
        """
        Obtém resumo de envios para um período
        
        Returns:
            Dict com resumo (total, por status, por tipo, etc.)
        """
        if not self._disponivel:
            return {}
        
        try:
            envios = self.buscar_por_periodo(mes, ano)
            
            por_status = {}
            por_tipo = {}
            total_arquivos = 0
            
            for envio in envios:
                # Contar por status
                status = envio.get("status", "desconhecido")
                por_status[status] = por_status.get(status, 0) + 1
                
                # Contar por tipo
                tipo = envio.get("tipo_envio", "desconhecido")
                por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
                
                # Contar arquivos
                total_arquivos += len(envio.get("arquivos_enviados", []))
            
            return {
                "periodo": f"{mes:02d}/{ano}",
                "total_envios": len(envios),
                "por_status": por_status,
                "por_tipo": por_tipo,
                "total_arquivos_enviados": total_arquivos
            }
        except Exception as e:
            logger.error(f"Erro ao obter resumo: {e}")
            return {}


# Instância singleton
envio_folha_ponto_service = EnvioFolhaPontoService()
