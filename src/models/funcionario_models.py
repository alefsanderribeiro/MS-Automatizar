"""
Modelos Pydantic para Funcionário
Estrutura completa para armazenamento em MongoDB
Mantém relacionamento com Folha de Ponto via ID
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timezone
from enum import Enum
from bson import ObjectId


class TipoContrato(str, Enum):
    """Tipos de contrato"""
    CLT = "CLT"
    PJ = "PJ"
    APRENDIZ = "Aprendiz"
    ESTAGIARIO = "Estagiário"
    INTERMITENTE = "Intermitente"


class StatusFuncionario(str, Enum):
    """Status do funcionário na empresa (situação trabalhista)"""
    ATIVO = "ativo"
    INATIVO = "inativo"
    AFASTADO = "afastado"
    DEMITIDO = "demitido"
    TRANSFERIDO = "transferido"


class StatusCadastro(str, Enum):
    """Status do cadastro do funcionário no sistema"""
    COMPLETO = "completo"           # Todos os dados obrigatórios preenchidos
    INCOMPLETO = "incompleto"       # Cadastro automático via holerite (só nome/cpf)
    PENDENTE_REVISAO = "pendente_revisao"  # Precisa de conferência manual


class FuncionarioMongoDB(BaseModel):
    """
    Modelo completo do Funcionário para armazenamento em MongoDB
    Inclui campos de controle para busca e rastreamento
    """
    
    # ==================== DADOS OBRIGATÓRIOS ====================
    
    # Identificação (ID único é o _id gerado pelo MongoDB)
    nome: str = Field(..., description="Nome completo do funcionário")
    pis: Optional[str] = Field(default=None, description="PIS do funcionário")
    cpf: Optional[str] = Field(default=None, description="CPF do funcionário")
    
    # Código do funcionário no sistema de folha (código do PDF/planilha)
    codigo_funcionario: Optional[int] = Field(
        default=None,
        description="Código do funcionário no sistema de folha de pagamento (ex: código do PDF)"
    )
    
    # Informações contratuais (opcionais para cadastro incompleto)
    lotacao: Optional[str] = Field(default=None, description="Lotação/departamento")
    contrato: Optional[TipoContrato] = Field(default=None, description="Tipo de contrato")
    
    # ==================== RELACIONAMENTOS (ObjectIds) ====================
    
    # Relacionamento com empresas (N:N - funcionário pode estar em múltiplas empresas)
    empresas_ids: List[ObjectId] = Field(
        default_factory=list,
        description="Lista de ObjectIds das empresas onde o funcionário trabalha"
    )
    
    # Relacionamento com Contrato Empresa (1:1) - Opcional para cadastro incompleto
    contrato_empresa_id: Optional[ObjectId] = Field(
        default=None, 
        description="ObjectId do contrato da empresa com órgãos (ex: CENSIPAM, CNJ). Referência à coleção 'contratos'"
    )
    
    # Relacionamento com Horário (1:1) - Opcional para cadastro incompleto
    horario_id: Optional[ObjectId] = Field(
        default=None, 
        description="ObjectId do horário de trabalho. Referência à coleção 'horarios'"
    )
    
    # Relacionamento com Função (1:1) - Opcional para cadastro incompleto
    funcao_id: Optional[ObjectId] = Field(
        default=None, 
        description="ObjectId da função/cargo. Referência à coleção 'funcoes'"
    )
    
    # Relacionamento com Diretório (1:1)
    diretorio_id: Optional[ObjectId] = Field(
        default=None,
        description="ObjectId do diretório interno. Referência à coleção 'diretorios'. Se None, usar fallback '\\'"
    )
    
    # ==================== CAMPO LEGADO (manter até migração completa) ====================
    # TODO: Remover após migração para diretorio_id ser concluída
    diretorio_interno: Optional[str] = Field(
        default=None,
        description="[LEGADO] Diretório interno para organização de arquivos. Usar diretorio_id."
    )
    
    # Datas importantes
    data_nascimento: Optional[date] = Field(default=None, description="Data de nascimento")
    data_admissao: Optional[date] = Field(default=None, description="Data de admissão")
    data_demissao: Optional[date] = Field(default=None, description="Data de demissão/rescisão (se aplicável)")
    
    # ==================== CAMPOS DE CONTROLE ====================
    
    status: StatusFuncionario = Field(
        default=StatusFuncionario.ATIVO, 
        description="Status do funcionário na empresa (situação trabalhista)"
    )
    
    # Status do cadastro no sistema
    status_cadastro: StatusCadastro = Field(
        default=StatusCadastro.COMPLETO,
        description="Status do cadastro no sistema (completo, incompleto, pendente_revisao)"
    )
    
    # Para busca fuzzy matching
    nome_normalizado: Optional[str] = Field(
        default=None,
        description="Nome normalizado (minúsculas, sem acentos) para busca"
    )
    
    # ==================== TIMESTAMPS E METADADOS ====================
    
    # Controle de ciclo de vida
    criado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Data de criação")
    atualizado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Última atualização")
    
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
            raise ValueError("Nome não pode ser vazio")
        return v.strip()
    
    @validator('lotacao', pre=True)
    def validar_lotacao(cls, v: Optional[str]) -> Optional[str]:
        """Lotação: se fornecida, não pode ser string vazia"""
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v
    
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
    
    def marcar_inativo(self, motivo: str = "") -> None:
        """Marca o funcionário como inativo"""
        self.status = StatusFuncionario.INATIVO
        self.data_demissao = date.today() if not self.data_demissao else self.data_demissao
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico(f"Funcionário marcado como inativo. Motivo: {motivo}")
    
    def reativar(self, motivo: str = "") -> None:
        """Reativa o funcionário"""
        self.status = StatusFuncionario.ATIVO
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico(f"Funcionário reativado. Motivo: {motivo}")
    
    def adicionar_empresa(self, empresa_id: ObjectId) -> None:
        """
        Adiciona referência a uma empresa
        
        Args:
            empresa_id: ID (ObjectId) da empresa
        """
        if empresa_id not in self.empresas_ids:
            self.empresas_ids.append(empresa_id)
            self.adicionar_historico(
                "Empresa adicionada ao funcionário",
                {"empresa_id": str(empresa_id)}
            )
    
    def remover_empresa(self, empresa_id: ObjectId) -> None:
        """
        Remove referência a uma empresa
        
        Args:
            empresa_id: ID (ObjectId) da empresa
        """
        if empresa_id in self.empresas_ids:
            self.empresas_ids.remove(empresa_id)
            self.adicionar_historico(
                "Empresa removida do funcionário",
                {"empresa_id": str(empresa_id)}
            )
    
    def obter_empresas(self) -> List[ObjectId]:
        """
        Retorna lista de IDs de empresas
        
        Returns:
            Lista de empresa_ids (ObjectId)
        """
        return self.empresas_ids.copy()
    
    def obter_contrato_empresa(self) -> ObjectId:
        """
        Retorna ObjectId do contrato da empresa
        
        Returns:
            ObjectId do contrato
        """
        return self.contrato_empresa_id
    
    def obter_horario(self) -> ObjectId:
        """
        Retorna ObjectId do horário de trabalho
        
        Returns:
            ObjectId do horário
        """
        return self.horario_id
    
    def obter_funcao(self) -> ObjectId:
        """
        Retorna ObjectId da função
        
        Returns:
            ObjectId da função
        """
        return self.funcao_id
    
    def atualizar_dados(self, **kwargs) -> None:
        """Atualiza dados do funcionário com histórico"""
        alteracoes = {}
        for chave, valor in kwargs.items():
            if hasattr(self, chave):
                alteracoes[chave] = {"antigo": getattr(self, chave), "novo": valor}
                setattr(self, chave, valor)
        
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico("Dados atualizados", alteracoes)
    
    def obter_chave_busca(self) -> tuple:
        """
        Retorna chave composta para busca: (nome, lotação, contrato)
        Utilizada para identificar funcionário no Excel
        
        Returns:
            tuple: (nome, lotacao, contrato)
        """
        return (self.nome, self.lotacao, self.contrato)
    
    def is_cadastro_completo(self) -> bool:
        """
        Verifica se o cadastro do funcionário está completo.
        Um cadastro completo possui todos os campos obrigatórios preenchidos.
        
        Returns:
            bool: True se completo, False se incompleto
        """
        campos_obrigatorios = [
            self.lotacao,
            self.contrato,
            self.contrato_empresa_id,
            self.horario_id,
            self.funcao_id
        ]
        return all(campo is not None for campo in campos_obrigatorios)
    
    def completar_cadastro(
        self,
        lotacao: str,
        contrato: TipoContrato,
        contrato_empresa_id: ObjectId,
        horario_id: ObjectId,
        funcao_id: ObjectId,
        diretorio_id: Optional[ObjectId] = None
    ) -> None:
        """
        Completa o cadastro de um funcionário que foi criado de forma incompleta.
        Atualiza os campos obrigatórios e muda o status para COMPLETO.
        
        Args:
            lotacao: Lotação/setor do funcionário
            contrato: Tipo de contrato (MENSALISTA, HORISTA, etc.)
            contrato_empresa_id: ID do contrato da empresa
            horario_id: ID do horário de trabalho
            funcao_id: ID da função
            diretorio_id: ID do diretório (opcional)
        """
        self.lotacao = lotacao
        self.contrato = contrato
        self.contrato_empresa_id = contrato_empresa_id
        self.horario_id = horario_id
        self.funcao_id = funcao_id
        if diretorio_id:
            self.diretorio_id = diretorio_id
        
        self.status_cadastro = StatusCadastro.COMPLETO
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico(
            "Cadastro completado",
            {
                "lotacao": lotacao,
                "contrato": contrato.value if contrato else None,
                "contrato_empresa_id": str(contrato_empresa_id),
                "horario_id": str(horario_id),
                "funcao_id": str(funcao_id)
            }
        )
    
    def marcar_pendente_revisao(self, motivo: str) -> None:
        """
        Marca o cadastro como pendente de revisão.
        
        Args:
            motivo: Motivo pelo qual o cadastro precisa de revisão
        """
        self.status_cadastro = StatusCadastro.PENDENTE_REVISAO
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico("Marcado para revisão", {"motivo": motivo})
    
    def obter_diretorio_interno_ou_fallback(self) -> str:
        """
        Retorna diretorio_interno se preenchido, caso contrário usa lotação como fallback.
        
        NOTA: Este método é legado. Use DiretorioService.obter_nome_diretorio(diretorio_id) 
        para obter o nome do diretório a partir do diretorio_id.
        
        Fallback: converte espaços para underscores e coloca em maiúsculas.
        
        Returns:
            str: Diretório interno ou lotação normalizada
        
        Examples:
            >>> func.diretorio_interno = "ADMINISTRATIVO_JOAO"
            >>> func.obter_diretorio_interno_ou_fallback()
            'ADMINISTRATIVO_JOAO'
            
            >>> func.diretorio_interno = None
            >>> func.lotacao = "Recursos Humanos"
            >>> func.obter_diretorio_interno_ou_fallback()
            'RECURSOS_HUMANOS'
        """
        # Primeiro verifica o campo legado (para compatibilidade durante migração)
        if self.diretorio_interno:
            return self.diretorio_interno
        
        # Fallback: normalizar lotação
        return self.lotacao.replace(" ", "_").upper() if self.lotacao else "GERAL"
    
    def obter_diretorio_id(self) -> Optional[ObjectId]:
        """
        Retorna o ObjectId do diretório associado ao funcionário.
        
        Returns:
            ObjectId do diretório ou None se não definido
        """
        return self.diretorio_id
    
    def to_mongo_insert(self) -> Dict[str, Any]:
        """
        Converte para formato adequado para inserção em MongoDB
        Converte objetos date para datetime para compatibilidade com MongoDB
        
        Returns:
            Dicionário pronto para inserção
        """
        doc = self.dict()
        doc.pop('_id', None)
        
        # Converter date para datetime para compatibilidade MongoDB
        if doc.get('data_nascimento') and isinstance(doc['data_nascimento'], date) and not isinstance(doc['data_nascimento'], datetime):
            doc['data_nascimento'] = datetime.combine(doc['data_nascimento'], datetime.min.time())
        if doc.get('data_admissao') and isinstance(doc['data_admissao'], date) and not isinstance(doc['data_admissao'], datetime):
            doc['data_admissao'] = datetime.combine(doc['data_admissao'], datetime.min.time())
        if doc.get('data_demissao') and isinstance(doc['data_demissao'], date) and not isinstance(doc['data_demissao'], datetime):
            doc['data_demissao'] = datetime.combine(doc['data_demissao'], datetime.min.time())
        
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

class FuncionarioBuilder:
    """
    Builder para facilitar criação de instâncias de FuncionarioMongoDB
    com validação progressiva
    """
    
    def __init__(self):
        self.dados: Dict[str, Any] = {}
    
    def set_identificacao(
        self,
        nome: str,
        pis: Optional[str] = None,
        cpf: Optional[str] = None
    ) -> 'FuncionarioBuilder':
        """Define dados de identificação"""
        self.dados['nome'] = nome
        self.dados['pis'] = pis
        self.dados['cpf'] = cpf
        return self
    
    def set_contratacao(
        self,
        lotacao: Optional[str] = None,
        contrato: Optional[TipoContrato] = None,
        contrato_empresa_id: Optional[ObjectId] = None,
        horario_id: Optional[ObjectId] = None,
        funcao_id: Optional[ObjectId] = None,
        data_admissao: Optional[date] = None
    ) -> 'FuncionarioBuilder':
        """Define dados contratuais com ObjectIds (todos opcionais para cadastro incompleto)"""
        if lotacao:
            self.dados['lotacao'] = lotacao
        if contrato:
            self.dados['contrato'] = contrato.value if isinstance(contrato, TipoContrato) else contrato
        if contrato_empresa_id:
            self.dados['contrato_empresa_id'] = contrato_empresa_id
        if horario_id:
            self.dados['horario_id'] = horario_id
        if funcao_id:
            self.dados['funcao_id'] = funcao_id
        if data_admissao:
            self.dados['data_admissao'] = data_admissao
        return self
    
    def set_status(
        self,
        status: StatusFuncionario = StatusFuncionario.ATIVO,
        data_demissao: Optional[date] = None
    ) -> 'FuncionarioBuilder':
        """Define status do funcionário na empresa"""
        self.dados['status'] = status.value if isinstance(status, StatusFuncionario) else status
        self.dados['data_demissao'] = data_demissao
        return self
    
    def set_status_cadastro(
        self,
        status_cadastro: StatusCadastro = StatusCadastro.COMPLETO
    ) -> 'FuncionarioBuilder':
        """Define status do cadastro no sistema"""
        self.dados['status_cadastro'] = status_cadastro.value if isinstance(status_cadastro, StatusCadastro) else status_cadastro
        return self
    
    def build(self) -> FuncionarioMongoDB:
        """
        Constrói a instância final com validação Pydantic.
        
        Para cadastro COMPLETO, valida campos obrigatórios.
        Para cadastro INCOMPLETO, apenas nome é obrigatório.
        """
        if 'nome' not in self.dados:
            raise ValueError("Nome não foi definido. Use set_identificacao()")
        
        # Se status_cadastro não definido, verificar se tem todos os campos para ser COMPLETO
        if 'status_cadastro' not in self.dados:
            campos_completos = all([
                self.dados.get('lotacao'),
                self.dados.get('contrato'),
                self.dados.get('contrato_empresa_id'),
                self.dados.get('horario_id'),
                self.dados.get('funcao_id'),
            ])
            self.dados['status_cadastro'] = StatusCadastro.COMPLETO.value if campos_completos else StatusCadastro.INCOMPLETO.value
        
        return FuncionarioMongoDB(**self.dados)
    
    def build_incompleto(self) -> FuncionarioMongoDB:
        """
        Constrói funcionário com cadastro incompleto.
        Útil para criação automática via processamento de holerites.
        """
        if 'nome' not in self.dados:
            raise ValueError("Nome não foi definido. Use set_identificacao()")
        
        self.dados['status_cadastro'] = StatusCadastro.INCOMPLETO.value
        return FuncionarioMongoDB(**self.dados)


# ==================== EXEMPLOS DE USO ====================

if __name__ == "__main__":
    """
    Exemplos de como usar os modelos
    NOTA: Exemplos comentados pois agora precisam de ObjectIds válidos das coleções de referência
    Use o FuncionarioBuilder após importar dados de contratos, horários e funções
    """
    from datetime import date
    
    print("=" * 50)
    print("AVISO: Exemplos requerem ObjectIds válidos")
    print("Execute primeiro: importar_dados_referencia.py")
    print("=" * 50)
    
    # # Exemplo 1: Criar funcionário direto (REQUER ObjectIds válidos)
    # print("=" * 50)
    # print("EXEMPLO 1: Criar FuncionarioMongoDB direto")
    # print("=" * 50)
    # 
    # from bson import ObjectId
    # 
    # func1 = FuncionarioMongoDB(
    #     nome="João Silva",
    #     pis="12345678901",
    #     cpf="123.456.789-00",
    #     lotacao="TI",
    #     contrato=TipoContrato.CLT,
    #     contrato_empresa_id=ObjectId(),  # Substituir por ID válido
    #     horario_id=ObjectId(),  # Substituir por ID válido
    #     funcao_id=ObjectId(),  # Substituir por ID válido
    #     data_admissao=date(2020, 1, 15),
    #     status=StatusFuncionario.ATIVO
    # )
    # print(f"Funcionário criado: {func1.nome}")
    # print(f"Status: {func1.status}")
    # print(f"Chave de busca: {func1.obter_chave_busca()}")
    
    # # Exemplo 2: Criar com Builder (REQUER ObjectIds válidos)
    # print("\n" + "=" * 50)
    # print("EXEMPLO 2: Criar FuncionarioMongoDB com Builder")
    # print("=" * 50)
    # 
    # from bson import ObjectId
    # 
    # func2 = (FuncionarioBuilder()
    #     .set_identificacao(
    #         nome="Maria Santos",
    #         pis="98765432109",
    #         cpf="987.654.321-00"
    #     )
    #     .set_contratacao(
    #         lotacao="Backend",
    #         contrato=TipoContrato.CLT,
    #         contrato_empresa_id=ObjectId(),  # Substituir por ID válido
    #         horario_id=ObjectId(),  # Substituir por ID válido
    #         funcao_id=ObjectId(),  # Substituir por ID válido (Desenvolvedora)
    #         data_admissao=date(2021, 6, 1)
    #     )
    #     .set_status(StatusFuncionario.ATIVO)
    #     .build()
    # )
    # 
    # print(f"Funcionário criado: {func2.nome}")
    # print(f"Chave de busca: {func2.obter_chave_busca()}")
    # print(f"Nome normalizado (para busca): {func2.nome_normalizado}")
    # 
    # # Exemplo 3: Atualizar dados e marcar como inativo
    # print("\n" + "=" * 50)
    # print("EXEMPLO 3: Atualizar e marcar como inativo")
    # print("=" * 50)
    # 
    # print(f"Versão antes: {func2.versao}")
    # func2.atualizar_dados(lotacao="Infraestrutura")
    # print(f"Versão depois: {func2.versao}")
    # print(f"Histórico: {len(func2.historico_alteracoes)} alterações")
    
    print(f"Status antes: {func2.status}")
    func2.marcar_inativo("Transferência para outra empresa")
    print(f"Status depois: {func2.status}")
    print(f"Versão final: {func2.versao}")
