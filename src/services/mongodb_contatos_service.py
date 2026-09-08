"""
Service para leitura de contatos do MongoDB para envio de folhas de ponto
Responsabilidades:
- Buscar contatos da colecao contatos_folha_ponto
- Montar dados no mesmo formato do PlanilhaContatosService
- Listar arquivos PDF dos diretorios
- Montar diretorio completo
"""

import os
from typing import Dict, Any, Optional, List, Generator
from datetime import datetime
from pathlib import Path

from src.utils.telefone_utils import parsear_multiplos_telefones
from src.utils.logger_config_v2 import get_logger
from src.utils.dotenv_path import caminho_dotenv
import dotenv

logger = get_logger("mongodb_contatos")


class MongoDBContatosService:
    """
    Le contatos do MongoDB (colecao contatos_folha_ponto) para envio de folhas de ponto
    
    Mantem a mesma interface de iteracao do PlanilhaContatosService para compatibilidade.
    
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
        "origem": "migracao_planilha",
        "criado_em": "2026-09-08T...",
        "atualizado_em": "2026-09-08T..."
    }
    """

    def __init__(self, collection_name: str = "contatos_folha_ponto"):
        self.logger = get_logger("mongodb_contatos")
        self.collection_name = collection_name
        self._disponivel = False
        self._colecao = None
        self._conectar()

    def _conectar(self):
        """Conecta ao MongoDB"""
        try:
            from pymongo import MongoClient
            from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

            env_path = caminho_dotenv()
            dotenv.load_dotenv(env_path, override=True)

            mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
            db_name = os.getenv("MONGO_DATABASE_NAME", "MS_Automatizar")

            self.cliente = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            # Testar conexao
            self.cliente.admin.command('ping')

            self.db = self.cliente[db_name]
            self._colecao = self.db[self.collection_name]

            # Criar indice unico por funcionario_id (ignorar se ja existe)
            existing_index_names = [idx['name'] for idx in self._colecao.list_indexes()]
            has_funcionario_id_index = any('funcionario_id' in name for name in existing_index_names)
            if not has_funcionario_id_index:
                try:
                    self._colecao.create_index(
                        "funcionario_id",
                        unique=True,
                        sparse=True,
                        name="idx_funcionario_id_contato"
                    )
                except Exception:
                    pass  # Indice ja existe

            self._disponivel = True
            logger.debug(f"MongoDB Contatos Service conectado (colecao: {self.collection_name})")

        except Exception as e:
            logger.error(f"Erro ao conectar MongoDB Contatos: {e}")
            self._disponivel = False

    @property
    def disponivel(self) -> bool:
        """Verifica se o MongoDB esta disponivel"""
        return self._disponivel

    def montar_diretorio_completo(self,
                                   diretorio_geral: str,
                                   diretorio_especifico: str,
                                   mes: int,
                                   ano: int) -> str:
        """
        Monta o caminho completo do diretorio das folhas de ponto
        
        Padrao: {DIRETORIO_GERAL}\\{ANO}\\{MES:02d}.{ANO}\\{DIRETORIO_ESPECIFICO}
        Exemplo: Z:\\04. PESSOAL\\FOLHA PONTO\\2026\\01.2026\\01. MS SERVICOS\\ADMINISTRATIVO
        """
        caminho = Path(diretorio_geral.strip()) / str(ano) / f"{mes:02d}.{ano}" / diretorio_especifico.strip()
        return str(caminho)

    def listar_arquivos_pdf(self, diretorio: str) -> List[str]:
        """
        Lista arquivos PDF em um diretorio e subdiretorios (busca recursiva)
        """
        if not diretorio or not Path(diretorio).exists():
            if diretorio:
                logger.warning(f"Diretorio nao encontrado: {diretorio}")
            return []

        try:
            arquivos = [
                str(f) for f in Path(diretorio).rglob("*.pdf")
                if f.is_file()
            ]
            arquivos.sort(key=lambda x: os.path.basename(x).lower())

            if arquivos:
                logger.debug(f"Encontrados {len(arquivos)} PDFs em {diretorio} (recursivo)")

            return arquivos
        except Exception as e:
            logger.error(f"Erro ao listar arquivos: {e}")
            return []

    def iterar_contatos(self, mes: int, ano: int) -> Generator[Dict[str, Any], None, None]:
        """
        Itera sobre os contatos do MongoDB
        
        Args:
            mes: Mes de referencia
            ano: Ano de referencia
        
        Yields:
            Dict com dados processados de cada contato (mesmo formato do PlanilhaContatosService)
        """
        if not self._disponivel:
            logger.error("MongoDB Contatos indisponivel")
            return

        try:
            contatos = list(self._colecao.find({}))

            if not contatos:
                logger.warning("Nenhum contato encontrado no MongoDB")
                return

            for contato in contatos:
                try:
                    # Verificar se ha algum canal de envio ativo
                    enviar_email = contato.get("enviar_email", False)
                    enviar_whatsapp = contato.get("enviar_whatsapp", False)
                    enviar_grupo = contato.get("enviar_grupo_whatsapp", False)

                    if not any([enviar_email, enviar_whatsapp, enviar_grupo]):
                        continue

                    # Montar diretorio
                    diretorio_geral = contato.get("diretorio_geral", "")
                    diretorio_especifico = contato.get("diretorio_especifico", "")

                    if diretorio_geral and diretorio_especifico:
                        diretorio_completo = self.montar_diretorio_completo(
                            diretorio_geral,
                            diretorio_especifico,
                            mes,
                            ano
                        )
                    else:
                        diretorio_completo = ""
                        logger.warning(f"Contato {contato.get('nome')} sem diretorios configurados")

                    # Listar PDFs
                    arquivos = self.listar_arquivos_pdf(diretorio_completo) if diretorio_completo else []

                    # Parsear emails e telefones
                    emails_raw = contato.get("email", "")
                    telefones_raw = contato.get("telefone", "")
                    grupos_raw = contato.get("grupo_whatsapp", "")

                    # Emails: separados por virgula
                    emails = [e.strip() for e in str(emails_raw).split(",") if e.strip()] if emails_raw else []

                    # Telefones: usar parser existente
                    telefones = parsear_multiplos_telefones(telefones_raw) if telefones_raw else []

                    # Grupos WhatsApp: separados por virgula
                    grupos = [g.strip() for g in str(grupos_raw).split(",") if g.strip()] if grupos_raw else []

                    yield {
                        "id": contato.get("funcionario_id", ""),
                        "nome": contato.get("nome", ""),
                        "empresa": contato.get("empresa", ""),
                        "local_contrato_polo": contato.get("local_contrato_polo", ""),
                        "diretorio_geral": diretorio_geral,
                        "diretorio_especifico": diretorio_especifico,
                        "diretorio_completo": diretorio_completo,
                        "arquivos_pdf": arquivos,

                        # Dados de envio
                        "emails": emails,
                        "telefones": telefones,
                        "grupos_whatsapp": grupos,

                        # Flags de envio
                        "enviar_email": enviar_email,
                        "enviar_whatsapp": enviar_whatsapp,
                        "enviar_grupo_whatsapp": enviar_grupo,
                        "enviar_impresso": contato.get("enviar_impresso", False),

                        # Metadados
                        "mes_referencia": mes,
                        "ano_referencia": ano,
                        "linha_planilha": 0  # Nao se aplica ao MongoDB
                    }

                except Exception as e:
                    logger.error(f"Erro ao processar contato {contato.get('nome', 'desconhecido')}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Erro ao listar contatos do MongoDB: {e}")
            return

    def obter_contato_por_id(self, contato_id: str, mes: int, ano: int) -> Optional[Dict[str, Any]]:
        """
        Obtem dados de um contato especifico pelo ID
        
        Args:
            contato_id: ID do contato (funcionario_id)
            mes: Mes de referencia
            ano: Ano de referencia
        
        Returns:
            Dict com dados do contato ou None
        """
        for contato in self.iterar_contatos(mes, ano):
            if str(contato.get("id")) == str(contato_id):
                return contato
        return None


# Instancia singleton
mongodb_contatos_service = MongoDBContatosService()
