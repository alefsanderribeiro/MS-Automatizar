"""Interface para operações com Holerites."""

from pathlib import Path

from src.holerite import Holerite
from src.services.cache_ocr_service import cache_ocr
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
from src.interface.core.validators import validar_mes_ano


def _cache_disponivel() -> bool:
    """Verifica se o cache OCR está disponível."""
    return bool(cache_ocr and cache_ocr.disponivel)


def Interface_Holerite() -> None:
    """Menu principal de operações com holerites."""
    (
        MenuBuilder("OPERACOES COM HOLERITE", ICONES["holerite"])
        .adicionar("Renomear arquivo(s)", _processar_renomear_holerite, ICONES["editar"])
        .adicionar("Processar PDFs com IA (Gemini)", _processar_pdfs_gemini, ICONES["ia"])
        .adicionar("Enviar Holerites", _abrir_menu_envio, ICONES["enviar"])
        .adicionar("Listar Holerites no MongoDB", _listar_holerites, ICONES["listar"])
        .separador()
        .adicionar("Estatisticas do Cache OCR", _exibir_stats_cache, ICONES["estatistica"])
        .adicionar(
            "Limpar Cache OCR (antigos)",
            _limpar_cache_antigo,
            ICONES["excluir"],
            visivel=_cache_disponivel,
        )
        .adicionar(
            "Limpar todo o Cache OCR",
            _limpar_todo_cache,
            ICONES["excluir"],
            visivel=_cache_disponivel,
        )
        .com_voltar("Voltar ao Menu Principal")
        .executar()
    )


def _processar_renomear_holerite() -> None:
    """Processa renomeacao de holerites com cache."""
    try:
        diretorio = pedir_texto("Informe o diretorio do(s) arquivo(s):")
        if not diretorio:
            return

        mes_ano = pedir_texto(
            "Mes e ano (ex: 01.2025) ou deixe em branco:",
            obrigatorio=False,
            validador=validar_mes_ano,
            erro_validacao="Formato invalido! Use MM.AAAA (ex: 01.2025)",
        )

        # Inicializar e processar
        console.print("\n[info]Processando arquivos...[/info]")
        hl = Holerite(diretório=diretorio)
        processados, erros = hl.renomear_arquivos(mês_ano=mes_ano)

        exibir_resultado(
            "RESULTADO DA RENOMEACAO",
            sucesso=processados,
            erros=erros,
        )

    except Exception as e:
        logger.error(f"Erro ao processar holerites: {e}")
        exibir_erro(f"Erro: {e}")


def _processar_pdfs_gemini() -> None:
    """Processa PDFs de holerites com extracao Gemini AI."""
    try:
        from src.processadores.holerite_processador import HoleriteProcessador

        exibir_painel(
            "[bold]Este processo ira:[/bold]\n"
            "  * Extrair dados dos holerites usando IA (Gemini)\n"
            "  * Vincular ou criar funcionarios no MongoDB\n"
            "  * Salvar holerites processados\n\n"
            f"[yellow]Nota:[/yellow] Apenas PDFs que começam com '{HoleriteProcessador.PREFIXO_HOLERITE}' serão processados",
            titulo="PROCESSAMENTO DE PDFs COM GEMINI AI",
            estilo_borda="blue",
        )

        processador = HoleriteProcessador()

        if not processador.disponivel:
            exibir_erro("Processador nao disponivel!")
            exibir_info("Verifique se Gemini API e MongoDB estao configurados.")
            return

        caminho_input = pedir_texto("Caminho do diretorio ou arquivo PDF:")
        if not caminho_input:
            return

        caminho = Path(caminho_input)

        if not caminho.exists():
            exibir_erro(f"Caminho nao encontrado: {caminho}")
            return

        # Validar arquivo ou diretorio
        if caminho.is_file():
            # Processar arquivo individual
            if not processador._arquivo_eh_holerite_valido(caminho):
                exibir_erro(f"Arquivo '{caminho.name}' nao eh um holerite valido!")
                exibir_info(f"Deve ser um PDF que comeca com '{HoleriteProcessador.PREFIXO_HOLERITE}'")
                return

            exibir_info(f"Processando arquivo: {caminho.name}")

            if not pedir_confirmacao("Deseja continuar?"):
                exibir_aviso("Operacao cancelada.")
                return

            console.print("\n[info]Processando arquivo...[/info]")
            console.print("-" * 60)

            resultado = processador.processar_arquivo(caminho)

            if resultado.sucesso:
                console.print(f"\n[green]{ICONES['sucesso']} Processado com sucesso[/green]")
                if resultado.funcionario_criado:
                    console.print(f"[info]{ICONES['info']} Novo funcionario criado[/info]")
                console.print(f"Holerite ID: {resultado.holerite_id}")
            else:
                console.print(f"\n[red]{ICONES['erro']} Erro: {resultado.erro}[/red]")

            for msg in resultado.mensagens:
                console.print(f"* {msg}")

            exibir_resultado(
                "RESUMO DO PROCESSAMENTO",
                sucesso=1 if resultado.sucesso else 0,
                erros=0 if resultado.sucesso else 1,
                detalhes=[] if resultado.sucesso else [resultado.erro],
            )

        else:
            # Processar diretorio
            exibir_info(f"Processando diretorio: {caminho}")

            if not pedir_confirmacao("Deseja continuar?"):
                exibir_aviso("Operacao cancelada.")
                return

            console.print("\n[info]Processando arquivos...[/info]")
            console.print("-" * 60)

            resultados = processador.processar_diretorio(caminho)

            if not resultados:
                exibir_aviso(f"Nenhum holerite valido foi encontrado ou processado.")
                return

            sucesso = sum(1 for r in resultados if r.sucesso)
            falhas = len(resultados) - sucesso
            detalhes = [r.erro for r in resultados if r.erro]

            exibir_resultado(
                "RESUMO DO PROCESSAMENTO",
                sucesso=sucesso,
                erros=falhas,
                detalhes=detalhes if detalhes else None,
            )

    except ImportError as e:
        logger.error(f"Erro ao importar processador: {e}")
        exibir_erro("Modulo de processamento nao disponivel!")
    except Exception as e:
        logger.error(f"Erro no processamento: {e}")
        exibir_erro(f"Erro: {e}")


def _abrir_menu_envio() -> None:
    """Abre o menu de envio de holerites."""
    try:
        from src.interface.interface_envio_holerite import iniciar_menu_envio_holerite
        iniciar_menu_envio_holerite()
    except ImportError as e:
        logger.error(f"Erro ao importar menu de envio: {e}")
        exibir_erro("Modulo de envio de holerites nao disponivel!")
        exibir_info(f"Detalhes: {e}")
    except Exception as e:
        logger.error(f"Erro ao abrir menu de envio: {e}")
        exibir_erro(f"Erro: {e}")


def _listar_holerites() -> None:
    """Lista holerites salvos no MongoDB."""
    try:
        from src.services.holerite_service import holerite_service

        if not holerite_service.disponivel:
            exibir_erro("Servico de holerites nao disponivel!")
            exibir_info("Verifique a conexao com MongoDB.")
            return

        # Filtro
        opcao_filtro = pedir_selecao(
            "Filtro de busca:",
            ["Listar todos", "Filtrar por competencia (MM/AAAA)", "Filtrar por funcionario"],
        )

        if opcao_filtro is None:
            return

        filtros = {}

        if "competencia" in (opcao_filtro or "").lower():
            competencia = pedir_texto("Competencia (MM/AAAA):", obrigatorio=False)
            if competencia:
                filtros["competencia"] = competencia

        elif "funcionario" in (opcao_filtro or "").lower():
            nome = pedir_texto("Nome do funcionario:", obrigatorio=False)
            if nome:
                filtros["funcionario_nome"] = nome

        limite = pedir_inteiro("Quantidade maxima de resultados:", padrao=20, minimo=1, maximo=500)
        if limite is None:
            limite = 20

        # Buscar holerites
        holerites = holerite_service.listar_todos(limite=limite, **filtros)

        if not holerites:
            exibir_info("Nenhum holerite encontrado com os filtros informados.")
            return

        # Montar tabela
        dados = []
        for h in holerites:
            nome = h.get("funcionario_nome", "Desconhecido")
            competencia = h.get("competencia", "N/A")
            status = h.get("status", "N/A")
            salario = h.get("salario_liquido", 0)
            salario_fmt = f"R$ {salario:,.2f}" if salario else "-"
            dados.append([nome, competencia, status, salario_fmt])

        exibir_tabela(
            f"Holerites Encontrados ({len(holerites)})",
            ["Funcionario", "Competencia", "Status", "Salario Liq."],
            dados,
        )

    except Exception as e:
        logger.error(f"Erro ao listar holerites: {e}")
        exibir_erro(f"Erro: {e}")


def _exibir_stats_cache() -> None:
    """Exibe estatisticas do cache OCR."""
    try:
        if not _cache_disponivel():
            exibir_erro("Cache OCR nao esta disponivel ou MongoDB nao esta conectado.")
            exibir_info("Verifique se MongoDB esta rodando.")
            return

        stats = cache_ocr.obter_estatisticas()

        conteudo = (
            f"[bold]Status:[/bold] {stats.get('status', 'Desconhecido')}\n"
            f"[bold]Total de documentos:[/bold] {stats.get('total_documentos', 0)}\n"
            f"[bold]Tamanho total:[/bold] {stats.get('tamanho_total_mb', 0):.2f} MB\n"
            f"[bold]Banco de dados:[/bold] {stats.get('banco_dados', 'N/A')}\n"
            f"[bold]Colecao:[/bold] {stats.get('colecao', 'N/A')}\n"
            f"[bold]Arquivos unicos:[/bold] {stats.get('arquivos_unicos', 0)}\n"
            f"[bold]Endereco MongoDB:[/bold] {stats.get('mongo_uri', 'N/A')}"
        )

        exibir_painel(conteudo, titulo="ESTATISTICAS DO CACHE OCR", estilo_borda="blue")

        # Últimos documentos
        console.print(f"\n[subtitulo]Ultimos 5 documentos em cache:[/subtitulo]\n")
        ultimos = cache_ocr.listar_cache(limite=5)

        if ultimos:
            dados = []
            for doc in ultimos:
                resultado_truncado = (
                    doc["resultado_ocr"][:40] + "..."
                    if len(doc["resultado_ocr"]) > 40
                    else doc["resultado_ocr"]
                )
                dados.append([doc["nome_arquivo"], resultado_truncado, str(doc["data_criacao"])])

            exibir_tabela(
                "Documentos em Cache",
                ["Arquivo", "Resultado OCR", "Data"],
                dados,
            )
        else:
            exibir_info("Nenhum documento em cache.")

    except Exception as e:
        logger.error(f"Erro ao exibir estatisticas: {e}")
        exibir_erro(f"Erro ao exibir estatisticas: {e}")


def _limpar_cache_antigo() -> None:
    """Limpa documentos antigos do cache."""
    try:
        if not _cache_disponivel():
            exibir_erro("Cache OCR nao esta disponivel.")
            return

        dias = pedir_inteiro("Quantos dias manter (ex: 30):", minimo=1)
        if dias is None:
            return

        if not pedir_confirmacao(f"Limpar documentos com mais de {dias} dias?"):
            exibir_aviso("Operacao cancelada.")
            return

        removidos = cache_ocr.limpar_cache_antigo(dias=dias)

        exibir_resultado(
            "CACHE LIMPO",
            sucesso=removidos,
            erros=0,
            detalhes=[f"Mantendo documentos mais novos que {dias} dias"],
        )

    except Exception as e:
        logger.error(f"Erro ao limpar cache: {e}")
        exibir_erro(f"Erro ao limpar cache: {e}")


def _limpar_todo_cache() -> None:
    """Limpa todo o cache OCR."""
    try:
        if not _cache_disponivel():
            exibir_erro("Cache OCR nao esta disponivel.")
            return

        exibir_aviso("Esta acao ira REMOVER TODOS os documentos do cache!")

        if not pedir_confirmacao("Tem certeza que deseja limpar TODO o cache?"):
            exibir_aviso("Operacao cancelada.")
            return

        cache_ocr.limpar_tudo()

        exibir_sucesso("Cache completamente limpo! Todos os documentos foram removidos.")

    except Exception as e:
        logger.error(f"Erro ao limpar cache completo: {e}")
        exibir_erro(f"Erro ao limpar cache: {e}")
