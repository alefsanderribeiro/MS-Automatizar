"""
Módulo core da interface - componentes reutilizáveis.

Este módulo fornece a infraestrutura base para todos os menus e interfaces
do sistema MS-Automatizar, utilizando questionary + rich para uma experiência
moderna e consistente.

Uso:
    from src.interface.core import (
        MenuBuilder,
        console,
        exibir_sucesso,
        exibir_erro,
        pedir_confirmacao,
        pedir_texto,
    )
"""

from src.interface.core.theme import (
    console,
    ESTILO_QUESTIONARY,
    ICONES,
    TEMA_CUSTOM,
)

from src.interface.core.components import (
    # Classes
    OpcaoMenu,
    MenuBuilder,
    # Exibição
    exibir_cabecalho,
    exibir_sucesso,
    exibir_erro,
    exibir_aviso,
    exibir_info,
    exibir_tabela,
    exibir_resultado,
    exibir_com_spinner,
    exibir_painel,
    limpar_tela,
    # Input
    pausar,
    pedir_confirmacao,
    pedir_texto,
    pedir_selecao,
    pedir_selecao_multipla,
    pedir_data,
    pedir_cpf,
    pedir_inteiro,
)

from src.interface.core.validators import (
    validar_email,
    validar_cnpj,
    validar_cpf,
    validar_telefone,
    validar_mes_ano,
    validar_data,
    parse_data,
)

__all__ = [
    # Theme
    "console",
    "ESTILO_QUESTIONARY",
    "ICONES",
    "TEMA_CUSTOM",
    # Classes
    "OpcaoMenu",
    "MenuBuilder",
    # Exibição
    "exibir_cabecalho",
    "exibir_sucesso",
    "exibir_erro",
    "exibir_aviso",
    "exibir_info",
    "exibir_tabela",
    "exibir_resultado",
    "exibir_com_spinner",
    "exibir_painel",
    "limpar_tela",
    # Input
    "pausar",
    "pedir_confirmacao",
    "pedir_texto",
    "pedir_selecao",
    "pedir_selecao_multipla",
    "pedir_data",
    "pedir_cpf",
    "pedir_inteiro",
    # Validadores
    "validar_email",
    "validar_cnpj",
    "validar_cpf",
    "validar_telefone",
    "validar_mes_ano",
    "validar_data",
    "parse_data",
]
