"""
Modelos Pydantic para Contrato
Estrutura completa para armazenamento em MongoDB
Relacionamento com Funcionário (1:N)
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, date
from enum import Enum


class StatusContrato(str, Enum):
    """Status do contrato"""
    ATIVO = "ativo"
    INATIVO = "inativo"


class ContratoMongoDB(BaseModel):
    """
    Modelo completo do Contrato para armazenamento em MongoDB
    Representa contratos de empresas com informações de vigência
    """

    # ==================== DADOS OBRIGATÓRIOS ====================

    # ID único (gerado pelo MongoDB na primeira inserção)
    id_contrato: Optional[str] = Field(
        default=None,
        description="ID único do contrato (string do ObjectId do MongoDB)"
    )

    # Identificação do contrato (campo único)
    nome: str = Field(..., description="Nome do contrato (ex: ADMINISTRATIVO, CENSIPAM, DSEI ALTO RIO NEGRO)")
    
    # ==================== DADOS OPCIONAIS ====================
    
    numero_contrato: Optional[str] = Field(default=None, description="Número do contrato")
    numero_processo: Optional[str] = Field(default=None, description="Número do processo")
    orgao: Optional[str] = Field(default=None, description="Órgão responsável pelo contrato")
    localidade: Optional[str] = Field(default=None, description="Localidade do contrato")
    inicio_vigencia: Optional[date] = Field(default=None, description="Data de início da vigência")
    fim_vigencia: Optional[date] = Field(default=None, description="Data de fim da vigência")

    # ==================== CAMPOS DE CONTROLE ====================

    status: StatusContrato = Field(
        default=StatusContrato.ATIVO,
        description="Status do contrato (usar enum StatusContrato)"
    )

    ordem: int = Field(
        default=0,
        description="Ordem de exibição/classificação"
    )

    # Para busca fuzzy matching
    nome_normalizado: Optional[str] = Field(
        default=None,
        description="Nome normalizado (minúsculas, sem acentos) para busca"
    )

    # Flag para identificar criação automática
    auto_criado: bool = Field(
        default=False,
        description="True se foi criado automaticamente durante importação de funcionários"
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

    @validator('nome')
    def validar_nome_nao_vazio(cls, v: str) -> str:
        """Nome não pode ser vazio"""
        if not v or not v.strip():
            raise ValueError("Nome do contrato não pode ser vazio")
        return v.strip()

    @validator('nome_normalizado', pre=True, always=True)
    def normalizar_nome(cls, v: str, values: Dict) -> str:
        """Normaliza o nome para busca fuzzy matching"""
        if 'nome' in values:
            nome = values['nome']
            # Remove acentos e converte para minúsculas
            import unicodedata
            nfkd = unicodedata.normalize('NFKD', nome)
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

    def marcar_como_inativo(self) -> None:
        """Marca o contrato como inativo (soft delete)"""
        self.status = StatusContrato.INATIVO
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico("Contrato marcado como inativo")

    def reativar(self) -> None:
        """Reativa o contrato"""
        self.status = StatusContrato.ATIVO
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico("Contrato reativado")

    def obter_info_resumida(self) -> Dict[str, Any]:
        """
        Retorna informações resumidas do contrato

        Returns:
            Dicionário com informações principais
        """
        return {
            "id_contrato": self.id_contrato,
            "nome": self.nome,
            "status": self.status,
            "vigencia": {
                "inicio": self.inicio_vigencia.isoformat() if self.inicio_vigencia else None,
                "fim": self.fim_vigencia.isoformat() if self.fim_vigencia else None
            },
            "auto_criado": self.auto_criado
        }

    def to_mongo_insert(self) -> Dict[str, Any]:
        """
        Converte para formato adequado para inserção em MongoDB

        Returns:
            Dicionário pronto para inserção
        """
        doc = self.dict()
        doc.pop('_id', None)
        
        # Converter date para datetime para compatibilidade MongoDB
        if doc.get('inicio_vigencia') and isinstance(doc['inicio_vigencia'], date):
            doc['inicio_vigencia'] = datetime.combine(doc['inicio_vigencia'], datetime.min.time())
        if doc.get('fim_vigencia') and isinstance(doc['fim_vigencia'], date):
            doc['fim_vigencia'] = datetime.combine(doc['fim_vigencia'], datetime.min.time())
        
        return doc

    def to_mongo_update(self) -> Dict[str, Any]:
        """
        Converte para formato adequado para atualização em MongoDB

        Returns:
            Dicionário com estrutura {'$set': {...}}
        """
        doc = self.dict(exclude={'_id'})
        
        # Converter date para datetime para compatibilidade MongoDB
        if doc.get('inicio_vigencia') and isinstance(doc['inicio_vigencia'], date):
            doc['inicio_vigencia'] = datetime.combine(doc['inicio_vigencia'], datetime.min.time())
        if doc.get('fim_vigencia') and isinstance(doc['fim_vigencia'], date):
            doc['fim_vigencia'] = datetime.combine(doc['fim_vigencia'], datetime.min.time())
        
        return {'$set': doc}


# ==================== BUILDERS/FACTORIES ====================

class ContratoBuilder:
    """
    Builder para facilitar criação de instâncias de ContratoMongoDB
    com validação progressiva
    """

    def __init__(self):
        self.dados: Dict[str, Any] = {}

    def set_nome(self, nome: str) -> 'ContratoBuilder':
        """Define nome do contrato"""
        self.dados['nome'] = nome
        return self

    def set_numero_contrato(self, numero: str) -> 'ContratoBuilder':
        """Define número do contrato"""
        self.dados['numero_contrato'] = numero
        return self

    def set_numero_processo(self, numero: str) -> 'ContratoBuilder':
        """Define número do processo"""
        self.dados['numero_processo'] = numero
        return self

    def set_orgao(self, orgao: str) -> 'ContratoBuilder':
        """Define órgão"""
        self.dados['orgao'] = orgao
        return self

    def set_localidade(self, localidade: str) -> 'ContratoBuilder':
        """Define localidade"""
        self.dados['localidade'] = localidade
        return self

    def set_vigencia(self, inicio: Optional[date] = None, fim: Optional[date] = None) -> 'ContratoBuilder':
        """Define período de vigência"""
        if inicio:
            self.dados['inicio_vigencia'] = inicio
        if fim:
            self.dados['fim_vigencia'] = fim
        return self

    def set_ordem(self, ordem: int) -> 'ContratoBuilder':
        """Define ordem de exibição"""
        self.dados['ordem'] = ordem
        return self

    def marcar_como_auto_criado(self) -> 'ContratoBuilder':
        """Marca como criado automaticamente"""
        self.dados['auto_criado'] = True
        return self

    def build(self) -> ContratoMongoDB:
        """Constrói a instância final com validação Pydantic"""
        if 'nome' not in self.dados:
            raise ValueError("Nome não foi definido. Use set_nome()")

        return ContratoMongoDB(**self.dados)


# ==================== EXEMPLOS DE USO ====================

if __name__ == "__main__":
    """
    Exemplos de como usar os modelos
    """

    # Exemplo 1: Criar contrato completo
    print("=" * 50)
    print("EXEMPLO 1: Criar contrato completo")
    print("=" * 50)

    contrato = (ContratoBuilder()
        .set_nome("ADMINISTRATIVO")
        .set_numero_contrato("2024/001")
        .set_orgao("Ministério da Saúde")
        .set_localidade("Brasília - DF")
        .set_vigencia(
            inicio=date(2024, 1, 1),
            fim=date(2024, 12, 31)
        )
        .set_ordem(1)
        .build()
    )

    print(f"Contrato criado: {contrato.nome}")
    print(f"Vigência: {contrato.inicio_vigencia} até {contrato.fim_vigencia}")
    print(f"Info resumida: {contrato.obter_info_resumida()}")

    # Exemplo 2: Criar contrato auto-criado (simplificado)
    print("\n" + "=" * 50)
    print("EXEMPLO 2: Criar contrato auto-criado")
    print("=" * 50)

    contrato_auto = (ContratoBuilder()
        .set_nome("CENSIPAM")
        .marcar_como_auto_criado()
        .build()
    )

    print(f"Contrato criado: {contrato_auto.nome}")
    print(f"Auto-criado: {contrato_auto.auto_criado}")
    print(f"Status: {contrato_auto.status}")
