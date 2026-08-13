"""
Modelos Pydantic para Folha de Ponto
Estrutura completa para armazenamento em MongoDB com validação de dados
Mantém relacionamento com modelo de Funcionário via funcionario_id (ObjectId)
Relacionamento com Empresa via empresa_id (ObjectId)

IMPORTANTE: Não duplica dados de funcionário/empresa (usa apenas referências ObjectId)
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timezone
from enum import Enum
from bson import ObjectId

# Importar enums do modelo de funcionário
from .funcionario_models import TipoContrato


# ==================== ENUMS ====================

class DiaSemana(str, Enum):
    """Dias da semana"""
    SEGUNDA = "Segunda"
    TERCA = "Terça"
    QUARTA = "Quarta"
    QUINTA = "Quinta"
    SEXTA = "Sexta"
    SABADO = "Sábado"
    DOMINGO = "Domingo"


class TipoDia(str, Enum):
    """Tipos de dia na folha de ponto"""
    NORMAL = "NORMAL"
    FERIADO = "FERIADO"
    FALTA = "FALTA"
    ATESTADO = "ATESTADO"
    FOLGA = "FOLGA"
    SABADO = "SÁBADO"
    DOMINGO = "DOMINGO"
    LICENCA = "LICENÇA"
    FERIAS = "FÉRIAS"
    COMPENSACAO = "COMPENSAÇÃO"


class StatusFolhaPonto(str, Enum):
    """Status da folha de ponto"""
    CRIADA = "criada"
    PREENCHIDA = "preenchida"
    ANALISE_PENDENTE = "analise_pendente"
    ANALISE_CONCLUIDA = "analise_concluida"
    EXPORTADA = "exportada"
    ERRO = "erro"


# ==================== MODELOS ====================

class DiaFolhaPonto(BaseModel):
    """
    Representa um dia na Folha de Ponto
    Todos os campos são inicialmente vazios (Optional) até serem preenchidos
    """
    numero_dia: int = Field(..., description="Número do dia (1-31)")
    data: Optional[datetime] = Field(default=None, description="Data do dia (datetime para compatibilidade MongoDB)")
    dia_semana: Optional[DiaSemana] = Field(default=None, description="Dia da semana")
    
    # Horários (vazios até preenchimento manual + análise IA)
    hora_entrada: Optional[str] = Field(default=None, description="Hora de entrada (HH:MM)")
    hora_intervalo_inicio: Optional[str] = Field(default=None, description="Início do intervalo (HH:MM)")
    hora_intervalo_fim: Optional[str] = Field(default=None, description="Fim do intervalo (HH:MM)")
    hora_saida: Optional[str] = Field(default=None, description="Hora de saída (HH:MM)")
    
    # Totalizações (calculadas pela IA depois)
    total_horas_trabalhadas: Optional[str] = Field(default=None, description="Total de horas trabalhadas")
    
    # Observações e status
    observacoes: Optional[str] = Field(default=None, description="Observações do dia")
    tipo_dia: Optional[TipoDia] = Field(
        default=None, 
        description="Tipo de dia (usar enum TipoDia)"
    )
    
    # Controle
    preenchido_manualmente: bool = Field(default=False, description="Se foi preenchido manualmente")
    analise_ia_processada: bool = Field(default=False, description="Se passou pela análise IA")
    
    class Config:
        use_enum_values = True


# ==================== MODELOS AUXILIARES (REMOVIDOS) ====================
# NOTA: DadosEmpresa e DadosFuncionario foram REMOVIDOS para evitar duplicação.
# A folha de ponto agora mantém apenas ObjectId references para empresa e funcionário.
# Para obter dados completos, fazer lookup/join nas coleções respectivas.


class AnaliseIAResultado(BaseModel):
    """Resultado da análise da IA Gemini para a Folha de Ponto"""
    
    # Metadados da análise
    data_analise: Optional[datetime] = Field(default=None, description="Data/hora da análise")
    modelo_ia: Optional[str] = Field(default=None, description="Modelo usado (gemini-2.5-flash-lite)")
    prompt_utilizado: Optional[str] = Field(default=None, description="Prompt enviado para a IA")
    
    # Resposta bruta da IA
    resposta_bruta: Optional[str] = Field(default=None, description="Resposta completa bruta da IA")
    
    # Resultado estruturado (preenchimento dos dias)
    dias_analisados: Optional[int] = Field(default=None, description="Quantidade de dias analisados")
    taxa_preenchimento: Optional[float] = Field(default=None, description="Percentual de preenchimento (0-100)")
    
    # Possíveis avisos/erros da IA
    avisos: Optional[List[str]] = Field(default=None, description="Avisos encontrados durante análise")
    erros: Optional[List[str]] = Field(default=None, description="Erros encontrados durante análise")
    
    # Metadados adicionais
    tempo_processamento_segundos: Optional[float] = Field(default=None, description="Tempo de processamento")
    tokens_utilizados: Optional[int] = Field(default=None, description="Tokens da API utilizados")


class FolhaDePontoData(BaseModel):
    """
    Dados da Folha de Ponto de um mês específico
    Contém apenas a estrutura dos dias + análise IA
    
    IMPORTANTE: Não duplica dados de funcionário/empresa!
    Use funcionario_id e empresa_id (ObjectId) para fazer lookup quando necessário.
    """
    
    # Período
    mes_referencia: str = Field(..., description="Mês de referência em formato YYYY-MM")
    data_inicio: date = Field(..., description="Data de início do período (primeiro dia do mês)")
    data_fim: date = Field(..., description="Data de fim do período (último dia do mês)")
    
    # Dias do mês (sempre lista completa de 28-31 dias)
    dias: Optional[List[DiaFolhaPonto]] = Field(
        default_factory=list,
        description="Lista de todos os dias do mês (28-31 dias, mesmo com campos vazios)"
    )
    
    # Informações detalhadas do funcionário (para renderização/referência rápida)
    # NOTA: Essas informações também estão no funcionário, mas duplicadas aqui para facilitar
    # renderização de relatórios e PDFs sem necessidade de fazer join
    nome_funcionario: Optional[str] = Field(default=None, description="Nome do funcionário")
    nome_normalizado: Optional[str] = Field(
        default=None,
        description="Nome do funcionário normalizado (sem acentos, minúsculas) para busca insensível a acentos"
    )
    cpf_funcionario: Optional[str] = Field(default=None, description="CPF do funcionário")
    cargo_funcionario: Optional[str] = Field(default=None, description="Cargo do funcionário")
    lotacao_funcionario: Optional[str] = Field(default=None, description="Lotação/departamento do funcionário")
    contrato_funcionario: Optional[str] = Field(default=None, description="Nome do contrato (ex: CENSIPAM, CNJ) - obtido a partir de contrato_empresa_id do funcionário")
    horario_funcionario: Optional[str] = Field(default=None, description="Horário de trabalho do funcionário")
    
    # Cálculos e totalizações (preenchidos posteriormente)
    total_horas_mes: Optional[str] = Field(default=None, description="Total de horas trabalhadas no mês")
    total_faltas: Optional[int] = Field(default=None, description="Total de faltas")
    total_feriados: Optional[int] = Field(default=None, description="Total de feriados")
    total_finais_semana: Optional[int] = Field(default=None, description="Total de sábados/domingos")
    
    # Análise IA
    analise_ia: Optional[AnaliseIAResultado] = Field(
        default=None, 
        description="Resultado da análise realizada por IA"
    )
    
    # Status
    preenchimento_concluido: bool = Field(default=False, description="Se o preenchimento foi concluído")
    analise_ia_concluida: bool = Field(default=False, description="Se a análise IA foi concluída")
    
    @validator('dias')
    def validar_quantidade_dias(cls, dias: Optional[List[DiaFolhaPonto]]) -> Optional[List[DiaFolhaPonto]]:
        """Valida que a quantidade de dias está entre 1 e 31 (pode ser menor por feriados/férias)"""
        if dias and not (1 <= len(dias) <= 31):
            raise ValueError(f"Quantidade de dias deve estar entre 1 e 31, recebido: {len(dias)}")
        return dias
    
    @validator('mes_referencia')
    def validar_formato_mes(cls, mes: Optional[str]) -> Optional[str]:
        """Valida formato YYYY-MM (se fornecido)"""
        if not mes:
            return mes
        if len(mes) != 7 or mes[4] != '-':
            raise ValueError(f"Formato inválido para mês_referencia. Use YYYY-MM, recebido: {mes}")
        try:
            parts = mes.split('-')
            int(parts[0])  # ano
            int(parts[1])  # mês
        except (ValueError, IndexError):
            raise ValueError(f"Formato inválido para mês_referencia. Use YYYY-MM, recebido: {mes}")
        return mes
    
    class Config:
        use_enum_values = True


class FolhaDePontoMongoDB(BaseModel):
    """
    Modelo completo da Folha de Ponto para armazenamento em MongoDB
    Inclui campos de controle para busca e rastreamento
    
    RELACIONAMENTOS (via ObjectId - sem duplicação):
    - funcionario_id: ObjectId referenciando coleção 'funcionarios'
    - empresa_id: ObjectId referenciando coleção 'empresas'
    
    Para obter dados completos, use $lookup (join) nas coleções respectivas.
    """
    
    # Dados da folha (núcleo - apenas estrutura de dias)
    folha_data: FolhaDePontoData = Field(..., description="Dados completos da folha de ponto")
    
    # ==================== CAMPOS DE CONTROLE PARA BUSCA ====================
    
    # Chave composta (única combinação) - AGORA COM ObjectId
    funcionario_id: ObjectId = Field(..., description="ID único do funcionário (ObjectId do MongoDB)")
    empresa_id: ObjectId = Field(..., description="ID único da empresa (ObjectId do MongoDB)")
    mes_referencia: str = Field(..., description="Mês em formato YYYY-MM")
    
    # Caminhos de arquivos (absolutos)
    caminho_arquivo_gerado: Optional[str] = Field(
        default=None,
        description="Caminho absoluto do arquivo PDF gerado pelo sistema"
    )
    caminho_arquivo_analisado: Optional[str] = Field(
        default=None,
        description="Caminho absoluto do arquivo PDF preenchido e analisado pela IA"
    )
    
    # ==================== TIMESTAMPS E METADADOS ====================
    
    # Controle de ciclo de vida
    data_criacao: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Data de criação")
    data_atualizacao: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Última atualização")
    
    # Rastreamento de processamento
    status: StatusFolhaPonto = Field(
        default=StatusFolhaPonto.CRIADA, 
        description="Status da folha de ponto (usar enum StatusFolhaPonto)"
    )
    
    # Versão do documento
    versao: int = Field(default=1, description="Versão do documento (incrementa a cada atualização)")
    
    # Histórico de alterações
    historico_alteracoes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Lista de alterações realizadas no documento"
    )
    
    # ==================== SOFT DELETE (EXCLUSÃO LÓGICA) ====================
    # A folha NUNCA é removida fisicamente do banco. Quando excluída, apenas
    # recebe excluida=True + data_exclusao + motivo, preservando o registro
    # e o histórico de envios (trilha de auditoria).
    excluida: bool = Field(
        default=False,
        description="Soft delete: True quando a folha foi marcada como excluída (nunca removida do banco)"
    )
    data_exclusao: Optional[datetime] = Field(
        default=None,
        description="Data/hora em que a folha foi marcada como excluída (soft delete)"
    )
    motivo_exclusao: Optional[str] = Field(
        default=None,
        description="Motivo da exclusão (soft delete), informado pelo usuário"
    )
    
    # ==================== VALIDADORES ====================
    
    @validator('data_atualizacao', pre=True, always=True)
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
    
    def marcar_como_preenchida(self) -> None:
        """Marca a folha como preenchida e incrementa versão"""
        self.status = StatusFolhaPonto.PREENCHIDA
        self.versao += 1
        self.data_atualizacao = datetime.now(timezone.utc)
        self.adicionar_historico("Folha marcada como preenchida")
    
    def marcar_analise_concluida(self) -> None:
        """Marca análise IA como concluída e incrementa versão"""
        self.status = StatusFolhaPonto.ANALISE_CONCLUIDA
        self.versao += 1
        self.data_atualizacao = datetime.now(timezone.utc)
        self.adicionar_historico("Análise IA concluída")
    
    def obter_chave_unica(self) -> tuple:
        """
        Retorna a chave composta única (funcionário_id, empresa_id, mês)
        Utilizada para verificar duplicatas e fazer upsert
        
        Returns:
            tuple: (funcionario_id, empresa_id, mes_referencia)
        """
        return (self.funcionario_id, self.empresa_id, self.mes_referencia)
    
    def to_mongo_insert(self) -> Dict[str, Any]:
        """
        Converte para formato adequado para inserção em MongoDB
        
        Returns:
            Dicionário pronto para inserção
        """
        from datetime import date, datetime
        
        doc = self.dict()
        # Remover _id se existir (MongoDB vai gerar um novo)
        doc.pop('_id', None)
        
        # Converter date para datetime para compatibilidade com MongoDB
        if 'folha_data' in doc:
            folha_data = doc['folha_data']
            if folha_data.get('data_inicio') and isinstance(folha_data['data_inicio'], date):
                folha_data['data_inicio'] = datetime.combine(folha_data['data_inicio'], datetime.min.time())
            if folha_data.get('data_fim') and isinstance(folha_data['data_fim'], date):
                folha_data['data_fim'] = datetime.combine(folha_data['data_fim'], datetime.min.time())
        
        return doc
    
    def to_mongo_update(self) -> Dict[str, Any]:
        """
        Converte para formato adequado para atualização em MongoDB
        Usa operador $set para atualizar apenas campos especificados
        
        Returns:
            Dicionário com estrutura {'$set': {...}}
        """
        return {
            '$set': self.dict(exclude={'_id'})
        }


# ==================== BUILDERS/FACTORIES ====================
# NOTA: FolhaDePontoBuilder foi REMOVIDO pois não faz mais sentido com a nova arquitetura.
# Agora a folha de ponto mantém apenas ObjectId references (funcionario_id, empresa_id).
# Use diretamente FolhaDePontoMongoDB() para criar instâncias.


# ==================== EXEMPLOS DE USO ====================

if __name__ == "__main__":
    """
    Exemplos de como usar os modelos
    """
    from datetime import datetime, date, timedelta
    
    # Exemplo 1: Criar um dia
    print("=" * 50)
    print("EXEMPLO 1: Criar um DiaFolhaPonto")
    print("=" * 50)
    
    dia = DiaFolhaPonto(
        numero_dia=1,
        data=date(2025, 1, 1),
        dia_semana=DiaSemana.QUARTA,
        hora_entrada=None,  # Vazio inicialmente
        hora_intervalo_inicio=None,
        hora_intervalo_fim=None,
        hora_saida=None,
        total_horas_trabalhadas=None,
        observacoes="Feriado",
        tipo_dia=TipoDia.FERIADO,
        preenchido_manualmente=False,
        analise_ia_processada=False
    )
    print(f"Dia criado: {dia.json(indent=2)}")
    
    # Exemplo 2: Criar lista de dias para um mês
    print("\n" + "=" * 50)
    print("EXEMPLO 2: Criar lista de dias para janeiro/2025")
    print("=" * 50)
    
    dias_janeiro = []
    data_inicio = date(2025, 1, 1)
    data_fim = date(2025, 1, 31)
    
    mapa_dias = {
        0: DiaSemana.SEGUNDA,
        1: DiaSemana.TERCA,
        2: DiaSemana.QUARTA,
        3: DiaSemana.QUINTA,
        4: DiaSemana.SEXTA,
        5: DiaSemana.SABADO,
        6: DiaSemana.DOMINGO
    }
    
    data_atual = data_inicio
    numero = 1
    while data_atual <= data_fim:
        dia_semana = mapa_dias[data_atual.weekday()]
        
        dias_janeiro.append(
            DiaFolhaPonto(
                numero_dia=numero,
                data=data_atual,
                dia_semana=dia_semana,
                tipo_dia=TipoDia.SABADO if dia_semana == DiaSemana.SABADO else (
                    TipoDia.DOMINGO if dia_semana == DiaSemana.DOMINGO else TipoDia.NORMAL
                ),
                preenchido_manualmente=False,
                analise_ia_processada=False
            )
        )
        data_atual += timedelta(days=1)
        numero += 1
    
    print(f"Total de dias criados: {len(dias_janeiro)}")
    
    # Exemplo 3: Criar usando o Builder
    print("\n" + "=" * 50)
    print("EXEMPLO 3: Criar FolhaDePontoMongoDB com Builder")
    print("=" * 50)
    
    folha = (FolhaDePontoBuilder()
        .set_funcionario(
            id_funcionario=1,
            nome="João Silva",
            pis="12345678901",
            funcao="Analista",
            lotacao="TI",
            contrato=TipoContrato.CLT,
            horario="08:00-17:00"
        )
        .set_empresa(
            razao_social="Solucoes Dinamicas",
            cnpj="12.345.678/0001-90",
            atividade="Consultoria",
            endereco="Rua A, 123"
        )
        .set_periodo(data_inicio, data_fim)
        .set_dias(dias_janeiro)
        .set_caminhos_arquivos(
            caminho_excel=r"C:\output\folha_janeiro.xlsx",
            caminho_pdf=r"C:\output\folha_janeiro.pdf"
        )
        .build()
    )
    
    print(f"Folha criada com sucesso!")
    print(f"Chave única: {folha.obter_chave_unica()}")
    print(f"Status: {folha.status}")
    print(f"Total de dias: {len(folha.folha_data.dias)}")
