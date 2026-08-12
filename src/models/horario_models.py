"""
Modelos Pydantic para Horário de Trabalho
Estrutura completa para armazenamento em MongoDB
Relacionamento com Funcionário (1:N)
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, time
from enum import Enum


class StatusHorario(str, Enum):
    """Status do horário"""
    ATIVO = "ativo"
    INATIVO = "inativo"


class HorarioMongoDB(BaseModel):
    """
    Modelo completo do Horário de Trabalho para armazenamento em MongoDB
    Representa horários e jornadas de trabalho
    """

    # ==================== DADOS OBRIGATÓRIOS ====================

    # Identificação do horário (campo único)
    descricao: str = Field(
        ..., 
        description="Descrição do horário (ex: '12x36 DIURNO', 'Segunda à Sexta-feira: 07:00 às 17:00')"
    )
    
    # ==================== DADOS OPCIONAIS ====================
    
    dias_trabalho_mes: Optional[int] = Field(
        default=None, 
        description="Número de dias trabalhados por mês"
    )
    
    entrada1: Optional[time] = Field(
        default=None, 
        description="Horário de entrada 1 (formato 07:00)"
    )
    saida1: Optional[time] = Field(
        default=None, 
        description="Horário de saída 1 (formato 17:00)"
    )
    entrada2: Optional[time] = Field(
        default=None, 
        description="Horário de entrada 2 (formato 13:00) - para jornadas com intervalo"
    )
    saida2: Optional[time] = Field(
        default=None, 
        description="Horário de saída 2 (formato 18:00) - para jornadas com intervalo"
    )
    total_horas: Optional[time] = Field(
        default=None, 
        description="Total de horas trabalhadas por dia (formato 08:00)"
    )

    # ==================== CAMPOS DE CONTROLE ====================

    status: StatusHorario = Field(
        default=StatusHorario.ATIVO,
        description="Status do horário (usar enum StatusHorario)"
    )

    ordem: int = Field(
        default=0,
        description="Ordem de exibição/classificação"
    )

    # Para busca fuzzy matching
    nome_normalizado: Optional[str] = Field(
        default=None,
        description="Descrição normalizada (minúsculas, sem acentos) para busca"
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

    @validator('descricao')
    def validar_descricao_nao_vazia(cls, v: str) -> str:
        """Descrição não pode ser vazia"""
        if not v or not v.strip():
            raise ValueError("Descrição do horário não pode ser vazia")
        return v.strip()

    @validator('entrada1', 'saida1', 'entrada2', 'saida2', 'total_horas', pre=True)
    def validar_formato_time(cls, v) -> Optional[time]:
        """Valida e converte strings de horário para time (formato 07:00)"""
        if v is None or v == "":
            return None
        
        if isinstance(v, time):
            return v
        
        if isinstance(v, str):
            # Aceita formatos: "07:00", "7:00"
            v = v.strip()
            try:
                # Tenta parse direto
                hora, minuto = v.split(':')
                return time(int(hora), int(minuto))
            except (ValueError, AttributeError):
                raise ValueError(f"Formato de horário inválido: {v}. Use formato '07:00'")
        
        return v

    @validator('nome_normalizado', pre=True, always=True)
    def normalizar_descricao(cls, v: str, values: Dict) -> str:
        """Normaliza a descrição para busca fuzzy matching"""
        if 'descricao' in values:
            descricao = values['descricao']
            # Remove acentos e converte para minúsculas
            import unicodedata
            nfkd = unicodedata.normalize('NFKD', descricao)
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
        """Marca o horário como inativo (soft delete)"""
        self.status = StatusHorario.INATIVO
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico("Horário marcado como inativo")

    def reativar(self) -> None:
        """Reativa o horário"""
        self.status = StatusHorario.ATIVO
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico("Horário reativado")

    def obter_info_resumida(self) -> Dict[str, Any]:
        """
        Retorna informações resumidas do horário

        Returns:
            Dicionário com informações principais
        """
        return {
            "descricao": self.descricao,
            "status": self.status,
            "jornada": {
                "entrada1": self.entrada1.strftime("%H:%M") if self.entrada1 else None,
                "saida1": self.saida1.strftime("%H:%M") if self.saida1 else None,
                "entrada2": self.entrada2.strftime("%H:%M") if self.entrada2 else None,
                "saida2": self.saida2.strftime("%H:%M") if self.saida2 else None,
                "total_horas": self.total_horas.strftime("%H:%M") if self.total_horas else None,
            },
            "dias_trabalho_mes": self.dias_trabalho_mes,
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
        
        # Converter time para string para compatibilidade MongoDB
        for campo in ['entrada1', 'saida1', 'entrada2', 'saida2', 'total_horas']:
            if doc.get(campo) and isinstance(doc[campo], time):
                doc[campo] = doc[campo].strftime("%H:%M")
        
        return doc

    def to_mongo_update(self) -> Dict[str, Any]:
        """
        Converte para formato adequado para atualização em MongoDB

        Returns:
            Dicionário com estrutura {'$set': {...}}
        """
        doc = self.dict(exclude={'_id'})
        
        # Converter time para string para compatibilidade MongoDB
        for campo in ['entrada1', 'saida1', 'entrada2', 'saida2', 'total_horas']:
            if doc.get(campo) and isinstance(doc[campo], time):
                doc[campo] = doc[campo].strftime("%H:%M")
        
        return {'$set': doc}


# ==================== BUILDERS/FACTORIES ====================

class HorarioBuilder:
    """
    Builder para facilitar criação de instâncias de HorarioMongoDB
    com validação progressiva
    """

    def __init__(self):
        self.dados: Dict[str, Any] = {}

    def set_descricao(self, descricao: str) -> 'HorarioBuilder':
        """Define descrição do horário"""
        self.dados['descricao'] = descricao
        return self

    def set_dias_trabalho_mes(self, dias: int) -> 'HorarioBuilder':
        """Define número de dias trabalhados por mês"""
        self.dados['dias_trabalho_mes'] = dias
        return self

    def set_jornada(
        self, 
        entrada1: Optional[time] = None,
        saida1: Optional[time] = None,
        entrada2: Optional[time] = None,
        saida2: Optional[time] = None
    ) -> 'HorarioBuilder':
        """Define horários de entrada e saída"""
        if entrada1:
            self.dados['entrada1'] = entrada1
        if saida1:
            self.dados['saida1'] = saida1
        if entrada2:
            self.dados['entrada2'] = entrada2
        if saida2:
            self.dados['saida2'] = saida2
        return self

    def set_total_horas(self, total: time) -> 'HorarioBuilder':
        """Define total de horas trabalhadas"""
        self.dados['total_horas'] = total
        return self

    def set_ordem(self, ordem: int) -> 'HorarioBuilder':
        """Define ordem de exibição"""
        self.dados['ordem'] = ordem
        return self

    def marcar_como_auto_criado(self) -> 'HorarioBuilder':
        """Marca como criado automaticamente"""
        self.dados['auto_criado'] = True
        return self

    def build(self) -> HorarioMongoDB:
        """Constrói a instância final com validação Pydantic"""
        if 'descricao' not in self.dados:
            raise ValueError("Descrição não foi definida. Use set_descricao()")

        return HorarioMongoDB(**self.dados)


# ==================== EXEMPLOS DE USO ====================

if __name__ == "__main__":
    """
    Exemplos de como usar os modelos
    """

    # Exemplo 1: Criar horário completo
    print("=" * 50)
    print("EXEMPLO 1: Criar horário completo")
    print("=" * 50)

    horario = (HorarioBuilder()
        .set_descricao("Segunda à Sexta-feira: 07:00 às 17:00")
        .set_dias_trabalho_mes(22)
        .set_jornada(
            entrada1=time(7, 0),
            saida1=time(17, 0)
        )
        .set_total_horas(time(8, 0))
        .set_ordem(1)
        .build()
    )

    print(f"Horário criado: {horario.descricao}")
    print(f"Jornada: {horario.entrada1} - {horario.saida1}")
    print(f"Info resumida: {horario.obter_info_resumida()}")

    # Exemplo 2: Criar horário auto-criado
    print("\n" + "=" * 50)
    print("EXEMPLO 2: Criar horário auto-criado")
    print("=" * 50)

    horario_auto = (HorarioBuilder()
        .set_descricao("12x36 DIURNO")
        .marcar_como_auto_criado()
        .build()
    )

    print(f"Horário criado: {horario_auto.descricao}")
    print(f"Auto-criado: {horario_auto.auto_criado}")
    print(f"Ativo: {horario_auto.ativo}")
