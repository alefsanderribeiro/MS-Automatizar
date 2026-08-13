"""
Modelos Pydantic para o projeto MS-Automatizar
"""

# Modelos de Funcionário
from .funcionario_models import (
    TipoContrato,
    StatusFuncionario,
    FuncionarioMongoDB,
    FuncionarioBuilder,
)

# Modelos de Folha de Ponto
from .folha_de_ponto_models import (
    DiaSemana,
    DiaFolhaPonto,
    AnaliseIAResultado,
    FolhaDePontoData,
    FolhaDePontoMongoDB,
)

# Modelos de Empresa
from .empresa_models import (
    StatusEmpresa,
    EmpresaMongoDB,
    EmpresaBuilder,
)

# Modelos de Diretório
from .diretorio_models import (
    DiretorioMongoDB,
    DiretorioBuilder,
    DIRETORIO_PADRAO,
)

# Modelos de Envio de Folha de Ponto
from .envio_folha_ponto_models import (
    TipoEnvioEnum,
    StatusEnvioEnum,
    EnvioFolhaPontoMongoDB,
    EnvioFolhaPontoBuilder,
)

# Modelos de Configuração de Envio de Folha de Ponto
from .config_envio_folha_ponto_models import (
    SimNaoEnum,
    OrigemConfigEnum,
    ConfigEnvioFolhaPontoMongoDB,
    ConfigEnvioFolhaPontoBuilder,
)

# Modelos de Template de Mensagem
from .template_mensagem_models import (
    TipoTemplateEnum,
    StatusTemplate,
    TemplateMensagemMongoDB,
    criar_templates_padrao,
)

# Modelos de Grupo WhatsApp
from .grupo_whatsapp_models import (
    StatusGrupo,
    GrupoWhatsAppMongoDB,
    GrupoWhatsAppBuilder,
)

__all__ = [
    # Funcionário
    "TipoContrato",
    "StatusFuncionario",
    "FuncionarioMongoDB",
    "FuncionarioBuilder",
    
    # Folha de Ponto
    "DiaSemana",
    "DiaFolhaPonto",
    "AnaliseIAResultado",
    "FolhaDePontoData",
    "FolhaDePontoMongoDB",
    
    # Empresa
    "StatusEmpresa",
    "EmpresaMongoDB",
    "EmpresaBuilder",
    
    # Diretório
    "DiretorioMongoDB",
    "DiretorioBuilder",
    "DIRETORIO_PADRAO",
    
    # Envio de Folha de Ponto
    "TipoEnvioEnum",
    "StatusEnvioEnum",
    "EnvioFolhaPontoMongoDB",
    "EnvioFolhaPontoBuilder",

    # Configuração de Envio de Folha de Ponto
    "SimNaoEnum",
    "OrigemConfigEnum",
    "ConfigEnvioFolhaPontoMongoDB",
    "ConfigEnvioFolhaPontoBuilder",
    
    # Template de Mensagem
    "TipoTemplateEnum",
    "StatusTemplate",
    "TemplateMensagemMongoDB",
    "criar_templates_padrao",
    
    # Grupo WhatsApp
    "StatusGrupo",
    "GrupoWhatsAppMongoDB",
    "GrupoWhatsAppBuilder",
]
