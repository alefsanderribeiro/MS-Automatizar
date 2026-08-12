from datetime import date
from src.utils.type import bool_type, date_type, list_type
from src.folha_de_ponto import Folha_de_Ponto
from src.utils.logger_config import logger


def arquivo_arguments(parser):
    parser.add_argument('--arquivo', type=str, help='Informa o arquivo.')


def folha_de_ponto_subcommands(subparsers):
    parser_fp = subparsers.add_parser('folha_de_ponto', help='Comando para as Folhas de Pontos dos funcionários')
    subparsers_fp = parser_fp.add_subparsers(dest='subcommand', help='Subcomandos para Folhas de Ponto')

    parser_fp_sub1 = subparsers_fp.add_parser('criar', help='Cria as folhas de ponto do sistema.')
    #arquivo_arguments(parser_nfe_sub1)
    parser_fp_sub1.add_argument('--data', type=date_type, help='Informa a data. (YYYY-MM-DD)')
    parser_fp_sub1.add_argument('--id_funcionario', default=None, type=list_type, help='ID(s) do(s) funcionário(s). Separe por vírgula.')
    parser_fp_sub1.add_argument('--nome_funcionario', default=None, type=list_type, help='Nome(s) do(s) funcionário(s). Separe por vírgula.')
    parser_fp_sub1.add_argument('--lotacao', default=None, type=list_type, help='Lotação do(s) funcionário(s) para o qual deseja criar a folha de ponto. Separar por vírgula')
    parser_fp_sub1.add_argument('--contrato', default=None, type=list_type, help='Contrato(s) do(s) funcionário(s) para o qual deseja criar a folha de ponto. Separar por vírgula')
    parser_fp_sub1.add_argument('--diretorio_destino', default=None, type=str, help='Informa o diretório em que será salvo o arquivo criado')


    parser_fp_sub2 = subparsers_fp.add_parser('análise', help='Fazer uma análise da folha de ponto do funcionário')
    arquivo_arguments(parser_fp_sub2)

    parser_fp_sub3 = subparsers_fp.add_parser('gerar_dataframe', help='Imprime na tela todos os dados da folha de ponto dos funcionários')
    
    parser_fp_sub3.add_argument('--memória', default=False, type=str, help='Deixa o dataframe na memória (visando utilizar outros sistemas para acessar esses dados). True or False')

    parser_fp_sub3.add_argument('--diretorio_destino', default=None, type=str, help='Informa o diretório em que será salvo o arquivo criado')

    # Novo subcomando para processar e salvar em MongoDB
    parser_fp_sub5 = subparsers_fp.add_parser('mongodb', help='Processa folhas de ponto e salva em MongoDB')
    parser_fp_sub5.add_argument('--data', type=date_type, help='Informa a data. (YYYY-MM-DD)', required=False)
    parser_fp_sub5.add_argument('--id_funcionario', dest='id_funcionario', default=None, type=list_type, help='ID(s) do(s) funcionário(s). Separe por vírgula.')
    parser_fp_sub5.add_argument('--nome_funcionario', dest='nome_funcionario', default=None, type=list_type, help='Nome(s) do(s) funcionário(s). Separe por vírgula.')
    parser_fp_sub5.add_argument('--lotacao', dest='lotacao', default=None, type=list_type, help='Lotação do(s) funcionário(s). Separar por vírgula')
    parser_fp_sub5.add_argument('--contrato', default=None, type=list_type, help='Contrato(s) do(s) funcionário(s). Separar por vírgula')
    parser_fp_sub5.add_argument('--diretorio_destino', dest='diretorio_destino', default=None, type=str, help='Informa o diretório em que será salvo o arquivo criado')

    # Novo subcomando para processar PDFs com IA
    parser_fp_sub6 = subparsers_fp.add_parser('processar_pdf', help='Processa PDF(s) de folhas de ponto preenchidas com IA e salva em MongoDB')
    parser_fp_sub6.add_argument('--arquivo', type=str, help='Caminho para arquivo PDF único', required=False)
    parser_fp_sub6.add_argument('--arquivos', type=list_type, help='Lista de caminhos de arquivos PDF (separados por vírgula)', required=False)
    parser_fp_sub6.add_argument('--diretorio', type=str, help='Diretório contendo arquivos PDF para processar', required=False)

    # Novo subcomando para criar folha a partir do MongoDB por ID
    parser_fp_sub7 = subparsers_fp.add_parser('criar_mongodb_id', help='Cria folha de ponto a partir de dados do MongoDB usando IDs')
    parser_fp_sub7.add_argument('--funcionario_id', type=str, help='ObjectId do funcionário no MongoDB', required=True)
    parser_fp_sub7.add_argument('--empresa_id', type=str, help='ObjectId da empresa no MongoDB', required=True)
    parser_fp_sub7.add_argument('--data', type=date_type, help='Data de referência (YYYY-MM-DD)', required=True)
    parser_fp_sub7.add_argument('--diretorio_destino', type=str, help='Diretório customizado para salvar PDF', required=False)

    # Novo subcomando para criar folhas a partir do MongoDB por filtros
    parser_fp_sub8 = subparsers_fp.add_parser('criar_mongodb_filtro', help='Cria folhas de ponto a partir do MongoDB usando filtros')
    parser_fp_sub8.add_argument('--lotacao', type=str, help='Filtrar por lotação', required=False)
    parser_fp_sub8.add_argument('--funcao', type=str, help='Filtrar por função', required=False)
    parser_fp_sub8.add_argument('--contrato', type=str, help='Filtrar por contrato', required=False)
    parser_fp_sub8.add_argument('--ativo', type=bool_type, help='Filtrar por status ativo (True/False)', required=False)
    parser_fp_sub8.add_argument('--data', type=date_type, help='Data de referência (YYYY-MM-DD)', required=True)
    parser_fp_sub8.add_argument('--diretorio_destino', type=str, help='Diretório customizado para salvar PDFs', required=False)

    # ==================== SUBCOMANDOS DE ENVIO ====================
    
    # Subcomando: envio - menu interativo
    parser_fp_envio = subparsers_fp.add_parser('envio', help='Abre menu interativo de envio de folhas de ponto')
    
    # Subcomando: envio-verificar - verifica serviços
    parser_fp_envio_verificar = subparsers_fp.add_parser('envio-verificar', help='Verifica status dos serviços de envio')
    
    # Subcomando: envio-validar - valida planilha
    parser_fp_envio_validar = subparsers_fp.add_parser('envio-validar', help='Valida planilha de contatos')
    
    # Subcomando: envio-sincronizar - sincroniza grupos WhatsApp
    parser_fp_envio_sync = subparsers_fp.add_parser('envio-sincronizar', help='Sincroniza grupos WhatsApp')
    parser_fp_envio_sync.add_argument('--listar', action='store_true', help='Lista grupos após sincronizar')
    
    # Subcomando: envio-dispositivos - gerencia dispositivos WhatsApp
    parser_fp_envio_dev = subparsers_fp.add_parser('envio-dispositivos', help='Gerencia dispositivos WhatsApp para múltiplas empresas')
    parser_fp_envio_dev.add_argument('--listar', action='store_true', help='Lista todos os dispositivos conectados')
    parser_fp_envio_dev.add_argument('--empresa', type=str, help='Mostra device de uma empresa específica')
    parser_fp_envio_dev.add_argument('--status', action='store_true', help='Verifica status de todos os dispositivos')

    # Subcomando: envio-listar - lista contatos
    parser_fp_envio_listar = subparsers_fp.add_parser('envio-listar', help='Lista contatos da planilha')
    
    # Subcomando: envio-executar - executa envio
    parser_fp_envio_exec = subparsers_fp.add_parser('envio-executar', help='Executa envio de folhas de ponto')
    parser_fp_envio_exec.add_argument('--mes', '-m', type=int, help='Mês de referência')
    parser_fp_envio_exec.add_argument('--ano', '-a', type=int, help='Ano de referência')
    parser_fp_envio_exec.add_argument('--dry-run', '-d', action='store_true', help='Simula sem enviar')
    parser_fp_envio_exec.add_argument('--email', '-e', action='store_true', help='Enviar apenas por e-mail')
    parser_fp_envio_exec.add_argument('--whatsapp', '-w', action='store_true', help='Enviar apenas por WhatsApp individual')
    parser_fp_envio_exec.add_argument('--grupo', '-g', action='store_true', help='Enviar apenas para grupos WhatsApp')
    parser_fp_envio_exec.add_argument('--ids', type=str, help='IDs de contatos específicos (separados por vírgula)')
    parser_fp_envio_exec.add_argument('--force', '-f', action='store_true', help='Não pedir confirmação')
    parser_fp_envio_exec.add_argument('--verbose', '-v', action='store_true', help='Saída detalhada')

def handle_folha_de_ponto(args, parser_fp):
    
    from src.utils.logger_config import logger
    import pickle
    import sys
    
    
    logger.debug(f"Subcomando: {args.subcommand}")

    # Criar folhas de ponto
    if args.subcommand == "criar":

        logger.debug(f"Criando a folha de ponto do(s) funcionário(s) {args.nome_funcionario} na data {args.data}")
        logger.debug(f"Diretório de destino: {args.diretorio_destino}")
        logger.debug(f"Lotação: {args.lotacao}")
        logger.debug(f"Contrato: {args.contrato}")

        fp = Folha_de_Ponto()
        data = args.data if args.data else date.today()

        if args.id_funcionario:
            from bson import ObjectId
            from src.services.funcionario_service import FuncionarioService

            funcionario_service = FuncionarioService()
            ids = args.id_funcionario if isinstance(args.id_funcionario, list) else [args.id_funcionario]

            for id_val in ids:
                try:
                    funcionario_id = str(ObjectId(id_val)) if isinstance(id_val, str) else str(id_val)
                    funcionario = funcionario_service.buscar_por_id(ObjectId(funcionario_id))
                    if not funcionario or not funcionario.get('empresas_ids'):
                        logger.error(f"❌ Funcionário {funcionario_id} não encontrado ou sem empresa vinculada")
                        continue

                    empresa_id = str(funcionario['empresas_ids'][0])
                    resultado = fp.criar_mongodb_por_id(
                        funcionario_id=funcionario_id,
                        empresa_id=empresa_id,
                        data=data,
                        diretorio_destino=args.diretorio_destino
                    )
                    if resultado and resultado.get('status') in ['sucesso', 'parcial']:
                        logger.info(f"✅ Folha criada para {resultado.get('funcionario', 'N/A')}")
                    else:
                        logger.error("❌ Erro ao criar folha")
                except Exception as e:
                    logger.error(f"❌ Erro ao processar ID {id_val}: {e}")
        else:
            filtros = {}
            if args.nome_funcionario:
                filtros["nome"] = args.nome_funcionario[0] if isinstance(args.nome_funcionario, list) else args.nome_funcionario
            if args.lotacao:
                filtros["lotacao"] = args.lotacao[0] if isinstance(args.lotacao, list) else args.lotacao
            if args.contrato:
                filtros["contrato"] = args.contrato[0] if isinstance(args.contrato, list) else args.contrato
            if not filtros:
                filtros["status"] = "ativo"

            resultado = fp.criar_mongodb_por_filtros(
                filtros=filtros,
                data=data,
                diretorio_destino=args.diretorio_destino
            )
            if resultado:
                logger.info(f"✅ Folhas criadas: {resultado.get('sucesso', 0)}/{resultado.get('total', 0)}")
            else:
                logger.error("❌ Erro ao criar folhas de ponto")

    elif args.subcommand == "análise":
        
        logger.debug(f"arquivo para análise: {args.arquivo}")
        fp = Folha_de_Ponto()
        if args.arquivo is not None:
            logger.info(f"Analisando a folha de ponto do arquivo {args.arquivo}")
            try:
                resultado = fp.análise_folha_de_ponto(args.arquivo)
                if resultado:
                    from src.utils.logger_config import logger
                    import json
                    logger.info(
                        f"Resultado da análise:\n{json.dumps(resultado, ensure_ascii=False, indent=2, default=str)}"
                    )
            except Exception as e:
                logger.error(f"Erro ao analisar folha de ponto: {e}")
        else:
            logger.error("Nenhum arquivo informado para análise.")
            parser_fp.print_help()
            pass

    elif args.subcommand == "gerar_dataframe":

        fp = Folha_de_Ponto()

        if args.memória == "True":
            try:
                obj = fp.criar_dataFrame_funcionários()
                logger.debug(f"DataFrame guardado na memória:\n {obj}")
                pickle.dump(obj, sys.stdout.buffer)
                logger.info("Mantendo o DataFrame na memória para uso posterior.")
            except Exception as e:
                logger.error(f"❌ Falha ao gerar DataFrame: {e}")

        if args.diretorio_destino is not None:
            logger.info(f"Exportando os dados da folha de ponto para o diretório {args.diretorio_destino}")
            try:
                fp.exportar_dataframe(args.diretorio_destino)
            except Exception as e:
                logger.error(f"❌ Falha ao exportar DataFrame: {e}")
        else:
            try:
                logger.debug(f"DataFrame:\n {fp.criar_dataFrame_funcionários()}")
            except Exception as e:
                logger.error(f"❌ Falha ao exibir DataFrame: {e}")
            
            
    elif args.subcommand == "mongodb":
        """Processa folhas de ponto e salva em MongoDB usando filtros"""
        from datetime import date
        
        logger.debug(f"Processando folhas para MongoDB")
        logger.debug(f"Data: {args.data}")
        logger.debug(f"ID Funcionario: {args.id_funcionario}")
        logger.debug(f"Nome Funcionario: {args.nome_funcionario}")
        logger.debug(f"Lotacao: {args.lotacao}")
        logger.debug(f"Contrato: {args.contrato}")
        
        # Se nenhuma data for fornecida, usar data atual
        data = args.data if args.data else date.today()
        
        # Construir filtros a partir dos parâmetros
        filtros = {}
        
        if args.id_funcionario:
            # Se tem ID específico, usar criar_mongodb_por_id
            from bson import ObjectId
            try:
                funcionario_id = str(args.id_funcionario[0]) if isinstance(args.id_funcionario, list) else str(args.id_funcionario)
                # Buscar empresa do funcionário
                from src.services.funcionario_service import FuncionarioService
                func_service = FuncionarioService()
                funcionario = func_service.buscar_por_id(ObjectId(funcionario_id))
                if funcionario and funcionario.get('empresas_ids'):
                    empresa_id = str(funcionario['empresas_ids'][0])
                    fp = Folha_de_Ponto()
                    resultado = fp.criar_mongodb_por_id(
                        funcionario_id=funcionario_id,
                        empresa_id=empresa_id,
                        data=data,
                        diretorio_destino=args.diretorio_destino
                    )
                    if resultado and resultado.get('status') in ['sucesso', 'parcial']:
                        logger.info(f"✅ Folha criada para {resultado.get('funcionario', 'N/A')}")
                    else:
                        logger.error("❌ Erro ao criar folha")
                else:
                    logger.error(f"❌ Funcionário {funcionario_id} não encontrado ou sem empresa vinculada")
            except Exception as e:
                logger.error(f"❌ Erro ao processar ID: {e}")
        else:
            # Usar filtros
            if args.nome_funcionario:
                filtros["nome"] = args.nome_funcionario[0] if isinstance(args.nome_funcionario, list) else args.nome_funcionario
            if args.lotacao:
                filtros["lotacao"] = args.lotacao[0] if isinstance(args.lotacao, list) else args.lotacao
            if args.contrato:
                filtros["contrato"] = args.contrato[0] if isinstance(args.contrato, list) else args.contrato
            
            if not filtros:
                # Sem filtros = todos os funcionários ativos
                filtros["status"] = "ativo"
            
            fp = Folha_de_Ponto()
            
            logger.info(f"✓ Iniciando processamento para MongoDB - Data: {data}")
            logger.info(f"📋 Filtros: {filtros}")
            
            resultado = fp.criar_mongodb_por_filtros(
                filtros=filtros,
                data=data,
                diretorio_destino=args.diretorio_destino
            )
            
            if "erro" in resultado:
                logger.error(f"❌ Erro: {resultado['erro']}")
            else:
                logger.info(f"\n📊 RESUMO: {resultado['sucesso']}/{resultado['total']} folhas criadas")
        
        logger.info("✓ Processamento MongoDB concluído!")
    
    elif args.subcommand == "processar_pdf":
        """Processa PDF(s) de folhas de ponto com IA e salva em MongoDB"""
        from pathlib import Path
        
        # Determinar caminho(s) dos PDFs
        caminho_pdfs = None
        
        if args.arquivo:
            caminho_pdfs = args.arquivo
            logger.info(f"📄 Processando arquivo único: {args.arquivo}")
        elif args.arquivos:
            caminho_pdfs = args.arquivos
            logger.info(f"📄 Processando {len(args.arquivos)} arquivo(s)")
        elif args.diretorio:
            caminho_pdfs = args.diretorio
            logger.info(f"📁 Processando diretório: {args.diretorio}")
        else:
            logger.error("❌ É necessário informar --arquivo, --arquivos ou --diretorio")
            parser_fp.print_help()
            return
        
        # Criar instância e processar
        fp = Folha_de_Ponto()
        
        logger.info("🤖 Iniciando processamento com IA...")
        resultado = fp.processar_pdfs(caminho_pdfs)
        
        # Exibir resumo
        logger.info("\n" + "="*60)
        logger.info("📊 RESUMO DO PROCESSAMENTO")
        logger.info("="*60)
        logger.info(f"Total de arquivos: {resultado['total_arquivos']}")
        logger.info(f"✅ Processados com sucesso: {resultado['processados_sucesso']}")
        logger.info(f"❌ Erros: {resultado['processados_erro']}")
        
        if resultado['processados_sucesso'] > 0:
            taxa_sucesso = (resultado['processados_sucesso'] / resultado['total_arquivos']) * 100
            logger.info(f"📈 Taxa de sucesso: {taxa_sucesso:.1f}%")
        
        logger.info("="*60)
        
        # Exibir detalhes de cada arquivo
        for res in resultado['resultados']:
            if res['sucesso']:
                logger.info(f"\n✅ {res['nome_arquivo']}")
                logger.info(f"   Funcionário ID: {res['funcionario_id']}")
                logger.info(f"   Folha ID: {res['folha_id']}")
                logger.info(f"   Dias extraídos: {res['dias_extraidos']}")
                logger.info(f"   Tempo: {res['tempo_s']:.2f}s")
                if res['avisos']:
                    for aviso in res['avisos']:
                        logger.warning(f"   ⚠️ {aviso}")
            else:
                logger.error(f"\n❌ {res['nome_arquivo']}")
                for erro in res['erros']:
                    logger.error(f"   {erro}")
        
        logger.info("\n✓ Processamento concluído!")
        
    elif args.subcommand == "criar_mongodb_id":
        """Cria folha de ponto a partir do MongoDB usando IDs específicos"""
        
        logger.info(f"🔍 Criando folha de ponto a partir do MongoDB")
        logger.info(f"Funcionário ID: {args.funcionario_id}")
        logger.info(f"Empresa ID: {args.empresa_id}")
        logger.info(f"Data: {args.data}")
        
        fp = Folha_de_Ponto()
        
        resultado = fp.criar_mongodb_por_id(
            funcionario_id=args.funcionario_id,
            empresa_id=args.empresa_id,
            data=args.data,
            diretorio_destino=args.diretorio_destino
        )
        
        if resultado:
            if resultado.get("status") == "sucesso":
                logger.info("\n✅ Folha criada com sucesso!")
                logger.info(f"Funcionário: {resultado['funcionario']}")
                logger.info(f"Empresa: {resultado['empresa']}")
                logger.info(f"Mês: {resultado['mes']}")
                logger.info(f"PDF: {resultado['caminho_pdf']}")
            elif resultado.get("status") == "parcial":
                logger.warning("\n⚠️ Folha criada parcialmente")
                logger.warning(f"PDF: {resultado['caminho_pdf']}")
                logger.warning("Falha ao salvar registro no MongoDB")
            else:
                logger.error("\n❌ Erro ao criar folha")
        else:
            logger.error("\n❌ Falha ao criar folha de ponto")
    
    elif args.subcommand == "criar_mongodb_filtro":
        """Cria folhas de ponto a partir do MongoDB usando filtros"""
        
        # Construir filtros
        filtros = {}

        if args.lotacao:
            filtros["lotacao"] = args.lotacao
        if args.funcao:
            # O modelo de funcionário grava a função em `funcao_id` (ObjectId).
            # O flag --funcao recebe o NOME da função: resolve nome → funcao_id.
            try:
                from src.services.funcao_service import FuncaoService
                funcao_service = FuncaoService()
                funcao_doc = funcao_service.buscar_por_nome(args.funcao)
                if funcao_doc:
                    filtros["funcao_id"] = funcao_doc.get('_id')
                else:
                    logger.error(f"\u274c Fun\u00e7\u00e3o n\u00e3o encontrada: {args.funcao}")
                    return
            except ImportError:
                logger.error("\u274c FuncaoService n\u00e3o dispon\u00edvel para resolver a fun\u00e7\u00e3o")
                return
        if args.contrato:
            filtros["contrato"] = args.contrato
        if args.ativo is not None:
            # O modelo usa `status` ("ativo"/"inativo"), n\u00e3o um booleano `ativo`.
            filtros["status"] = "ativo" if args.ativo else "inativo"
        
        if not filtros:
            logger.error("❌ É necessário informar ao menos um filtro")
            logger.error("Use --lotacao, --funcao, --contrato ou --ativo")
            parser_fp.print_help()
            return
        
        logger.info(f"🔍 Criando folhas de ponto a partir do MongoDB")
        logger.info(f"Filtros: {filtros}")
        logger.info(f"Data: {args.data}")
        
        fp = Folha_de_Ponto()
        
        resultado = fp.criar_mongodb_por_filtros(
            filtros=filtros,
            data=args.data,
            diretorio_destino=args.diretorio_destino
        )
        
        if "erro" in resultado:
            logger.error(f"\n❌ Erro: {resultado['erro']}")
        else:
            logger.info("\n" + "="*60)
            logger.info("📊 RESUMO DA OPERAÇÃO")
            logger.info("="*60)
            logger.info(f"Total de funcionários: {resultado['total']}")
            logger.info(f"✅ Sucesso: {resultado['sucesso']}")
            logger.info(f"❌ Erros: {resultado['erros']}")
            logger.info(f"📈 Taxa de sucesso: {resultado['taxa_sucesso']}%")
            logger.info("="*60)
            
            # Exibir detalhes
            logger.info("\n📋 DETALHES:")
            for detalhe in resultado['detalhes']:
                if detalhe['status'] == 'sucesso':
                    logger.info(f"\n✅ {detalhe['funcionario']}")
                    logger.info(f"   PDF: {detalhe['caminho_pdf']}")
                else:
                    logger.error(f"\n❌ {detalhe['funcionario']}")
                    logger.error(f"   Motivo: {detalhe['motivo']}")
            
            logger.info("\n✓ Processamento concluído!")
        
    # ==================== HANDLERS DE ENVIO ====================
    
    elif args.subcommand == "envio":
        """Abre menu interativo de envio"""
        from src.interface.interface_envio_folha_ponto import iniciar_menu_envio
        iniciar_menu_envio()
    
    elif args.subcommand == "envio-verificar":
        """Verifica status dos serviços de envio"""
        from src.processadores.envio_folha_ponto_orquestrador import envio_folha_ponto_orquestrador
        
        print("Verificando serviços...")
        status = envio_folha_ponto_orquestrador.verificar_servicos()
        
        print("\n--- Status dos Serviços ---")
        for servico, disponivel in status.items():
            emoji = "✓" if disponivel else "✗"
            print(f"  {emoji} {servico}")
    
    elif args.subcommand == "envio-validar":
        """Valida planilha de contatos"""
        from src.services.planilha_contatos_service import planilha_contatos_service
        
        print(f"Validando planilha: {planilha_contatos_service.planilha_path}")
        
        if not planilha_contatos_service.carregar():
            print("✗ Erro ao carregar planilha")
            return
        
        resultado = planilha_contatos_service.validar_planilha()
        
        print(f"\nTotal de linhas: {resultado.get('total_linhas', 0)}")
        
        if resultado.get("valida"):
            print("✓ Planilha válida")
        else:
            print("✗ Planilha com problemas:")
            for problema in resultado.get("problemas", []):
                print(f"  • {problema}")
    
    elif args.subcommand == "envio-sincronizar":
        """Sincroniza grupos do WhatsApp"""
        from src.processadores.envio_folha_ponto_orquestrador import envio_folha_ponto_orquestrador
        from src.services.grupo_whatsapp_service import grupo_whatsapp_service
        from src.services.empresa_service import empresa_service

        print("Sincronizando grupos WhatsApp...")
        resultado = envio_folha_ponto_orquestrador.sincronizar_grupos_whatsapp()

        print(f"\nResultado:")
        print(f"  Criados: {resultado.get('criados', 0)}")
        print(f"  Atualizados: {resultado.get('atualizados', 0)}")
        print(f"  Inativos: {resultado.get('inativos', 0)}")

        if hasattr(args, 'listar') and args.listar:
            # Listar empresas com device configurado para selecao
            if not empresa_service or not empresa_service.disponivel:
                print("\n[X] Servico de empresas nao disponivel!")
                return

            empresas_ativas = empresa_service.listar_ativos()
            empresas_com_device = [
                e for e in empresas_ativas
                if e.get('whatsapp_device_id')
            ]

            if not empresas_com_device:
                print("\n[!] Nenhuma empresa com dispositivo WhatsApp configurado.")
                print("    Configure o whatsapp_device_id nas empresas primeiro.")
                return

            print(f"\n--- Empresas com Dispositivo WhatsApp ({len(empresas_com_device)}) ---")
            for i, empresa in enumerate(empresas_com_device, 1):
                nome = empresa.get('nome', 'N/A')
                nome_simples = empresa.get('nome_simplificado', '')
                device_id = empresa.get('whatsapp_device_id', 'N/A')
                display_nome = f"{nome} ({nome_simples})" if nome_simples else nome
                print(f"  {i}. {display_nome} [Device: {device_id}]")

            print(f"\n  0. Cancelar")

            opcao = input("\nSelecione a empresa (0-{}): ".format(len(empresas_com_device))).strip()

            if not opcao or opcao == "0":
                print("Listagem cancelada.")
                return

            try:
                indice = int(opcao) - 1
                if 0 <= indice < len(empresas_com_device):
                    empresa_selecionada = empresas_com_device[indice]
                    device_id = empresa_selecionada.get('whatsapp_device_id')
                    nome_empresa = empresa_selecionada.get('nome')

                    if not device_id:
                        print(f"\n[X] Empresa '{nome_empresa}' nao tem dispositivo WhatsApp configurado!")
                        return

                    print(f"\n[OK] Empresa selecionada: {nome_empresa}")

                    # Listar grupos da empresa selecionada
                    try:
                        grupos = grupo_whatsapp_service.listar_para_exibicao(device_id)
                        print(f"\n--- Grupos de '{nome_empresa}' ({len(grupos)}) ---")
                        for g in grupos:
                            print(f"  {g['nome']} ({g['participantes']} participantes)")

                        if not grupos:
                            print(f"  Nenhum grupo encontrado para esta empresa.")
                    except ValueError as e:
                        print(f"\n[X] Erro: {e}")
                else:
                    print("\n[X] Opcao invalida!")
            except ValueError:
                print("\n[X] Digite um numero valido!")

    elif args.subcommand == "envio-dispositivos":
        """Gerencia dispositivos WhatsApp para múltiplas empresas"""
        try:
            from src.services.whatsapp_service import whatsapp_service
            from src.services.empresa_service import empresa_service

            if not whatsapp_service.disponivel:
                print("[X] WhatsApp Service nao disponivel")
                return

            # Opção: Listar dispositivos conectados
            if hasattr(args, 'listar') and args.listar:
                print("[*] Listando dispositivos WhatsApp conectados...\n")
                dispositivos = whatsapp_service.listar_dispositivos()

                if not dispositivos:
                    print("[!] Nenhum dispositivo conectado encontrado")
                    return

                print(f"--- Dispositivos Conectados ({len(dispositivos)}) ---")
                for d in dispositivos:
                    jid = d.get('jid', 'N/A')  # Device ID completo
                    display_name = d.get('display_name', 'Desconhecido')
                    state = d.get('state', 'unknown')  # logged_in, connection_lost, etc
                    status = "[OK] Conectado" if state == "logged_in" else "[X] Desconectado"

                    # Extrair número do JID
                    numero = jid.split('@')[0] if '@' in jid else jid

                    print(f"  {numero} ({display_name}) - {status}")
                    print(f"     JID: {jid}")

            # Opção: Verificar status dos dispositivos
            elif hasattr(args, 'status') and args.status:
                print("[*] Verificando status dos dispositivos...\n")

                empresas = empresa_service.listar_todos(limit=1000)['dados']
                dispositivos_unicos = set()

                for empresa in empresas:
                    device_id = empresa.get('whatsapp_device_id')
                    if device_id:
                        dispositivos_unicos.add(device_id)

                if not dispositivos_unicos:
                    print("⚠ Nenhuma empresa tem dispositivo configurado")
                    return

                print(f"--- Status de {len(dispositivos_unicos)} Dispositivo(s) ---\n")

                for device_id in sorted(dispositivos_unicos):
                    status = whatsapp_service.verificar_status_dispositivo(device_id)

                    if status.get('sucesso'):
                        is_logged = "[OK]" if status.get('is_logged_in') else "[X]"
                        numero = status.get('numero', 'Desconhecido')
                        print(f"{is_logged} {numero}")
                        print(f"   Device ID: {device_id}")
                        print(f"   Status: {status.get('mensagem', 'N/A')}\n")
                    else:
                        print(f"[ERR] Erro ao verificar {device_id}: {status.get('mensagem', 'Erro desconhecido')}\n")

            # Opção: Mostrar device de uma empresa específica
            elif hasattr(args, 'empresa') and args.empresa:
                print(f"[*] Procurando empresa: {args.empresa}\n")

                empresa = empresa_service.buscar_por_nome_ou_simplificado(args.empresa)

                if not empresa:
                    print(f"[X] Empresa '{args.empresa}' não encontrada")
                    return

                device_id = empresa.get('whatsapp_device_id')
                nome = empresa.get('nome')
                nome_simples = empresa.get('nome_simplificado', 'N/A')

                print(f"--- Empresa: {nome} ---")
                print(f"Nome Simplificado: {nome_simples}")

                if device_id:
                    print(f"Device ID: {device_id}")

                    # Verificar status do device
                    status = whatsapp_service.verificar_status_dispositivo(device_id)
                    if status.get('sucesso'):
                        is_logged = "[OK] Conectado" if status.get('is_logged_in') else "[X] Desconectado"
                        print(f"Status: {is_logged}")
                    else:
                        print(f"Status: [!] Nao foi possivel verificar ({status.get('mensagem', 'Erro')})")
                else:
                    print("[!] Nenhum dispositivo configurado")

            else:
                # Mostrar ajuda
                print("Uso: python automatizar.py folha_de_ponto envio-dispositivos [opção]")
                print("\nOpções:")
                print("  --listar          Lista todos os dispositivos conectados na API")
                print("  --status          Verifica status de todos os dispositivos configurados")
                print("  --empresa <nome>  Mostra device de uma empresa específica")

        except ImportError as e:
            print(f"✗ Módulo não disponível: {e}")
        except Exception as e:
            logger.error(f"Erro ao gerenciar dispositivos: {e}")
            print(f"✗ Erro: {e}")

    elif args.subcommand == "envio-listar":
        """Lista contatos da planilha"""
        from src.services.planilha_contatos_service import planilha_contatos_service
        
        if not planilha_contatos_service.carregar():
            print("✗ Erro ao carregar planilha")
            return
        
        resumo = planilha_contatos_service.listar_resumo()
        
        print(f"\n--- Contatos ({len(resumo)}) ---")
        print(f"{'ID':<5} {'Nome':<30} {'Local':<25} {'Email':<6} {'WA':<6} {'Grupo':<6}")
        print("-" * 80)
        
        for c in resumo:
            print(f"{c['id']:<5} {c['nome'][:29]:<30} {c['local'][:24]:<25} {c['enviar_email']:<6} {c['enviar_whatsapp']:<6} {c['enviar_grupo']:<6}")
    
    elif args.subcommand == "envio-executar":
        """Executa envio de folhas de ponto"""
        from datetime import datetime
        from src.models.envio_folha_ponto_models import TipoEnvioEnum
        from src.processadores.envio_folha_ponto_orquestrador import envio_folha_ponto_orquestrador
        
        mes = args.mes if hasattr(args, 'mes') and args.mes else datetime.now().month
        ano = args.ano if hasattr(args, 'ano') and args.ano else datetime.now().year
        dry_run = args.dry_run if hasattr(args, 'dry_run') else False
        
        # Determinar tipos de envio
        tipos = []
        if hasattr(args, 'email') and args.email:
            tipos.append(TipoEnvioEnum.EMAIL)
        if hasattr(args, 'whatsapp') and args.whatsapp:
            tipos.append(TipoEnvioEnum.WHATSAPP_INDIVIDUAL)
        if hasattr(args, 'grupo') and args.grupo:
            tipos.append(TipoEnvioEnum.WHATSAPP_GRUPO)
        
        # Se nenhum tipo especificado, usar todos
        if not tipos:
            tipos = [TipoEnvioEnum.EMAIL, TipoEnvioEnum.WHATSAPP_INDIVIDUAL, TipoEnvioEnum.WHATSAPP_GRUPO]
        
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Enviando folhas de ponto {mes:02d}/{ano}")
        print(f"Tipos: {', '.join([t.value for t in tipos])}")
        
        force = hasattr(args, 'force') and args.force
        if not dry_run and not force:
            confirma = input("\nConfirma? (SIM para prosseguir): ").strip().upper()
            if confirma != "SIM":
                print("Operação cancelada.")
                return
        
        # Filtrar por IDs se especificado
        contatos_ids = args.ids.split(",") if hasattr(args, 'ids') and args.ids else None
        
        relatorio = envio_folha_ponto_orquestrador.executar(
            mes=mes,
            ano=ano,
            tipos_envio=tipos,
            contatos_ids=contatos_ids,
            dry_run=dry_run
        )
        
        # Exibir resumo
        print(f"\n--- Resumo ---")
        print(f"Contatos processados: {relatorio.total_contatos}")
        print(f"Total de envios: {relatorio.total_envios}")
        print(f"Sucesso: {relatorio.enviados_sucesso}")
        print(f"Erro: {relatorio.enviados_erro}")
        print(f"Duração: {relatorio.duracao_segundos():.1f}s")
        
        verbose = hasattr(args, 'verbose') and args.verbose
        if relatorio.erros and verbose:
            print("\n--- Erros ---")
            for erro in relatorio.erros:
                print(f"  • {erro}")
        
    else:
        # Exibe a ajuda quando nenhum subcomando é fornecido
        parser_fp.print_help()
        pass




