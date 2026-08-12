"""
Modelos Pydantic para Holerite (Recibo de Pagamento)
Estrutura completa para:
- Extração via IA Gemini (HoleriteExtracaoSchema)
- Armazenamento em MongoDB (HoleriteMongoDB)

Separação de responsabilidades:
- HoleriteExtracaoSchema: Schema para o Gemini extrair dados do PDF
- HoleriteMongoDB: Modelo completo com referências ObjectId e metadados
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timezone
from enum import Enum
from bson import ObjectId


# ==================== ENUMS ====================

class TipoFolhaEnum(str, Enum):
    """Tipos de folha de pagamento"""
    MENSAL = "Folha Mensal"
    HORISTA = "Horista"
    MENSALISTA = "Mensalista"
    DECIMO_TERCEIRO_1 = "13º Salário 1ª Parcela"
    DECIMO_TERCEIRO_2 = "13º Salário 2ª Parcela"
    FERIAS = "Férias"
    RESCISAO = "Rescisão"
    ADIANTAMENTO = "Adiantamento"


class StatusHoleriteEnum(str, Enum):
    """Status do holerite no sistema"""
    PROCESSADO = "processado"
    PENDENTE = "pendente"
    PENDENTE_REVISAO = "pendente_revisao"
    ENVIADO = "enviado"
    ERRO = "erro"


# ==================== MODELOS AUXILIARES ====================

class ItemHoleriteExtracao(BaseModel):
    """
    Item de vencimento ou desconto extraído do documento.
    Usado pelo Gemini para extração estruturada.
    """
    codigo: Optional[int] = Field(None, description="Código do evento (ex: 998, 210)")
    descricao: str = Field(..., description="Descrição do evento (ex: 'I.N.S.S.', 'PLANO DE SAUDE')")
    referencia: Optional[str] = Field(None, description="Referência (ex: '227:20', '100,36')")
    valor: Optional[float] = Field(None, description="Valor do evento")
    
    class Config:
        extra = "forbid"


class ItemHolerite(BaseModel):
    """Item de vencimento ou desconto para armazenamento no MongoDB"""
    codigo: Optional[int] = None
    descricao: str
    referencia: Optional[str] = None
    valor: Optional[float] = None


class BasesCalculo(BaseModel):
    """Bases de cálculo do holerite"""
    salario_base: Optional[float] = Field(None, description="Salário base")
    sal_contr_inss: Optional[float] = Field(None, description="Salário de contribuição INSS")
    base_calc_fgts: Optional[float] = Field(None, description="Base de cálculo FGTS")
    fgts_do_mes: Optional[float] = Field(None, description="FGTS do mês")
    base_calc_irrf: Optional[float] = Field(None, description="Base de cálculo IRRF")
    faixa_irrf: Optional[float] = Field(None, description="Faixa IRRF")


class ArquivoHolerite(BaseModel):
    """Informações do arquivo PDF do holerite"""
    caminho_completo: str = Field(..., description="Caminho absoluto do arquivo")
    nome_arquivo: str = Field(..., description="Nome do arquivo")
    hash_sha256: str = Field(..., description="Hash SHA256 para detecção de duplicatas")
    tamanho_bytes: int = Field(..., description="Tamanho do arquivo em bytes")
    verificado_em: Optional[datetime] = Field(None, description="Última verificação de existência")


class ProcessamentoHolerite(BaseModel):
    """Metadados do processamento do holerite"""
    processado_em: datetime = Field(..., description="Data/hora do processamento")
    modelo_ia: str = Field(..., description="Modelo de IA usado (ex: gemini-2.0-flash)")
    tempo_processamento_ms: Optional[int] = Field(None, description="Tempo de processamento em ms")
    confianca: Optional[float] = Field(None, description="Score de confiança da extração (0-1)")


# ==================== SCHEMA PARA GEMINI ====================

class HoleriteExtracaoSchema(BaseModel):
    """
    Schema para extração de dados do holerite via Gemini.
    
    Este schema é passado para GeminiService.documento_estruturado()
    para obter uma saída estruturada do PDF.
    
    Contém apenas dados BRUTOS do documento, sem referências ObjectId.
    """
    
    # === EMPRESA (dados brutos do documento) ===
    empresa_razao_social: str = Field(
        ..., 
        description="Razão social da empresa (ex: 'MORAES & SANTOS SERVIÇOS LTDA')"
    )
    empresa_cnpj: str = Field(
        ..., 
        description="CNPJ da empresa (ex: '13.912.590/0001-70')"
    )
    empresa_codigo_cc: Optional[str] = Field(
        None, 
        description="Centro de Custo / CC (ex: 'ADMINISTRATIVO')"
    )
    
    # === FUNCIONÁRIO (dados brutos do documento) ===
    funcionario_codigo: Optional[int] = Field(
        None, 
        description="Código do funcionário no sistema da empresa"
    )
    funcionario_nome: str = Field(
        ..., 
        description="Nome completo do funcionário"
    )
    funcionario_cpf: Optional[str] = Field(
        None, 
        description="CPF do funcionário (com ou sem formatação)"
    )
    funcionario_cbo: Optional[str] = Field(
        None, 
        description="Código CBO da função"
    )
    funcionario_departamento: Optional[int] = Field(
        None, 
        description="Número do departamento"
    )
    funcionario_filial: Optional[int] = Field(
        None, 
        description="Número da filial"
    )
    funcionario_funcao: Optional[str] = Field(
        None, 
        description="Função/cargo do funcionário"
    )
    funcionario_data_admissao: Optional[str] = Field(
        None, 
        description="Data de admissão (formato DD/MM/YYYY)"
    )
    
    # === REFERÊNCIA DO PERÍODO ===
    tipo_folha: str = Field(
        ..., 
        description="Tipo da folha (ex: 'Folha Mensal', 'Horista', '13º Salário 1ª Parcela')"
    )
    mes_referencia_texto: str = Field(
        ..., 
        description="Mês de referência por extenso (ex: 'Dezembro de 2025')"
    )
    mes_referencia: int = Field(
        ..., 
        ge=1, 
        le=14, 
        description="Mês numérico (1-12 para meses normais, 13 para 13º 1ª parcela, 14 para 13º 2ª parcela)"
    )
    ano_referencia: int = Field(
        ..., 
        ge=2000, 
        description="Ano de referência"
    )
    
    # === VENCIMENTOS (Acréscimos) ===
    vencimentos: List[ItemHoleriteExtracao] = Field(
        default_factory=list,
        description="Lista de vencimentos/proventos do funcionário"
    )
    total_vencimentos: float = Field(
        ..., 
        description="Total de vencimentos"
    )
    
    # === DESCONTOS ===
    descontos: List[ItemHoleriteExtracao] = Field(
        default_factory=list,
        description="Lista de descontos do funcionário"
    )
    total_descontos: float = Field(
        ..., 
        description="Total de descontos"
    )
    
    # === VALOR LÍQUIDO ===
    valor_liquido: float = Field(
        ..., 
        description="Valor líquido a receber"
    )
    
    # === BASES DE CÁLCULO ===
    salario_base: Optional[float] = Field(None, description="Salário base")
    sal_contr_inss: Optional[float] = Field(None, description="Salário de contribuição INSS")
    base_calc_fgts: Optional[float] = Field(None, description="Base de cálculo FGTS")
    fgts_do_mes: Optional[float] = Field(None, description="FGTS do mês")
    base_calc_irrf: Optional[float] = Field(None, description="Base de cálculo IRRF")
    faixa_irrf: Optional[float] = Field(None, description="Faixa IRRF")
    
    class Config:
        extra = "forbid"  # Gemini não pode inventar campos extras
    
    @validator('empresa_cnpj')
    def validar_cnpj_nao_vazio(cls, v: str) -> str:
        """CNPJ não pode ser vazio"""
        if not v or not v.strip():
            raise ValueError("CNPJ da empresa não pode ser vazio")
        return v.strip()
    
    @validator('funcionario_nome')
    def validar_nome_nao_vazio(cls, v: str) -> str:
        """Nome não pode ser vazio"""
        if not v or not v.strip():
            raise ValueError("Nome do funcionário não pode ser vazio")
        return v.strip()


# ==================== MODELO PARA MONGODB ====================

class HoleriteMongoDB(BaseModel):
    """
    Modelo completo do Holerite para armazenamento em MongoDB.
    
    Usa ObjectId para referências normalizadas (empresa, funcionário).
    Mantém dados brutos do documento em funcionario_documento para auditoria.
    """
    
    # === REFERÊNCIAS (ObjectId) ===
    empresa_id: ObjectId = Field(
        ..., 
        description="Referência à coleção 'empresas' (ObjectId)"
    )
    funcionario_id: Optional[ObjectId] = Field(
        None, 
        description="Referência à coleção 'funcionarios' (ObjectId). None se não vinculado."
    )
    
    # === DADOS DO FUNCIONÁRIO NO DOCUMENTO (para auditoria) ===
    funcionario_documento: Dict[str, Any] = Field(
        ...,
        description="Dados do funcionário conforme aparecem no documento PDF (para auditoria)"
    )
    
    # === REFERÊNCIA DO PERÍODO ===
    tipo_folha: str = Field(..., description="Tipo da folha")
    mes_referencia: int = Field(..., ge=1, le=14, description="Mês (1-12, 13=13º 1ª, 14=13º 2ª)")
    ano_referencia: int = Field(..., ge=2000, description="Ano de referência")
    
    # === VALORES ===
    vencimentos: List[ItemHolerite] = Field(default_factory=list)
    total_vencimentos: float
    
    descontos: List[ItemHolerite] = Field(default_factory=list)
    total_descontos: float
    
    valor_liquido: float
    
    bases_calculo: Optional[BasesCalculo] = None
    
    # === ARQUIVO ===
    arquivo: ArquivoHolerite
    
    # === PROCESSAMENTO ===
    processamento: ProcessamentoHolerite
    
    # === STATUS ===
    status: StatusHoleriteEnum = Field(
        default=StatusHoleriteEnum.PROCESSADO,
        description="Status do holerite no sistema"
    )
    
    # === TIMESTAMPS E CONTROLE ===
    criado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Data de criação"
    )
    atualizado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Última atualização"
    )
    versao: int = Field(default=1, description="Versão do documento")
    historico_alteracoes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Histórico de alterações"
    )
    
    class Config:
        arbitrary_types_allowed = True
        use_enum_values = True
    
    # === VALIDADORES ===
    
    @validator('atualizado_em', pre=True, always=True)
    def atualizar_timestamp(cls, v: datetime, values: Dict) -> datetime:
        """Sempre atualiza timestamp de modificação"""
        return datetime.now(timezone.utc)
    
    # === PROPRIEDADES ===

    @property
    def competencia(self) -> str:
        """Retorna competência no formato MM/AAAA"""
        return f"{self.mes_referencia:02d}/{self.ano_referencia}"

    # === MÉTODOS AUXILIARES ===

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
    
    def obter_chave_unica(self) -> tuple:
        """
        Retorna chave para verificar duplicatas.
        Combinação: (hash do arquivo) - para arquivos idênticos
        OU (empresa_id, funcionario_documento.cpf, mes, ano) - para mesmo período
        """
        cpf = self.funcionario_documento.get("cpf", "")
        return (self.empresa_id, cpf, self.mes_referencia, self.ano_referencia)
    
    def vincular_funcionario(self, funcionario_id: ObjectId) -> None:
        """Vincula holerite a um funcionário"""
        self.funcionario_id = funcionario_id
        self.versao += 1
        self.adicionar_historico(
            "Funcionário vinculado",
            {"funcionario_id": str(funcionario_id)}
        )
    
    def marcar_como_enviado(self) -> None:
        """Marca holerite como enviado"""
        self.status = StatusHoleriteEnum.ENVIADO
        self.versao += 1
        self.adicionar_historico("Holerite marcado como enviado")
    
    def to_mongo_insert(self) -> Dict[str, Any]:
        """Converte para formato adequado para inserção em MongoDB"""
        doc = self.dict()
        doc.pop('_id', None)
        return doc
    
    def to_mongo_update(self) -> Dict[str, Any]:
        """Converte para formato de atualização MongoDB"""
        return {'$set': self.dict(exclude={'_id'})}
    
    @classmethod
    def from_extracao(
        cls,
        extracao: HoleriteExtracaoSchema,
        empresa_id: ObjectId,
        arquivo: ArquivoHolerite,
        processamento: ProcessamentoHolerite,
        funcionario_id: Optional[ObjectId] = None
    ) -> 'HoleriteMongoDB':
        """
        Cria HoleriteMongoDB a partir de dados extraídos pelo Gemini.
        
        Args:
            extracao: Dados extraídos pelo Gemini
            empresa_id: ObjectId da empresa
            arquivo: Informações do arquivo PDF
            processamento: Metadados do processamento
            funcionario_id: ObjectId do funcionário (opcional)
        
        Returns:
            Instância de HoleriteMongoDB pronta para inserção
        """
        # Montar dados do funcionário do documento (para auditoria)
        funcionario_documento = {
            "codigo": extracao.funcionario_codigo,
            "nome": extracao.funcionario_nome,
            "cpf": extracao.funcionario_cpf,
            "cbo": extracao.funcionario_cbo,
            "departamento": extracao.funcionario_departamento,
            "filial": extracao.funcionario_filial,
            "funcao": extracao.funcionario_funcao,
            "data_admissao": extracao.funcionario_data_admissao,
        }
        
        # Converter itens de extração para itens de armazenamento
        vencimentos = [
            ItemHolerite(
                codigo=v.codigo,
                descricao=v.descricao,
                referencia=v.referencia,
                valor=v.valor
            ) for v in extracao.vencimentos
        ]
        
        descontos = [
            ItemHolerite(
                codigo=d.codigo,
                descricao=d.descricao,
                referencia=d.referencia,
                valor=d.valor
            ) for d in extracao.descontos
        ]
        
        # Montar bases de cálculo
        bases_calculo = BasesCalculo(
            salario_base=extracao.salario_base,
            sal_contr_inss=extracao.sal_contr_inss,
            base_calc_fgts=extracao.base_calc_fgts,
            fgts_do_mes=extracao.fgts_do_mes,
            base_calc_irrf=extracao.base_calc_irrf,
            faixa_irrf=extracao.faixa_irrf,
        )
        
        return cls(
            empresa_id=empresa_id,
            funcionario_id=funcionario_id,
            funcionario_documento=funcionario_documento,
            tipo_folha=extracao.tipo_folha,
            mes_referencia=extracao.mes_referencia,
            ano_referencia=extracao.ano_referencia,
            vencimentos=vencimentos,
            total_vencimentos=extracao.total_vencimentos,
            descontos=descontos,
            total_descontos=extracao.total_descontos,
            valor_liquido=extracao.valor_liquido,
            bases_calculo=bases_calculo,
            arquivo=arquivo,
            processamento=processamento,
        )


# ==================== MODELO PARA ENVIO ====================

class EnvioHoleriteMongoDB(BaseModel):
    """
    Registro de envio de holerite.
    Armazena informações sobre cada envio realizado.
    """
    
    # === REFERÊNCIAS ===
    holerite_id: ObjectId = Field(..., description="Referência ao holerite enviado")
    funcionario_id: Optional[ObjectId] = Field(None, description="Funcionário destinatário")
    
    # === TIPO DE ENVIO ===
    tipo_envio: str = Field(
        ..., 
        description="Tipo de envio: 'email', 'whatsapp_individual', 'whatsapp_grupo'"
    )
    
    # === DESTINATÁRIOS ===
    destinatarios: List[str] = Field(
        ..., 
        description="Lista de destinatários (emails, telefones ou JIDs de grupo)"
    )
    
    # === STATUS ===
    sucesso: bool = Field(..., description="Se o envio foi bem sucedido")
    mensagem: Optional[str] = Field(None, description="Mensagem de sucesso ou erro")
    
    # === TIMESTAMPS ===
    enviado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Data/hora do envio"
    )
    
    class Config:
        arbitrary_types_allowed = True


# ==================== EXEMPLO DE USO ====================

if __name__ == "__main__":
    from bson import ObjectId
    
    print("=" * 60)
    print("EXEMPLO: Criar HoleriteExtracaoSchema (para Gemini)")
    print("=" * 60)
    
    # Schema que o Gemini preencheria
    extracao = HoleriteExtracaoSchema(
        empresa_razao_social="MORAES & SANTOS SERVIÇOS LTDA",
        empresa_cnpj="13.912.590/0001-70",
        empresa_codigo_cc="ADMINISTRATIVO",
        funcionario_codigo=1439,
        funcionario_nome="VALDILENE BASTOS LIMA",
        funcionario_cpf="51432089",
        funcionario_funcao="SERVENTE DE LIMPEZA",
        funcionario_data_admissao="20/03/2025",
        tipo_folha="Horista",
        mes_referencia_texto="Dezembro de 2025",
        mes_referencia=12,
        ano_referencia=2025,
        vencimentos=[
            ItemHoleriteExtracao(codigo=9435, descricao="HORAS TRAB INTERMITENTE", referencia="100,36", valor=794.85),
            ItemHoleriteExtracao(codigo=201, descricao="AUXILIO ALIMENTACAO", referencia="250,77", valor=250.77),
        ],
        total_vencimentos=1416.64,
        descontos=[
            ItemHoleriteExtracao(codigo=998, descricao="I.N.S.S.", referencia="7,50", valor=81.30),
        ],
        total_descontos=90.64,
        valor_liquido=1326.00,
        salario_base=7.92,
        fgts_do_mes=93.22,
    )
    
    print(f"Funcionário: {extracao.funcionario_nome}")
    print(f"Valor líquido: R$ {extracao.valor_liquido:,.2f}")
    print(f"Schema JSON:\n{extracao.model_json_schema()}")
