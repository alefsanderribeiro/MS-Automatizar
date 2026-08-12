"""
Serviço de Empresas em MongoDB
Gerencia armazenamento, busca e atualização de empresas
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import dotenv

from src.utils.logger_config import logger
from src.utils.dotenv_path import caminho_dotenv
from src.services.mongodb_connection import MongoDBConnectionPool, retry_mongodb, medir_tempo
from src.services.historico_decorators import registrar_historico, HistoricoMixin
from src.services.cache_service import cache_service

try:
    from pymongo import ASCENDING
    MONGODB_DISPONIVEL = True
except ImportError:
    MONGODB_DISPONIVEL = False
    logger.warning("PyMongo não instalado. Instale com: pip install pymongo")


class EmpresaService(HistoricoMixin):
    """
    Gerencia armazenamento de Empresas em MongoDB.

    Responsabilidades:
    - Salvar/atualizar empresas (upsert)
    - Buscar empresas existentes por nome/CNPJ
    - Autocadastro de empresas incompletas
    - Gerenciar índices para performance
    - Manter relacionamentos com funcionários e folhas de ponto
    - Cache em memória para evitar buscas repetidas
    - Usa MongoDBConnectionPool para evitar múltiplas conexões

    Coleção: "empresas"
    """

    def __init__(self, collection_name: str = "empresas"):
        """
        Inicializa serviço de empresas usando pool centralizado.

        Args:
            collection_name: Nome da coleção
        """
        # Armazenar informações do .env para referência
        self.mongo_uri = dotenv.get_key(caminho_dotenv(), "MONGO_URI") or "mongodb://localhost:27017"
        self.db_name = dotenv.get_key(caminho_dotenv(), "MONGO_DATABASE_NAME") or "MS_Automatizar"
        self.collection_name = collection_name

        # Cache em memória para empresas (chave: ObjectId string, valor: documento)
        self._cache_empresas: Dict[str, Dict[str, Any]] = {}

        # Cache service (Redis + memória) para otimização
        self.cache = cache_service

        if not MONGODB_DISPONIVEL:
            logger.error(
                "MongoDB não disponível. "
                "Instale PyMongo com: pip install pymongo"
            )
            self.pool = None
            self.db = None
            self.colecao = None
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
            # Criar índices para melhor performance
            self._criar_indices()
            
            # Carregar cache completo para otimização
            self._carregar_cache_completo()
            
            self._disponivel = True
            logger.debug(
                f"✓ EmpresaService inicializado (usando pool centralizado)"
            )

        except Exception as e:
            logger.error(f"✗ Erro ao inicializar EmpresaService: {e}")
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
        - Índice simples em nome (para autocadastro por busca)
        - Índice simples em cnpj (único se preenchido)
        - Índice simples em status
        """
        try:
            # Índice em nome para busca fuzzy (normalizado)
            self.colecao.create_index([("nome_normalizado", ASCENDING)], name="idx_nome_normalizado")
            
            # Índice em CNPJ (único, mas sparse para permitir nulos)
            self.colecao.create_index(
                [("cnpj", ASCENDING)],
                unique=True,
                sparse=True,
                name="idx_cnpj_unico"
            )
            
            # Índices simples para buscas frequentes
            self.colecao.create_index([("status", ASCENDING)], name="idx_status")
            self.colecao.create_index([("incompleto", ASCENDING)], name="idx_incompleto")
            self.colecao.create_index([("criado_em", ASCENDING)], name="idx_criado_em")
            
            logger.debug("✓ Índices criados para Empresas em MongoDB")
        except Exception as e:
            logger.warning(f"Erro ao criar índices: {e}")
    
    def _carregar_cache_completo(self) -> None:
        """
        Pré-carrega TODAS as empresas em cache (memória + Redis).
        
        Empresas são uma tabela de referência pequena (~50-200 registros),
        então é viável carregar tudo para otimizar lookups O(1).
        
        Cache híbrido:
        - Cache local em memória (_cache_empresas) para acesso ultra-rápido
        - Cache Redis (cache_service) para persistência entre restarts
        """
        try:
            # Buscar TODAS as empresas do MongoDB
            todas_empresas = list(self.colecao.find({}))
            
            if not todas_empresas:
                logger.warning("⚠️ Nenhuma empresa encontrada para carregar cache")
                return
            
            # Poplar cache em memória (dict local)
            cache_data_redis = {}
            for empresa in todas_empresas:
                empresa_id = str(empresa["_id"])
                # Cache local
                self._cache_empresas[empresa_id] = empresa
                # Preparar para cache Redis
                cache_data_redis[f"empresas:{empresa_id}"] = empresa
            
            # Poplar cache Redis em batch (uma operação)
            ttl = int(os.getenv("CACHE_TTL", "300"))  # 5 minutos padrão
            self.cache.set_many(cache_data_redis, ttl=ttl)
            
            logger.info(f"✅ Cache de empresas carregado: {len(todas_empresas)} registros (memória + Redis)")
            
        except Exception as e:
            logger.error(f"Erro ao carregar cache de empresas: {e}")
    
    def _invalidar_cache(self) -> None:
        """
        Invalida TODO o cache de empresas (memória + Redis).
        
        Deve ser chamado após operações de CREATE, UPDATE ou DELETE
        para garantir que próximas leituras busquem dados atualizados.
        
        Após invalidação, próxima busca recarregará o cache automaticamente.
        """
        try:
            # Limpar cache local
            self._cache_empresas.clear()
            
            # Limpar cache Redis (todas as chaves empresas:*)
            deleted_count = self.cache.invalidate("empresas:*")
            
            logger.debug(f"🗑️ Cache de empresas invalidado: {deleted_count} chaves removidas do Redis")
            
            # Recarregar cache imediatamente para próximas buscas
            self._carregar_cache_completo()
            
        except Exception as e:
            logger.error(f"Erro ao invalidar cache de empresas: {e}")
    
    def buscar_por_nome(self, nome_empresa: str, exato: bool = False) -> Optional[Dict[str, Any]]:
        """
        Busca uma empresa pelo nome (com busca normalizada para flexibilidade)
        Usa cache em memória para otimizar buscas repetidas.

        Args:
            nome_empresa: Nome ou parte do nome da empresa
            exato: Se True, busca exata; se False, busca parcial normalizada

        Returns:
            Dicionário com os dados da empresa ou None
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para busca")
            return None

        try:
            import unicodedata

            # Normalizar nome para busca
            nfkd = unicodedata.normalize('NFKD', nome_empresa)
            nome_normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)])
            nome_normalizado = nome_normalizado.lower()

            if exato:
                # Busca exata
                filtro = {"nome_normalizado": nome_normalizado}
            else:
                # Busca com regex (parcial)
                filtro = {"nome_normalizado": {"$regex": nome_normalizado, "$options": "i"}}

            documento = self.colecao.find_one(filtro)

            if documento:
                # Adicionar ao cache (usar _id como chave)
                empresa_id = str(documento.get("_id"))
                self._cache_empresas[empresa_id] = documento

                logger.debug(f"✓ Empresa encontrada: {documento.get('nome')}")
                return documento
            else:
                logger.debug(f"✗ Empresa não encontrada: {nome_empresa}")
                return None

        except Exception as e:
            logger.error(f"Erro ao buscar empresa por nome: {e}")
            return None

    def buscar_por_nome_ou_simplificado(self, nome_empresa: str, exato: bool = False) -> Optional[Dict[str, Any]]:
        """
        Busca uma empresa primeiro pelo nome_simplificado, com fallback para nome completo.
        Estratégia para envio multidevice: tenta nome simplificado (ex: "Moraes") antes do nome completo.

        Args:
            nome_empresa: Nome ou parte do nome da empresa
            exato: Se True, busca exata; se False, busca parcial normalizada

        Returns:
            Dicionário com os dados da empresa ou None
        """
        logger.info(f"[EMPRESA] Iniciando buscar_por_nome_ou_simplificado: {nome_empresa}")

        if not self.disponivel:
            logger.warning("MongoDB não disponível para busca de empresa")
            return None

        try:
            import unicodedata

            def normalizar_texto(texto: str) -> str:
                """Remove acentos e converte para minúsculas"""
                if not texto:
                    return ""
                nfkd = unicodedata.normalize('NFKD', texto)
                return ''.join([c for c in nfkd if not unicodedata.combining(c)]).lower()

            # Normalizar nome para busca
            nome_normalizado = normalizar_texto(nome_empresa)
            logger.debug(f"[EMPRESA] Nome normalizado: '{nome_empresa}' → '{nome_normalizado}'")

            # Buscar TODOS os documentos (cache faz isso ser rápido)
            todos_docs = list(self.colecao.find({}))
            logger.debug(f"[EMPRESA] Total de empresas em base: {len(todos_docs)}")

            # 1. PRIMEIRO: Tentar buscar por nome_simplificado
            logger.debug(f"[EMPRESA] ETAPA 1: Buscando por nome_simplificado...")
            for documento in todos_docs:
                nome_simp = documento.get("nome_simplificado", "")
                if not nome_simp:
                    continue

                nome_simp_normalizado = normalizar_texto(nome_simp)

                # Comparação: exata ou parcial
                match = (nome_simp_normalizado == nome_normalizado) if exato else (nome_normalizado in nome_simp_normalizado)

                if match:
                    empresa_id = str(documento.get("_id"))
                    self._cache_empresas[empresa_id] = documento
                    logger.info(f"[EMPRESA] ✓ Encontrada por nome_simplificado: {documento.get('nome')} ({documento.get('nome_simplificado')}) - ID: {empresa_id}")
                    return documento

            # 2. FALLBACK: Buscar por nome completo
            logger.debug(f"[EMPRESA] ETAPA 2: Buscando por nome completo...")
            for documento in todos_docs:
                nome_completo = documento.get("nome", "")
                if not nome_completo:
                    continue

                nome_completo_normalizado = normalizar_texto(nome_completo)

                # Comparação: exata ou parcial
                match = (nome_completo_normalizado == nome_normalizado) if exato else (nome_normalizado in nome_completo_normalizado)

                if match:
                    empresa_id = str(documento.get("_id"))
                    self._cache_empresas[empresa_id] = documento
                    logger.info(f"[EMPRESA] ✓ Encontrada por nome completo: {documento.get('nome')} - ID: {empresa_id}")
                    return documento

            logger.warning(f"[EMPRESA] ✗ Nenhuma empresa encontrada para: '{nome_empresa}'")
            return None

        except Exception as e:
            logger.error(f"[EMPRESA] ✗ Erro ao buscar empresa por nome: {e}", exc_info=True)
            return None
    
    def buscar_todas_por_nome(self, nome_empresa: str) -> List[Dict[str, Any]]:
        """
        Busca TODAS as empresas que correspondem ao nome (busca parcial).
        Útil para listagem e seleção quando há múltiplos resultados.
        
        Args:
            nome_empresa: Nome ou parte do nome da empresa
        
        Returns:
            Lista de empresas encontradas (pode ser vazia)
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para busca")
            return []
        
        try:
            import unicodedata
            
            # Normalizar nome para busca
            nfkd = unicodedata.normalize('NFKD', nome_empresa)
            nome_normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)])
            nome_normalizado = nome_normalizado.lower()
            
            # Busca com regex (parcial)
            filtro = {"nome_normalizado": {"$regex": nome_normalizado, "$options": "i"}}
            
            documentos = list(self.colecao.find(filtro).sort("nome", 1))
            
            # Adicionar ao cache
            for doc in documentos:
                empresa_id = str(doc.get("_id"))
                self._cache_empresas[empresa_id] = doc
            
            logger.debug(f"✓ {len(documentos)} empresa(s) encontrada(s) com nome contendo '{nome_empresa}'")
            return documentos
        
        except Exception as e:
            logger.error(f"Erro ao buscar empresas por nome: {e}")
            return []

    def buscar_por_cnpj(self, cnpj: str) -> Optional[Dict[str, Any]]:
        """
        Busca uma empresa pelo CNPJ
        
        Args:
            cnpj: CNPJ da empresa
        
        Returns:
            Dicionário com os dados da empresa ou None
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para busca")
            return None
        
        try:
            # Remover caracteres especiais do CNPJ para busca
            cnpj_limpo = cnpj.replace(".", "").replace("-", "").replace("/", "")
            
            documento = self.colecao.find_one({"cnpj": {"$regex": cnpj_limpo}})
            
            if documento:
                # Adicionar ao cache
                empresa_id = str(documento.get("_id"))
                self._cache_empresas[empresa_id] = documento
                
                logger.debug(f"✓ Empresa encontrada por CNPJ: {documento.get('nome')}")
                return documento
            else:
                logger.debug(f"✗ Empresa não encontrada pelo CNPJ: {cnpj}")
                return None
        
        except Exception as e:
            logger.error(f"Erro ao buscar empresa por CNPJ: {e}")
            return None
    
    def buscar_por_id(self, empresa_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca uma empresa por ObjectId.
        
        OTIMIZADO: Verifica cache (memória → Redis → MongoDB) nessa ordem.
        Cache hit = O(1), cache miss = O(log n) no MongoDB com índice.
        
        Args:
            empresa_id: ID da empresa (ObjectId em formato string)
        
        Returns:
            Dicionário com os dados da empresa ou None
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para busca")
            return None
        
        # 1. Verificar cache local em memória (mais rápido - O(1))
        if empresa_id in self._cache_empresas:
            logger.debug(f"✓ Empresa encontrada no cache local: {empresa_id}")
            return self._cache_empresas[empresa_id]
        
        # 2. Verificar cache Redis (rápido - O(1) remoto)
        cache_key = f"empresas:{empresa_id}"
        empresa_redis = self.cache.get(cache_key)
        if empresa_redis:
            # Atualizar cache local
            self._cache_empresas[empresa_id] = empresa_redis
            logger.debug(f"✓ Empresa encontrada no cache Redis: {empresa_id}")
            return empresa_redis
        
        # 3. Buscar no MongoDB (último recurso - O(log n))
        try:
            from bson.objectid import ObjectId
            
            # Converter string para ObjectId
            try:
                obj_id = ObjectId(empresa_id)
            except Exception:
                logger.warning(f"ID inválido para conversão: {empresa_id}")
                return None
            
            documento = self.colecao.find_one({"_id": obj_id})
            
            if documento:
                # Atualizar AMBOS os caches para próximas buscas
                self._cache_empresas[empresa_id] = documento
                ttl = int(os.getenv("CACHE_TTL", "300"))
                self.cache.set(cache_key, documento, ttl=ttl)
                
                logger.debug(f"✓ Empresa encontrada no MongoDB (cache miss): {documento.get('nome')}")
                return documento
            else:
                logger.debug(f"✗ Empresa não encontrada pelo ID: {empresa_id}")
                return None
        
        except Exception as e:
            logger.error(f"Erro ao buscar empresa por ID: {e}")
            return None
    
    def obter_ou_criar_incompleta(self, nome_empresa: str) -> Dict[str, Any]:
        """
        Busca uma empresa existente ou cria uma nova incompleta (autocadastro)
        Similar ao autocadastro de funcionários
        Trata erros de duplicata E11000 buscando novamente
        
        Args:
            nome_empresa: Nome da empresa
        
        Returns:
            Dicionário com os dados da empresa (existente ou nova)
        """
        if not self.disponivel:
            logger.error("MongoDB não disponível para autocadastro")
            return {"nome": nome_empresa, "incompleto": True, "erro": "MongoDB indisponível"}
        
        try:
            # Verificar se empresa já existe (busca exata)
            empresa_existente = self.buscar_por_nome(nome_empresa, exato=True)
            
            if empresa_existente and empresa_existente.get("_id"):
                logger.info(f"✓ Empresa reutilizada: {nome_empresa}")
                return empresa_existente
            
            # Se não encontrou exato, tentar busca parcial
            if not empresa_existente:
                empresa_existente = self.buscar_por_nome(nome_empresa, exato=False)
                
                if empresa_existente and empresa_existente.get("_id"):
                    logger.info(f"✓ Empresa encontrada (busca parcial): {nome_empresa}")
                    return empresa_existente
            
            # Criar empresa incompleta
            from src.models.empresa_models import EmpresaBuilder
            
            empresa = (EmpresaBuilder()
                .set_nome(nome_empresa)
                .marcar_como_incompleta()
                .build()
            )
            
            # Converter para dict e NÃO INCLUIR o campo cnpj se for None
            doc_empresa = empresa.to_mongo_insert()
            
            # IMPORTANTE: Não incluir cnpj se for None para evitar E11000 unique violation
            # com múltiplos NULL values (mesmo com sparse=true, MongoDB não permite múltiplos NULL)
            if doc_empresa.get('cnpj') is None:
                doc_empresa.pop('cnpj', None)
            
            resultado = self.colecao.insert_one(doc_empresa)
            
            # Adicionar o ID gerado
            doc_empresa['_id'] = resultado.inserted_id
            
            logger.info(f"✓ Empresa incompleta criada (autocadastro): {nome_empresa} - ID: {resultado.inserted_id}")
            return doc_empresa
        
        except Exception as e:
            # Se erro E11000 (duplicata), tentar buscar novamente
            if "E11000" in str(e):
                logger.debug(f"Erro de duplicata ao criar empresa, buscando novamente: {e}")
                
                # Tentar busca exata novamente
                empresa_retry = self.buscar_por_nome(nome_empresa, exato=True)
                if empresa_retry and empresa_retry.get("_id"):
                    logger.info(f"✓ Empresa encontrada após erro de duplicata: {nome_empresa}")
                    return empresa_retry
                
                # Tentar busca parcial
                empresa_retry = self.buscar_por_nome(nome_empresa, exato=False)
                if empresa_retry and empresa_retry.get("_id"):
                    logger.info(f"✓ Empresa encontrada (busca parcial) após erro de duplicata: {nome_empresa}")
                    return empresa_retry
                
                logger.error(f"Erro de duplicata mas empresa não encontrada na busca: {nome_empresa}")
            
            logger.error(f"Erro ao criar empresa incompleta: {e}")
            # Retornar estrutura com erro para rastreamento
            return {"nome": nome_empresa, "incompleto": True, "erro": str(e)}
    
    def salvar_ou_atualizar(self, empresa_mongodb: Dict[str, Any]) -> bool:
        """
        Salva ou atualiza uma empresa (UPSERT)
        Se já existir com o mesmo nome normalizado, atualiza; senão, insere
        
        Args:
            empresa_mongodb: Dicionário com dados da EmpresaMongoDB ou instância convertida
        
        Returns:
            True se sucesso, False caso contrário
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para salvar")
            return False
        
        try:
            # Se receber uma instância Pydantic, converter para dict
            if hasattr(empresa_mongodb, 'dict'):
                documento = empresa_mongodb.dict()
            else:
                documento = empresa_mongodb.copy()
            
            # Filtro por nome normalizado (para atualizar existentes)
            filtro = {
                "nome_normalizado": documento.get('nome_normalizado')
            }
            
            # Remover _id se existir
            documento.pop('_id', None)
            
            # Upsert: atualizar se existir, inserir se não
            resultado = self.colecao.update_one(
                filtro,
                {'$set': documento},
                upsert=True
            )
            
            if resultado.upserted_id:
                logger.info(
                    f"✓ Nova empresa inserida: {documento.get('nome')} - ID: {resultado.upserted_id}"
                )
                # Invalidar cache para forçar reload
                self._invalidar_cache()
                return True
            elif resultado.modified_count > 0:
                logger.info(f"✓ Empresa atualizada: {documento.get('nome')}")
                # Invalidar cache para forçar reload
                self._invalidar_cache()
                return True
            else:
                logger.debug(f"ℹ Empresa já existia com mesmos dados: {documento.get('nome')}")
                return True
        
        except Exception as e:
            logger.error(f"Erro ao salvar/atualizar empresa: {e}")
            return False
    
    def listar_todos(self, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """
        Lista todas as empresas com paginação
        
        Args:
            skip: Número de documentos a pular (offset)
            limit: Número máximo de documentos a retornar
        
        Returns:
            Dicionário com:
            - dados: Lista de empresas
            - total: Total de empresas no banco
            - skip: Offset usado
            - limit: Limite usado
            - paginas: Total de páginas
            - pagina_atual: Página atual (1-indexed)
        """
        if not self.disponivel:
            return {"dados": [], "total": 0, "skip": skip, "limit": limit, "paginas": 0, "pagina_atual": 0}
        
        try:
            # Contar total
            total = self.colecao.count_documents({})
            
            # Buscar com paginação
            documentos = list(
                self.colecao.find({})
                .sort("nome", 1)
                .skip(skip)
                .limit(limit)
            )
            
            # Calcular paginação
            paginas = (total + limit - 1) // limit if limit > 0 else 1
            pagina_atual = (skip // limit) + 1 if limit > 0 else 1
            
            logger.debug(f"✓ {len(documentos)}/{total} empresas listadas (página {pagina_atual}/{paginas})")
            
            return {
                "dados": documentos,
                "total": total,
                "skip": skip,
                "limit": limit,
                "paginas": paginas,
                "pagina_atual": pagina_atual
            }
        
        except Exception as e:
            logger.error(f"Erro ao listar empresas: {e}")
            return {"dados": [], "total": 0, "skip": skip, "limit": limit, "paginas": 0, "pagina_atual": 0, "erro": str(e)}
    
    def listar_incompletas(self) -> list:
        """
        Lista todas as empresas incompletas (para serem preenchidas)
        
        Returns:
            Lista de dicionários com as empresas incompletas
        """
        if not self.disponivel:
            return []
        
        try:
            documentos = list(
                self.colecao.find(
                    {"incompleto": True},
                    {"_id": 0}
                ).sort("criado_em", -1)
            )
            
            logger.info(f"✓ {len(documentos)} empresas incompletas encontradas")
            return documentos
        
        except Exception as e:
            logger.error(f"Erro ao listar empresas incompletas: {e}")
            return []
    
    def obter_estatisticas(self) -> Dict[str, Any]:
        """
        Retorna estatísticas sobre empresas
        
        Returns:
            Dicionário com estatísticas
        """
        if not self.disponivel:
            return {'status': 'MongoDB indisponível', 'total_empresas': 0}
        
        try:
            total = self.colecao.count_documents({})
            completas = self.colecao.count_documents({"incompleto": False})
            incompletas = self.colecao.count_documents({"incompleto": True})
            ativas = self.colecao.count_documents({"status": "ativa"})
            
            stats = {
                'status': 'OK' if self.disponivel else 'Erro',
                'total_empresas': total,
                'empresas_completas': completas,
                'empresas_incompletas': incompletas,
                'empresas_ativas': ativas,
                'banco_dados': self.db_name,
                'colecao': self.collection_name
            }
            
            logger.info(f"Estatísticas de Empresas: {total} empresas no banco")
            return stats
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {'status': 'Erro ao obter estatísticas', 'erro': str(e)}
    
    def atualizar_cnpj(self, empresa_id: str, cnpj: str) -> bool:
        """
        Atualiza o CNPJ de uma empresa existente
        
        Args:
            empresa_id: ID da empresa (string do ObjectId)
            cnpj: CNPJ a ser adicionado/atualizado
        
        Returns:
            True se sucesso, False caso contrário
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para atualizar CNPJ")
            return False
        
        try:
            from bson.objectid import ObjectId
            
            # Converter string ID para ObjectId
            try:
                obj_id = ObjectId(empresa_id)
            except Exception:
                logger.warning(f"ID inválido para conversão: {empresa_id}")
                return False
            
            # Limpar CNPJ (remover caracteres especiais)
            cnpj_limpo = cnpj.replace(".", "").replace("-", "").replace("/", "")
            
            resultado = self.colecao.update_one(
                {"_id": obj_id},
                {"$set": {"cnpj": cnpj_limpo}}
            )
            
            if resultado.modified_count > 0:
                logger.info(f"✓ CNPJ atualizado para empresa {empresa_id}: {cnpj_limpo}")
                # Invalidar cache
                self._invalidar_cache()
                return True
            else:
                logger.debug(f"CNPJ não foi modificado (já existia?): {empresa_id}")
                return True  # Não é erro, pode já estar atualizado
        
        except Exception as e:
            logger.error(f"Erro ao atualizar CNPJ: {e}")
            return False
    
    @registrar_historico(campos_rastrear=None, origem_padrao="interface_cli")
    def atualizar(
        self, 
        object_id: str, 
        alteracoes: Dict[str, Any],
        **kwargs
    ) -> bool:
        """
        Atualiza dados de uma empresa com suporte a histórico de alterações.
        
        O histórico é registrado AUTOMATICAMENTE pelo decorador @registrar_historico.
        
        Args:
            object_id: ID da empresa (ObjectId em formato string)
            alteracoes: Dicionário com campos a atualizar
            **kwargs: 
                - registrar_historico (bool): Se False, não registra histórico
                - origem (str): Origem da alteração
        
        Returns:
            True se sucesso, False caso contrário
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para atualizar empresa")
            return False
        
        try:
            from bson.objectid import ObjectId
            
            # Converter ID
            try:
                obj_id = ObjectId(object_id)
            except Exception:
                logger.warning(f"ID inválido: {object_id}")
                return False
            
            # Atualizar timestamp
            alteracoes['atualizado_em'] = datetime.now(timezone.utc)
            
            # Se nome foi alterado, atualizar nome_normalizado também
            if "nome" in alteracoes:
                import unicodedata
                nome = alteracoes["nome"]
                nfkd = unicodedata.normalize('NFKD', nome)
                nome_normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)])
                alteracoes["nome_normalizado"] = nome_normalizado.lower()
            
            resultado = self.colecao.update_one(
                {"_id": obj_id},
                {"$set": alteracoes}
            )
            
            if resultado.modified_count > 0:
                # Invalidar cache completo (memória + Redis)
                self._invalidar_cache()
                
                campos = ", ".join([k for k in alteracoes.keys() if k not in ['atualizado_em', 'nome_normalizado']])
                logger.info(f"✓ Empresa atualizada: {object_id} - campos: {campos}")
                return True
            else:
                logger.debug(f"Nenhuma alteração efetiva para empresa: {object_id}")
                return True
        
        except Exception as e:
            logger.error(f"Erro ao atualizar empresa: {e}")
            return False
    
    def criar_empresa(self, dados: Dict[str, Any]) -> Optional[str]:
        """
        Cria uma nova empresa completa.
        
        Args:
            dados: Dicionário com dados da empresa (nome obrigatório)
        
        Returns:
            ObjectId da empresa criada ou None se erro
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para criar empresa")
            return None
        
        try:
            from src.models.empresa_models import EmpresaMongoDB, StatusEmpresa
            import unicodedata
            
            # Validar nome obrigatório
            nome = dados.get("nome", "").strip()
            if not nome:
                logger.error("Nome da empresa é obrigatório")
                return None
            
            # Verificar se empresa já existe
            existente = self.buscar_por_nome(nome, exato=True)
            if existente:
                logger.warning(f"Empresa já existe: {nome}")
                return str(existente.get("_id"))
            
            # Preparar documento
            agora = datetime.now(timezone.utc)
            
            # Normalizar nome
            nfkd = unicodedata.normalize('NFKD', nome)
            nome_normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)])
            
            documento = {
                "nome": nome,
                "nome_normalizado": nome_normalizado.lower(),
                "cnpj": dados.get("cnpj"),
                "atividade": dados.get("atividade"),
                "endereco": dados.get("endereco"),
                "telefone": dados.get("telefone"),
                "email": dados.get("email"),
                "responsavel": dados.get("responsavel"),
                "status": dados.get("status", StatusEmpresa.ATIVA.value),
                "incompleto": False,
                "criado_em": agora,
                "atualizado_em": agora,
                "versao": 1,
                "historico_alteracoes": [{
                    "timestamp": agora.isoformat(),
                    "acao": "Empresa criada",
                    "versao_anterior": 0,
                    "versao_nova": 1,
                    "detalhes": {"origem": "interface_gerenciamento"}
                }]
            }
            
            # Remover campos None para evitar problemas com índices sparse
            documento = {k: v for k, v in documento.items() if v is not None}
            
            resultado = self.colecao.insert_one(documento)
            
            logger.info(f"✓ Empresa criada: {nome} - ID: {resultado.inserted_id}")
            
            # Invalidar cache para incluir nova empresa
            self._invalidar_cache()
            
            return str(resultado.inserted_id)
        
        except Exception as e:
            logger.error(f"Erro ao criar empresa: {e}")
            return None
    
    def alterar_status(self, empresa_id: str, novo_status: str) -> bool:
        """
        Altera o status de uma empresa (ativa, inativa, suspensa, em_construcao).
        Registra no histórico de alterações.
        
        Args:
            empresa_id: ID da empresa
            novo_status: Novo status (ativa, inativa, suspensa, em_construcao)
        
        Returns:
            True se sucesso, False caso contrário
        """
        from src.models.empresa_models import StatusEmpresa
        
        # Validar status
        status_validos = [s.value for s in StatusEmpresa]
        if novo_status not in status_validos:
            logger.error(f"Status inválido: {novo_status}. Válidos: {status_validos}")
            return False
        
        alteracoes = {"status": novo_status}
        
        # Se mudar para ativa, marcar como completa
        if novo_status == StatusEmpresa.ATIVA.value:
            alteracoes["incompleto"] = False
        
        return self.atualizar(empresa_id, alteracoes, registrar_historico=True)
    
    def listar_por_status(self, status: str) -> List[Dict[str, Any]]:
        """
        Lista empresas por status.
        
        Args:
            status: Status a filtrar (ativa, inativa, suspensa, em_construcao)
        
        Returns:
            Lista de empresas com o status especificado
        """
        if not self.disponivel:
            return []
        
        try:
            documentos = list(
                self.colecao.find({"status": status})
                .sort("nome", 1)
            )
            
            logger.debug(f"✓ {len(documentos)} empresas com status '{status}'")
            return documentos
        
        except Exception as e:
            logger.error(f"Erro ao listar empresas por status: {e}")
            return []
    
    def listar_ativos(self) -> List[Dict[str, Any]]:
        """
        Lista apenas empresas ativas (pré-filtradas no MongoDB).
        Aceita tanto "ativa" (feminino) quanto "ativo" (masculino) para compatibilidade.
        
        Returns:
            Lista de empresas ativas ordenadas alfabeticamente
        """
        if not self.disponivel:
            return []
        
        try:
            # Query MongoDB com $in para aceitar ambas as formas de gênero
            documentos = list(
                self.colecao.find({"status": {"$in": ["ativa", "ativo"]}})
                .sort("nome", 1)
            )
            
            logger.debug(f"✓ {len(documentos)} empresas ativas encontradas")
            return documentos
        
        except Exception as e:
            logger.error(f"Erro ao listar empresas ativas: {e}")
            return []
    
    def remover_campo_id_empresa(self) -> int:
        """
        Remove o campo id_empresa de todas as empresas (migração).
        Este campo era redundante pois MongoDB usa _id automaticamente.
        
        Returns:
            Número de documentos atualizados
        """
        if not self.disponivel:
            return 0
        
        try:
            resultado = self.colecao.update_many(
                {"id_empresa": {"$exists": True}},
                {"$unset": {"id_empresa": ""}}
            )
            
            if resultado.modified_count > 0:
                logger.info(f"✓ Campo id_empresa removido de {resultado.modified_count} empresas")
            
            return resultado.modified_count
        
        except Exception as e:
            logger.error(f"Erro ao remover campo id_empresa: {e}")
            return 0
    
    def desconectar(self) -> None:
        """Desconecta do MongoDB (não necessário com pool centralizado)"""
        logger.debug("desconectar() chamado - pool centralizado gerencia conexões")


# Instância global do serviço de Empresas
empresa_service = EmpresaService() if MONGODB_DISPONIVEL else None
