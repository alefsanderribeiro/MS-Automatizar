"""
Menu principal do sistema MS-Automatizar.

Este módulo fornece a interface interativa principal do programa,
incluindo o menu de entrada e navegação para os demais módulos.
"""

import os

from src.utils.logger_config import logger

# Carrega metadados do pacote a partir do __init__.py raiz, sem depender
# de hack de sys.path (importlib via caminho absoluto evita identidade duplicada).
def _carregar_metadados() -> dict:
    import importlib.util
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[2]
    arquivo_init = raiz / "__init__.py"
    try:
        spec = importlib.util.spec_from_file_location("ms_automatizar_meta", arquivo_init)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return {
            "version": getattr(modulo, "__version__", "0.0.0"),
            "autor": getattr(modulo, "__autor__", ""),
            "email": getattr(modulo, "__email__", ""),
            "github": getattr(modulo, "__github__", ""),
        }
    except Exception as e:
        logger.warning(f"Nao foi possivel carregar metadados do pacote: {e}")
        return {"version": "0.0.0", "autor": "", "email": "", "github": ""}


_METADADOS = _carregar_metadados()
__version__ = _METADADOS["version"]
__autor__ = _METADADOS["autor"]
__email__ = _METADADOS["email"]
__github__ = _METADADOS["github"]

# Imports do novo sistema de interface
from src.interface.core.components import (
    MenuBuilder,
    exibir_cabecalho,
    exibir_sucesso,
    exibir_erro,
    exibir_aviso,
    exibir_info,
    exibir_painel,
    limpar_tela,
    pausar,
)
from src.interface.core.theme import console, ICONES


# ═══════════════════════════════════════════════════════════════
# LOGO E APRESENTAÇÃO
# ═══════════════════════════════════════════════════════════════

LOGO = """
[cyan]
               AAA               lllllll                        ffffffffffffffff
              A:::A              l:::::l                       f::::::::::::::::f
             A:::::A             l:::::l                      f::::::::::::::::::f
            A:::::::A            l:::::l                      f::::::fffffff:::::f
           A:::::::::A            l::::l     eeeeeeeeeeee     f:::::f       ffffffeeeeeeeeeeee
          A:::::A:::::A           l::::l   ee::::::::::::ee   f:::::f           ee::::::::::::ee
         A:::::A A:::::A          l::::l  e::::::eeeee:::::eef:::::::ffffff    e::::::eeeee:::::ee
        A:::::A   A:::::A         l::::l e::::::e     e:::::ef::::::::::::f   e::::::e     e:::::e
       A:::::A     A:::::A        l::::l e:::::::eeeee::::::ef::::::::::::f   e:::::::eeeee::::::e
      A:::::AAAAAAAAA:::::A       l::::l e:::::::::::::::::e f:::::::ffffff   e:::::::::::::::::e
     A:::::::::::::::::::::A      l::::l e::::::eeeeeeeeeee   f:::::f         e::::::eeeeeeeeeee
    A:::::AAAAAAAAAAAAA:::::A     l::::l e:::::::e            f:::::f         e:::::::e
   A:::::A             A:::::A   l::::::le::::::::e          f:::::::f        e::::::::e
  A:::::A               A:::::A  l::::::l e::::::::eeeeeeee  f:::::::f         e::::::::eeeeeeee
 A:::::A                 A:::::A l::::::l  ee:::::::::::::e  f:::::::f          ee:::::::::::::e
AAAAAAA                   AAAAAAAllllllll    eeeeeeeeeeeeee  fffffffff            eeeeeeeeeeeeee
[/cyan]
"""


def _verificar_ambiente_startup() -> dict:
    """
    Verifica ambiente e conexões no startup.

    Returns:
        Dict com status do sistema (ambiente_valido, mongodb_conectado, avisos).
    """
    status = {
        "ambiente_valido": False,
        "mongodb_conectado": False,
        "avisos": []
    }

    # Verificar variáveis de ambiente
    try:
        from src.utils.env_validator import validar_ambiente
        status["ambiente_valido"] = validar_ambiente(strict=False, exibir_resumo=False)
        if not status["ambiente_valido"]:
            status["avisos"].append("Algumas variáveis de ambiente não estão configuradas")
    except Exception as e:
        logger.warning(f"Erro ao validar ambiente: {e}")
        status["avisos"].append(f"Erro ao validar ambiente: {e}")

    # Verificar conexão MongoDB
    try:
        from src.services.mongodb_connection import verificar_conexao_mongodb, mongodb_pool
        status["mongodb_conectado"] = verificar_conexao_mongodb()
        if status["mongodb_conectado"]:
            health = mongodb_pool.health_check()
            logger.debug(f"MongoDB conectado (latência: {health.get('latencia_ms', 'N/A')}ms)")
    except Exception as e:
        logger.warning(f"Erro ao verificar MongoDB: {e}")
        status["avisos"].append(f"Erro ao verificar MongoDB: {e}")

    return status


def _exibir_status_sistema(status: dict) -> None:
    """
    Exibe o status do sistema no startup.

    Args:
        status: Dict com status do sistema.
    """
    # Monta conteúdo do painel
    ambiente_icon = ICONES["sucesso"] if status["ambiente_valido"] else ICONES["aviso"]
    ambiente_status = "[green]OK[/green]" if status["ambiente_valido"] else "[yellow]Incompleto[/yellow]"

    mongo_icon = ICONES["sucesso"] if status["mongodb_conectado"] else ICONES["erro"]
    mongo_status = "[green]Conectado[/green]" if status["mongodb_conectado"] else "[red]Desconectado[/red]"

    conteudo = f"""
{ambiente_icon} Ambiente: {ambiente_status}
{mongo_icon} MongoDB: {mongo_status}
"""

    if status["avisos"]:
        conteudo += f"\n[yellow]{ICONES['aviso']} Avisos:[/yellow]\n"
        for aviso in status["avisos"]:
            conteudo += f"   • {aviso}\n"

    exibir_painel(conteudo, titulo="Status do Sistema", estilo_borda="blue")


def _exibir_apresentacao() -> None:
    """Exibe a apresentação do programa."""
    limpar_tela()
    console.print(LOGO)

    info = f"""
[bold cyan]Versão:[/bold cyan] {__version__}
[bold cyan]Autor:[/bold cyan] {__autor__}
[bold cyan]Email:[/bold cyan] {__email__}
[bold cyan]GitHub:[/bold cyan] {__github__}

[dim]Seja Bem-vindo ao Automatiza MS!
Este programa automatiza processos manuais da empresa Moraes e Santos.
Você pode fazer várias operações com Folhas de Pontos ou Holerites dos seus funcionários.[/dim]
"""
    exibir_painel(info, titulo="MS-Automatizar", estilo_borda="cyan")


# ═══════════════════════════════════════════════════════════════
# SUBMENUS
# ═══════════════════════════════════════════════════════════════

def _abrir_folha_ponto() -> None:
    """Abre o menu de Folha de Ponto."""
    from src.interface.interface_folha_de_ponto import Interface_Folha_de_Ponto
    logger.debug("Iniciando operações com Folha de Ponto")
    Interface_Folha_de_Ponto()


def _abrir_holerite() -> None:
    """Abre o menu de Holerite."""
    from src.interface.interface_holerite import Interface_Holerite
    logger.debug("Iniciando operações com Holerite")
    Interface_Holerite()


def _abrir_funcionarios() -> None:
    """Abre o menu de Funcionários."""
    from src.interface.interface_funcionarios import Interface_Funcionarios
    logger.debug("Iniciando operações com Funcionários")
    Interface_Funcionarios()


def _abrir_empresas() -> None:
    """Abre o menu de Empresas."""
    from src.interface.interface_empresas import Interface_Empresas
    logger.debug("Iniciando gerenciamento de Empresas")
    Interface_Empresas()


def _abrir_referencias() -> None:
    """Abre o menu de Referências."""
    from src.interface.interface_referencias import Interface_Referencias
    logger.debug("Iniciando operações com Referências")
    Interface_Referencias()


def _abrir_configuracoes() -> None:
    """Abre o menu de Configurações."""
    from src.interface.interface_configuracoes import Interface_Configuracoes
    logger.debug("Iniciando menu de Configurações")
    Interface_Configuracoes()


# ═══════════════════════════════════════════════════════════════
# MENUS PRINCIPAIS
# ═══════════════════════════════════════════════════════════════

def menu_gerenciar_dados() -> None:
    """Submenu para gerenciamento de dados (Funcionários, Empresas, etc.)."""
    (
        MenuBuilder("GERENCIAR DADOS", ICONES["dados"])
        .adicionar("Funcionários", _abrir_funcionarios, ICONES["funcionarios"])
        .adicionar("Empresas", _abrir_empresas, ICONES["empresa"])
        .adicionar("Referências (Funções, Horários, etc.)", _abrir_referencias, ICONES["config"])
        .com_voltar("Voltar ao Menu Principal")
        .executar()
    )


def menu_interface() -> None:
    """Menu principal do programa - interface interativa."""
    (
        MenuBuilder("MENU PRINCIPAL", ICONES["home"])
        .adicionar("Operações com Folha de Ponto", _abrir_folha_ponto, ICONES["folha_ponto"])
        .adicionar("Operações com Holerite", _abrir_holerite, ICONES["holerite"])
        .separador()
        .adicionar("Gerenciar Dados", menu_gerenciar_dados, ICONES["dados"])
        .adicionar("Configurações", _abrir_configuracoes, ICONES["config"])
        .com_voltar("Sair")
        .executar()
    )

    # Mensagem de encerramento
    console.print("\n[dim]Programa finalizado. Até logo![/dim]\n")


def init_interface() -> None:
    """
    Inicia o programa em modo interativo.

    Esta é a função principal de entrada que:
    1. Exibe a apresentação
    2. Verifica o ambiente e conexões
    3. Inicia o menu principal
    """
    _exibir_apresentacao()

    # Verificar ambiente e conexões
    status = _verificar_ambiente_startup()
    _exibir_status_sistema(status)

    pausar("Pressione ENTER para continuar...")

    menu_interface()


# ═══════════════════════════════════════════════════════════════
# FUNÇÕES LEGADAS (mantidas para compatibilidade)
# ═══════════════════════════════════════════════════════════════

def verificar_ambiente_startup() -> dict:
    """
    Função legada - use _verificar_ambiente_startup().

    Mantida para compatibilidade com código existente.
    """
    return _verificar_ambiente_startup()


def exibir_status_sistema(status: dict) -> None:
    """
    Função legada - use _exibir_status_sistema().

    Mantida para compatibilidade com código existente.
    """
    _exibir_status_sistema(status)


def Apresentação() -> str:
    """
    Função legada - use _exibir_apresentacao().

    Mantida para compatibilidade com código existente.

    Returns:
        String com a apresentação formatada.
    """
    return f"""
    By: {"".center(50, "—")}
    {LOGO}
    Versão: {__version__}
    Autor: {__autor__}
    Email: {__email__}
    GitHub: {__github__}
    {"".center(50, "—")}
    Seja Bem-vindo ao Automatiza MS!
    Este programa automatiza processos manuais da empresa Moraes e Santos.
    Você pode fazer várias operações com Folhas de Pontos ou Holerites dos seus funcionários.
    Você pode usar o comando --help ou -h para ver todas as opções disponíveis.
    Caso não escolha nenhuma opção na inicialização, o programa será iniciado em modo interativo.
    {"".center(50, "—")}
    """
