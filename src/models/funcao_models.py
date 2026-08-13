"""
Modelos Pydantic para Função
Estrutura completa para armazenamento em MongoDB
Relacionamento com Funcionário (1:N)
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum


class StatusFuncao(str, Enum):
    """Status da função"""
    ATIVO = "ativo"
    INATIVO = "inativo"


class FuncaoMongoDB(BaseModel):
    """
    Modelo completo da Função para armazenamento em MongoDB
    Representa funções/cargos de funcionários
    """

    # ==================== DADOS OBRIGATÓRIOS ====================

    # Identificação da função (campo único)
    nome: str = Field(
        ..., 
        description="Nome da função (ex: ASSISTENTE ADMINISTRATIVO, MOTORISTA, COZINHEIRA)"
    )
    
    # ==================== DADOS OPCIONAIS ====================
    
    funcao_geral: Optional[str] = Field(
        default=None, 
        description="Categoria/classificação geral da função (ex: ADMINISTRATIVO, MOTORISTA, COZINHA, LAVANDERIA, LIMPEZA, SERVIÇOS GERAIS) - campo livre para classificação"
    )

    # ==================== CAMPOS DE CONTROLE ====================

    status: StatusFuncao = Field(
        default=StatusFuncao.ATIVO,
        description="Status da função (usar enum StatusFuncao)"
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
            raise ValueError("Nome da função não pode ser vazio")
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
        """Marca a função como inativa (soft delete)"""
        self.status = StatusFuncao.INATIVO
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico("Função marcada como inativa")

    def reativar(self) -> None:
        """Reativa a função"""
        self.status = StatusFuncao.ATIVO
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico("Função reativada")

    def obter_info_resumida(self) -> Dict[str, Any]:
        """
        Retorna informações resumidas da função

        Returns:
            Dicionário com informações principais
        """
        return {
            "nome": self.nome,
            "funcao_geral": self.funcao_geral,
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
        return {
            '$set': self.dict(exclude={'_id'})
        }


# ==================== BUILDERS/FACTORIES ====================

class FuncaoBuilder:
    """
    Builder para facilitar criação de instâncias de FuncaoMongoDB
    com validação progressiva
    """

    def __init__(self):
        self.dados: Dict[str, Any] = {}

    def set_nome(self, nome: str) -> 'FuncaoBuilder':
        """Define nome da função"""
        self.dados['nome'] = nome
        return self

    def set_funcao_geral(self, funcao_geral: str) -> 'FuncaoBuilder':
        """Define categoria geral da função"""
        self.dados['funcao_geral'] = funcao_geral
        return self

    def set_ordem(self, ordem: int) -> 'FuncaoBuilder':
        """Define ordem de exibição"""
        self.dados['ordem'] = ordem
        return self

    def marcar_como_auto_criado(self) -> 'FuncaoBuilder':
        """Marca como criado automaticamente"""
        self.dados['auto_criado'] = True
        return self

    def build(self) -> FuncaoMongoDB:
        """Constrói a instância final com validação Pydantic"""
        if 'nome' not in self.dados:
            raise ValueError("Nome não foi definido. Use set_nome()")

        return FuncaoMongoDB(**self.dados)


# ==================== EXEMPLOS DE USO ====================

if __name__ == "__main__":
    """
    Exemplos de como usar os modelos
    """

    # Exemplo 1: Criar função completa
    print("=" * 50)
    print("EXEMPLO 1: Criar função completa")
    print("=" * 50)

    funcao = (FuncaoBuilder()
        .set_nome("ASSISTENTE ADMINISTRATIVO")
        .set_funcao_geral("ADMINISTRATIVO")
        .set_ordem(1)
        .build()
    )

    print(f"Função criada: {funcao.nome}")
    print(f"Categoria: {funcao.funcao_geral}")
    print(f"Info resumida: {funcao.obter_info_resumida()}")

    # Exemplo 2: Criar função auto-criada
    print("\n" + "=" * 50)
    print("EXEMPLO 2: Criar função auto-criada")
    print("=" * 50)

    funcao_auto = (FuncaoBuilder()
        .set_nome("MOTORISTA")
        .marcar_como_auto_criado()
        .build()
    )

    print(f"Função criada: {funcao_auto.nome}")
    print(f"Auto-criado: {funcao_auto.auto_criado}")
    print(f"Ativo: {funcao_auto.ativo}")

    # Exemplo 3: Função sem categoria geral
    print("\n" + "=" * 50)
    print("EXEMPLO 3: Função sem categoria")
    print("=" * 50)

    funcao_simples = (FuncaoBuilder()
        .set_nome("COZINHEIRA")
        .build()
    )

    print(f"Função criada: {funcao_simples.nome}")
    print(f"Categoria: {funcao_simples.funcao_geral}")
