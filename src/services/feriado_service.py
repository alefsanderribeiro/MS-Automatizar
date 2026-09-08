"""
Service para gerenciar Feriados em MongoDB
Responsabilidades:
- CRUD completo de feriados
- Busca por data, ano, tipo
- Importação de feriados padrão do Brasil
- Retorno de feriados para um período específico
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, date
import dotenv

from src.utils.dotenv_path import caminho_dotenv
from src.models.feriado_models import (
    FeriadoMongoDB, 
    StatusFeriado, 
    TipoFeriado,
    FERIADOS_NACIONAIS_FIXOS
)
from src.utils.logger_config_v2 import get_logger
from src.services.historico_decorators import registrar_historico, HistoricoMixin
from src.services.mongodb_connection import MongoDBConnectionPool

# Tentativa de importação do MongoDB
try:
    from pymongo import ASCENDING, DESCENDING
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, DuplicateKeyError
    from bson.objectid import ObjectId
    MONGODB_DISPONIVEL = True
except ImportError:
    MONGODB_DISPONIVEL = False

logger = get_logger("feriado")
if not MONGODB_DISPONIVEL:
    logger.warning("PyMongo não instalado - FeriadoService ficará limitado")


class FeriadoService(HistoricoMixin):
    """
    Gerencia armazenamento de Feriados em MongoDB
    
    Responsabilidades:
    - Salvar/atualizar feriados
    - Buscar feriados por data, período, tipo
    - Importar feriados nacionais padrão
    - Gerar DataFrame para uso no processador de folha de ponto
    - Histórico de alterações via HistoricoMixin
    
    Coleção: "feriados"
    """
    
    def __init__(self, mongo_uri: str = None, 
                 db_name: str = None,
                 collection_name: str = "feriados"):
        """
        Inicializa conexão com MongoDB para Feriados
        
        Args:
            mongo_uri: String de conexão MongoDB (usa .env se não fornecido)
            db_name: Nome do banco de dados (usa .env se não fornecido)
            collection_name: Nome da coleção
        """
        # Usar valores do .env se não fornecidos
        mongo_uri = mongo_uri or dotenv.get_key(caminho_dotenv(), "MONGO_URI")
        db_name = db_name or dotenv.get_key(caminho_dotenv(), "MONGO_DATABASE_NAME")
        
        self.logger = get_logger("feriado")
        
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
            
            self._disponivel = True
            logger.debug(f"✓ MongoDB conectado para Feriados (via pool): {db_name}.{collection_name}")
        
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
        """Cria índices na coleção para melhor performance"""
        try:
            # Índice único em data + descricao_normalizada
            self.colecao.create_index(
                [("data", ASCENDING), ("descricao_normalizada", ASCENDING)],
                unique=True,
                name="idx_data_descricao_unico"
            )
            
            # Índices simples para buscas frequentes
            self.colecao.create_index([("data", ASCENDING)], name="idx_data")
            self.colecao.create_index([("status", ASCENDING)], name="idx_status")
            self.colecao.create_index([("tipo", ASCENDING)], name="idx_tipo")
            self.colecao.create_index([("uf", ASCENDING)], name="idx_uf")
            self.colecao.create_index([("recorrente", ASCENDING)], name="idx_recorrente")
            
            logger.debug("✓ Índices criados para Feriados em MongoDB")
        except Exception as e:
            logger.warning(f"Erro ao criar índices: {e}")
    
    # ==================== CRIAÇÃO ====================
    
    def criar(self, feriado: FeriadoMongoDB) -> Optional[str]:
        """
        Cria um novo feriado
        
        Args:
            feriado: Instância de FeriadoMongoDB
        
        Returns:
            ID do feriado criado (string) ou None se erro
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para criar feriado")
            return None
        
        try:
            doc = feriado.to_mongo_insert()
            resultado = self.colecao.insert_one(doc)

            if resultado and resultado.inserted_id:

                self.logger.audit(

                    action="REGISTRO_CRIADO",

                    target=f"{self.collection_name}:{resultado.inserted_id}",

                    changes={'dados': str(doc)[:200]}

                )
            feriado_id = str(resultado.inserted_id)
            logger.info(f"✓ Feriado criado: {feriado.descricao} ({feriado.data})")
            return feriado_id
        except DuplicateKeyError:
            logger.warning(f"Feriado já existe: {feriado.descricao} ({feriado.data})")
            return None
        except Exception as e:
            logger.error(f"Erro ao criar feriado: {e}")
            return None
    
    def criar_varios(self, feriados: List[FeriadoMongoDB]) -> Dict[str, Any]:
        """
        Cria múltiplos feriados
        
        Args:
            feriados: Lista de FeriadoMongoDB
        
        Returns:
            Dict com estatísticas da operação
        """
        if not self.disponivel:
            return {"sucesso": 0, "erros": 0, "total": len(feriados)}
        
        sucesso = 0
        erros = 0
        
        for feriado in feriados:
            resultado = self.criar(feriado)
            if resultado:
                sucesso += 1
            else:
                erros += 1
        
        return {"sucesso": sucesso, "erros": erros, "total": len(feriados)}
    
    # ==================== BUSCA ====================
    
    def buscar_por_id(self, feriado_id: str) -> Optional[Dict[str, Any]]:
        """Busca feriado por ID"""
        if not self.disponivel:
            return None
        
        try:
            doc = self.colecao.find_one({"_id": ObjectId(feriado_id)})
            return doc
        except Exception as e:
            logger.error(f"Erro ao buscar feriado por ID: {e}")
            return None
    
    def buscar_por_data(self, data: date) -> Optional[Dict[str, Any]]:
        """Busca feriado por data exata"""
        if not self.disponivel:
            return None
        
        try:
            # Converter date para datetime para MongoDB
            data_dt = datetime.combine(data, datetime.min.time())
            doc = self.colecao.find_one({
                "data": data_dt,
                "status": StatusFeriado.ATIVO.value
            })
            return doc
        except Exception as e:
            logger.error(f"Erro ao buscar feriado por data: {e}")
            return None
    
    def listar_por_periodo(self, data_inicio: date, data_fim: date) -> List[Dict[str, Any]]:
        """
        Lista feriados em um período
        
        Args:
            data_inicio: Data inicial
            data_fim: Data final
        
        Returns:
            Lista de feriados no período
        """
        if not self.disponivel:
            return []
        
        try:
            data_inicio_dt = datetime.combine(data_inicio, datetime.min.time())
            data_fim_dt = datetime.combine(data_fim, datetime.max.time())
            
            feriados = list(self.colecao.find({
                "data": {"$gte": data_inicio_dt, "$lte": data_fim_dt},
                "status": StatusFeriado.ATIVO.value
            }).sort("data", ASCENDING))
            
            return feriados
        except Exception as e:
            logger.error(f"Erro ao listar feriados por período: {e}")
            return []
    
    def listar_por_ano(self, ano: int) -> List[Dict[str, Any]]:
        """Lista todos os feriados de um ano"""
        data_inicio = date(ano, 1, 1)
        data_fim = date(ano, 12, 31)
        return self.listar_por_periodo(data_inicio, data_fim)
    
    def listar_por_mes(self, ano: int, mes: int) -> List[Dict[str, Any]]:
        """Lista feriados de um mês específico"""
        from calendar import monthrange
        ultimo_dia = monthrange(ano, mes)[1]
        data_inicio = date(ano, mes, 1)
        data_fim = date(ano, mes, ultimo_dia)
        return self.listar_por_periodo(data_inicio, data_fim)
    
    def listar_todos(self, skip: int = 0, limit: int = 100, 
                     apenas_ativos: bool = True) -> Dict[str, Any]:
        """
        Lista todos os feriados com paginação
        
        Args:
            skip: Número de documentos a pular
            limit: Número máximo de documentos
            apenas_ativos: Se True, retorna apenas ativos
        
        Returns:
            Dict com dados, total e paginação
        """
        if not self.disponivel:
            return {"dados": [], "total": 0, "skip": skip, "limit": limit}
        
        try:
            filtro = {}
            if apenas_ativos:
                filtro["status"] = StatusFeriado.ATIVO.value
            
            total = self.colecao.count_documents(filtro)
            
            feriados = list(
                self.colecao.find(filtro)
                .sort("data", DESCENDING)
                .skip(skip)
                .limit(limit)
            )
            
            return {
                "dados": feriados,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        except Exception as e:
            logger.error(f"Erro ao listar feriados: {e}")
            return {"dados": [], "total": 0, "skip": skip, "limit": limit}
    
    def listar_por_tipo(self, tipo: TipoFeriado) -> List[Dict[str, Any]]:
        """Lista feriados por tipo"""
        if not self.disponivel:
            return []
        
        try:
            feriados = list(self.colecao.find({
                "tipo": tipo.value,
                "status": StatusFeriado.ATIVO.value
            }).sort("data", ASCENDING))
            return feriados
        except Exception as e:
            logger.error(f"Erro ao listar feriados por tipo: {e}")
            return []
    
    # ==================== ATUALIZAÇÃO ====================
    
    @registrar_historico(campos_rastrear=None, origem_padrao="interface_cli")
    def atualizar(
        self, 
        object_id: str, 
        alteracoes: Dict[str, Any],
        **kwargs
    ) -> bool:
        """
        Atualiza campos de um feriado usando ObjectId.
        
        O histórico é registrado AUTOMATICAMENTE pelo decorador @registrar_historico.
        
        Args:
            object_id: ObjectId do feriado em formato string (alias: feriado_id)
            alteracoes: Dicionário com campos a atualizar (alias: dados)
            **kwargs: 
                - registrar_historico (bool): Se False, não registra histórico
                - origem (str): Origem da alteração
        
        Returns:
            True se atualizou com sucesso
        """
        if not self.disponivel:
            return False
        
        try:
            try:
                obj_id = ObjectId(object_id)
            except Exception as e:
                logger.warning(f"ObjectId inválido: {object_id}. Erro: {e}")
                return False
            
            alteracoes['atualizado_em'] = datetime.now(timezone.utc)
            
            # Converter date para datetime se presente
            if 'data' in alteracoes and isinstance(alteracoes['data'], date):
                alteracoes['data'] = datetime.combine(alteracoes['data'], datetime.min.time())
            
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
                logger.info(f"✓ Feriado atualizado: {object_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao atualizar feriado: {e}")
            return False
    
    # ==================== REMOÇÃO ====================
    
    def inativar(self, feriado_id: str) -> bool:
        """Inativa um feriado (soft delete)"""
        return self.atualizar(feriado_id, {"status": StatusFeriado.INATIVO.value})
    
    def remover(self, feriado_id: str) -> bool:
        """Remove um feriado permanentemente"""
        if not self.disponivel:
            return False
        
        try:
            resultado = self.colecao.delete_one({"_id": ObjectId(feriado_id)})
            if resultado.deleted_count > 0:
                logger.info(f"✓ Feriado removido: {feriado_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao remover feriado: {e}")
            return False
    
    # ==================== IMPORTAÇÃO ====================
    
    def importar_feriados_nacionais(self, ano: int) -> Dict[str, Any]:
        """
        Importa os feriados nacionais fixos para um ano específico
        
        Args:
            ano: Ano para criar os feriados
        
        Returns:
            Dict com estatísticas da importação
        """
        if not self.disponivel:
            return {"sucesso": 0, "erros": 0, "ja_existentes": 0, "total": 0}
        
        feriados = []
        for feriado_info in FERIADOS_NACIONAIS_FIXOS:
            mes, dia = feriado_info["data"]
            feriado = FeriadoMongoDB(
                data=date(ano, mes, dia),
                descricao=feriado_info["descricao"],
                tipo=TipoFeriado.NACIONAL,
                recorrente=feriado_info.get("recorrente", True)
            )
            feriados.append(feriado)
        
        resultado = self.criar_varios(feriados)
        logger.info(f"✓ Feriados nacionais de {ano}: {resultado['sucesso']} criados, {resultado['erros']} já existentes")
        return resultado
    
    def importar_feriados_estaduais_ro(self, ano: int) -> Dict[str, Any]:
        """
        Importa feriados estaduais de Rondônia
        
        Args:
            ano: Ano para criar os feriados
        
        Returns:
            Dict com estatísticas da importação
        """
        feriados_ro = [
            {"data": (1, 4), "descricao": "Criação do Estado de Rondônia"},
            {"data": (6, 18), "descricao": "Dia do Evangélico"},
        ]
        
        feriados = []
        for feriado_info in feriados_ro:
            mes, dia = feriado_info["data"]
            feriado = FeriadoMongoDB(
                data=date(ano, mes, dia),
                descricao=feriado_info["descricao"],
                tipo=TipoFeriado.ESTADUAL,
                uf="RO",
                recorrente=True
            )
            feriados.append(feriado)
        
        return self.criar_varios(feriados)
    
    # ==================== UTILITÁRIOS ====================
    
    def obter_dataframe(self, ano: int = None):
        """
        Retorna DataFrame de feriados para uso no processador de folha de ponto
        
        Args:
            ano: Ano específico (se None, retorna todos)
        
        Returns:
            DataFrame com colunas DATA e DESCRICAO
        """
        import pandas as pd
        
        if ano:
            feriados = self.listar_por_ano(ano)
        else:
            resultado = self.listar_todos(limit=1000)
            feriados = resultado.get("dados", [])
        
        if not feriados:
            return pd.DataFrame(columns=["DATA", "DESCRICAO"])
        
        dados = []
        for f in feriados:
            data = f.get("data")
            if isinstance(data, datetime):
                data = data.date() if hasattr(data, 'date') else data
            dados.append({
                "DATA": pd.Timestamp(data) if data else None,
                "DESCRICAO": f.get("descricao", "")
            })
        
        df = pd.DataFrame(dados)
        return df
    
    def verificar_feriado(self, data: date) -> bool:
        """Verifica se uma data é feriado"""
        return self.buscar_por_data(data) is not None
    
    def contar(self, apenas_ativos: bool = True) -> int:
        """Conta total de feriados"""
        if not self.disponivel:
            return 0
        
        try:
            filtro = {}
            if apenas_ativos:
                filtro["status"] = StatusFeriado.ATIVO.value
            return self.colecao.count_documents(filtro)
        except Exception as e:
            logger.error(f"Erro ao contar feriados: {e}")
            return 0
