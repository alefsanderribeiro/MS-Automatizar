"""
Modelos Pydantic para Templates de Mensagem
Estrutura para armazenamento em MongoDB
Permite personalização de mensagens por tipo de envio
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum


class TipoTemplateEnum(str, Enum):
    """Tipos de template disponíveis"""
    # Folha de Ponto
    EMAIL = "email"
    WHATSAPP_GRUPO = "whatsapp_grupo"
    WHATSAPP_INDIVIDUAL = "whatsapp_individual"
    # Holerite
    EMAIL_HOLERITE = "email_holerite"
    WHATSAPP_GRUPO_HOLERITE = "whatsapp_grupo_holerite"
    WHATSAPP_INDIVIDUAL_HOLERITE = "whatsapp_individual_holerite"


class StatusTemplate(str, Enum):
    """Status do template"""
    ATIVO = "ativo"
    INATIVO = "inativo"


class TemplateMensagemMongoDB(BaseModel):
    """
    Modelo de Template de Mensagem para armazenamento em MongoDB
    
    Placeholders disponíveis para uso no corpo da mensagem:
    - {nome}: Nome do destinatário (para mensagens individuais)
    - {mes}: Número do mês (01-12)
    - {ano}: Ano (ex: 2026)
    - {mes_extenso}: Nome do mês por extenso (ex: Janeiro)
    - {local}: Local/Contrato/Polo
    - {empresa}: Nome da empresa
    """
    
    # ==================== IDENTIFICAÇÃO ====================
    
    nome: str = Field(
        ...,
        description="Nome identificador do template (ex: 'Email Formal', 'WhatsApp Grupo Padrão')"
    )
    
    tipo: TipoTemplateEnum = Field(
        ...,
        description="Tipo de envio para o qual este template se aplica"
    )
    
    descricao: Optional[str] = Field(
        default=None,
        description="Descrição do template e quando usar"
    )
    
    # ==================== CONTEÚDO ====================
    
    assunto: Optional[str] = Field(
        default=None,
        description="Assunto do email (apenas para tipo EMAIL). Suporta placeholders."
    )
    
    corpo_mensagem: str = Field(
        ...,
        description="Corpo da mensagem com placeholders. Ex: 'Olá {nome}, segue a folha de ponto de {mes_extenso}/{ano}'"
    )
    
    
    # ==================== CONFIGURAÇÕES ====================
    
    is_padrao: bool = Field(
        default=False,
        description="Se é o template padrão para este tipo de envio"
    )
    
    status: StatusTemplate = Field(
        default=StatusTemplate.ATIVO,
        description="Status do template"
    )
    
    # Para busca
    nome_normalizado: Optional[str] = Field(
        default=None,
        description="Nome normalizado (minúsculas, sem acentos) para busca"
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
    
    versao: int = Field(default=1, description="Versão do documento")
    
    historico_alteracoes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Lista de alterações realizadas"
    )
    
    # ==================== VALIDADORES ====================
    
    @validator('nome')
    def validar_nome_nao_vazio(cls, v: str) -> str:
        """Nome não pode ser vazio"""
        if not v or not v.strip():
            raise ValueError("Nome do template não pode ser vazio")
        return v.strip()
    
    @validator('corpo_mensagem')
    def validar_corpo_nao_vazio(cls, v: str) -> str:
        """Corpo da mensagem não pode ser vazio"""
        if not v or not v.strip():
            raise ValueError("Corpo da mensagem não pode ser vazio")
        return v.strip()
    
    @validator('assunto')
    def validar_assunto_para_email(cls, v: Optional[str], values: Dict) -> Optional[str]:
        """Assunto é obrigatório para templates de email"""
        tipo = values.get('tipo')
        if tipo == TipoTemplateEnum.EMAIL and (not v or not v.strip()):
            raise ValueError("Assunto é obrigatório para templates de email")
        return v.strip() if v else None
    
    @validator('nome_normalizado', pre=True, always=True)
    def normalizar_nome(cls, v: str, values: Dict) -> str:
        """Normaliza o nome para busca"""
        if 'nome' in values:
            nome = values['nome']
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
        """Adiciona entrada ao histórico de alterações"""
        entrada = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "acao": acao,
            "versao_anterior": self.versao,
            "versao_nova": self.versao + 1,
            "detalhes": detalhes or {}
        }
        self.historico_alteracoes.append(entrada)
    
    def renderizar(self, contexto: Dict[str, Any]) -> Dict[str, str]:
        """
        Renderiza o template substituindo os placeholders
        
        Args:
            contexto: Dicionário com valores para os placeholders
                - nome: Nome do destinatário
                - mes: Número do mês
                - ano: Ano
                - mes_extenso: Nome do mês por extenso
                - local: Local/Contrato/Polo
                - empresa: Nome da empresa
        
        Returns:
            Dict com 'assunto' (se email) e 'mensagem' renderizados
        """
        # Mapear número do mês para nome extenso
        meses_extenso = {
            1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
            5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
            9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
        }
        
        # Adicionar mes_extenso se não fornecido mas mes está presente
        if 'mes' in contexto and 'mes_extenso' not in contexto:
            mes_num = int(contexto['mes'])
            contexto['mes_extenso'] = meses_extenso.get(mes_num, str(mes_num))
        
        # Formatar mês com zero à esquerda se necessário
        if 'mes' in contexto:
            contexto['mes'] = str(contexto['mes']).zfill(2)
        
        # Renderizar corpo da mensagem
        mensagem = self.corpo_mensagem
        for placeholder, valor in contexto.items():
            mensagem = mensagem.replace(f"{{{placeholder}}}", str(valor))
        
        resultado = {"mensagem": mensagem}
        
        # Renderizar assunto se for email
        if self.assunto:
            assunto = self.assunto
            for placeholder, valor in contexto.items():
                assunto = assunto.replace(f"{{{placeholder}}}", str(valor))
            resultado["assunto"] = assunto
        
        return resultado
    
    def marcar_como_padrao(self) -> None:
        """Marca este template como padrão"""
        self.is_padrao = True
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico("Marcado como template padrão")
    
    def inativar(self) -> None:
        """Inativa o template"""
        self.status = StatusTemplate.INATIVO
        self.is_padrao = False
        self.versao += 1
        self.atualizado_em = datetime.now(timezone.utc)
        self.adicionar_historico("Template inativado")


# ==================== TEMPLATES PADRÃO ====================

def criar_templates_padrao() -> List[Dict[str, Any]]:
    """
    Retorna lista de templates padrão para inicialização
    
    Returns:
        Lista de dicionários com dados dos templates padrão
    """
    return [
        {
            "nome": "Email Formal Folha de Ponto",
            "tipo": TipoTemplateEnum.EMAIL,
            "descricao": "Template formal para envio de folhas de ponto por email",
            "assunto": "Folha de Ponto - {mes_extenso}/{ano} - {local}",
            "corpo_mensagem": """Bom dia,

Segue anexo das folhas de ponto referente ao mês de {mes}/{ano}.

Atenciosamente,
""",
            "is_padrao": True,
        },
        {
            "nome": "WhatsApp Grupo Padrão",
            "tipo": TipoTemplateEnum.WHATSAPP_GRUPO,
            "descricao": "Template para envio em grupos de WhatsApp",
            "assunto": None,
            "corpo_mensagem": """Bom dia!

Seguem as folhas de ponto referente ao mês de {mes_extenso}/{ano}.

Atenciosamente,
""",
            "is_padrao": True,
        },
        {
            "nome": "WhatsApp Individual Personalizado",
            "tipo": TipoTemplateEnum.WHATSAPP_INDIVIDUAL,
            "descricao": "Template personalizado para envio individual no WhatsApp",
            "assunto": None,
            "corpo_mensagem": """Olá {nome},

Segue a folha de ponto referente ao mês de {mes_extenso}/{ano}.

Qualquer dúvida, estou à disposição.

Atenciosamente,
""",
            "is_padrao": True,
        },
        # ==================== HOLERITES ====================
        {
            "nome": "Email Recibo de Pagamento",
            "tipo": TipoTemplateEnum.EMAIL_HOLERITE,
            "descricao": "Template formal para envio de holerites/recibos de pagamento por email",
            "assunto": "Recibo de Pagamento - {mes}/{ano} - {local}",
            "corpo_mensagem": """Bom dia,

Segue anexo do(s) recibo(s) de pagamento referente ao mês de {mes_extenso}/{ano}.

Atenciosamente,
""",
            "is_padrao": True,
        },
        {
            "nome": "WhatsApp Grupo Holerite",
            "tipo": TipoTemplateEnum.WHATSAPP_GRUPO_HOLERITE,
            "descricao": "Template para envio de holerites em grupos de WhatsApp",
            "assunto": None,
            "corpo_mensagem": """Bom dia!

Seguem os recibos de pagamento referente ao mês de {mes_extenso}/{ano}.

Atenciosamente,
""",
            "is_padrao": True,
        },
        {
            "nome": "WhatsApp Individual Holerite",
            "tipo": TipoTemplateEnum.WHATSAPP_INDIVIDUAL_HOLERITE,
            "descricao": "Template personalizado para envio de holerite individual no WhatsApp (via MongoDB)",
            "assunto": None,
            "corpo_mensagem": """Olá {nome},

Segue seu recibo de pagamento referente ao mês de {mes_extenso}/{ano}.

Qualquer dúvida, estou à disposição.

Atenciosamente,
""",
            "is_padrao": True,
        },
    ]
