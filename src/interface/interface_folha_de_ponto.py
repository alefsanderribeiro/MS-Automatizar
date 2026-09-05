"""Interface para operacoes com Folha de Ponto."""

from datetime import date
from typing import Optional, List, Dict, Any

from src.folha_de_ponto import Folha_de_Ponto
# Importar funcoes utilitarias centralizadas
from src.utils.logger_config_v2 import get_logger

# Logger do módulo
logger = get_logger("interface")

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
        f"[bold]Periodo:[/bold]            {folha_data.get('data_inicio', 'N/A')} a {folha_data.get('data_fim', 'N/A')}\n"
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
            data_dia = dia.get("data", "N/A")
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
        "Data (YYYY-MM-DD) ou ENTER para data atual:",
        obrigatorio=False,
    )
    try:
        data = date.fromisoformat(data_str) if data_str else date.today()
    except Exception:
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
        .adicionar("Enviar Folhas de Ponto (E-mail/WhatsApp)", _abrir_envio_folha_ponto, ICONES["enviar"])
        .com_voltar("Voltar ao Menu Principal")
        .executar()
    )
