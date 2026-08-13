"""Interface para operacoes com Folha de Ponto."""

from datetime import date
from typing import Optional, List, Dict, Any

from src.folha_de_ponto import Folha_de_Ponto
from src.utils.logger_config import logger
from src.utils.data_utils import parse_data_flexivel, formatar_data_br

# Importar funcoes utilitarias centralizadas
from src.services.mongodb_utils import (
    buscar_nome_funcao,
    buscar_nome_horario,
    buscar_nome_contrato,
    buscar_funcionario,
    buscar_empresa,
    buscar_folha_existente,
    listar_funcionarios_por_filtro,
    buscar_contratos_por_nome,
    formatar_data,
)

from src.interface.core.components import (
    MenuBuilder,
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


# =====================================================================
# FUNCOES AUXILIARES
# =====================================================================


def _input_lista(mensagem: str) -> Optional[List[str]]:
    """
    Recebe multiplos valores do usuario via pedir_texto.

    Args:
        mensagem: Prompt a exibir.

    Returns:
        Lista de valores ou None se vazio.
    """
    entrada = pedir_texto(mensagem, obrigatorio=False)
    if not entrada:
        return None
    if "," in entrada:
        return [e.strip() for e in entrada.split(",") if e.strip()]
    return [entrada]


def _criar_instancia_folha_ponto() -> Folha_de_Ponto:
    """
    Cria instancia da Folha_de_Ponto usando o fluxo HTML-only.
    """
    return Folha_de_Ponto()


def _exibir_dados_folha_existente(folha: Dict[str, Any], funcionario: Dict[str, Any]) -> None:
    """Exibe os dados de uma folha de ponto existente de forma formatada."""

    # Buscar dados relacionados
    funcao_nome = buscar_nome_funcao(funcionario.get("funcao_id"))
    horario_descricao = buscar_nome_horario(funcionario.get("horario_id"))
    contrato_nome = buscar_nome_contrato(funcionario.get("contrato_empresa_id"))
    empresa = buscar_empresa(folha.get("empresa_id"))

    folha_data = folha.get("folha_data", {})
    dias = folha_data.get("dias", [])

    # Dados do Funcionario
    func_info = (
        f"[bold]Nome:[/bold]     {funcionario.get('nome', 'N/A')}\n"
        f"[bold]Lotacao:[/bold]  {funcionario.get('lotacao', 'N/A')}\n"
        f"[bold]Funcao:[/bold]   {funcao_nome}\n"
        f"[bold]Horario:[/bold]  {horario_descricao}\n"
        f"[bold]Contrato:[/bold] {contrato_nome}\n"
        f"[bold]Status:[/bold]   {funcionario.get('status', 'N/A')}"
    )
    exibir_painel(func_info, titulo=f"{ICONES['funcionario']} DADOS DO FUNCIONARIO", estilo_borda="blue")

    # Dados da Empresa
    if empresa:
        emp_info = (
            f"[bold]Nome:[/bold] {empresa.get('nome', 'N/A')}\n"
            f"[bold]CNPJ:[/bold] {empresa.get('cnpj', 'N/A')}"
        )
    else:
        emp_info = f"[bold]Empresa ID:[/bold] {folha.get('empresa_id', 'N/A')}"
    exibir_painel(emp_info, titulo=f"{ICONES['empresa']} DADOS DA EMPRESA", estilo_borda="blue")

    # Dados da Folha
    folha_info = (
        f"[bold]Mes Referencia:[/bold]     {folha.get('mes_referencia', 'N/A')}\n"
        f"[bold]Periodo:[/bold]            {formatar_data_br(folha_data.get('data_inicio'))} a {formatar_data_br(folha_data.get('data_fim'))}\n"
        f"[bold]Total Horas Mes:[/bold]    {folha_data.get('total_horas_mes', 'N/A')}\n"
        f"[bold]Total Faltas:[/bold]       {folha_data.get('total_faltas', 0)}\n"
        f"[bold]Total Feriados:[/bold]     {folha_data.get('total_feriados', 0)}\n"
        f"[bold]Finais de Semana:[/bold]   {folha_data.get('total_finais_semana', 0)}\n"
        f"[bold]Status:[/bold]             {folha.get('status', 'N/A')}\n"
        f"[bold]Data Criacao:[/bold]       {formatar_data(folha.get('data_criacao'))}\n"
        f"[bold]Ultima Atualizacao:[/bold] {formatar_data(folha.get('data_atualizacao'))}"
    )
    exibir_painel(folha_info, titulo=f"{ICONES['folha_ponto']} DADOS DA FOLHA DE PONTO", estilo_borda="cyan")

    # Resumo dos dias
    if dias:
        dias_trabalhados = sum(1 for d in dias if d.get("trabalhado", False))
        dias_falta = sum(1 for d in dias if d.get("falta", False))
        dias_feriado = sum(1 for d in dias if d.get("feriado", False))
        dias_fim_semana = sum(1 for d in dias if d.get("fim_de_semana", False))

        resumo_info = (
            f"[bold]Total de dias:[/bold]    {len(dias)}\n"
            f"[bold]Dias trabalhados:[/bold] {dias_trabalhados}\n"
            f"[bold]Dias de falta:[/bold]    {dias_falta}\n"
            f"[bold]Feriados:[/bold]         {dias_feriado}\n"
            f"[bold]Finais de semana:[/bold] {dias_fim_semana}"
        )
        exibir_painel(resumo_info, titulo=f"{ICONES['estatistica']} RESUMO DOS DIAS", estilo_borda="green")

        # Mostrar primeiros 5 dias como amostra
        dados_dias = []
        for dia in dias[:5]:
            data_dia = formatar_data_br(dia.get("data")) or "N/A"
            entrada = dia.get("entrada", "-")
            saida = dia.get("saida", "-")
            obs = dia.get("observacao", "")
            status = "T" if dia.get("trabalhado") else ("F" if dia.get("falta") else "-")
            obs_trunc = obs[:20] + "..." if len(obs) > 20 else obs
            dados_dias.append([data_dia, entrada, saida, status, obs_trunc])

        if dados_dias:
            exibir_tabela(
                "Primeiros 5 dias",
                ["Data", "Entrada", "Saida", "Status", "Obs"],
                dados_dias,
                mostrar_indice=False,
            )

    # Analise IA
    if folha_data.get("analise_ia_concluida"):
        analise = folha_data.get("analise_ia", {})
        ia_info = f"[bold]Analise concluida:[/bold] Sim"
        if analise:
            ia_info += f"\n[bold]Observacoes:[/bold] {analise.get('observacoes', 'N/A')[:80]}..."
        exibir_painel(ia_info, titulo=f"{ICONES['ia']} ANALISE IA", estilo_borda="magenta")


# =====================================================================
# BUSCA DE FUNCIONARIOS POR FILTRO
# =====================================================================


def _buscar_funcionarios_por_filtro(opcao: str) -> List[Dict[str, Any]]:
    """Busca funcionarios no MongoDB conforme o filtro escolhido."""
    try:
        from bson import ObjectId

        filtro = {"status": "ativo"}

        if opcao == "Todos os funcionarios (ativos)":
            pass

        elif opcao == "Filtrar por ID(s) (ObjectId)":
            ids = _input_lista("ObjectId(s) dos funcionarios (separados por virgula):")
            if not ids:
                return []
            try:
                object_ids = [ObjectId(i.strip()) for i in ids]
                filtro["_id"] = {"$in": object_ids}
            except Exception as e:
                exibir_erro(f"ID(s) invalido(s): {e}")
                return []

        elif opcao == "Filtrar por nome(s)":
            nomes = _input_lista("Nome(s) dos funcionarios (separados por virgula):")
            if not nomes:
                return []
            regex_nomes = [{"nome": {"$regex": nome, "$options": "i"}} for nome in nomes]
            filtro["$or"] = regex_nomes

        elif opcao == "Filtrar por lotacao(oes)":
            lotacoes = _input_lista("Lotacao(oes) (separadas por virgula):")
            if not lotacoes:
                return []
            regex_lotacoes = [{"lotacao": {"$regex": lot, "$options": "i"}} for lot in lotacoes]
            filtro["$or"] = regex_lotacoes

        elif opcao == "Filtrar por contrato(s)":
            contratos = _input_lista("Contrato(s) (separados por virgula):")
            if not contratos:
                return []
            contrato_ids = buscar_contratos_por_nome(contratos)
            if contrato_ids:
                filtro["contrato_empresa_id"] = {"$in": contrato_ids}
            else:
                exibir_aviso("Nenhum contrato encontrado com os nomes informados")
                return []
        else:
            return []

        return listar_funcionarios_por_filtro(filtro)

    except Exception as e:
        logger.error(f"Erro ao buscar funcionarios: {e}")
        exibir_erro(f"Erro ao buscar funcionarios: {e}")
        return []


# =====================================================================
# OPERACOES PRINCIPAIS
# =====================================================================


def _gerar_folha_ponto() -> None:
    """Interface unificada para gerar folhas de ponto."""
    logger.debug("Iniciando interface para geracao de folha de ponto")

    exibir_painel(
        "[bold]Gerar folhas de ponto a partir do MongoDB e exportar como PDF.[/bold]\n"
        "Todos os dados sao buscados do MongoDB.",
        titulo="GERAR FOLHA DE PONTO (MongoDB -> PDF)",
        estilo_borda="blue",
    )

    # Filtro de funcionarios
    opcao = pedir_selecao(
        "Como deseja filtrar a criacao das folhas?",
        [
            "Todos os funcionarios (ativos)",
            "Filtrar por ID(s) (ObjectId)",
            "Filtrar por nome(s)",
            "Filtrar por lotacao(oes)",
            "Filtrar por contrato(s)",
        ],
    )

    if opcao is None:
        return

    # Solicitar data
    data_str = pedir_texto(
        "Data (DD/MM/YYYY, ex: 15/08/2026) ou ENTER para data atual:",
        obrigatorio=False,
    )
    data = None
    if data_str:
        data = parse_data_flexivel(data_str, retornar_date=True)
    if data is None:
        exibir_aviso("Data invalida! Usando data atual.")
        data = date.today()

    mes_referencia = data.strftime("%Y-%m")

    # Buscar funcionarios conforme o filtro
    funcionarios = _buscar_funcionarios_por_filtro(opcao)

    if not funcionarios:
        exibir_info("Nenhum funcionario encontrado com os filtros informados.")
        return

    exibir_info(f"{len(funcionarios)} funcionario(s) encontrado(s)")
    exibir_info(f"Mes de referencia: {mes_referencia}")

    # Processar cada funcionario
    fp = _criar_instancia_folha_ponto()
    total_processados = 0
    total_erros = 0

    for func in funcionarios:
        funcionario_id = func.get("_id")
        funcionario_nome = func.get("nome", "Desconhecido")

        # Buscar empresa do funcionario
        empresas_ids = func.get("empresas_ids", [])
        if not empresas_ids:
            exibir_aviso(f"{funcionario_nome}: Sem empresa vinculada")
            total_erros += 1
            continue

        funcionario_id_str = str(funcionario_id)

        # Processar todas as empresas vinculadas
        for emp in empresas_ids:
            empresa_id = str(emp)

            # Verificar se existe folha no MongoDB
            folha_existente = buscar_folha_existente(funcionario_id, empresa_id, mes_referencia)

            if folha_existente:
                _exibir_dados_folha_existente(folha_existente, func)

                escolha = pedir_selecao(
                    f"Ja existe folha para {funcionario_nome} nesta empresa. O que fazer?",
                    [
                        "Gerar PDF com dados existentes",
                        "Criar nova folha (sobrescreve)",
                        "Pular esta empresa",
                        "Cancelar operacao",
                    ],
                )

                if escolha is None or "Cancelar" in (escolha or ""):
                    exibir_aviso("Operacao cancelada pelo usuario.")
                    return

                elif "PDF" in (escolha or ""):
                    console.print(f"\n[info]Gerando PDF para {funcionario_nome} (empresa {empresa_id})...[/info]")
                    try:
                        resultado = fp.gerar_pdf_de_folha_existente(folha_existente)
                        if resultado:
                            exibir_sucesso(f"PDF gerado: {resultado}")
                            total_processados += 1
                        else:
                            exibir_erro("Erro ao gerar PDF")
                            total_erros += 1
                    except Exception as e:
                        exibir_erro(f"Erro: {e}")
                        total_erros += 1

                elif "nova folha" in (escolha or "").lower():
                    console.print(f"\n[info]Criando nova folha para {funcionario_nome} (empresa {empresa_id})...[/info]")
                    try:
                        resultado = fp.criar_mongodb_por_id(
                            funcionario_id=funcionario_id_str,
                            empresa_id=empresa_id,
                            data=data,
                        )
                        if resultado and resultado.get("status") in ["sucesso", "parcial"]:
                            exibir_sucesso(f"Nova folha criada para {funcionario_nome} (empresa {empresa_id})")
                            total_processados += 1
                        else:
                            exibir_erro("Erro ao criar folha")
                            total_erros += 1
                    except Exception as e:
                        exibir_erro(f"Erro: {e}")
                        total_erros += 1

                elif "Pular" in (escolha or ""):
                    exibir_info(f"Pulando empresa {empresa_id} para {funcionario_nome}")

            else:
                # Nao existe folha, criar nova
                console.print(f"\n[info]Criando folha para: {funcionario_nome} (empresa {empresa_id})...[/info]")
                try:
                    resultado = fp.criar_mongodb_por_id(
                        funcionario_id=funcionario_id_str,
                        empresa_id=empresa_id,
                        data=data,
                    )
                    if resultado and resultado.get("status") in ["sucesso", "parcial"]:
                        exibir_sucesso(f"Folha criada para {funcionario_nome} (empresa {empresa_id})")
                        total_processados += 1
                    else:
                        exibir_erro(f"Erro ao criar folha para {funcionario_nome} (empresa {empresa_id})")
                        total_erros += 1
                except Exception as e:
                    exibir_erro(f"Erro ao criar folha para {funcionario_nome} (empresa {empresa_id}): {e}")
                    total_erros += 1

    exibir_resultado(
        "RESUMO DA OPERACAO",
        sucesso=total_processados,
        erros=total_erros,
        detalhes=[f"Total de funcionarios: {len(funcionarios)}"],
    )


def _ler_folha_de_ponto() -> None:
    """Interface para ler folhas de ponto."""
    logger.debug("Iniciando interface para leitura de folha de ponto")

    opcao = pedir_selecao(
        "Como deseja ler as folhas?",
        ["Exibir todos os funcionarios", "Exportar DataFrame para arquivo"],
    )

    if opcao is None:
        return

    if "Exibir" in (opcao or ""):
        fp = _criar_instancia_folha_ponto()
        console.print(fp.criar_dataFrame_funcionários().to_string())

    elif "Exportar" in (opcao or ""):
        caminho = pedir_texto("Caminho do arquivo de destino (ex: funcionarios.xlsx):")
        if caminho:
            fp = _criar_instancia_folha_ponto()
            fp.exportar_dataframe(caminho)
            exibir_sucesso(f"Arquivo exportado para {caminho}")


def _processar_pdfs_interface() -> None:
    """Interface para processar PDFs de folhas de ponto preenchidas com IA."""
    logger.debug("Iniciando interface para processamento de PDFs")

    exibir_painel(
        "[bold]Processar PDFs de folhas de ponto preenchidas usando IA.[/bold]",
        titulo="PROCESSAMENTO DE PDFs COM IA",
        estilo_borda="blue",
    )

    opcao = pedir_selecao(
        "Como deseja fornecer os arquivos PDF?",
        [
            "Processar arquivo unico",
            "Processar multiplos arquivos",
            "Processar todos PDFs de um diretorio",
        ],
    )

    if opcao is None:
        return

    caminho_pdfs = None

    if "unico" in (opcao or "").lower():
        caminho = pedir_texto("Caminho completo do arquivo PDF:")
        if not caminho:
            return
        caminho_pdfs = caminho
        exibir_info(f"Processando arquivo: {caminho}")

    elif "multiplos" in (opcao or "").lower():
        caminhos_str = pedir_texto("Caminhos dos arquivos PDF (separados por virgula):")
        if not caminhos_str:
            return
        caminho_pdfs = [c.strip() for c in caminhos_str.split(",") if c.strip()]
        exibir_info(f"Processando {len(caminho_pdfs)} arquivo(s)")

    elif "diretorio" in (opcao or "").lower():
        caminho = pedir_texto("Caminho do diretorio contendo os PDFs:")
        if not caminho:
            return
        caminho_pdfs = caminho
        exibir_info(f"Processando diretorio: {caminho}")

    # Processar PDFs
    try:
        fp = _criar_instancia_folha_ponto()
        console.print(f"\n[info]{ICONES['ia']} Iniciando processamento com IA...[/info]")
        console.print("[dim]Aguarde, isso pode levar alguns minutos...[/dim]\n")

        resultado = fp.processar_pdfs(caminho_pdfs)

        # Detalhes de cada arquivo
        detalhes = []
        for res in resultado["resultados"]:
            if res["sucesso"]:
                detalhes.append(
                    f"{ICONES['sucesso']} {res['nome_arquivo']} - "
                    f"Dias: {res['dias_extraidos']} | Tempo: {res['tempo_s']:.2f}s"
                )
                for aviso in res.get("avisos", []):
                    detalhes.append(f"  {ICONES['aviso']} {aviso}")
            else:
                erros_str = "; ".join(res.get("erros", []))
                detalhes.append(f"{ICONES['erro']} {res['nome_arquivo']} - {erros_str}")

        # Taxa de sucesso
        if resultado["processados_sucesso"] > 0:
            taxa = (resultado["processados_sucesso"] / resultado["total_arquivos"]) * 100
            detalhes.append(f"\nTaxa de sucesso: {taxa:.1f}%")

        exibir_resultado(
            "RESUMO DO PROCESSAMENTO",
            sucesso=resultado["processados_sucesso"],
            erros=resultado["processados_erro"],
            detalhes=detalhes,
        )

    except Exception as e:
        logger.error(f"Erro ao processar PDFs: {e}", exc_info=True)
        exibir_erro(f"Erro ao processar PDFs: {e}")


def _abrir_envio_folha_ponto() -> None:
    """Abre o menu de envio de folhas de ponto."""
    try:
        from src.interface.interface_envio_folha_ponto import iniciar_menu_envio
        logger.debug("Iniciando envio de Folhas de Ponto")
        iniciar_menu_envio()
    except ImportError as e:
        logger.error(f"Erro ao importar menu de envio: {e}")
        exibir_erro("Modulo de envio de folhas de ponto nao disponivel!")
        exibir_info(f"Detalhes: {e}")
    except Exception as e:
        logger.error(f"Erro ao abrir menu de envio: {e}")
        exibir_erro(f"Erro: {e}")


# =====================================================================
# GERENCIAR FOLHAS GERADAS (Visualizar / Buscar / Excluir / Editar)
# =====================================================================


def _obter_servico_folha() -> Optional[Any]:
    """Retorna instância do FolhaDePontoService (ou None se indisponível)."""
    try:
        from src.services.folha_ponto_service import FolhaDePontoService
        servico = FolhaDePontoService()
        return servico if servico.disponivel else None
    except Exception as e:
        logger.error(f"Erro ao obter serviço de folha de ponto: {e}")
        return None


def _obter_servico_envio() -> Optional[Any]:
    """Retorna instância do EnvioFolhaPontoService (ou None se indisponível)."""
    try:
        from src.services.envio_folha_ponto_service import EnvioFolhaPontoService
        servico = EnvioFolhaPontoService()
        return servico if servico.disponivel else None
    except Exception as e:
        logger.debug(f"Erro ao obter serviço de envio: {e}")
        return None


def _exibir_detalhes_folha_completa(folha: Dict[str, Any]) -> None:
    """Exibe detalhes completos de uma folha (funcionário, período, dias, totais, status)."""
    funcionario = buscar_funcionario(folha.get("funcionario_id"))
    _exibir_dados_folha_existente(folha, funcionario or {})

    # Informações extras: versão, histórico e soft delete
    extras = (
        f"[bold]Versao:[/bold]        {folha.get('versao', 1)}\n"
        f"[bold]ID Folha:[/bold]     {folha.get('_id', 'N/A')}\n"
        f"[bold]Excluida:[/bold]     {'SIM' if folha.get('excluida') else 'Nao'}\n"
        f"[bold]Motivo Excl.:[/bold] {folha.get('motivo_exclusao') or 'N/A'}\n"
        f"[bold]PDF:[/bold]          {folha.get('caminho_arquivo_gerado') or 'N/A'}"
    )
    exibir_painel(extras, titulo=f"{ICONES['info']} CONTROLE E VERSÃO", estilo_borda="yellow")

    historico = folha.get("historico_alteracoes", []) or []
    if historico:
        linhas_hist = []
        for item in historico[-5:]:
            acao = item.get("acao", "")
            ts = item.get("timestamp", "")
            versao_hist = f"v{item.get('versao_anterior')}->v{item.get('versao_nova')}"
            linhas_hist.append([str(ts)[:19], versao_hist, acao])
        if linhas_hist:
            exibir_tabela(
                "Ultimas alteracoes (historico)",
                ["Data", "Versao", "Acao"],
                linhas_hist,
                mostrar_indice=False,
            )


def _buscar_folhas_por_nome(
    nome: Optional[str] = None,
    mes_referencia: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Busca folhas por nome do funcionário (com filtros opcionais de mês/status)."""
    servico = _obter_servico_folha()
    if not servico:
        exibir_erro("Servico de folha de ponto indisponivel (MongoDB?).")
        return []

    if not nome:
        nome = pedir_texto("Nome (ou parte) do funcionario:", obrigatorio=True)
    if not nome:
        return []

    if mes_referencia is None:
        mes_input = pedir_texto("Mes (YYYY-MM) para filtrar (ENTER para todos):", obrigatorio=False)
        if mes_input and len(mes_input.strip()) >= 7:
            mes_referencia = mes_input.strip()[:7]

    if status is None:
        status_opcao = pedir_selecao(
            "Filtrar por status?",
            ["Todos", "criada", "preenchida", "analise_pendente", "analise_concluida", "exportada", "erro"],
        )
        if status_opcao and status_opcao != "Todos":
            status = status_opcao

    folhas = servico.buscar_por_nome_funcionario(
        nome=nome,
        mes_referencia=mes_referencia,
        status=status,
    )
    return folhas


def _visualizar_folha_gerada() -> None:
    """Acao 1: Visualizar uma folha de ponto ja gerada (por busca ou ID)."""
    servico = _obter_servico_folha()
    if not servico:
        exibir_erro("Servico de folha de ponto indisponivel (MongoDB?).")
        return

    exibir_painel(
        "[bold]Visualizar uma folha de ponto ja gerada.[/bold]\n"
        "Selecione por busca (nome/período) ou informe o ID diretamente.",
        titulo="VISUALIZAR FOLHA GERADA",
        estilo_borda="blue",
    )

    opcao = pedir_selecao(
        "Como deseja localizar a folha?",
        ["Buscar por nome do funcionario", "Informar ID da folha"],
    )

    folha = None

    if opcao is None:
        return

    if "Buscar por nome" in (opcao or ""):
        folhas = _buscar_folhas_por_nome()
        if not folhas:
            exibir_info("Nenhuma folha encontrada com os filtros informados.")
            return

        opcoes = [
            f"{f.get('folha_data', {}).get('nome_funcionario', 'N/A')} - {f.get('mes_referencia', '')} ({f.get('status', '')})"
            for f in folhas
        ]
        escolha = pedir_selecao("Folhas encontradas:", opcoes)
        if escolha is None:
            return
        idx = opcoes.index(escolha)
        folha_id = folhas[idx].get("_id")
        if folha_id:
            folha = servico.buscar_por_id(str(folha_id))
    else:
        folha_id_input = pedir_texto("ID da folha (ObjectId):", obrigatorio=True)
        if not folha_id_input:
            return
        folha = servico.buscar_por_id(folha_id_input.strip())
        if not folha:
            exibir_erro("Folha nao encontrada com esse ID.")
            return

    if not folha:
        exibir_erro("Nao foi possivel recuperar a folha.")
        return

    _exibir_detalhes_folha_completa(folha)
    pausar()


def _buscar_folha_por_nome_acao() -> None:
    """Acao 2: Buscar folhas por nome do funcionario (retorna lista)."""
    servico = _obter_servico_folha()
    if not servico:
        exibir_erro("Servico de folha de ponto indisponivel (MongoDB?).")
        return

    exibir_painel(
        "[bold]Buscar folhas de ponto por NOME do funcionario.[/bold]\n"
        "Filtros opcionais: mes/período e status.",
        titulo="BUSCAR FOLHA POR NOME",
        estilo_borda="blue",
    )

    folhas = _buscar_folhas_por_nome()

    if not folhas:
        exibir_info("Nenhuma folha encontrada com os filtros informados.")
        return

    exibir_info(f"{len(folhas)} folha(s) encontrada(s)")

    linhas = []
    for f in folhas:
        folha_data = f.get("folha_data", {}) or {}
        linhas.append([
            str(f.get("_id", ""))[-8:],
            folha_data.get("nome_funcionario", "N/A"),
            f.get("mes_referencia", ""),
            folha_data.get("total_horas_mes", "-"),
            f.get("status", ""),
            "SIM" if f.get("excluida") else "nao",
        ])

    exibir_tabela(
        "Folhas encontradas",
        ["ID", "Funcionario", "Mes", "Total Horas", "Status", "Excluida"],
        linhas,
        mostrar_indice=True,
    )
    pausar()


def _excluir_folha_gerada() -> None:
    """Acao 3: Excluir folha (SOFT DELETE - marca como excluida, nunca remove do banco)."""
    servico = _obter_servico_folha()
    if not servico:
        exibir_erro("Servico de folha de ponto indisponivel (MongoDB?).")
        return

    exibir_painel(
        "[bold]Excluir folha de ponto (SOFT DELETE).[/bold]\n"
        "A folha sera marcada como EXCLUIDA e mantida no banco para\n"
        "preservar o historico e os envios registrados (nunca apagada de vez).",
        titulo="EXCLUIR FOLHA GERADA",
        estilo_borda="red",
    )

    opcao = pedir_selecao(
        "Como deseja localizar a folha para excluir?",
        ["Buscar por nome do funcionario", "Informar ID da folha"],
    )

    folha = None

    if opcao is None:
        return

    if "Buscar por nome" in (opcao or ""):
        folhas = _buscar_folhas_por_nome()
        if not folhas:
            exibir_info("Nenhuma folha encontrada.")
            return
        opcoes = [
            f"{f.get('folha_data', {}).get('nome_funcionario', 'N/A')} - {f.get('mes_referencia', '')} ({f.get('status', '')})"
            for f in folhas
        ]
        escolha = pedir_selecao("Folhas encontradas:", opcoes)
        if escolha is None:
            return
        idx = opcoes.index(escolha)
        folha_id = folhas[idx].get("_id")
        if folha_id:
            folha = servico.buscar_por_id(str(folha_id))
    else:
        folha_id_input = pedir_texto("ID da folha (ObjectId):", obrigatorio=True)
        if not folha_id_input:
            return
        folha = servico.buscar_por_id(folha_id_input.strip())
        if not folha:
            exibir_erro("Folha nao encontrada com esse ID.")
            return

    if not folha:
        exibir_erro("Nao foi possivel recuperar a folha.")
        return

    if folha.get("excluida"):
        exibir_aviso("Esta folha ja esta marcada como excluida (soft delete).")
        return

    # Verificar se a folha ja foi enviada
    ja_enviada = False
    try:
        ja_enviada = servico.verificar_folha_enviada(str(folha.get("_id")))
    except Exception as e:
        logger.debug(f"Erro ao verificar envio da folha: {e}")

    nome_func = (folha.get("folha_data", {}) or {}).get("nome_funcionario", "N/A")
    mes_ref = folha.get("mes_referencia", "")

    if ja_enviada:
        exibir_aviso(
            f"⚠ Esta folha de {nome_func} ({mes_ref}) ja possui ENVIO registrado.\n"
            "A exclusao sera feita como SOFT DELETE: o registro da folha e o historico\n"
            "de envio serao PRESERVADOS no banco, porem a folha deixara de aparecer\n"
            "nas listagens/buscas padrao."
        )
        confirmar = pedir_confirmacao("Deseja marcar a folha como excluida mesmo assim?", padrao=False)
        if not confirmar:
            exibir_info("Exclusao cancelada.")
            return
    else:
        confirmar = pedir_confirmacao(
            f"Marcar a folha de {nome_func} ({mes_ref}) como EXCLUIDA?",
            padrao=False,
        )
        if not confirmar:
            exibir_info("Exclusao cancelada.")
            return

    motivo = pedir_texto("Motivo da exclusao (opcional):", obrigatorio=False)

    resultado = servico.marcar_excluida(str(folha.get("_id")), motivo=motivo)
    if resultado:
        exibir_sucesso(f"Folha de {nome_func} ({mes_ref}) marcada como EXCLUIDA (soft delete).")
        exibir_info("O registro permanece no banco com historico e envios preservados.")
    else:
        exibir_erro("Falha ao marcar a folha como excluida.")


def _editar_folha_gerada() -> None:
    """Acao 4: Editar folha ja gerada (recalcula totais, regenera PDF, incrementa versao)."""
    servico = _obter_servico_folha()
    if not servico:
        exibir_erro("Servico de folha de ponto indisponivel (MongoDB?).")
        return

    exibir_painel(
        "[bold]Editar folha de ponto ja gerada.[/bold]\n"
        "Ao salvar: os TOTAIS serao RECALCULADOS, o PDF sera REGENERADO\n"
        "automaticamente e a VERSÃO sera incrementada (com historico).",
        titulo="EDITAR FOLHA GERADA",
        estilo_borda="yellow",
    )

    opcao = pedir_selecao(
        "Como deseja localizar a folha para editar?",
        ["Buscar por nome do funcionario", "Informar ID da folha"],
    )

    folha = None

    if opcao is None:
        return

    if "Buscar por nome" in (opcao or ""):
        folhas = _buscar_folhas_por_nome()
        if not folhas:
            exibir_info("Nenhuma folha encontrada.")
            return
        opcoes = [
            f"{f.get('folha_data', {}).get('nome_funcionario', 'N/A')} - {f.get('mes_referencia', '')} ({f.get('status', '')})"
            for f in folhas
        ]
        escolha = pedir_selecao("Folhas encontradas:", opcoes)
        if escolha is None:
            return
        idx = opcoes.index(escolha)
        folha_id = folhas[idx].get("_id")
        if folha_id:
            folha = servico.buscar_por_id(str(folha_id))
    else:
        folha_id_input = pedir_texto("ID da folha (ObjectId):", obrigatorio=True)
        if not folha_id_input:
            return
        folha = servico.buscar_por_id(folha_id_input.strip())
        if not folha:
            exibir_erro("Folha nao encontrada com esse ID.")
            return

    if not folha:
        exibir_erro("Nao foi possivel recuperar a folha.")
        return

    if folha.get("excluida"):
        exibir_erro("Esta folha esta EXCLUIDA (soft delete). Edicao bloqueada.")
        return

    # Aviso se ja enviada (rastreabilidade preservada via versao/historico)
    ja_enviada = False
    try:
        ja_enviada = servico.verificar_folha_enviada(str(folha.get("_id")))
    except Exception as e:
        logger.debug(f"Erro ao verificar envio da folha: {e}")
    if ja_enviada:
        exibir_aviso(
            "Esta folha ja possui ENVIO registrado. A edicao sera rastreada\n"
            "(nova versao + historico) e o PDF sera regenerado. Considere\n"
            "re-enviar a folha corrigida se necessario."
        )

    _exibir_dados_folha_existente(folha, buscar_funcionario(folha.get("funcionario_id")) or {})

    # Coletar edicoes de dias
    exibir_info("Informe as correcoes dia a dia (ENTER em um campo mantem o valor atual).")
    exibir_info("Digite 'sair' no numero do dia para concluir.")

    dias_editados = []
    folha_data = folha.get("folha_data", {}) or {}
    dias_existentes = folha_data.get("dias", []) or []
    mapa_dias = {}
    for dia in dias_existentes:
        if isinstance(dia, dict):
            mapa_dias[dia.get("numero_dia")] = dia
        else:
            mapa_dias[getattr(dia, "numero_dia", None)] = dia

    while True:
        dia_input = pedir_texto(
            "Numero do dia a editar (1-31) ou 'sair':",
            obrigatorio=False,
        )
        if not dia_input:
            continue
        if dia_input.strip().lower() == "sair":
            break
        try:
            numero = int(dia_input.strip())
        except ValueError:
            exibir_aviso("Numero de dia invalido.")
            continue

        dia_atual = mapa_dias.get(numero, {}) or {}
        if not isinstance(dia_atual, dict):
            dia_atual = {
                "hora_entrada": getattr(dia_atual, "hora_entrada", None),
                "hora_saida": getattr(dia_atual, "hora_saida", None),
                "hora_intervalo_inicio": getattr(dia_atual, "hora_intervalo_inicio", None),
                "hora_intervalo_fim": getattr(dia_atual, "hora_intervalo_fim", None),
                "tipo_dia": getattr(dia_atual, "tipo_dia", None),
                "observacoes": getattr(dia_atual, "observacoes", None),
            }

        def _valor_atual(campo):
            val = dia_atual.get(campo)
            if hasattr(val, "value"):
                return val.value
            return val

        entrada = pedir_texto(
            f"Hora entrada dia {numero} (atual: {_valor_atual('hora_entrada') or '-'}):",
            obrigatorio=False,
        )
        saida = pedir_texto(
            f"Hora saida dia {numero} (atual: {_valor_atual('hora_saida') or '-'}):",
            obrigatorio=False,
        )
        intervalo_inicio = pedir_texto(
            f"Inicio intervalo dia {numero} (atual: {_valor_atual('hora_intervalo_inicio') or '-'}):",
            obrigatorio=False,
        )
        intervalo_fim = pedir_texto(
            f"Fim intervalo dia {numero} (atual: {_valor_atual('hora_intervalo_fim') or '-'}):",
            obrigatorio=False,
        )
        observacoes = pedir_texto(
            f"Observacoes dia {numero} (atual: {_valor_atual('observacoes') or '-'}):",
            obrigatorio=False,
        )

        tipo_opcao = pedir_selecao(
            f"Tipo do dia {numero} (atual: {_valor_atual('tipo_dia') or 'NORMAL'}):",
            ["Manter atual", "NORMAL", "FERIADO", "FALTA", "ATESTADO", "FOLGA", "SÁBADO", "DOMINGO", "LICENÇA", "FÉRIAS", "COMPENSAÇÃO"],
        )
        tipo_dia = None
        if tipo_opcao and tipo_opcao != "Manter atual":
            tipo_dia = tipo_opcao

        edicao = {"numero_dia": numero}
        limpar_campos = []
        # Empty string = intenção de limpar o campo
        if entrada is not None:
            if entrada.strip() == "":
                limpar_campos.append("hora_entrada")
            else:
                edicao["hora_entrada"] = entrada.strip()
        if saida is not None:
            if saida.strip() == "":
                limpar_campos.append("hora_saida")
            else:
                edicao["hora_saida"] = saida.strip()
        if intervalo_inicio is not None:
            if intervalo_inicio.strip() == "":
                limpar_campos.append("hora_intervalo_inicio")
            else:
                edicao["hora_intervalo_inicio"] = intervalo_inicio.strip()
        if intervalo_fim is not None:
            if intervalo_fim.strip() == "":
                limpar_campos.append("hora_intervalo_fim")
            else:
                edicao["hora_intervalo_fim"] = intervalo_fim.strip()
        if observacoes is not None:
            if observacoes.strip() == "":
                limpar_campos.append("observacoes")
            else:
                edicao["observacoes"] = observacoes.strip()
        if tipo_dia:
            edicao["tipo_dia"] = tipo_dia

        if limpar_campos:
            edicao["limpar_campos"] = limpar_campos
        if len(edicao) > 1 or limpar_campos:
            dias_editados.append(edicao)
            exibir_sucesso(f"Dia {numero} registrado para edicao.")
        else:
            exibir_info("Nenhuma alteracao informada para esse dia.")

    if not dias_editados:
        exibir_aviso("Nenhuma edicao informada. Operacao cancelada.")
        return

    confirmar = pedir_confirmacao(
        "Confirmar edicao? (totais serao recalculados e o PDF regenerado)",
        padrao=False,
    )
    if not confirmar:
        exibir_info("Edicao cancelada.")
        return

    fp = _criar_instancia_folha_ponto()
    resultado = fp.editar_folha(
        folha_id=str(folha.get("_id")),
        dias_editados=dias_editados,
        atualizar_pdf=True,
    )

    if resultado and resultado.get("status") == "sucesso":
        exibir_sucesso(f"Folha editada com sucesso (versao {resultado.get('versao')}).")
        totais = resultado.get("totais", {}) or {}
        exibir_info(
            f"Totais recalculados: {totais.get('total_horas_mes', '-')}h | "
            f"faltas: {totais.get('total_faltas', 0)} | "
            f"feriados: {totais.get('total_feriados', 0)}"
        )
        if resultado.get("caminho_pdf"):
            exibir_sucesso(f"PDF regenerado: {resultado['caminho_pdf']}")
        else:
            exibir_aviso("PDF nao foi regenerado (verifique logs).")
    else:
        motivo = (resultado or {}).get("motivo", "")
        exibir_erro(f"Falha ao editar a folha. {motivo}")


def _gerenciar_folhas_geradas() -> None:
    """Submenu GERENCIAR FOLHAS GERADAS (visualizar/buscar/excluir/editar)."""
    logger.debug("Abrindo menu Gerenciar Folhas Geradas")
    (
        MenuBuilder("GERENCIAR FOLHAS GERADAS", ICONES["config"])
        .adicionar("(1) Visualizar uma folha ja gerada", _visualizar_folha_gerada, ICONES["listar"])
        .adicionar("(2) Buscar folha por nome do funcionario", _buscar_folha_por_nome_acao, ICONES["buscar"])
        .adicionar("(3) Excluir folha (soft delete)", _excluir_folha_gerada, ICONES["excluir"])
        .adicionar("(4) Editar folha gerada", _editar_folha_gerada, ICONES["editar"])
        .com_voltar("Voltar ao Menu de Folha de Ponto")
        .executar()
    )


# =====================================================================
# MENU PRINCIPAL
# =====================================================================


def Interface_Folha_de_Ponto() -> None:
    """Menu principal de operacoes com Folha de Ponto."""
    logger.debug("Iniciando a interface para operacoes com Folha de Ponto")
    (
        MenuBuilder("OPERACOES COM FOLHA DE PONTO", ICONES["folha_ponto"])
        .adicionar("Gerar Folha de Ponto (PDF + MongoDB)", _gerar_folha_ponto, ICONES["processar"])
        .adicionar("Processar PDFs Preenchidos com IA", _processar_pdfs_interface, ICONES["ia"])
        .separador()
        .adicionar("Ler/Exportar DataFrame", _ler_folha_de_ponto, ICONES["listar"])
        .adicionar("Gerenciar Folhas Geradas", _gerenciar_folhas_geradas, ICONES["config"])
        .adicionar("Enviar Folhas de Ponto (E-mail/WhatsApp)", _abrir_envio_folha_ponto, ICONES["enviar"])
        .com_voltar("Voltar ao Menu Principal")
        .executar()
    )
