"""
Serviço de Folha de Ponto em MongoDB
Gerencia armazenamento, busca e atualização de folhas de ponto
"""

from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from enum import Enum
import dotenv

from src.utils.dotenv_path import caminho_dotenv
from src.services.mongodb_connection import MongoDBConnectionPool
from src.utils.logger_config_v2 import get_logger

logger = get_logger("folha_ponto")


try:
    from pymongo import ASCENDING
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, DuplicateKeyError
    MONGODB_DISPONIVEL = True
except ImportError:
    MONGODB_DISPONIVEL = False
    logger.warning("PyMongo não instalado. Instale com: pip install pymongo")


class ResultadoSalvamento(Enum):
    """Enum para resultados de salvamento de folha de ponto"""
    SUCESSO_INSERIDO = "inserido"        # Nova folha inserida
    SUCESSO_ATUALIZADO = "atualizado"    # Folha existente atualizada
    SUCESSO_INALTERADO = "inalterado"    # Folha já existia com mesmos dados
    DUPLICIDADE = "duplicidade"          # Já existe folha com mesma chave (funcionário/empresa/mês)
    ERRO = "erro"                        # Erro genérico
    INDISPONIVEL = "indisponivel"        # MongoDB não disponível


class FolhaDePontoService:
    """
    Gerencia armazenamento de Folha de Ponto em MongoDB.
    
    Responsabilidades:
    - Salvar/atualizar folhas de ponto (upsert) via pool centralizado.
    - Buscar folhas existentes por critérios.
    - Validar unicidade (funcionário, período, lotação, função).
    - Gerenciar índices para performance.
    
    """

    def __init__(self, collection_name: str = "folha_de_ponto"):

        self.logger = get_logger("folha_ponto")
        """
        Inicializa serviço de folha de ponto usando pool centralizado.

        Args:
            collection_name: Nome da coleção para folha de ponto
        """
        # Carregar configurações do ambiente (padrão FuncionarioService)
        self.mongo_uri = dotenv.get_key(caminho_dotenv(), "MONGO_URI") or "mongodb://localhost:27017"
        self.db_name = dotenv.get_key(caminho_dotenv(), "MONGO_DATABASE_NAME") or "MS_Automatizar"
        self.collection_name = collection_name

        if not MONGODB_DISPONIVEL:
            logger.error("MongoDB não disponível para FolhaDePonto")
            self.pool = None
            self.db = None
            self.colecao = None
            self._disponivel = False
            return

        try:
            # Usar pool centralizado em vez de criar novo MongoClient
            self.pool = MongoDBConnectionPool()
            self.db = self.pool.get_database()

            if self.db is None:
                logger.error("Banco de dados não disponível no pool MongoDB")
                self._disponivel = False
                return

            self.colecao = self.db[collection_name]

            # Criar índices para performance
            self._criar_indices()

            self._disponivel = True
            logger.debug(f"✓ FolhaDePontoService inicializado (usando pool centralizado)")

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
        - Índice composto (não único) em (funcionario_id, empresa_id, mes_referencia, lotacao, funcao)
        - Índices simples em mes_referencia, funcionario_id, empresa_id
        
        NOTA: A validação de duplicidade é feita via código, não por índice único.
        Isso permite flexibilidade na lógica de negócio (buscar lotação/função do funcionário).
        """
        try:
            # Primeiro, tentar dropar índices únicos antigos se existirem (migração)
            for idx_nome in ["idx_folha_unica", "idx_folha_unica_v2", "idx_folha_unica_v3", "idx_folha_unica_v4"]:
                try:
                    self.colecao.drop_index(idx_nome)
                    logger.debug(f"Índice antigo '{idx_nome}' removido para atualização")
                except Exception:
                    pass  # Índice não existe ou já foi removido
            
            # Índice composto para buscas rápidas (NÃO ÚNICO)
            # A validação de duplicidade é feita via código buscando lotação/função do funcionário
            self.colecao.create_index(
                [
                    ("funcionario_id", ASCENDING),
                    ("empresa_id", ASCENDING),
                    ("mes_referencia", ASCENDING),
                    ("lotacao", ASCENDING),
                    ("funcao", ASCENDING)
                ],
                unique=False,  # NÃO único - validação via código
                name="idx_folha_composto"
            )
            
            # Índices simples para buscas frequentes
            self.colecao.create_index([("mes_referencia", ASCENDING)], name="idx_mes_referencia")
            self.colecao.create_index([("funcionario_id", ASCENDING)], name="idx_funcionario_id")
            self.colecao.create_index([("empresa_id", ASCENDING)], name="idx_empresa_id")
            self.colecao.create_index([("data_criacao", ASCENDING)], name="idx_data_criacao")
            self.colecao.create_index([("status", ASCENDING)], name="idx_status")
            
            logger.debug("✓ Índices criados para Folha de Ponto em MongoDB")
        except Exception as e:
            logger.warning(f"Erro ao criar índices: {e}")
    
    def buscar_folha_existente(
        self,
        funcionario_id: str,
        empresa_id: str,
        mes_referencia: str
    ) -> Optional[Dict[str, Any]]:
        """
        Busca uma folha de ponto existente pela chave composta
        
        Args:
            funcionario_id: ID do funcionário (ObjectId string)
            empresa_id: ID da empresa (ObjectId string)
            mes_referencia: Mês em formato YYYY-MM
        
        Returns:
            Dicionário com os dados da folha ou None se não encontrada
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para busca")
            return None
        
        try:
            filtro = {
                "funcionario_id": funcionario_id,
                "empresa_id": empresa_id,
                "mes_referencia": mes_referencia
            }
            
            with self.logger.performance("buscar_folha_existente"):
                documento = self.colecao.find_one(filtro)
            
            if documento:
                logger.debug(
                    f"✓ Folha encontrada: "
                    f"funcionário_id={funcionario_id}, empresa_id={empresa_id}, mes={mes_referencia}"
                )
                # Remover ObjectId se necessário (para serialização)
                documento.pop('_id', None)
                return documento
            else:
                logger.debug(
                    f"✗ Folha não encontrada: "
                    f"funcionário_id={funcionario_id}, empresa_id={empresa_id}, mes={mes_referencia}"
                )
                return None
        
        except Exception as e:
            logger.error(f"Erro ao buscar folha: {e}")
            return None
    
    def salvar_ou_atualizar(
        self, 
        folha_mongodb: Dict[str, Any],
        forcar_sobrescrita: bool = False
    ) -> Tuple[ResultadoSalvamento, Optional[Dict[str, Any]], Optional[Any]]:
        """
        Salva ou atualiza uma folha de ponto (UPSERT)
        Se já existir com a chave composta, pode retornar duplicidade ou sobrescrever.
        
        Args:
            folha_mongodb: Dicionário com dados da FolhaDePontoMongoDB ou instância convertida
            forcar_sobrescrita: Se True, sobrescreve folha existente mesmo com duplicidade
        
        Returns:
            Tupla (ResultadoSalvamento, folha_existente ou None)
            - ResultadoSalvamento.SUCESSO_INSERIDO: Nova folha inserida
            - ResultadoSalvamento.SUCESSO_ATUALIZADO: Folha atualizada
            - ResultadoSalvamento.DUPLICIDADE: Já existe folha (retorna a existente no segundo elemento)
            - ResultadoSalvamento.ERRO: Erro genérico
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para salvar")
            return (ResultadoSalvamento.INDISPONIVEL, None, None)
        
        try:
            from datetime import date, datetime
            import json
            
            # Se receber uma instância Pydantic, converter para dict
            if hasattr(folha_mongodb, 'dict'):
                documento = folha_mongodb.dict()
            else:
                documento = folha_mongodb
            
            # Converter dates para datetime para compatibilidade com MongoDB
            def converter_dates(obj):
                """Recursivamente converte datetime.date para datetime"""
                if isinstance(obj, date) and not isinstance(obj, datetime):
                    return datetime.combine(obj, datetime.min.time())
                elif isinstance(obj, dict):
                    return {k: converter_dates(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [converter_dates(item) for item in obj]
                return obj
            
            documento = converter_dates(documento)
            
            # Extrair dados para filtros
            funcionario_id = documento['funcionario_id']
            empresa_id = documento.get('empresa_id')
            mes_referencia = documento['mes_referencia']
            
            # Buscar lotação e função do funcionário na coleção 'funcionarios'
            # para usar como critério de duplicidade
            lotacao_funcionario = ""
            funcao_funcionario = ""
            
            try:
                from bson import ObjectId
                # Acessar a coleção de funcionários diretamente
                db = self.colecao.database
                col_funcionarios = db['funcionarios']
                col_funcoes = db['funcoes']
                
                # Converter funcionario_id para ObjectId se necessário
                if isinstance(funcionario_id, str):
                    func_obj_id = ObjectId(funcionario_id)
                else:
                    func_obj_id = funcionario_id
                
                func_doc = col_funcionarios.find_one({"_id": func_obj_id})
                if func_doc:
                    lotacao_funcionario = func_doc.get('lotacao', '')
                    
                    # Buscar nome da função na coleção 'funcoes' usando funcao_id
                    funcao_id = func_doc.get('funcao_id')
                    if funcao_id:
                        if isinstance(funcao_id, str):
                            funcao_id = ObjectId(funcao_id)
                        funcao_doc = col_funcoes.find_one({"_id": funcao_id})
                        if funcao_doc:
                            funcao_funcionario = funcao_doc.get('nome', '')
                    
                    logger.debug(
                        f"Funcionário encontrado: lotação={lotacao_funcionario}, função={funcao_funcionario}"
                    )
            except Exception as e:
                logger.warning(f"Não foi possível buscar dados do funcionário: {e}")
            
            # Verificar se já existe uma folha com a mesma combinação:
            # funcionário + empresa + mês + lotação + função
            filtro_unico = {
                "funcionario_id": funcionario_id,
                "empresa_id": empresa_id,
                "mes_referencia": mes_referencia,
                "lotacao": lotacao_funcionario,
                "funcao": funcao_funcionario
            }
            
            with self.logger.performance("salvar_ou_atualizar_buscar"):
                folha_existente = self.colecao.find_one(filtro_unico)
            
            if folha_existente and not forcar_sobrescrita:
                # Há uma folha existente com mesma lotação/função
                logger.warning(
                    f"⚠ Folha duplicada detectada: funcionário={funcionario_id} ({mes_referencia}), "
                    f"lotação={lotacao_funcionario}, função={funcao_funcionario}. "
                    f"Use 'forcar_sobrescrita=True' para substituir."
                )
                # Retorna a folha existente para que o chamador possa decidir
                return (ResultadoSalvamento.DUPLICIDADE, folha_existente, folha_existente.get('_id'))
            
            # Adicionar lotação e função ao documento para referência futura
            documento['lotacao'] = lotacao_funcionario
            documento['funcao'] = funcao_funcionario
            
            # Remover _id se existir no documento novo
            documento.pop('_id', None)
            
            if folha_existente and forcar_sobrescrita:
                # Sobrescrever a folha existente
                resultado = self.colecao.replace_one(
                    {"_id": folha_existente["_id"]},
                    documento
                )
                
                if resultado.modified_count > 0:
                    funcionario_nome = documento.get('folha_data', {}).get('funcionario', {}).get('nome', '')
                    logger.info(
                        f"✓ Folha sobrescrita: {funcionario_nome} ({mes_referencia})"
                    )
                    return (ResultadoSalvamento.SUCESSO_ATUALIZADO, None, folha_existente.get('_id'))
                else:
                    return (ResultadoSalvamento.SUCESSO_INALTERADO, None, folha_existente.get('_id'))
            
            # Inserir nova folha
            resultado = self.colecao.insert_one(documento)

            if resultado and resultado.inserted_id:

                self.logger.audit(

                    action="REGISTRO_CRIADO",

                    target=f"{self.collection_name}:{resultado.inserted_id}",

                    changes={'dados': str(documento)[:200]}

                )
            
            if resultado.inserted_id:
                funcionario_nome = documento.get('folha_data', {}).get('funcionario', {}).get('nome', '')
                logger.info(
                    f"✓ Nova folha inserida: {funcionario_nome} ({mes_referencia}), ID: {resultado.inserted_id}"
                )
                return (ResultadoSalvamento.SUCESSO_INSERIDO, None, resultado.inserted_id)
            
            return (ResultadoSalvamento.ERRO, None, None)
        
        except DuplicateKeyError as e:
            # Captura erro de duplicidade do MongoDB (caso de race condition)
            # Como o índice não é mais único, isso não deveria acontecer
            mes = documento.get('mes_referencia', '')
            lotacao = documento.get('lotacao', '')
            funcao = documento.get('funcao', '')
            
            logger.warning(
                f"⚠ Folha duplicada (race condition): funcionario_id={documento.get('funcionario_id')} ({mes}), "
                f"lotação={lotacao}, função={funcao}"
            )
            
            # Buscar a folha existente para retornar
            try:
                folha_existente = self.colecao.find_one({
                    "funcionario_id": documento.get('funcionario_id'),
                    "empresa_id": documento.get('empresa_id'),
                    "mes_referencia": mes,
                    "lotacao": lotacao,
                    "funcao": funcao
                })
                return (ResultadoSalvamento.DUPLICIDADE, folha_existente, folha_existente.get('_id') if folha_existente else None)
            except Exception as busca_err:
                logger.error(f"Erro ao buscar folha existente: {busca_err}")
                return (ResultadoSalvamento.DUPLICIDADE, None, None)
        
        except Exception as e:
            logger.error(f"Erro ao salvar/atualizar folha: {e}")
            return (ResultadoSalvamento.ERRO, None, None)
    
    def listar_por_funcionario(self, funcionario_id: int) -> list:
        """
        Lista todas as folhas de ponto de um funcionário
        
        Args:
            funcionario_id: ID do funcionário (ObjectId string ou ObjectId)
        
        Returns:
            Lista de dicionários com as folhas
        """
        if not self.disponivel:
            return []
        
        try:
            # O documento grava funcionario_id como ObjectId. Aceita string ou
            # ObjectId na chamada e converte para ObjectId antes da query.
            from bson import ObjectId
            filtro = {"funcionario_id": funcionario_id}
            if isinstance(funcionario_id, str):
                try:
                    filtro["funcionario_id"] = ObjectId(funcionario_id)
                except Exception:
                    # Se não for um ObjectId válido, mantém como está
                    # (sem conversão, a query simplesmente não retorna nada)
                    filtro["funcionario_id"] = funcionario_id
            elif isinstance(funcionario_id, ObjectId):
                filtro["funcionario_id"] = funcionario_id
            else:
                # ID numérico legado: converte para string e tenta ObjectId
                try:
                    filtro["funcionario_id"] = ObjectId(str(funcionario_id))
                except Exception:
                    filtro["funcionario_id"] = funcionario_id

            with self.logger.performance("listar_por_funcionario"):
                documentos = list(
                    self.colecao.find(
                        filtro,
                        {"_id": 0}
                    ).sort("mes_referencia", -1)
                )
            
            logger.debug(f"✓ {len(documentos)} folhas encontradas para funcionário_id={funcionario_id}")
            return documentos
        
        except Exception as e:
            logger.error(f"Erro ao listar folhas por funcionário: {e}")
            return []
    
    def buscar_por_periodo(self, data_inicio: str, data_fim: str) -> list:
        """
        Lista folhas de ponto dentro de um período
        
        Args:
            data_inicio: Data no formato YYYY-MM
            data_fim: Data no formato YYYY-MM
        
        Returns:
            Lista de dicionários com as folhas
        """
        if not self.disponivel:
            return []
        
        try:
            filtro = {
                "mes_referencia": {
                    "$gte": data_inicio,
                    "$lte": data_fim
                }
            }
            
            with self.logger.performance("buscar_por_periodo"):
                documentos = list(
                    self.colecao.find(
                        filtro,
                        {"_id": 0}
                    ).sort("mes_referencia", 1).sort("funcionario_id", 1)
                )
            
            logger.debug(
                f"✓ {len(documentos)} folhas encontradas entre {data_inicio} e {data_fim}"
            )
            return documentos
        
        except Exception as e:
            logger.error(f"Erro ao buscar folhas por período: {e}")
            return []
    
    def buscar_por_empresa(self, empresa: str) -> list:
        """
        Lista todas as folhas de uma empresa
        
        Args:
            empresa: ObjectId da empresa (string) ou ObjectId
        
        Note:
            O documento grava o vínculo com a empresa em `empresa_id` como ObjectId.
            Este método aceita tanto a string do ObjectId quanto o próprio ObjectId
            e converte para ObjectId antes da query.
        
        Returns:
            Lista de dicionários com as folhas
        """
        if not self.disponivel:
            return []
        
        try:
            from bson import ObjectId
            filtro = {"empresa_id": empresa}
            if isinstance(empresa, str):
                try:
                    filtro["empresa_id"] = ObjectId(empresa)
                except Exception:
                    filtro["empresa_id"] = empresa
            elif isinstance(empresa, ObjectId):
                filtro["empresa_id"] = empresa

            with self.logger.performance("buscar_por_empresa"):
                documentos = list(
                    self.colecao.find(
                        filtro,
                        {"_id": 0}
                    ).sort("mes_referencia", -1)
                )
            
            logger.debug(f"✓ {len(documentos)} folhas encontradas para empresa={empresa}")
            return documentos
        
        except Exception as e:
            logger.error(f"Erro ao buscar folhas por empresa: {e}")
            return []
    
    def buscar_por_status(self, status: str) -> list:
        """
        Lista folhas com determinado status
        
        Args:
            status: Status da folha (criada, preenchida, analise_concluida, etc)
        
        Returns:
            Lista de dicionários com as folhas
        """
        if not self.disponivel:
            return []
        
        try:
            with self.logger.performance("buscar_por_status"):
                documentos = list(
                    self.colecao.find(
                        {"status": status},
                        {"_id": 0}
                    ).sort("data_atualizacao", -1)
                )
            
            logger.debug(f"✓ {len(documentos)} folhas encontradas com status={status}")
            return documentos
        
        except Exception as e:
            logger.error(f"Erro ao buscar folhas por status: {e}")
            return []
    
    def obter_estatisticas(self) -> Dict[str, Any]:
        """
        Retorna estatísticas sobre as folhas de ponto
        
        Returns:
            Dicionário com estatísticas
        """
        if not self.disponivel:
            return {
                'status': 'MongoDB indisponível',
                'total_folhas': 0
            }
        
        try:
            with self.logger.performance("obter_estatisticas"):
                total_folhas = self.colecao.count_documents({})
            
            # Contar por status
            pipeline_status = [
                {
                    "$group": {
                        "_id": "$status",
                        "count": {"$sum": 1}
                    }
                }
            ]
            
            with self.logger.performance("obter_estatisticas_status"):
                status_count = {
                    doc['_id']: doc['count']
                    for doc in self.colecao.aggregate(pipeline_status)
                }
            
            # Contar por empresa
            pipeline_empresa = [
                {
                    "$group": {
                        "_id": "$empresa",
                        "count": {"$sum": 1}
                    }
                }
            ]
            
            with self.logger.performance("obter_estatisticas_empresa"):
                empresa_count = {
                    doc['_id']: doc['count']
                    for doc in self.colecao.aggregate(pipeline_empresa)
                }
            
            stats = {
                'status': 'OK' if self.disponivel else 'Erro',
                'total_folhas': total_folhas,
                'status_distribuicao': status_count,
                'empresa_distribuicao': empresa_count,
                'banco_dados': self.db_name,
                'colecao': self.collection_name
            }
            
            logger.info(f"Estatísticas de Folha de Ponto: {total_folhas} folhas no banco")
            return stats
        
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {
                'status': 'Erro ao obter estatísticas',
                'erro': str(e)
            }
    
    def deletar_folha(
        self,
        funcionario_id: int,
        mes_referencia: str,
        lotacao: str,
        funcao: str
    ) -> bool:
        """
        Deleta uma folha de ponto específica
        
        Args:
            funcionario_id: ID do funcionário
            mes_referencia: Mês em formato YYYY-MM
            lotacao: Lotação
            funcao: Função
        
        Returns:
            True se sucesso
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para deletar")
            return False
        
        try:
            filtro = {
                "funcionario_id": funcionario_id,
                "mes_referencia": mes_referencia,
                "lotacao": lotacao,
                "funcao": funcao
            }
            
            resultado = self.colecao.delete_one(filtro)
            
            if resultado.deleted_count > 0:
                logger.info(
                    f"✓ Folha deletada: "
                    f"funcionário_id={funcionario_id}, mes={mes_referencia}"
                )
                return True
            else:
                logger.debug("Nenhuma folha encontrada para deletar")
                return False
        
        except Exception as e:
            logger.error(f"Erro ao deletar folha: {e}")
            return False
    
    def listar_todos(self, skip: int = 0, limit: int = 100) -> dict:
        """
        Lista todas as folhas de ponto com paginação
        
        Args:
            skip: Número de documentos a pular (offset)
            limit: Número máximo de documentos a retornar
        
        Returns:
            Dicionário com:
            - dados: Lista de folhas de ponto
            - total: Total de folhas no banco
            - skip: Offset usado
            - limit: Limite usado
            - paginas: Total de páginas
            - pagina_atual: Página atual (1-indexed)
        """
        if not self.disponivel:
            return {"dados": [], "total": 0, "skip": skip, "limit": limit, "paginas": 0, "pagina_atual": 0}
        
        try:
            with self.logger.performance("listar_todos_contar"):
                total = self.colecao.count_documents({})
            
            # Buscar com paginação
            with self.logger.performance("listar_todos_buscar"):
                documentos = list(
                    self.colecao.find({})
                    .sort([("mes_referencia", -1), ("funcionario_id", 1)])
                    .skip(skip)
                    .limit(limit)
                )
            
            # Calcular paginação
            paginas = (total + limit - 1) // limit if limit > 0 else 1
            pagina_atual = (skip // limit) + 1 if limit > 0 else 1
            
            logger.debug(f"✓ {len(documentos)}/{total} folhas listadas (página {pagina_atual}/{paginas})")
            
            return {
                "dados": documentos,
                "total": total,
                "skip": skip,
                "limit": limit,
                "paginas": paginas,
                "pagina_atual": pagina_atual
            }
        
        except Exception as e:
            logger.error(f"Erro ao listar folhas: {e}")
            return {"dados": [], "total": 0, "skip": skip, "limit": limit, "paginas": 0, "pagina_atual": 0, "erro": str(e)}
    


# Instância global do serviço de Folha de Ponto
folha_de_ponto_service = FolhaDePontoService() if MONGODB_DISPONIVEL else None
