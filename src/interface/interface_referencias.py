"""
Interface interativa para gerenciar Referências (Contratos, Horários, Funções, Diretórios, Feriados)
"""

from src.comandos.referencias import (
    listar_contratos, adicionar_contrato_interativo, inativar_contrato,
    listar_horarios, adicionar_horario_interativo, inativar_horario,
    listar_funcoes, adicionar_funcao_interativo, inativar_funcao,
    exibir_estatisticas
)
from src.comandos.diretorios import (
    listar_diretorios, adicionar_diretorio_interativo, inativar_diretorio,
    criar_diretorio_para_contrato, atualizar_diretorio_interativo,
    exibir_estatisticas_diretorios, criar_diretorios_todos_contratos
)
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
from src.utils.logger_config import logger


def Interface_Referencias():
    """Interface principal de Referências"""
    (
        MenuBuilder("GERENCIAMENTO DE REFERENCIAS", ICONES["config"])
        .adicionar("Gerenciar Contratos", submenu_contratos, ICONES["contrato"])
        .adicionar("Gerenciar Horarios", submenu_horarios, ICONES["horario"])
        .adicionar("Gerenciar Funcoes", submenu_funcoes, ICONES["funcao"])
        .adicionar("Gerenciar Diretorios", submenu_diretorios, ICONES["diretorio"])
        .adicionar("Gerenciar Feriados", submenu_feriados, ICONES["feriado"])
        .separador()
        .adicionar("Exibir Estatisticas", exibir_estatisticas, ICONES["estatistica"])
        .com_voltar("Voltar ao Menu Principal")
        .executar()
    )


def submenu_contratos():
    """Submenu para gerenciar contratos"""
    (
        MenuBuilder("GERENCIAMENTO DE CONTRATOS", ICONES["contrato"])
        .adicionar("Listar Contratos", submenu_listar_contratos, ICONES["listar"])
        .adicionar("Adicionar Contrato", adicionar_contrato_interativo, ICONES["criar"])
        .adicionar("Inativar Contrato", _inativar_contrato, ICONES["excluir"])
        .com_voltar("Voltar")
        .executar()
    )


def submenu_horarios():
    """Submenu para gerenciar horários"""
    (
        MenuBuilder("GERENCIAMENTO DE HORARIOS", ICONES["horario"])
        .adicionar("Listar Horarios", submenu_listar_horarios, ICONES["listar"])
        .adicionar("Adicionar Horario", adicionar_horario_interativo, ICONES["criar"])
        .adicionar("Inativar Horario", _inativar_horario, ICONES["excluir"])
        .com_voltar("Voltar")
        .executar()
    )


def submenu_funcoes():
    """Submenu para gerenciar funções"""
    (
        MenuBuilder("GERENCIAMENTO DE FUNCOES", ICONES["funcao"])
        .adicionar("Listar Funcoes", submenu_listar_funcoes, ICONES["listar"])
        .adicionar("Adicionar Funcao", adicionar_funcao_interativo, ICONES["criar"])
        .adicionar("Inativar Funcao", _inativar_funcao, ICONES["excluir"])
        .com_voltar("Voltar")
        .executar()
    )


def submenu_diretorios():
    """Submenu para gerenciar diretórios"""
    (
        MenuBuilder("GERENCIAMENTO DE DIRETORIOS", ICONES["diretorio"])
        .adicionar("Listar Diretorios", submenu_listar_diretorios, ICONES["listar"])
        .adicionar("Adicionar Diretorio", adicionar_diretorio_interativo, ICONES["criar"])
        .adicionar("Atualizar Diretorio", atualizar_diretorio_interativo, ICONES["editar"])
        .adicionar("Inativar Diretorio", _inativar_diretorio, ICONES["excluir"])
        .separador()
        .adicionar("Criar Diretorio para Contrato", criar_diretorio_para_contrato, ICONES["criar"])
        .adicionar("Criar Diretorios para TODOS os Contratos", _criar_diretorios_todos, ICONES["criar"])
        .separador()
        .adicionar("Estatisticas de Diretorios", exibir_estatisticas_diretorios, ICONES["estatistica"])
        .com_voltar("Voltar")
        .executar()
    )


def submenu_listar_contratos():
    """Submenu para listar contratos com opções"""
    opcao = pedir_selecao(
        "Listar Contratos:",
        [
            "Todos os contratos",
            "Apenas contratos ativos",
            "Formato JSON",
        ],
    )

    if not opcao:
        return

    try:
        if "Todos" in opcao:
            _listar_contratos(apenas_ativos=False)
            pausar()
        elif "ativos" in opcao:
            _listar_contratos(apenas_ativos=True)
            pausar()
        elif "JSON" in opcao:
            listar_contratos(apenas_ativos=False, formato="json")
            pausar()
    except Exception as e:
        logger.error(f"Erro ao listar contratos: {e}")
        exibir_erro(f"Erro ao listar contratos: {e}")
        pausar()


def submenu_listar_horarios():
    """Submenu para listar horários com opções"""
    opcao = pedir_selecao(
        "Listar Horarios:",
        [
            "Todos os horarios",
            "Apenas horarios ativos",
            "Formato JSON",
        ],
    )

    if not opcao:
        return

    try:
        if "Todos" in opcao:
            _listar_horarios(apenas_ativos=False)
            pausar()
        elif "ativos" in opcao:
            _listar_horarios(apenas_ativos=True)
            pausar()
        elif "JSON" in opcao:
            listar_horarios(apenas_ativos=False, formato="json")
            pausar()
    except Exception as e:
        logger.error(f"Erro ao listar horarios: {e}")
        exibir_erro(f"Erro ao listar horarios: {e}")
        pausar()


def submenu_listar_funcoes():
    """Submenu para listar funções com opções"""
    opcao = pedir_selecao(
        "Listar Funcoes:",
        [
            "Todas as funcoes",
            "Apenas funcoes ativas",
            "Filtrar por categoria",
            "Formato JSON",
        ],
    )

    if not opcao:
        return

    try:
        if "Todas" in opcao:
            _listar_funcoes(apenas_ativos=False)
            pausar()
        elif "ativas" in opcao:
            _listar_funcoes(apenas_ativos=True)
            pausar()
        elif "categoria" in opcao:
            categoria = pedir_texto("Digite a categoria (funcao geral):")
            if categoria:
                _listar_funcoes(apenas_ativos=False, categoria=categoria)
            else:
                exibir_aviso("Categoria nao pode ser vazia")
            pausar()
        elif "JSON" in opcao:
            listar_funcoes(apenas_ativos=False, formato="json")
            pausar()
    except Exception as e:
        logger.error(f"Erro ao listar funcoes: {e}")
        exibir_erro(f"Erro ao listar funcoes: {e}")
        pausar()


def submenu_listar_diretorios():
    """Submenu para listar diretórios com opções"""
    opcao = pedir_selecao(
        "Listar Diretorios:",
        [
            "Todos os diretorios",
            "Apenas diretorios ativos",
            "Formato JSON",
        ],
    )

    if not opcao:
        return

    try:
        if "Todos" in opcao:
            _listar_diretorios(apenas_ativos=False)
            pausar()
        elif "ativos" in opcao:
            _listar_diretorios(apenas_ativos=True)
            pausar()
        elif "JSON" in opcao:
            listar_diretorios(apenas_ativos=False, formato="json")
            pausar()
    except Exception as e:
        logger.error(f"Erro ao listar diretorios: {e}")
        exibir_erro(f"Erro ao listar diretorios: {e}")
        pausar()


def _inativar_contrato():
    """Inativa um contrato"""
    try:
        contrato_id = pedir_texto("Digite o ID do contrato (ObjectId):")
        if not contrato_id:
            exibir_aviso("ID nao pode ser vazio")
            return

        inativar_contrato(contrato_id)
        pausar()
    except Exception as e:
        logger.error(f"Erro ao inativar contrato: {e}")
        exibir_erro(f"Erro ao inativar contrato: {e}")
        pausar()


def _inativar_horario():
    """Inativa um horário"""
    try:
        horario_id = pedir_texto("Digite o ID do horario (ObjectId):")
        if not horario_id:
            exibir_aviso("ID nao pode ser vazio")
            return

        inativar_horario(horario_id)
        pausar()
    except Exception as e:
        logger.error(f"Erro ao inativar horario: {e}")
        exibir_erro(f"Erro ao inativar horario: {e}")
        pausar()


def _inativar_funcao():
    """Inativa uma função"""
    try:
        funcao_id = pedir_texto("Digite o ID da funcao (ObjectId):")
        if not funcao_id:
            exibir_aviso("ID nao pode ser vazio")
            return

        inativar_funcao(funcao_id)
        pausar()
    except Exception as e:
        logger.error(f"Erro ao inativar funcao: {e}")
        exibir_erro(f"Erro ao inativar funcao: {e}")
        pausar()


def _inativar_diretorio():
    """Inativa um diretório"""
    try:
        diretorio_id = pedir_texto("Digite o ID do diretorio (ObjectId):")
        if not diretorio_id:
            exibir_aviso("ID nao pode ser vazio")
            return

        inativar_diretorio(diretorio_id)
        pausar()
    except Exception as e:
        logger.error(f"Erro ao inativar diretorio: {e}")
        exibir_erro(f"Erro ao inativar diretorio: {e}")
        pausar()


def _criar_diretorios_todos():
    """Cria diretórios para todos os contratos sem diretório"""
    try:
        if pedir_confirmacao("Criar diretorios para TODOS os contratos sem diretorio?"):
            criar_diretorios_todos_contratos()
        else:
            logger.info("Operacao cancelada")
            exibir_info("Operacao cancelada")
        pausar()
    except Exception as e:
        logger.error(f"Erro ao criar diretorios: {e}")
        exibir_erro(f"Erro ao criar diretorios: {e}")
        pausar()


# ==================== FUNCOES DE LISTAGEM COM RICH TABLE ====================

def _listar_contratos(apenas_ativos: bool = False) -> None:
    """Lista contratos em tabela formatada."""
    from rich.table import Table
    from src.services.contrato_service import ContratoService
    from src.models.contrato_models import StatusContrato

    try:
        service = ContratoService()
        if not service.disponivel:
            exibir_erro("MongoDB nao disponivel")
            return

        contratos = service.listar_ativos() if apenas_ativos else service.listar_todos()

        if not contratos:
            exibir_info("Nenhum contrato cadastrado.")
            return

        tabela = Table(title=f"{ICONES['contrato']} {len(contratos)} contrato(s) cadastrado(s)")
        tabela.add_column("#", style="cyan", no_wrap=True)
        tabela.add_column("Nome", style="white")
        tabela.add_column("Status", style="yellow")
        tabela.add_column("Numero", style="white")
        tabela.add_column("Orgao", style="white")
        tabela.add_column("Localidade", style="white")

        for idx, c in enumerate(contratos, 1):
            status_val = c.get("status")
            if isinstance(status_val, str):
                status_val = status_val.lower()
            is_ativo = status_val == StatusContrato.ATIVO.value
            status = "[green]ATIVO[/green]" if is_ativo else "[red]INATIVO[/red]"
            auto = " [dim][AUTO][/dim]" if c.get("auto_criado") else ""

            tabela.add_row(
                str(idx),
                f"{c.get('nome', '')}{auto}",
                status,
                c.get("numero_contrato", "-"),
                c.get("orgao", "-"),
                c.get("localidade", "-"),
            )

        console.print(tabela)
    except Exception as e:
        logger.error(f"Erro ao listar contratos: {e}")
        exibir_erro(f"Erro ao listar contratos: {e}")


def _listar_horarios(apenas_ativos: bool = False) -> None:
    """Lista horarios em tabela formatada."""
    from rich.table import Table
    from src.services.horario_service import HorarioService
    from src.models.horario_models import StatusHorario

    try:
        service = HorarioService()
        if not service.disponivel:
            exibir_erro("MongoDB nao disponivel")
            return

        horarios = service.listar_ativos() if apenas_ativos else service.listar_todos()

        if not horarios:
            exibir_info("Nenhum horario cadastrado.")
            return

        tabela = Table(title=f"{ICONES['horario']} {len(horarios)} horario(s) cadastrado(s)")
        tabela.add_column("#", style="cyan", no_wrap=True)
        tabela.add_column("Descricao", style="white")
        tabela.add_column("Status", style="yellow")
        tabela.add_column("Dias/Mes", style="green", justify="center")
        tabela.add_column("Entrada 1", style="white", justify="center")
        tabela.add_column("Saida 1", style="white", justify="center")
        tabela.add_column("Entrada 2", style="white", justify="center")
        tabela.add_column("Saida 2", style="white", justify="center")
        tabela.add_column("Total", style="cyan", justify="center")

        for idx, h in enumerate(horarios, 1):
            status_val = h.get("status", StatusHorario.ATIVO.value)
            is_ativo = status_val == StatusHorario.ATIVO.value
            status = "[green]ATIVO[/green]" if is_ativo else "[red]INATIVO[/red]"
            auto = " [dim][AUTO][/dim]" if h.get("auto_criado") else ""

            tabela.add_row(
                str(idx),
                f"{h.get('descricao', '')}{auto}",
                status,
                str(h.get("dias_trabalho_mes", "-")),
                h.get("entrada1", "-") or "-",
                h.get("saida1", "-") or "-",
                h.get("entrada2", "-") or "-",
                h.get("saida2", "-") or "-",
                h.get("total_horas", "-") or "-",
            )

        console.print(tabela)
    except Exception as e:
        logger.error(f"Erro ao listar horarios: {e}")
        exibir_erro(f"Erro ao listar horarios: {e}")


def _listar_funcoes(apenas_ativos: bool = False, categoria: str | None = None) -> None:
    """Lista funcoes em tabela formatada."""
    from rich.table import Table
    from src.services.funcao_service import FuncaoService
    from src.models.funcao_models import StatusFuncao

    try:
        service = FuncaoService()
        if not service.disponivel:
            exibir_erro("MongoDB nao disponivel")
            return

        if categoria:
            funcoes = service.listar_por_categoria(categoria)
        elif apenas_ativos:
            funcoes = service.listar_ativos()
        else:
            funcoes = service.listar_todos()

        if not funcoes:
            exibir_info("Nenhuma funcao cadastrada.")
            return

        tabela = Table(title=f"{ICONES['funcao']} {len(funcoes)} funcao(oes) cadastrada(s)")
        tabela.add_column("#", style="cyan", no_wrap=True)
        tabela.add_column("Nome", style="white")
        tabela.add_column("Status", style="yellow")
        tabela.add_column("Categoria", style="green")

        for idx, f in enumerate(funcoes, 1):
            status_val = f.get("status", StatusFuncao.ATIVO.value)
            is_ativo = status_val == StatusFuncao.ATIVO.value
            status = "[green]ATIVO[/green]" if is_ativo else "[red]INATIVO[/red]"
            auto = " [dim][AUTO][/dim]" if f.get("auto_criado") else ""

            tabela.add_row(
                str(idx),
                f"{f.get('nome', '')}{auto}",
                status,
                f.get("funcao_geral", "-") or "-",
            )

        console.print(tabela)
    except Exception as e:
        logger.error(f"Erro ao listar funcoes: {e}")
        exibir_erro(f"Erro ao listar funcoes: {e}")


def _listar_diretorios(apenas_ativos: bool = False) -> None:
    """Lista diretorios em tabela formatada."""
    from rich.table import Table
    from src.services.diretorio_service import DiretorioService
    from src.services.contrato_service import ContratoService
    from src.models.diretorio_models import StatusDiretorio

    try:
        service = DiretorioService()
        if not service.disponivel:
            exibir_erro("MongoDB nao disponivel")
            return

        if apenas_ativos:
            diretorios = service.listar_ativos()
        else:
            resultado = service.listar_todos()
            diretorios = resultado.get("dados", [])

        if not diretorios:
            exibir_info("Nenhum diretorio cadastrado.")
            return

        # Pre-fetch contratos para evitar N+1 queries
        contrato_service = ContratoService()
        todos_contratos = contrato_service.listar_todos() if contrato_service.disponivel else []
        mapa_contratos = {str(c.get("_id")): c.get("nome", "") for c in todos_contratos}

        tabela = Table(title=f"{ICONES['diretorio']} {len(diretorios)} diretorio(s) cadastrado(s)")
        tabela.add_column("#", style="cyan", no_wrap=True)
        tabela.add_column("Nome", style="white")
        tabela.add_column("Status", style="yellow")
        tabela.add_column("Contrato", style="green")
        tabela.add_column("Caminho", style="white")

        for idx, d in enumerate(diretorios, 1):
            status_val = d.get("status", StatusDiretorio.ATIVO.value)
            is_ativo = status_val == StatusDiretorio.ATIVO.value
            status = "[green]ATIVO[/green]" if is_ativo else "[red]INATIVO[/red]"
            auto = " [dim][AUTO][/dim]" if d.get("auto_criado") else ""

            contrato_nome = "-"
            contrato_id = d.get("contrato_id")
            if contrato_id:
                contrato_nome = mapa_contratos.get(str(contrato_id), str(contrato_id))

            tabela.add_row(
                str(idx),
                f"{d.get('nome', '')}{auto}",
                status,
                contrato_nome,
                d.get("caminho_relativo", "-") or "-",
            )

        console.print(tabela)
    except Exception as e:
        logger.error(f"Erro ao listar diretorios: {e}")
        exibir_erro(f"Erro ao listar diretorios: {e}")


# ==================== SUBMENU FERIADOS ====================

def submenu_feriados():
    """Submenu para gerenciar feriados"""
    from src.services.feriado_service import FeriadoService

    servico = FeriadoService()

    if not servico.disponivel:
        exibir_erro("MongoDB nao disponivel para gerenciar feriados")
        pausar()
        return

    (
        MenuBuilder("GERENCIAMENTO DE FERIADOS", ICONES["feriado"])
        .adicionar("Listar feriados", lambda: _listar_feriados(servico), ICONES["listar"])
        .adicionar("Adicionar feriado", lambda: _adicionar_feriado(servico), ICONES["criar"])
        .adicionar("Remover feriado", lambda: _remover_feriado(servico), ICONES["excluir"])
        .separador()
        .adicionar("Importar feriados nacionais (por ano)", lambda: _importar_feriados_nacionais(servico), ICONES["enviar"])
        .adicionar("Importar feriados estaduais RO (por ano)", lambda: _importar_feriados_estaduais_ro(servico), ICONES["enviar"])
        .separador()
        .adicionar("Listar feriados de um mes", lambda: _listar_feriados_mes(servico), ICONES["calendario"])
        .adicionar("Importar feriados do Excel", _importar_feriados_excel, ICONES["excel"])
        .com_voltar("Voltar")
        .executar()
    )


def _listar_feriados(servico):
    """Lista todos os feriados"""
    from datetime import datetime
    from rich.table import Table

    try:
        resultado = servico.listar_todos(limit=500)
        feriados = resultado.get("dados", [])
        total = resultado.get("total", 0)

        if not feriados:
            exibir_info("Nenhum feriado cadastrado.")
            pausar()
            return

        # Criar tabela com rich
        tabela = Table(title=f"{ICONES['feriado']} {total} feriado(s) cadastrado(s)")
        tabela.add_column("#", style="cyan", no_wrap=True)
        tabela.add_column("Data", style="green")
        tabela.add_column("Descricao", style="white")
        tabela.add_column("Tipo", style="yellow")

        for idx, f in enumerate(feriados, 1):
            data = f.get("data")
            if isinstance(data, datetime):
                data_str = data.strftime("%d/%m/%Y")
            else:
                data_str = str(data)[:10]

            descricao = f.get("descricao", "")
            tipo = f.get("tipo", "nacional")

            tabela.add_row(str(idx), data_str, descricao, tipo)

        console.print(tabela)
        pausar()
    except Exception as e:
        logger.error(f"Erro ao listar feriados: {e}")
        exibir_erro(f"Erro ao listar feriados: {e}")
        pausar()


def _adicionar_feriado(servico):
    """Adiciona um novo feriado"""
    from src.models.feriado_models import FeriadoMongoDB, TipoFeriado
    from datetime import date

    try:
        exibir_cabecalho("Adicionar Novo Feriado", ICONES["criar"])

        # Data
        data_str = pedir_texto("Data do feriado (DD/MM/AAAA):")
        if not data_str:
            return

        try:
            partes = data_str.split("/")
            data = date(int(partes[2]), int(partes[1]), int(partes[0]))
        except:
            exibir_erro("Data invalida. Use o formato DD/MM/AAAA")
            pausar()
            return

        # Descrição
        descricao = pedir_texto("Descricao do feriado:")
        if not descricao:
            exibir_erro("Descricao nao pode ser vazia.")
            pausar()
            return

        # Tipo
        tipo_opcao = pedir_selecao(
            "Tipo do feriado:",
            [
                "Nacional",
                "Estadual",
                "Municipal",
                "Ponto Facultativo"
            ]
        )

        if not tipo_opcao:
            return

        tipos_map = {
            "Nacional": TipoFeriado.NACIONAL,
            "Estadual": TipoFeriado.ESTADUAL,
            "Municipal": TipoFeriado.MUNICIPAL,
            "Ponto Facultativo": TipoFeriado.PONTO_FACULTATIVO
        }
        tipo = tipos_map.get(tipo_opcao, TipoFeriado.NACIONAL)

        # UF (para estadual/municipal)
        uf = None
        municipio = None
        if tipo in [TipoFeriado.ESTADUAL, TipoFeriado.MUNICIPAL]:
            uf = pedir_texto("Estado (UF):")
            if uf:
                uf = uf.strip().upper()
            if tipo == TipoFeriado.MUNICIPAL:
                municipio = pedir_texto("Municipio:")

        # Recorrente
        recorrente = pedir_confirmacao("Feriado se repete todo ano?")

        # Criar feriado
        feriado = FeriadoMongoDB(
            data=data,
            descricao=descricao,
            tipo=tipo,
            uf=uf,
            municipio=municipio,
            recorrente=recorrente
        )

        resultado = servico.criar(feriado)
        if resultado:
            exibir_sucesso(f"Feriado criado com sucesso! ID: {resultado}")
        else:
            exibir_erro("Erro ao criar feriado (pode ja existir).")

        pausar()
    except Exception as e:
        logger.error(f"Erro ao adicionar feriado: {e}")
        exibir_erro(f"Erro ao adicionar feriado: {e}")
        pausar()


def _remover_feriado(servico):
    """Remove um feriado"""
    try:
        _listar_feriados(servico)

        id_str = pedir_texto("Digite o ID do feriado para remover (ou numero da lista):")

        if not id_str:
            return

        # Se for número, buscar da lista
        try:
            idx = int(id_str)
            resultado = servico.listar_todos(limit=500)
            feriados = resultado.get("dados", [])
            if 1 <= idx <= len(feriados):
                feriado = feriados[idx - 1]
                feriado_id = str(feriado.get("_id"))
                descricao = feriado.get("descricao", "")
            else:
                exibir_erro("Numero fora do intervalo.")
                pausar()
                return
        except ValueError:
            feriado_id = id_str
            descricao = ""

        if pedir_confirmacao(f"Confirma remocao de '{descricao}'?"):
            if servico.remover(feriado_id):
                exibir_sucesso("Feriado removido com sucesso!")
            else:
                exibir_erro("Erro ao remover feriado.")

        pausar()
    except Exception as e:
        logger.error(f"Erro ao remover feriado: {e}")
        exibir_erro(f"Erro ao remover feriado: {e}")
        pausar()


def _importar_feriados_nacionais(servico):
    """Importa feriados nacionais para um ano"""
    from datetime import date

    try:
        ano_atual = date.today().year
        ano_str = pedir_texto(f"Ano para importar feriados [{ano_atual}]:")

        try:
            ano = int(ano_str) if ano_str else ano_atual
        except ValueError:
            exibir_erro("Ano invalido.")
            pausar()
            return

        exibir_info(f"Importando feriados nacionais de {ano}...")
        resultado = servico.importar_feriados_nacionais(ano)

        exibir_sucesso("Importacao concluida:")
        console.print(f"  {ICONES['criar']} Criados: {resultado['sucesso']}")
        console.print(f"  {ICONES['aviso']} Ja existentes: {resultado['erros']}")
        pausar()
    except Exception as e:
        logger.error(f"Erro ao importar feriados nacionais: {e}")
        exibir_erro(f"Erro ao importar feriados nacionais: {e}")
        pausar()


def _importar_feriados_estaduais_ro(servico):
    """Importa feriados estaduais de RO para um ano"""
    from datetime import date

    try:
        ano_atual = date.today().year
        ano_str = pedir_texto(f"Ano para importar feriados RO [{ano_atual}]:")

        try:
            ano = int(ano_str) if ano_str else ano_atual
        except ValueError:
            exibir_erro("Ano invalido.")
            pausar()
            return

        exibir_info(f"Importando feriados estaduais de Rondonia para {ano}...")
        resultado = servico.importar_feriados_estaduais_ro(ano)

        exibir_sucesso("Importacao concluida:")
        console.print(f"  {ICONES['criar']} Criados: {resultado['sucesso']}")
        console.print(f"  {ICONES['aviso']} Ja existentes: {resultado['erros']}")
        pausar()
    except Exception as e:
        logger.error(f"Erro ao importar feriados estaduais: {e}")
        exibir_erro(f"Erro ao importar feriados estaduais: {e}")
        pausar()


def _listar_feriados_mes(servico):
    """Lista feriados de um mês específico"""
    from datetime import date

    try:
        ano_atual = date.today().year
        mes_atual = date.today().month

        ano_str = pedir_texto(f"Ano [{ano_atual}]:")
        mes_str = pedir_texto(f"Mes (1-12) [{mes_atual}]:")

        try:
            ano = int(ano_str) if ano_str else ano_atual
            mes = int(mes_str) if mes_str else mes_atual

            if not 1 <= mes <= 12:
                exibir_erro("Mes invalido (1-12).")
                pausar()
                return
        except ValueError:
            exibir_erro("Valores invalidos.")
            pausar()
            return

        feriados = servico.listar_por_mes(ano, mes)

        meses = ["", "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
                 "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

        exibir_cabecalho(f"Feriados de {meses[mes]}/{ano}", ICONES["calendario"])

        if not feriados:
            exibir_info("Nenhum feriado neste mes.")
        else:
            for f in feriados:
                data = f.get("data")
                if hasattr(data, 'strftime'):
                    data_str = data.strftime("%d/%m")
                else:
                    data_str = str(data)[:10]
                descricao = f.get("descricao", "")
                console.print(f"  {ICONES['feriado']} {data_str} - {descricao}")

        pausar()
    except Exception as e:
        logger.error(f"Erro ao listar feriados do mes: {e}")
        exibir_erro(f"Erro ao listar feriados do mes: {e}")
        pausar()


def _importar_feriados_excel():
    """Importa feriados do arquivo Excel"""
    from pathlib import Path

    try:
        # Importar função de migração
        try:
            from scripts.migrar_feriados import migrar_feriados_excel
        except ImportError:
            # Fallback: adicionar ao path
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from scripts.migrar_feriados import migrar_feriados_excel

        # Caminho padrão do Excel
        caminho_padrao = Path(__file__).parent.parent / "data" / "input" / "30.07.25 - 10.09 - Folha de Ponto - Alefe - Dados.xlsx"

        exibir_cabecalho("Importar Feriados do Excel", ICONES["excel"])
        console.print(f"Arquivo padrao: {caminho_padrao.name}")

        if not caminho_padrao.exists():
            exibir_erro("Arquivo padrao nao encontrado!")
            caminho_custom = pedir_texto("Digite o caminho do arquivo Excel:")
            if not caminho_custom:
                return
            caminho_padrao = Path(caminho_custom)
            if not caminho_padrao.exists():
                exibir_erro("Arquivo nao encontrado.")
                pausar()
                return

        # Perguntar se deseja limpar existentes
        opcao = pedir_selecao(
            "Opcoes:",
            [
                "Adicionar aos feriados existentes (pula duplicados)",
                "Substituir todos os feriados (remove antes de importar)"
            ]
        )

        if not opcao:
            return

        limpar = "Substituir" in opcao

        if limpar:
            if not pedir_confirmacao("ATENCAO: Isso removera todos os feriados. Confirma?"):
                exibir_info("Operacao cancelada.")
                pausar()
                return

        exibir_info("Importando feriados do Excel...")

        resultado = migrar_feriados_excel(
            caminho_excel=str(caminho_padrao),
            limpar_existentes=limpar
        )

        if "erro" in resultado:
            exibir_erro(f"Erro: {resultado['erro']}")
        else:
            exibir_sucesso("Importacao concluida:")
            console.print(f"  {ICONES['criar']} Importados: {resultado['sucesso']}")
            console.print(f"  {ICONES['erro']} Erros/Duplicados: {resultado['erros']}")
            console.print(f"  {ICONES['aviso']} Ignorados (sem data): {resultado['ignorados']}")

            if resultado.get("detalhes"):
                console.print("\nDetalhes:")
                for detalhe in resultado["detalhes"][:15]:
                    console.print(f"  {detalhe}")

                if len(resultado["detalhes"]) > 15:
                    console.print(f"  ... e mais {len(resultado['detalhes']) - 15} itens")

        pausar()
    except Exception as e:
        logger.error(f"Erro ao importar feriados do Excel: {e}")
        exibir_erro(f"Erro ao importar feriados do Excel: {e}")
        pausar()


if __name__ == "__main__":
    # Permite testar interface diretamente
    Interface_Referencias()
