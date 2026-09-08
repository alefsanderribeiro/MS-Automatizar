"""
Interface de Menu para Envio de Folhas de Ponto
Responsabilidades:
- Menu interativo no terminal
- Opcoes de configuracao e envio
- Exibicao de relatorios e status
"""

from datetime import datetime
from typing import Optional

from src.models.envio_folha_ponto_models import TipoEnvioEnum
from src.utils.logger_config_v2 import get_logger

# Logger do módulo
logger = get_logger("interface")

from src.processadores.envio_folha_ponto_orquestrador import (
    envio_folha_ponto_orquestrador,
    RelatorioEnvio,
    MESES_EXTENSO
)
from src.services.planilha_contatos_service import planilha_contatos_service
from src.services.envio_folha_ponto_service import envio_folha_ponto_service
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


def solicitar_mes_ano() -> tuple[int, int]:
    """Solicita mes e ano ao usuario"""
    agora = datetime.now()

    mes = pedir_inteiro(
        "Mes de referencia (1-12)",
        obrigatorio=False,
        minimo=1,
        maximo=12,
        padrao=agora.month
    )

    ano = pedir_inteiro(
        "Ano de referencia",
        obrigatorio=False,
        minimo=2020,
        maximo=2100,
        padrao=agora.year
    )

    return mes, ano


def exibir_relatorio(relatorio: RelatorioEnvio):
    """Exibe relatorio de envio formatado"""
    exibir_cabecalho(f"RELATORIO DE ENVIO - {relatorio.mes:02d}/{relatorio.ano}", ICONES["relatorio"])

    # Resumo principal
    resumo = f"""[bold]Periodo:[/bold] {MESES_EXTENSO.get(relatorio.mes, relatorio.mes)} de {relatorio.ano}
[bold]Total de contatos processados:[/bold] {relatorio.total_contatos}
[bold]Total de envios realizados:[/bold] {relatorio.total_envios}
[bold]Duracao:[/bold] {relatorio.duracao_segundos():.1f} segundos"""

    exibir_painel(resumo, titulo="Resumo Geral", estilo_borda="cyan")

    # Resultado por Status
    console.print("\n[bold cyan]Resultado por Status[/bold cyan]")
    console.print(f"  {ICONES['sucesso']} Sucesso: [green]{relatorio.enviados_sucesso}[/green]")
    console.print(f"  {ICONES['erro']} Erro: [red]{relatorio.enviados_erro}[/red]")
    console.print(f"  {ICONES['aviso']} Parcial: [yellow]{relatorio.enviados_parcial}[/yellow]")

    # Resultado por Tipo
    console.print("\n[bold cyan]Resultado por Tipo[/bold cyan]")
    for tipo, stats in relatorio.por_tipo.items():
        console.print(f"  [bold]{tipo}:[/bold]")
        console.print(f"    Sucesso: [green]{stats.get('sucesso', 0)}[/green]")
        console.print(f"    Erro: [red]{stats.get('erro', 0)}[/red]")

    # Erros
    if relatorio.erros:
        console.print(f"\n[bold red]{ICONES['erro']} Erros[/bold red]")
        for erro in relatorio.erros[:10]:
            contato = erro.get('contato', 'N/A')
            tipo = erro.get('tipo', 'N/A')
            msg_erro = erro.get('erro', 'N/A')
            console.print(f"  {ICONES['ponto']} {contato} ({tipo}): {msg_erro}")

        if len(relatorio.erros) > 10:
            console.print(f"  [dim]... e mais {len(relatorio.erros) - 10} erros[/dim]")


def menu_verificar_servicos():
    """Menu para verificar status dos servicos"""
    exibir_cabecalho("VERIFICACAO DE SERVICOS", ICONES["config"])

    exibir_info("Verificando conexoes...")
    status = envio_folha_ponto_orquestrador.verificar_servicos()

    # Montar conteudo do painel
    linhas = []
    for servico, disponivel in status.items():
        icone = ICONES["sucesso"] if disponivel else ICONES["erro"]
        status_texto = "[green]OK[/green]" if disponivel else "[red]Indisponivel[/red]"
        linhas.append(f"{icone} {servico}: {status_texto}")

    exibir_painel("\n".join(linhas), titulo="Status dos Servicos", estilo_borda="cyan")
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
            console.print("    Configure o whatsapp_device_id nas empresas primeiro.")
            return None, None

        # Montar opcoes para selecao
        opcoes = []
        for empresa in empresas_com_device:
            nome = empresa.get('nome', 'N/A')
            nome_simples = empresa.get('nome_simplificado', '')
            device_id = empresa.get('whatsapp_device_id', 'N/A')
            display_nome = f"{nome} ({nome_simples})" if nome_simples else nome
            opcoes.append(f"{display_nome} - Device: {device_id}")

        selecao = pedir_selecao(
            f"Selecione a empresa ({len(empresas_com_device)} disponiveis)",
            opcoes
        )

        if not selecao:
            exibir_info("Operacao cancelada.")
            return None, None

        # Extrair indice da selecao
        indice = opcoes.index(selecao)
        empresa_selecionada = empresas_com_device[indice]
        device_id = empresa_selecionada.get('whatsapp_device_id')
        nome_empresa = empresa_selecionada.get('nome')

        if not device_id:
            exibir_erro(f"Empresa '{nome_empresa}' nao tem dispositivo WhatsApp configurado!")
            return None, None

        exibir_sucesso(f"Empresa selecionada: {nome_empresa}")
        console.print(f"     Device ID: [cyan]{device_id}[/cyan]")
        return device_id, nome_empresa

    except Exception as e:
        logger.error(f"Erro ao selecionar empresa: {e}")
        exibir_erro(f"Erro: {e}")
        return None, None


def menu_sincronizar_grupos():
    """Menu para sincronizar grupos do WhatsApp"""
    exibir_cabecalho("SINCRONIZAR GRUPOS WHATSAPP", ICONES["whatsapp"])

    exibir_info("Sincronizando grupos com a API do WhatsApp...")
    resultado = envio_folha_ponto_orquestrador.sincronizar_grupos_whatsapp()

    # Montar resultado
    resultado_texto = f"""[bold]Grupos criados:[/bold] [green]{resultado.get('criados', 0)}[/green]
[bold]Grupos atualizados:[/bold] [cyan]{resultado.get('atualizados', 0)}[/cyan]
[bold]Grupos inativos:[/bold] [yellow]{resultado.get('inativos', 0)}[/yellow]"""

    exibir_painel(resultado_texto, titulo="Resultado da Sincronizacao", estilo_borda="green")

    # Perguntar se deseja listar grupos
    if not pedir_confirmacao("Deseja ver os grupos sincronizados?", padrao=False):
        return

    # Selecionar empresa para listar grupos
    console.print("\nPara listar grupos, selecione a empresa/dispositivo:")
    device_id, nome_empresa = _selecionar_empresa_para_grupos()

    if not device_id:
        return

    # Listar grupos da empresa selecionada
    try:
        grupos = grupo_whatsapp_service.listar_para_exibicao(device_id)
        if grupos:
            console.print(f"\n[bold cyan]Grupos de '{nome_empresa}' ({len(grupos)})[/bold cyan]")
            for g in grupos[:20]:
                console.print(f"  {ICONES['ponto']} {g['nome']} ({g['participantes']} participantes)")

            if len(grupos) > 20:
                console.print(f"  [dim]... e mais {len(grupos) - 20} grupos[/dim]")
        else:
            exibir_aviso(f"Nenhum grupo encontrado para '{nome_empresa}'")
    except ValueError as e:
        exibir_erro(f"Erro: {e}")

    pausar()


def menu_validar_planilha():
    """Menu para validar planilha de contatos"""
    exibir_cabecalho("VALIDAR PLANILHA DE CONTATOS", ICONES["excel"])

    console.print(f"\nCarregando planilha: [cyan]{planilha_contatos_service.planilha_path}[/cyan]")

    if not planilha_contatos_service.carregar():
        exibir_erro("Erro ao carregar planilha!")
        pausar()
        return

    resultado = planilha_contatos_service.validar_planilha()

    # Resultado da validacao
    valida = resultado.get('valida')
    icone_valida = ICONES["sucesso"] if valida else ICONES["erro"]
    status_valida = "[green]Sim[/green]" if valida else "[red]Nao[/red]"

    resultado_texto = f"""[bold]Total de linhas:[/bold] {resultado.get('total_linhas', 0)}
[bold]Valida:[/bold] {icone_valida} {status_valida}"""

    exibir_painel(resultado_texto, titulo="Resultado da Validacao", estilo_borda="cyan")

    # Problemas
    if resultado.get("problemas"):
        console.print(f"\n[bold red]{ICONES['aviso']} Problemas encontrados ({len(resultado['problemas'])}):[/bold red]")
        for problema in resultado["problemas"][:10]:
            console.print(f"  {ICONES['ponto']} {problema}")
        if len(resultado["problemas"]) > 10:
            console.print(f"  [dim]... e mais {len(resultado['problemas']) - 10}[/dim]")

    # Avisos
    if resultado.get("avisos"):
        console.print(f"\n[bold yellow]{ICONES['aviso']} Avisos ({len(resultado['avisos'])}):[/bold yellow]")
        for aviso in resultado["avisos"][:5]:
            console.print(f"  {ICONES['ponto']} {aviso}")
        if len(resultado["avisos"]) > 5:
            console.print(f"  [dim]... e mais {len(resultado['avisos']) - 5}[/dim]")

    # Resumo de envios
    contagem = planilha_contatos_service.contar_envios_pendentes()
    envios_texto = f"""[bold]E-mail:[/bold] {contagem.get('email', 0)} contatos
[bold]WhatsApp Individual:[/bold] {contagem.get('whatsapp', 0)} contatos
[bold]WhatsApp Grupo:[/bold] {contagem.get('grupo_whatsapp', 0)} contatos"""

    exibir_painel(envios_texto, titulo="Envios Configurados", estilo_borda="blue")
    pausar()


def menu_enviar_dry_run():
    """Menu para executar envio em modo simulacao"""
    exibir_cabecalho("ENVIO DE FOLHAS DE PONTO (SIMULACAO)", ICONES["processar"])

    mes, ano = solicitar_mes_ano()

    exibir_aviso("MODO SIMULACAO - Nenhum envio sera realizado")
    console.print(f"Periodo: [cyan]{MESES_EXTENSO.get(mes, mes)} de {ano}[/cyan]")

    if not pedir_confirmacao("Confirma execucao da simulacao?", padrao=False):
        exibir_info("Operacao cancelada.")
        return

    exibir_info("Executando simulacao...")
    relatorio = envio_folha_ponto_orquestrador.executar(
        mes=mes,
        ano=ano,
        dry_run=True
    )

    exibir_relatorio(relatorio)
    pausar()


def menu_enviar_real():
    """Menu para executar envio real"""
    exibir_cabecalho("ENVIO DE FOLHAS DE PONTO", ICONES["enviar"])

    mes, ano = solicitar_mes_ano()

    # Selecionar tipos de envio
    opcoes_tipo = [
        "Todos (E-mail + WhatsApp Individual + WhatsApp Grupo)",
        "Apenas E-mail",
        "Apenas WhatsApp Individual",
        "Apenas WhatsApp Grupo",
        "E-mail + WhatsApp Individual",
        "Apenas WhatsApp (Individual + Grupo)"
    ]

    selecao_tipo = pedir_selecao(
        "Selecionar Tipos de Envio",
        opcoes_tipo
    )

    if not selecao_tipo:
        exibir_info("Operacao cancelada.")
        return

    # Mapear selecao para tipos
    tipos_map = {
        0: [TipoEnvioEnum.EMAIL, TipoEnvioEnum.WHATSAPP_INDIVIDUAL, TipoEnvioEnum.WHATSAPP_GRUPO],
        1: [TipoEnvioEnum.EMAIL],
        2: [TipoEnvioEnum.WHATSAPP_INDIVIDUAL],
        3: [TipoEnvioEnum.WHATSAPP_GRUPO],
        4: [TipoEnvioEnum.EMAIL, TipoEnvioEnum.WHATSAPP_INDIVIDUAL],
        5: [TipoEnvioEnum.WHATSAPP_INDIVIDUAL, TipoEnvioEnum.WHATSAPP_GRUPO]
    }

    indice_tipo = opcoes_tipo.index(selecao_tipo)
    tipos_selecionados = tipos_map.get(indice_tipo, tipos_map[0])

    # Confirmacao final
    exibir_aviso("ATENCAO: Esta operacao ira enviar arquivos para os destinatarios!")
    console.print(f"Periodo: [cyan]{MESES_EXTENSO.get(mes, mes)} de {ano}[/cyan]")
    console.print(f"Tipos: [cyan]{', '.join([t.value for t in tipos_selecionados])}[/cyan]")

    confirmacao = pedir_texto(
        "Digite 'CONFIRMAR' para prosseguir",
        obrigatorio=True
    )

    if not confirmacao or confirmacao.upper() != "CONFIRMAR":
        exibir_info("Operacao cancelada.")
        return

    exibir_info("Executando envio...")
    relatorio = envio_folha_ponto_orquestrador.executar(
        mes=mes,
        ano=ano,
        tipos_envio=tipos_selecionados,
        dry_run=False
    )

    exibir_relatorio(relatorio)
    pausar()


def menu_historico():
    """Menu para visualizar historico de envios"""
    exibir_cabecalho("HISTORICO DE ENVIOS", ICONES["relatorio"])

    mes, ano = solicitar_mes_ano()

    resumo = envio_folha_ponto_service.obter_resumo_periodo(mes, ano)

    if not resumo:
        exibir_aviso("Nenhum envio encontrado para este periodo.")
        pausar()
        return

    # Resumo principal
    resumo_texto = f"""[bold]Periodo:[/bold] {resumo.get('periodo', '')}
[bold]Total de envios:[/bold] {resumo.get('total_envios', 0)}
[bold]Arquivos enviados:[/bold] {resumo.get('total_arquivos_enviados', 0)}"""

    exibir_painel(resumo_texto, titulo="Resumo do Periodo", estilo_borda="cyan")

    # Por Status
    console.print("\n[bold cyan]Por Status[/bold cyan]")
    for status, count in resumo.get("por_status", {}).items():
        console.print(f"  {ICONES['ponto']} {status}: {count}")

    # Por Tipo
    console.print("\n[bold cyan]Por Tipo[/bold cyan]")
    for tipo, count in resumo.get("por_tipo", {}).items():
        console.print(f"  {ICONES['ponto']} {tipo}: {count}")

    pausar()


def menu_templates():
    """Menu para gerenciar templates"""
    exibir_cabecalho("GERENCIAR TEMPLATES", ICONES["editar"])

    templates = template_mensagem_service.listar_todos()

    if not templates:
        exibir_aviso("Nenhum template encontrado.")
        console.print("Os templates padrao serao criados automaticamente.")
        pausar()
        return

    # Montar dados para tabela
    colunas = ["Padrao", "Tipo", "Nome"]
    dados = []

    for t in templates:
        padrao = ICONES["check"] if t.get("is_padrao") else ICONES["uncheck"]
        tipo = t.get('tipo', 'N/A')
        nome = t.get('nome', 'N/A')
        dados.append([padrao, tipo, nome])

    exibir_tabela(
        titulo=f"Templates Disponiveis ({len(templates)})",
        colunas=colunas,
        dados=dados,
        mostrar_indice=False
    )

    console.print(f"\n{ICONES['info']} {ICONES['check']} = Template padrao para o tipo")
    pausar()


def menu_listar_dispositivos():
    """Lista dispositivos WhatsApp conectados"""
    from src.services.whatsapp_service import whatsapp_service

    exibir_info("Listando dispositivos WhatsApp conectados...")
    dispositivos = whatsapp_service.listar_dispositivos()

    if not dispositivos:
        exibir_aviso("Nenhum dispositivo conectado encontrado")
        return

    # Montar dados para tabela
    colunas = ["Status", "Numero", "Nome", "JID"]
    dados = []

    for d in dispositivos:
        jid = d.get('jid', 'N/A')
        display_name = d.get('display_name', 'Desconhecido')
        state = d.get('state', 'unknown')
        status_emoji = ICONES["sucesso"] if state == "logged_in" else ICONES["erro"]

        # Extrair numero do JID
        numero = jid.split('@')[0] if '@' in jid else jid

        dados.append([status_emoji, numero, display_name, jid])

    exibir_tabela(
        titulo=f"Dispositivos Conectados ({len(dispositivos)})",
        colunas=colunas,
        dados=dados,
        mostrar_indice=False
    )


def menu_verificar_status_dispositivos():
    """Verifica status dos dispositivos configurados"""
    from src.services.whatsapp_service import whatsapp_service
    from src.services.empresa_service import empresa_service

    exibir_info("Verificando status dos dispositivos...")

    # Obter dispositivos unicos das empresas configuradas
    empresas = empresa_service.listar_todos(limit=1000)['dados']
    dispositivos_unicos = set()

    for empresa in empresas:
        device_id = empresa.get('whatsapp_device_id')
        if device_id:
            dispositivos_unicos.add(device_id)

    if not dispositivos_unicos:
        exibir_aviso("Nenhuma empresa tem dispositivo configurado")
        return

    # Montar dados para tabela
    colunas = ["Status", "Numero", "Device ID", "Mensagem"]
    dados = []

    for device_id in sorted(dispositivos_unicos):
        status = whatsapp_service.verificar_status_dispositivo(device_id)

        if status.get('sucesso'):
            is_logged = ICONES["sucesso"] if status.get('is_logged_in') else ICONES["erro"]
            numero = status.get('numero', 'Desconhecido')
            mensagem = status.get('mensagem', 'N/A')
            dados.append([is_logged, numero, device_id, mensagem])
        else:
            dados.append([ICONES["erro"], "Erro", device_id, status.get('mensagem', 'Erro desconhecido')])

    exibir_tabela(
        titulo=f"Status de {len(dispositivos_unicos)} Dispositivo(s)",
        colunas=colunas,
        dados=dados,
        mostrar_indice=False
    )


def menu_mostrar_dispositivo_empresa():
    """Mostra dispositivo de uma empresa especifica"""
    from src.services.whatsapp_service import whatsapp_service
    from src.services.empresa_service import empresa_service

    nome_empresa = pedir_texto("Nome da empresa", obrigatorio=True)

    if not nome_empresa:
        exibir_erro("Nome vazio!")
        return

    console.print(f"\n{ICONES['buscar']} Procurando empresa: [cyan]{nome_empresa}[/cyan]\n")

    empresa = empresa_service.buscar_por_nome_ou_simplificado(nome_empresa)

    if not empresa:
        exibir_erro(f"Empresa '{nome_empresa}' nao encontrada")
        return

    device_id = empresa.get('whatsapp_device_id')
    nome = empresa.get('nome')
    nome_simples = empresa.get('nome_simplificado', 'N/A')

    info_texto = f"""[bold]Empresa:[/bold] {nome}
[bold]Nome Simplificado:[/bold] {nome_simples}"""

    if device_id:
        # Verificar status do device
        status = whatsapp_service.verificar_status_dispositivo(device_id)

        if status.get('sucesso'):
            is_logged = status.get('is_logged_in')
            status_icone = ICONES["sucesso"] if is_logged else ICONES["erro"]
            status_texto = "Conectado" if is_logged else "Desconectado"
            info_texto += f"\n[bold]Device ID:[/bold] {device_id}\n[bold]Status:[/bold] {status_icone} {status_texto}"
        else:
            info_texto += f"\n[bold]Device ID:[/bold] {device_id}\n[bold]Status:[/bold] {ICONES['aviso']} Nao foi possivel verificar"
    else:
        info_texto += f"\n{ICONES['aviso']} Nenhum dispositivo configurado para esta empresa"

    exibir_painel(info_texto, titulo="Informacoes da Empresa", estilo_borda="cyan")


def menu_dispositivos():
    """Menu para gerenciar dispositivos WhatsApp"""
    try:
        from src.services.whatsapp_service import whatsapp_service

        if not whatsapp_service.disponivel:
            exibir_erro("WhatsApp Service nao disponivel!")
            pausar()
            return

        menu = (
            MenuBuilder("GERENCIAR DISPOSITIVOS WHATSAPP", ICONES["whatsapp"])
            .adicionar("Listar dispositivos conectados", menu_listar_dispositivos)
            .adicionar("Verificar status dos dispositivos", menu_verificar_status_dispositivos)
            .adicionar("Mostrar dispositivo de uma empresa", menu_mostrar_dispositivo_empresa)
        )

        menu.executar()

    except Exception as e:
        logger.error(f"Erro ao gerenciar dispositivos: {e}")
        exibir_erro(f"Erro: {e}")
        pausar()


def _abrir_contatos_envio() -> None:
    """Abre o menu de Contatos de Envio de Folha de Ponto."""
    from src.interface.interface_contatos_folha_ponto import InterfaceContatosFolhaPonto
    InterfaceContatosFolhaPonto().executar()


def menu_principal():
    """Menu principal do sistema de envio"""
    menu = (
        MenuBuilder("SISTEMA DE ENVIO DE FOLHAS DE PONTO", ICONES["folha_ponto"])
        .adicionar("Verificar Servicos", menu_verificar_servicos)
        .adicionar("Validar Planilha de Contatos", menu_validar_planilha)
        .adicionar("Sincronizar Grupos WhatsApp", menu_sincronizar_grupos)
        .adicionar("Gerenciar Dispositivos WhatsApp", menu_dispositivos)
        .adicionar("Gerenciar Templates", menu_templates)
        .separador()
        .adicionar("Simulacao de Envio (Dry Run)", menu_enviar_dry_run)
        .adicionar("Executar Envio", menu_enviar_real)
        .separador()
        .adicionar("Historico de Envios", menu_historico)
        .separador()
        .adicionar("Gerenciar Contatos de Envio", _abrir_contatos_envio)
    )

    menu.executar()


def iniciar_menu_envio():
    """Funcao de entrada para o menu de envio"""
    try:
        menu_principal()
    except KeyboardInterrupt:
        exibir_info("\nEncerrando...")
