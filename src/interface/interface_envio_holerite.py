"""
Interface de Menu para Envio de Holerites
Responsabilidades:
- Menu interativo no terminal
- Dois modos: via planilha ou via MongoDB
- Opcoes de configuracao e envio
- Exibicao de relatorios e status
"""

from datetime import datetime
from typing import Optional

from src.utils.logger_config import logger
from src.processadores.envio_holerite_orquestrador import (
    envio_holerite_orquestrador,
    RelatorioEnvioHolerite,
    MESES_EXTENSO
)
from src.services.holerite_service import holerite_service
from src.services.template_mensagem_service import template_mensagem_service
from src.services.grupo_whatsapp_service import grupo_whatsapp_service

from src.interface.core.components import (
    MenuBuilder,
    exibir_cabecalho,
    exibir_sucesso,
    exibir_erro,
    exibir_aviso,
    exibir_info,
    exibir_tabela,
    exibir_resultado,
    exibir_painel,
    pausar,
    pedir_confirmacao,
    pedir_texto,
    pedir_selecao,
    pedir_inteiro,
)
from src.interface.core.theme import console, ICONES

# Tentar importar planilha de holerites
try:
    from src.services.planilha_holerites_service import planilha_holerites_service
    PLANILHA_DISPONIVEL = True
except ImportError:
    PLANILHA_DISPONIVEL = False
    planilha_holerites_service = None


def solicitar_competencia() -> str:
    """Solicita competencia ao usuario no formato MM/AAAA"""
    agora = datetime.now()

    mes = pedir_inteiro(
        "Mes de referencia (1-12)",
        obrigatorio=False,
        minimo=1,
        maximo=12,
        padrao=agora.month
    )
    if mes is None:
        mes = agora.month

    ano = pedir_inteiro(
        "Ano de referencia",
        obrigatorio=False,
        minimo=2020,
        maximo=2099,
        padrao=agora.year
    )
    if ano is None:
        ano = agora.year

    return f"{mes:02d}/{ano}"


def exibir_relatorio(relatorio: RelatorioEnvioHolerite):
    """Exibe relatorio de envio formatado"""
    exibir_cabecalho(f"RELATORIO DE ENVIO - {relatorio.competencia}", icone=ICONES["relatorio"])

    mes_nome = relatorio.competencia.split('/')[0] if '/' in relatorio.competencia else relatorio.competencia
    try:
        mes_num = int(mes_nome)
        mes_extenso = MESES_EXTENSO.get(mes_num, relatorio.competencia)
    except:
        mes_extenso = relatorio.competencia

    # Painel com resumo principal
    conteudo_resumo = f"""[cyan]Periodo:[/cyan] {mes_extenso}
[cyan]Modo de envio:[/cyan] {relatorio.modo_envio.upper()}
[cyan]Total de holerites processados:[/cyan] {relatorio.total_holerites}
[cyan]Total de envios realizados:[/cyan] {relatorio.total_envios}
[cyan]Duracao:[/cyan] {relatorio.duracao_segundos():.1f} segundos"""

    exibir_painel(conteudo_resumo, titulo="Resumo Geral", estilo_borda="cyan")

    # Resultado por status
    console.print(f"\n{ICONES['estatistica']} [bold]Resultado por Status[/bold]")
    console.print(f"  {ICONES['sucesso']} Sucesso: [green]{relatorio.enviados_sucesso}[/green]")
    console.print(f"  {ICONES['erro']} Erro: [red]{relatorio.enviados_erro}[/red]")

    # Resultado por tipo
    if relatorio.por_tipo:
        console.print(f"\n{ICONES['estatistica']} [bold]Resultado por Tipo[/bold]")
        for tipo, stats in relatorio.por_tipo.items():
            console.print(f"  [cyan]{tipo}:[/cyan]")
            console.print(f"    Sucesso: [green]{stats.get('sucesso', 0)}[/green]")
            console.print(f"    Erro: [red]{stats.get('erro', 0)}[/red]")

    # Erros
    if relatorio.erros:
        console.print(f"\n{ICONES['erro']} [bold red]Erros ({len(relatorio.erros)})[/bold red]")
        for erro in relatorio.erros[:10]:  # Limitar a 10 erros
            contato = erro.get('contato', erro.get('funcionario', 'N/A'))
            console.print(f"  {ICONES['ponto']} {contato} ({erro.get('tipo', 'N/A')}): {erro.get('erro', 'N/A')}")

        if len(relatorio.erros) > 10:
            console.print(f"  ... e mais {len(relatorio.erros) - 10} erros")


def menu_verificar_servicos():
    """Menu para verificar status dos servicos"""
    exibir_cabecalho("VERIFICACAO DE SERVICOS", icone=ICONES["config"])

    console.print("\nVerificando conexoes...")
    status = envio_holerite_orquestrador.verificar_servicos()

    # Preparar conteudo do painel
    linhas = []
    for servico, disponivel in status.items():
        icone = ICONES["sucesso"] if disponivel else ICONES["erro"]
        cor = "green" if disponivel else "red"
        status_texto = "OK" if disponivel else "Indisponivel"
        linhas.append(f"{icone} [cyan]{servico}:[/cyan] [{cor}]{status_texto}[/{cor}]")

    conteudo = "\n".join(linhas)
    exibir_painel(conteudo, titulo="Status dos Servicos", estilo_borda="cyan")

    pausar()


def _selecionar_empresa_para_grupos() -> tuple[str | None, str | None]:
    """
    Exibe lista de empresas ativas com device configurado e solicita selecao.

    Returns:
        Tupla (device_id, nome_empresa) ou (None, None) se cancelado/erro
    """
    try:
        from src.services.empresa_service import empresa_service

        if not empresa_service or not empresa_service.disponivel:
            exibir_erro("Servico de empresas nao disponivel!")
            return None, None

        # Buscar empresas ativas com device configurado
        empresas_ativas = empresa_service.listar_ativos()

        # Filtrar apenas empresas com device_id configurado
        empresas_com_device = [
            e for e in empresas_ativas
            if e.get('whatsapp_device_id')
        ]

        if not empresas_com_device:
            exibir_aviso("Nenhuma empresa com dispositivo WhatsApp configurado.")
            exibir_info("Configure o whatsapp_device_id nas empresas primeiro.")
            return None, None

        # Preparar opcoes para selecao
        opcoes = []
        for empresa in empresas_com_device:
            nome = empresa.get('nome', 'N/A')
            nome_simples = empresa.get('nome_simplificado', '')
            device_id = empresa.get('whatsapp_device_id', 'N/A')
            display_nome = f"{nome} ({nome_simples})" if nome_simples else nome
            opcoes.append(f"{display_nome} - Device: {device_id}")

        resultado = pedir_selecao(
            "Selecione a empresa",
            opcoes,
            instrucao=f"{len(empresas_com_device)} empresa(s) com dispositivo WhatsApp"
        )

        if not resultado:
            exibir_info("Operacao cancelada.")
            return None, None

        # Extrair indice da opcao selecionada
        indice = opcoes.index(resultado)
        empresa_selecionada = empresas_com_device[indice]
        device_id = empresa_selecionada.get('whatsapp_device_id')
        nome_empresa = empresa_selecionada.get('nome')

        if not device_id:
            exibir_erro(f"Empresa '{nome_empresa}' nao tem dispositivo WhatsApp configurado!")
            return None, None

        exibir_sucesso(f"Empresa selecionada: {nome_empresa}")
        exibir_info(f"Device ID: {device_id}")
        return device_id, nome_empresa

    except Exception as e:
        logger.error(f"Erro ao selecionar empresa: {e}")
        exibir_erro(f"Erro: {e}")
        return None, None


def menu_sincronizar_grupos():
    """Menu para sincronizar grupos do WhatsApp"""
    exibir_cabecalho("SINCRONIZAR GRUPOS WHATSAPP", icone=ICONES["whatsapp"])

    console.print("\nSincronizando grupos com a API do WhatsApp...")

    try:
        from src.processadores.envio_folha_ponto_orquestrador import envio_folha_ponto_orquestrador
        resultado = envio_folha_ponto_orquestrador.sincronizar_grupos_whatsapp()

        # Exibir resultado em painel
        conteudo = f"""[green]Grupos criados:[/green] {resultado.get('criados', 0)}
[cyan]Grupos atualizados:[/cyan] {resultado.get('atualizados', 0)}
[yellow]Grupos inativos:[/yellow] {resultado.get('inativos', 0)}"""

        exibir_painel(conteudo, titulo="Resultado da Sincronizacao", estilo_borda="green")

    except Exception as e:
        exibir_erro(f"Erro na sincronizacao: {e}")

    # Perguntar se deseja listar grupos
    ver_grupos = pedir_confirmacao("Deseja ver os grupos sincronizados?", padrao=False)
    if not ver_grupos:
        pausar()
        return

    # Selecionar empresa para listar grupos
    console.print("\nPara listar grupos, selecione a empresa/dispositivo:")
    device_id, nome_empresa = _selecionar_empresa_para_grupos()

    if not device_id:
        pausar()
        return

    # Listar grupos da empresa selecionada
    try:
        grupos = grupo_whatsapp_service.listar_para_exibicao(device_id)
        if grupos:
            # Preparar dados para tabela
            dados = []
            for g in grupos[:20]:  # Limitar a 20
                dados.append([g['nome'], g['participantes']])

            exibir_tabela(
                titulo=f"Grupos de '{nome_empresa}' ({len(grupos)})",
                colunas=["Nome do Grupo", "Participantes"],
                dados=dados,
                mostrar_indice=False
            )

            if len(grupos) > 20:
                exibir_info(f"... e mais {len(grupos) - 20} grupos")
        else:
            exibir_aviso(f"Nenhum grupo encontrado para '{nome_empresa}'")
    except ValueError as e:
        exibir_erro(f"Erro: {e}")

    pausar()


def menu_validar_planilha():
    """Menu para validar planilha de contatos de holerites"""
    exibir_cabecalho("VALIDAR PLANILHA DE CONTATOS DE HOLERITES", icone=ICONES["excel"])

    if not PLANILHA_DISPONIVEL:
        exibir_erro("Servico de planilha de holerites nao disponivel!")
        pausar()
        return

    console.print(f"\nCarregando planilha: [cyan]{planilha_holerites_service.planilha_path}[/cyan]")

    if not planilha_holerites_service.carregar():
        exibir_erro("Erro ao carregar planilha!")
        pausar()
        return

    resultado = planilha_holerites_service.validar_planilha()

    # Painel com resultado geral
    icone_valida = ICONES["sucesso"] if resultado.get('valida') else ICONES["erro"]
    valida_texto = "Sim" if resultado.get('valida') else "Nao"
    cor_valida = "green" if resultado.get('valida') else "red"

    conteudo = f"""[cyan]Total de linhas:[/cyan] {resultado.get('total_linhas', 0)}
{icone_valida} [cyan]Valida:[/cyan] [{cor_valida}]{valida_texto}[/{cor_valida}]"""

    exibir_painel(conteudo, titulo="Resultado da Validacao", estilo_borda="cyan")

    # Problemas
    if resultado.get("problemas"):
        console.print(f"\n{ICONES['aviso']} [bold yellow]Problemas encontrados ({len(resultado['problemas'])})[/bold yellow]")
        for problema in resultado["problemas"][:10]:
            console.print(f"  {ICONES['ponto']} {problema}")
        if len(resultado["problemas"]) > 10:
            console.print(f"  ... e mais {len(resultado['problemas']) - 10}")

    # Avisos
    if resultado.get("avisos"):
        console.print(f"\n{ICONES['aviso']} [bold yellow]Avisos ({len(resultado['avisos'])})[/bold yellow]")
        for aviso in resultado["avisos"][:5]:
            console.print(f"  {ICONES['ponto']} {aviso}")
        if len(resultado["avisos"]) > 5:
            console.print(f"  ... e mais {len(resultado['avisos']) - 5}")

    # Resumo de envios
    contagem = planilha_holerites_service.contar_envios_pendentes()

    dados_envios = [
        ["E-mail", contagem.get('email', 0)],
        ["WhatsApp Individual", contagem.get('whatsapp', 0)],
        ["WhatsApp Grupo", contagem.get('grupo_whatsapp', 0)]
    ]

    exibir_tabela(
        titulo="Envios Configurados",
        colunas=["Canal", "Contatos"],
        dados=dados_envios,
        mostrar_indice=False
    )

    pausar()


def menu_enviar_planilha_dry_run():
    """Menu para executar envio via planilha em modo simulacao"""
    exibir_cabecalho("ENVIO DE HOLERITES VIA PLANILHA (SIMULACAO)", icone=ICONES["holerite"])

    if not PLANILHA_DISPONIVEL:
        exibir_erro("Servico de planilha de holerites nao disponivel!")
        pausar()
        return

    competencia = solicitar_competencia()
    mes, ano = competencia.split('/')

    exibir_aviso("MODO SIMULACAO - Nenhum envio sera realizado")
    console.print(f"Periodo: [cyan]{MESES_EXTENSO.get(int(mes), mes)} de {ano}[/cyan]")

    confirma = pedir_confirmacao("Confirma execucao da simulacao?", padrao=False)
    if not confirma:
        exibir_info("Operacao cancelada.")
        pausar()
        return

    console.print("\nExecutando simulacao...")
    relatorio = envio_holerite_orquestrador.enviar_via_planilha(
        mes=int(mes),
        ano=int(ano),
        apenas_simular=True
    )

    exibir_relatorio(relatorio)
    pausar()


def menu_enviar_planilha_real():
    """Menu para executar envio via planilha real"""
    exibir_cabecalho("ENVIO DE HOLERITES VIA PLANILHA", icone=ICONES["enviar"])

    if not PLANILHA_DISPONIVEL:
        exibir_erro("Servico de planilha de holerites nao disponivel!")
        pausar()
        return

    competencia = solicitar_competencia()
    mes, ano = competencia.split('/')

    exibir_aviso("ATENCAO: Esta operacao ira enviar arquivos para os destinatarios!")
    console.print(f"Periodo: [cyan]{MESES_EXTENSO.get(int(mes), mes)} de {ano}[/cyan]")

    # Confirmacao digitada
    confirmacao_texto = pedir_texto(
        "Digite SIM para confirmar o envio",
        obrigatorio=True
    )

    if confirmacao_texto != "SIM":
        exibir_info("Operacao cancelada.")
        pausar()
        return

    console.print("\nExecutando envio...")
    relatorio = envio_holerite_orquestrador.enviar_via_planilha(
        mes=int(mes),
        ano=int(ano),
        apenas_simular=False
    )

    exibir_relatorio(relatorio)
    pausar()


def menu_enviar_mongodb_dry_run():
    """Menu para executar envio via MongoDB em modo simulacao"""
    exibir_cabecalho("ENVIO DE HOLERITES VIA MONGODB (SIMULACAO)", icone=ICONES["banco_dados"])

    competencia = solicitar_competencia()

    exibir_aviso("MODO SIMULACAO - Nenhum envio sera realizado")
    console.print(f"Periodo: [cyan]{competencia}[/cyan]")

    # Selecionar canais
    opcoes_canal = [
        "Todos (E-mail + WhatsApp)",
        "Apenas E-mail",
        "Apenas WhatsApp"
    ]

    canal_escolhido = pedir_selecao(
        "Selecione os canais de envio",
        opcoes_canal,
        instrucao="Escolha o canal"
    )

    if not canal_escolhido:
        exibir_info("Operacao cancelada.")
        pausar()
        return

    canais_map = {
        opcoes_canal[0]: ["email", "whatsapp"],
        opcoes_canal[1]: ["email"],
        opcoes_canal[2]: ["whatsapp"]
    }

    canais = canais_map.get(canal_escolhido, ["email", "whatsapp"])

    confirma = pedir_confirmacao("Confirma execucao da simulacao?", padrao=False)
    if not confirma:
        exibir_info("Operacao cancelada.")
        pausar()
        return

    console.print("\nExecutando simulacao...")
    relatorio = envio_holerite_orquestrador.enviar_via_mongodb(
        competencia=competencia,
        canais=canais,
        apenas_simular=True
    )

    exibir_relatorio(relatorio)
    pausar()


def menu_enviar_mongodb_real():
    """Menu para executar envio via MongoDB real"""
    exibir_cabecalho("ENVIO DE HOLERITES VIA MONGODB", icone=ICONES["enviar"])

    competencia = solicitar_competencia()

    # Mostrar estatisticas
    stats = envio_holerite_orquestrador.obter_estatisticas_competencia(competencia)

    conteudo_stats = f"""[cyan]Total de holerites:[/cyan] {stats.get('total', 0)}
[yellow]Pendentes de envio:[/yellow] {stats.get('pendentes', 0)}
[green]Ja enviados:[/green] {stats.get('enviados', 0)}
[red]Com erro:[/red] {stats.get('erros', 0)}"""

    exibir_painel(conteudo_stats, titulo=f"Estatisticas para {competencia}", estilo_borda="cyan")

    if stats.get('pendentes', 0) == 0:
        exibir_aviso("Nao ha holerites pendentes de envio para este periodo.")
        pausar()
        return

    # Selecionar canais
    opcoes_canal = [
        "Todos (E-mail + WhatsApp)",
        "Apenas E-mail",
        "Apenas WhatsApp"
    ]

    canal_escolhido = pedir_selecao(
        "Selecione os canais de envio",
        opcoes_canal,
        instrucao="Escolha o canal"
    )

    if not canal_escolhido:
        exibir_info("Operacao cancelada.")
        pausar()
        return

    canais_map = {
        opcoes_canal[0]: ["email", "whatsapp"],
        opcoes_canal[1]: ["email"],
        opcoes_canal[2]: ["whatsapp"]
    }

    canais = canais_map.get(canal_escolhido, ["email", "whatsapp"])

    exibir_aviso("ATENCAO: Esta operacao ira enviar arquivos para os destinatarios!")
    console.print(f"Periodo: [cyan]{competencia}[/cyan]")
    console.print(f"Canais: [cyan]{', '.join(canais)}[/cyan]")

    # Confirmacao digitada
    confirmacao_texto = pedir_texto(
        "Digite SIM para confirmar o envio",
        obrigatorio=True
    )

    if confirmacao_texto != "SIM":
        exibir_info("Operacao cancelada.")
        pausar()
        return

    console.print("\nExecutando envio...")
    relatorio = envio_holerite_orquestrador.enviar_via_mongodb(
        competencia=competencia,
        canais=canais,
        apenas_simular=False
    )

    exibir_relatorio(relatorio)
    pausar()


def menu_estatisticas():
    """Menu para visualizar estatisticas de holerites"""
    exibir_cabecalho("ESTATISTICAS DE HOLERITES", icone=ICONES["estatistica"])

    competencia = solicitar_competencia()

    stats = envio_holerite_orquestrador.obter_estatisticas_competencia(competencia)

    conteudo_geral = f"""[cyan]Total de holerites:[/cyan] {stats.get('total', 0)}
[yellow]Pendentes de envio:[/yellow] {stats.get('pendentes', 0)}
[green]Ja enviados:[/green] {stats.get('enviados', 0)}
[red]Com erro:[/red] {stats.get('erros', 0)}"""

    exibir_painel(conteudo_geral, titulo=f"Estatisticas para {competencia}", estilo_borda="cyan")

    # Por status
    por_status = stats.get("por_status", {})
    if por_status:
        console.print(f"\n{ICONES['estatistica']} [bold]Por Status[/bold]")
        for status, count in por_status.items():
            console.print(f"  [cyan]{status}:[/cyan] {count}")

    pausar()


def menu_templates():
    """Menu para gerenciar templates"""
    exibir_cabecalho("GERENCIAR TEMPLATES", icone=ICONES["config"])

    templates = template_mensagem_service.listar_todos()

    if not templates:
        exibir_info("Nenhum template encontrado.")
        exibir_info("Os templates padrao serao criados automaticamente no primeiro envio.")
        pausar()
        return

    # Preparar dados para tabela
    dados = []
    for t in templates:
        padrao_icone = ICONES["check"] if t.get("is_padrao") else " "
        tipo = t.get('tipo', 'N/A')
        nome = t.get('nome', 'N/A')
        dados.append([padrao_icone, tipo, nome])

    exibir_tabela(
        titulo=f"Templates Disponiveis ({len(templates)})",
        colunas=["Padrao", "Tipo", "Nome"],
        dados=dados,
        mostrar_indice=False
    )

    console.print(f"\n{ICONES['info']} ({ICONES['check']} = Template padrao para o tipo)")
    pausar()


def menu_listar_dispositivos():
    """Lista dispositivos WhatsApp conectados"""
    try:
        from src.services.whatsapp_service import whatsapp_service

        if not whatsapp_service.disponivel:
            exibir_erro("WhatsApp Service nao disponivel!")
            pausar()
            return

        console.print(f"\n{ICONES['whatsapp']} Listando dispositivos WhatsApp conectados...\n")
        dispositivos = whatsapp_service.listar_dispositivos()

        if not dispositivos:
            exibir_aviso("Nenhum dispositivo conectado encontrado")
            pausar()
            return

        # Preparar dados para tabela
        dados = []
        for d in dispositivos:
            jid = d.get('jid', 'N/A')
            display_name = d.get('display_name', 'Desconhecido')
            state = d.get('state', 'unknown')

            # Icone de status
            status_icone = ICONES["sucesso"] if state == "logged_in" else ICONES["erro"]

            # Extrair numero do JID
            numero = jid.split('@')[0] if '@' in jid else jid

            dados.append([status_icone, numero, display_name, jid])

        exibir_tabela(
            titulo=f"Dispositivos Conectados ({len(dispositivos)})",
            colunas=["Status", "Numero", "Nome", "JID"],
            dados=dados,
            mostrar_indice=False
        )

        pausar()

    except Exception as e:
        logger.error(f"Erro ao listar dispositivos: {e}")
        exibir_erro(f"Erro: {e}")
        pausar()


def menu_verificar_status_dispositivos():
    """Verifica status dos dispositivos configurados"""
    try:
        from src.services.whatsapp_service import whatsapp_service
        from src.services.empresa_service import empresa_service

        if not whatsapp_service.disponivel:
            exibir_erro("WhatsApp Service nao disponivel!")
            pausar()
            return

        console.print(f"\n{ICONES['processando']} Verificando status dos dispositivos...\n")

        # Obter dispositivos unicos das empresas configuradas
        empresas = empresa_service.listar_todos(limit=1000)['dados']
        dispositivos_unicos = set()

        for empresa in empresas:
            device_id = empresa.get('whatsapp_device_id')
            if device_id:
                dispositivos_unicos.add(device_id)

        if not dispositivos_unicos:
            exibir_aviso("Nenhuma empresa tem dispositivo configurado")
            pausar()
            return

        # Preparar dados para tabela
        dados = []
        for device_id in sorted(dispositivos_unicos):
            status = whatsapp_service.verificar_status_dispositivo(device_id)

            if status.get('sucesso'):
                is_logged = status.get('is_logged_in')
                status_icone = ICONES["sucesso"] if is_logged else ICONES["erro"]
                numero = status.get('numero', 'Desconhecido')
                mensagem = status.get('mensagem', 'N/A')
                dados.append([status_icone, numero, device_id, mensagem])
            else:
                dados.append([ICONES["erro"], "N/A", device_id, status.get('mensagem', 'Erro desconhecido')])

        exibir_tabela(
            titulo=f"Status de {len(dispositivos_unicos)} Dispositivo(s)",
            colunas=["Status", "Numero", "Device ID", "Mensagem"],
            dados=dados,
            mostrar_indice=False
        )

        pausar()

    except Exception as e:
        logger.error(f"Erro ao verificar status: {e}")
        exibir_erro(f"Erro: {e}")
        pausar()


def menu_mostrar_dispositivo_empresa():
    """Mostra dispositivo de uma empresa especifica"""
    try:
        from src.services.whatsapp_service import whatsapp_service
        from src.services.empresa_service import empresa_service

        if not whatsapp_service.disponivel:
            exibir_erro("WhatsApp Service nao disponivel!")
            pausar()
            return

        nome_empresa = pedir_texto("Nome da empresa", obrigatorio=True)
        if not nome_empresa:
            exibir_erro("Nome vazio!")
            pausar()
            return

        console.print(f"\n{ICONES['buscar']} Procurando empresa: [cyan]{nome_empresa}[/cyan]\n")

        empresa = empresa_service.buscar_por_nome_ou_simplificado(nome_empresa)

        if not empresa:
            exibir_erro(f"Empresa '{nome_empresa}' nao encontrada")
            pausar()
            return

        device_id = empresa.get('whatsapp_device_id')
        nome = empresa.get('nome')
        nome_simples = empresa.get('nome_simplificado', 'N/A')

        conteudo = f"""[cyan]Nome:[/cyan] {nome}
[cyan]Nome Simplificado:[/cyan] {nome_simples}"""

        if device_id:
            # Verificar status do device
            status = whatsapp_service.verificar_status_dispositivo(device_id)
            if status.get('sucesso'):
                is_logged = status.get('is_logged_in')
                status_icone = ICONES["sucesso"] if is_logged else ICONES["erro"]
                status_texto = "Conectado" if is_logged else "Desconectado"
                conteudo += f"\n[cyan]Device ID:[/cyan] {device_id}\n{status_icone} [cyan]Status:[/cyan] {status_texto}"
            else:
                conteudo += f"\n[cyan]Device ID:[/cyan] {device_id}\n{ICONES['aviso']} [cyan]Status:[/cyan] Nao foi possivel verificar"
        else:
            conteudo += f"\n{ICONES['aviso']} Nenhum dispositivo configurado para esta empresa"

        exibir_painel(conteudo, titulo=f"Empresa: {nome}", estilo_borda="cyan")
        pausar()

    except Exception as e:
        logger.error(f"Erro ao mostrar dispositivo: {e}")
        exibir_erro(f"Erro: {e}")
        pausar()


def menu_dispositivos():
    """Menu para gerenciar dispositivos WhatsApp"""
    menu = (
        MenuBuilder("GERENCIAR DISPOSITIVOS WHATSAPP - MULTIPLOS DISPOSITIVOS", icone=ICONES["whatsapp"])
        .adicionar("Listar dispositivos conectados", menu_listar_dispositivos)
        .adicionar("Verificar status dos dispositivos", menu_verificar_status_dispositivos)
        .adicionar("Mostrar dispositivo de uma empresa", menu_mostrar_dispositivo_empresa)
        .executar()
    )


def menu_modo_planilha():
    """Submenu para envio via planilha"""
    menu = (
        MenuBuilder("ENVIO DE HOLERITES - MODO PLANILHA", icone=ICONES["excel"])
        .adicionar("Validar Planilha de Contatos", menu_validar_planilha)
        .adicionar("Simulacao de Envio (Dry Run)", menu_enviar_planilha_dry_run)
        .adicionar("Executar Envio Real", menu_enviar_planilha_real)
        .executar()
    )


def menu_modo_mongodb():
    """Submenu para envio via MongoDB"""
    menu = (
        MenuBuilder("ENVIO DE HOLERITES - MODO MONGODB", icone=ICONES["banco_dados"])
        .adicionar("Ver Estatisticas", menu_estatisticas)
        .adicionar("Simulacao de Envio (Dry Run)", menu_enviar_mongodb_dry_run)
        .adicionar("Executar Envio Real", menu_enviar_mongodb_real)
        .executar()
    )


def menu_principal():
    """Menu principal do sistema de envio de holerites"""
    menu = (
        MenuBuilder("SISTEMA DE ENVIO DE HOLERITES", icone=ICONES["holerite"])
        .adicionar("Via Planilha (similar ao envio de folhas de ponto)", menu_modo_planilha)
        .adicionar("Via MongoDB (usa contatos cadastrados)", menu_modo_mongodb)
        .separador()
        .separador()
        .adicionar("Verificar Servicos", menu_verificar_servicos)
        .adicionar("Sincronizar Grupos WhatsApp", menu_sincronizar_grupos)
        .adicionar(f"Gerenciar Dispositivos WhatsApp {ICONES['whatsapp']}", menu_dispositivos)
        .adicionar("Gerenciar Templates", menu_templates)
        .executar()
    )


def iniciar_menu_envio_holerite():
    """Funcao de entrada para o menu de envio de holerites"""
    try:
        menu_principal()
    except KeyboardInterrupt:
        console.print("\n\nEncerrando...")
