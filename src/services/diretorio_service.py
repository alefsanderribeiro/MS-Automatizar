"""
Service para gerenciar Diretórios em MongoDB
Responsabilidades:
- CRUD completo de diretórios
- Cache em memória permanente (até reiniciar app)
- Soft delete (verificar referências antes de inativar)
- Busca por nome/ID/contrato_id
- Auto-cadastro de diretórios baseado no contrato
- Integração com histórico automático via decorador
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import unicodedata
import dotenv

from src.utils.dotenv_path import caminho_dotenv
from src.services.historico_decorators import registrar_historico, HistoricoMixin
from src.services.cache_service import cache_service
from src.models.diretorio_models import DiretorioMongoDB, DiretorioBuilder, DIRETORIO_PADRAO, StatusDiretorio
from src.services.mongodb_connection import MongoDBConnectionPool
from src.utils.logger_config_v2 import get_logger


# Tentativa de importação do MongoDB
try:
    from pymongo import ASCENDING
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, DuplicateKeyError
    from bson.objectid import ObjectId
    MONGODB_DISPONIVEL = True
except ImportError:
    MONGODB_DISPONIVEL = False

logger = get_logger("diretorio")
if not MONGODB_DISPONIVEL:
    logger.warning("PyMongo não instalado - DiretorioService ficará limitado")


class DiretorioService(HistoricoMixin):
    """
    Gerencia armazenamento de Diretórios em MongoDB
    
    Responsabilidades:
    - Salvar/atualizar diretórios (upsert)
    - Buscar diretórios por nome/ID/contrato_id
    - Auto-cadastro de diretórios baseado em contrato
    - Gerenciar índices para performance
    - Cache em memória para evitar buscas repetidas
    - Soft delete (marcar como inativo se referenciado)
    - Histórico de alterações via HistoricoMixin
    
    Coleção: "diretorios"
    """
    
    def __init__(self, mongo_uri: str = None, 
                 db_name: str = None,
                 collection_name: str = "diretorios"):
        """
        Inicializa conexão com MongoDB para Diretórios
        
        Args:
            mongo_uri: String de conexão MongoDB (usa .env se não fornecido)
            db_name: Nome do banco de dados (usa .env se não fornecido)
            collection_name: Nome da coleção
        """
        # Usar valores do .env se não fornecidos
        mongo_uri = mongo_uri or dotenv.get_key(caminho_dotenv(), "MONGO_URI")
        db_name = db_name or dotenv.get_key(caminho_dotenv(), "MONGO_DATABASE_NAME")
        
        self.logger = get_logger("diretorio")
        
        # Cache em memória para diretórios (chave: ObjectId string, valor: documento)
        self._cache_diretorios: Dict[str, Dict[str, Any]] = {}
        # Cache por contrato_id para busca rápida
        self._cache_por_contrato: Dict[str, Dict[str, Any]] = {}
        
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
                f"✓ MongoDB conectado para Diretórios (via pool): {db_name}.{collection_name}"
            )
        
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"✗ Erro ao conectar MongoDB (Diretórios): {e}")
            self.pool = None
            self.db = None
            self.colecao = None
            self._disponivel = False
        except Exception as e:
            logger.error(f"✗ Erro ao inicializar MongoDB (Diretórios): {e}")
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
        - contrato_id (não único, sparse) para buscar diretórios por contrato
        - ativo para filtrar ativos/inativos
        """
        try:
            # Índice único em nome_normalizado
            self.colecao.create_index(
                [("nome_normalizado", ASCENDING)],
                unique=True,
                name="idx_nome_normalizado_unico"
            )
            
            # Índice em contrato_id (não único - múltiplos diretórios por contrato)
            self.colecao.create_index(
                [("contrato_id", ASCENDING)],
                sparse=True,
                name="idx_contrato_id"
            )
            
            # Índices simples para buscas frequentes
            self.colecao.create_index([("status", ASCENDING)], name="idx_status")
            self.colecao.create_index([("auto_criado", ASCENDING)], name="idx_auto_criado")
            self.colecao.create_index([("criado_em", ASCENDING)], name="idx_criado_em")
            
            logger.debug("✓ Índices criados para Diretórios em MongoDB")
        except Exception as e:
            logger.warning(f"Erro ao criar índices de diretórios: {e}")
    
    def _carregar_cache_completo(self) -> None:
        """
        Pré-carrega TODOS os diretórios em cache (memória + Redis).
        
        Diretórios são uma tabela de referência média (~100-500 registros),
        então é viável carregar tudo para otimizar lookups O(1).
        
        Cache híbrido:
        - Cache local em memória (_cache_diretorios) para acesso ultra-rápido
        - Cache Redis (cache_service) para persistência entre restarts
        - Cache por contrato_id para busca rápida
        """
        try:
            import os
            # Buscar TODOS os diretórios do MongoDB
            todos_diretorios = list(self.colecao.find({}))
            
            if not todos_diretorios:
                logger.warning("⚠️ Nenhum diretório encontrado para carregar cache")
                return
            
            # Poplar cache em memória (dict local)
            cache_data_redis = {}
            for diretorio in todos_diretorios:
                diretorio_id = str(diretorio["_id"])
                # Cache local por ID
                self._cache_diretorios[diretorio_id] = diretorio
                
                # Cache por contrato_id se existir
                contrato_id = diretorio.get("contrato_id")
                if contrato_id:
                    self._cache_por_contrato[str(contrato_id)] = diretorio
                
                # Preparar para cache Redis
                cache_data_redis[f"diretorios:{diretorio_id}"] = diretorio
            
            # Poplar cache Redis em batch (uma operação)
            ttl = int(os.getenv("CACHE_TTL", "300"))  # 5 minutos padrão
            self.cache.set_many(cache_data_redis, ttl=ttl)
            
            logger.info(f"✅ Cache de diretórios carregado: {len(todos_diretorios)} registros (memória + Redis)")
            
        except Exception as e:
            logger.error(f"Erro ao carregar cache de diretórios: {e}")
    
    def _invalidar_cache(self) -> None:
        """
        Invalida TODO o cache de diretórios (memória + Redis).
        
        Deve ser chamado após operações de CREATE, UPDATE ou DELETE
        para garantir que próximas leituras busquem dados atualizados.
        
        Após invalidação, próxima busca recarregará o cache automaticamente.
        """
        try:
            # Limpar caches locais
            self._cache_diretorios.clear()
            self._cache_por_contrato.clear()
            
            # Limpar cache Redis (todas as chaves diretorios:*)
            deleted_count = self.cache.invalidate("diretorios:*")
            
            logger.debug(f"🗑️ Cache de diretórios invalidado: {deleted_count} chaves removidas do Redis")
            
            # Recarregar cache imediatamente para próximas buscas
            self._carregar_cache_completo()
            
        except Exception as e:
            logger.error(f"Erro ao invalidar cache de diretórios: {e}")
    
    def _normalizar_nome(self, nome: str) -> str:
        """
        Normaliza o nome para busca (remove acentos, converte para minúsculas)
        
        Args:
            nome: Nome a normalizar
            
        Returns:
            Nome normalizado
        """
        nfkd = unicodedata.normalize('NFKD', nome)
        return ''.join([c for c in nfkd if not unicodedata.combining(c)]).lower()
    
    # ==================== BUSCA ====================
    
    def buscar_por_nome(self, nome_diretorio: str, exato: bool = True) -> Optional[Dict[str, Any]]:
        """
        Busca um diretório pelo nome
        
        Args:
            nome_diretorio: Nome do diretório
            exato: Se True, busca exata; se False, busca parcial
        
        Returns:
            Dicionário com os dados do diretório ou None
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para busca")
            return None
        
        try:
            nome_normalizado = self._normalizar_nome(nome_diretorio)
            
            if exato:
                filtro = {"nome_normalizado": nome_normalizado}
            else:
                filtro = {"nome_normalizado": {"$regex": nome_normalizado, "$options": "i"}}
            
            documento = self.colecao.find_one(filtro)
            
            if documento:
                # Adicionar ao cache
                diretorio_id = str(documento.get("_id"))
                self._cache_diretorios[diretorio_id] = documento
                logger.debug(f"✓ Diretório encontrado: {documento.get('nome')}")
                return documento
            else:
                logger.debug(f"✗ Diretório não encontrado: {nome_diretorio}")
                return None
        
        except Exception as e:
            logger.error(f"Erro ao buscar diretório por nome: {e}")
            return None
    
    def buscar_por_id(self, diretorio_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca um diretório por ObjectId
        Usa cache em memória
        
        Args:
            diretorio_id: ID do diretório (ObjectId em formato string)
        
        Returns:
            Dicionário com os dados do diretório ou None
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para busca")
            return None
        
        # Verificar cache primeiro
        if diretorio_id in self._cache_diretorios:
            logger.debug(f"✓ Diretório encontrado no cache: {diretorio_id}")
            return self._cache_diretorios[diretorio_id]
        
        try:
            # Converter string para ObjectId
            try:
                obj_id = ObjectId(diretorio_id)
            except Exception:
                logger.warning(f"ID inválido para conversão: {diretorio_id}")
                return None
            
            documento = self.colecao.find_one({"_id": obj_id})
            
            if documento:
                # Adicionar ao cache
                self._cache_diretorios[diretorio_id] = documento
                logger.debug(f"✓ Diretório encontrado por ID: {documento.get('nome')}")
                return documento
            else:
                logger.debug(f"✗ Diretório não encontrado pelo ID: {diretorio_id}")
                return None
        
        except Exception as e:
            logger.error(f"Erro ao buscar diretório por ID: {e}")
            return None
    
    def buscar_por_contrato_id(self, contrato_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca um diretório pelo ObjectId do contrato associado
        Usa cache em memória
        
        Args:
            contrato_id: ID do contrato (ObjectId em formato string)
        
        Returns:
            Dicionário com os dados do diretório ou None
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para busca")
            return None
        
        # Verificar cache primeiro
        if contrato_id in self._cache_por_contrato:
            logger.debug(f"✓ Diretório encontrado no cache por contrato: {contrato_id}")
            return self._cache_por_contrato[contrato_id]
        
        try:
            # Converter string para ObjectId
            try:
                obj_id = ObjectId(contrato_id)
            except Exception:
                logger.warning(f"contrato_id inválido para conversão: {contrato_id}")
                return None
            
            documento = self.colecao.find_one({"contrato_id": obj_id})
            
            if documento:
                # Adicionar aos caches
                diretorio_id = str(documento.get("_id"))
                self._cache_diretorios[diretorio_id] = documento
                self._cache_por_contrato[contrato_id] = documento
                logger.debug(f"✓ Diretório encontrado por contrato_id: {documento.get('nome')}")
                return documento
            else:
                logger.debug(f"✗ Diretório não encontrado para contrato: {contrato_id}")
                return None
        
        except Exception as e:
            logger.error(f"Erro ao buscar diretório por contrato_id: {e}")
            return None
    
    def obter_nome_diretorio(self, diretorio_id: str) -> str:
        """
        Retorna o caminho relativo do diretório pelo ID.
        
        Prioridade:
        1. caminho_relativo (ex: "01. MS SERVIÇOS\\DSEI VILHENA CC - MOTORISTAS\\CACOAL")
        2. nome (fallback se caminho_relativo não existir)
        3. DIRETORIO_PADRAO se nada encontrado
        
        Args:
            diretorio_id: ID do diretório (ObjectId em formato string)
        
        Returns:
            Caminho relativo do diretório ou DIRETORIO_PADRAO se não encontrar
        """
        if not diretorio_id:
            return DIRETORIO_PADRAO
        
        diretorio = self.buscar_por_id(diretorio_id)
        
        if diretorio:
            # Prioridade: caminho_relativo > nome > DIRETORIO_PADRAO
            caminho = diretorio.get('caminho_relativo') or diretorio.get('nome')
            if caminho:
                return caminho
        
        return DIRETORIO_PADRAO
    
    # ==================== LISTAGEM ====================
    
    def listar_todos(self, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """
        Lista todos os diretórios com paginação
        
        Args:
            skip: Número de documentos a pular
            limit: Número máximo de documentos
        
        Returns:
            Dicionário com dados, total, paginação
        """
        if not self.disponivel:
            return {"dados": [], "total": 0, "skip": skip, "limit": limit}
        
        try:
            total = self.colecao.count_documents({})
            
            diretorios = list(
                self.colecao.find({})
                .sort("ordem", ASCENDING)
                .skip(skip)
                .limit(limit)
            )
            
            paginas = (total + limit - 1) // limit if limit > 0 else 1
            pagina_atual = (skip // limit) + 1 if limit > 0 else 1
            
            logger.debug(f"✓ {len(diretorios)}/{total} diretórios listados")
            
            return {
                "dados": diretorios,
                "total": total,
                "skip": skip,
                "limit": limit,
                "paginas": paginas,
                "pagina_atual": pagina_atual
            }
        except Exception as e:
            logger.error(f"Erro ao listar diretórios: {e}")
            return {"dados": [], "total": 0, "skip": skip, "limit": limit, "erro": str(e)}
    
    def listar_ativos(self) -> List[Dict[str, Any]]:
        """
        Lista apenas diretórios ativos
        
        Returns:
            Lista de diretórios ativos
        """
        if not self.disponivel:
            return []
        
        try:
            # Buscar por status='ativo' (campo do modelo DiretorioMongoDB)
            diretorios = list(
                self.colecao.find({"status": StatusDiretorio.ATIVO.value})
                .sort("ordem", ASCENDING)
            )
            logger.debug(f"✓ {len(diretorios)} diretórios ativos encontrados")
            return diretorios
        except Exception as e:
            logger.error(f"Erro ao listar diretórios ativos: {e}")
            return []
    
    # ==================== CRIAÇÃO ====================
    
    def criar_diretorio(self, diretorio_modelo: DiretorioMongoDB) -> Optional[str]:
        """
        Cria um novo diretório
        
        Args:
            diretorio_modelo: Instância de DiretorioMongoDB
        
        Returns:
            ID do diretório criado (string) ou None se erro
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para criar diretório")
            return None
        
        try:
            # Converter para dict
            doc = diretorio_modelo.to_mongo_insert()
            
            # Inserir no MongoDB
            resultado = self.colecao.insert_one(doc)

            if resultado and resultado.inserted_id:

                self.logger.audit(

                    action="REGISTRO_CRIADO",

                    target=f"{self.collection_name}:{resultado.inserted_id}",

                    changes={'dados': str(doc)[:200]}

                )
            diretorio_id = str(resultado.inserted_id)
            
            # Atualizar com o ID gerado
            self.colecao.update_one(
                {"_id": resultado.inserted_id},
                {"$set": {"id_diretorio": diretorio_id}}
            )
            
            # Invalidar cache
            self._invalidar_cache()
            
            logger.info(f"✓ Diretório criado: {diretorio_modelo.nome} - ID: {diretorio_id}")
            return diretorio_id
        
        except DuplicateKeyError:
            logger.warning(f"✗ Diretório duplicado: {diretorio_modelo.nome}")
            # Retornar o existente
            existente = self.buscar_por_nome(diretorio_modelo.nome)
            if existente:
                return str(existente.get("_id"))
            return None
        except Exception as e:
            logger.error(f"Erro ao criar diretório: {e}")
            return None
    
    def criar_diretorio_para_contrato(self, contrato_id: str) -> Optional[str]:
        """
        Cria automaticamente um diretório baseado no contrato.
        Busca o nome do contrato via contrato_id e cria o diretório.
        Se já existir um diretório para este contrato, retorna o existente.
        
        Args:
            contrato_id: ID do contrato (ObjectId em formato string)
        
        Returns:
            ID do diretório criado/existente (string) ou None se erro
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para criar diretório")
            return None
        
        try:
            # Verificar se já existe diretório para este contrato
            diretorio_existente = self.buscar_por_contrato_id(contrato_id)
            if diretorio_existente:
                logger.debug(f"✓ Diretório já existe para contrato: {contrato_id}")
                return str(diretorio_existente.get("_id"))
            
            # Buscar dados do contrato
            try:
                obj_id = ObjectId(contrato_id)
            except Exception:
                logger.error(f"contrato_id inválido: {contrato_id}")
                return None
            
            contrato = self.db["contratos"].find_one({"_id": obj_id})
            
            if not contrato:
                logger.error(f"Contrato não encontrado: {contrato_id}")
                return None
            
            nome_contrato = contrato.get("nome", "SEM_NOME")
            
            # Criar diretório com o nome do contrato
            diretorio = (DiretorioBuilder()
                .set_nome(nome_contrato)
                .set_descricao(f"Diretório do contrato: {nome_contrato}")
                .set_contrato_id(obj_id)
                .marcar_como_auto_criado()
                .build()
            )
            
            diretorio_id = self.criar_diretorio(diretorio)
            
            if diretorio_id:
                logger.info(f"✓ Diretório auto-criado para contrato {nome_contrato}: {diretorio_id}")
            
            return diretorio_id
        
        except Exception as e:
            logger.error(f"Erro ao criar diretório para contrato: {e}")
            return None
    
    def obter_ou_criar_para_contrato(self, contrato_id: str) -> Optional[str]:
        """
        Obtém o diretório existente para um contrato ou cria um novo.
        Método de conveniência que combina busca e criação.
        
        Args:
            contrato_id: ID do contrato (ObjectId em formato string)
        
        Returns:
            ID do diretório (string) ou None se erro
        """
        # Primeiro tentar buscar existente
        diretorio = self.buscar_por_contrato_id(contrato_id)
        if diretorio:
            return str(diretorio.get("_id"))
        
        # Se não existir, criar
        return self.criar_diretorio_para_contrato(contrato_id)
    
    # ==================== ATUALIZAÇÃO ====================
    
    @registrar_historico(campos_rastrear=None, origem_padrao="interface_cli")
    def atualizar(
        self, 
        object_id: str, 
        alteracoes: Dict[str, Any],
        **kwargs
    ) -> bool:
        """
        Atualiza dados de um diretório usando ObjectId.
        
        O histórico é registrado AUTOMATICAMENTE pelo decorador @registrar_historico.
        
        Args:
            object_id: ObjectId do diretório em formato string
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
                alteracoes['nome_normalizado'] = self._normalizar_nome(alteracoes['nome'])
            
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
                logger.info(f"✓ Diretório {object_id} atualizado - campos: {campos}")
                return True
            else:
                logger.debug(f"Diretório {object_id} sem alterações")
                return False
        except Exception as e:
            logger.error(f"Erro ao atualizar diretório: {e}")
            return False
    
    # ==================== INATIVAÇÃO ====================
    
    def marcar_inativo(self, diretorio_id: str) -> bool:
        """
        Marca um diretório como inativo (soft delete)
        Verifica se há funcionários usando antes de inativar
        
        Args:
            diretorio_id: ID do diretório
        
        Returns:
            True se sucesso, False se há referências ou erro
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível")
            return False
        
        try:
            # Verificar se há funcionários usando este diretório
            if self._verificar_referencias_funcionarios(diretorio_id):
                logger.warning(
                    f"✗ Não é possível inativar diretório {diretorio_id}: "
                    "existem funcionários vinculados"
                )
                return False
            
            # Converter para ObjectId
            obj_id = ObjectId(diretorio_id)
            
            # Marcar como inativo
            resultado = self.colecao.update_one(
                {"_id": obj_id},
                {
                    "$set": {
                        "status": StatusDiretorio.INATIVO.value,
                        "atualizado_em": datetime.now(timezone.utc)
                    },
                    "$inc": {"versao": 1},
                    "$push": {
                        "historico_alteracoes": {
                            "timestamp": datetime.now(timezone.utc),
                            "acao": "Diretório marcado como inativo",
                            "origem": "interface_cli",
                            "detalhes": {}
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
                # Invalidar cache
                self._invalidar_cache()
                logger.info(f"✓ Diretório marcado como inativo: {diretorio_id}")
                return True
            else:
                logger.warning(f"Diretório não encontrado: {diretorio_id}")
                return False
        
        except Exception as e:
            logger.error(f"Erro ao marcar diretório como inativo: {e}")
            return False
    
    def _verificar_referencias_funcionarios(self, diretorio_id: str) -> bool:
        """
        Verifica se existem funcionários usando este diretório
        
        Args:
            diretorio_id: ID do diretório
        
        Returns:
            True se há funcionários usando, False caso contrário
        """
        try:
            # Converter para ObjectId
            obj_id = ObjectId(diretorio_id)
            
            # Buscar na coleção de funcionários
            funcionarios_colecao = self.db["funcionarios"]
            count = funcionarios_colecao.count_documents({"diretorio_id": obj_id})
            
            return count > 0
        
        except Exception as e:
            logger.error(f"Erro ao verificar referências de funcionários: {e}")
            return False
    
    # ==================== ESTATÍSTICAS ====================
    
    def obter_estatisticas(self) -> Dict[str, Any]:
        """
        Retorna estatísticas sobre diretórios
        
        Returns:
            Dicionário com estatísticas
        """
        if not self.disponivel:
            return {'status': 'MongoDB indisponível', 'total_diretorios': 0}
        
        try:
            total = self.colecao.count_documents({})
            ativos = self.colecao.count_documents({"status": StatusDiretorio.ATIVO.value})
            inativos = self.colecao.count_documents({"status": StatusDiretorio.INATIVO.value})
            auto_criados = self.colecao.count_documents({"auto_criado": True})
            com_contrato = self.colecao.count_documents({"contrato_id": {"$ne": None}})
            
            stats = {
                'status': 'OK',
                'total_diretorios': total,
                'diretorios_ativos': ativos,
                'diretorios_inativos': inativos,
                'auto_criados': auto_criados,
                'com_contrato_vinculado': com_contrato,
                'banco_dados': self.db_name,
                'colecao': self.collection_name
            }
            
            logger.debug(f"Estatísticas de Diretórios: {total} no banco")
            return stats
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {'status': 'Erro ao obter estatísticas', 'erro': str(e)}
    
    # ==================== DESCONEXÃO ====================
    
    def desconectar(self) -> None:
        """
        Desconecta do MongoDB.
        
        Nota: os serviços usam o pool compartilhado MongoDBConnectionPool,
        portanto "desconectar" aqui apenas registra no log. O cliente real
        é gerenciado pelo pool (compartilhado com outros serviços).
        """
        try:
            logger.info("Solicitação de desconexão (Diretórios) - conexão é gerenciada pelo pool compartilhado")
        except Exception as e:
            logger.error(f"Erro ao desconectar: {e}")


# Instância global do serviço de Diretórios
diretorio_service = DiretorioService() if MONGODB_DISPONIVEL else None
