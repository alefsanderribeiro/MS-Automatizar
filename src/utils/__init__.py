"""
Utilitários do projeto MS-Automatizar
"""

from src.utils.logger_config import logger
from src.utils.dotenv_path import caminho_dotenv
from src.utils.env_validator import validar_ambiente

# Utilitários de telefone
from src.utils.telefone_utils import (
    normalizar_telefone,
    validar_telefone,
    formatar_para_exibicao,
    limpar_telefone,
    parsear_multiplos_telefones,
    DDDS_VALIDOS,
)

# Utilitários de retry
from src.utils.retry_utils import (
    retry_com_log,
    retry_simples,
    RetryContextManager,
    obter_config_retry,
)

# Utilitários de data (formato DD/MM/YYYY) — conversão nas bordas
from src.utils.data_utils import (
    parse_data_flexivel,
    formatar_data_br,
    formatar_data_hora_br,
    date_para_datetime_inicio,
    date_para_datetime_fim,
)

__all__ = [
    # Logger
    "logger",
    
    # Dotenv
    "caminho_dotenv",
    
    # Validação
    "validar_ambiente",
    
    # Telefone
    "normalizar_telefone",
    "validar_telefone",
    "formatar_para_exibicao",
    "limpar_telefone",
    "parsear_multiplos_telefones",
    "DDDS_VALIDOS",
    
    # Retry
    "retry_com_log",
    "retry_simples",
    "RetryContextManager",
    "obter_config_retry",

    # Data (formato DD/MM/YYYY)
    "parse_data_flexivel",
    "formatar_data_br",
    "formatar_data_hora_br",
    "date_para_datetime_inicio",
    "date_para_datetime_fim",
]
