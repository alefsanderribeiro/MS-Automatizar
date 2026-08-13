"""
Modelos Pydantic para Feriado
Estrutura completa para armazenamento em MongoDB
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, date
from enum import Enum
import unicodedata


class TipoFeriado(str, Enum):
    """Tipo do feriado"""
    NACIONAL = "nacional"
    ESTADUAL = "estadual"
    MUNICIPAL = "municipal"
    PONTO_FACULTATIVO = "ponto_facultativo"


class StatusFeriado(str, Enum):
    """Status do feriado"""
    ATIVO = "ativo"
    INATIVO = "inativo"


class FeriadoMongoDB(BaseModel):
    """
    Modelo completo do Feriado para armazenamento em MongoDB
    Representa feriados nacionais, estaduais e municipais
    """

    # ==================== DADOS OBRIGATÓRIOS ====================

    # Data do feriado
    data: date = Field(
        ..., 
        description="Data do feriado (YYYY-MM-DD)"
    )
    
    # Nome/descrição do feriado
    descricao: str = Field(
        ..., 
        description="Descrição do feriado (ex: Natal, Ano Novo, Independência)"
    )
    
    # ==================== DADOS OPCIONAIS ====================
    
    tipo: TipoFeriado = Field(
        default=TipoFeriado.NACIONAL,
        description="Tipo do feriado (nacional, estadual, municipal, ponto_facultativo)"
    )
    
    # Para feriados estaduais/municipais
    uf: Optional[str] = Field(
        default=None,
        description="Estado (UF) para feriados estaduais (ex: RO, AM, SP)"
    )
    
    municipio: Optional[str] = Field(
        default=None,
        description="Município para feriados municipais"
    )
    
    # Feriado recorrente (mesmo dia todo ano)
    recorrente: bool = Field(
        default=True,
        description="Se True, o feriado se repete todo ano na mesma data"
    )

    # ==================== CAMPOS DE CONTROLE ====================

    status: StatusFeriado = Field(
        default=StatusFeriado.ATIVO,
        description="Status do feriado (usar enum StatusFeriado)"
    )

    # Para busca fuzzy matching
    descricao_normalizada: Optional[str] = Field(
        default=None,
        description="Descrição normalizada (minúsculas, sem acentos) para busca"
    )

    # Flag para identificar criação automática
    auto_criado: bool = Field(
        default=False,
        description="True se foi criado automaticamente durante importação"
    )

    # ==================== TIMESTAMPS E METADADOS ====================

    criado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), 
        description="Data de criação"
    )
    atualizado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), 
        description="Última atualização"
    )

    # Versão do documento
    versao: int = Field(default=1, description="Versão do documento")

    # Histórico de alterações
    historico_alteracoes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Lista de alterações realizadas no documento"
    )

    # ==================== VALIDADORES ====================

    @validator('descricao')
    def validar_descricao_nao_vazia(cls, v: str) -> str:
        """Descrição não pode ser vazia"""
        if not v or not v.strip():
            raise ValueError("Descrição do feriado não pode ser vazia")
        return v.strip()

    @validator('descricao_normalizada', pre=True, always=True)
    def normalizar_descricao(cls, v: str, values: Dict) -> str:
        """Normaliza a descrição para busca"""
        descricao = values.get('descricao', '')
        if descricao:
            # Remove acentos e converte para minúsculas
            normalizado = unicodedata.normalize('NFKD', descricao)
            normalizado = ''.join([c for c in normalizado if not unicodedata.combining(c)])
            return normalizado.lower().strip()
        return v or ''
    
    @validator('uf')
    def validar_uf(cls, v: Optional[str]) -> Optional[str]:
        """Valida UF se fornecido"""
        if v:
            v = v.strip().upper()
            ufs_validas = [
                'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA',
                'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN',
                'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'
            ]
            if v not in ufs_validas:
                raise ValueError(f"UF inválida: {v}")
            return v
        return None

    # ==================== MÉTODOS AUXILIARES ====================

    def to_mongo_insert(self) -> Dict[str, Any]:
        """Converte para documento MongoDB (inserção)"""
        doc = self.dict()
        # Converter date para datetime para MongoDB
        if isinstance(doc.get('data'), date):
            doc['data'] = datetime.combine(doc['data'], datetime.min.time())
        return doc

    def to_mongo_update(self) -> Dict[str, Any]:
        """Converte para documento MongoDB (atualização)"""
        doc = self.dict(exclude={'criado_em'})
        doc['atualizado_em'] = datetime.now(timezone.utc)
        # Converter date para datetime para MongoDB
        if isinstance(doc.get('data'), date):
            doc['data'] = datetime.combine(doc['data'], datetime.min.time())
        return doc

    def registrar_alteracao(self, campo: str, valor_anterior: Any, valor_novo: Any, usuario: str = "sistema"):
        """Registra uma alteração no histórico"""
        self.historico_alteracoes.append({
            "campo": campo,
            "valor_anterior": valor_anterior,
            "valor_novo": valor_novo,
            "data": datetime.now(timezone.utc),
            "usuario": usuario
        })
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)

    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }


class FeriadoBuilder:
    """Builder para criar instâncias de FeriadoMongoDB"""
    
    def __init__(self):
        self._data: Dict[str, Any] = {}
    
    def com_data(self, data: date) -> 'FeriadoBuilder':
        self._data['data'] = data
        return self
    
    def com_descricao(self, descricao: str) -> 'FeriadoBuilder':
        self._data['descricao'] = descricao
        return self
    
    def com_tipo(self, tipo: TipoFeriado) -> 'FeriadoBuilder':
        self._data['tipo'] = tipo
        return self
    
    def com_uf(self, uf: str) -> 'FeriadoBuilder':
        self._data['uf'] = uf
        return self
    
    def com_municipio(self, municipio: str) -> 'FeriadoBuilder':
        self._data['municipio'] = municipio
        return self
    
    def recorrente(self, recorrente: bool = True) -> 'FeriadoBuilder':
        self._data['recorrente'] = recorrente
        return self
    
    def com_status(self, status: StatusFeriado) -> 'FeriadoBuilder':
        self._data['status'] = status
        return self
    
    def build(self) -> FeriadoMongoDB:
        return FeriadoMongoDB(**self._data)


# Feriados nacionais fixos do Brasil
FERIADOS_NACIONAIS_FIXOS = [
    {"data": (1, 1), "descricao": "Confraternização Universal", "recorrente": True},
    {"data": (4, 21), "descricao": "Tiradentes", "recorrente": True},
    {"data": (5, 1), "descricao": "Dia do Trabalho", "recorrente": True},
    {"data": (9, 7), "descricao": "Independência do Brasil", "recorrente": True},
    {"data": (10, 12), "descricao": "Nossa Senhora Aparecida", "recorrente": True},
    {"data": (11, 2), "descricao": "Finados", "recorrente": True},
    {"data": (11, 15), "descricao": "Proclamação da República", "recorrente": True},
    {"data": (12, 25), "descricao": "Natal", "recorrente": True},
]
