"""Interface para gerenciamento de Empresas
Permite criar, visualizar, atualizar e alterar status de empresas
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
    exibir_resultado,
    exibir_painel,
    pausar,
    pedir_confirmacao,
    pedir_texto,
    pedir_selecao,
    pedir_inteiro,
)
from src.interface.core.theme import console, ICONES

# Importar serviço de empresas
try:
    from src.services.empresa_service import EmpresaService
    from src.models.empresa_models import StatusEmpresa
    EMPRESA_SERVICE_DISPONIVEL = True
except ImportError as e:
    logger.warning(f"Servico de empresas nao disponivel: {e}")
    EMPRESA_SERVICE_DISPONIVEL = False


def _criar_servico_empresa() -> Optional[EmpresaService]:
    """Cria instância do serviço de empresas"""
    if not EMPRESA_SERVICE_DISPONIVEL:
        exibir_erro("Servico de empresas nao disponivel")
        return None

    servico = EmpresaService()
    if not servico.disponivel:
        exibir_erro("MongoDB nao esta conectado")
        return None

    return servico


# Mapeamento de StatusEmpresa para exibição (usando Enum)
STATUS_DISPLAY = {
    StatusEmpresa.ATIVA: f"{ICONES['sucesso']} Ativa",
    StatusEmpresa.INATIVA: f"{ICONES['erro']} Inativa",
    StatusEmpresa.SUSPENSA: f"{ICONES['aviso']} Suspensa",
    StatusEmpresa.EM_CONSTRUCAO: f"{ICONES['processando']} Em Construcao"
} if EMPRESA_SERVICE_DISPONIVEL else {}


def _formatar_status(status) -> str:
    """Formata status para exibição (aceita Enum ou string)"""
    # Se for string, converter para Enum
    if isinstance(status, str) and EMPRESA_SERVICE_DISPONIVEL:
        try:
            status = StatusEmpresa(status)
        except ValueError:
            return status

    return STATUS_DISPLAY.get(status, str(status))


def _formatar_data(data) -> str:
    """Formata data para exibição"""
    if not data:
        return "N/A"
    if hasattr(data, 'strftime'):
        return data.strftime("%d/%m/%Y %H:%M")
    return str(data)[:19]


def _exibir_empresa_detalhada(empresa: Dict[str, Any]) -> None:
    """Exibe detalhes completos de uma empresa"""
    exibir_cabecalho("DETALHES DA EMPRESA", ICONES["empresa"])

    # Painel de Identificação
    identificacao = (
        f"[bold]ID:[/bold] {empresa.get('_id', 'N/A')}\n"
        f"[bold]Nome:[/bold] {empresa.get('nome', 'N/A')}\n"
        f"[bold]CNPJ:[/bold] {empresa.get('cnpj', 'Nao informado')}\n"
        f"[bold]Status:[/bold] {_formatar_status(empresa.get('status', 'N/A'))}\n"
        f"[bold]Incompleta:[/bold] {'Sim' if empresa.get('incompleto') else 'Nao'}"
    )
    exibir_painel(identificacao, titulo=f"{ICONES['info']} IDENTIFICACAO", estilo_borda="blue")

    # Painel de Informações
    informacoes = (
        f"[bold]Atividade:[/bold] {empresa.get('atividade') or 'Nao informada'}\n"
        f"[bold]Endereco:[/bold] {empresa.get('endereco') or 'Nao informado'}\n"
        f"[bold]Telefone:[/bold] {empresa.get('telefone') or 'Nao informado'}\n"
        f"[bold]Email:[/bold] {empresa.get('email') or 'Nao informado'}\n"
        f"[bold]Responsavel:[/bold] {empresa.get('responsavel') or 'Nao informado'}"
    )
    exibir_painel(informacoes, titulo=f"{ICONES['config']} INFORMACOES", estilo_borda="green")

    # Painel de Metadados
    metadados = (
        f"[bold]Criado em:[/bold] {_formatar_data(empresa.get('criado_em'))}\n"
        f"[bold]Atualizado em:[/bold] {_formatar_data(empresa.get('atualizado_em'))}\n"
        f"[bold]Versao:[/bold] {empresa.get('versao', 1)}"
    )
    exibir_painel(metadados, titulo=f"{ICONES['calendario']} METADADOS", estilo_borda="yellow")

    # Histórico de alterações (últimas 5)
    historico = empresa.get('historico_alteracoes', [])
    if historico:
        historico_texto = []
        for entrada in historico[-5:]:
            timestamp = entrada.get('timestamp', 'N/A')[:19]
            acao = entrada.get('acao', 'N/A')
            versao = f"v{entrada.get('versao_anterior', '?')} -> v{entrada.get('versao_nova', '?')}"
            historico_texto.append(f"[{timestamp}] {acao} ({versao})")
            if entrada.get('campos_alterados'):
                campos = ", ".join(entrada.get('campos_alterados', []))
                historico_texto.append(f"  Campos: {campos}")

        exibir_painel(
            "\n".join(historico_texto),
            titulo=f"{ICONES['relatorio']} HISTORICO (ultimas 5 alteracoes)",
            estilo_borda="cyan"
        )


def _listar_empresas() -> None:
    """Lista todas as empresas cadastradas"""
    servico = _criar_servico_empresa()
    if not servico:
        return

    exibir_cabecalho("LISTA DE EMPRESAS", ICONES["listar"])

    # Paginação
    pagina = 1
    limite = 10

    while True:
        skip = (pagina - 1) * limite
        with logger.performance("listar_empresas"):
            resultado = servico.listar_todos(skip=skip, limit=limite)

        empresas = resultado.get('dados', [])
        total = resultado.get('total', 0)
        paginas = resultado.get('paginas', 1)

        if not empresas:
            exibir_info("Nenhuma empresa cadastrada.")
            break

        # Montar tabela
        dados = []
        for idx, emp in enumerate(empresas, start=skip + 1):
            nome = (emp.get('nome', 'N/A')[:28] + '..') if len(emp.get('nome', '')) > 30 else emp.get('nome', 'N/A')
            cnpj = emp.get('cnpj', '-') or '-'
            status = _formatar_status(emp.get('status', 'N/A'))
            dados.append([str(idx), nome, cnpj, status])

        exibir_tabela(
            f"Empresas (Pagina {pagina}/{paginas} - Total: {total})",
            ["#", "Nome", "CNPJ", "Status"],
            dados
        )

        # Navegação
        if paginas > 1:
            opcoes = ["Proxima pagina", "Pagina anterior", "Ver detalhes", "Voltar"]
            opcao = pedir_selecao("Navegacao:", opcoes)

            if opcao is None or "Voltar" in opcao:
                break
            elif "Proxima" in opcao and pagina < paginas:
                pagina += 1
            elif "anterior" in opcao and pagina > 1:
                pagina -= 1
            elif "Ver detalhes" in opcao:
                num = pedir_inteiro("Digite o numero da empresa:", minimo=1, maximo=total)
                if num:
                    try:
                        idx = num - 1
                        # Buscar empresa específica
                        resultado_all = servico.listar_todos(skip=idx, limit=1)
                        if resultado_all.get('dados'):
                            _exibir_empresa_detalhada(resultado_all['dados'][0])
                            pausar()
                    except Exception as e:
                        logger.error(f"Erro ao buscar empresa: {e}")
                        exibir_erro("Erro ao buscar empresa")
        else:
            opcoes = ["Ver detalhes", "Voltar"]
            opcao = pedir_selecao("Navegacao:", opcoes)
            if opcao and "Ver detalhes" in opcao:
                num = pedir_inteiro("Digite o numero da empresa:", minimo=1, maximo=len(empresas))
                if num and 1 <= num <= len(empresas):
                    _exibir_empresa_detalhada(empresas[num - 1])
                    pausar()
            break


def _criar_empresa() -> None:
    """Interface para criar nova empresa"""
    servico = _criar_servico_empresa()
    if not servico:
        return

    exibir_cabecalho("CRIAR NOVA EMPRESA", ICONES["criar"])
    exibir_info("Preencha os dados da empresa (* = obrigatorio)")

    # Coletar dados
    nome = pedir_texto("* Nome/Razao Social:")
    if not nome:
        exibir_erro("Nome e obrigatorio!")
        pausar()
        return

    # Verificar se já existe
    existente = servico.buscar_por_nome(nome, exato=True)
    if existente:
        exibir_aviso("Ja existe uma empresa com esse nome!")
        _exibir_empresa_detalhada(existente)
        pausar()
        return

    cnpj = pedir_texto("CNPJ (XX.XXX.XXX/XXXX-XX):", obrigatorio=False) or None
    atividade = pedir_texto("Atividade Principal:", obrigatorio=False) or None
    endereco = pedir_texto("Endereco Completo:", obrigatorio=False) or None
    telefone = pedir_texto("Telefone:", obrigatorio=False) or None
    email = pedir_texto("Email:", obrigatorio=False) or None
    responsavel = pedir_texto("Responsavel:", obrigatorio=False) or None

    # Status (usando Enum)
    status_opcoes = [STATUS_DISPLAY.get(s, s.value) for s in StatusEmpresa]
    status_selecionado = pedir_selecao("Status:", status_opcoes)

    if status_selecionado is None:
        exibir_aviso("Operacao cancelada.")
        pausar()
        return

    # Mapear de volta para enum value
    status_lista = list(StatusEmpresa)
    idx_status = status_opcoes.index(status_selecionado) if status_selecionado in status_opcoes else 0
    status = status_lista[idx_status].value if 0 <= idx_status < len(status_lista) else StatusEmpresa.ATIVA.value

    # Confirmar
    resumo = (
        f"[bold]Nome:[/bold] {nome}\n"
        f"[bold]CNPJ:[/bold] {cnpj or 'Nao informado'}\n"
        f"[bold]Atividade:[/bold] {atividade or 'Nao informada'}\n"
        f"[bold]Endereco:[/bold] {endereco or 'Nao informado'}\n"
        f"[bold]Telefone:[/bold] {telefone or 'Nao informado'}\n"
        f"[bold]Email:[/bold] {email or 'Nao informado'}\n"
        f"[bold]Responsavel:[/bold] {responsavel or 'Nao informado'}\n"
        f"[bold]Status:[/bold] {_formatar_status(status)}"
    )
    exibir_painel(resumo, titulo="RESUMO DA NOVA EMPRESA", estilo_borda="yellow")

    if not pedir_confirmacao("Confirmar criacao?"):
        exibir_aviso("Operacao cancelada.")
        pausar()
        return

    # Criar empresa
    dados = {
        "nome": nome,
        "cnpj": cnpj,
        "atividade": atividade,
        "endereco": endereco,
        "telefone": telefone,
        "email": email,
        "responsavel": responsavel,
        "status": status
    }

    empresa_id = servico.criar_empresa(dados)

    if empresa_id:
        exibir_sucesso("Empresa criada com sucesso!")
        exibir_info(f"ID: {empresa_id}")
        logger.audit("EMPRESA_CRIADA_INTERFACE", target=f"empresa:{empresa_id}", changes={"nome": nome, "cnpj": cnpj})
    else:
        exibir_erro("Erro ao criar empresa.")

    pausar()


def _buscar_empresa() -> Optional[Dict[str, Any]]:
    """Busca uma empresa por nome (busca parcial com seleção)"""
    servico = _criar_servico_empresa()
    if not servico:
        return None

    nome = pedir_texto("Digite o nome da empresa (ou parte dele):")
    if not nome:
        exibir_erro("Nome nao informado.")
        return None

    # Buscar todas as empresas que correspondem
    empresas = servico.buscar_todas_por_nome(nome)

    if not empresas:
        exibir_erro("Nenhuma empresa encontrada.")
        return None

    if len(empresas) == 1:
        # Apenas uma empresa encontrada - confirmar
        empresa = empresas[0]
        cnpj = empresa.get('cnpj') or 'CNPJ nao informado'
        exibir_sucesso(f"Empresa encontrada: {empresa.get('nome')} ({cnpj})")
        exibir_info(f"Status: {_formatar_status(empresa.get('status', 'N/A'))}")

        if pedir_confirmacao("E esta empresa?"):
            _exibir_empresa_detalhada(empresa)
            return empresa
        else:
            exibir_aviso("Operacao cancelada.")
            return None

    # Múltiplas empresas encontradas - pedir para escolher
    exibir_info(f"{len(empresas)} empresa(s) encontrada(s)")

    # Montar tabela
    dados = []
    for idx, emp in enumerate(empresas, start=1):
        nome_emp = (emp.get('nome', 'N/A')[:33] + '..') if len(emp.get('nome', '')) > 35 else emp.get('nome', 'N/A')
        status = _formatar_status(emp.get('status', 'N/A'))
        dados.append([str(idx), nome_emp, status])

    exibir_tabela("Empresas Encontradas", ["#", "Nome", "Status"], dados)

    # Adicionar opção de cancelar
    escolha = pedir_inteiro("Escolha o numero da empresa (0 para cancelar):", minimo=0, maximo=len(empresas))

    if escolha is None or escolha == 0:
        exibir_aviso("Operacao cancelada.")
        return None

    if 1 <= escolha <= len(empresas):
        empresa = empresas[escolha - 1]
        _exibir_empresa_detalhada(empresa)
        return empresa
    else:
        exibir_erro("Numero invalido.")
        return None


def _buscar_empresa_menu() -> None:
    """Wrapper para buscar empresa com pausa no final"""
    empresa = _buscar_empresa()
    if empresa:
        pausar()


def _atualizar_empresa() -> None:
    """Interface para atualizar dados de uma empresa"""
    servico = _criar_servico_empresa()
    if not servico:
        return

    exibir_cabecalho("ATUALIZAR EMPRESA", ICONES["editar"])

    # Buscar empresa
    empresa = _buscar_empresa()
    if not empresa:
        pausar()
        return

    empresa_id = str(empresa.get('_id'))

    exibir_info("Digite os novos valores (ENTER para manter o atual)")

    alteracoes = {}

    # Nome
    atual = empresa.get('nome', '')
    novo = pedir_texto(f"Nome [{atual}]:", obrigatorio=False)
    if novo and novo != atual:
        alteracoes['nome'] = novo

    # CNPJ
    atual = empresa.get('cnpj', '') or ''
    novo = pedir_texto(f"CNPJ [{atual or 'Nao informado'}]:", obrigatorio=False)
    if novo and novo != atual:
        alteracoes['cnpj'] = novo

    # Atividade
    atual = empresa.get('atividade', '') or ''
    novo = pedir_texto(f"Atividade [{atual or 'Nao informada'}]:", obrigatorio=False)
    if novo and novo != atual:
        alteracoes['atividade'] = novo

    # Endereço
    atual = empresa.get('endereco', '') or ''
    novo = pedir_texto(f"Endereco [{atual or 'Nao informado'}]:", obrigatorio=False)
    if novo and novo != atual:
        alteracoes['endereco'] = novo

    # Telefone
    atual = empresa.get('telefone', '') or ''
    novo = pedir_texto(f"Telefone [{atual or 'Nao informado'}]:", obrigatorio=False)
    if novo and novo != atual:
        alteracoes['telefone'] = novo

    # Email
    atual = empresa.get('email', '') or ''
    novo = pedir_texto(f"Email [{atual or 'Nao informado'}]:", obrigatorio=False)
    if novo and novo != atual:
        alteracoes['email'] = novo

    # Responsável
    atual = empresa.get('responsavel', '') or ''
    novo = pedir_texto(f"Responsavel [{atual or 'Nao informado'}]:", obrigatorio=False)
    if novo and novo != atual:
        alteracoes['responsavel'] = novo

    if not alteracoes:
        exibir_aviso("Nenhuma alteracao informada.")
        pausar()
        return

    # Confirmar
    alteracoes_texto = []
    for campo, valor in alteracoes.items():
        valor_anterior = empresa.get(campo, 'N/A') or 'N/A'
        alteracoes_texto.append(f"[bold]{campo}:[/bold] {valor_anterior} -> {valor}")

    exibir_painel(
        "\n".join(alteracoes_texto),
        titulo="ALTERACOES A SEREM APLICADAS",
        estilo_borda="yellow"
    )

    if not pedir_confirmacao("Confirmar alteracoes?"):
        exibir_aviso("Operacao cancelada.")
        pausar()
        return

    # Aplicar alterações
    sucesso = servico.atualizar(empresa_id, alteracoes, registrar_historico=True)

    if sucesso:
        exibir_sucesso("Empresa atualizada com sucesso!")
        logger.audit("EMPRESA_ATUALIZADA_INTERFACE", target=f"empresa:{empresa_id}", changes=alteracoes)
        exibir_info("Versao incrementada automaticamente.")
        exibir_info("Historico de alteracoes registrado.")
    else:
        exibir_erro("Erro ao atualizar empresa.")

    pausar()


def _alterar_status_empresa() -> None:
    """Interface para alterar status de uma empresa"""
    servico = _criar_servico_empresa()
    if not servico:
        return

    exibir_cabecalho("ALTERAR STATUS DA EMPRESA", ICONES["atualizar"])

    # Buscar empresa
    empresa = _buscar_empresa()
    if not empresa:
        pausar()
        return

    empresa_id = str(empresa.get('_id'))
    status_atual = empresa.get('status', 'N/A')

    exibir_info(f"Status atual: {_formatar_status(status_atual)}")

    # Escolher novo status
    status_opcoes = [STATUS_DISPLAY.get(s, s.value) for s in StatusEmpresa]
    status_selecionado = pedir_selecao("Escolha o novo status:", status_opcoes)

    if status_selecionado is None:
        exibir_aviso("Operacao cancelada.")
        pausar()
        return

    # Mapear de volta para enum value
    status_lista = list(StatusEmpresa)
    idx_status = status_opcoes.index(status_selecionado) if status_selecionado in status_opcoes else -1

    if idx_status < 0 or idx_status >= len(status_lista):
        exibir_erro("Opcao invalida.")
        pausar()
        return

    novo_status = status_lista[idx_status].value

    if novo_status == status_atual:
        exibir_aviso("O status ja e esse.")
        pausar()
        return

    # Confirmar
    confirmacao_texto = f"[bold]De:[/bold] {_formatar_status(status_atual)}\n[bold]Para:[/bold] {_formatar_status(novo_status)}"
    exibir_painel(confirmacao_texto, titulo="CONFIRMACAO DE ALTERACAO", estilo_borda="yellow")

    if not pedir_confirmacao("Confirmar alteracao de status?"):
        exibir_aviso("Operacao cancelada.")
        pausar()
        return

    # Aplicar alteração
    sucesso = servico.alterar_status(empresa_id, novo_status)

    if sucesso:
        exibir_sucesso("Status alterado com sucesso!")
        exibir_info("Versao incrementada automaticamente.")
        exibir_info("Historico de alteracoes registrado.")
    else:
        exibir_erro("Erro ao alterar status.")

    pausar()


def _exibir_estatisticas() -> None:
    """Exibe estatísticas de empresas"""
    servico = _criar_servico_empresa()
    if not servico:
        return

    stats = servico.obter_estatisticas()

    conteudo = (
        f"[bold]Total de empresas:[/bold] {stats.get('total_empresas', 0)}\n"
        f"[bold]Empresas completas:[/bold] {stats.get('empresas_completas', 0)}\n"
        f"[bold]Empresas incompletas:[/bold] {stats.get('empresas_incompletas', 0)}\n"
        f"[bold]Empresas ativas:[/bold] {stats.get('empresas_ativas', 0)}"
    )

    exibir_painel(conteudo, titulo=f"{ICONES['estatistica']} ESTATISTICAS DE EMPRESAS", estilo_borda="blue")

    pausar()


def _migrar_remover_id_empresa() -> None:
    """Remove o campo id_empresa de todas as empresas (migração)"""
    servico = _criar_servico_empresa()
    if not servico:
        return

    exibir_cabecalho("MIGRACAO: Remover campo id_empresa", ICONES["config"])
    exibir_aviso("Esta operacao remove o campo 'id_empresa' de todas as empresas.")
    exibir_info("O MongoDB usa o campo '_id' automaticamente, tornando id_empresa desnecessario.")

    if not pedir_confirmacao("Continuar com a migracao?"):
        exibir_aviso("Operacao cancelada.")
        pausar()
        return

    quantidade = servico.remover_campo_id_empresa()

    exibir_sucesso("Migracao concluida!")
    exibir_info(f"{quantidade} documentos atualizados.")

    pausar()


def Interface_Empresas():
    """Interface principal para gerenciamento de empresas"""
    logger.debug("Iniciando interface de gerenciamento de empresas")

    if not EMPRESA_SERVICE_DISPONIVEL:
        exibir_erro("Servico de empresas nao disponivel!")
        return

    (
        MenuBuilder("GERENCIAR EMPRESAS", ICONES["empresa"])
        .adicionar("Listar todas as empresas", _listar_empresas, ICONES["listar"])
        .adicionar("Criar nova empresa", _criar_empresa, ICONES["criar"])
        .adicionar("Buscar empresa", _buscar_empresa_menu, ICONES["buscar"])
        .adicionar("Atualizar dados de empresa", _atualizar_empresa, ICONES["editar"])
        .adicionar("Alterar status (ativar/inativar)", _alterar_status_empresa, ICONES["atualizar"])
        .separador()
        .adicionar("Estatisticas", _exibir_estatisticas, ICONES["estatistica"])
        .adicionar("Migracao: Remover id_empresa", _migrar_remover_id_empresa, ICONES["config"])
        .com_voltar("Voltar ao Menu Principal")
        .executar()
    )
