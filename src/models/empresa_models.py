"""
Modelos Pydantic para Empresa
Estrutura completa para armazenamento em MongoDB
Relacionamento com Funcionário (1:N) e Folha de Ponto (1:N)
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum


class StatusEmpresa(str, Enum):
    """Status da empresa"""
    ATIVA = "ativa"
    INATIVA = "inativa"
    SUSPENSA = "suspensa"
    EM_CONSTRUCAO = "em_construcao"  # Para autocadastros incompletos


class EmpresaMongoDB(BaseModel):
    """
    Modelo completo da Empresa para armazenamento em MongoDB
    Inclui campos de controle para busca e rastreamento
    """

    # ==================== DADOS OBRIGATÓRIOS ====================

    # Identificação da empresa
    nome: str = Field(..., description="Nome/Razão Social da empresa")
    cnpj: Optional[str] = Field(default=None, description="CNPJ da empresa (formato: XX.XXX.XXX/XXXX-XX)")
    
    # Informações adicionais
    atividade: Optional[str] = Field(default=None, description="Atividade principal da empresa")
    endereco: Optional[str] = Field(default=None, description="Endereço completo da empresa")
    telefone: Optional[str] = Field(default=None, description="Telefone da empresa")
    email: Optional[str] = Field(default=None, description="Email da empresa")
    whatsapp_device_id: Optional[str] = Field(
        default=None,
        description="Device ID do WhatsApp para esta empresa (ex: 5569XXXXXXXX@s.whatsapp.net)"
    )
    responsavel: Optional[str] = Field(default=None, description="Responsável pela empresa")

    # ==================== CAMPOS DE CONTROLE ====================

    status: StatusEmpresa = Field(
        default=StatusEmpresa.EM_CONSTRUCAO,
        description="Status da empresa (ativa, inativa, em_construcao)"
    )

    # Flag para identificar autocadastros incompletos
    incompleto: bool = Field(
        default=False,
        description="True se foi criada automaticamente com dados incompletos"
    )

    # Para busca fuzzy matching
    nome_normalizado: Optional[str] = Field(
        default=None,
        description="Nome normalizado (minúsculas, sem acentos) para busca"
    )

    # Sigla e nome simplificado (opcionais, podem ser preenchidos depois)
    nome_sigla: Optional[str] = Field(
        default=None,
        description="Sigla curta da empresa (ex: 'ACME')"
    )

    nome_simplificado: Optional[str] = Field(
        default=None,
        description="Versão simplificada do nome (opcional)"
    )
    
    # ==================== RELACIONAMENTOS ====================

    # Relacionamentos não são mantidos na coleção de empresa
    # (Funcionários mantêm referência em empresas_ids; Folhas mantêm empresa_id)

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

    @validator('cnpj')
    def validar_cnpj_formato(cls, v: Optional[str]) -> Optional[str]:
        """Valida formato de CNPJ se fornecido"""
        if not v:
            return v

        # Remove caracteres especiais
        cnpj_limpo = v.replace(".", "").replace("-", "").replace("/", "")

        # Valida se tem 14 dígitos
        if len(cnpj_limpo) != 14 or not cnpj_limpo.isdigit():
            raise ValueError(f"CNPJ inválido: {v}")

        return v.strip()

    @validator('whatsapp_device_id')
    def validar_whatsapp_device_id(cls, v: Optional[str]) -> Optional[str]:
        """
        Valida formato de device_id do WhatsApp se fornecido
        Formato esperado: NÚMERO@s.whatsapp.net
        """
        if not v:
            return v

        v = v.strip()

        # Verifica presença de @ e domínio
        if '@' not in v or 's.whatsapp.net' not in v:
            raise ValueError(
                f"Device ID inválido: {v}. "
                "Formato esperado: 5569XXXXXXXX@s.whatsapp.net"
            )

        # Extrai e valida a parte do número
        partes = v.split('@')
        if len(partes) != 2:
            raise ValueError(
                f"Device ID inválido: {v}. "
                "Deve conter exatamente um caractere @"
            )

        numero_parte = partes[0]
        dominio_parte = partes[1]

        # Valida que o número contém apenas dígitos
        if not numero_parte.isdigit():
            raise ValueError(
                f"Parte do número inválida: {numero_parte}. "
                "Deve conter apenas dígitos"
            )

        # Valida domínio
        if dominio_parte != 's.whatsapp.net':
            raise ValueError(
                f"Domínio inválido: {dominio_parte}. "
                "Deve ser: s.whatsapp.net"
            )

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

    def marcar_como_completa(self) -> None:
        """Marca a empresa como completa e incrementa versão"""
        self.status = StatusEmpresa.ATIVA
        self.incompleto = False
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico("Empresa marcada como completa e ativa")

    def marcar_como_inativa(self) -> None:
        """Marca a empresa como inativa"""
        self.status = StatusEmpresa.INATIVA
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico("Empresa marcada como inativa")

    def obter_info_resumida(self) -> Dict[str, Any]:
        """
        Retorna informações resumidas da empresa

        Returns:
            Dicionário com informações principais
        """
        return {
            "nome": self.nome,
            "cnpj": self.cnpj,
            "status": self.status,
            "incompleto": self.incompleto
        }
    
    def obter_dados_folha_ponto(self) -> Dict[str, str]:
        """
        Retorna dados da empresa no formato esperado pelo ProcessadorFolhaPonto.
        Usado para compatibilidade com a geração de folhas a partir do MongoDB.

        Returns:
            Dict[str, str]: Dicionário com chaves EMPRESA, ATIVIDADE, ENDEREÇO, CNPJ

        Examples:
            >>> empresa.nome = "Solucoes Dinamicas"
            >>> empresa.atividade = "Consultoria"
            >>> empresa.obter_dados_folha_ponto()
            {
                'EMPRESA': 'Solucoes Dinamicas',
                'ATIVIDADE': 'Consultoria',
                'ENDEREÇO': 'Rua A, 123',
                'CNPJ': '12.345.678/0001-90'
            }
        """
        return {
            "EMPRESA": self.nome or "",
            "ATIVIDADE": self.atividade or "",
            "ENDEREÇO": self.endereco or "",
            "CNPJ": self.cnpj or ""
        }

    def obter_device_whatsapp(self) -> Optional[str]:
        """
        Retorna o device_id configurado para WhatsApp ou None se não configurado

        Returns:
            Optional[str]: Device ID do WhatsApp ou None
        """
        return self.whatsapp_device_id

    def to_mongo_insert(self) -> Dict[str, Any]:
        """
        Converte para formato adequado para inserção em MongoDB

        Returns:
            Dicionário pronto para inserção
        """
        doc = self.dict()
        # Remover _id se existir (MongoDB vai gerar um novo)
        doc.pop('_id', None)
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

class EmpresaBuilder:
    """
    Builder para facilitar criação de instâncias de EmpresaMongoDB
    com validação progressiva
    """

    def __init__(self):
        self.dados: Dict[str, Any] = {}

    def set_nome(self, nome: str) -> 'EmpresaBuilder':
        """Define nome da empresa"""
        self.dados['nome'] = nome
        return self

    def set_cnpj(self, cnpj: str) -> 'EmpresaBuilder':
        """Define CNPJ da empresa"""
        self.dados['cnpj'] = cnpj
        return self

    def set_atividade(self, atividade: str) -> 'EmpresaBuilder':
        """Define atividade principal"""
        self.dados['atividade'] = atividade
        return self

    def set_endereco(self, endereco: str) -> 'EmpresaBuilder':
        """Define endereço"""
        self.dados['endereco'] = endereco
        return self

    def set_contato(self, telefone: Optional[str] = None, email: Optional[str] = None) -> 'EmpresaBuilder':
        """Define informações de contato"""
        if telefone:
            self.dados['telefone'] = telefone
        if email:
            self.dados['email'] = email
        return self

    def set_whatsapp_device_id(self, device_id: str) -> 'EmpresaBuilder':
        """Define device_id do WhatsApp para esta empresa"""
        self.dados['whatsapp_device_id'] = device_id
        return self

    def set_responsavel(self, responsavel: str) -> 'EmpresaBuilder':
        """Define responsável pela empresa"""
        self.dados['responsavel'] = responsavel
        return self

    def set_status(self, status: StatusEmpresa) -> 'EmpresaBuilder':
        """Define status da empresa"""
        self.dados['status'] = status.value if isinstance(status, StatusEmpresa) else status
        return self

    def marcar_como_incompleta(self) -> 'EmpresaBuilder':
        """Marca como incompleta (para autocadastros)"""
        self.dados['incompleto'] = True
        self.dados['status'] = StatusEmpresa.EM_CONSTRUCAO.value
        return self
    
    def set_nome_sigla(self, sigla: str) -> 'EmpresaBuilder':
        self.dados['nome_sigla'] = sigla
        return self

    def set_nome_simplificado(self, nome_simplificado: str) -> 'EmpresaBuilder':
        self.dados['nome_simplificado'] = nome_simplificado
        return self
    

    def build(self) -> EmpresaMongoDB:
        """Constrói a instância final com validação Pydantic"""
        if 'nome' not in self.dados:
            raise ValueError("Nome não foi definido. Use set_nome()")

        return EmpresaMongoDB(**self.dados)


# ==================== EXEMPLOS DE USO ====================

if __name__ == "__main__":
    """
    Exemplos de como usar os modelos
    """

    # Exemplo 1: Criar empresa completa com Builder
    print("=" * 50)
    print("EXEMPLO 1: Criar empresa completa")
    print("=" * 50)

    empresa_completa = (EmpresaBuilder()
        .set_nome("Solucoes Dinamicas Consultoria")
        .set_cnpj("12.345.678/0001-90")
        .set_atividade("Consultoria em TI")
        .set_endereco("Rua A, 123 - São Paulo, SP")
        .set_contato("(11) 9999-9999", "contato@solucoesdinamicas.com.br")
        .set_responsavel("João Pereira")
        .set_status(StatusEmpresa.ATIVA)
        .build()
    )

    print(f"Empresa criada: {empresa_completa.nome}")
    print(f"Status: {empresa_completa.status}")
    print(f"Incompleto: {empresa_completa.incompleto}")
    print(f"Info resumida: {empresa_completa.obter_info_resumida()}")

    # Exemplo 2: Criar empresa incompleta (autocadastro)
    print("\n" + "=" * 50)
    print("EXEMPLO 2: Criar empresa incompleta (autocadastro)")
    print("=" * 50)

    empresa_incompleta = (EmpresaBuilder()
        .set_nome("Empresa Teste Ltda")
        .marcar_como_incompleta()
        .build()
    )

    print(f"Empresa criada: {empresa_incompleta.nome}")
    print(f"Status: {empresa_incompleta.status}")
    print(f"Incompleto: {empresa_incompleta.incompleto}")
    print(f"Info resumida: {empresa_incompleta.obter_info_resumida()}")

    # Exemplo 3: Operações básicas com histórico
    print("\n" + "=" * 50)
    print("EXEMPLO 3: Marcações de status")
    print("=" * 50)

    empresa = (EmpresaBuilder()
        .set_nome("TechCorp")
        .marcar_como_incompleta()
        .build()
    )

    print(f"Empresa: {empresa.nome}")
    print(f"Status inicial: {empresa.status}")
    print(f"Incompleto: {empresa.incompleto}")

    # Marca como completa
    empresa.marcar_como_completa()
    print(f"Após marcar como completa - Status: {empresa.status}, Incompleto: {empresa.incompleto}")
    print(f"Histórico: {len(empresa.historico_alteracoes)} eventos")

    # Exemplo 4: Configurar device_id do WhatsApp
    print("\n" + "=" * 50)
    print("EXEMPLO 4: Configurar device_id do WhatsApp")
    print("=" * 50)

    empresa_whatsapp = (EmpresaBuilder()
        .set_nome("Communications Corp")
        .set_cnpj("98.765.432/0001-11")
        .set_atividade("Comunicações")
        .set_contato("(21) 98888-8888", "contato@comcorp.com.br")
        .set_whatsapp_device_id("5521999998888@s.whatsapp.net")
        .set_responsavel("Maria Silva")
        .set_status(StatusEmpresa.ATIVA)
        .build()
    )

    print(f"Empresa: {empresa_whatsapp.nome}")
    print(f"Device WhatsApp: {empresa_whatsapp.obter_device_whatsapp()}")
    print(f"Configurado: {empresa_whatsapp.whatsapp_device_id is not None}")

    # Exemplo 5: Empresa sem device_id (retrocompatível)
    print("\n" + "=" * 50)
    print("EXEMPLO 5: Empresa sem device_id (retrocompatível)")
    print("=" * 50)

    empresa_sem_whatsapp = (EmpresaBuilder()
        .set_nome("Enterprise Solutions")
        .set_cnpj("11.111.111/0001-11")
        .set_atividade("Soluções Empresariais")
        .set_contato("(11) 3333-3333", "info@enterprise.com.br")
        .set_responsavel("Ana Pereira")
        .set_status(StatusEmpresa.ATIVA)
        .build()
    )

    print(f"Empresa: {empresa_sem_whatsapp.nome}")
    print(f"Device WhatsApp: {empresa_sem_whatsapp.obter_device_whatsapp()}")
    print(f"Configurado: {empresa_sem_whatsapp.whatsapp_device_id is not None}")
