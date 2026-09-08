"""
Serviço de Contatos de Funcionários em MongoDB
Gerencia múltiplos contatos por funcionário (telefones, emails)
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import dotenv

from src.utils.dotenv_path import caminho_dotenv
from src.services.mongodb_connection import MongoDBConnectionPool, retry_mongodb, medir_tempo
from src.models.contato_funcionario_models import (
    ContatoFuncionarioMongoDB,
    TipoContato,
    StatusContato,
    OrigemContato
)
from src.utils.logger_config_v2 import get_logger

logger = get_logger("contato")

try:
    from pymongo import ASCENDING, DESCENDING
    from pymongo.errors import DuplicateKeyError
    from bson import ObjectId
    MONGODB_DISPONIVEL = True
except ImportError:
    MONGODB_DISPONIVEL = False
    logger.warning("PyMongo não instalado.")


class ContatoFuncionarioService:
    """
    Gerencia contatos de funcionários em MongoDB.
    Permite múltiplos contatos por funcionário com diferentes tipos.
    Usa MongoDBConnectionPool para evitar múltiplas conexões.
    """

    def __init__(self, collection_name: str = "contatos_funcionarios"):

        self.logger = get_logger("contato")
        """
        Inicializa serviço de contatos usando pool centralizado.

        Args:
            collection_name: Nome da coleção
        """
        # Armazenar informações do .env para referência
        self.mongo_uri = dotenv.get_key(caminho_dotenv(), "MONGO_URI") or "mongodb://localhost:27017"
        self.db_name = dotenv.get_key(caminho_dotenv(), "MONGO_DATABASE_NAME") or "MS_Automatizar"
        self.collection_name = collection_name

        if not MONGODB_DISPONIVEL:
            logger.error("MongoDB não disponível para Contatos")
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
            logger.debug(f"✓ ContatoFuncionarioService inicializado (usando pool centralizado)")
        
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"✗ Erro ao conectar MongoDB (Contatos): {e}")
            self.cliente = None
            self.db = None
            self.colecao = None
            self._disponivel = False
    
    @property
    def disponivel(self) -> bool:
        """Verifica se MongoDB está disponível"""
        return self._disponivel
    
    def _criar_indices(self) -> None:
        """Cria índices para melhor performance."""
        try:
            # Índice composto único: funcionário + tipo + valor normalizado
            # Um funcionário não pode ter o mesmo contato duplicado
            self.colecao.create_index(
                [
                    ("funcionario_id", ASCENDING),
                    ("tipo", ASCENDING),
                    ("valor_normalizado", ASCENDING)
                ],
                unique=True,
                name="idx_contato_unico"
            )
            
            # Índice por funcionário
            self.colecao.create_index(
                [("funcionario_id", ASCENDING)],
                name="idx_funcionario"
            )
            
            # Índice por documento do funcionário
            self.colecao.create_index(
                [("funcionario_documento", ASCENDING)],
                name="idx_documento"
            )
            
            # Índice por tipo de contato
            self.colecao.create_index(
                [("tipo", ASCENDING)],
                name="idx_tipo"
            )
            
            # Índice por status
            self.colecao.create_index(
                [("status", ASCENDING)],
                name="idx_status"
            )
            
            # Índice para busca de contatos preferenciais ativos
            self.colecao.create_index(
                [
                    ("funcionario_id", ASCENDING),
                    ("preferencial", DESCENDING),
                    ("status", ASCENDING)
                ],
                name="idx_preferencial_ativo"
            )
            
            logger.debug("✓ Índices criados para Contatos em MongoDB")
        except Exception as e:
            logger.warning(f"Erro ao criar índices de contatos: {e}")
    
    def criar_contato(self, contato: Dict[str, Any]) -> Optional[ObjectId]:
        """
        Cria um novo contato.
        
        Args:
            contato: Dicionário com dados do contato (ou modelo Pydantic)
        
        Returns:
            ObjectId do contato criado ou None se erro/duplicata
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para criar contato")
            return None
        
        try:
            # Se for objeto Pydantic, converter
            if hasattr(contato, 'model_dump'):
                doc = contato.model_dump()
            elif hasattr(contato, 'dict'):
                doc = contato.dict()
            else:
                doc = contato.copy()
            
            # Remover _id se existir
            doc.pop('_id', None)
            
            # Garantir campos de controle
            if 'criado_em' not in doc:
                doc['criado_em'] = datetime.now(timezone.utc)
            if 'atualizado_em' not in doc:
                doc['atualizado_em'] = datetime.now(timezone.utc)
            
            resultado = self.colecao.insert_one(doc)

            
            if resultado and resultado.inserted_id:

            
                self.logger.audit(

            
                    action="REGISTRO_CRIADO",

            
                    target=f"{self.collection_name}:{resultado.inserted_id}",

            
                    changes={'dados': str(doc)[:200]}

            
                )
            if resultado.inserted_id:
                logger.debug(f"✓ Contato criado: {resultado.inserted_id}")
                return resultado.inserted_id
            
            return None
            
        except DuplicateKeyError:
            logger.debug("Contato já existe (duplicata ignorada)")
            return None
        except Exception as e:
            logger.error(f"Erro ao criar contato: {e}")
            return None
    
    def criar_ou_atualizar(self, contato: Dict[str, Any]) -> Optional[ObjectId]:
        """
        Cria novo contato ou atualiza se já existir.
        
        Args:
            contato: Dicionário com dados do contato
        
        Returns:
            ObjectId do contato
        """
        if not self.disponivel:
            return None
        
        try:
            # Se for objeto Pydantic, converter
            if hasattr(contato, 'model_dump'):
                doc = contato.model_dump()
            elif hasattr(contato, 'dict'):
                doc = contato.dict()
            else:
                doc = contato.copy()
            
            doc.pop('_id', None)
            doc['atualizado_em'] = datetime.now(timezone.utc)
            
            # Filtro para buscar existente
            filtro = {
                "funcionario_id": doc.get("funcionario_id"),
                "tipo": doc.get("tipo"),
                "valor_normalizado": doc.get("valor_normalizado")
            }
            
            resultado = self.colecao.find_one_and_update(
                filtro,
                {"$set": doc, "$setOnInsert": {"criado_em": datetime.now(timezone.utc)}},
                upsert=True,
                return_document=True
            )
            if resultado:
                return resultado['_id']
            return None
            
        except Exception as e:
            logger.error(f"Erro ao criar/atualizar contato: {e}")
            return None
    
    def buscar_por_funcionario(
        self, 
        funcionario_id: str,
        tipo: TipoContato = None,
        apenas_ativos: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Busca contatos de um funcionário.
        
        Args:
            funcionario_id: ObjectId do funcionário
            tipo: Filtrar por tipo (opcional)
            apenas_ativos: Se True, retorna apenas contatos ativos
        
        Returns:
            Lista de contatos ordenados (preferenciais primeiro)
        """
        if not self.disponivel:
            return []
        
        try:
            filtro = {"funcionario_id": ObjectId(funcionario_id)}
            
            if tipo:
                filtro["tipo"] = tipo.value if hasattr(tipo, 'value') else tipo
            
            if apenas_ativos:
                filtro["status"] = StatusContato.ATIVO.value
            
            cursor = self.colecao.find(filtro).sort([
                ("preferencial", DESCENDING),
                ("criado_em", ASCENDING)
            ])
            
            return list(cursor)
        except Exception as e:
            logger.error(f"Erro ao buscar contatos por funcionário: {e}")
            return []
    
    def buscar_por_documento(
        self, 
        documento: str,
        tipo: TipoContato = None,
        apenas_ativos: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Busca contatos por documento (CPF) do funcionário.
        
        Args:
            documento: CPF do funcionário
            tipo: Filtrar por tipo (opcional)
            apenas_ativos: Se True, retorna apenas contatos ativos
        
        Returns:
            Lista de contatos
        """
        if not self.disponivel:
            return []
        
        try:
            doc_normalizado = documento.replace(".", "").replace("-", "").strip()
            
            filtro = {"funcionario_documento": doc_normalizado}
            
            if tipo:
                filtro["tipo"] = tipo.value if hasattr(tipo, 'value') else tipo
            
            if apenas_ativos:
                filtro["status"] = StatusContato.ATIVO.value
            
            cursor = self.colecao.find(filtro).sort([
                ("preferencial", DESCENDING),
                ("criado_em", ASCENDING)
            ])
            
            return list(cursor)
        except Exception as e:
            logger.error(f"Erro ao buscar contatos por documento: {e}")
            return []
    
    def obter_contato_preferencial(
        self, 
        funcionario_id: str,
        tipo: TipoContato
    ) -> Optional[Dict[str, Any]]:
        """
        Obtém o contato preferencial de um tipo para um funcionário.
        
        Args:
            funcionario_id: ObjectId do funcionário
            tipo: Tipo do contato (celular, email, etc.)
        
        Returns:
            Contato preferencial ou primeiro disponível
        """
        contatos = self.buscar_por_funcionario(funcionario_id, tipo, apenas_ativos=True)
        
        if not contatos:
            return None
        
        # Primeiro tenta encontrar o marcado como preferencial
        for contato in contatos:
            if contato.get("preferencial"):
                return contato
        
        # Se não há preferencial, retorna o primeiro
        return contatos[0]
    
    def obter_whatsapp_funcionario(self, funcionario_id: str) -> Optional[str]:
        """
        Obtém número de WhatsApp do funcionário.
        
        Args:
            funcionario_id: ObjectId do funcionário
        
        Returns:
            Número de telefone formatado ou None
        """
        # Primeiro tenta WhatsApp confirmado
        contato = self.obter_contato_preferencial(funcionario_id, TipoContato.WHATSAPP)
        if contato:
            return contato.get("valor")
        
        # Depois tenta celular que aceita WhatsApp
        contatos_celular = self.buscar_por_funcionario(
            funcionario_id, TipoContato.CELULAR, apenas_ativos=True
        )
        
        for contato in contatos_celular:
            if contato.get("aceita_whatsapp"):
                return contato.get("valor")
        
        return None
    
    def obter_email_funcionario(self, funcionario_id: str) -> Optional[str]:
        """
        Obtém email do funcionário.
        
        Args:
            funcionario_id: ObjectId do funcionário
        
        Returns:
            Endereço de email ou None
        """
        # Primeiro tenta email pessoal
        contato = self.obter_contato_preferencial(funcionario_id, TipoContato.EMAIL_PESSOAL)
        if contato:
            return contato.get("valor")
        
        # Depois tenta email corporativo
        contato = self.obter_contato_preferencial(funcionario_id, TipoContato.EMAIL_CORPORATIVO)
        if contato:
            return contato.get("valor")
        
        return None
    
    def marcar_preferencial(
        self, 
        contato_id: str,
        funcionario_id: str,
        tipo: TipoContato
    ) -> bool:
        """
        Marca um contato como preferencial (e desmarca outros do mesmo tipo).
        
        Args:
            contato_id: ObjectId do contato a marcar
            funcionario_id: ObjectId do funcionário
            tipo: Tipo do contato
        
        Returns:
            True se sucesso
        """
        if not self.disponivel:
            return False
        
        try:
            tipo_valor = tipo.value if hasattr(tipo, 'value') else tipo
            
            # Desmarcar todos do mesmo tipo
            self.colecao.update_many(
                {
                    "funcionario_id": ObjectId(funcionario_id),
                    "tipo": tipo_valor
                },
                {"$set": {"preferencial": False, "atualizado_em": datetime.now(timezone.utc)}}
            )
            
            # Marcar o selecionado
            resultado = self.colecao.update_one(
                {"_id": ObjectId(contato_id)},
                {"$set": {"preferencial": True, "atualizado_em": datetime.now(timezone.utc)}}
            )
            
            if resultado and resultado.modified_count > 0:
                self.logger.audit(
                    action="REGISTRO_ATUALIZADO",
                    target=f"{self.collection_name}",
                    changes={'operacao': 'update'}
                )
            
            return resultado.modified_count > 0
        except Exception as e:
            logger.error(f"Erro ao marcar preferencial: {e}")
            return False
    
    def atualizar_status(
        self, 
        contato_id: str, 
        novo_status: StatusContato
    ) -> bool:
        """
        Atualiza o status de um contato.
        
        Args:
            contato_id: ObjectId do contato
            novo_status: Novo status
        
        Returns:
            True se atualizou
        """
        if not self.disponivel:
            return False
        
        try:
            resultado = self.colecao.update_one(
                {"_id": ObjectId(contato_id)},
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
            logger.error(f"Erro ao atualizar status: {e}")
            return False
    
    def registrar_envio(
        self, 
        contato_id: str, 
        sucesso: bool
    ) -> bool:
        """
        Registra uma tentativa de envio para o contato.
        
        Args:
            contato_id: ObjectId do contato
            sucesso: Se o envio foi bem-sucedido
        
        Returns:
            True se registrou
        """
        if not self.disponivel:
            return False
        
        try:
            update = {
                "$set": {"atualizado_em": datetime.now(timezone.utc)}
            }
            
            if sucesso:
                update["$set"]["ultimo_envio"] = datetime.now(timezone.utc)
                update["$inc"] = {"total_envios": 1}
            else:
                update["$inc"] = {"total_falhas": 1}
            
            resultado = self.colecao.update_one(
                {"_id": ObjectId(contato_id)},
                update
            )
            
            if resultado and resultado.modified_count > 0:
                self.logger.audit(
                    action="REGISTRO_ATUALIZADO",
                    target=f"{self.collection_name}",
                    changes={'operacao': 'update'}
                )
            return resultado.modified_count > 0
        except Exception as e:
            logger.error(f"Erro ao registrar envio: {e}")
            return False
    
    def remover_contato(self, contato_id: str) -> bool:
        """
        Remove um contato.
        
        Args:
            contato_id: ObjectId do contato
        
        Returns:
            True se removeu
        """
        if not self.disponivel:
            return False
        
        try:
            resultado = self.colecao.delete_one({"_id": ObjectId(contato_id)})
            return resultado.deleted_count > 0
        except Exception as e:
            logger.error(f"Erro ao remover contato: {e}")
            return False
    
    def contar_contatos_funcionario(self, funcionario_id: str) -> int:
        """
        Conta total de contatos de um funcionário.
        
        Args:
            funcionario_id: ObjectId do funcionário
        
        Returns:
            Total de contatos
        """
        if not self.disponivel:
            return 0
        
        try:
            return self.colecao.count_documents({
                "funcionario_id": ObjectId(funcionario_id)
            })
        except Exception as e:
            logger.error(f"Erro ao contar contatos: {e}")
            return 0
    
    def obter_contatos_batch(self, funcionario_ids: List[str]) -> Dict[str, Dict[str, Optional[str]]]:
        """
        Busca contatos (email e whatsapp) de múltiplos funcionários em uma única query.
        
        OTIMIZADO: Substitui N queries individuais por 1 aggregation pipeline.
        Uso típico: Pré-carregar contatos antes de loop de envio de holerites.
        
        Args:
            funcionario_ids: Lista de IDs de funcionários (strings)
        
        Returns:
            Dict com estrutura:
            {
                "funcionario_id_1": {"email": "email@example.com", "whatsapp": "+5511999999999"},
                "funcionario_id_2": {"email": "outro@example.com", "whatsapp": None},
                ...
            }
        
        Example:
            >>> service = ContatoFuncionarioService()
            >>> func_ids = ["507f1f77bcf86cd799439011", "507f191e810c19729de860ea"]
            >>> contatos = service.obter_contatos_batch(func_ids)
            >>> 
            >>> # Uso em loop de envio
            >>> for holerite in holerites:
            >>>     func_id = str(holerite.funcionario_id)
            >>>     email = contatos.get(func_id, {}).get("email")
            >>>     whatsapp = contatos.get(func_id, {}).get("whatsapp")
            >>>     if email:
            >>>         enviar_email(email, holerite)
        
        Performance:
            - ANTES: N funcionários = N × 2 queries (obter_email + obter_whatsapp)
            - DEPOIS: N funcionários = 1 aggregation query
            - Ganho: 1000 funcionários = 2000 queries → 1 query (99.95% redução)
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível para busca batch")
            return {}
        
        try:
            # Converter strings para ObjectId
            try:
                obj_ids = [ObjectId(fid) for fid in funcionario_ids]
            except Exception as e:
                logger.error(f"Erro ao converter IDs para ObjectId: {e}")
                return {}
            
            # Aggregation Pipeline para buscar contatos de todos funcionários
            pipeline = [
                # Stage 1: Filtrar apenas os funcionários da lista
                {
                    "$match": {
                        "funcionario_id": {"$in": obj_ids},
                        "status": StatusContato.ATIVO.value
                    }
                },
                # Stage 2: Agrupar por funcionário e coletar emails/whatsapps
                {
                    "$group": {
                        "_id": "$funcionario_id",
                        "emails": {
                            "$push": {
                                "$cond": [
                                    {
                                        "$in": [
                                            "$tipo",
                                            [TipoContato.EMAIL_PESSOAL.value, TipoContato.EMAIL_CORPORATIVO.value]
                                        ]
                                    },
                                    {
                                        "valor": "$valor",
                                        "preferencial": "$preferencial",
                                        "tipo": "$tipo"
                                    },
                                    None
                                ]
                            }
                        },
                        "whatsapps": {
                            "$push": {
                                "$cond": [
                                    {"$eq": ["$tipo", TipoContato.WHATSAPP.value]},
                                    {
                                        "valor": "$valor",
                                        "preferencial": "$preferencial"
                                    },
                                    None
                                ]
                            }
                        },
                        "celulares": {
                            "$push": {
                                "$cond": [
                                    {"$eq": ["$tipo", TipoContato.CELULAR.value]},
                                    {
                                        "valor": "$valor",
                                        "preferencial": "$preferencial",
                                        "whatsapp": "$whatsapp"
                                    },
                                    None
                                ]
                            }
                        }
                    }
                },
                # Stage 3: Processar arrays para extrair melhor contato
                {
                    "$project": {
                        "funcionario_id": "$_id",
                        # Filtrar nulls dos emails e pegar o primeiro preferencial ou primeiro disponível
                        "email": {
                            "$let": {
                                "vars": {
                                    "emails_validos": {
                                        "$filter": {
                                            "input": "$emails",
                                            "cond": {"$ne": ["$$this", None]}
                                        }
                                    }
                                },
                                "in": {
                                    "$cond": [
                                        {"$gt": [{"$size": "$$emails_validos"}, 0]},
                                        {
                                            "$let": {
                                                "vars": {
                                                    "preferencial": {
                                                        "$arrayElemAt": [
                                                            {
                                                                "$filter": {
                                                                    "input": "$$emails_validos",
                                                                    "cond": {"$eq": ["$$this.preferencial", True]}
                                                                }
                                                            },
                                                            0
                                                        ]
                                                    }
                                                },
                                                "in": {
                                                    "$cond": [
                                                        {"$ne": ["$$preferencial", None]},
                                                        "$$preferencial.valor",
                                                        {"$arrayElemAt": ["$$emails_validos.valor", 0]}
                                                    ]
                                                }
                                            }
                                        },
                                        None
                                    ]
                                }
                            }
                        },
                        # Processar whatsapp: preferir tipo WHATSAPP, depois CELULAR com flag whatsapp
                        "whatsapp": {
                            "$let": {
                                "vars": {
                                    "whatsapps_validos": {
                                        "$filter": {
                                            "input": "$whatsapps",
                                            "cond": {"$ne": ["$$this", None]}
                                        }
                                    },
                                    "celulares_whatsapp": {
                                        "$filter": {
                                            "input": "$celulares",
                                            "cond": {
                                                "$and": [
                                                    {"$ne": ["$$this", None]},
                                                    {"$eq": ["$$this.whatsapp", True]}
                                                ]
                                            }
                                        }
                                    }
                                },
                                "in": {
                                    "$cond": [
                                        {"$gt": [{"$size": "$$whatsapps_validos"}, 0]},
                                        # Tem whatsapp direto
                                        {
                                            "$let": {
                                                "vars": {
                                                    "preferencial": {
                                                        "$arrayElemAt": [
                                                            {
                                                                "$filter": {
                                                                    "input": "$$whatsapps_validos",
                                                                    "cond": {"$eq": ["$$this.preferencial", True]}
                                                                }
                                                            },
                                                            0
                                                        ]
                                                    }
                                                },
                                                "in": {
                                                    "$cond": [
                                                        {"$ne": ["$$preferencial", None]},
                                                        "$$preferencial.valor",
                                                        {"$arrayElemAt": ["$$whatsapps_validos.valor", 0]}
                                                    ]
                                                }
                                            }
                                        },
                                        # Não tem whatsapp direto, tentar celular com flag
                                        {
                                            "$cond": [
                                                {"$gt": [{"$size": "$$celulares_whatsapp"}, 0]},
                                                {"$arrayElemAt": ["$$celulares_whatsapp.valor", 0]},
                                                None
                                            ]
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            ]
            
            # Executar aggregation
            resultado = list(self.colecao.aggregate(pipeline))
            
            # Validar resultado
            if not resultado:
                logger.warning(f"Pipeline de contatos batch retornou vazio para {len(funcionario_ids)} funcionário(s)")
            
            # Converter para dicionário de lookup
            contatos_dict = {}
            for doc in resultado:
                func_id_str = str(doc["funcionario_id"])
                contatos_dict[func_id_str] = {
                    "email": doc.get("email"),
                    "whatsapp": doc.get("whatsapp")
                }
            
            # Adicionar entradas vazias para funcionários sem contatos
            for func_id in funcionario_ids:
                if func_id not in contatos_dict:
                    contatos_dict[func_id] = {"email": None, "whatsapp": None}
            
            logger.info(
                f"✅ Contatos batch carregados: {len(contatos_dict)} funcionários " 
                f"({len([c for c in contatos_dict.values() if c['email']])} emails, "
                f"{len([c for c in contatos_dict.values() if c['whatsapp']])} whatsapps)"
            )
            
            return contatos_dict
        
        except Exception as e:
            logger.error(f"Erro ao buscar contatos em batch: {e}")
            logger.error(f"Pipeline usado: {pipeline if 'pipeline' in locals() else 'não construído'}")
            return {}


# Instância singleton
contato_funcionario_service = ContatoFuncionarioService()
