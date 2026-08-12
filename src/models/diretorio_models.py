"""
Modelos Pydantic para Diretório
Estrutura completa para armazenamento em MongoDB
Relacionamento com Funcionário (1:N via diretorio_id) e Contrato (1:1 via contrato_id)

O diretório representa a pasta onde as folhas de ponto são salvas.
Cada diretório está associado a um contrato, permitindo agrupar funcionários
do mesmo contrato em um único local para envio.

Estrutura de pastas: /{ANO}/{MES.ANO}/{NOME_DIRETORIO}/{Nome_Funcionario}.pdf
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
from bson import ObjectId


# ==================== ENUMS ====================

class StatusDiretorio(str, Enum):
    """Status do diretório"""
    ATIVO = "ativo"
    INATIVO = "inativo"


class DiretorioMongoDB(BaseModel):
    """
    Modelo completo do Diretório para armazenamento em MongoDB
    Representa diretórios onde as folhas de ponto são salvas.
    Cada diretório está vinculado a um contrato.
    
    Relacionamentos:
    - 1:1 com Contrato (contrato_id)
    - 1:N com Funcionários (funcionários referenciam diretorio_id)
    """

    # ==================== DADOS OBRIGATÓRIOS ====================

    # ID único (gerado pelo MongoDB na primeira inserção)
    id_diretorio: Optional[str] = Field(
        default=None,
        description="ID único do diretório (string do ObjectId do MongoDB)"
    )

    # Nome do diretório = nome do contrato (campo único)
    nome: str = Field(
        ..., 
        description="Nome do diretório (igual ao nome do contrato vinculado, ex: CENSIPAM, CNJ)"
    )
    
    # ==================== DADOS OPCIONAIS ====================
    
    descricao: Optional[str] = Field(
        default=None, 
        description="Descrição legível do diretório (ex: 'Contrato CENSIPAM - Centro Gestor')"
    )
    
    caminho_relativo: Optional[str] = Field(
        default=None, 
        description="Subpasta customizada para override do caminho padrão (opcional)"
    )
    
    # ==================== RELACIONAMENTO COM CONTRATO ====================
    
    contrato_id: Optional[ObjectId] = Field(
        default=None,
        description="ObjectId do contrato associado. Referência 1:1 à coleção 'contratos'"
    )

    # ==================== CAMPOS DE CONTROLE ====================

    status: StatusDiretorio = Field(
        default=StatusDiretorio.ATIVO,
        description="Status do diretório (usar enum StatusDiretorio)"
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
        description="True se foi criado automaticamente durante migração ou importação"
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
            raise ValueError("Nome do diretório não pode ser vazio")
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
            "timestamp": datetime.now(timezone.utc),
            "acao": acao,
            "versao_anterior": self.versao,
            "versao_nova": self.versao + 1,
            "detalhes": detalhes or {}
        }
        self.historico_alteracoes.append(entrada)

    def marcar_como_inativo(self) -> None:
        """Marca o diretório como inativo (soft delete)"""
        self.status = StatusDiretorio.INATIVO
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico("Diretório marcado como inativo")

    def reativar(self) -> None:
        """Reativa o diretório"""
        self.status = StatusDiretorio.ATIVO
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico("Diretório reativado")

    def obter_caminho(self) -> str:
        """
        Retorna o caminho do diretório.
        Se caminho_relativo estiver definido, usa ele. Caso contrário, usa o nome.
        
        Returns:
            String com o caminho do diretório
        """
        if self.caminho_relativo:
            return self.caminho_relativo
        return self.nome

    def obter_info_resumida(self) -> Dict[str, Any]:
        """
        Retorna informações resumidas do diretório

        Returns:
            Dicionário com informações principais
        """
        return {
            "id_diretorio": self.id_diretorio,
            "nome": self.nome,
            "caminho": self.obter_caminho(),
            "contrato_id": str(self.contrato_id) if self.contrato_id else None,
            "status": self.status,
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
        return doc

    def to_mongo_update(self) -> Dict[str, Any]:
        """
        Converte para formato adequado para atualização em MongoDB

        Returns:
            Dicionário com estrutura {'$set': {...}}
        """
        doc = self.dict(exclude={'_id'})
        return {'$set': doc}


# ==================== BUILDERS/FACTORIES ====================

class DiretorioBuilder:
    """
    Builder para facilitar criação de instâncias de DiretorioMongoDB
    com validação progressiva
    """

    def __init__(self):
        self.dados: Dict[str, Any] = {}

    def set_nome(self, nome: str) -> 'DiretorioBuilder':
        """Define nome do diretório"""
        self.dados['nome'] = nome
        return self

    def set_descricao(self, descricao: str) -> 'DiretorioBuilder':
        """Define descrição do diretório"""
        self.dados['descricao'] = descricao
        return self

    def set_caminho_relativo(self, caminho: str) -> 'DiretorioBuilder':
        """Define caminho relativo customizado"""
        self.dados['caminho_relativo'] = caminho
        return self

    def set_contrato_id(self, contrato_id: ObjectId) -> 'DiretorioBuilder':
        """Define contrato associado"""
        self.dados['contrato_id'] = contrato_id
        return self

    def set_ordem(self, ordem: int) -> 'DiretorioBuilder':
        """Define ordem de exibição"""
        self.dados['ordem'] = ordem
        return self

    def marcar_como_auto_criado(self) -> 'DiretorioBuilder':
        """Marca como criado automaticamente"""
        self.dados['auto_criado'] = True
        return self

    def build(self) -> DiretorioMongoDB:
        """Constrói a instância final com validação Pydantic"""
        if 'nome' not in self.dados:
            raise ValueError("Nome não foi definido. Use set_nome()")

        return DiretorioMongoDB(**self.dados)


# ==================== CONSTANTES ====================

# Nome do diretório padrão para funcionários sem contrato
DIRETORIO_PADRAO = "\\"


# ==================== EXEMPLOS DE USO ====================

if __name__ == "__main__":
    """
    Exemplos de como usar os modelos
    """
    from bson import ObjectId

    # Exemplo 1: Criar diretório completo
    print("=" * 50)
    print("EXEMPLO 1: Criar diretório com contrato")
    print("=" * 50)

    diretorio = (DiretorioBuilder()
        .set_nome("CENSIPAM")
        .set_descricao("Contrato CENSIPAM - Centro Gestor e Operacional do Sistema de Proteção da Amazônia")
        .set_contrato_id(ObjectId())  # Substituir por ID válido
        .set_ordem(1)
        .build()
    )

    print(f"Diretório criado: {diretorio.nome}")
    print(f"Caminho: {diretorio.obter_caminho()}")
    print(f"Info resumida: {diretorio.obter_info_resumida()}")

    # Exemplo 2: Criar diretório auto-criado (migração)
    print("\n" + "=" * 50)
    print("EXEMPLO 2: Criar diretório auto-criado")
    print("=" * 50)

    diretorio_auto = (DiretorioBuilder()
        .set_nome("ADMINISTRATIVO")
        .marcar_como_auto_criado()
        .build()
    )

    print(f"Diretório criado: {diretorio_auto.nome}")
    print(f"Auto-criado: {diretorio_auto.auto_criado}")
    print(f"Status: {diretorio_auto.status}")

    # Exemplo 3: Diretório padrão
    print("\n" + "=" * 50)
    print(f"EXEMPLO 3: Diretório padrão = '{DIRETORIO_PADRAO}'")
    print("=" * 50)
