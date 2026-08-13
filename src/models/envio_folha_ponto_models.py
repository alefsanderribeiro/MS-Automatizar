"""
Modelos Pydantic para Envio de Folhas de Ponto
Estrutura completa para armazenamento em MongoDB
Registra todos os envios realizados (email, whatsapp grupo, whatsapp individual)
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
from bson import ObjectId


class TipoEnvioEnum(str, Enum):
    """Tipos de envio disponíveis"""
    EMAIL = "email"
    WHATSAPP_GRUPO = "whatsapp_grupo"
    WHATSAPP_INDIVIDUAL = "whatsapp_individual"


class StatusEnvioEnum(str, Enum):
    """Status do envio"""
    PENDENTE = "pendente"
    ENVIADO = "enviado"
    ERRO = "erro"
    PARCIAL = "parcial"  # Alguns arquivos enviados, outros falharam


class EnvioFolhaPontoMongoDB(BaseModel):
    """
    Modelo completo do Envio de Folha de Ponto para armazenamento em MongoDB
    Registra cada envio realizado com todos os detalhes
    """
    
    # ==================== DADOS DO ENVIO ====================
    
    tipo_envio: TipoEnvioEnum = Field(
        ..., 
        description="Tipo do envio (email, whatsapp_grupo, whatsapp_individual)"
    )
    
    # Destinatários (pode ser lista de emails, JID de grupo, ou telefone)
    destinatarios: List[str] = Field(
        ...,
        description="Lista de destinatários (emails, JID do grupo, ou telefones)"
    )
    
    # Nome do destinatário (para personalização de mensagem)
    nome_destinatario: Optional[str] = Field(
        default=None,
        description="Nome do destinatário para personalização da mensagem"
    )
    
    # ==================== REFERÊNCIA DO PERÍODO ====================
    
    mes_referencia: int = Field(
        ...,
        ge=1,
        le=12,
        description="Mês de referência da folha de ponto (1-12)"
    )
    
    ano_referencia: int = Field(
        ...,
        ge=2020,
        description="Ano de referência da folha de ponto"
    )
    
    local_contrato_polo: str = Field(
        ...,
        description="Local/Contrato/Polo do envio (ex: DSEI AMAPÁ)"
    )
    
    # ==================== DIRETÓRIO E ARQUIVOS ====================
    
    diretorio_completo: str = Field(
        ...,
        description="Caminho completo do diretório onde os PDFs estão"
    )
    
    arquivos_enviados: List[str] = Field(
        default_factory=list,
        description="Lista de nomes dos arquivos PDF enviados (ordem alfabética)"
    )
    
    total_arquivos: int = Field(
        default=0,
        description="Total de arquivos no diretório"
    )
    
    arquivos_com_erro: List[str] = Field(
        default_factory=list,
        description="Lista de arquivos que falharam no envio"
    )
    
    # ==================== TEMPLATE E MENSAGEM ====================
    
    template_usado: Optional[str] = Field(
        default=None,
        description="ID ou nome do template usado para a mensagem"
    )
    
    assunto_email: Optional[str] = Field(
        default=None,
        description="Assunto do email (apenas para tipo EMAIL)"
    )
    
    mensagem_enviada: Optional[str] = Field(
        default=None,
        description="Mensagem completa que foi enviada (após renderização do template)"
    )
    
    # ==================== CONTROLE DE STATUS E RETRY ====================
    
    status: StatusEnvioEnum = Field(
        default=StatusEnvioEnum.PENDENTE,
        description="Status atual do envio"
    )
    
    tentativas: int = Field(
        default=0,
        description="Número de tentativas realizadas"
    )
    
    max_tentativas: int = Field(
        default=3,
        description="Número máximo de tentativas permitidas"
    )
    
    erro_detalhes: Optional[str] = Field(
        default=None,
        description="Detalhes do erro (se houver)"
    )
    
    data_ultima_tentativa: Optional[datetime] = Field(
        default=None,
        description="Data/hora da última tentativa de envio"
    )
    
    data_envio_sucesso: Optional[datetime] = Field(
        default=None,
        description="Data/hora do envio bem sucedido"
    )
    
    # ==================== CAMPOS DE CONTROLE ====================
    
    # Para busca e agrupamento
    nome_normalizado: Optional[str] = Field(
        default=None,
        description="Local/Contrato normalizado (minúsculas, sem acentos) para busca"
    )
    
    # ==================== TIMESTAMPS E METADADOS ====================
    
    criado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Data de criação do registro"
    )
    
    atualizado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Última atualização"
    )
    
    versao: int = Field(default=1, description="Versão do documento")
    
    historico_alteracoes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Lista de alterações realizadas no documento"
    )
    
    # ==================== VALIDADORES ====================
    
    @validator('destinatarios')
    def validar_destinatarios_nao_vazio(cls, v: List[str]) -> List[str]:
        """Deve haver pelo menos um destinatário"""
        if not v or len(v) == 0:
            raise ValueError("Deve haver pelo menos um destinatário")
        return [d.strip() for d in v if d.strip()]
    
    @validator('local_contrato_polo')
    def validar_local_nao_vazio(cls, v: str) -> str:
        """Local/Contrato/Polo não pode ser vazio"""
        if not v or not v.strip():
            raise ValueError("Local/Contrato/Polo não pode ser vazio")
        return v.strip()
    
    @validator('nome_normalizado', pre=True, always=True)
    def normalizar_local(cls, v: str, values: Dict) -> str:
        """Normaliza o local para busca"""
        if 'local_contrato_polo' in values:
            local = values['local_contrato_polo']
            import unicodedata
            nfkd = unicodedata.normalize('NFKD', local)
            normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)])
            return normalizado.lower()
        return v
    
    @validator('atualizado_em', pre=True, always=True)
    def atualizar_timestamp(cls, v: datetime, values: Dict) -> datetime:
        """Sempre atualiza timestamp de modificação"""
        return datetime.now(timezone.utc)
    
    class Config:
        use_enum_values = True
        arbitrary_types_allowed = True
    
    # ==================== MÉTODOS AUXILIARES ====================
    
    def adicionar_historico(self, acao: str, detalhes: Optional[Dict[str, Any]] = None) -> None:
        """
        Adiciona entrada ao histórico de alterações
        
        Args:
            acao: Descrição da ação realizada
            detalhes: Detalhes adicionais da alteração
        """
        entrada = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "acao": acao,
            "versao_anterior": self.versao,
            "versao_nova": self.versao + 1,
            "detalhes": detalhes or {}
        }
        self.historico_alteracoes.append(entrada)
    
    def incrementar_tentativa(self) -> None:
        """Incrementa o contador de tentativas"""
        self.tentativas += 1
        self.data_ultima_tentativa = datetime.now(timezone.utc)
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico(f"Tentativa {self.tentativas} realizada")
    
    def marcar_enviado(self, arquivos: List[str]) -> None:
        """Marca o envio como realizado com sucesso"""
        self.status = StatusEnvioEnum.ENVIADO
        self.arquivos_enviados = arquivos
        self.data_envio_sucesso = datetime.now(timezone.utc)
        self.atualizado_em = datetime.now(timezone.utc)
        self.versao += 1
        self.adicionar_historico("Envio realizado com sucesso", {"arquivos": arquivos})
    
    def marcar_erro(self, erro: str) -> None:
        """Marca o envio como erro"""
        self.status = StatusEnvioEnum.ERRO
        self.erro_detalhes = erro
        self.atualizado_em = datetime.now(timezone.utc)
        self.versao += 1
        self.adicionar_historico("Erro no envio", {"erro": erro})
    
    def marcar_parcial(self, enviados: List[str], com_erro: List[str]) -> None:
        """Marca o envio como parcial (alguns arquivos enviados)"""
        self.status = StatusEnvioEnum.PARCIAL
        self.arquivos_enviados = enviados
        self.arquivos_com_erro = com_erro
        self.atualizado_em = datetime.now(timezone.utc)
        self.versao += 1
        self.adicionar_historico(
            "Envio parcial", 
            {"enviados": enviados, "com_erro": com_erro}
        )
    
    def pode_retentar(self) -> bool:
        """Verifica se ainda pode retentar o envio"""
        return self.tentativas < self.max_tentativas and self.status == StatusEnvioEnum.ERRO


class EnvioFolhaPontoBuilder:
    """Builder para facilitar a criação de EnvioFolhaPontoMongoDB"""
    
    def __init__(self):
        self._data: Dict[str, Any] = {}
    
    def tipo_envio(self, tipo: TipoEnvioEnum) -> 'EnvioFolhaPontoBuilder':
        self._data['tipo_envio'] = tipo
        return self
    
    def destinatarios(self, dest: List[str]) -> 'EnvioFolhaPontoBuilder':
        self._data['destinatarios'] = dest
        return self
    
    def nome_destinatario(self, nome: str) -> 'EnvioFolhaPontoBuilder':
        self._data['nome_destinatario'] = nome
        return self
    
    def periodo(self, mes: int, ano: int) -> 'EnvioFolhaPontoBuilder':
        self._data['mes_referencia'] = mes
        self._data['ano_referencia'] = ano
        return self
    
    def local(self, local: str) -> 'EnvioFolhaPontoBuilder':
        self._data['local_contrato_polo'] = local
        return self
    
    def diretorio(self, diretorio: str) -> 'EnvioFolhaPontoBuilder':
        self._data['diretorio_completo'] = diretorio
        return self
    
    def arquivos(self, arquivos: List[str]) -> 'EnvioFolhaPontoBuilder':
        self._data['arquivos_enviados'] = arquivos
        self._data['total_arquivos'] = len(arquivos)
        return self
    
    def template(self, template: str) -> 'EnvioFolhaPontoBuilder':
        self._data['template_usado'] = template
        return self
    
    def assunto(self, assunto: str) -> 'EnvioFolhaPontoBuilder':
        self._data['assunto_email'] = assunto
        return self
    
    def mensagem(self, mensagem: str) -> 'EnvioFolhaPontoBuilder':
        self._data['mensagem_enviada'] = mensagem
        return self
    
    def max_tentativas(self, max_tent: int) -> 'EnvioFolhaPontoBuilder':
        self._data['max_tentativas'] = max_tent
        return self
    
    def build(self) -> EnvioFolhaPontoMongoDB:
        """Constrói e retorna o modelo"""
        return EnvioFolhaPontoMongoDB(**self._data)
