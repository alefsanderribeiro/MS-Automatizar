from pathlib import Path
from src.holerite import Holerite
from src.utils.logger_config_v2 import get_logger


# Logger do módulo
logger = get_logger("comando")

def arquivo_arguments(parser):
    parser.add_argument('--arquivo', type=str, help='Informa o arquivo.')


def holerite_subcommands(subparsers):
    parser_holerite = subparsers.add_parser('holerite', help='Comando para os recibos de pagamento (Holerites)')
    subparsers_holerite = parser_holerite.add_subparsers(dest='subcommand', help='Subcomandos para Holerite')

    # Subcomando: renomear_arquivos
    parser_holerite_sub1 = subparsers_holerite.add_parser('renomear_arquivos', help='Renomeia os arquivos de um diretório informado.')
    parser_holerite_sub1.add_argument('--diretório', default=None, type=str, help='Informa o diretório em que será salvo o arquivo criado')
    parser_holerite_sub1.add_argument('--mês_ano', default=None, type=str, help='Filtra arquivos por mês e ano no formato MM.AAAA (ex: 01.2025)')
    
    # Subcomando: processar_pdfs (NOVO)
    parser_processar = subparsers_holerite.add_parser('processar_pdfs', help='Processa PDFs de holerites com IA (Gemini) e salva no MongoDB.')
    parser_processar.add_argument('--caminho', required=True, type=str, help='Caminho do diretório ou arquivo PDF a processar')
    parser_processar.add_argument('--empresa_id', default=None, type=str, help='ObjectId da empresa (opcional)')
    parser_processar.add_argument('--temperatura', default=0.1, type=float, help='Temperatura do modelo Gemini (0.0 a 1.0)')
    
    # Subcomando: enviar (NOVO)
    parser_enviar = subparsers_holerite.add_parser('enviar', help='Envia holerites por e-mail e/ou WhatsApp.')
    parser_enviar.add_argument('--competencia', required=True, type=str, help='Competência no formato MM/AAAA (ex: 01/2025)')
    parser_enviar.add_argument('--modo', default='mongodb', choices=['mongodb', 'planilha'], help='Modo de envio: mongodb (usa contatos do banco) ou planilha')
    parser_enviar.add_argument('--canais', default='email,whatsapp', type=str, help='Canais de envio separados por vírgula (email,whatsapp)')
    parser_enviar.add_argument('--dry_run', action='store_true', help='Apenas simula o envio, sem enviar de fato')
    parser_enviar.add_argument('--empresa_id', default=None, type=str, help='Filtrar por empresa (ObjectId)')
    
    # Subcomando: listar (NOVO)
    parser_listar = subparsers_holerite.add_parser('listar', help='Lista holerites salvos no MongoDB.')
    parser_listar.add_argument('--competencia', default=None, type=str, help='Filtrar por competência (MM/AAAA)')
    parser_listar.add_argument('--funcionario', default=None, type=str, help='Filtrar por nome do funcionário')
    parser_listar.add_argument('--status', default=None, type=str, help='Filtrar por status (pendente, processado, enviado, erro)')
    parser_listar.add_argument('--limite', default=20, type=int, help='Limite de resultados (padrão: 20)')
    
    # Subcomando: stats (NOVO)
    parser_stats = subparsers_holerite.add_parser('stats', help='Exibe estatísticas de holerites.')
    parser_stats.add_argument('--competencia', default=None, type=str, help='Competência específica (MM/AAAA)')


def handle_holerite(args, parser_holerite):
    if args.subcommand == 'renomear_arquivos':
        _handle_renomear_arquivos(args)
    
    elif args.subcommand == 'processar_pdfs':
        _handle_processar_pdfs(args)
    
    elif args.subcommand == 'enviar':
        _handle_enviar(args)
    
    elif args.subcommand == 'listar':
        _handle_listar(args)
    
    elif args.subcommand == 'stats':
        _handle_stats(args)
            
    else:
        parser_holerite.print_help()


def _handle_renomear_arquivos(args):
    """Handler para o subcomando renomear_arquivos"""
    diretório = args.diretório
    mês_ano = args.mês_ano
    
    # Validação do formato mês_ano, similar à interface
    if mês_ano is not None:
        # Verifica se o formato está correto
        if len(mês_ano.split('.')) != 2:
            logger.error("Formato inválido! Use o formato MM.AAAA (ex: 01.2025).")
            return
        if not mês_ano.replace('.', '').isdigit():
            logger.error("Formato inválido! Use apenas números.")
            return
            
        # Verifica se o mês é válido
        mês, ano = mês_ano.split('.')
        if int(mês) < 1 or int(mês) > 12:
            logger.error("Mês inválido! Deve ser entre 01 e 12.")
            return
        if int(ano) < 1900 or int(ano) > 2100:
            logger.error("Ano inválido! Deve ser entre 1900 e 2100.")
            return
    
    hl = Holerite(diretório)
    logger.info(f"Renomeando arquivos no diretório: {diretório} {f'para o mês/ano: {mês_ano}' if mês_ano else ''}")
    hl.renomear_arquivos(mês_ano=mês_ano)
    logger.audit("HOLERITE_ARQUIVOS_RENOMEADOS", target=f"diretorio:{diretório}", changes={"mês_ano": mês_ano})


def _handle_processar_pdfs(args):
    """Handler para o subcomando processar_pdfs"""
    try:
        from src.processadores.holerite_processador import HoleriteProcessador

        caminho = Path(args.caminho)

        if not caminho.exists():
            logger.error(f"Caminho não encontrado: {caminho}")
            return

        processador = HoleriteProcessador()

        if not processador.disponivel:
            logger.error("Processador não disponível! Verifique Gemini API e MongoDB.")
            return

        # Processar arquivo individual ou diretório
        if caminho.is_file():
            # Validar arquivo individual
            if not processador._arquivo_eh_holerite_valido(caminho):
                logger.error(
                    f"Arquivo '{caminho.name}' não é um holerite válido!\n"
                    f"Deve ser um PDF que começa com '{HoleriteProcessador.PREFIXO_HOLERITE}'"
                )
                return

            logger.info(f"Processando arquivo: {caminho.name}")

            resultado = processador.processar_arquivo(
                caminho,
                empresa_id=args.empresa_id,
                temperatura=args.temperatura
            )

            if resultado.sucesso:
                logger.info(f"✓ Sucesso - Holerite ID: {resultado.holerite_id}")
                if resultado.funcionario_criado:
                    logger.info(f"  Novo funcionário criado")
            else:
                logger.error(f"✗ Erro: {resultado.erro}")

            logger.info(f"\n=== RESUMO ===")
            logger.info(f"Sucesso: 1" if resultado.sucesso else "Sucesso: 0")
            logger.info(f"Falhas: 0" if resultado.sucesso else "Falhas: 1")

        else:
            # Processar diretório
            logger.info(f"Processando diretório: {caminho}")
            logger.info(f"Filtro: apenas PDFs que começam com '{HoleriteProcessador.PREFIXO_HOLERITE}'")

            resultados = processador.processar_diretorio(
                caminho,
                empresa_id=args.empresa_id,
                temperatura=args.temperatura
            )

            if not resultados:
                logger.warning("Nenhum holerite válido foi encontrado ou processado.")
                return

            sucesso = sum(1 for r in resultados if r.sucesso)
            falhas = len(resultados) - sucesso

            logger.info(f"\n=== RESUMO ===")
            logger.info(f"Total processado: {len(resultados)}")
            logger.info(f"Sucesso: {sucesso}")
            logger.info(f"Falhas: {falhas}")

    except ImportError as e:
        logger.error(f"Módulo não disponível: {e}")
    except Exception as e:
        logger.error(f"Erro ao processar: {e}")


def _handle_enviar(args):
    """Handler para o subcomando enviar"""
    try:
        from src.processadores.envio_holerite_orquestrador import envio_holerite_orquestrador
        
        competencia = args.competencia
        modo = args.modo
        canais = [c.strip() for c in args.canais.split(',')]
        dry_run = args.dry_run
        empresa_id = args.empresa_id
        
        # Validar formato da competência
        if '/' not in competencia or len(competencia.split('/')) != 2:
            logger.error("Formato de competência inválido! Use MM/AAAA (ex: 01/2025)")
            return
        
        mes, ano = competencia.split('/')
        if not mes.isdigit() or not ano.isdigit():
            logger.error("Competência deve conter apenas números!")
            return
        
        logger.info(f"Iniciando envio de holerites para {competencia}...")
        logger.info(f"Modo: {modo.upper()}")
        logger.info(f"Canais: {', '.join(canais)}")
        if dry_run:
            logger.info("⚠ MODO SIMULAÇÃO (dry_run) - Nenhum envio será realizado")
        
        if modo == 'mongodb':
            relatorio = envio_holerite_orquestrador.enviar_via_mongodb(
                competencia=competencia,
                empresa_id=empresa_id,
                canais=canais,
                apenas_simular=dry_run
            )
        else:  # planilha
            relatorio = envio_holerite_orquestrador.enviar_via_planilha(
                mes=int(mes),
                ano=int(ano),
                apenas_simular=dry_run
            )
        
        logger.info(f"\n=== RELATÓRIO ===")
        logger.info(f"Competência: {relatorio.competencia}")
        logger.info(f"Total holerites: {relatorio.total_holerites}")
        logger.info(f"Total envios: {relatorio.total_envios}")
        logger.info(f"Sucesso: {relatorio.enviados_sucesso}")
        logger.info(f"Erros: {relatorio.enviados_erro}")
        logger.info(f"Duração: {relatorio.duracao_segundos():.1f}s")
        
    except ImportError as e:
        logger.error(f"Módulo não disponível: {e}")
    except Exception as e:
        logger.error(f"Erro ao enviar: {e}")


def _handle_listar(args):
    """Handler para o subcomando listar"""
    try:
        from src.services.holerite_service import holerite_service
        
        if not holerite_service.disponivel:
            logger.error("Serviço de holerites não disponível! Verifique MongoDB.")
            return
        
        filtros = {}
        if args.competencia:
            filtros['competencia'] = args.competencia
        if args.funcionario:
            filtros['funcionario_nome'] = args.funcionario
        if args.status:
            filtros['status'] = args.status
        
        holerites = holerite_service.listar_todos(limite=args.limite, **filtros)
        
        if not holerites:
            logger.info("Nenhum holerite encontrado com os filtros informados.")
            return
        
        logger.info(f"\n=== HOLERITES ENCONTRADOS ({len(holerites)}) ===\n")
        
        for i, h in enumerate(holerites, 1):
            nome = h.get("funcionario_nome", "Desconhecido")
            competencia = h.get("competencia", "N/A")
            status = h.get("status", "N/A")
            salario_liquido = h.get("salario_liquido", 0)
            
            logger.info(f"{i:3}. {nome}")
            logger.info(f"     Competência: {competencia} | Status: {status}")
            if salario_liquido:
                logger.info(f"     Salário Líquido: R$ {salario_liquido:,.2f}")
        
    except ImportError as e:
        logger.error(f"Módulo não disponível: {e}")
    except Exception as e:
        logger.error(f"Erro ao listar: {e}")


def _handle_stats(args):
    """Handler para o subcomando stats"""
    try:
        from src.processadores.envio_holerite_orquestrador import envio_holerite_orquestrador
        from src.services.holerite_service import holerite_service
        
        if not holerite_service.disponivel:
            logger.error("Serviço de holerites não disponível! Verifique MongoDB.")
            return
        
        if args.competencia:
            # Stats de uma competência específica
            stats = envio_holerite_orquestrador.obter_estatisticas_competencia(args.competencia)
            
            logger.info(f"\n=== ESTATÍSTICAS - {args.competencia} ===")
            logger.info(f"Total de holerites: {stats.get('total', 0)}")
            logger.info(f"Pendentes de envio: {stats.get('pendentes', 0)}")
            logger.info(f"Já enviados: {stats.get('enviados', 0)}")
            logger.info(f"Com erro: {stats.get('erros', 0)}")
            
            logger.info("\nPor Status:")
            for status, count in stats.get("por_status", {}).items():
                logger.info(f"  {status}: {count}")
        else:
            # Stats gerais
            total = holerite_service.contar_total()
            logger.info(f"\n=== ESTATÍSTICAS GERAIS ===")
            logger.info(f"Total de holerites no MongoDB: {total}")
        
    except ImportError as e:
        logger.error(f"Módulo não disponível: {e}")
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}")