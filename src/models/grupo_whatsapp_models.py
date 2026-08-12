"""
Modelos Pydantic para Cache de Grupos do WhatsApp
Estrutura para armazenamento em MongoDB
Permite mapeamento automático nome → JID do grupo
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum


class StatusGrupo(str, Enum):
    """Status do grupo no cache"""
    ATIVO = "ativo"
    INATIVO = "inativo"  # Grupo não encontrado na última sincronização


class GrupoWhatsAppMongoDB(BaseModel):
    """
    Modelo de Grupo WhatsApp para cache em MongoDB
    Permite busca por nome para obter JID automaticamente
    """
    
    # ==================== IDENTIFICAÇÃO ====================
    
    jid: str = Field(
        ...,
        description="JID do grupo no formato XXXXXXXXXX@g.us"
    )

    whatsapp_device_id: str = Field(
        default="",
        description="Device ID do WhatsApp para este grupo (ex: WhatsApp-Alefe)"
    )

    nome: str = Field(
        ...,
        description="Nome do grupo como aparece no WhatsApp"
    )
    
    # Para busca fuzzy
    nome_normalizado: Optional[str] = Field(
        default=None,
        description="Nome normalizado (minúsculas, sem acentos) para busca"
    )
    
    # ==================== INFORMAÇÕES DO GRUPO ====================
    
    descricao: Optional[str] = Field(
        default=None,
        description="Descrição/tópico do grupo"
    )
    
    owner_jid: Optional[str] = Field(
        default=None,
        description="JID do dono/criador do grupo"
    )
    
    participantes_count: int = Field(
        default=0,
        description="Número de participantes no grupo"
    )
    
    # ==================== CONTROLE ====================
    
    status: StatusGrupo = Field(
        default=StatusGrupo.ATIVO,
        description="Status do grupo no cache"
    )
    
    data_sincronizacao: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Data da última sincronização com a API do WhatsApp"
    )
    
    # ==================== TIMESTAMPS E METADADOS ====================
    
    criado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Data de criação no cache"
    )
    
    atualizado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Última atualização"
    )
    
    versao: int = Field(default=1, description="Versão do documento")
    
    historico_alteracoes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Lista de alterações realizadas"
    )
    
    # ==================== VALIDADORES ====================
    
    @validator('jid')
    def validar_jid_formato(cls, v: str) -> str:
        """Valida formato do JID de grupo"""
        if not v or not v.strip():
            raise ValueError("JID não pode ser vazio")
        v = v.strip()
        if not v.endswith('@g.us'):
            raise ValueError("JID de grupo deve terminar com @g.us")
        return v

    @validator('whatsapp_device_id')
    def validar_device_id_formato(cls, v: str) -> str:
        """
        Valida formato do Device ID do WhatsApp.
        Device ID é o identificador interno (ex: WhatsApp-Alefe), não o JID.
        Permite vazio para retrocompatibilidade.
        """
        if not v:
            return ""
        return v.strip()

    @validator('nome')
    def validar_nome_nao_vazio(cls, v: str) -> str:
        """Nome não pode ser vazio"""
        if not v or not v.strip():
            raise ValueError("Nome do grupo não pode ser vazio")
        return v.strip()
    
    @validator('nome_normalizado', pre=True, always=True)
    def normalizar_nome(cls, v: str, values: Dict) -> str:
        """Normaliza o nome para busca fuzzy"""
        if 'nome' in values:
            nome = values['nome']
            import unicodedata
            nfkd = unicodedata.normalize('NFKD', nome)
            normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)])
            return normalizado.lower().strip()
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
        """Adiciona entrada ao histórico de alterações"""
        entrada = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "acao": acao,
            "versao_anterior": self.versao,
            "versao_nova": self.versao + 1,
            "detalhes": detalhes or {}
        }
        self.historico_alteracoes.append(entrada)
    
    def atualizar_sincronizacao(self, participantes: int = None, descricao: str = None) -> None:
        """Atualiza dados após sincronização com API"""
        self.data_sincronizacao = datetime.now(timezone.utc)
        self.status = StatusGrupo.ATIVO
        if participantes is not None:
            self.participantes_count = participantes
        if descricao is not None:
            self.descricao = descricao
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico("Sincronização realizada")
    
    def marcar_inativo(self) -> None:
        """Marca grupo como não encontrado na sincronização"""
        self.status = StatusGrupo.INATIVO
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico("Grupo não encontrado na sincronização")
    
    @staticmethod
    def normalizar_texto(texto: str) -> str:
        """
        Normaliza texto para comparação
        Remove acentos e converte para minúsculas
        
        Args:
            texto: Texto a ser normalizado
        
        Returns:
            Texto normalizado
        """
        import unicodedata
        nfkd = unicodedata.normalize('NFKD', texto)
        normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)])
        return normalizado.lower().strip()
    
    def match_nome(self, nome_busca: str) -> bool:
        """
        Verifica se o nome do grupo corresponde ao nome buscado
        Faz match exato primeiro, depois parcial

        Args:
            nome_busca: Nome a ser buscado

        Returns:
            True se houver correspondência
        """
        nome_busca_norm = self.normalizar_texto(nome_busca)

        # Match exato
        if self.nome_normalizado == nome_busca_norm:
            return True

        # Match parcial (nome da busca contido no nome do grupo ou vice-versa)
        if nome_busca_norm in self.nome_normalizado or self.nome_normalizado in nome_busca_norm:
            return True

        return False

    def obter_device_id(self) -> str:
        """
        Retorna o Device ID do WhatsApp associado a este grupo.

        Returns:
            Device ID do WhatsApp (ex: WhatsApp-Alefe) ou string vazia se não configurado
        """
        return self.whatsapp_device_id or ""


class GrupoWhatsAppBuilder:
    """Builder para facilitar a criação de GrupoWhatsAppMongoDB"""

    def __init__(self):
        self._data: Dict[str, Any] = {}

    def jid(self, jid: str) -> 'GrupoWhatsAppBuilder':
        self._data['jid'] = jid
        return self

    def device_id(self, device_id: str) -> 'GrupoWhatsAppBuilder':
        """Define o Device ID do WhatsApp para este grupo"""
        self._data['whatsapp_device_id'] = device_id
        return self

    def nome(self, nome: str) -> 'GrupoWhatsAppBuilder':
        self._data['nome'] = nome
        return self

    def descricao(self, descricao: str) -> 'GrupoWhatsAppBuilder':
        self._data['descricao'] = descricao
        return self

    def owner(self, owner_jid: str) -> 'GrupoWhatsAppBuilder':
        self._data['owner_jid'] = owner_jid
        return self

    def participantes(self, count: int) -> 'GrupoWhatsAppBuilder':
        self._data['participantes_count'] = count
        return self

    def build(self) -> GrupoWhatsAppMongoDB:
        """Constrói e retorna o modelo"""
        return GrupoWhatsAppMongoDB(**self._data)

    @classmethod
    def from_api_response(cls, data: Dict[str, Any], device_id: str = "") -> GrupoWhatsAppMongoDB:
        """
        Cria modelo a partir da resposta da API do WhatsApp

        Args:
            data: Dados retornados pela API (estrutura do go-whatsapp-web-multidevice)
            device_id: Device ID do WhatsApp que obteve este grupo (ex: WhatsApp-Alefe)

        Returns:
            GrupoWhatsAppMongoDB populado
        """
        builder = cls()

        # Mapear campos da API para o modelo
        # A API retorna: JID, OwnerJID, Name, Participants, etc.
        builder.jid(data.get('JID', ''))
        builder.nome(data.get('Name', ''))

        # Adicionar device_id se fornecido
        if device_id:
            builder.device_id(device_id)

        if data.get('OwnerJID'):
            builder.owner(data['OwnerJID'])

        if data.get('Topic'):
            builder.descricao(data['Topic'])

        if data.get('Participants'):
            builder.participantes(len(data['Participants']))

        return builder.build()
