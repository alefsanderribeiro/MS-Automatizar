"""
Modelos Pydantic para Configuração de Envio de Folhas de Ponto

Representa a CONFIGURAÇÃO de envio por funcionário/contato (antiga linha da
planilha Excel). Cada documento corresponde a uma linha da planilha e define
para onde e como enviar as folhas de ponto (email, WhatsApp individual, grupo
WhatsApp e impresso).

A migração de planilha Excel para MongoDB é feita através do serviço
ConfigEnvioFolhaPontoService.importar_da_planilha().

Os flags S/N (enviar_email, enviar_whatsapp, enviar_grupo_whatsapp,
enviar_impresso) são CRÍTICOS: controlam para onde o envio é realizado.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
from bson import ObjectId


class SimNaoEnum(str, Enum):
    """Valores S/N para flags de envio (preserva leitura humana da planilha)"""
    SIM = "S"
    NAO = "N"


class OrigemConfigEnum(str, Enum):
    """Origem do registro de configuração"""
    PLANILHA = "planilha"           # Importado da planilha Excel
    MANUAL = "manual"               # Cadastrado manualmente no MongoDB
    API = "api"                     # Criado via API
    MIGRACAO = "migracao"           # Criado durante a migração


class ConfigEnvioFolhaPontoMongoDB(BaseModel):
    """
    Modelo de Configuração de Envio de Folha de Ponto em MongoDB.

    Corresponde a UMA linha da planilha "planilha de contatos (folhas de ponto)".
    Os campos seguem a nomenclatura/valores da planilha para preservar
    compatibilidade com o fluxo existente (o orquestrador consome o dict
    retornado por iterar_contatos()).
    """

    # ==================== IDENTIFICAÇÃO ====================

    identificador: str = Field(
        ...,
        description="ID único da linha/contato (campo 'ID' da planilha)",
    )

    nome: str = Field(
        ...,
        description="Nome completo do contato/funcionário",
    )

    nome_normalizado: str = Field(
        default="",
        description="Nome normalizado (minúsculas, sem acentos) para busca",
    )

    # ==================== DADOS DE CONTATO ====================

    emails: List[str] = Field(
        default_factory=list,
        description="Lista de e-mails (separados por , ou ; na planilha)",
    )

    telefones: List[str] = Field(
        default_factory=list,
        description="Lista de telefones normalizados (formato WhatsApp)",
    )

    grupos_whatsapp: List[str] = Field(
        default_factory=list,
        description="Lista de nomes de grupos WhatsApp",
    )

    # ==================== FLAGS DE ENVIO (S/N) ====================

    # Mantidos como strings "S"/"N" para compatibilidade com a planilha e com
    # a leitura humana. O service/orquestrador converte para booleano quando
    # necessário (usa-se o helper par como a planilha: S = True).
    enviar_email: str = Field(
        default=SimNaoEnum.NAO.value,
        description="Flag S/N - envia folha por e-mail",
    )

    enviar_whatsapp: str = Field(
        default=SimNaoEnum.NAO.value,
        description="Flag S/N - envia folha por WhatsApp individual",
    )

    enviar_grupo_whatsapp: str = Field(
        default=SimNaoEnum.NAO.value,
        description="Flag S/N - envia folha para grupo(s) WhatsApp",
    )

    enviar_impresso: str = Field(
        default=SimNaoEnum.NAO.value,
        description="Flag S/N - envia folha impressa (referência, não é envio digital)",
    )

    # ==================== REFERÊNCIA ORGANIZACIONAL ====================

    empresa: str = Field(
        default="",
        description="Nome da empresa",
    )

    local_contrato_polo: str = Field(
        default="",
        description="Local/Contrato/Polo de trabalho (ex: DSEI AMAPÁ)",
    )

    # ==================== DIRETÓRIO ====================

    diretorio_geral: str = Field(
        default="",
        description="Caminho base (ex: Z:\\04. PESSOAL\\FOLHA PONTO)",
    )

    diretorio_especifico: str = Field(
        default="",
        description="Subpasta específica (ex: 01. MS SERVIÇOS\\ADMINISTRATIVO)",
    )

    # ==================== CONTROLE ====================

    ativo: bool = Field(
        default=True,
        description="Se a configuração está ativa (envios consideram apenas ativas)",
    )

    origem: OrigemConfigEnum = Field(
        default=OrigemConfigEnum.MANUAL,
        description="Origem do registro",
    )

    # ==================== TIMESTAMPS E METADADOS ====================

    criado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Data de criação do registro",
    )

    atualizado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Última atualização",
    )

    versao: int = Field(default=1, description="Versão do documento")

    historico_alteracoes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Lista de alterações realizadas no documento",
    )

    # ==================== SOFT DELETE ====================

    excluida: bool = Field(
        default=False,
        description="Soft delete: True quando o registro foi excluído (preservando histórico)",
    )

    excluida_em: Optional[datetime] = Field(
        default=None,
        description="Data da exclusão lógica",
    )

    # ==================== VALIDADORES ====================

    @validator("identificador")
    def validar_identificador(cls, v: str) -> str:
        """Identificador não pode ser vazio"""
        if not v or not str(v).strip():
            raise ValueError("identificador não pode ser vazio")
        return str(v).strip()

    @validator("nome")
    def validar_nome(cls, v: str) -> str:
        """Nome não pode ser vazio"""
        if not v or not str(v).strip():
            raise ValueError("nome não pode ser vazio")
        return str(v).strip()

    @validator("enviar_email", "enviar_whatsapp", "enviar_grupo_whatsapp", "enviar_impresso", pre=True, always=True)
    def normalizar_flag(cls, v: Any) -> str:
        """
        Normaliza flag para "S" ou "N".
        Aceita valores da planilha (S, SIM, Y, YES, 1, TRUE, True, X) e converte
        para "S"/"N" canônico. Preserva os flags S/N de forma consistente.
        """
        valores_sim = ("S", "SIM", "Y", "YES", "1", "TRUE", "TRUE", "X", True, 1)
        if v is None:
            return SimNaoEnum.NAO.value
        if isinstance(v, str):
            normalizado = v.strip().upper()
            if normalizado in ("S", "SIM", "Y", "YES", "1", "TRUE", "X"):
                return SimNaoEnum.SIM.value
            return SimNaoEnum.NAO.value
        if v is True or v == 1:
            return SimNaoEnum.SIM.value
        return SimNaoEnum.NAO.value

    @validator("nome_normalizado", pre=True, always=True)
    def normalizar_nome(cls, v: str, values: Dict) -> str:
        """Normaliza o nome do contato para busca"""
        import unicodedata
        nome = values.get("nome", "")
        if nome:
            nfkd = unicodedata.normalize("NFKD", str(nome))
            normalizado = "".join([c for c in nfkd if not unicodedata.combining(c)])
            return normalizado.lower().strip()
        return v or ""

    @validator("atualizado_em", pre=True, always=True)
    def atualizar_timestamp(cls, v: datetime, values: Dict) -> datetime:
        """Sempre atualiza timestamp de modificação"""
        return datetime.now(timezone.utc)

    class Config:
        use_enum_values = True
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat(),
        }

    # ==================== MÉTODOS AUXILIARES ====================

    @classmethod
    def normalizar_texto(cls, texto: str) -> str:
        """Normaliza texto para comparação (minúsculas, sem acentos)."""
        import unicodedata
        nfkd = unicodedata.normalize("NFKD", str(texto))
        normalizado = "".join([c for c in nfkd if not unicodedata.combining(c)])
        return normalizado.lower().strip()

    def flag_booleano(self, campo: str) -> bool:
        """
        Converte um flag S/N em booleano.
        Retorna True apenas se o valor for "S".
        """
        valor = str(getattr(self, campo, "N") or "N").strip().upper()
        return valor == "S"

    def to_dict_contato(self, mes: int, ano: int, diretorio_completo: str = "", arquivos_pdf: List[str] = None) -> Dict[str, Any]:
        """
        Converte a config em dict no formato esperado pelo orquestrador
        (mesmo shape do dict retornado por planilha_contatos_service.iterar_contatos()).

        Isso garante que o fluxo de envio (email/whatsapp/grupo com flags)
        funcione identicamente a partir do MongoDB.
        """
        return {
            "id": self.identificador,
            "nome": self.nome,
            "empresa": self.empresa,
            "local_contrato_polo": self.local_contrato_polo,
            "diretorio_geral": self.diretorio_geral,
            "diretorio_especifico": self.diretorio_especifico,
            "diretorio_completo": diretorio_completo,
            "arquivos_pdf": arquivos_pdf or [],
            "emails": self.emails,
            "telefones": self.telefones,
            "grupos_whatsapp": self.grupos_whatsapp,
            "enviar_email": self.flag_booleano("enviar_email"),
            "enviar_whatsapp": self.flag_booleano("enviar_whatsapp"),
            "enviar_grupo_whatsapp": self.flag_booleano("enviar_grupo_whatsapp"),
            "enviar_impresso": self.flag_booleano("enviar_impresso"),
            "mes_referencia": mes,
            "ano_referencia": ano,
        }

    def adicionar_historico(self, acao: str, detalhes: Optional[Dict[str, Any]] = None) -> None:
        """Adiciona entrada ao histórico de alterações."""
        self.historico_alteracoes.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "acao": acao,
            "versao_anterior": self.versao,
            "versao_nova": self.versao + 1,
            "detalhes": detalhes or {},
        })

    def marcar_excluida(self) -> None:
        """Marca a configuração como excluída (soft delete)."""
        if not self.excluida:
            self.excluida = True
            self.excluida_em = datetime.now(timezone.utc)
            self.ativo = False
            self.versao += 1
            self.atualizado_em = datetime.now(timezone.utc)
            self.adicionar_historico("Configuração excluída (soft delete)")


class ConfigEnvioFolhaPontoBuilder:
    """Builder para facilitar a criação de ConfigEnvioFolhaPontoMongoDB."""

    def __init__(self):
        self._data: Dict[str, Any] = {}

    def identificacao(self, identificador: str, nome: str) -> "ConfigEnvioFolhaPontoBuilder":
        self._data["identificador"] = identificador
        self._data["nome"] = nome
        return self

    def contato(self, emails=None, telefones=None, grupos_whatsapp=None) -> "ConfigEnvioFolhaPontoBuilder":
        self._data["emails"] = emails or []
        self._data["telefones"] = telefones or []
        self._data["grupos_whatsapp"] = grupos_whatsapp or []
        return self

    def flags(self, email="N", whatsapp="N", grupo="N", impresso="N") -> "ConfigEnvioFolhaPontoBuilder":
        self._data["enviar_email"] = email
        self._data["enviar_whatsapp"] = whatsapp
        self._data["enviar_grupo_whatsapp"] = grupo
        self._data["enviar_impresso"] = impresso
        return self

    def organizacao(self, empresa="", local_contrato_polo="") -> "ConfigEnvioFolhaPontoBuilder":
        self._data["empresa"] = empresa
        self._data["local_contrato_polo"] = local_contrato_polo
        return self

    def diretorio(self, diretorio_geral="", diretorio_especifico="") -> "ConfigEnvioFolhaPontoBuilder":
        self._data["diretorio_geral"] = diretorio_geral
        self._data["diretorio_especifico"] = diretorio_especifico
        return self

    def origem(self, origem: OrigemConfigEnum) -> "ConfigEnvioFolhaPontoBuilder":
        self._data["origem"] = origem
        return self

    def build(self) -> ConfigEnvioFolhaPontoMongoDB:
        """Constrói e retorna o modelo validado."""
        return ConfigEnvioFolhaPontoMongoDB(**self._data)
