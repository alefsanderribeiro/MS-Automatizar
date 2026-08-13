"""
Service para Configuração de Envio de Folhas de Ponto em MongoDB

Responsabilidades:
- CRUD completo das configurações de envio (antiga planilha Excel)
- Soft delete (excluida=True) preservando histórico
- Importação da planilha Excel (migração 1x sem perda de dados)
- Consulta por funcionário/empresa/local
- Normalização de nome para busca
- Índices e pool centralizado MongoDBConnectionPool

Coleção: "configs_envio_folha_ponto"
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import dotenv

from src.utils.dotenv_path import caminho_dotenv
from src.utils.logger_config import logger
from src.models.config_envio_folha_ponto_models import (
    SimNaoEnum,
    OrigemConfigEnum,
    ConfigEnvioFolhaPontoMongoDB,
)
from src.services.planilha_contatos_service import planilha_contatos_service, PlanilhaContatosService
from src.services.historico_decorators import HistoricoMixin
from src.services.mongodb_connection import MongoDBConnectionPool

# Tentativa de importação do MongoDB
try:
    from pymongo import ASCENDING, DESCENDING
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    from bson.objectid import ObjectId
    MONGODB_DISPONIVEL = True
except ImportError:
    MONGODB_DISPONIVEL = False
    logger.warning("PyMongo não instalado - ConfigEnvioFolhaPontoService ficará limitado")


class ConfigEnvioFolhaPontoService(HistoricoMixin):
    """
    Gerencia Configurações de Envio de Folhas de Ponto em MongoDB.

    Cada documento representa UMA linha da planilha de contatos (uma config
    de envio por funcionário). Os flags S/N (enviar_email, enviar_whatsapp,
    enviar_grupo_whatsapp, enviar_impresso) são preservados e editáveis.

    Coleção: "configs_envio_folha_ponto"
    """

    def __init__(self, mongo_uri: str = None,
                 db_name: str = None,
                 collection_name: str = "configs_envio_folha_ponto"):
        """
        Inicializa conexão com MongoDB para as Configurações de Envio.
        """
        mongo_uri = mongo_uri or dotenv.get_key(caminho_dotenv(), "MONGO_URI")
        db_name = db_name or dotenv.get_key(caminho_dotenv(), "MONGO_DATABASE_NAME")

        if not MONGODB_DISPONIVEL:
            logger.error("MongoDB não disponível para Configurações de Envio de Folha de Ponto")
            self.db = None
            self.colecao = None
            self.pool = None
            self._disponivel = False
            return

        try:
            self.mongo_uri = mongo_uri
            self.db_name = db_name
            self.collection_name = collection_name

            # Pool centralizado em vez de criar novo MongoClient
            self.pool = MongoDBConnectionPool()
            self.db = self.pool.get_database()

            if self.db is None:
                logger.error("Banco de dados não disponível no pool MongoDB")
                self.pool = None
                self.db = None
                self.colecao = None
                self._disponivel = False
                return

            self.colecao = self.db[collection_name]
            self._criar_indices()

            self._disponivel = True
            logger.debug(f"✓ MongoDB conectado para Config. Envio Folha Ponto (via pool): {db_name}.{collection_name}")

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

    # ==================== ÍNDICES ====================

    def _criar_indices(self) -> None:
        """Cria índices na coleção."""
        try:
            # Índice único para identificador não-excluído (evita duplicidade)
            self.colecao.create_index(
                [("identificador", ASCENDING)],
                name="idx_identificador",
            )
            self.colecao.create_index(
                [("nome_normalizado", ASCENDING)],
                name="idx_nome_normalizado",
            )
            self.colecao.create_index(
                [("empresa", ASCENDING)],
                name="idx_empresa",
            )
            self.colecao.create_index(
                [("local_contrato_polo", ASCENDING)],
                name="idx_local",
            )
            self.colecao.create_index(
                [("ativo", ASCENDING)],
                name="idx_ativo",
            )
            self.colecao.create_index(
                [("excluida", ASCENDING)],
                name="idx_excluida",
            )
            self.colecao.create_index(
                [("criado_em", DESCENDING)],
                name="idx_criado_em",
            )
            # Composto para busca ativas + excluídas
            self.colecao.create_index(
                [("ativo", ASCENDING), ("excluida", ASCENDING)],
                name="idx_ativo_excluida",
            )
            logger.debug("✓ Índices criados para Config. Envio Folha de Ponto")
        except Exception as e:
            logger.warning(f"Erro ao criar índices: {e}")

    # ==================== HELPERS ====================

    @staticmethod
    def _flag_para_valor(flag) -> str:
        """Converte qualquer valor de flag para 'S'/'N' canônico."""
        valores_sim = ("S", "SIM", "Y", "YES", "1", "TRUE", "X")
        if isinstance(flag, str) and flag.strip().upper() in valores_sim:
            return SimNaoEnum.SIM.value
        if flag is True or flag == 1:
            return SimNaoEnum.SIM.value
        return SimNaoEnum.NAO.value

    @staticmethod
    def _parsear_lista(valor) -> List[str]:
        """Parseia string separada por , ou ; em lista de strings limpas."""
        if not valor:
            return []
        texto = str(valor).strip()
        if not texto:
            return []
        separador = ";" if ";" in texto else ","
        return [item.strip() for item in texto.split(separador) if item.strip()]

    # ==================== CRUD ====================

    def criar(self, dados: Dict[str, Any]) -> Optional[str]:
        """
        Cria uma nova configuração de envio.

        Args:
            dados: Dados da config (campos do modelo). Strings de flag são
                   normalizadas para S/N automaticamente.

        Returns:
            ID do documento criado ou None em erro.
        """
        if not self._disponivel:
            return None

        try:
            # Normalizar flags S/N
            dados = dict(dados)
            for campo in ("enviar_email", "enviar_whatsapp", "enviar_grupo_whatsapp", "enviar_impresso"):
                if campo in dados:
                    dados[campo] = self._flag_para_valor(dados[campo])

            config = ConfigEnvioFolhaPontoMongoDB(**dados)
            doc = config.model_dump()

            resultado = self.colecao.insert_one(doc)
            logger.info(
                f"✓ Config de envio criada: {dados.get('nome', '')} "
                f"(ID: {resultado.inserted_id})"
            )
            return str(resultado.inserted_id)

        except Exception as e:
            logger.error(f"Erro ao criar config de envio: {e}")
            return None

    def buscar_por_id(self, config_id: str, incluir_excluidas: bool = False) -> Optional[Dict[str, Any]]:
        """Busca uma configuração por ID."""
        if not self._disponivel:
            return None

        try:
            filtro = {"_id": ObjectId(config_id)}
            if not incluir_excluidas:
                filtro["excluida"] = False
            return self.colecao.find_one(filtro)
        except Exception as e:
            logger.error(f"Erro ao buscar config por ID: {e}")
            return None

    def listar(self, apenas_ativas: bool = True, limit: int = 100, skip: int = 0,
               incluir_excluidas: bool = False) -> List[Dict[str, Any]]:
        """
        Lista configurações de envio com paginação.

        Args:
            apenas_ativas: Se True, retorna apenas ativas (padrão).
            limit: Limite de resultados.
            skip: Deslocamento (paginação).
            incluir_excluidas: Se True, inclui registros com soft delete.

        Returns:
            Lista de configurações.
        """
        if not self._disponivel:
            return []

        try:
            filtro: Dict[str, Any] = {}
            if not incluir_excluidas:
                filtro["excluida"] = False
            if apenas_ativas:
                filtro["ativo"] = True

            return list(
                self.colecao.find(filtro)
                .sort("nome_normalizado", ASCENDING)
                .skip(skip)
                .limit(limit)
            )
        except Exception as e:
            logger.error(f"Erro ao listar configs de envio: {e}")
            return []

    def atualizar(self, config_id: str, alteracoes: Dict[str, Any], origem: str = "interface_cli") -> bool:
        """
        Atualiza uma configuração registrando histórico (via HistoricoMixin).

        Args:
            config_id: ID do documento.
            alteracoes: Campos a atualizar (flags normalizados para S/N).
            origem: Origem da alteração (interface_cli, excel, api, etc).

        Returns:
            True se atualizado com sucesso.
        """
        if not self._disponivel:
            return False

        try:
            alteracoes = dict(alteracoes)
            for campo in ("enviar_email", "enviar_whatsapp", "enviar_grupo_whatsapp", "enviar_impresso"):
                if campo in alteracoes:
                    alteracoes[campo] = self._flag_para_valor(alteracoes[campo])

            # Validar contra o modelo (parcial)
            dados_validacao = self.buscar_por_id(config_id, incluir_excluidas=True) or {}
            dados_validacao.update(alteracoes)
            ConfigEnvioFolhaPontoMongoDB(**dados_validacao)

            return self.atualizar_com_historico(config_id, alteracoes, origem=origem)

        except Exception as e:
            logger.error(f"Erro ao atualizar config de envio: {e}")
            return False

    def excluir(self, config_id: str, origem: str = "interface_cli") -> bool:
        """
        Exclui (soft delete) uma configuração, preservando histórico.

        Args:
            config_id: ID do documento.
            origem: Origem da exclusão.

        Returns:
            True se excluído (logicamente) com sucesso.
        """
        if not self._disponivel:
            return False

        try:
            resultado = self.colecao.update_one(
                {"_id": ObjectId(config_id)},
                {
                    "$set": {
                        "excluida": True,
                        "excluida_em": datetime.now(timezone.utc),
                        "ativo": False,
                        "atualizado_em": datetime.now(timezone.utc),
                    },
                    "$inc": {"versao": 1},
                    "$push": {
                        "historico_alteracoes": {
                            "timestamp": datetime.now(timezone.utc),
                            "acao": "Configuração excluída (soft delete)",
                            "origem": origem,
                        }
                    },
                }
            )
            if resultado.modified_count > 0:
                logger.info(f"✓ Config de envio {config_id} excluída (soft delete)")
            return resultado.modified_count > 0
        except Exception as e:
            logger.error(f"Erro ao excluir config de envio: {e}")
            return False

    def reativar(self, config_id: str, origem: str = "interface_cli") -> bool:
        """
        Reativa uma configuração excluída (remove soft delete e ativa).

        Args:
            config_id: ID do documento.
            origem: Origem da reativação.

        Returns:
            True se reativado com sucesso.
        """
        if not self._disponivel:
            return False

        try:
            resultado = self.colecao.update_one(
                {"_id": ObjectId(config_id)},
                {
                    "$set": {
                        "excluida": False,
                        "excluida_em": None,
                        "ativo": True,
                        "atualizado_em": datetime.now(timezone.utc),
                    },
                    "$inc": {"versao": 1},
                    "$push": {
                        "historico_alteracoes": {
                            "timestamp": datetime.now(timezone.utc),
                            "acao": "Configuração reativada",
                            "origem": origem,
                        }
                    },
                }
            )
            if resultado.modified_count > 0:
                logger.info(f"✓ Config de envio {config_id} reativada")
            return resultado.modified_count > 0
        except Exception as e:
            logger.error(f"Erro ao reativar config de envio: {e}")
            return False

    # ==================== CONSULTAS ====================

    def buscar_por_nome(self, nome: str, exato: bool = False, incluir_inativas: bool = False) -> List[Dict[str, Any]]:
        """
        Busca configurações pelo nome do funcionário.

        Args:
            nome: Nome ou parte do nome.
            exato: Se True, busca por normalização exata; senão usa regex.
            incluir_inativas: Se True, inclui configs inativas.

        Returns:
            Lista de configurações encontradas.
        """
        if not self._disponivel:
            return []

        try:
            filtro: Dict[str, Any] = {"excluida": False}
            if not incluir_inativas:
                filtro["ativo"] = True

            normalizado = ConfigEnvioFolhaPontoMongoDB.normalizar_texto(nome)
            if exato:
                filtro["nome_normalizado"] = normalizado
            else:
                import re
                filtro["nome_normalizado"] = {"$regex": re.escape(normalizado), "$options": "i"}

            return list(self.colecao.find(filtro).sort("nome_normalizado", ASCENDING))
        except Exception as e:
            logger.error(f"Erro ao buscar config por nome: {e}")
            return []

    def buscar_por_identificador(self, identificador: str) -> Optional[Dict[str, Any]]:
        """Busca config pelo identificador (ID da planilha/linha)."""
        if not self._disponivel:
            return None

        try:
            return self.colecao.find_one(
                {"identificador": str(identificador), "excluida": False}
            )
        except Exception as e:
            logger.error(f"Erro ao buscar config por identificador: {e}")
            return None

    def buscar_por_empresa(self, empresa: str) -> List[Dict[str, Any]]:
        """Busca configs pela empresa (nome normalizado)."""
        if not self._disponivel:
            return []

        try:
            normalizado = ConfigEnvioFolhaPontoMongoDB.normalizar_texto(empresa)
            return list(self.colecao.find({
                "excluida": False,
                "ativo": True,
                "$or": [
                    {"empresa": {"$regex": normalizado, "$options": "i"}},
                ],
            }).sort("nome_normalizado", ASCENDING))
        except Exception as e:
            logger.error(f"Erro ao buscar config por empresa: {e}")
            return []

    def buscar_por_local(self, local_contrato_polo: str) -> List[Dict[str, Any]]:
        """Busca configs por Local/Contrato/Polo."""
        if not self._disponivel:
            return []

        try:
            return list(self.colecao.find({
                "excluida": False,
                "ativo": True,
                "local_contrato_polo": {"$regex": local_contrato_polo, "$options": "i"},
            }).sort("nome_normalizado", ASCENDING))
        except Exception as e:
            logger.error(f"Erro ao buscar config por local: {e}")
            return []

    def listar_ativos_para_envio(self, mes: int, ano: int) -> List[Dict[str, Any]]:
        """
        Lista configurações ativas para envio no formato esperado pelo
        orquestrador (dict de contato). Monta o diretório completo e lista
        os PDFs, replicando o comportamento de iterar_contatos() da planilha.

        Args:
            mes: Mês de referência.
            ano: Ano de referência.

        Returns:
            Lista de contatos prontos para envio.
        """
        if not self._disponivel:
            return []

        try:
            configs = self.listar(apenas_ativas=True, limit=100000)
            contatos = []
            for doc in configs:
                diretorio = planilha_contatos_service.montar_diretorio_completo(
                    doc.get("diretorio_geral", ""),
                    doc.get("diretorio_especifico", ""),
                    mes,
                    ano,
                )
                arquivos = planilha_contatos_service.listar_arquivos_pdf(diretorio)
                config = ConfigEnvioFolhaPontoMongoDB(**doc)
                contatos.append(config.to_dict_contato(
                    mes=mes,
                    ano=ano,
                    diretorio_completo=diretorio,
                    arquivos_pdf=arquivos,
                ))
            return contatos
        except Exception as e:
            logger.error(f"Erro ao listar configs para envio: {e}")
            return []

    # ==================== VALIDAÇÃO ====================

    def validar(self) -> Dict[str, Any]:
        """
        Valida as configurações no MongoDB e retorna relatório de problemas.

        Semelhante a planilha_contatos_service.validar_planilha(), mas opera
        sobre os documentos do Mongo.

        Returns:
            Dict com resultado da validação.
        """
        if not self._disponivel:
            return {"valida": False, "erro": "MongoDB não disponível"}

        problemas = []
        avisos = []
        total = 0

        try:
            configs = self.listar(apenas_ativas=False, limit=100000, incluir_excluidas=True)
            total = len(configs)

            for doc in configs:
                ident = doc.get("identificador", "?")
                if doc.get("excluida"):
                    continue

                enviar_email = self._flag_para_valor(doc.get("enviar_email")) == "S"
                enviar_whatsapp = self._flag_para_valor(doc.get("enviar_whatsapp")) == "S"
                enviar_grupo = self._flag_para_valor(doc.get("enviar_grupo_whatsapp")) == "S"

                if enviar_email and not doc.get("emails"):
                    problemas.append(f"{ident}: ENVIAR EMAIL = S mas sem EMAIL preenchido")

                if enviar_whatsapp and not doc.get("telefones"):
                    problemas.append(f"{ident}: ENVIAR WHATSAPP = S mas sem TELEFONE preenchido")

                if enviar_grupo and not doc.get("grupos_whatsapp"):
                    problemas.append(f"{ident}: ENVIAR GRUPO WHATSAPP = S mas sem GRUPO WHATSAPP preenchido")

                if any([enviar_email, enviar_whatsapp, enviar_grupo]):
                    if not doc.get("diretorio_geral", "").strip():
                        problemas.append(f"{ident}: Sem DIRETÓRIO GERAL preenchido")
                    if not doc.get("diretorio_especifico", "").strip():
                        avisos.append(f"{ident}: Sem DIRETÓRIO ESPECÍFICO preenchido")

            return {
                "valida": len(problemas) == 0,
                "total_configs": total,
                "problemas": problemas,
                "avisos": avisos,
            }
        except Exception as e:
            logger.error(f"Erro ao validar configs: {e}")
            return {"valida": False, "erro": str(e)}

    def contar(self) -> Dict[str, int]:
        """Conta configurações por status."""
        if not self._disponivel:
            return {}

        try:
            total = self.colecao.count_documents({"excluida": False})
            ativas = self.colecao.count_documents({"excluida": False, "ativo": True})
            excluidas = self.colecao.count_documents({"excluida": True})
            return {
                "total": total,
                "ativas": ativas,
                "inativas": total - ativas,
                "excluidas": excluidas,
            }
        except Exception as e:
            logger.error(f"Erro ao contar configs: {e}")
            return {}

    # ==================== IMPORTAÇÃO DA PLANILHA ====================

    def importar_da_planilha(self, planilha_path: str = None,
                             sobrescrever: bool = False,
                             marcar_removidos: bool = False) -> Dict[str, Any]:
        """
        Importa as configurações da planilha Excel para o MongoDB.

        Migração 1x: lê o Excel atual e popula o Mongo sem perder dados.

        Args:
            planilha_path: Caminho da planilha. None usa o padrão do service.
            sobrescrever: Se True, atualiza configs existentes (mesmo identificador).
                          Se False, pula configs com mesmo identificador.
            marcar_removidos: Se True, marca como excluída (soft delete) as configs
                              que existem no Mongo mas não estão mais na planilha.

        Returns:
            Dict com resumo (criados, atualizados, pulados, erros).
        """
        resumo = {
            "criados": 0,
            "atualizados": 0,
            "pulados": 0,
            "erros": 0,
            "total_planilha": 0,
            "detalhes": [],
        }

        if not self._disponivel:
            logger.error("MongoDB não disponível para importar configurações")
            resumo["erros"] = 1
            resumo["detalhes"].append({"erro": "MongoDB não disponível"})
            return resumo

        service = PlanilhaContatosService(planilha_path) if planilha_path else planilha_contatos_service

        if not service.carregar():
            logger.error("Não foi possível carregar a planilha para importação")
            resumo["erros"] = 1
            resumo["detalhes"].append({"erro": "Falha ao carregar planilha"})
            return resumo

        # Mês/ano não importam para a migração da config; usar 1/ano atual apenas
        # para iterar (o método monta diretório, mas não enviamos aqui).
        import datetime as _dt
        ano_atual = _dt.datetime.now().year

        identificadores_planilha = set()

        for contato in service.iterar_contatos(1, ano_atual):
            try:
                identificador = str(contato.get("id", ""))
                if not identificador:
                    continue
                identificadores_planilha.add(identificador)

                existe = self.buscar_por_identificador(identificador)

                if existe and not sobrescrever:
                    resumo["pulados"] += 1
                    continue

                dados = self._contato_para_dados(contato)

                if existe and sobrescrever:
                    sucesso = self.atualizar(
                        str(existe["_id"]),
                        dados,
                        origem="importacao",
                    )
                    if sucesso:
                        resumo["atualizados"] += 1
                    else:
                        resumo["erros"] += 1
                        resumo["detalhes"].append({"erro": f"Falha ao atualizar {identificador}"})
                else:
                    dados["origem"] = OrigemConfigEnum.PLANILHA.value
                    novo_id = self.criar(dados)
                    if novo_id:
                        resumo["criados"] += 1
                    else:
                        resumo["erros"] += 1
                        resumo["detalhes"].append({"erro": f"Falha ao criar {identificador}"})

            except Exception as e:
                resumo["erros"] += 1
                resumo["detalhes"].append({"erro": f"{e}"})
                logger.error(f"Erro ao importar linha: {e}")

        resumo["total_planilha"] = len(identificadores_planilha)

        # Soft delete dos que não estão mais na planilha
        if marcar_removidos:
            removidos = 0
            for doc in self.listar(apenas_ativas=False, limit=100000, incluir_excluidas=True):
                if doc.get("excluida"):
                    continue
                if str(doc.get("identificador", "")) not in identificadores_planilha:
                    if self.excluir(str(doc["_id"]), origem="migracao"):
                        removidos += 1
            resumo["removidos"] = removidos

        logger.info(
            f"✓ Importação da planilha concluída: {resumo['criados']} criados, "
            f"{resumo['atualizados']} atualizados, {resumo['pulados']} pulados, "
            f"{resumo['erros']} erros"
        )
        return resumo

    def _contato_para_dados(self, contato: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converte um dict de contato (shape do planilha_contatos_service) em
        dados para o modelo ConfigEnvioFolhaPontoMongoDB.

        Args:
            contato: Dict de contato (de iterar_contatos()).

        Returns:
            Dict de dados prontos para criar/atualizar a config.
        """
        return {
            "identificador": str(contato.get("id", "")),
            "nome": contato.get("nome", ""),
            "emails": contato.get("emails", []),
            "telefones": contato.get("telefones", []),
            "grupos_whatsapp": contato.get("grupos_whatsapp", []),
            "enviar_email": "S" if contato.get("enviar_email") else "N",
            "enviar_whatsapp": "S" if contato.get("enviar_whatsapp") else "N",
            "enviar_grupo_whatsapp": "S" if contato.get("enviar_grupo_whatsapp") else "N",
            "enviar_impresso": "S" if contato.get("enviar_impresso") else "N",
            "empresa": contato.get("empresa", ""),
            "local_contrato_polo": contato.get("local_contrato_polo", ""),
            "diretorio_geral": contato.get("diretorio_geral", ""),
            "diretorio_especifico": contato.get("diretorio_especifico", ""),
        }


# Instância singleton
config_envio_folha_ponto_service = ConfigEnvioFolhaPontoService()
