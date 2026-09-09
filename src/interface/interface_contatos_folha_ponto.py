"""
Interface para gerenciamento de Contatos de Envio de Folha de Ponto
Permite criar, listar, buscar, editar e excluir contatos
Seguindo o padrão do projeto (MenuBuilder + functions + core/components)
"""

from typing import Optional, List, Dict, Any
from src.utils.logger_config_v2 import get_logger

# Logger do módulo
logger = get_logger("interface")

from src.interface.core.components import (
    MenuBuilder,
    exibir_cabecalho,
    exibir_sucesso,
    exibir_erro,
    exibir_aviso,
    exibir_info,
    exibir_tabela,
    exibir_painel,
    pausar,
    pedir_confirmacao,
    pedir_texto,
    pedir_selecao,
    pedir_selecao_multipla,
    pedir_inteiro,
)
from src.interface.core.theme import console, ICONES

# Importar serviço de contatos
try:
    from src.services.contatos_folha_ponto_service import contatos_folha_ponto_service
    CONTATO_SERVICE_DISPONIVEL = True
except ImportError as e:
    logger.warning(f"Servico de contatos nao disponivel: {e}")
    CONTATO_SERVICE_DISPONIVEL = False


# ═══════════════════════════════════════════════════════════════
# ESTADO GLOBAL DE PAGINAÇÃO
# ═══════════════════════════════════════════════════════════════

_estado_paginacao = {
    "pagina_atual": 1,
    "itens_por_pagina": 20,
    "contatos": [],
    "total": 0,
    "filtro_atual": None,
}


# ═══════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ═══════════════════════════════════════════════════════════════


def _criar_servico():
    """Cria instância do serviço de contatos"""
    if not CONTATO_SERVICE_DISPONIVEL:
        exibir_erro("Servico de contatos nao disponivel")
        return None

    if not contatos_folha_ponto_service.disponivel:
        exibir_erro("MongoDB nao esta conectado")
        return None

    return contatos_folha_ponto_service


def _obter_icone_envio(contato: Dict[str, Any]) -> str:
    """Retorna ícones de envio formatados para um contato"""
    envios = []
    if contato.get("enviar_email"):
        envios.append(f"{ICONES['email']}")
    if contato.get("enviar_whatsapp"):
        envios.append(f"{ICONES['whatsapp']}")
    if contato.get("enviar_grupo_whatsapp"):
        envios.append("👥")
    if contato.get("enviar_impresso"):
        envios.append("📄")
    return " ".join(envios) if envios else "-"


def _formatar_contato_linha(contato: Dict[str, Any]) -> List[str]:
    """Formata um contato como linha de tabela"""
    nome = (contato.get("nome", "N/A")[:28] + "..") if len(contato.get("nome", "")) > 30 else contato.get("nome", "N/A")
    empresa = (contato.get("empresa", "")[:20] + "..") if len(contato.get("empresa", "")) > 22 else contato.get("empresa", "-")
    email = (contato.get("email", "")[:25] + "..") if len(contato.get("email", "")) > 27 else contato.get("email", "-")
    telefone = contato.get("telefone", "-") or "-"
    envios = _obter_icone_envio(contato)
    return [str(contato.get("_id", ""))[:8], nome, empresa, email, telefone, envios]


def _mostrar_estatisticas_rapidas():
    """Mostra estatísticas rápidas no cabeçalho"""
    servico = _criar_servico()
    if servico:
        total = servico.contar()
        if total is not None and total > 0:
            exibir_info(f"Total de contatos: {total}")


def _visualizar_documentos_contato():
    """Visualiza quais documentos (PDFs) serao enviados para um contato"""
    servico = _criar_servico()
    if servico is None:
        return

    exibir_cabecalho("Visualizar Documentos por Contato")

    # Pedir mes/ano de referencia
    mes = pedir_inteiro("Mes de referencia (1-12)", minimo=1, maximo=12)
    if mes is None:
        return

    ano = pedir_inteiro("Ano de referencia", minimo=2020, maximo=2030)
    if ano is None:
        return

    exibir_info(f"Periodo: {mes:02d}/{ano}")

    # Listar contatos com envio ativo
    contatos = servico.listar_todos()
    contatos_com_envio = [c for c in contatos if any([
        c.get("enviar_email"),
        c.get("enviar_whatsapp"),
        c.get("enviar_grupo_whatsapp")
    ])]

    if not contatos_com_envio:
        exibir_aviso("Nenhum contato com envio ativo encontrado")
        pausar()
        return

    # Mostrar lista resumida
    colunas = ["#", "Nome", "Local", "Empresa", "Envios"]
    dados = []
    for i, c in enumerate(contatos_com_envio, 1):
        nome = c.get("nome", "(sem nome)") or "(sem nome)"
        local = c.get("local_contrato_polo", "-")[:30]
        empresa = c.get("empresa", "-")[:15]
        envios = []
        if c.get("enviar_email"): envios.append("email")
        if c.get("enviar_whatsapp"): envios.append("whatsapp")
        if c.get("enviar_grupo_whatsapp"): envios.append("grupo")
        dados.append([str(i), nome, local, empresa, ", ".join(envios)])

    exibir_tabela("Contatos com Envio Ativo", colunas, dados)

    # Pedir selecao
    opcao = pedir_inteiro("Selecione o numero do contato (0 para voltar)", minimo=0, maximo=len(contatos_com_envio))
    if opcao is None or opcao == 0:
        return

    contato = contatos_com_envio[opcao - 1]

    # Montar diretorio e listar PDFs
    try:
        from src.services.mongodb_contatos_service import MongoDBContatosService
        s = MongoDBContatosService()

        diretorio_geral = contato.get("diretorio_geral", "")
        diretorio_especifico = contato.get("diretorio_especifico", "")

        if diretorio_geral and diretorio_especifico:
            diretorio_completo = s.montar_diretorio_completo(diretorio_geral, diretorio_especifico, mes, ano)
            pdfs = s.listar_arquivos_pdf(diretorio_completo)
        else:
            diretorio_completo = "(diretorio nao configurado)"
            pdfs = []
    except Exception as e:
        diretorio_completo = f"(erro: {e})"
        pdfs = []

    # Exibir detalhes
    nome = contato.get("nome", "(sem nome)") or "(sem nome)"
    empresa = contato.get("empresa", "-")
    local = contato.get("local_contrato_polo", "-")

    envios = []
    if contato.get("enviar_email"): envios.append(f"📧 Email: {contato.get('email', '-')}")
    if contato.get("enviar_whatsapp"): envios.append(f"💬 WhatsApp: {contato.get('telefone', '-')}")
    if contato.get("enviar_grupo_whatsapp"): envios.append(f"👥 Grupo: {contato.get('grupo_whatsapp', '-')}")

    envios_str = "\n".join(envios) if envios else "Nenhum"

    conteudo = f"""[bold]{nome}[/bold]
Empresa: {empresa}
Local: {local}
Periodo: {mes:02d}/{ano}

[bold]Canais de envio:[/bold]
{envios_str}

[bold]Diretorio:[/bold]
{diretorio_completo}

[bold]Documentos encontrados:[/bold] ({len(pdfs)} PDFs)"""

    if pdfs:
        for pdf in pdfs:
            conteudo += f"\n  📄 {pdf}"
    else:
        conteudo += "\n  ⚠️ Nenhum PDF encontrado no diretorio"

    exibir_painel(conteudo, titulo="Detalhes do Contato", estilo_borda="blue")
    pausar()


# ═══════════════════════════════════════════════════════════════
# INTERFACE PRINCIPAL
# ═══════════════════════════════════════════════════════════════


def Interface_Contatos_Folha_Ponto():
    """Interface principal para gerenciamento de contatos de envio de folha de ponto"""
    logger.debug("Iniciando interface de contatos de envio de folha de ponto")

    if not CONTATO_SERVICE_DISPONIVEL:
        exibir_erro("Servico de contatos nao disponivel!")
        return

    (
        MenuBuilder("GERENCIAR CONTATOS DE ENVIO DE FOLHA DE PONTO", ICONES["funcionarios"])
        .adicionar("Listar contatos", _listar_contatos, ICONES["listar"])
        .adicionar("Visualizar documentos por contato", _visualizar_documentos_contato, ICONES["buscar"])
        .adicionar("Buscar contato", _buscar_contato, ICONES["buscar"])
        .adicionar("Adicionar novo contato", _adicionar_contato, ICONES["criar"])
        .adicionar("Editar contato existente", _editar_contato, ICONES["editar"])
        .adicionar("Excluir contato", _excluir_contato, ICONES["excluir"])
        .separador()
        .adicionar("Estatisticas", _exibir_estatisticas, ICONES["estatistica"])
        .com_voltar("Voltar ao Menu Principal")
        .executar()
    )


# ═══════════════════════════════════════════════════════════════
# FUNÇÕES DE LISTAGEM
# ═══════════════════════════════════════════════════════════════


def _listar_contatos():
    """Lista contatos com filtros e paginação"""
    servico = _criar_servico()
    if not servico:
        return

    exibir_cabecalho("LISTAR CONTATOS", ICONES["listar"])
    _mostrar_estatisticas_rapidas()

    # Opções de filtro
    filtro_opcoes = [
        "Todos",
        "Filtrar por empresa",
        "Filtrar por local",
        "Filtrar por tipo de envio",
    ]

    filtro = pedir_selecao("Tipo de filtro:", filtro_opcoes)

    if filtro is None:
        return

    # Resetar paginação apenas ao trocar de filtro
    _estado_paginacao["pagina_atual"] = 1
    _estado_paginacao["filtro_atual"] = filtro

    # Parâmetros de paginação
    itens_por_pagina = _estado_paginacao["itens_por_pagina"]

    # Aplicar filtro
    contatos = []

    if filtro == "Todos":
        contatos = servico.listar_todos(skip=0, limit=itens_por_pagina)
        _estado_paginacao["total"] = servico.contar()
    elif filtro == "Filtrar por empresa":
        empresa = pedir_texto("Nome da empresa:")
        if not empresa:
            exibir_aviso("Operacao cancelada.")
            return
        contatos = servico.listar_por_empresa(empresa, skip=0, limit=itens_por_pagina)
        _estado_paginacao["total"] = servico.contar_por_empresa(empresa)
    elif filtro == "Filtrar por local":
        local = pedir_texto("Local/contrato/polo:")
        if not local:
            exibir_aviso("Operacao cancelada.")
            return
        contatos = servico.listar_por_local(local, skip=0, limit=itens_por_pagina)
        _estado_paginacao["total"] = servico.contar_por_local(local)
    elif filtro == "Filtrar por tipo de envio":
        tipo_envio = pedir_selecao(
            "Tipo de envio:",
            ["email", "whatsapp", "grupo_whatsapp", "impresso"],
        )
        if not tipo_envio:
            exibir_aviso("Operacao cancelada.")
            return
        contatos = servico.listar_por_envio(tipo_envio, skip=0, limit=itens_por_pagina)
        _estado_paginacao["total"] = servico.contar()

    _estado_paginacao["contatos"] = contatos

    # Exibir e navegar
    _exibir_pagina_contatos()


def _exibir_pagina_contatos():
    """Exibe a página atual de contatos com navegação"""
    contatos = _estado_paginacao["contatos"]
    total = _estado_paginacao["total"]
    pagina = _estado_paginacao["pagina_atual"]
    itens_por_pagina = _estado_paginacao["itens_por_pagina"]

    if not contatos:
        exibir_info("Nenhum contato encontrado.")
        pausar()
        return

    # Calcular páginas totais
    paginas = max(1, (total + itens_por_pagina - 1) // itens_por_pagina)

    # Montar tabela
    dados = [_formatar_contato_linha(c) for c in contatos]

    exibir_tabela(
        f"Contatos (Pagina {pagina}/{paginas} - Total: {total})",
        ["ID", "Nome", "Empresa", "Email", "Telefone", "Envios"],
        dados,
    )

    # Navegação (se houver mais de uma página)
    if paginas > 1:
        opcoes_navegacao = []
        if pagina > 1:
            opcoes_navegacao.append("Pagina anterior")
        if pagina < paginas:
            opcoes_navegacao.append("Proxima pagina")
        opcoes_navegacao.append("Voltar")

        opcao = pedir_selecao("Navegacao:", opcoes_navegacao)

        if opcao and "Proxima" in opcao and pagina < paginas:
            _estado_paginacao["pagina_atual"] = pagina + 1
            _carregar_pagina_atual()
            _exibir_pagina_contatos()
        elif opcao and "anterior" in opcao and pagina > 1:
            _estado_paginacao["pagina_atual"] = pagina - 1
            _carregar_pagina_atual()
            _exibir_pagina_contatos()
    else:
        pausar()


def _carregar_pagina_atual():
    """Recarrega a página atual usando o filtro armazenado"""
    servico = _criar_servico()
    if not servico:
        return

    pagina = _estado_paginacao["pagina_atual"]
    itens_por_pagina = _estado_paginacao["itens_por_pagina"]
    skip = (pagina - 1) * itens_por_pagina
    filtro = _estado_paginacao["filtro_atual"]

    contatos = []

    if filtro == "Todos":
        contatos = servico.listar_todos(skip=skip, limit=itens_por_pagina)
    elif filtro == "Filtrar por empresa":
        # Reutilizar termo do filtro (simplificado)
        contatos = servico.listar_todos(skip=skip, limit=itens_por_pagina)
    elif filtro == "Filtrar por local":
        contatos = servico.listar_todos(skip=skip, limit=itens_por_pagina)
    elif filtro == "Filtrar por tipo de envio":
        contatos = servico.listar_todos(skip=skip, limit=itens_por_pagina)

    _estado_paginacao["contatos"] = contatos


# ═══════════════════════════════════════════════════════════════
# FUNÇÕES DE BUSCA
# ═══════════════════════════════════════════════════════════════


def _buscar_contato():
    """Busca contato por nome, email ou telefone"""
    servico = _criar_servico()
    if not servico:
        return

    exibir_cabecalho("BUSCAR CONTATO", ICONES["buscar"])

    # Mostrar total antes de buscar (fix #12)
    total = servico.contar()
    exibir_info(f"Total de contatos cadastrados: {total}")

    tipo_busca = pedir_selecao(
        "Buscar por:",
        ["Nome", "Email", "Telefone"],
    )

    if tipo_busca is None:
        return

    termo = pedir_texto(f"Digite o {tipo_busca.lower()}:")
    if not termo:
        return

    contatos = []

    if tipo_busca == "Nome":
        contatos = servico.buscar_por_nome(termo)
    elif tipo_busca == "Email":
        contatos = servico.buscar_por_email(termo)
    elif tipo_busca == "Telefone":
        contatos = servico.buscar_por_telefone(termo)

    if not contatos:
        exibir_info("Nenhum contato encontrado.")
        pausar()
        return

    # Montar tabela
    dados = [_formatar_contato_linha(c) for c in contatos]

    exibir_tabela(
        f"Resultados da busca por {tipo_busca} ({len(contatos)} encontrado(s))",
        ["ID", "Nome", "Empresa", "Email", "Telefone", "Envios"],
        dados,
    )

    pausar()


# ═══════════════════════════════════════════════════════════════
# FUNÇÕES DE CRIAÇÃO
# ═══════════════════════════════════════════════════════════════


def _adicionar_contato():
    """Adiciona um novo contato"""
    servico = _criar_servico()
    if not servico:
        return

    exibir_cabecalho("ADICIONAR NOVO CONTATO", ICONES["criar"])
    exibir_info("Preencha os dados do contato (* = obrigatorio)")

    # Dados obrigatórios
    funcionario_id = pedir_texto("* ID do funcionario (da planilha):")
    if not funcionario_id:
        exibir_erro("ID do funcionario e obrigatorio!")
        pausar()
        return

    # Verificar duplicata (fix #11)
    existente = servico.buscar_por_funcionario_id(funcionario_id)
    if existente:
        exibir_aviso(f"Ja existe um contato com ID '{funcionario_id}': {existente.get('nome', 'N/A')}")
        pausar()
        return

    nome = pedir_texto("* Nome completo:")
    if not nome:
        exibir_erro("Nome e obrigatorio!")
        pausar()
        return

    # Dados opcionais
    email = pedir_texto("Email(s) separados por virgula (opcional):", obrigatorio=False) or ""
    telefone = pedir_texto("Telefone(s) separados por virgula (opcional):", obrigatorio=False) or ""
    grupo_whatsapp = pedir_texto("Grupo(s) WhatsApp separados por virgula (opcional):", obrigatorio=False) or ""

    empresa = pedir_texto("Nome da empresa (opcional):", obrigatorio=False) or ""
    local_contrato_polo = pedir_texto("Local/Contrato/Polo (opcional):", obrigatorio=False) or ""

    diretorio_geral = pedir_texto("Diretorio geral (opcional):", obrigatorio=False) or ""
    diretorio_especifico = pedir_texto("Diretorio especifico (opcional):", obrigatorio=False) or ""

    # Flags de envio
    console.print()
    console.print("[bold]Configurar canais de envio:[/bold]")
    enviar_email = pedir_confirmacao("Enviar por email?", padrao=False)
    enviar_whatsapp = pedir_confirmacao("Enviar por WhatsApp?", padrao=True)
    enviar_grupo_whatsapp = pedir_confirmacao("Enviar para grupo WhatsApp?", padrao=False)
    enviar_impresso = pedir_confirmacao("Enviar impresso?", padrao=False)

    # Resumo para confirmação
    resumo = (
        f"[bold]ID:[/bold] {funcionario_id}\n"
        f"[bold]Nome:[/bold] {nome}\n"
        f"[bold]Email:[/bold] {email or 'Nao informado'}\n"
        f"[bold]Telefone:[/bold] {telefone or 'Nao informado'}\n"
        f"[bold]Grupo WhatsApp:[/bold] {grupo_whatsapp or 'Nao informado'}\n"
        f"[bold]Empresa:[/bold] {empresa or 'Nao informada'}\n"
        f"[bold]Local:[/bold] {local_contrato_polo or 'Nao informado'}\n"
        f"[bold]Envio Email:[/bold] {'Sim' if enviar_email else 'Nao'}\n"
        f"[bold]Envio WhatsApp:[/bold] {'Sim' if enviar_whatsapp else 'Nao'}\n"
        f"[bold]Envio Grupo WhatsApp:[/bold] {'Sim' if enviar_grupo_whatsapp else 'Nao'}\n"
        f"[bold]Envio Impresso:[/bold] {'Sim' if enviar_impresso else 'Nao'}"
    )
    exibir_painel(resumo, titulo="RESUMO DO NOVO CONTATO", estilo_borda="yellow")

    if not pedir_confirmacao("Confirmar criacao?"):
        exibir_aviso("Operacao cancelada.")
        pausar()
        return

    # Criar contato
    dados = {
        "funcionario_id": funcionario_id,
        "nome": nome,
        "email": email,
        "telefone": telefone,
        "grupo_whatsapp": grupo_whatsapp,
        "empresa": empresa,
        "local_contrato_polo": local_contrato_polo,
        "diretorio_geral": diretorio_geral,
        "diretorio_especifico": diretorio_especifico,
        "enviar_email": enviar_email,
        "enviar_whatsapp": enviar_whatsapp,
        "enviar_grupo_whatsapp": enviar_grupo_whatsapp,
        "enviar_impresso": enviar_impresso,
    }

    resultado = servico.criar(dados)

    if resultado:
        exibir_sucesso("Contato criado com sucesso!")
        exibir_info(f"ID: {resultado}")
        logger.audit("CONTATO_CRIADO_INTERFACE", target=f"contato:{resultado}", changes={"nome": nome, "funcionario_id": funcionario_id})
    else:
        # Erro mais específico (fix #10)
        exibir_erro("Erro ao criar contato. Verifique se o ID do funcionario nao esta duplicado ou se os dados estao corretos.")

    pausar()


# ═══════════════════════════════════════════════════════════════
# FUNÇÕES DE EDIÇÃO
# ═══════════════════════════════════════════════════════════════


def _editar_contato():
    """Edita um contato existente - busca por nome antes de editar"""
    servico = _criar_servico()
    if not servico:
        return

    exibir_cabecalho("EDITAR CONTATO", ICONES["editar"])

    # Buscar por nome primeiro (fix #9 - sem exigir ObjectId)
    nome_busca = pedir_texto("Nome do contato para buscar:")
    if not nome_busca:
        return

    contatos_encontrados = servico.buscar_por_nome(nome_busca)

    if not contatos_encontrados:
        exibir_info("Nenhum contato encontrado com esse nome.")
        pausar()
        return

    # Se encontrou apenas um, selecionar automaticamente
    if len(contatos_encontrados) == 1:
        contato = contatos_encontrados[0]
        exibir_sucesso(f"Contato encontrado: {contato.get('nome')} ({contato.get('empresa', 'N/A')})")
    else:
        # Múltiplos - permitir escolher
        exibir_info(f"{len(contatos_encontrados)} contato(s) encontrado(s)")

        dados = [_formatar_contato_linha(c) for c in contatos_encontrados]
        exibir_tabela(
            "Contatos Encontrados",
            ["ID", "Nome", "Empresa", "Email", "Telefone", "Envios"],
            dados,
        )

        escolha = pedir_inteiro("Escolha o numero do contato (0 para cancelar):", minimo=0, maximo=len(contatos_encontrados))

        if escolha is None or escolha == 0:
            exibir_aviso("Operacao cancelada.")
            return

        contato = contatos_encontrados[escolha - 1]

    contato_id = str(contato.get("_id"))

    # Mostrar dados atuais
    console.print("\n[bold]Dados atuais:[/bold]")
    for key, value in contato.items():
        if key not in ["_id", "criado_em", "atualizado_em"]:
            console.print(f"  {key}: {value}")

    # Campos editáveis
    campos_editaveis = [
        "funcionario_id", "nome", "email", "telefone", "grupo_whatsapp",
        "empresa", "local_contrato_polo", "diretorio_geral", "diretorio_especifico",
        "enviar_email", "enviar_whatsapp", "enviar_grupo_whatsapp", "enviar_impresso",
    ]

    campos_para_editar = pedir_selecao_multipla(
        "Selecione os campos para editar:",
        campos_editaveis,
    )

    if not campos_para_editar:
        exibir_aviso("Nenhum campo selecionado.")
        pausar()
        return

    dados_atualizacao = {}

    for campo in campos_para_editar:
        valor_atual = contato.get(campo, "")

        if isinstance(valor_atual, bool):
            novo_valor = pedir_confirmacao(
                f"Valor atual de {campo}: {valor_atual}. Novo valor:",
                padrao=valor_atual,
            )
            dados_atualizacao[campo] = novo_valor
        else:
            novo_valor = pedir_texto(
                f"Valor atual de {campo}: {valor_atual}. Novo valor:",
                obrigatorio=False,
                padrao=str(valor_atual),
            )
            if novo_valor is not None:
                dados_atualizacao[campo] = novo_valor

    if not dados_atualizacao:
        exibir_aviso("Nenhum campo alterado.")
        pausar()
        return

    # Confirmar
    alteracoes_texto = []
    for campo, valor in dados_atualizacao.items():
        valor_anterior = contato.get(campo, "N/A")
        alteracoes_texto.append(f"[bold]{campo}:[/bold] {valor_anterior} -> {valor}")

    exibir_painel(
        "\n".join(alteracoes_texto),
        titulo="ALTERACOES A SEREM APLICADAS",
        estilo_borda="yellow",
    )

    if not pedir_confirmacao("Confirmar atualizacao?"):
        exibir_aviso("Operacao cancelada.")
        pausar()
        return

    sucesso = servico.atualizar(contato_id, dados_atualizacao)

    if sucesso:
        exibir_sucesso("Contato atualizado com sucesso!")
        logger.audit("CONTATO_ATUALIZADO_INTERFACE", target=f"contato:{contato_id}", changes=dados_atualizacao)
    else:
        exibir_erro("Erro ao atualizar contato.")

    pausar()


# ═══════════════════════════════════════════════════════════════
# FUNÇÕES DE EXCLUSÃO
# ═══════════════════════════════════════════════════════════════


def _excluir_contato():
    """Exclui um contato - busca por nome antes de excluir"""
    servico = _criar_servico()
    if not servico:
        return

    exibir_cabecalho("EXCLUIR CONTATO", ICONES["excluir"])

    # Buscar por nome primeiro (fix #9)
    nome_busca = pedir_texto("Nome do contato para buscar:")
    if not nome_busca:
        return

    contatos_encontrados = servico.buscar_por_nome(nome_busca)

    if not contatos_encontrados:
        exibir_info("Nenhum contato encontrado com esse nome.")
        pausar()
        return

    # Se encontrou apenas um
    if len(contatos_encontrados) == 1:
        contato = contatos_encontrados[0]
    else:
        # Múltiplos - permitir escolher
        exibir_info(f"{len(contatos_encontrados)} contato(s) encontrado(s)")

        dados = [_formatar_contato_linha(c) for c in contatos_encontrados]
        exibir_tabela(
            "Contatos Encontrados",
            ["ID", "Nome", "Empresa", "Email", "Telefone", "Envios"],
            dados,
        )

        escolha = pedir_inteiro("Escolha o numero do contato (0 para cancelar):", minimo=0, maximo=len(contatos_encontrados))

        if escolha is None or escolha == 0:
            exibir_aviso("Operacao cancelada.")
            return

        contato = contatos_encontrados[escolha - 1]

    contato_id = str(contato.get("_id"))

    # Mostrar dados do contato a ser excluído
    exibir_painel(
        f"[bold]Nome:[/bold] {contato.get('nome', 'N/A')}\n"
        f"[bold]Empresa:[/bold] {contato.get('empresa', 'N/A')}\n"
        f"[bold]Email:[/bold] {contato.get('email', 'N/A')}\n"
        f"[bold]Telefone:[/bold] {contato.get('telefone', 'N/A')}",
        titulo=f"{ICONES['aviso']} CONTATO A SER EXCLUIDO",
        estilo_borda="red",
    )

    if not pedir_confirmacao("Tem certeza que deseja excluir este contato?", padrao=False):
        exibir_aviso("Exclusao cancelada.")
        pausar()
        return

    sucesso = servico.excluir(contato_id)

    if sucesso:
        exibir_sucesso("Contato excluido com sucesso!")
        logger.audit("CONTATO_EXCLUIDO_INTERFACE", target=f"contato:{contato_id}", changes={"nome": contato.get("nome")})
    else:
        exibir_erro("Erro ao excluir contato.")

    pausar()


# ═══════════════════════════════════════════════════════════════
# FUNÇÕES DE ESTATÍSTICAS
# ═══════════════════════════════════════════════════════════════


def _exibir_estatisticas():
    """Exibe estatísticas dos contatos"""
    servico = _criar_servico()
    if not servico:
        return

    exibir_cabecalho("ESTATISTICAS DOS CONTATOS", ICONES["estatistica"])

    stats = servico.estatisticas()

    if not stats:
        exibir_info("Nao foi possivel carregar estatisticas.")
        pausar()
        return

    # Total geral
    console.print(f"\n[bold]{ICONES['estatistica']} Total de contatos:[/bold] {stats.get('total', 0)}")

    # Por empresa
    empresas = stats.get("por_empresa", [])
    if empresas:
        console.print("\n[bold]Por Empresa:[/bold]")
        dados_empresas = []
        for empresa in empresas[:10]:
            nome_emp = empresa.get("empresa", "N/A") or "N/A"
            dados_empresas.append([nome_emp, str(empresa.get("count", 0))])

        exibir_tabela(
            f"Top {min(len(empresas), 10)} Empresas",
            ["Empresa", "Quantidade"],
            dados_empresas,
            mostrar_indice=False,
        )

    # Por local
    locais = stats.get("por_local", [])
    if locais:
        console.print("\n[bold]Por Local:[/bold]")
        dados_locais = []
        for local in locais[:10]:
            nome_local = local.get("local", "N/A") or "N/A"
            dados_locais.append([nome_local, str(local.get("count", 0))])

        exibir_tabela(
            f"Top {min(len(locais), 10)} Locais",
            ["Local", "Quantidade"],
            dados_locais,
            mostrar_indice=False,
        )

    # Por tipo de envio
    envios = stats.get("por_envio", {})
    if envios:
        console.print("\n[bold]Por Tipo de Envio:[/bold]")
        dados_envios = [
            [f"{ICONES['email']} Email", str(envios.get("email", 0))],
            [f"{ICONES['whatsapp']} WhatsApp", str(envios.get("whatsapp", 0))],
            ["👥 Grupo WhatsApp", str(envios.get("grupo_whatsapp", 0))],
            ["📄 Impresso", str(envios.get("impresso", 0))],
        ]

        exibir_tabela(
            "Canais de Envio",
            ["Canal", "Quantidade"],
            dados_envios,
            mostrar_indice=False,
        )

    pausar()
