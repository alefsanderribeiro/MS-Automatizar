"""
Serviço CRUD de Contatos de Envio de Folhas de Ponto
Gerencia operações de criação, leitura, atualização e exclusão de contatos
"""

import os
import re
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import dotenv

from src.utils.dotenv_path import caminho_dotenv
from src.services.mongodb_connection import MongoDBConnectionPool, retry_mongodb
from src.utils.logger_config_v2 import get_logger

logger = get_logger("contatos_folha_ponto")

try:
    from pymongo import ASCENDING, DESCENDING
    from bson import ObjectId
    MONGODB_DISPONIVEL = True
except ImportError:
    MONGODB_DISPONIVEL = False
    logger.warning("PyMongo não instalado. Instale com: pip install pymongo")


class ContatosFolhaPontoService:
    """
    Gerencia contatos de envio de folhas de ponto em MongoDB.
    
    Coleção: "contatos_folha_ponto"
    
    Estrutura do documento:
    {
        "funcionario_id": "ID da planilha",
        "nome": "Nome completo",
        "email": "email1@example.com,email2@example.com",
        "telefone": "+5511999999999",
        "grupo_whatsapp": "Grupo 1,Grupo 2",
        "enviar_email": true,
        "enviar_whatsapp": true,
        "enviar_grupo_whatsapp": true,
        "enviar_impresso": false,
        "empresa": "Nome da Empresa",
        "local_contrato_polo": "Local/Contrato/Polo",
        "diretorio_geral": "Z:\\04. PESSOAL\\FOLHA PONTO",
        "diretorio_especifico": "01. MS SERVICOS\\ADMINISTRATIVO",
        "criado_em": datetime,
        "atualizado_em": datetime
    }
    """

    def __init__(self, collection_name: str = "contatos_folha_ponto"):
        """
        Inicializa o serviço de contatos.
        
        Args:
            collection_name: Nome da coleção MongoDB
        """
        self.logger = get_logger("contatos_folha_ponto")
        self.collection_name = collection_name
        
        # Variáveis de ambiente
        self.mongo_uri = dotenv.get_key(caminho_dotenv(), "MONGO_URI") or "mongodb://localhost:27017"
        self.db_name = dotenv.get_key(caminho_dotenv(), "MONGO_DATABASE_NAME") or "MS_Automatizar"
        
        if not MONGODB_DISPONIVEL:
            logger.error("MongoDB não disponível. Instale PyMongo com: pip install pymongo")
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
            self._criar_indices()
            
            self._disponivel = True
            logger.debug("✓ ContatosFolhaPontoService inicializado")
            
        except Exception as e:
            logger.error(f"✗ Erro ao inicializar ContatosFolhaPontoService: {e}")
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
            # Índice único por funcionario_id (sparse para permitir nulos)
            self.colecao.create_index(
                [("funcionario_id", ASCENDING)],
                unique=True,
                sparse=True,
                name="idx_funcionario_id_unico"
            )
            
            # Índices para buscas frequentes
            self.colecao.create_index([("nome", ASCENDING)], name="idx_nome")
            self.colecao.create_index([("empresa", ASCENDING)], name="idx_empresa")
            self.colecao.create_index([("local_contrato_polo", ASCENDING)], name="idx_local")
            self.colecao.create_index([("email", ASCENDING)], name="idx_email")
            self.colecao.create_index([("telefone", ASCENDING)], name="idx_telefone")
            
            logger.debug("✓ Índices criados para contatos_folha_ponto")
        except Exception as e:
            logger.warning(f"Erro ao criar índices: {e}")
    
    def _validar_email(self, email: str) -> bool:
        """
        Valida formato de email.
        
        Args:
            email: Email para validar
            
        Returns:
            True se válido, False caso contrário
        """
        if not email:
            return True  # Email é opcional
        
        # Aceitar múltiplos emails separados por vírgula
        emails = [e.strip() for e in email.split(",") if e.strip()]
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        for e in emails:
            if not re.match(pattern, e):
                return False
        return True
    
    def _validar_telefone(self, telefone: str) -> bool:
        """
        Valida formato de telefone.
        
        Args:
            telefone: Telefone para validar
            
        Returns:
            True se válido, False caso contrário
        """
        if not telefone:
            return True  # Telefone é opcional
        
        # Aceitar múltiplos telefones separados por vírgula
        telefones = [t.strip() for t in telefone.split(",") if t.strip()]
        
        # Padrão: +5511999999999 ou 11999999999
        pattern = r'^\+?\d{10,13}$'
        for t in telefones:
            if not re.match(pattern, t.replace(" ", "").replace("-", "")):
                return False
        return True
    
    def _validar_documento(self, doc: Dict[str, Any], is_update: bool = False) -> tuple[bool, str]:
        """
        Valida documento antes de salvar.
        
        Args:
            doc: Documento para validar
            is_update: Se é atualização (campos obrigatórios menores)
            
        Returns:
            Tuple (is_valid, error_message)
        """
        # Campos obrigatórios na criação
        if not is_update:
            if not doc.get("nome", "").strip():
                return False, "Nome é obrigatório"
            if not doc.get("funcionario_id", "").strip():
                return False, "ID do funcionário é obrigatório"
        
        # Validar email
        if not self._validar_email(doc.get("email", "")):
            return False, f"Email inválido: {doc.get('email')}"
        
        # Validar telefone
        if not self._validar_telefone(doc.get("telefone", "")):
            return False, f"Telefone inválido: {doc.get('telefone')}"
        
        # Validar campos booleanos
        campos_booleanos = ["enviar_email", "enviar_whatsapp", "enviar_grupo_whatsapp", "enviar_impresso"]
        for campo in campos_booleanos:
            if campo in doc and not isinstance(doc[campo], bool):
                return False, f"Campo {campo} deve ser booleano"
        
        return True, ""
    
    def criar(self, doc: Dict[str, Any]) -> Optional[str]:
        """
        Cria um novo contato.
        
        Args:
            doc: Documento com dados do contato
            
        Returns:
            ID do contato criado ou None se erro
        """
        if not self._disponivel:
            logger.error("MongoDB indisponível")
            return None
        
        # Validar documento
        is_valid, error_msg = self._validar_documento(doc)
        if not is_valid:
            logger.error(f"Validação falhou: {error_msg}")
            return None
        
        try:
            # Preparar documento
            doc_para_salvar = doc.copy()
            
            # Normalizar strings
            for key in ["nome", "email", "telefone", "grupo_whatsapp", "empresa", 
                        "local_contrato_polo", "diretorio_geral", "diretorio_especifico", 
                        "funcionario_id"]:
                if key in doc_para_salvar and isinstance(doc_para_salvar[key], str):
                    doc_para_salvar[key] = doc_para_salvar[key].strip()
            
            # Definir timestamps
            agora = datetime.now(timezone.utc)
            doc_para_salvar["criado_em"] = agora
            doc_para_salvar["atualizado_em"] = agora
            
            # Inserir documento
            resultado = self.colecao.insert_one(doc_para_salvar)
            
            contato_id = str(resultado.inserted_id)
            logger.info(f"✓ Contato criado: {contato_id} - {doc.get('nome')}")
            
            return contato_id
            
        except Exception as e:
            logger.error(f"Erro ao criar contato: {e}")
            return None
    
    def buscar_por_id(self, contato_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca contato por ID.
        
        Args:
            contato_id: ID do contato (ObjectId)
            
        Returns:
            Documento do contato ou None
        """
        if not self._disponivel:
            return None
        
        try:
            # Converter para ObjectId
            oid = ObjectId(contato_id)
            
            contato = self.colecao.find_one({"_id": oid})
            
            if contato:
                contato["_id"] = str(contato["_id"])
                return contato
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao buscar contato por ID: {e}")
            return None
    
    def buscar_por_funcionario_id(self, funcionario_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca contato por funcionario_id.
        
        Args:
            funcionario_id: ID do funcionário na planilha
            
        Returns:
            Documento do contato ou None
        """
        if not self._disponivel:
            return None
        
        try:
            contato = self.colecao.find_one({"funcionario_id": funcionario_id})
            
            if contato:
                contato["_id"] = str(contato["_id"])
                return contato
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao buscar contato por funcionario_id: {e}")
            return None
    
    def buscar_por_nome(self, nome: str, exato: bool = False) -> List[Dict[str, Any]]:
        """
        Busca contatos por nome.
        
        Args:
            nome: Nome para busca
            exato: Se True, busca exata; se False, busca parcial
            
        Returns:
            Lista de contatos encontrados
        """
        if not self._disponivel:
            return []
        
        try:
            if exato:
                filtro = {"nome": {"$regex": f"^{re.escape(nome)}$", "$options": "i"}}
            else:
                filtro = {"nome": {"$regex": re.escape(nome), "$options": "i"}}
            
            contatos = list(self.colecao.find(filtro).sort("nome", ASCENDING))
            
            # Converter ObjectId para string
            for contato in contatos:
                contato["_id"] = str(contato["_id"])
            
            return contatos
            
        except Exception as e:
            logger.error(f"Erro ao buscar contatos por nome: {e}")
            return []
    
    def buscar_por_empresa(self, empresa: str) -> List[Dict[str, Any]]:
        """
        Busca contatos por empresa.
        
        Args:
            empresa: Nome da empresa
            
        Returns:
            Lista de contatos da empresa
        """
        if not self._disponivel:
            return []
        
        try:
            contatos = list(self.colecao.find({
                "empresa": {"$regex": re.escape(empresa), "$options": "i"}
            }).sort("nome", ASCENDING))
            
            for contato in contatos:
                contato["_id"] = str(contato["_id"])
            
            return contatos
            
        except Exception as e:
            logger.error(f"Erro ao buscar contatos por empresa: {e}")
            return []
    
    def buscar_por_email(self, email: str) -> List[Dict[str, Any]]:
        """
        Busca contatos por email.
        
        Args:
            email: Email para busca
            
        Returns:
            Lista de contatos com o email
        """
        if not self._disponivel:
            return []
        
        try:
            contatos = list(self.colecao.find({
                "email": {"$regex": re.escape(email), "$options": "i"}
            }).sort("nome", ASCENDING))
            
            for contato in contatos:
                contato["_id"] = str(contato["_id"])
            
            return contatos
            
        except Exception as e:
            logger.error(f"Erro ao buscar contatos por email: {e}")
            return []
    
    def buscar_por_telefone(self, telefone: str) -> List[Dict[str, Any]]:
        """
        Busca contatos por telefone.
        
        Args:
            telefone: Telefone para busca
            
        Returns:
            Lista de contatos com o telefone
        """
        if not self._disponivel:
            return []
        
        try:
            contatos = list(self.colecao.find({
                "telefone": {"$regex": re.escape(telefone), "$options": "i"}
            }).sort("nome", ASCENDING))
            
            for contato in contatos:
                contato["_id"] = str(contato["_id"])
            
            return contatos
            
        except Exception as e:
            logger.error(f"Erro ao buscar contatos por telefone: {e}")
            return []
    
    def listar_todos(self, skip: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Lista todos os contatos com paginação.
        
        Args:
            skip: Quantidade de registros para pular
            limit: Limite de registros por página
            
        Returns:
            Lista de contatos
        """
        if not self._disponivel:
            return []
        
        try:
            contatos = list(
                self.colecao.find({})
                .sort("nome", ASCENDING)
                .skip(skip)
                .limit(limit)
            )
            
            for contato in contatos:
                contato["_id"] = str(contato["_id"])
            
            return contatos
            
        except Exception as e:
            logger.error(f"Erro ao listar contatos: {e}")
            return []
    
    def listar_por_empresa(self, empresa: str, skip: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Lista contatos por empresa com paginação.
        
        Args:
            empresa: Nome da empresa
            skip: Quantidade de registros para pular
            limit: Limite de registros por página
            
        Returns:
            Lista de contatos da empresa
        """
        if not self._disponivel:
            return []
        
        try:
            contatos = list(
                self.colecao.find({
                    "empresa": {"$regex": re.escape(empresa), "$options": "i"}
                })
                .sort("nome", ASCENDING)
                .skip(skip)
                .limit(limit)
            )
            
            for contato in contatos:
                contato["_id"] = str(contato["_id"])
            
            return contatos
            
        except Exception as e:
            logger.error(f"Erro ao listar contatos por empresa: {e}")
            return []
    
    def listar_por_local(self, local: str, skip: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Lista contatos por local/contrato/polo com paginação.
        
        Args:
            local: Local/contrato/polo
            skip: Quantidade de registros para pular
            limit: Limite de registros por página
            
        Returns:
            Lista de contatos do local
        """
        if not self._disponivel:
            return []
        
        try:
            contatos = list(
                self.colecao.find({
                    "local_contrato_polo": {"$regex": re.escape(local), "$options": "i"}
                })
                .sort("nome", ASCENDING)
                .skip(skip)
                .limit(limit)
            )
            
            for contato in contatos:
                contato["_id"] = str(contato["_id"])
            
            return contatos
            
        except Exception as e:
            logger.error(f"Erro ao listar contatos por local: {e}")
            return []
    
    def listar_por_envio(self, tipo_envio: str, skip: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Lista contatos por tipo de envio ativo.
        
        Args:
            tipo_envio: Tipo de envio (email, whatsapp, grupo_whatsapp, impresso)
            skip: Quantidade de registros para pular
            limit: Limite de registros por página
            
        Returns:
            Lista de contatos com o tipo de envio ativo
        """
        if not self._disponivel:
            return []
        
        try:
            campo_envio = f"enviar_{tipo_envio}"
            contatos = list(
                self.colecao.find({
                    campo_envio: True
                })
                .sort("nome", ASCENDING)
                .skip(skip)
                .limit(limit)
            )
            
            for contato in contatos:
                contato["_id"] = str(contato["_id"])
            
            return contatos
            
        except Exception as e:
            logger.error(f"Erro ao listar contatos por envio: {e}")
            return []
    
    def atualizar(self, contato_id: str, doc: Dict[str, Any]) -> bool:
        """
        Atualiza um contato existente.
        
        Args:
            contato_id: ID do contato (ObjectId)
            doc: Campos para atualizar
            
        Returns:
            True se atualizado, False caso contrário
        """
        if not self._disponivel:
            return False
        
        # Validar documento (is_update=True para campos obrigatórios menores)
        is_valid, error_msg = self._validar_documento(doc, is_update=True)
        if not is_valid:
            logger.error(f"Validação falhou: {error_msg}")
            return False
        
        try:
            # Converter para ObjectId
            oid = ObjectId(contato_id)
            
            # Normalizar strings
            doc_para_atualizar = {}
            for key, value in doc.items():
                if isinstance(value, str):
                    doc_para_atualizar[key] = value.strip()
                else:
                    doc_para_atualizar[key] = value
            
            # Adicionar timestamp de atualização
            doc_para_atualizar["atualizado_em"] = datetime.now(timezone.utc)
            
            # Atualizar documento
            resultado = self.colecao.update_one(
                {"_id": oid},
                {"$set": doc_para_atualizar}
            )
            
            if resultado.modified_count > 0:
                logger.info(f"✓ Contato atualizado: {contato_id}")
                return True
            else:
                logger.warning(f"Nenhum contato encontrado com ID: {contato_id}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao atualizar contato: {e}")
            return False
    
    def excluir(self, contato_id: str) -> bool:
        """
        Exclui um contato.
        
        Args:
            contato_id: ID do contato (ObjectId)
            
        Returns:
            True se excluído, False caso contrário
        """
        if not self._disponivel:
            return False
        
        try:
            # Converter para ObjectId
            oid = ObjectId(contato_id)
            
            # Excluir documento
            resultado = self.colecao.delete_one({"_id": oid})
            
            if resultado.deleted_count > 0:
                logger.info(f"✓ Contato excluído: {contato_id}")
                return True
            else:
                logger.warning(f"Nenhum contato encontrado com ID: {contato_id}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao excluir contato: {e}")
            return False
    
    def contar(self) -> int:
        """
        Conta total de contatos.
        
        Returns:
            Quantidade total de contatos
        """
        if not self._disponivel:
            return 0
        
        try:
            return self.colecao.count_documents({})
        except Exception as e:
            logger.error(f"Erro ao contar contatos: {e}")
            return 0
    
    def contar_por_empresa(self, empresa: str) -> int:
        """
        Conta contatos por empresa.
        
        Args:
            empresa: Nome da empresa
            
        Returns:
            Quantidade de contatos da empresa
        """
        if not self._disponivel:
            return 0
        
        try:
            return self.colecao.count_documents({
                "empresa": {"$regex": re.escape(empresa), "$options": "i"}
            })
        except Exception as e:
            logger.error(f"Erro ao contar contatos por empresa: {e}")
            return 0
    
    def contar_por_local(self, local: str) -> int:
        """
        Conta contatos por local.
        
        Args:
            local: Local/contrato/polo
            
        Returns:
            Quantidade de contatos do local
        """
        if not self._disponivel:
            return 0
        
        try:
            return self.colecao.count_documents({
                "local_contrato_polo": {"$regex": re.escape(local), "$options": "i"}
            })
        except Exception as e:
            logger.error(f"Erro ao contar contatos por local: {e}")
            return 0
    
    def estatisticas(self) -> Dict[str, Any]:
        """
        Gera estatísticas dos contatos.
        
        Returns:
            Dicionário com estatísticas
        """
        if not self._disponivel:
            return {}
        
        try:
            # Total geral
            total = self.contar()
            
            # Contagem por empresa
            pipeline_empresas = [
                {"$group": {"_id": "$empresa", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            empresas = list(self.colecao.aggregate(pipeline_empresas))
            
            # Contagem por local
            pipeline_locais = [
                {"$group": {"_id": "$local_contrato_polo", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            locais = list(self.colecao.aggregate(pipeline_locais))
            
            # Contagem por tipo de envio
            envio_email = self.colecao.count_documents({"enviar_email": True})
            envio_whatsapp = self.colecao.count_documents({"enviar_whatsapp": True})
            envio_grupo = self.colecao.count_documents({"enviar_grupo_whatsapp": True})
            envio_impresso = self.colecao.count_documents({"enviar_impresso": True})
            
            return {
                "total": total,
                "por_empresa": [{"empresa": e["_id"], "count": e["count"]} for e in empresas],
                "por_local": [{"local": l["_id"], "count": l["count"]} for l in locais],
                "por_envio": {
                    "email": envio_email,
                    "whatsapp": envio_whatsapp,
                    "grupo_whatsapp": envio_grupo,
                    "impresso": envio_impresso
                }
            }
            
        except Exception as e:
            logger.error(f"Erro ao gerar estatísticas: {e}")
            return {}
    
    def importar_de_planilha(self, contatos: List[Dict[str, Any]]) -> int:
        """
        Importa contatos de uma lista (vinda de planilha Excel).
        
        Args:
            contatos: Lista de contatos para importar
            
        Returns:
            Quantidade de contatos importados
        """
        if not self._disponivel:
            return 0
        
        importados = 0
        
        for contato in contatos:
            try:
                # Verificar se já existe pelo funcionario_id
                funcionario_id = contato.get("funcionario_id", "")
                if funcionario_id:
                    existente = self.buscar_por_funcionario_id(funcionario_id)
                    if existente:
                        # Atualizar existente
                        self.atualizar(existente["_id"], contato)
                        importados += 1
                        continue
                
                # Criar novo contato
                resultado = self.criar(contato)
                if resultado:
                    importados += 1
                    
            except Exception as e:
                logger.error(f"Erro ao importar contato: {e}")
                continue
        
        logger.info(f"✓ Importados {importados} contatos")
        return importados
    
    def exportar_para_lista(self) -> List[Dict[str, Any]]:
        """
        Exporta todos os contatos para uma lista.
        
        Returns:
            Lista de contatos
        """
        if not self._disponivel:
            return []
        
        try:
            contatos = list(self.colecao.find({}).sort("nome", ASCENDING))
            
            # Converter ObjectId para string e remover _id
            for contato in contatos:
                contato.pop("_id", None)
            
            return contatos
            
        except Exception as e:
            logger.error(f"Erro ao exportar contatos: {e}")
            return []


# Instância singleton
contatos_folha_ponto_service = ContatosFolhaPontoService()
