
import argparse
from src.utils.logger_config_v2 import get_logger

# Logger do módulo
logger = get_logger("comando")

from src.comandos.folha_de_ponto import folha_de_ponto_subcommands, handle_folha_de_ponto
from src.comandos.holerite import holerite_subcommands, handle_holerite
from src.comandos.referencias import (
    listar_contratos, adicionar_contrato_interativo, inativar_contrato,
    listar_horarios, adicionar_horario_interativo, inativar_horario,
    listar_funcoes, adicionar_funcao_interativo, inativar_funcao,
    exibir_estatisticas
)
from src.comandos.diretorios import (
    listar_diretorios, adicionar_diretorio_interativo, inativar_diretorio,
    criar_diretorio_para_contrato, atualizar_diretorio_interativo,
    exibir_estatisticas_diretorios, criar_diretorios_todos_contratos
)
from src.comandos.contatos_folha_ponto import (
    contatos_subcommands, handle_contatos
)




def referencias_subcommands(subparsers):
    """
    Adiciona subcomandos para gerenciar referências (contratos, horários, funções)
    """
    referencias = subparsers.add_parser('referencias', help='Gerenciar contratos, horários e funções')
    referencias_subs = referencias.add_subparsers(dest='referencias_command', help='Operações com referências')
    
    # Estatísticas
    referencias_subs.add_parser('stats', help='Exibir estatísticas das coleções')
    
    # CONTRATOS
    contrato_list = referencias_subs.add_parser('contratos', help='Listar contratos')
    contrato_list.add_argument('--ativos', action='store_true', help='Apenas contratos ativos')
    contrato_list.add_argument('--json', action='store_true', help='Formato JSON')
    
    referencias_subs.add_parser('contrato-add', help='Adicionar contrato (interativo)')
    
    contrato_del = referencias_subs.add_parser('contrato-inativar', help='Inativar contrato')
    contrato_del.add_argument('id', help='ID do contrato (ObjectId)')
    
    # HORÁRIOS
    horario_list = referencias_subs.add_parser('horarios', help='Listar horários')
    horario_list.add_argument('--ativos', action='store_true', help='Apenas horários ativos')
    horario_list.add_argument('--json', action='store_true', help='Formato JSON')
    
    referencias_subs.add_parser('horario-add', help='Adicionar horário (interativo)')
    
    horario_del = referencias_subs.add_parser('horario-inativar', help='Inativar horário')
    horario_del.add_argument('id', help='ID do horário (ObjectId)')
    
    # FUNÇÕES
    funcao_list = referencias_subs.add_parser('funcoes', help='Listar funções')
    funcao_list.add_argument('--ativos', action='store_true', help='Apenas funções ativas')
    funcao_list.add_argument('--json', action='store_true', help='Formato JSON')
    funcao_list.add_argument('--categoria', help='Filtrar por categoria')
    
    referencias_subs.add_parser('funcao-add', help='Adicionar função (interativo)')
    
    funcao_del = referencias_subs.add_parser('funcao-inativar', help='Inativar função')
    funcao_del.add_argument('id', help='ID da função (ObjectId)')


def handle_referencias(args, parser):
    """
    Handler para comandos de referências
    """
    if not args.referencias_command:
        parser.print_help()
        return
    
    cmd = args.referencias_command
    
    # Estatísticas
    if cmd == 'stats':
        exibir_estatisticas()
    
    # CONTRATOS
    elif cmd == 'contratos':
        formato = 'json' if args.json else 'tabela'
        listar_contratos(apenas_ativos=args.ativos, formato=formato)
    
    elif cmd == 'contrato-add':
        adicionar_contrato_interativo()
    
    elif cmd == 'contrato-inativar':
        inativar_contrato(args.id)
    
    # HORÁRIOS
    elif cmd == 'horarios':
        formato = 'json' if args.json else 'tabela'
        listar_horarios(apenas_ativos=args.ativos, formato=formato)
    
    elif cmd == 'horario-add':
        adicionar_horario_interativo()
    
    elif cmd == 'horario-inativar':
        inativar_horario(args.id)
    
    # FUNÇÕES
    elif cmd == 'funcoes':
        formato = 'json' if args.json else 'tabela'
        listar_funcoes(apenas_ativos=args.ativos, formato=formato, categoria=args.categoria if hasattr(args, 'categoria') else None)
    
    elif cmd == 'funcao-add':
        adicionar_funcao_interativo()
    
    elif cmd == 'funcao-inativar':
        inativar_funcao(args.id)


def contatos_subcommands(subparsers):
    """
    Adiciona subcomandos para gerenciar contatos de envio de folha de ponto.
    """
    contatos = subparsers.add_parser('contatos', help='Gerenciar contatos de envio de folha de ponto')


def diretorios_subcommands(subparsers):
    """
    Adiciona subcomandos para gerenciar diretórios (paridade CLI/TUI).
    """
    diretorios = subparsers.add_parser('diretorios', help='Gerenciar diretórios')
    diretorios_subs = diretorios.add_subparsers(dest='diretorios_command', help='Operações com diretórios')

    diretorio_list = diretorios_subs.add_parser('listar', help='Listar diretórios')
    diretorio_list.add_argument('--ativos', action='store_true', help='Apenas diretórios ativos')
    diretorio_list.add_argument('--json', action='store_true', help='Formato JSON')

    diretorios_subs.add_parser('estatisticas', help='Exibir estatísticas dos diretórios')
    diretorios_subs.add_parser('adicionar', help='Adicionar diretório (interativo)')
    diretorios_subs.add_parser('atualizar', help='Atualizar diretório (interativo)')
    diretorios_subs.add_parser('criar-para-contrato', help='Criar diretório para contrato (interativo)')
    diretorios_subs.add_parser('criar-todos', help='Criar diretórios para TODOS os contratos')

    diretorio_del = diretorios_subs.add_parser('inativar', help='Inativar diretório')
    diretorio_del.add_argument('id', help='ID do diretório (ObjectId)')


def handle_diretorios(args, parser):
    """
    Handler para comandos de diretórios.
    """
    if not args.diretorios_command:
        parser.print_help()
        return

    cmd = args.diretorios_command

    if cmd == 'listar':
        formato = 'json' if getattr(args, 'json', False) else 'tabela'
        listar_diretorios(apenas_ativos=getattr(args, 'ativos', False), formato=formato)

    elif cmd == 'estatisticas':
        exibir_estatisticas_diretorios()

    elif cmd == 'adicionar':
        adicionar_diretorio_interativo()

    elif cmd == 'atualizar':
        atualizar_diretorio_interativo()

    elif cmd == 'criar-para-contrato':
        criar_diretorio_para_contrato()

    elif cmd == 'criar-todos':
        criar_diretorios_todos_contratos()

    elif cmd == 'inativar':
        inativar_diretorio(args.id)


def start_command():
    parser = argparse.ArgumentParser(description="Automatizar tarefas com Python na empresa Moraes e Santos")
    subparsers = parser.add_subparsers(dest='command', help='Comandos principais')
    
    folha_de_ponto_subcommands(subparsers)
    holerite_subcommands(subparsers)
    referencias_subcommands(subparsers)
    diretorios_subcommands(subparsers)
    contatos_subcommands(subparsers)
    
    args = parser.parse_args()
    
    logger.info(f"Comando CLI iniciado: {vars(args)}")
    
    if not any(vars(args).values()):
        from src.interface.menu import init_interface
        init_interface()
        
    else:
        
        if args.command == 'folha_de_ponto':

            handle_folha_de_ponto(args, parser)
            
        elif args.command == 'holerite':

            handle_holerite(args, parser)
        
        elif args.command == 'referencias':
            
            handle_referencias(args, parser)

        elif args.command == 'diretorios':

            handle_diretorios(args, parser)

        elif args.command == 'contatos':

            handle_contatos(args, parser)
            






    
    
    

