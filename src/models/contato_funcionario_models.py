"""
Modelos Pydantic para Contatos de Funcionários
Gerencia múltiplos contatos por funcionário (telefones, emails)
Com suporte a preferências de envio e validação
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
from bson import ObjectId


class TipoContato(str, Enum):
    """Tipos de contato disponíveis"""
    TELEFONE = "telefone"           # Telefone fixo
    CELULAR = "celular"             # Celular (pode receber WhatsApp)
    WHATSAPP = "whatsapp"           # WhatsApp confirmado
    EMAIL_PESSOAL = "email_pessoal" # E-mail pessoal
    EMAIL_CORPORATIVO = "email_corporativo"  # E-mail corporativo


class StatusContato(str, Enum):
    """Status de validação do contato"""
    ATIVO = "ativo"                 # Contato verificado e ativo
    PENDENTE = "pendente"           # Aguardando verificação
    INVALIDO = "invalido"           # Contato inválido (não existe, bloqueado, etc.)
    INATIVO = "inativo"             # Desativado pelo usuário


class OrigemContato(str, Enum):
    """Como o contato foi cadastrado"""
    PLANILHA_EXCEL = "planilha_excel"       # Importado de planilha
    HOLERITE = "holerite"                   # Extraído de holerite
    CADASTRO_MANUAL = "cadastro_manual"     # Digitado manualmente
    API = "api"                             # Recebido via API


class ContatoFuncionarioMongoDB(BaseModel):
    """
    Modelo de contato individual de um funcionário.
    Cada funcionário pode ter múltiplos contatos (vários celulares, emails, etc.)
    """
    
    # ==================== IDENTIFICAÇÃO ====================
    
    funcionario_id: ObjectId = Field(
        ..., 
        description="ObjectId do funcionário dono deste contato"
    )
    
    funcionario_documento: Optional[str] = Field(
        default=None, 
        description="CPF do funcionário (para referência rápida e auditoria)"
    )
    
    funcionario_nome: Optional[str] = Field(
        default=None,
        description="Nome do funcionário (cache para exibição rápida)"
    )
    
    # ==================== DADOS DO CONTATO ====================
    
    tipo: TipoContato = Field(
        ..., 
        description="Tipo do contato (celular, email, etc.)"
    )
    
    valor: str = Field(
        ..., 
        description="Valor do contato (número ou e-mail)"
    )
    
    valor_normalizado: str = Field(
        default="",
        description="Valor normalizado para busca (sem formatação)"
    )
    
    # ==================== PREFERÊNCIAS DE ENVIO ====================
    
    preferencial: bool = Field(
        default=False,
        description="Se é o contato preferencial para o tipo"
    )
    
    aceita_whatsapp: bool = Field(
        default=False,
        description="Se aceita receber mensagens via WhatsApp (para celulares)"
    )
    
    aceita_email: bool = Field(
        default=True,
        description="Se aceita receber e-mails (para emails)"
    )
    
    # ==================== STATUS E CONTROLE ====================
    
    status: StatusContato = Field(
        default=StatusContato.PENDENTE,
        description="Status de validação do contato"
    )
    
    origem: OrigemContato = Field(
        default=OrigemContato.CADASTRO_MANUAL,
        description="Origem do cadastro do contato"
    )
    
    # ==================== METADADOS ====================
    
    criado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Data de criação"
    )
    
    atualizado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Data da última atualização"
    )
    
    ultima_verificacao: Optional[datetime] = Field(
        default=None,
        description="Data da última verificação do contato"
    )
    
    ultimo_envio: Optional[datetime] = Field(
        default=None,
        description="Data do último envio bem-sucedido para este contato"
    )
    
    total_envios: int = Field(
        default=0,
        description="Total de envios realizados para este contato"
    )
    
    total_falhas: int = Field(
        default=0,
        description="Total de falhas de envio"
    )
    
    observacoes: Optional[str] = Field(
        default=None,
        description="Observações sobre o contato"
    )
    
    class Config:
        """Configurações do modelo Pydantic"""
        arbitrary_types_allowed = True
        use_enum_values = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }
    
    # ==================== VALIDATORS ====================
    
    @validator("valor_normalizado", always=True, pre=True)
    def normalizar_valor(cls, v, values):
        """Normaliza o valor para busca"""
        valor = values.get("valor", "")
        tipo = values.get("tipo", "")
        
        if tipo in [TipoContato.TELEFONE, TipoContato.CELULAR, TipoContato.WHATSAPP, 
                    "telefone", "celular", "whatsapp"]:
            # Remove tudo que não é dígito
            return "".join(filter(str.isdigit, valor))
        elif tipo in [TipoContato.EMAIL_PESSOAL, TipoContato.EMAIL_CORPORATIVO,
                      "email_pessoal", "email_corporativo"]:
            # Lowercase e strip
            return valor.lower().strip()
        return valor
    
    @validator("valor")
    def validar_valor(cls, v, values):
        """Valida formato básico do valor"""
        tipo = values.get("tipo", "")
        
        if tipo in [TipoContato.TELEFONE, TipoContato.CELULAR, TipoContato.WHATSAPP,
                    "telefone", "celular", "whatsapp"]:
            # Remover formatação e verificar se tem dígitos suficientes
            digitos = "".join(filter(str.isdigit, v))
            if len(digitos) < 8:
                raise ValueError(f"Número de telefone muito curto: {v}")
            return v
        elif tipo in [TipoContato.EMAIL_PESSOAL, TipoContato.EMAIL_CORPORATIVO,
                      "email_pessoal", "email_corporativo"]:
            if "@" not in v:
                raise ValueError(f"E-mail inválido (sem @): {v}")
            return v.strip()
        return v
    
    # ==================== MÉTODOS ====================
    
    def marcar_como_verificado(self) -> None:
        """Marca o contato como verificado e ativo"""
        self.status = StatusContato.ATIVO
        self.ultima_verificacao = datetime.now(timezone.utc)
        self.atualizado_em = datetime.now(timezone.utc)
    
    def marcar_como_invalido(self, motivo: str = None) -> None:
        """Marca o contato como inválido"""
        self.status = StatusContato.INVALIDO
        self.atualizado_em = datetime.now(timezone.utc)
        if motivo:
            self.observacoes = motivo
    
    def registrar_envio(self, sucesso: bool) -> None:
        """Registra uma tentativa de envio"""
        if sucesso:
            self.ultimo_envio = datetime.now(timezone.utc)
            self.total_envios += 1
        else:
            self.total_falhas += 1
        self.atualizado_em = datetime.now(timezone.utc)
    
    def is_whatsapp_disponivel(self) -> bool:
        """Verifica se pode receber WhatsApp"""
        tipos_whatsapp = [TipoContato.CELULAR, TipoContato.WHATSAPP, "celular", "whatsapp"]
        return (
            self.tipo in tipos_whatsapp and
            self.aceita_whatsapp and
            self.status == StatusContato.ATIVO
        )
    
    def is_email_disponivel(self) -> bool:
        """Verifica se pode receber e-mail"""
        tipos_email = [TipoContato.EMAIL_PESSOAL, TipoContato.EMAIL_CORPORATIVO,
                       "email_pessoal", "email_corporativo"]
        return (
            self.tipo in tipos_email and
            self.aceita_email and
            self.status == StatusContato.ATIVO
        )
    
    def to_mongo_insert(self) -> Dict[str, Any]:
        """
        Converte para formato de inserção no MongoDB.
        
        Returns:
            Dicionário pronto para inserção
        """
        doc = self.dict()
        doc.pop('_id', None)
        return doc


class ContatoFuncionarioBuilder:
    """
    Builder para criar contatos de funcionários de forma mais intuitiva.
    """
    
    def __init__(self):
        self._funcionario_id: Optional[ObjectId] = None
        self._funcionario_documento: Optional[str] = None
        self._funcionario_nome: Optional[str] = None
        self._tipo: Optional[TipoContato] = None
        self._valor: Optional[str] = None
        self._preferencial: bool = False
        self._aceita_whatsapp: bool = False
        self._aceita_email: bool = True
        self._status: StatusContato = StatusContato.PENDENTE
        self._origem: OrigemContato = OrigemContato.CADASTRO_MANUAL
        self._observacoes: Optional[str] = None
    
    def set_funcionario(
        self,
        funcionario_id: ObjectId,
        documento: str = None,
        nome: str = None
    ) -> "ContatoFuncionarioBuilder":
        """Define o funcionário dono do contato"""
        self._funcionario_id = funcionario_id
        self._funcionario_documento = documento
        self._funcionario_nome = nome
        return self
    
    def set_telefone(
        self, 
        numero: str, 
        whatsapp: bool = False
    ) -> "ContatoFuncionarioBuilder":
        """Define um contato de celular/telefone"""
        # Detectar se é celular ou fixo pelo número de dígitos
        digitos = "".join(filter(str.isdigit, numero))
        if len(digitos) >= 11 or (len(digitos) >= 10 and digitos[2] == "9"):
            self._tipo = TipoContato.CELULAR
        else:
            self._tipo = TipoContato.TELEFONE
        
        self._valor = numero
        self._aceita_whatsapp = whatsapp
        return self
    
    def set_whatsapp(self, numero: str) -> "ContatoFuncionarioBuilder":
        """Define um contato de WhatsApp confirmado"""
        self._tipo = TipoContato.WHATSAPP
        self._valor = numero
        self._aceita_whatsapp = True
        return self
    
    def set_email(
        self, 
        email: str, 
        corporativo: bool = False
    ) -> "ContatoFuncionarioBuilder":
        """Define um contato de e-mail"""
        self._tipo = TipoContato.EMAIL_CORPORATIVO if corporativo else TipoContato.EMAIL_PESSOAL
        self._valor = email
        self._aceita_email = True
        return self
    
    def set_preferencial(self, preferencial: bool = True) -> "ContatoFuncionarioBuilder":
        """Define se é o contato preferencial"""
        self._preferencial = preferencial
        return self
    
    def set_origem(self, origem: OrigemContato) -> "ContatoFuncionarioBuilder":
        """Define a origem do contato"""
        self._origem = origem
        return self
    
    def set_status(self, status: StatusContato) -> "ContatoFuncionarioBuilder":
        """Define o status do contato"""
        self._status = status
        return self
    
    def set_observacoes(self, obs: str) -> "ContatoFuncionarioBuilder":
        """Define observações"""
        self._observacoes = obs
        return self
    
    def build(self) -> ContatoFuncionarioMongoDB:
        """
        Constrói e retorna o contato.
        
        Returns:
            ContatoFuncionarioMongoDB validado
            
        Raises:
            ValueError: Se campos obrigatórios não estiverem preenchidos
        """
        if not self._funcionario_id:
            raise ValueError("funcionario_id é obrigatório")
        if not self._tipo:
            raise ValueError("tipo de contato é obrigatório (use set_telefone, set_email, etc.)")
        if not self._valor:
            raise ValueError("valor do contato é obrigatório")
        
        return ContatoFuncionarioMongoDB(
            funcionario_id=self._funcionario_id,
            funcionario_documento=self._funcionario_documento,
            funcionario_nome=self._funcionario_nome,
            tipo=self._tipo,
            valor=self._valor,
            preferencial=self._preferencial,
            aceita_whatsapp=self._aceita_whatsapp,
            aceita_email=self._aceita_email,
            status=self._status,
            origem=self._origem,
            observacoes=self._observacoes
        )


# ==================== FACTORY METHODS ====================

def criar_contato_de_holerite(
    funcionario_id: ObjectId,
    funcionario_documento: str,
    funcionario_nome: str,
    telefone: str = None,
    email: str = None
) -> List[ContatoFuncionarioMongoDB]:
    """
    Cria contatos a partir de dados extraídos de um holerite.
    Pode retornar 0, 1 ou 2 contatos dependendo dos dados disponíveis.
    
    Args:
        funcionario_id: ObjectId do funcionário
        funcionario_documento: CPF do funcionário
        funcionario_nome: Nome do funcionário
        telefone: Telefone/celular (opcional)
        email: E-mail (opcional)
    
    Returns:
        Lista de contatos criados
    """
    contatos = []
    
    builder_base = ContatoFuncionarioBuilder().set_funcionario(
        funcionario_id=funcionario_id,
        documento=funcionario_documento,
        nome=funcionario_nome
    ).set_origem(OrigemContato.HOLERITE)
    
    if telefone:
        try:
            contato_tel = (ContatoFuncionarioBuilder()
                .set_funcionario(funcionario_id, funcionario_documento, funcionario_nome)
                .set_telefone(telefone, whatsapp=True)  # Assume que aceita WhatsApp
                .set_origem(OrigemContato.HOLERITE)
                .set_preferencial(True)
                .build())
            contatos.append(contato_tel)
        except ValueError:
            pass  # Telefone inválido, ignora
    
    if email:
        try:
            contato_email = (ContatoFuncionarioBuilder()
                .set_funcionario(funcionario_id, funcionario_documento, funcionario_nome)
                .set_email(email, corporativo=False)
                .set_origem(OrigemContato.HOLERITE)
                .set_preferencial(True)
                .build())
            contatos.append(contato_email)
        except ValueError:
            pass  # Email inválido, ignora
    
    return contatos
