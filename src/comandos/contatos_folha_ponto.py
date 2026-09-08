"""
Comando CLI para gerenciamento de Contatos de Envio de Folhas de Ponto
"""

import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.services.contatos_folha_ponto_service import contatos_folha_ponto_service
from src.utils.logger_config_v2 import get_logger

logger = get_logger("comando_contatos")
console = Console()


def cmd_contatos_folha_ponto():
    """
    Comando principal para gerenciar contatos de envio de folhas de ponto.
    
    Uso:
        python -m src comandos contatos [opção]
    """
    parser = argparse.ArgumentParser(
        description="Gerencia contatos de envio de folhas de ponto",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python -m src comandos contatos list          # Listar todos os contatos
  python -m src comandos contatos list --empresa "MS Serviços"
  python -m src comandos contatos busca --nome "João"
  python -m src comandos contatos stats         # Ver estatísticas
        """
    )
    
    subparsers = parser.add_subparsers(dest='comando', help='Comandos disponíveis')
    
    # Comando: list
    list_parser = subparsers.add_parser('list', help='Listar contatos')
    list_parser.add_argument('--empresa', help='Filtrar por empresa')
    list_parser.add_argument('--local', help='Filtrar por local/contrato/polo')
    list_parser.add_argument('--envio', choices=['email', 'whatsapp', 'grupo_whatsapp', 'impresso'],
                            help='Filtrar por tipo de envio')
    list_parser.add_argument('--skip', type=int, default=0, help='Pular N registros')
    list_parser.add_argument('--limit', type=int, default=50, help='Limite de registros')
    
    # Comando: busca
    busca_parser = subparsers.add_parser('busca', help='Buscar contato')
    busca_parser.add_argument('--nome', help='Buscar por nome')
    busca_parser.add_argument('--email', help='Buscar por email')
    busca_parser.add_argument('--telefone', help='Buscar por telefone')
    busca_parser.add_argument('--funcionario-id', help='Buscar por ID do funcionário')
    
    # Comando: stats
    subparsers.add_parser('stats', help='Exibir estatísticas')
    
    # Comando: contar
    contar_parser = subparsers.add_parser('contar', help='Contar contatos')
    contar_parser.add_argument('--empresa', help='Contar por empresa')
    contar_parser.add_argument('--local', help='Contar por local')
    
    # Comando: interface
    subparsers.add_parser('interface', help='Abrir interface interativa')
    
    args = parser.parse_args()
    
    if not args.comando:
        parser.print_help()
        return
    
    # Verificar se MongoDB está disponível
    if not contatos_folha_ponto_service.disponivel:
        console.print("[red]Erro: MongoDB não está disponível[/red]")
        return
    
    if args.comando == 'list':
        cmd_listar(args)
    elif args.comando == 'busca':
        cmd_buscar(args)
    elif args.comando == 'stats':
        cmd_estatisticas()
    elif args.comando == 'contar':
        cmd_contar(args)
    elif args.comando == 'interface':
        cmd_interface()


def cmd_listar(args):
    """Lista contatos com filtros"""
    if args.empresa:
        contatos = contatos_folha_ponto_service.listar_por_empresa(
            args.empresa, skip=args.skip, limit=args.limit
        )
        titulo = f"Contatos da empresa: {args.empresa}"
    elif args.local:
        contatos = contatos_folha_ponto_service.listar_por_local(
            args.local, skip=args.skip, limit=args.limit
        )
        titulo = f"Contatos do local: {args.local}"
    elif args.envio:
        contatos = contatos_folha_ponto_service.listar_por_envio(
            args.envio, skip=args.skip, limit=args.limit
        )
        titulo = f"Contatos com envio por: {args.envio}"
    else:
        contatos = contatos_folha_ponto_service.listar_todos(
            skip=args.skip, limit=args.limit
        )
        titulo = "Todos os Contatos"
    
    _exibir_tabela(contatos, titulo)


def cmd_buscar(args):
    """Busca contato"""
    if args.nome:
        contatos = contatos_folha_ponto_service.buscar_por_nome(args.nome)
        titulo = f"Busca por nome: {args.nome}"
    elif args.email:
        contatos = contatos_folha_ponto_service.buscar_por_email(args.email)
        titulo = f"Busca por email: {args.email}"
    elif args.telefone:
        contatos = contatos_folha_ponto_service.buscar_por_telefone(args.telefone)
        titulo = f"Busca por telefone: {args.telefone}"
    elif args.funcionario_id:
        contato = contatos_folha_ponto_service.buscar_por_funcionario_id(args.funcionario_id)
        contatos = [contato] if contato else []
        titulo = f"Busca por ID: {args.funcionario_id}"
    else:
        console.print("[red]Especifique um critério de busca[/red]")
        return
    
    _exibir_tabela(contatos, titulo)


def cmd_estatisticas():
    """Exibe estatísticas"""
    stats = contatos_folha_ponto_service.estatisticas()
    
    if not stats:
        console.print("[yellow]Não foi possível carregar estatísticas[/yellow]")
        return
    
    console.print(Panel("[bold cyan]ESTATÍSTICAS DOS CONTATOS[/bold cyan]", style="cyan"))
    
    # Total geral
    console.print(f"\n[bold]Total de contatos:[/bold] {stats.get('total', 0)}")
    
    # Por empresa
    empresas = stats.get("por_empresa", [])
    if empresas:
        console.print("\n[bold]Por Empresa:[/bold]")
        table_empresas = Table(show_header=True, header_style="bold cyan")
        table_empresas.add_column("Empresa")
        table_empresas.add_column("Quantidade", justify="right")
        
        for empresa in empresas[:10]:
            table_empresas.add_row(
                empresa.get("empresa", "N/A"),
                str(empresa.get("count", 0))
            )
        
        console.print(table_empresas)
    
    # Por local
    locais = stats.get("por_local", [])
    if locais:
        console.print("\n[bold]Por Local:[/bold]")
        table_locais = Table(show_header=True, header_style="bold cyan")
        table_locais.add_column("Local")
        table_locais.add_column("Quantidade", justify="right")
        
        for local in locais[:10]:
            table_locais.add_row(
                local.get("local", "N/A"),
                str(local.get("count", 0))
            )
        
        console.print(table_locais)
    
    # Por tipo de envio
    envios = stats.get("por_envio", {})
    if envios:
        console.print("\n[bold]Por Tipo de Envio:[/bold]")
        console.print(f"  📧 Email: {envios.get('email', 0)}")
        console.print(f"  💬 WhatsApp: {envios.get('whatsapp', 0)}")
        console.print(f"  👥 Grupo WhatsApp: {envios.get('grupo_whatsapp', 0)}")
        console.print(f"  📄 Impresso: {envios.get('impresso', 0)}")


def cmd_contar(args):
    """Conta contatos"""
    if args.empresa:
        count = contatos_folha_ponto_service.contar_por_empresa(args.empresa)
        console.print(f"Contatos da empresa '{args.empresa}': {count}")
    elif args.local:
        count = contatos_folha_ponto_service.contar_por_local(args.local)
        console.print(f"Contatos do local '{args.local}': {count}")
    else:
        count = contatos_folha_ponto_service.contar()
        console.print(f"Total de contatos: {count}")


def cmd_interface():
    """Abre interface interativa"""
    from src.interface.interface_contatos_folha_ponto import InterfaceContatosFolhaPonto
    InterfaceContatosFolhaPonto()


def _exibir_tabela(contatos, titulo):
    """Exibe tabela de contatos"""
    if not contatos:
        console.print("[yellow]Nenhum contato encontrado[/yellow]")
        return
    
    table = Table(title=titulo, show_header=True, header_style="bold cyan")
    
    table.add_column("ID", style="dim", width=10)
    table.add_column("Nome", style="bold")
    table.add_column("Empresa", style="green")
    table.add_column("Email", style="blue")
    table.add_column("Telefone", style="magenta")
    table.add_column("Envios", style="yellow")
    
    for contato in contatos:
        # Montar flags de envio
        envios = []
        if contato.get("enviar_email"):
            envios.append("📧")
        if contato.get("enviar_whatsapp"):
            envios.append("💬")
        if contato.get("enviar_grupo_whatsapp"):
            envios.append("👥")
        if contato.get("enviar_impresso"):
            envios.append("📄")
        
        table.add_row(
            str(contato.get("_id", ""))[:8],
            contato.get("nome", ""),
            contato.get("empresa", ""),
            contato.get("email", ""),
            contato.get("telefone", ""),
            " ".join(envios) if envios else "-"
        )
    
    console.print(table)
