from datetime import date
from typing import List

from src.utils.type import bool_type, date_type, list_type
from src.utils.data_utils import formatar_data_br
from src.folha_de_ponto import Folha_de_Ponto
from src.utils.logger_config import logger


def arquivo_arguments(parser):
    parser.add_argument('--arquivo', type=str, help='Informa o arquivo.')


def folha_de_ponto_subcommands(subparsers):
    parser_fp = subparsers.add_parser('folha_de_ponto', help='Comando para as Folhas de Pontos dos funcionários')
    subparsers_fp = parser_fp.add_subparsers(dest='subcommand', help='Subcomandos para Folhas de Ponto')

    parser_fp_sub1 = subparsers_fp.add_parser('criar', help='Cria as folhas de ponto do sistema.')
    #arquivo_arguments(parser_nfe_sub1)
    parser_fp_sub1.add_argument('--data', type=date_type, help='Informa a data. (DD/MM/YYYY ex: 15/08/2026)')
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
    parser_fp_sub5.add_argument('--data', type=date_type, help='Informa a data. (DD/MM/YYYY ex: 15/08/2026)', required=False)
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
    parser_fp_sub7.add_argument('--data', type=date_type, help='Data de referência (DD/MM/YYYY ex: 15/08/2026)', required=True)
    parser_fp_sub7.add_argument('--diretorio_destino', type=str, help='Diretório customizado para salvar PDF', required=False)

    # Novo subcomando para criar folhas a partir do MongoDB por filtros
    parser_fp_sub8 = subparsers_fp.add_parser('criar_mongodb_filtro', help='Cria folhas de ponto a partir do MongoDB usando filtros')
    parser_fp_sub8.add_argument('--lotacao', type=str, help='Filtrar por lotação', required=False)
    parser_fp_sub8.add_argument('--funcao', type=str, help='Filtrar por função', required=False)
    parser_fp_sub8.add_argument('--contrato', type=str, help='Filtrar por contrato', required=False)
    parser_fp_sub8.add_argument('--ativo', type=bool_type, help='Filtrar por status ativo (True/False)', required=False)
    parser_fp_sub8.add_argument('--data', type=date_type, help='Data de referência (DD/MM/YYYY ex: 15/08/2026)', required=True)
    parser_fp_sub8.add_argument('--diretorio_destino', type=str, help='Diretório customizado para salvar PDFs', required=False)

    # ==================== GERENCIAR FOLHAS GERADAS ====================

    # Subcomando: visualizar - visualiza uma folha ja gerada
    parser_fp_visualizar = subparsers_fp.add_parser('visualizar', help='Visualiza uma folha de ponto ja gerada (por id ou nome)')
    parser_fp_visualizar.add_argument('--id', type=str, help='ObjectId da folha', required=False)
    parser_fp_visualizar.add_argument('--nome', type=str, help='Nome (ou parte) do funcionário', required=False)
    parser_fp_visualizar.add_argument('--mes', type=str, help='Mês YYYY-MM para filtrar', required=False)

    # Subcomando: buscar - busca folhas por nome do funcionario
    parser_fp_buscar = subparsers_fp.add_parser('buscar', help='Busca folhas de ponto por NOME do funcionário (+ período/status)')
    parser_fp_buscar.add_argument('--nome', type=str, help='Nome (ou parte) do funcionário', required=False)
    parser_fp_buscar.add_argument('--mes', type=str, help='Mês YYYY-MM para filtrar', required=False)
    parser_fp_buscar.add_argument('--status', type=str, help='Status da folha (criada, preenchida, ...)', required=False)
    parser_fp_buscar.add_argument('--incluir-excluidas', action='store_true', help='Inclui folhas com soft delete', required=False)

    # Subcomando: excluir - soft delete de folha
    parser_fp_excluir = subparsers_fp.add_parser('excluir', help='Exclui (SOFT DELETE) uma folha de ponto — marca como excluída, nunca remove do banco')
    parser_fp_excluir.add_argument('--id', type=str, help='ObjectId da folha', required=True)
    parser_fp_excluir.add_argument('--motivo', type=str, help='Motivo da exclusão', required=False)
    parser_fp_excluir.add_argument('--force', '-f', action='store_true', help='Não pedir confirmação (mesmo se já enviada)', required=False)

    # Subcomando: editar - edita folha ja gerada
    parser_fp_editar = subparsers_fp.add_parser('editar', help='Edita folha ja gerada (recalcula totais, regenera PDF, nova versão + histórico)')
    parser_fp_editar.add_argument('--id', type=str, help='ObjectId da folha', required=True)
    parser_fp_editar.add_argument('--dia', type=int, help='Número do dia a editar (usar com --hora-entrada etc)', required=False)
    parser_fp_editar.add_argument('--hora_entrada', type=str, help='Hora de entrada (HH:MM)', required=False)
    parser_fp_editar.add_argument('--hora_saida', type=str, help='Hora de saída (HH:MM)', required=False)
    parser_fp_editar.add_argument('--intervalo_inicio', type=str, help='Início do intervalo (HH:MM)', required=False)
    parser_fp_editar.add_argument('--intervalo_fim', type=str, help='Fim do intervalo (HH:MM)', required=False)
    parser_fp_editar.add_argument('--tipo_dia', type=str, help='Tipo do dia (NORMAL, FALTA, FERIADO, etc)', required=False)
    parser_fp_editar.add_argument('--observacoes', type=str, help='Observações do dia', required=False)
    # Suporta múltiplos --dia para editar vários dias de uma vez
    parser_fp_editar.add_argument('--diretorio_destino', type=str, help='Diretório customizado para o PDF', required=False)

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
    parser_fp_envio_exec.add_argument('--fonte', type=str, choices=['mongodb', 'planilha'], default=None,
                                     help='Fonte das configurações de envio (default: MongoDB com fallback planilha)')

    # ==================== SUBCOMANDOS DE CONFIG DE ENVIO (MongoDB) ====================

    # envio-config-criar - cria uma configuração de envio no MongoDB
    parser_fp_config_criar = subparsers_fp.add_parser('envio-config-criar', help='Cria uma configuração de envio no MongoDB (interativo)')

    # envio-config-listar - lista configurações
    parser_fp_config_listar = subparsers_fp.add_parser('envio-config-listar', help='Lista configurações de envio no MongoDB')
    parser_fp_config_listar.add_argument('--todos', action='store_true', help='Inclui configs inativas')
    parser_fp_config_listar.add_argument('--json', action='store_true', help='Formato JSON')

    # envio-config-buscar - busca configuração
    parser_fp_config_buscar = subparsers_fp.add_parser('envio-config-buscar', help='Busca configuração de envio')
    parser_fp_config_buscar.add_argument('--id', type=str, help='ID do documento (ObjectId)')
    parser_fp_config_buscar.add_argument('--nome', type=str, help='Nome do funcionário (busca parcial)')
    parser_fp_config_buscar.add_argument('--empresa', type=str, help='Nome da empresa')
    parser_fp_config_buscar.add_argument('--local', type=str, help='Local/Contrato/Polo')

    # envio-config-editar - edita configuração
    parser_fp_config_editar = subparsers_fp.add_parser('envio-config-editar', help='Edita configuração de envio (interativo)')
    parser_fp_config_editar.add_argument('id', help='ID do documento (ObjectId)')

    # envio-config-excluir - exclui (soft delete) configuração
    parser_fp_config_excluir = subparsers_fp.add_parser('envio-config-excluir', help='Exclui (soft delete) configuração de envio')
    parser_fp_config_excluir.add_argument('id', help='ID do documento (ObjectId)')

    # envio-config-reativar - reativa configuração excluída
    parser_fp_config_reativar = subparsers_fp.add_parser('envio-config-reativar', help='Reativa configuração de envio excluída')
    parser_fp_config_reativar.add_argument('id', help='ID do documento (ObjectId)')

    # envio-config-importar - importa da planilha Excel
    parser_fp_config_importar = subparsers_fp.add_parser('envio-config-importar', help='Importa configs da planilha Excel para o MongoDB')
    parser_fp_config_importar.add_argument('--sobrescrever', action='store_true', help='Atualiza configs existentes (mesmo ID)')
    parser_fp_config_importar.add_argument('--marcar-removidos', action='store_true', help='Marca (soft delete) configs que não estão mais na planilha')

    # envio-config-validar - valida configurações
    parser_fp_config_validar = subparsers_fp.add_parser('envio-config-validar', help='Valida configurações de envio no MongoDB')

    # envio-config-stats - estatísticas
    parser_fp_config_stats = subparsers_fp.add_parser('envio-config-stats', help='Exibe estatísticas das configurações de envio')

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
        
    # ==================== GERENCIAR FOLHAS GERADAS (CLI) ====================
    
    elif args.subcommand == "visualizar":
        """Visualiza uma folha de ponto já gerada (por id ou nome)"""
        from src.services.folha_ponto_service import FolhaDePontoService

        servico = FolhaDePontoService()
        if not servico.disponivel:
            logger.error("❌ MongoDB não disponível para visualizar folha")
            return

        folha = None
        if getattr(args, 'id', None):
            folha = servico.buscar_por_id(args.id)
            if not folha:
                logger.error(f"❌ Folha não encontrada com ID {args.id}")
                return
        elif getattr(args, 'nome', None):
            folhas = servico.buscar_por_nome_funcionario(
                nome=args.nome,
                mes_referencia=getattr(args, 'mes', None),
            )
            if not folhas:
                logger.error(f"❌ Nenhuma folha encontrada para nome '{args.nome}'")
                return
            if len(folhas) == 1:
                folha = servico.buscar_por_id(str(folhas[0]['_id']))
            else:
                logger.info(f"📋 {len(folhas)} folha(s) encontrada(s) para '{args.nome}':")
                for f in folhas:
                    fd = f.get('folha_data', {}) or {}
                    logger.info(
                        f"  • ID: {f.get('_id')} | {fd.get('nome_funcionario', 'N/A')} | "
                        f"{f.get('mes_referencia', '')} | {f.get('status', '')}"
                    )
                return
        else:
            logger.error("❌ Informe --id ou --nome para visualizar")
            return

        if not folha:
            logger.error("❌ Não foi possível recuperar a folha")
            return

        fd = folha.get('folha_data', {}) or {}
        logger.info("=" * 60)
        logger.info("📋 FOLHA DE PONTO")
        logger.info("=" * 60)
        logger.info(f"ID: {folha.get('_id')}")
        logger.info(f"Funcionário: {fd.get('nome_funcionario', 'N/A')}")
        logger.info(f"Mês: {folha.get('mes_referencia', '')}")
        logger.info(
            f"Período: {formatar_data_br(fd.get('data_inicio'))} a "
            f"{formatar_data_br(fd.get('data_fim'))}"
        )
        logger.info(f"Total horas mês: {fd.get('total_horas_mes', 'N/A')}")
        logger.info(f"Faltas: {fd.get('total_faltas', 0)}")
        logger.info(f"Feriados: {fd.get('total_feriados', 0)}")
        logger.info(f"Finais de semana: {fd.get('total_finais_semana', 0)}")
        logger.info(f"Status: {folha.get('status', 'N/A')}")
        logger.info(f"Versão: {folha.get('versao', 1)}")
        logger.info(f"Excluída: {'SIM' if folha.get('excluida') else 'não'}")
        logger.info(f"PDF: {folha.get('caminho_arquivo_gerado') or 'N/A'}")

        dias = fd.get('dias', []) or []
        logger.info("-" * 60)
        logger.info(f"Dias ({len(dias)}):")
        for dia in dias:
            if isinstance(dia, dict):
                num = dia.get('numero_dia')
                entrada = dia.get('hora_entrada') or '-'
                saida = dia.get('hora_saida') or '-'
                tipo = dia.get('tipo_dia') or ''
                obs = dia.get('observacoes') or ''
            else:
                num = getattr(dia, 'numero_dia', None)
                entrada = getattr(dia, 'hora_entrada', None) or '-'
                saida = getattr(dia, 'hora_saida', None) or '-'
                tipo = getattr(dia, 'tipo_dia', '') or ''
                obs = getattr(dia, 'observacoes', '') or ''
            if hasattr(tipo, 'value'):
                tipo = tipo.value
            logger.info(f"  Dia {num}: {entrada} -> {saida} [{tipo}] {obs}")

    elif args.subcommand == "buscar":
        """Busca folhas de ponto por NOME do funcionário (+ período/status)"""
        from src.services.folha_ponto_service import FolhaDePontoService

        servico = FolhaDePontoService()
        if not servico.disponivel:
            logger.error("❌ MongoDB não disponível para buscar folhas")
            return

        nome = getattr(args, 'nome', None)
        if not nome:
            nome = input("Nome (ou parte) do funcionário: ").strip()
        if not nome:
            logger.error("❌ Nome é obrigatório")
            return

        folhas = servico.buscar_por_nome_funcionario(
            nome=nome,
            mes_referencia=getattr(args, 'mes', None),
            status=getattr(args, 'status', None),
            incluir_excluidas=getattr(args, 'incluir_excluidas', False),
        )

        if not folhas:
            logger.info(f"ℹ Nenhuma folha encontrada para '{nome}'")
            return

        logger.info(f"\n🔍 {len(folhas)} folha(s) encontrada(s) para '{nome}':")
        logger.info("=" * 100)
        logger.info(f"{'ID':<28} {'Funcionário':<30} {'Mês':<10} {'Status':<20} {'Excluída'}")
        logger.info("-" * 100)
        for f in folhas:
            fd = f.get('folha_data', {}) or {}
            excluida = "SIM" if f.get('excluida') else "não"
            logger.info(
                f"{str(f.get('_id', '')):<28} {str(fd.get('nome_funcionario', 'N/A')):<30} "
                f"{str(f.get('mes_referencia', '')):<10} {str(f.get('status', '')):<20} {excluida}"
            )

    elif args.subcommand == "excluir":
        """Exclui folha (SOFT DELETE): marca como excluída, nunca remove do banco"""
        from src.services.folha_ponto_service import FolhaDePontoService

        servico = FolhaDePontoService()
        if not servico.disponivel:
            logger.error("❌ MongoDB não disponível para excluir folha")
            return

        folha = servico.buscar_por_id(args.id)
        if not folha:
            logger.error(f"❌ Folha não encontrada com ID {args.id}")
            return

        if folha.get('excluida'):
            logger.warning(f"⚠ Folha {args.id} já está marcada como excluída")
            return

        nome_func = (folha.get('folha_data', {}) or {}).get('nome_funcionario', 'N/A')
        mes_ref = folha.get('mes_referencia', '')

        # Verificar se já foi enviada
        ja_enviada = False
        try:
            ja_enviada = servico.verificar_folha_enviada(args.id)
        except Exception as e:
            logger.debug(f"Erro ao verificar envio: {e}")

        if ja_enviada and not getattr(args, 'force', False):
            logger.warning(
                f"⚠ Esta folha de {nome_func} ({mes_ref}) já possui ENVIO registrado.\n"
                "   O soft delete PRESERVA o registro e o histórico de envio.\n"
                "   Use --force para prosseguir sem confirmação."
            )
            confirma = input("Confirma? (SIM para prosseguir): ").strip().upper()
            if confirma != "SIM":
                logger.info("Operação cancelada.")
                return
        elif not getattr(args, 'force', False):
            confirma = input(
                f"Marcar a folha de {nome_func} ({mes_ref}) como EXCLUÍDA? (SIM): "
            ).strip().upper()
            if confirma != "SIM":
                logger.info("Operação cancelada.")
                return

        resultado = servico.marcar_excluida(args.id, motivo=getattr(args, 'motivo', None))
        if resultado:
            logger.info(f"✅ Folha de {nome_func} ({mes_ref}) marcada como EXCLUÍDA (soft delete).")
            logger.info("   Registro mantido no banco com histórico e envios preservados.")
        else:
            logger.error("❌ Falha ao marcar a folha como excluída")

    elif args.subcommand == "editar":
        """Edita folha já gerada (recalcula totais, regenera PDF, nova versão + histórico)"""
        from src.services.folha_ponto_service import FolhaDePontoService

        servico = FolhaDePontoService()
        if not servico.disponivel:
            logger.error("❌ MongoDB não disponível para editar folha")
            return

        folha = servico.buscar_por_id(args.id)
        if not folha:
            logger.error(f"❌ Folha não encontrada com ID {args.id}")
            return

        if folha.get('excluida'):
            logger.error("❌ Folha está EXCLUÍDA (soft delete). Edição bloqueada.")
            return

        # Verificar se já foi enviada (aviso, rastreabilidade via versão/histórico)
        try:
            if servico.verificar_folha_enviada(args.id):
                logger.warning("⚠ Esta folha já possui ENVIO registrado. A edição será rastreada "
                               "(nova versão + histórico). Considere re-enviar a folha corrigida.")
        except Exception as e:
            logger.debug(f"Erro ao verificar envio: {e}")

        dias_editados = []

        if getattr(args, 'dia', None) is not None:
            edicao = {"numero_dia": args.dia}
            if getattr(args, 'hora_entrada', None):
                edicao["hora_entrada"] = args.hora_entrada
            if getattr(args, 'hora_saida', None):
                edicao["hora_saida"] = args.hora_saida
            if getattr(args, 'intervalo_inicio', None):
                edicao["hora_intervalo_inicio"] = args.intervalo_inicio
            if getattr(args, 'intervalo_fim', None):
                edicao["hora_intervalo_fim"] = args.intervalo_fim
            if getattr(args, 'tipo_dia', None):
                edicao["tipo_dia"] = args.tipo_dia
            if getattr(args, 'observacoes', None):
                edicao["observacoes"] = args.observacoes
            dias_editados.append(edicao)
        else:
            # Modo interativo: editar dia a dia até 'sair'
            logger.info("Edição interativa — informe os dias a corrigir (ou 'sair' para concluir).")
            while True:
                dia_input = input("Número do dia (1-31) ou 'sair': ").strip()
                if not dia_input:
                    continue
                if dia_input.lower() == 'sair':
                    break
                try:
                    numero = int(dia_input)
                except ValueError:
                    logger.warning("Dia inválido.")
                    continue

                edicao = {"numero_dia": numero}
                entrada = input(f"  Hora entrada dia {numero} (ENTER mantém): ").strip()
                if entrada:
                    edicao["hora_entrada"] = entrada
                saida = input(f"  Hora saída dia {numero} (ENTER mantém): ").strip()
                if saida:
                    edicao["hora_saida"] = saida
                obs = input(f"  Observações dia {numero} (ENTER mantém): ").strip()
                if obs:
                    edicao["observacoes"] = obs
                tipo = input(f"  Tipo dia {numero} (NORMAL/FALTA/FERIADO... ENTER mantém): ").strip().upper()
                if tipo:
                    edicao["tipo_dia"] = tipo

                if len(edicao) > 1:
                    dias_editados.append(edicao)
                    logger.info(f"  ✓ Dia {numero} registrado")
                else:
                    logger.info("  Nenhuma alteração para esse dia.")

        if not dias_editados:
            logger.error("❌ Nenhuma edição informada.")
            return

        confirma = input(f"Confirmar edição da folha {args.id}? (SIM): ").strip().upper()
        if confirma != "SIM":
            logger.info("Operação cancelada.")
            return

        fp = Folha_de_Ponto()
        resultado = fp.editar_folha(
            folha_id=args.id,
            dias_editados=dias_editados,
            atualizar_pdf=True,
            diretorio_destino=getattr(args, 'diretorio_destino', None),
        )

        if resultado and resultado.get('status') == 'sucesso':
            logger.info(f"✅ Folha editada com sucesso (versão {resultado.get('versao')})")
            totais = resultado.get('totais', {}) or {}
            logger.info(f"   Totais recalculados: {totais.get('total_horas_mes', '-')}h | "
                        f"faltas: {totais.get('total_faltas', 0)} | "
                        f"feriados: {totais.get('total_feriados', 0)}")
            if resultado.get('caminho_pdf'):
                logger.info(f"   📕 PDF regenerado: {resultado['caminho_pdf']}")
            else:
                logger.warning("   ⚠ PDF não foi regenerado (verifique logs).")
        else:
            motivo = (resultado or {}).get('motivo', '')
            logger.error(f"❌ Falha ao editar a folha. {motivo}")

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

        # Fonte das configurações (default: MongoDB com fallback planilha)
        usar_mongodb = True
        if hasattr(args, 'fonte') and args.fonte == 'planilha':
            usar_mongodb = False
            print("Fonte: Planilha Excel (forçada)")
        elif hasattr(args, 'fonte') and args.fonte == 'mongodb':
            print("Fonte: MongoDB (forçada)")

        relatorio = envio_folha_ponto_orquestrador.executar(
            mes=mes,
            ano=ano,
            tipos_envio=tipos,
            contatos_ids=contatos_ids,
            dry_run=dry_run,
            usar_mongodb=usar_mongodb
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

    # ==================== CONFIGS DE ENVIO (MongoDB) ====================

    elif args.subcommand == "envio-config-listar":
        """Lista configurações de envio no MongoDB"""
        from src.services.config_envio_folha_ponto_service import config_envio_folha_ponto_service

        if not config_envio_folha_ponto_service.disponivel:
            print("✗ MongoDB de configurações não disponível")
            return

        configs = config_envio_folha_ponto_service.listar(
            apenas_ativas=not getattr(args, 'todos', False),
            limit=100000,
        )

        if getattr(args, 'json', False):
            import json
            print(json.dumps([
                {"id": str(c["_id"]), "identificador": c.get("identificador"), "nome": c.get("nome"),
                 "empresa": c.get("empresa"), "local": c.get("local_contrato_polo"),
                 "email": c.get("enviar_email"), "whatsapp": c.get("enviar_whatsapp"),
                 "grupo": c.get("enviar_grupo_whatsapp")}
                for c in configs
            ], ensure_ascii=False, indent=2))
            return

        print(f"\n--- Configurações de Envio ({len(configs)}) ---")
        print(f"{'ID':<6} {'Nome':<30} {'Local':<22} {'E':<3} {'WA':<3} {'GR':<3} {'Ativa':<6}")
        print("-" * 80)
        for c in configs:
            print(f"{str(c['_id'])[-6:]:<6} {c.get('nome','')[:29]:<30} "
                  f"{c.get('local_contrato_polo','')[:21]:<22} "
                  f"{c.get('enviar_email',''):<3} {c.get('enviar_whatsapp',''):<3} "
                  f"{c.get('enviar_grupo_whatsapp',''):<3} {'✓' if c.get('ativo') else ''}")

    elif args.subcommand == "envio-config-buscar":
        """Busca configuração de envio"""
        from src.services.config_envio_folha_ponto_service import config_envio_folha_ponto_service

        if not config_envio_folha_ponto_service.disponivel:
            print("✗ MongoDB de configurações não disponível")
            return

        resultados = []
        if getattr(args, 'id', None):
            doc = config_envio_folha_ponto_service.buscar_por_id(args.id, incluir_excluidas=True)
            if doc:
                resultados.append(doc)
        elif getattr(args, 'nome', None):
            resultados = config_envio_folha_ponto_service.buscar_por_nome(args.nome)
        elif getattr(args, 'empresa', None):
            resultados = config_envio_folha_ponto_service.buscar_por_empresa(args.empresa)
        elif getattr(args, 'local', None):
            resultados = config_envio_folha_ponto_service.buscar_por_local(args.local)
        else:
            print("Informe --id, --nome, --empresa ou --local")
            return

        if not resultados:
            print("Nenhuma configuração encontrada")
            return

        for doc in resultados:
            print(f"\nID: {doc.get('_id')}")
            print(f"Identificador: {doc.get('identificador')}")
            print(f"Nome: {doc.get('nome')}")
            print(f"Emails: {', '.join(doc.get('emails', [])) or '-'}")
            print(f"Telefones: {', '.join(doc.get('telefones', [])) or '-'}")
            print(f"Grupos WhatsApp: {', '.join(doc.get('grupos_whatsapp', [])) or '-'}")
            print(f"Enviar Email: {doc.get('enviar_email')} | WhatsApp: {doc.get('enviar_whatsapp')} | Grupo: {doc.get('enviar_grupo_whatsapp')} | Impresso: {doc.get('enviar_impresso')}")
            print(f"Empresa: {doc.get('empresa')}")
            print(f"Local/Contrato/Polo: {doc.get('local_contrato_polo')}")
            print(f"Diretório Geral: {doc.get('diretorio_geral')}")
            print(f"Diretório Específico: {doc.get('diretorio_especifico')}")
            print(f"Ativa: {'✓' if doc.get('ativo') else '✗'} | Excluída: {'✓' if doc.get('excluida') else '✗'}")
            print(f"Origem: {doc.get('origem')}")

    elif args.subcommand == "envio-config-criar":
        """Cria configuração de envio no MongoDB (interativo)"""
        from src.services.config_envio_folha_ponto_service import config_envio_folha_ponto_service

        if not config_envio_folha_ponto_service.disponivel:
            print("✗ MongoDB de configurações não disponível")
            return

        identificador = input("Identificador (ID da linha/contato): ").strip()
        nome = input("Nome completo: ").strip()
        email = input("Emails (separados por ,): ").strip()
        telefone = input("Telefones (separados por ,): ").strip()
        grupos = input("Grupos WhatsApp (separados por ,): ").strip()

        def _flag(mensagem: str, padrao: str = "N") -> str:
            v = input(f"{mensagem} (S/N) [{padrao}]: ").strip().upper()
            return v if v in ("S", "N") else padrao

        dados = {
            "identificador": identificador,
            "nome": nome,
            "emails": [e.strip() for e in email.split(",") if e.strip()] if email else [],
            "telefones": [t.strip() for t in telefone.split(",") if t.strip()] if telefone else [],
            "grupos_whatsapp": [g.strip() for g in grupos.split(",") if g.strip()] if grupos else [],
            "enviar_email": _flag("Enviar por email"),
            "enviar_whatsapp": _flag("Enviar por WhatsApp individual"),
            "enviar_grupo_whatsapp": _flag("Enviar para grupo WhatsApp"),
            "enviar_impresso": _flag("Enviar impresso"),
            "empresa": input("Empresa: ").strip(),
            "local_contrato_polo": input("Local/Contrato/Polo: ").strip(),
            "diretorio_geral": input("Diretório geral: ").strip(),
            "diretorio_especifico": input("Diretório específico: ").strip(),
        }

        novo_id = config_envio_folha_ponto_service.criar(dados)
        if novo_id:
            print(f"✓ Configuração criada: {novo_id}")
        else:
            print("✗ Erro ao criar configuração")

    elif args.subcommand == "envio-config-editar":
        """Edita configuração de envio (interativo)"""
        from src.services.config_envio_folha_ponto_service import config_envio_folha_ponto_service

        if not config_envio_folha_ponto_service.disponivel:
            print("✗ MongoDB de configurações não disponível")
            return

        doc = config_envio_folha_ponto_service.buscar_por_id(args.id, incluir_excluidas=True)
        if not doc:
            print(f"✗ Configuração {args.id} não encontrada")
            return

        print(f"\nEditando: {doc.get('nome')} ({doc.get('identificador')})")

        def _campos_lista(campo: str) -> List[str]:
            atual = doc.get(campo, [])
            novo = input(f"{campo} [{', '.join(atual)}] (enter para manter): ").strip()
            if not novo:
                return atual
            return [x.strip() for x in novo.split(",") if x.strip()]

        def _flag(campo: str) -> str:
            atual = doc.get(campo, "N")
            novo = input(f"{campo} [{atual}] (S/N, enter para manter): ").strip().upper()
            return novo if novo in ("S", "N") else atual

        alteracoes = {}

        emails = _campos_lista("emails")
        telefones = _campos_lista("telefones")
        grupos = _campos_lista("grupos_whatsapp")
        if emails != doc.get("emails"): alteracoes["emails"] = emails
        if telefones != doc.get("telefones"): alteracoes["telefones"] = telefones
        if grupos != doc.get("grupos_whatsapp"): alteracoes["grupos_whatsapp"] = grupos

        for campo, _ in [("enviar_email", ""), ("enviar_whatsapp", ""), ("enviar_grupo_whatsapp", ""), ("enviar_impresso", "")]:
            novo_flag = _flag(campo)
            if novo_flag != doc.get(campo):
                alteracoes[campo] = novo_flag

        if not alteracoes:
            print("Nenhuma alteração.")
            return

        if config_envio_folha_ponto_service.atualizar(args.id, alteracoes):
            print("✓ Configuração atualizada")
        else:
            print("✗ Erro ao atualizar configuração")

    elif args.subcommand == "envio-config-excluir":
        """Exclui (soft delete) configuração de envio"""
        from src.services.config_envio_folha_ponto_service import config_envio_folha_ponto_service

        doc = config_envio_folha_ponto_service.buscar_por_id(args.id, incluir_excluidas=True)
        if not doc:
            print(f"✗ Configuração {args.id} não encontrada")
            return

        confirma = input(f"Excluir (soft delete) '{doc.get('nome')}'? (SIM): ").strip().upper()
        if confirma != "SIM":
            print("Cancelado.")
            return

        if config_envio_folha_ponto_service.excluir(args.id):
            print("✓ Configuração excluída (soft delete)")
        else:
            print("✗ Erro ao excluir configuração")

    elif args.subcommand == "envio-config-reativar":
        """Reativa configuração de envio excluída"""
        from src.services.config_envio_folha_ponto_service import config_envio_folha_ponto_service

        if config_envio_folha_ponto_service.reativar(args.id):
            print("✓ Configuração reativada")
        else:
            print("✗ Erro ao reativar configuração")

    elif args.subcommand == "envio-config-importar":
        """Importa configs da planilha Excel para o MongoDB"""
        from src.services.config_envio_folha_ponto_service import config_envio_folha_ponto_service

        if not config_envio_folha_ponto_service.disponivel:
            print("✗ MongoDB de configurações não disponível")
            return

        sobrescrever = getattr(args, 'sobrescrever', False)
        marcar_removidos = getattr(args, 'marcar_removidos', False)

        print("Importando configurações da planilha Excel...")
        resumo = config_envio_folha_ponto_service.importar_da_planilha(
            sobrescrever=sobrescrever,
            marcar_removidos=marcar_removidos,
        )

        print(f"\n--- Resumo da Importação ---")
        print(f"Total na planilha: {resumo.get('total_planilha', 0)}")
        print(f"Criados: {resumo.get('criados', 0)}")
        print(f"Atualizados: {resumo.get('atualizados', 0)}")
        print(f"Pulados (já existem): {resumo.get('pulados', 0)}")
        print(f"Erros: {resumo.get('erros', 0)}")
        if 'removidos' in resumo:
            print(f"Removidos (soft delete): {resumo.get('removidos', 0)}")

    elif args.subcommand == "envio-config-validar":
        """Valida configurações de envio no MongoDB"""
        from src.services.config_envio_folha_ponto_service import config_envio_folha_ponto_service

        if not config_envio_folha_ponto_service.disponivel:
            print("✗ MongoDB de configurações não disponível")
            return

        resultado = config_envio_folha_ponto_service.validar()

        print(f"\nTotal de configs: {resultado.get('total_configs', 0)}")
        if resultado.get("valida"):
            print("✓ Configurações válidas")
        else:
            print("✗ Problemas encontrados:")
            for p in resultado.get("problemas", []):
                print(f"  • {p}")
            if resultado.get("avisos"):
                print("\nAvisos:")
                for a in resultado.get("avisos", []):
                    print(f"  ~ {a}")

    elif args.subcommand == "envio-config-stats":
        """Exibe estatísticas das configurações de envio"""
        from src.services.config_envio_folha_ponto_service import config_envio_folha_ponto_service

        if not config_envio_folha_ponto_service.disponivel:
            print("✗ MongoDB de configurações não disponível")
            return

        stats = config_envio_folha_ponto_service.contar()
        print(f"\n--- Estatísticas de Configurações de Envio ---")
        print(f"Total (não excluídas): {stats.get('total', 0)}")
        print(f"Ativas: {stats.get('ativas', 0)}")
        print(f"Inativas: {stats.get('inativas', 0)}")
        print(f"Excluídas (soft delete): {stats.get('excluidas', 0)}")

    else:
        # Exibe a ajuda quando nenhum subcomando é fornecido
        parser_fp.print_help()
        pass




