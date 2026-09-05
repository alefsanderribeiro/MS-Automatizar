"""
Serviço de Holerites em MongoDB
Gerencia armazenamento, busca e atualização de holerites
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import dotenv

from src.utils.dotenv_path import caminho_dotenv
from src.services.mongodb_connection import MongoDBConnectionPool, retry_mongodb, medir_tempo
from src.models.holerite_models import (
    HoleriteMongoDB,
    EnvioHoleriteMongoDB,
    StatusHoleriteEnum,
    TipoFolhaEnum
)
from src.utils.logger_config_v2 import get_logger

try:
    from pymongo import ASCENDING, DESCENDING
    from pymongo.errors import DuplicateKeyError
    from bson import ObjectId
    MONGODB_DISPONIVEL = True
except ImportError:
    MONGODB_DISPONIVEL = False

logger = get_logger("holerite")
if not MONGODB_DISPONIVEL:
    logger.warning("PyMongo não instalado. Instale com: pip install pymongo")


class HoleriteService:
    """
    Gerencia holerites em MongoDB.
    Permite busca, criação, atualização e controle de envio.
    Usa MongoDBConnectionPool para evitar múltiplas conexões.
    """

    def __init__(
        self,
        collection_name: str = "holerites",
        collection_envios: str = "envios_holerites"
    ):
        """
        Inicializa serviço de holerites usando pool centralizado.

        Args:
            collection_name: Nome da coleção para holerites
            collection_envios: Nome da coleção para registros de envio
        """
        # Armazenar informações do .env para referência
        self.mongo_uri = dotenv.get_key(caminho_dotenv(), "MONGO_URI") or "mongodb://localhost:27017"
        self.db_name = dotenv.get_key(caminho_dotenv(), "MONGO_DATABASE_NAME") or "MS_Automatizar"
        self.collection_name = collection_name
        self.collection_envios = collection_envios

        if not MONGODB_DISPONIVEL:
            logger.error("MongoDB não disponível para Holerites")
            self.pool = None
            self.db = None
            self.colecao = None
            self.colecao_envios = None
            self._disponivel = False
            return

        try:
            # Usar pool centralizado
            self.pool = MongoDBConnectionPool()
            self.db = self.pool.get_database()

            if self.db is None:
                logger.error("Banco de dados não disponível no pool MongoDB")
                self._disponivel = False
                return

            self.colecao = self.db[collection_name]
            self.colecao_envios = self.db[collection_envios]
            
            self._criar_indices()

            self._disponivel = True
            logger.debug(f"✓ HoleriteService inicializado (usando pool centralizado)")

        except Exception as e:
            logger.error(f"✗ Erro ao inicializar HoleriteService: {e}")
            self.pool = None
            self.db = None
            self.colecao = None
            self.colecao_envios = None
            self._disponivel = False
    
    @property
    def disponivel(self) -> bool:
        """Verifica se MongoDB está disponível"""
        return self._disponivel
    
    def _criar_indices(self) -> None:
        """
        Cria índices para melhor performance.
        """
        try:
            # Índice composto único: funcionário + competência + tipo_folha
            # Um funcionário só pode ter um holerite por competência e tipo
            self.colecao.create_index(
                [
                    ("funcionario_id", ASCENDING),
                    ("competencia", ASCENDING),
                    ("tipo_folha", ASCENDING)
                ],
                unique=True,
                name="idx_holerite_unico"
            )
            
            # Índice por hash do arquivo (para evitar duplicatas de arquivo)
            self.colecao.create_index(
                [("arquivo.hash_sha256", ASCENDING)],
                unique=True,
                sparse=True,  # Ignora documentos sem hash
                name="idx_arquivo_hash"
            )
            
            # Índices para busca
            self.colecao.create_index(
                [("funcionario_documento", ASCENDING)],
                name="idx_funcionario_doc"
            )
            
            self.colecao.create_index(
                [("empresa_id", ASCENDING)],
                name="idx_empresa"
            )
            
            self.colecao.create_index(
                [("competencia", DESCENDING)],
                name="idx_competencia"
            )
            
            self.colecao.create_index(
                [("status", ASCENDING)],
                name="idx_status"
            )
            
            self.colecao.create_index(
                [("criado_em", DESCENDING)],
                name="idx_criado_em"
            )
            
            # Índices para envios
            self.colecao_envios.create_index(
                [("holerite_id", ASCENDING)],
                name="idx_holerite"
            )
            
            self.colecao_envios.create_index(
                [("funcionario_id", ASCENDING)],
                name="idx_funcionario"
            )
            
            self.colecao_envios.create_index(
                [("enviado_em", DESCENDING)],
                name="idx_enviado_em"
            )
            
            logger.debug("✓ Índices criados para Holerites em MongoDB")
        except Exception as e:
            logger.warning(f"Erro ao criar índices de holerites: {e}")
    
    def calcular_hash_arquivo(self, caminho_arquivo: str) -> Optional[str]:
        """
        Calcula hash SHA256 de um arquivo PDF.
        
        Args:
            caminho_arquivo: Caminho completo do arquivo
        
        Returns:
            Hash SHA256 em hexadecimal ou None se erro
        """
        try:
            path = Path(caminho_arquivo)
            if not path.exists():
                logger.warning(f"Arquivo não encontrado: {caminho_arquivo}")
                return None
            
            sha256 = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"Erro ao calcular hash do arquivo: {e}")
            return None
    
    def criar_holerite(self, holerite: Dict[str, Any]) -> Optional[ObjectId]:
        """
        Cria um novo holerite no MongoDB.
        
        Args:
            holerite: Dicionário com dados do holerite (ou modelo Pydantic)
        
        Returns:
            ObjectId do holerite criado ou None se erro
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para criar holerite")
            return None
        
        try:
            # Se for objeto Pydantic, converter
            if hasattr(holerite, 'model_dump'):
                doc = holerite.model_dump()
            elif hasattr(holerite, 'dict'):
                doc = holerite.dict()
            else:
                doc = holerite.copy()
            
            # Remover _id se existir (MongoDB gera automaticamente)
            doc.pop('_id', None)
            
            # Garantir campos de controle
            if 'criado_em' not in doc:
                doc['criado_em'] = datetime.now(timezone.utc)
            if 'atualizado_em' not in doc:
                doc['atualizado_em'] = datetime.now(timezone.utc)
            if 'status' not in doc:
                doc['status'] = StatusHoleriteEnum.PENDENTE.value
            
            resultado = self.colecao.insert_one(doc)

            
            if resultado and resultado.inserted_id:

            
                self.logger.audit(

            
                    action="REGISTRO_CRIADO",

            
                    target=f"{self.collection_name}:{resultado.inserted_id}",

            
                    changes={'dados': str(doc)[:200]}

            
                )
            if resultado.inserted_id:
                logger.info(f"✓ Holerite criado: {resultado.inserted_id}")
                return resultado.inserted_id
            
            return None
            
        except DuplicateKeyError as e:
            # Já existe - tentar buscar o existente
            logger.warning(f"Holerite já existe (duplicata): {e}")
            # Tentar buscar o existente pelo hash
            if 'arquivo' in doc and doc['arquivo'].get('hash_sha256'):
                existente = self.colecao.find_one({
                    "arquivo.hash_sha256": doc['arquivo']['hash_sha256']
                })
                if existente:
                    return existente['_id']
            return None
        except Exception as e:
            logger.error(f"Erro ao criar holerite: {e}")
            return None
    
    def buscar_por_id(self, holerite_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca holerite por ObjectId.
        
        Args:
            holerite_id: ObjectId em formato string
        
        Returns:
            Dicionário com dados do holerite ou None
        """
        if not self.disponivel:
            return None
        
        try:
            object_id = ObjectId(holerite_id)
            return self.colecao.find_one({"_id": object_id})
        except Exception as e:
            logger.error(f"Erro ao buscar holerite por ID: {e}")
            return None
    
    def buscar_por_hash(self, hash_sha256: str) -> Optional[Dict[str, Any]]:
        """
        Busca holerite pelo hash SHA256 do arquivo.
        
        Args:
            hash_sha256: Hash SHA256 do arquivo PDF
        
        Returns:
            Dicionário com dados do holerite ou None
        """
        if not self.disponivel:
            return None
        
        try:
            return self.colecao.find_one({"arquivo.hash_sha256": hash_sha256})
        except Exception as e:
            logger.error(f"Erro ao buscar holerite por hash: {e}")
            return None
    
    def buscar_por_funcionario(
        self, 
        funcionario_id: str,
        competencia: str = None,
        limite: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Busca holerites de um funcionário.
        
        Args:
            funcionario_id: ObjectId do funcionário
            competencia: Competência específica (ex: "12/2024") - opcional
            limite: Limite de resultados (default: últimos 12 meses)
        
        Returns:
            Lista de holerites ordenados por competência (mais recente primeiro)
        """
        if not self.disponivel:
            return []
        
        try:
            filtro = {"funcionario_id": ObjectId(funcionario_id)}
            
            if competencia:
                filtro["competencia"] = competencia
            
            cursor = self.colecao.find(filtro).sort(
                "competencia", DESCENDING
            ).limit(limite)
            
            return list(cursor)
        except Exception as e:
            logger.error(f"Erro ao buscar holerites por funcionário: {e}")
            return []
    
    def buscar_por_documento(
        self, 
        documento: str,
        competencia: str = None,
        limite: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Busca holerites por documento (CPF) do funcionário.
        
        Args:
            documento: CPF do funcionário (com ou sem formatação)
            competencia: Competência específica - opcional
            limite: Limite de resultados
        
        Returns:
            Lista de holerites
        """
        if not self.disponivel:
            return []
        
        try:
            # Normalizar documento
            doc_normalizado = documento.replace(".", "").replace("-", "").strip()
            
            filtro = {"funcionario_documento": doc_normalizado}
            
            if competencia:
                filtro["competencia"] = competencia
            
            cursor = self.colecao.find(filtro).sort(
                "competencia", DESCENDING
            ).limit(limite)
            
            return list(cursor)
        except Exception as e:
            logger.error(f"Erro ao buscar holerites por documento: {e}")
            return []
    
    def listar_todos(
        self, 
        limite: int = 100,
        skip: int = 0,
        **filtros
    ) -> List[Dict[str, Any]]:
        """
        Lista holerites com filtros opcionais.
        
        Args:
            limite: Número máximo de resultados
            skip: Pular N primeiros resultados
            **filtros: Filtros opcionais (competencia, funcionario_nome, status, etc.)
        
        Returns:
            Lista de holerites
        """
        if not self.disponivel:
            return []
        
        try:
            filtro = {}
            
            # Aplicar filtros dinâmicos
            if "competencia" in filtros and filtros["competencia"]:
                filtro["competencia"] = filtros["competencia"]
            
            if "funcionario_nome" in filtros and filtros["funcionario_nome"]:
                # Busca case-insensitive
                filtro["funcionario_nome"] = {"$regex": filtros["funcionario_nome"], "$options": "i"}
            
            if "status" in filtros and filtros["status"]:
                filtro["status"] = filtros["status"]
            
            if "empresa_id" in filtros and filtros["empresa_id"]:
                filtro["empresa_id"] = ObjectId(filtros["empresa_id"])
            
            cursor = self.colecao.find(filtro) \
                .sort("criado_em", DESCENDING) \
                .skip(skip) \
                .limit(limite)
            
            return list(cursor)
        except Exception as e:
            logger.error(f"Erro ao listar holerites: {e}")
            return []
    
    def contar_total(self, **filtros) -> int:
        """
        Conta total de holerites com filtros opcionais.
        
        Args:
            **filtros: Filtros opcionais (competencia, status, etc.)
        
        Returns:
            Número total de holerites
        """
        if not self.disponivel:
            return 0
        
        try:
            filtro = {}
            
            if "competencia" in filtros and filtros["competencia"]:
                filtro["competencia"] = filtros["competencia"]
            
            if "status" in filtros and filtros["status"]:
                filtro["status"] = filtros["status"]
            
            return self.colecao.count_documents(filtro)
        except Exception as e:
            logger.error(f"Erro ao contar holerites: {e}")
            return 0
    
    def buscar_por_competencia(
        self, 
        competencia: str,
        empresa_id: str = None,
        status: str = None
    ) -> List[Dict[str, Any]]:
        """
        Busca holerites por competência (mês/ano).
        
        Args:
            competencia: Competência no formato "MM/AAAA"
            empresa_id: Filtrar por empresa (opcional)
            status: Filtrar por status (opcional)
        
        Returns:
            Lista de holerites
        """
        if not self.disponivel:
            return []
        
        try:
            filtro = {"competencia": competencia}
            
            if empresa_id:
                filtro["empresa_id"] = ObjectId(empresa_id)
            
            if status:
                filtro["status"] = status
            
            cursor = self.colecao.find(filtro).sort("funcionario_nome", ASCENDING)
            
            return list(cursor)
        except Exception as e:
            logger.error(f"Erro ao buscar holerites por competência: {e}")
            return []
    
    def atualizar_status(
        self, 
        holerite_id: str, 
        novo_status: StatusHoleriteEnum
    ) -> bool:
        """
        Atualiza o status de um holerite.
        
        Args:
            holerite_id: ObjectId do holerite
            novo_status: Novo status
        
        Returns:
            True se atualizou com sucesso
        """
        if not self.disponivel:
            return False
        
        try:
            resultado = self.colecao.update_one(
                {"_id": ObjectId(holerite_id)},
                {"$set": {
                    "status": novo_status.value,
                    "atualizado_em": datetime.now(timezone.utc)
                }}
            )
            
            if resultado and resultado.modified_count > 0:
                self.logger.audit(
                    action="REGISTRO_ATUALIZADO",
                    target=f"{self.collection_name}",
                    changes={'operacao': 'update'}
                )
            return resultado.modified_count > 0
        except Exception as e:
            logger.error(f"Erro ao atualizar status do holerite: {e}")
            return False
    
    def registrar_envio(
        self, 
        holerite_id: str,
        funcionario_id: str,
        canal: str,
        destino: str,
        sucesso: bool,
        mensagem_erro: str = None
    ) -> Optional[ObjectId]:
        """
        Registra uma tentativa de envio de holerite.
        
        Args:
            holerite_id: ObjectId do holerite
            funcionario_id: ObjectId do funcionário
            canal: Canal de envio ("email", "whatsapp", "whatsapp_grupo")
            destino: Destinatário (email, telefone, nome do grupo)
            sucesso: Se o envio foi bem-sucedido
            mensagem_erro: Mensagem de erro (se falhou)
        
        Returns:
            ObjectId do registro de envio ou None
        """
        if not self.disponivel:
            return None
        
        try:
            envio = {
                "holerite_id": ObjectId(holerite_id),
                "funcionario_id": ObjectId(funcionario_id),
                "canal": canal,
                "destino": destino,
                "sucesso": sucesso,
                "mensagem_erro": mensagem_erro,
                "enviado_em": datetime.now(timezone.utc)
            }
            
            resultado = self.colecao_envios.insert_one(envio)
            
            # Atualizar status do holerite se enviado com sucesso
            if sucesso:
                self.atualizar_status(holerite_id, StatusHoleriteEnum.ENVIADO)
            
            return resultado.inserted_id
        except Exception as e:
            logger.error(f"Erro ao registrar envio: {e}")
            return None
    
    def listar_envios_holerite(self, holerite_id: str) -> List[Dict[str, Any]]:
        """
        Lista todos os envios de um holerite.
        
        Args:
            holerite_id: ObjectId do holerite
        
        Returns:
            Lista de registros de envio
        """
        if not self.disponivel:
            return []
        
        try:
            cursor = self.colecao_envios.find({
                "holerite_id": ObjectId(holerite_id)
            }).sort("enviado_em", DESCENDING)
            
            return list(cursor)
        except Exception as e:
            logger.error(f"Erro ao listar envios: {e}")
            return []
    
    def listar_pendentes_envio(
        self, 
        empresa_id: str | None = None,
        competencia: str | None = None,
        limite: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Lista holerites pendentes de envio.
        
        Args:
            empresa_id: Filtrar por empresa (opcional)
            competencia: Filtrar por competência (opcional)
            limite: Limite de resultados
        
        Returns:
            Lista de holerites pendentes
        """
        if not self.disponivel:
            return []
        
        try:
            filtro = {
                "status": {"$in": [
                    StatusHoleriteEnum.PENDENTE.value,
                    StatusHoleriteEnum.PROCESSADO.value
                ]}
            }
            
            if empresa_id:
                filtro["empresa_id"] = ObjectId(empresa_id)
            
            if competencia:
                filtro["competencia"] = competencia
            
            cursor = self.colecao.find(filtro).sort(
                [("competencia", DESCENDING), ("funcionario_nome", ASCENDING)]
            ).limit(limite)
            
            return list(cursor)
        except Exception as e:
            logger.error(f"Erro ao listar pendentes: {e}")
            return []
    
    def contar_por_status(self, competencia: str = None) -> Dict[str, int]:
        """
        Conta holerites por status.
        
        Args:
            competencia: Filtrar por competência (opcional)
        
        Returns:
            Dicionário com contagem por status
        """
        if not self.disponivel:
            return {}
        
        try:
            match = {}
            if competencia:
                match["competencia"] = competencia
            
            pipeline = [
                {"$match": match} if match else {"$match": {}},
                {"$group": {"_id": "$status", "count": {"$sum": 1}}}
            ]
            
            resultado = self.colecao.aggregate(pipeline)
            
            return {doc["_id"]: doc["count"] for doc in resultado}
        except Exception as e:
            logger.error(f"Erro ao contar por status: {e}")
            return {}
    
    def existe_holerite(
        self, 
        funcionario_id: str, 
        competencia: str,
        tipo_folha: str | None = None
    ) -> bool:
        """
        Verifica se já existe holerite para funcionário/competência.
        
        Args:
            funcionario_id: ObjectId do funcionário
            competencia: Competência (MM/AAAA)
            tipo_folha: Tipo de folha (opcional)
        
        Returns:
            True se existe
        """
        if not self.disponivel:
            return False
        
        try:
            filtro = {
                "funcionario_id": ObjectId(funcionario_id),
                "competencia": competencia
            }
            
            if tipo_folha:
                filtro["tipo_folha"] = tipo_folha
            
            return self.colecao.count_documents(filtro) > 0
        except Exception as e:
            logger.error(f"Erro ao verificar existência: {e}")
            return False


# Instância singleton
holerite_service = HoleriteService()
