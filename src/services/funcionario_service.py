"""
Serviço de Funcionários em MongoDB
Gerencia armazenamento, busca e atualização de funcionários
"""

from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
import dotenv

from src.utils.dotenv_path import caminho_dotenv
from src.services.mongodb_connection import MongoDBConnectionPool
from src.services.historico_decorators import registrar_historico, HistoricoMixin
from src.services.cache_service import cache_service
from src.models.funcionario_models import StatusFuncionario, StatusCadastro
from src.utils.logger_config_v2 import get_logger


try:
    from pymongo import ASCENDING
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, DuplicateKeyError
    from bson import ObjectId
    MONGODB_DISPONIVEL = True
except ImportError:
    MONGODB_DISPONIVEL = False
    logger.warning("PyMongo não instalado. Instale com: pip install pymongo")


class FuncionarioService(HistoricoMixin):
    """
    Gerencia funcionários em MongoDB.
    Permite busca, criação, atualização e lookup para relacionamento com Folha de Ponto.
    Suporta busca fuzzy matching por nome + lotação + contrato.
    Usa MongoDBConnectionPool para evitar múltiplas conexões.
    """

    def __init__(self, collection_name: str = "funcionarios"):

        self.logger = get_logger("funcionario")
        """
        Inicializa serviço de funcionários usando pool centralizado.

        Args:
            collection_name: Nome da coleção para funcionários
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
        Cria índices para melhor performance
        Índices:
        - Composto único: (nome_normalizado, lotacao, contrato) com partialFilter
        - Documento único: CPF (sparse)
        - Simples: empresa, ativo, criado_em
        """
        try:
            # Verificar e limpar índices problemáticos
            indices_existentes = self.colecao.index_information()

            # Dropar índices antigos com nomes incorretos ou problemáticos
            indices_para_dropar = ["idx_documento_unico", "idx_cpf_unico"]

            for nome_indice in indices_para_dropar:
                if nome_indice in indices_existentes:
                    logger.info(f"Dropando índice antigo/problemático: {nome_indice}...")
                    try:
                        self.colecao.drop_index(nome_indice)
                        logger.info(f"✓ Índice {nome_indice} removido com sucesso")
                    except Exception as e:
                        logger.warning(f"Não foi possível dropar {nome_indice}: {e}")

            # Verificar se precisa recriar índice com partialFilterExpression
            # O índice antigo não tinha partialFilterExpression
            if "idx_funcionario_unico" in indices_existentes:
                indice_existente = indices_existentes["idx_funcionario_unico"]
                # Se não tem partialFilterExpression, dropar para recriar
                if "partialFilterExpression" not in indice_existente:
                    logger.info("Dropando índice antigo idx_funcionario_unico para recriar com partialFilter...")
                    self.colecao.drop_index("idx_funcionario_unico")
            
            # Índice composto único para evitar duplicatas
            # Usa partialFilterExpression para aplicar unicidade APENAS
            # quando lotacao e contrato estão preenchidos (cadastros completos)
            self.colecao.create_index(
                [
                    ("nome_normalizado", ASCENDING),
                    ("lotacao", ASCENDING),
                    ("contrato", ASCENDING)
                ],
                unique=True,
                name="idx_funcionario_unico",
                partialFilterExpression={
                    "lotacao": {"$type": "string"},
                    "contrato": {"$type": "string"}
                }
            )
            
            # Índice simples por CPF para busca rápida
            # NÃO é unique pois nem todos os funcionários têm CPF preenchido
            # e pode haver duplicatas durante o processamento de holerites
            self.colecao.create_index(
                [("cpf", ASCENDING)],
                name="idx_cpf"
            )
            
            # Índice para buscar funcionários por status de cadastro
            self.colecao.create_index(
                [("status_cadastro", ASCENDING)],
                name="idx_status_cadastro"
            )
            
            # Índices simples para buscas
            self.colecao.create_index([("nome", ASCENDING)], name="idx_nome")
            self.colecao.create_index([("nome_normalizado", ASCENDING)], name="idx_nome_normalizado")
            self.colecao.create_index([("empresa", ASCENDING)], name="idx_empresa_func")
            self.colecao.create_index([("status", ASCENDING)], name="idx_status_func")
            self.colecao.create_index([("criado_em", ASCENDING)], name="idx_criado_em")
            
            # ==================== ÍNDICES COMPOSTOS OTIMIZADOS ====================
            # Índices para queries de aggregation pipelines e filtros mais frequentes
            
            # 1. Busca por empresa + status (listar_por_empresa_com_contagem, filtros)
            self.colecao.create_index(
                [("id_contrato", ASCENDING), ("status", ASCENDING)],
                name="idx_contrato_status"
            )
            
            # 2. Filtro de aniversariantes (buscar_aniversariantes - suporta $expr)
            self.colecao.create_index(
                [("data_nascimento", ASCENDING)],
                name="idx_data_nascimento"
            )
            
            # 3. Busca por contrato + lotação (relatórios e estatísticas)
            self.colecao.create_index(
                [("id_contrato", ASCENDING), ("lotacao", ASCENDING)],
                name="idx_contrato_lotacao"
            )
            
            # 4. Busca por função + horário (folha de ponto, filtros)
            self.colecao.create_index(
                [("funcao_id", ASCENDING), ("horario_id", ASCENDING)],
                name="idx_funcao_horario"
            )
            
            # 5. Busca por diretório + status (geração de folhas, validações)
            self.colecao.create_index(
                [("id_diretorio", ASCENDING), ("status", ASCENDING)],
                name="idx_diretorio_status"
            )
            
            logger.debug("✓ Índices criados para Funcionários em MongoDB")
        except Exception as e:
            logger.warning(f"Erro ao criar índices de funcionários: {e}")
    
    def criar_funcionario(self, funcionario: Dict[str, Any]) -> Optional[int]:
        """
        Cria um novo funcionário ou atualiza se já existe (upsert)
        Em caso de erro de chave única, faz update em vez de falhar
        
        IMPORTANTE: Valida ObjectIds das referências (contrato_empresa_id, horario_id, funcao_id)
        antes de inserir. Se não existirem, retorna None e loga erro.
        
        Auto-criação de diretório:
            - Se diretorio_id não fornecido mas contrato_empresa_id existe,
              cria/busca automaticamente o diretório baseado no contrato
        
        Args:
            funcionario: Dicionário com dados do funcionário (Pydantic dict)
        
        Returns:
            ID do funcionário criado ou atualizado, ou None em caso de erro
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para criar funcionário")
            return None
        
        try:
            # Se for objeto Pydantic, converter
            if hasattr(funcionario, 'model_dump'):
                doc = funcionario.model_dump()
            elif hasattr(funcionario, 'dict'):
                doc = funcionario.dict()
            else:
                doc = funcionario.copy()
            
            # ==================== VALIDAR REFERÊNCIAS ====================
            # Verificar se ObjectIds de referência existem nas coleções
            
            # Validar contrato_empresa_id
            contrato_id = doc.get('contrato_empresa_id')
            if contrato_id:
                if not isinstance(contrato_id, ObjectId):
                    try:
                        contrato_id = ObjectId(contrato_id)
                    except Exception:
                        logger.error(f"contrato_empresa_id inválido: {contrato_id}")
                        return None
                
                if not self.db['contratos'].find_one({"_id": contrato_id}):
                    logger.error(f"Contrato não encontrado: {contrato_id}")
                    return None
            
            # Validar horario_id
            horario_id = doc.get('horario_id')
            if horario_id:
                if not isinstance(horario_id, ObjectId):
                    try:
                        horario_id = ObjectId(horario_id)
                    except Exception:
                        logger.error(f"horario_id inválido: {horario_id}")
                        return None
                
                if not self.db['horarios'].find_one({"_id": horario_id}):
                    logger.error(f"Horário não encontrado: {horario_id}")
                    return None
            
            # Validar funcao_id
            funcao_id = doc.get('funcao_id')
            if funcao_id:
                if not isinstance(funcao_id, ObjectId):
                    try:
                        funcao_id = ObjectId(funcao_id)
                    except Exception:
                        logger.error(f"funcao_id inválido: {funcao_id}")
                        return None
                
                if not self.db['funcoes'].find_one({"_id": funcao_id}):
                    logger.error(f"Função não encontrada: {funcao_id}")
                    return None
            
            # ==================== AUTO-CRIAR DIRETÓRIO ====================
            # Se diretorio_id não fornecido mas contrato_empresa_id existe
            diretorio_id = doc.get('diretorio_id')
            if not diretorio_id and contrato_id:
                diretorio_id = self._obter_ou_criar_diretorio_para_contrato(contrato_id)
                if diretorio_id:
                    doc['diretorio_id'] = diretorio_id
                    logger.debug(f"Diretório auto-associado: {diretorio_id}")
            
            # Validar diretorio_id se fornecido
            if diretorio_id:
                if not isinstance(diretorio_id, ObjectId):
                    try:
                        diretorio_id = ObjectId(diretorio_id)
                        doc['diretorio_id'] = diretorio_id
                    except Exception:
                        logger.warning(f"diretorio_id inválido: {diretorio_id}, ignorando")
                        doc.pop('diretorio_id', None)
                elif not self.db['diretorios'].find_one({"_id": diretorio_id}):
                    logger.warning(f"Diretório não encontrado: {diretorio_id}, ignorando")
                    doc.pop('diretorio_id', None)
            
            # Remover campos que não devem ser inseridos
            doc.pop('_id', None)
            doc.pop('id_funcionario', None)  # Retrocompatibilidade com código legado
            
            # Tentar inserção normal
            try:
                resultado = self.colecao.insert_one(doc)

                if resultado and resultado.inserted_id:

                    self.logger.audit(

                        action="REGISTRO_CRIADO",

                        target=f"{self.collection_name}:{resultado.inserted_id}",

                        changes={'dados': str(doc)[:200]}

                    )
                id_funcionario = str(resultado.inserted_id)
                
                logger.info(f"✓ Funcionário criado: {doc.get('nome')} (ID: {id_funcionario})")
                return id_funcionario
            
            except Exception as insert_error:
                # Se erro de chave duplicada (E11000), fazer upsert
                if "E11000" in str(insert_error) or "duplicate key" in str(insert_error):
                    logger.debug(f"Funcionário já existe, atualizando: {doc.get('nome')}")
                    
                    # Usar nome_normalizado, lotacao e contrato como chave
                    filtro = {
                        "nome_normalizado": doc.get("nome_normalizado"),
                        "lotacao": doc.get("lotacao"),
                        "contrato": doc.get("contrato")
                    }
                    
                    # Remover _id do doc para upsert (não pode modificar _id)
                    doc_update = doc.copy()
                    doc_update.pop('_id', None)
                    
                    # Fazer upsert
                    resultado_upsert = self.colecao.update_one(
                        filtro,
                        {"$set": doc_update},
                        upsert=True
                    )
                    
                    # Buscar o documento (novo ou existente) para pegar o ID
                    with self.logger.performance("criar_ou_buscar_apos_upsert"):
                        doc_encontrado = self.colecao.find_one(filtro)
                    
                    if doc_encontrado:
                        # Retornar o ObjectId em string
                        id_funcionario = str(doc_encontrado.get("_id"))
                        logger.info(f"✓ Funcionário atualizado/criado: {doc.get('nome')} (ID: {id_funcionario})")
                        return id_funcionario
                    else:
                        logger.error(f"Erro ao recuperar funcionário após upsert")
                        return None
                else:
                    # Erro diferente, re-lançar
                    raise insert_error
        
        except Exception as e:
            logger.error(f"Erro ao criar/atualizar funcionário: {e}")
            return None
    
    def _obter_ou_criar_diretorio_para_contrato(self, contrato_id: ObjectId) -> Optional[ObjectId]:
        """
        Obtém ou cria diretório para um contrato.
        Usado internamente para auto-criação de diretório ao criar funcionário.
        
        Args:
            contrato_id: ObjectId do contrato
        
        Returns:
            ObjectId do diretório ou None se erro
        """
        try:
            # Importar DiretorioService aqui para evitar import circular
            from src.services.diretorio_service import DiretorioService
            
            diretorio_service = DiretorioService(
                mongo_uri=self.mongo_uri,
                db_name=self.db_name
            )
            
            return diretorio_service.criar_diretorio_para_contrato(contrato_id)
            
        except Exception as e:
            logger.warning(f"Erro ao obter/criar diretório para contrato {contrato_id}: {e}")
            return None
    
    def buscar_por_id(self, funcionario_id: int) -> Optional[Dict[str, Any]]:
        """
        Busca funcionário por ID
        
        Args:
            funcionario_id: ID do funcionário
        
        Returns:
            Dicionário com dados ou None
        """
        if not self.disponivel:
            return None
        
        try:
            # Tentar converter para ObjectId se for string
            if isinstance(funcionario_id, str):
                try:
                    from bson import ObjectId
                    funcionario_id = ObjectId(funcionario_id)
                except:
                    # Se falhar, manter como string para retrocompatibilidade
                    pass
            
            with self.logger.performance("buscar_por_id"):
                doc = self.colecao.find_one({"_id": funcionario_id}, {"_id": 0})
            if doc:
                logger.debug(f"✓ Funcionário encontrado: {doc.get('nome')}")
            return doc
        except Exception as e:
            logger.error(f"Erro ao buscar funcionário por ID: {e}")
            return None
    
    def buscar_por_object_id(self, object_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca funcionário por ObjectId (_id do MongoDB)
        
        Args:
            object_id: ObjectId do funcionário (string ou ObjectId)
        
        Returns:
            Dicionário com dados ou None
        """
        if not self.disponivel:
            return None
        
        try:
            # Converter para ObjectId se for string
            if isinstance(object_id, str):
                obj_id = ObjectId(object_id)
            else:
                obj_id = object_id
            
            with self.logger.performance("buscar_por_objeto_id"):
                doc = self.colecao.find_one({"_id": obj_id})
            if doc:
                logger.debug(f"✓ Funcionário encontrado por ObjectId: {doc.get('nome')}")
            return doc
        except Exception as e:
            logger.error(f"Erro ao buscar funcionário por ObjectId: {e}")
            return None
    
    def buscar_por_nome_lotacao_contrato(
        self,
        nome: str,
        lotacao: str,
        contrato: str
    ) -> Optional[Dict[str, Any]]:
        """
        Busca funcionário pela chave composta exata
        
        Args:
            nome: Nome do funcionário
            lotacao: Lotação
            contrato: Tipo de contrato
        
        Returns:
            Dicionário com dados ou None (inclui _id para referência MongoDB)
        """
        if not self.disponivel:
            return None
        
        try:
            import unicodedata
            # Normalizar nome
            nfkd = unicodedata.normalize('NFKD', nome)
            nome_normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)]).lower()
            
            with self.logger.performance("buscar_por_nome_lotacao_contrato"):
                doc = self.colecao.find_one(
                    {
                        "nome_normalizado": nome_normalizado,
                        "lotacao": lotacao,
                        "contrato": contrato
                    }
                    # Incluir _id por padrão para referência
                )
            
            if doc:
                logger.debug(f"✓ Funcionário encontrado (busca exata): {doc.get('nome')}")
            return doc
        except Exception as e:
            logger.error(f"Erro na busca por nome/lotação/contrato: {e}")
            return None
    
    def buscar_todos_por_nome(
        self,
        nome: str
    ) -> List[Dict[str, Any]]:
        """
        Busca TODOS os funcionários pelo nome (normalizado).
        Retorna lista de todos os funcionários que possuem o mesmo nome normalizado,
        independente de lotação ou contrato.
        
        Args:
            nome: Nome do funcionário
        
        Returns:
            Lista de dicionários com dados dos funcionários encontrados (pode ser vazia)
        """
        if not self.disponivel:
            return []
        
        try:
            import unicodedata
            # Normalizar nome
            nfkd = unicodedata.normalize('NFKD', nome)
            nome_normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)]).lower()
            
            with self.logger.performance("buscar_todos_por_nome"):
                cursor = self.colecao.find({"nome_normalizado": nome_normalizado})
            funcionarios = list(cursor)
            
            if funcionarios:
                logger.debug(f"✓ {len(funcionarios)} funcionário(s) encontrado(s) com nome: {nome}")
            else:
                logger.debug(f"Nenhum funcionário encontrado com nome: {nome}")
            
            return funcionarios
        except Exception as e:
            logger.error(f"Erro na busca por nome: {e}")
            return []
    
    def buscar_por_nome_lotacao(
        self,
        nome: str,
        lotacao: str
    ) -> Optional[Dict[str, Any]]:
        """
        Busca funcionário pelo nome e lotação (sem contrato)
        Busca mais flexível para evitar duplicatas
        
        Args:
            nome: Nome do funcionário
            lotacao: Lotação
        
        Returns:
            Dicionário com dados ou None (inclui _id para referência MongoDB)
        """
        if not self.disponivel:
            return None
        
        try:
            import unicodedata
            # Normalizar nome
            nfkd = unicodedata.normalize('NFKD', nome)
            nome_normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)]).lower()
            
            with self.logger.performance("buscar_por_nome_lotacao"):
                doc = self.colecao.find_one(
                    {
                        "nome_normalizado": nome_normalizado,
                        "lotacao": lotacao
                    }
                )
            
            if doc:
                logger.debug(f"✓ Funcionário encontrado (nome+lotação): {doc.get('nome')}")
            return doc
        except Exception as e:
            logger.error(f"Erro na busca por nome/lotação: {e}")
            return None
    
    def buscar_similar(
        self,
        nome: str,
        lotacao: str,
        contrato: str,
        limiar_similaridade: float = 0.8
    ) -> Optional[Dict[str, Any]]:
        """
        Busca funcionário com fuzzy matching por nome similar
        Útil para encontrar o funcionário correto mesmo com variações no nome
        
        Args:
            nome: Nome a buscar
            lotacao: Lotação
            contrato: Tipo de contrato
            limiar_similaridade: Limiar mínimo (0-1) para considerar similar
        
        Returns:
            Dicionário com dados do funcionário mais similar ou None
        """
        if not self.disponivel:
            return None
        
        try:
            from difflib import SequenceMatcher
            import unicodedata
            
            # Normalizar nome de busca
            nfkd = unicodedata.normalize('NFKD', nome)
            nome_busca = ''.join([c for c in nfkd if not unicodedata.combining(c)]).lower()
            
            # Buscar todos com lotação e contrato
            with self.logger.performance("buscar_similar_listar"):
                funcionarios = list(self.colecao.find(
                    {
                        "lotacao": lotacao,
                        "contrato": contrato,
                        "status": StatusFuncionario.ATIVO.value
                    },
                    {"_id": 0}
                ))
            
            if not funcionarios:
                logger.debug(f"Nenhum funcionário ativo encontrado em {lotacao}/{contrato}")
                return None
            
            # Calcular similaridade
            melhor_match = None
            melhor_score = 0
            
            for func in funcionarios:
                score = SequenceMatcher(None, nome_busca, func.get('nome_normalizado', '')).ratio()
                if score > melhor_score:
                    melhor_score = score
                    melhor_match = func
            
            # Validar limiar
            if melhor_score >= limiar_similaridade:
                logger.info(
                    f"✓ Funcionário similar encontrado: "
                    f"{melhor_match.get('nome')} (score: {melhor_score:.2%})"
                )
                return melhor_match
            else:
                logger.warning(
                    f"✗ Nenhum funcionário similar encontrado "
                    f"para '{nome}' em {lotacao}/{contrato} "
                    f"(melhor score: {melhor_score:.2%})"
                )
                return None
        
        except Exception as e:
            logger.error(f"Erro em busca similar: {e}")
            return None
    
    def listar_por_empresa(self, empresa: str) -> list:
        """
        Lista todos os funcionários de uma empresa
        
        Args:
            empresa: Nome ou CNPJ da empresa
        
        Returns:
            Lista de dicionários com funcionários
        """
        if not self.disponivel:
            return []
        
        try:
            with self.logger.performance("listar_por_empresa"):
                docs = list(self.colecao.find(
                    {"empresa": empresa, "status": StatusFuncionario.ATIVO.value},
                    {"_id": 0}
                ).sort("nome", 1))
            
            logger.debug(f"✓ {len(docs)} funcionários encontrados para empresa: {empresa}")
            return docs
        except Exception as e:
            logger.error(f"Erro ao listar funcionários por empresa: {e}")
            return []
    
    def listar_por_lotacao(self, lotacao: str) -> list:
        """
        Lista todos os funcionários de uma lotação
        
        Args:
            lotacao: Lotação/departamento
        
        Returns:
            Lista de dicionários com funcionários
        """
        if not self.disponivel:
            return []
        
        try:
            with self.logger.performance("listar_por_lotacao"):
                docs = list(self.colecao.find(
                    {"lotacao": lotacao, "status": StatusFuncionario.ATIVO.value},
                    {"_id": 0}
                ).sort("nome", 1))
            
            logger.debug(f"✓ {len(docs)} funcionários encontrados para lotação: {lotacao}")
            return docs
        except Exception as e:
            logger.error(f"Erro ao listar funcionários por lotação: {e}")
            return []
    
    def buscar_por_documento(self, documento: str) -> Optional[Dict[str, Any]]:
        """
        Busca funcionário por documento (CPF).

        Args:
            documento: CPF do funcionário (com ou sem formatação)

        Returns:
            Dicionário com dados do funcionário ou None se não encontrado
        """
        if not self.disponivel:
            logger.warning(f"Serviço não disponível para buscar documento")
            return None

        if not documento or not documento.strip():
            logger.debug(f"Documento vazio/None - retornando None")
            return None

        try:
            # Normalizar documento (remover pontos e traços)
            doc_normalizado = documento.replace(".", "").replace("-", "").strip()
            logger.debug(f"Buscando funcionário por CPF normalizado: {doc_normalizado}")

            with self.logger.performance("buscar_por_documento"):
                funcionario = self.colecao.find_one({"cpf": doc_normalizado})
            if funcionario:
                logger.info(f"✓ Funcionário encontrado por documento: {doc_normalizado} - ID: {funcionario.get('_id')}")
                return funcionario

            logger.debug(f"✗ Nenhum funcionário encontrado para documento: {doc_normalizado}")
            return None
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar funcionário por documento: {e}")
            return None
    
    def listar_incompletos(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Lista funcionários com cadastro incompleto.
        Útil para revisão e completar cadastros pendentes.
        
        Args:
            skip: Quantos registros pular
            limit: Limite de registros
        
        Returns:
            Lista de funcionários com status_cadastro INCOMPLETO ou PENDENTE_REVISAO
        """
        if not self.disponivel:
            return []
        
        try:
            with self.logger.performance("listar_incompletos"):
                docs = list(self.colecao.find(
                    {
                        "status_cadastro": {
                            "$in": [
                                StatusCadastro.INCOMPLETO.value,
                                StatusCadastro.PENDENTE_REVISAO.value
                            ]
                        }
                    }
                ).sort("nome", 1).skip(skip).limit(limit))
            
            logger.debug(f"✓ {len(docs)} funcionários incompletos encontrados")
            return docs
        except Exception as e:
            logger.error(f"Erro ao listar funcionários incompletos: {e}")
            return []
    
    def criar_ou_buscar_por_documento(
        self,
        documento: str,
        nome: str,
        dados_extras: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Busca funcionário por documento (CPF) ou por nome normalizado.
        Se não encontrar, cria um novo com cadastro incompleto.
        Útil para processamento de holerites onde só temos nome e CPF.

        Estratégia de busca:
        1. Tenta buscar por CPF (se disponível)
        2. Se não encontrar, tenta buscar por nome normalizado
        3. Se ainda não encontrar, cria novo funcionário

        Args:
            documento: CPF do funcionário
            nome: Nome do funcionário
            dados_extras: Dados adicionais opcionais (telefone, email, etc.)

        Returns:
            Dicionário com dados do funcionário (existente ou recém-criado)
        """
        logger.info(f"Iniciando criar_ou_buscar_por_documento: nome={nome}, doc={documento[:3]}***")

        if not self.disponivel:
            logger.error("Serviço não disponível para criar/buscar funcionário")
            return None

        # Estratégia 1: Tenta buscar por CPF (se disponível)
        if documento and documento.strip():  # Apenas se documento não está vazio
            logger.debug(f"ETAPA 1: Tentando buscar funcionário existente por CPF: {documento}")
            existente = self.buscar_por_documento(documento)
            if existente:
                logger.info(f"✓ Funcionário ENCONTRADO por CPF: {nome} - ID: {existente.get('_id')}")
                return existente
            logger.info(f"Funcionário não encontrado por CPF. Tentando buscar por nome normalizado...")
        else:
            logger.info(f"CPF não disponível (vazio/None). Tentando buscar por nome normalizado...")

        # Estratégia 2: Tenta buscar por nome normalizado (fuzzy matching)
        logger.debug(f"ETAPA 2: Tentando buscar por nome normalizado...")
        try:
            import unicodedata

            def normalizar_nome(texto: str) -> str:
                """Remove acentos e converte para minúsculas"""
                if not texto:
                    return ""
                nfkd = unicodedata.normalize('NFKD', texto)
                return ''.join([c for c in nfkd if not unicodedata.combining(c)]).lower().strip()

            nome_normalizado = normalizar_nome(nome)
            logger.debug(f"Nome a buscar (normalizado): '{nome}' → '{nome_normalizado}'")

            # Buscar por nome normalizado usando regex case-insensitive
            # Procura por nomes que COMEÇAM com o texto procurado
            filtro = {"nome_normalizado": {"$regex": f"^{nome_normalizado}", "$options": "i"}}
            with self.logger.performance("criar_ou_buscar_por_nome"):
                funcionario_por_nome = self.colecao.find_one(filtro)

            if funcionario_por_nome:
                logger.info(f"✓ Funcionário ENCONTRADO por nome: {funcionario_por_nome.get('nome')} - ID: {funcionario_por_nome.get('_id')}")
                logger.info(f"  → Atualizando CPF do funcionário existente com CPF do holerite...")

                # Atualizar o CPF do funcionário existente
                doc_normalizado = documento.replace(".", "").replace("-", "").strip()
                try:
                    self.colecao.update_one(
                        {"_id": funcionario_por_nome["_id"]},
                        {"$set": {"cpf": doc_normalizado}}
                    )
                    logger.info(f"✓ CPF atualizado para funcionário: {doc_normalizado}")
                except Exception as e:
                    logger.warning(f"Não foi possível atualizar CPF: {e}")

                return funcionario_por_nome

            logger.info(f"Funcionário não encontrado por nome normalizado. Criando novo...")

        except Exception as e:
            logger.warning(f"Erro ao buscar por nome normalizado: {e}")
            logger.info(f"Prosseguindo para criar novo funcionário...")

        # Estratégia 3: Cria novo funcionário com cadastro incompleto
        logger.debug(f"ETAPA 3: Criando novo funcionário com cadastro incompleto...")
        from src.models.funcionario_models import FuncionarioBuilder

        try:
            # Normalizar documento (ou deixar None se vazio)
            doc_normalizado = None
            if documento and documento.strip():
                doc_normalizado = documento.replace(".", "").replace("-", "").strip()
                logger.debug(f"Documento normalizado: {documento} → {doc_normalizado}")
            else:
                logger.debug(f"Documento vazio - criando funcionário SEM CPF")

            builder = FuncionarioBuilder().set_identificacao(
                nome=nome,
                cpf=doc_normalizado
            ).set_status_cadastro(StatusCadastro.INCOMPLETO)

            # Adicionar dados extras se fornecidos
            if dados_extras:
                if dados_extras.get('telefone'):
                    builder.set_contato(telefone=dados_extras['telefone'])
                if dados_extras.get('email'):
                    builder.set_contato(email=dados_extras['email'])

            funcionario = builder.build_incompleto()
            logger.debug(f"FuncionarioBuilder criado com status: {funcionario.get('status_cadastro') if isinstance(funcionario, dict) else 'unknown'}")

            # Inserir no banco
            resultado = self.colecao.insert_one(funcionario.to_mongo_insert())
            if resultado.inserted_id:
                cpf_str = doc_normalizado if doc_normalizado else "SEM CPF"
                logger.info(f"✓ Funcionário incompleto criado e inserido no BD: {nome} ({cpf_str}) - ID: {resultado.inserted_id}")
                novo_funcionario = self.colecao.find_one({"_id": resultado.inserted_id})
                logger.info(f"✓ Funcionário recuperado do BD após inserção: {novo_funcionario.get('_id') if novo_funcionario else 'NÃO ENCONTRADO!'}")
                return novo_funcionario
            else:
                logger.error(f"✗ Falha ao inserir funcionário: insert_one não retornou inserted_id")
                return None
        except Exception as e:
            logger.error(f"✗ Erro ao criar funcionário incompleto: {e}", exc_info=True)
            return None

    @registrar_historico(campos_rastrear=None, origem_padrao="interface_cli")
    def atualizar(
        self, 
        object_id: str, 
        alteracoes: Dict[str, Any],
        **kwargs
    ) -> bool:
        """
        Atualiza dados de um funcionário usando ObjectId.
        
        O histórico é registrado AUTOMATICAMENTE pelo decorador @registrar_historico.
        Não é necessário passar valores_anteriores - o decorador busca automaticamente.
        
        Args:
            object_id: ObjectId do funcionário em formato string
            alteracoes: Dicionário com campos a atualizar (novos valores)
            **kwargs: 
                - registrar_historico (bool): Se False, não registra histórico. Default: True
                - origem (str): Origem da alteração. Default: "interface_cli"
        
        Returns:
            True se sucesso, False caso contrário
        
        Exemplo:
            # Atualização simples - histórico é registrado automaticamente
            servico.atualizar("507f1f77bcf86cd799439011", {"nome": "Novo Nome"})
            
            # Especificar origem
            servico.atualizar("507f1f77bcf86cd799439011", {"status": "inativo"}, origem="api")
            
            # Desabilitar histórico (raro)
            servico.atualizar("507f1f77bcf86cd799439011", {"temp": "x"}, registrar_historico=False)
        """
        # Este método é interceptado pelo decorador @registrar_historico
        # O decorador cuida de: buscar valores anteriores, adicionar timestamp,
        # registrar histórico e incrementar versão
        # 
        # Se o decorador falhar ou registrar_historico=False, este código executa:
        
        if not self.disponivel:
            return False
        
        try:
            try:
                obj_id = ObjectId(object_id)
            except Exception as e:
                logger.warning(f"ObjectId inválido: {object_id}. Erro: {e}")
                return False
            
            alteracoes['atualizado_em'] = datetime.now(timezone.utc)
            
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
                campos = ", ".join([k for k in alteracoes.keys() if k != 'atualizado_em'])
                logger.info(f"✓ Funcionário {object_id} atualizado - campos: {campos}")
                return True
            else:
                logger.debug(f"Funcionário {object_id} sem alterações")
                return False
        except Exception as e:
            logger.error(f"Erro ao atualizar funcionário: {e}")
            return False

    def deletar(self, funcionario_id: int) -> bool:
        """
        Deleta um funcionário (marca como inativo em vez de deletar)
        
        Args:
            funcionario_id: ID do funcionário
        
        Returns:
            True se sucesso
        """
        if not self.disponivel:
            return False
        
        try:
            # Tentar converter para ObjectId se for string
            if isinstance(funcionario_id, str):
                try:
                    from bson import ObjectId
                    funcionario_id = ObjectId(funcionario_id)
                except:
                    pass
            
            resultado = self.colecao.update_one(
                {"_id": funcionario_id},
                {
                    "$set": {
                        "status": StatusFuncionario.INATIVO.value,
                        "atualizado_em": datetime.now(timezone.utc)
                    }
                }
            )
            
            if resultado and resultado.modified_count > 0:
                self.logger.audit(
                    action="REGISTRO_ATUALIZADO",
                    target=f"{self.collection_name}:{funcionario_id}",
                    changes={'status': 'inativo'}
                )
            
            if resultado.modified_count > 0:
                logger.info(f"✓ Funcionário {funcionario_id} marcado como inativo")
                return True
            else:
                logger.debug(f"Funcionário {funcionario_id} não encontrado")
                return False
        except Exception as e:
            logger.error(f"Erro ao deletar funcionário: {e}")
            return False
    
    def buscar_por_filtros(self, filtro: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Lista funcionários conforme filtro MongoDB especificado.

        Mantém paridade com a TUI, que usa
        ``src.services.mongodb_utils.listar_funcionarios_por_filtro``: quando nenhum
        filtro é informado, assume funcionários ativos (status "ativo").

        Args:
            filtro: Dicionário com filtros MongoDB (ex: {"status": "ativo"}).

        Returns:
            Lista de funcionários ordenada por nome.
        """
        if not self.disponivel:
            return []
        try:
            filtro = filtro or {"status": StatusFuncionario.ATIVO.value}
            return list(self.colecao.find(filtro).sort("nome", 1))
        except Exception as e:
            logger.error(f"Erro ao buscar funcionários por filtro: {e}")
            return []

    def adicionar_empresa_funcionario(self, funcionario_id: str, empresa_id: str) -> bool:
        """
        Adiciona uma empresa à lista de empresas_ids do funcionário (relação N:N)
        Evita duplicatas usando $addToSet
        
        Args:
            funcionario_id: ID do funcionário (string do ObjectId)
            empresa_id: ID da empresa (string do ObjectId) a ser adicionada
        
        Returns:
            True se sucesso, False caso contrário
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para adicionar empresa")
            return False
        
        try:
            # Converter strings IDs para ObjectId
            try:
                func_obj_id = ObjectId(funcionario_id)
                emp_obj_id = ObjectId(empresa_id)
            except Exception as e:
                logger.warning(f"IDs inválidos para conversão: func={funcionario_id}, emp={empresa_id}. Erro: {e}")
                return False
            
            # Usar $addToSet para adicionar sem duplicatas
            resultado = self.colecao.update_one(
                {"_id": func_obj_id},
                {"$addToSet": {"empresas_ids": emp_obj_id}}
            )

            if resultado and resultado.modified_count > 0:

                self.logger.audit(

                    action="REGISTRO_ATUALIZADO",

                    target=f"{self.collection_name}",

                    changes={'operacao': 'update'}

                )
            
            if resultado.modified_count > 0:
                logger.info(f"✓ Empresa {empresa_id} adicionada ao funcionário {funcionario_id}")
                return True
            else:
                logger.debug(f"Empresa pode já estar na lista do funcionário: {funcionario_id}")
                return True  # Não é erro se já estava
        
        except Exception as e:
            logger.error(f"Erro ao adicionar empresa ao funcionário: {e}")
            return False
    
    def listar_todos(self, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """
        Lista funcionários com paginação
        
        Args:
            skip: Número de documentos a pular (offset)
            limit: Número máximo de documentos a retornar
        
        Returns:
            Dicionário com:
            - dados: Lista de funcionários
            - total: Total de funcionários no banco
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
                docs = list(
                    self.colecao.find({})
                    .sort("nome", 1)
                    .skip(skip)
                    .limit(limit)
                )
            
            # Calcular paginação
            paginas = (total + limit - 1) // limit if limit > 0 else 1
            pagina_atual = (skip // limit) + 1 if limit > 0 else 1
            
            logger.debug(f"✓ {len(docs)}/{total} funcionários listados (página {pagina_atual}/{paginas})")
            
            return {
                "dados": docs,
                "total": total,
                "skip": skip,
                "limit": limit,
                "paginas": paginas,
                "pagina_atual": pagina_atual
            }
        
        except Exception as e:
            logger.error(f"Erro ao listar funcionários: {e}")
            return {"dados": [], "total": 0, "skip": skip, "limit": limit, "paginas": 0, "pagina_atual": 0, "erro": str(e)}
    
    # ==================== MÉTODOS OTIMIZADOS COM AGGREGATION PIPELINE ====================
    
    def buscar_aniversariantes(self, mes: int) -> List[Dict[str, Any]]:
        """
        Busca funcionários que fazem aniversário em um mês específico.
        
        OTIMIZADO: Usa $expr + $month para filtrar diretamente no MongoDB.
        Substitui: listar_todos(1000) + loop Python filtrando por .month
        
        Args:
            mes: Mês do aniversário (1-12)
        
        Returns:
            Lista de funcionários aniversariantes do mês (ordenados por dia)
        
        Example:
            >>> service = FuncionarioService()
            >>> aniversariantes_janeiro = service.buscar_aniversariantes(1)
            >>> for func in aniversariantes_janeiro:
            >>>     print(f"{func['nome']} - {func['data_nascimento']}")
        
        Performance:
            - ANTES: 1 query (1000 registros) + loop Python filtrando
            - DEPOIS: 1 query agregada retornando apenas aniversariantes
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível")
            return []
        
        try:
            pipeline = [
                # Stage 1: Adicionar campo temporário com mês extraído
                {
                    "$addFields": {
                        "mes_nascimento": {"$month": "$data_nascimento"}
                    }
                },
                # Stage 2: Filtrar por mês
                {
                    "$match": {
                        "mes_nascimento": mes,
                        "data_nascimento": {"$ne": None}
                    }
                },
                # Stage 3: Ordenar por dia do mês
                {
                    "$addFields": {
                        "dia_nascimento": {"$dayOfMonth": "$data_nascimento"}
                    }
                },
                {
                    "$sort": {"dia_nascimento": 1, "nome": 1}
                },
                # Stage 4: Remover campos temporários
                {
                    "$project": {
                        "mes_nascimento": 0,
                        "dia_nascimento": 0
                    }
                }
            ]
            
            with self.logger.performance("buscar_aniversariantes"):
                resultado = list(self.colecao.aggregate(pipeline))
            
            if not resultado:
                logger.debug(f"Nenhum aniversariante encontrado no mês {mes}")
            else:
                logger.info(f"✅ {len(resultado)} aniversariante(s) encontrado(s) no mês {mes}")
            
            return resultado
        
        except Exception as e:
            logger.error(f"Erro ao buscar aniversariantes: {e}")
            return []
    
    def buscar_com_relacionamentos(self, funcionario_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca um funcionário com todos os relacionamentos populados.
        
        OTIMIZADO: Usa $lookup para joins + cache para referências.
        Substitui: 1 buscar_por_id() + 6 queries separadas para relacionamentos
        
        Args:
            funcionario_id: ID do funcionário
        
        Returns:
            Dict com funcionário populado ou None se não encontrado
        
        Example:
            >>> service = FuncionarioService()
            >>> func = service.buscar_com_relacionamentos("507f1f77bcf86cd799439011")
            >>> print(func['contrato_info']['tipo'])  # "CLT"
            >>> print(func['funcao_info']['nome'])    # "Analista"
        
        Performance:
            - ANTES: 7 queries (1 funcionário + 6 relacionamentos)
            - DEPOIS: 1 aggregation + cache hits para referências
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível")
            return None
        
        try:
            from bson import ObjectId
            
            pipeline = [
                # Stage 1: Filtrar por ID
                {
                    "$match": {"_id": ObjectId(funcionario_id)}
                },
                # Stage 2: Lookup para contrato
                {
                    "$lookup": {
                        "from": "contratos",
                        "localField": "id_contrato",
                        "foreignField": "_id",
                        "as": "contrato_info"
                    }
                },
                {
                    "$unwind": {
                        "path": "$contrato_info",
                        "preserveNullAndEmptyArrays": True
                    }
                },
                # Stage 3: Lookup para função
                {
                    "$lookup": {
                        "from": "funcoes",
                        "localField": "funcao_id",
                        "foreignField": "_id",
                        "as": "funcao_info"
                    }
                },
                {
                    "$unwind": {
                        "path": "$funcao_info",
                        "preserveNullAndEmptyArrays": True
                    }
                },
                # Stage 4: Lookup para horário
                {
                    "$lookup": {
                        "from": "horarios",
                        "localField": "horario_id",
                        "foreignField": "_id",
                        "as": "horario_info"
                    }
                },
                {
                    "$unwind": {
                        "path": "$horario_info",
                        "preserveNullAndEmptyArrays": True
                    }
                },
                # Stage 5: Lookup para diretório
                {
                    "$lookup": {
                        "from": "diretorios",
                        "localField": "id_diretorio",
                        "foreignField": "_id",
                        "as": "diretorio_info"
                    }
                },
                {
                    "$unwind": {
                        "path": "$diretorio_info",
                        "preserveNullAndEmptyArrays": True
                    }
                },
                # Stage 6: Lookup para empresa (via contrato)
                {
                    "$lookup": {
                        "from": "empresas",
                        "localField": "contrato_info.id_empresa",
                        "foreignField": "_id",
                        "as": "empresa_info"
                    }
                },
                {
                    "$unwind": {
                        "path": "$empresa_info",
                        "preserveNullAndEmptyArrays": True
                    }
                }
            ]
            
            with self.logger.performance("buscar_com_relacionamentos"):
                resultado = list(self.colecao.aggregate(pipeline))
            
            if not resultado:
                logger.warning(f"Funcionário {funcionario_id} não encontrado")
                return None
            
            funcionario = resultado[0]
            
            # Buscar contatos via batch service (se disponível)
            try:
                from src.services.contato_funcionario_service import contato_funcionario_service
                if contato_funcionario_service:
                    contatos = contato_funcionario_service.obter_contatos_batch([funcionario_id])
                    funcionario["contatos"] = contatos.get(funcionario_id, {})
            except Exception as e:
                logger.warning(f"Erro ao buscar contatos: {e}")
                funcionario["contatos"] = {}
            
            logger.info(f"✅ Funcionário {funcionario_id} carregado com relacionamentos")
            return funcionario
        
        except Exception as e:
            logger.error(f"Erro ao buscar funcionário com relacionamentos: {e}")
            return None
    
    def exportar_com_relacionamentos(
        self,
        filtro: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Exporta funcionários com todos os relacionamentos populados.
        
        OTIMIZADO: Usa $lookup para joins + obter_contatos_batch() para contatos.
        Substitui: listar_todos() + loop com 6 queries por funcionário
        
        Args:
            filtro: Filtro MongoDB opcional (ex: {"status": "ativo"})
            limit: Limite de registros (None = sem limite)
        
        Returns:
            Lista de funcionários com todos os relacionamentos
        
        Example:
            >>> service = FuncionarioService()
            >>> funcionarios = service.exportar_com_relacionamentos(
            >>>     filtro={"status": "ativo"},
            >>>     limit=100
            >>> )
            >>> for func in funcionarios:
            >>>     print(f"{func['nome']} - {func['empresa_info']['razao_social']}")
        
        Performance:
            - ANTES: 1 query (100 registros) + 600 queries (6 por funcionário)
            - DEPOIS: 1 aggregation + 1 batch query para contatos
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível")
            return []
        
        try:
            from bson import ObjectId
            
            # Pipeline de agregação
            pipeline = []
            
            # Stage 1: Filtro opcional
            if filtro:
                pipeline.append({"$match": filtro})
            
            # Stage 2: Ordenação por nome
            pipeline.append({"$sort": {"nome": 1}})
            
            # Stage 3: Limit opcional
            if limit:
                pipeline.append({"$limit": limit})
            
            # Stage 4-9: Lookups para relacionamentos
            lookups = [
                # Contrato
                {
                    "$lookup": {
                        "from": "contratos",
                        "localField": "id_contrato",
                        "foreignField": "_id",
                        "as": "contrato_info"
                    }
                },
                {
                    "$unwind": {
                        "path": "$contrato_info",
                        "preserveNullAndEmptyArrays": True
                    }
                },
                # Função
                {
                    "$lookup": {
                        "from": "funcoes",
                        "localField": "funcao_id",
                        "foreignField": "_id",
                        "as": "funcao_info"
                    }
                },
                {
                    "$unwind": {
                        "path": "$funcao_info",
                        "preserveNullAndEmptyArrays": True
                    }
                },
                # Horário
                {
                    "$lookup": {
                        "from": "horarios",
                        "localField": "horario_id",
                        "foreignField": "_id",
                        "as": "horario_info"
                    }
                },
                {
                    "$unwind": {
                        "path": "$horario_info",
                        "preserveNullAndEmptyArrays": True
                    }
                },
                # Diretório
                {
                    "$lookup": {
                        "from": "diretorios",
                        "localField": "id_diretorio",
                        "foreignField": "_id",
                        "as": "diretorio_info"
                    }
                },
                {
                    "$unwind": {
                        "path": "$diretorio_info",
                        "preserveNullAndEmptyArrays": True
                    }
                },
                # Empresa (via contrato)
                {
                    "$lookup": {
                        "from": "empresas",
                        "localField": "contrato_info.id_empresa",
                        "foreignField": "_id",
                        "as": "empresa_info"
                    }
                },
                {
                    "$unwind": {
                        "path": "$empresa_info",
                        "preserveNullAndEmptyArrays": True
                    }
                }
            ]
            
            pipeline.extend(lookups)
            
            # Executar pipeline
            with self.logger.performance("exportar_com_relacionamentos"):
                funcionarios = list(self.colecao.aggregate(pipeline))
            
            if not funcionarios:
                logger.info("Nenhum funcionário encontrado para exportação")
                return []
            
            # Buscar contatos em batch (1 query para todos)
            try:
                from src.services.contato_funcionario_service import contato_funcionario_service
                
                if contato_funcionario_service:
                    funcionario_ids = [str(f["_id"]) for f in funcionarios]
                    contatos_map = contato_funcionario_service.obter_contatos_batch(funcionario_ids)
                    
                    # Adicionar contatos a cada funcionário
                    for funcionario in funcionarios:
                        func_id = str(funcionario["_id"])
                        funcionario["contatos"] = contatos_map.get(func_id, {})
            except Exception as e:
                logger.warning(f"Erro ao buscar contatos em batch: {e}")
                for funcionario in funcionarios:
                    funcionario["contatos"] = {}
            
            logger.info(f"✅ {len(funcionarios)} funcionário(s) exportado(s) com relacionamentos")
            return funcionarios
        
        except Exception as e:
            logger.error(f"Erro ao exportar funcionários com relacionamentos: {e}")
            return []
    
    def listar_por_empresa_com_contagem(self, empresa_id: str) -> Tuple[List[Dict[str, Any]], int]:
        """
        Lista funcionários de uma empresa específica com contagem.
        
        OTIMIZADO: Usa aggregation com $match + $count paralelo via $facet.
        Substitui: listar_todos(1000) + loop Python filtrando por empresa
        
        Args:
            empresa_id: ID da empresa
        
        Returns:
            Tupla (lista_funcionarios, total)
        
        Performance:
            - ANTES: 1 query (1000 registros) + loop Python
            - DEPOIS: 1 aggregation com $facet (dados + contagem)
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível")
            return [], 0
        
        try:
            from bson import ObjectId
            
            with self.logger.performance("listar_por_empresa_contratos"):
                contratos_ids = list(
                    self.db["contratos"].find(
                        {"id_empresa": ObjectId(empresa_id)},
                        {"_id": 1}
                    )
                )
            
            if not contratos_ids:
                logger.info(f"Nenhum contrato encontrado para empresa {empresa_id}")
                return [], 0
            
            contrato_ids_list = [c["_id"] for c in contratos_ids]
            
            # Pipeline com $facet para dados + contagem
            pipeline = [
                {
                    "$match": {"id_contrato": {"$in": contrato_ids_list}}
                },
                {
                    "$facet": {
                        "dados": [
                            {"$sort": {"nome": 1}},
                            {"$limit": 1000}  # Proteção contra overload
                        ],
                        "total": [
                            {"$count": "count"}
                        ]
                    }
                }
            ]
            
            with self.logger.performance("listar_por_empresa_facet"):
                resultado = list(self.colecao.aggregate(pipeline))
            
            if not resultado:
                return [], 0
            
            dados = resultado[0]["dados"]
            total = resultado[0]["total"][0]["count"] if resultado[0]["total"] else 0
            
            logger.info(f"✅ {total} funcionário(s) encontrado(s) para empresa {empresa_id}")
            return dados, total
        
        except Exception as e:
            logger.error(f"Erro ao listar funcionários por empresa: {e}")
            return [], 0
    
    def obter_estatisticas(self) -> Dict[str, Any]:
        """
        Obtém estatísticas agregadas dos funcionários.
        
        OTIMIZADO: Usa $facet com múltiplos $group para calcular tudo em uma query.
        Substitui: listar_todos(1000) + loops Python para contagens
        
        Returns:
            Dict com estatísticas:
            {
                "por_status": {"ativo": 50, "inativo": 10, ...},
                "por_contrato": {"CLT": 30, "PJ": 20, ...},
                "por_lotacao": [{"lotacao": "TI", "total": 15}, ...] (top 10)
            }
        
        Example:
            >>> service = FuncionarioService()
            >>> stats = service.obter_estatisticas()
            >>> print(f"Ativos: {stats['por_status'].get('ativo', 0)}")
        
        Performance:
            - ANTES: 1 query (1000 registros) + 3 loops Python
            - DEPOIS: 1 aggregation com 3 facets paralelos
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível")
            return {"por_status": {}, "por_contrato": {}, "por_lotacao": []}
        
        try:
            pipeline = [
                {
                    "$facet": {
                        # Facet 1: Contagem por status
                        "por_status": [
                            {
                                "$group": {
                                    "_id": "$status",
                                    "total": {"$sum": 1}
                                }
                            }
                        ],
                        # Facet 2: Contagem por tipo de contrato
                        "por_contrato": [
                            {
                                "$group": {
                                    "_id": "$contrato",
                                    "total": {"$sum": 1}
                                }
                            }
                        ],
                        # Facet 3: Top 10 lotações
                        "por_lotacao": [
                            {
                                "$group": {
                                    "_id": "$lotacao",
                                    "total": {"$sum": 1}
                                }
                            },
                            {"$sort": {"total": -1}},
                            {"$limit": 10},
                            {
                                "$project": {
                                    "_id": 0,
                                    "lotacao": "$_id",
                                    "total": 1
                                }
                            }
                        ]
                    }
                }
            ]
            
            with self.logger.performance("obter_estatisticas"):
                resultado = list(self.colecao.aggregate(pipeline))
            
            if not resultado:
                logger.warning("Pipeline de estatísticas retornou vazio")
                return {"por_status": {}, "por_contrato": {}, "por_lotacao": []}
            
            stats_raw = resultado[0]
            
            # Converter arrays em dicts para facilitar acesso
            stats = {
                "por_status": {
                    item["_id"]: item["total"] 
                    for item in stats_raw.get("por_status", [])
                    if item["_id"]
                },
                "por_contrato": {
                    item["_id"]: item["total"] 
                    for item in stats_raw.get("por_contrato", [])
                    if item["_id"]
                },
                "por_lotacao": stats_raw.get("por_lotacao", [])
            }
            
            logger.info("✅ Estatísticas calculadas via aggregation")
            return stats
        
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {"por_status": {}, "por_contrato": {}, "por_lotacao": []}
    
    def validar_referencias_batch(
        self,
        contratos: List[str] = None,
        horarios: List[str] = None,
        funcoes: List[str] = None,
        diretorios: List[str] = None
    ) -> Dict[str, bool]:
        """
        Valida existência de múltiplas referências em uma única query por tipo.
        
        OTIMIZADO: 4 queries paralelas ao invés de N queries sequenciais.
        Usado em criar_funcionario() e atualizar_funcionario().
        
        Args:
            contratos: Lista de IDs de contratos para validar
            horarios: Lista de IDs de horários para validar
            funcoes: Lista de IDs de funções para validar
            diretorios: Lista de IDs de diretórios para validar
        
        Returns:
            Dict com resultado de validação:
            {
                "contratos_validos": bool,
                "horarios_validos": bool,
                "funcoes_validos": bool,
                "diretorios_validos": bool
            }
        
        Example:
            >>> service = FuncionarioService()
            >>> validas = service.validar_referencias_batch(
            >>>     contratos=["507f1f77bcf86cd799439011"],
            >>>     funcoes=["507f191e810c19729de860ea"]
            >>> )
            >>> if not validas["contratos_validos"]:
            >>>     raise ValueError("Contrato inválido")
        
        Performance:
            - ANTES: 4 queries sequenciais (find_one para cada)
            - DEPOIS: 4 queries paralelas com count_documents + $in
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para validação")
            return {
                "contratos_validos": False,
                "horarios_validos": False,
                "funcoes_validos": False,
                "diretorios_validos": False
            }
        
        resultado = {
            "contratos_validos": True,
            "horarios_validos": True,
            "funcoes_validos": True,
            "diretorios_validos": True
        }
        
        try:
            # Validar contratos
            if contratos:
                contratos_obj = [ObjectId(c) for c in contratos if c]
                if contratos_obj:
                    count = self.db["contratos"].count_documents({"_id": {"$in": contratos_obj}})
                    resultado["contratos_validos"] = (count == len(contratos_obj))
            
            # Validar horários
            if horarios:
                horarios_obj = [ObjectId(h) for h in horarios if h]
                if horarios_obj:
                    count = self.db["horarios"].count_documents({"_id": {"$in": horarios_obj}})
                    resultado["horarios_validos"] = (count == len(horarios_obj))
            
            # Validar funções
            if funcoes:
                funcoes_obj = [ObjectId(f) for f in funcoes if f]
                if funcoes_obj:
                    count = self.db["funcoes"].count_documents({"_id": {"$in": funcoes_obj}})
                    resultado["funcoes_validos"] = (count == len(funcoes_obj))
            
            # Validar diretórios
            if diretorios:
                diretorios_obj = [ObjectId(d) for d in diretorios if d]
                if diretorios_obj:
                    count = self.db["diretorios"].count_documents({"_id": {"$in": diretorios_obj}})
                    resultado["diretorios_validos"] = (count == len(diretorios_obj))
            
            return resultado
        
        except Exception as e:
            logger.error(f"Erro ao validar referências em batch: {e}")
            return {
                "contratos_validos": False,
                "horarios_validos": False,
                "funcoes_validos": False,
                "diretorios_validos": False
            }
    

# Instância global do serviço de Funcionários
funcionario_service = FuncionarioService() if MONGODB_DISPONIVEL else None
