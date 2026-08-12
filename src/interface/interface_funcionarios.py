"""
Interface interativa para gerenciar Funcionários (100% MongoDB)
Permite criar, atualizar, listar e remover funcionários
"""

from typing import Optional, List, Dict, Any
from datetime import date
from src.utils.logger_config import logger
from src.models.funcionario_models import StatusFuncionario
from src.models.contrato_models import StatusContrato
from src.models.funcao_models import StatusFuncao

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

# Imports dos serviços
try:
    from src.services.funcionario_service import FuncionarioService
    from src.services.empresa_service import EmpresaService
    from src.services.contrato_service import ContratoService
    from src.services.funcao_service import FuncaoService
    from src.services.horario_service import HorarioService
    from src.services.diretorio_service import DiretorioService
    from bson import ObjectId
    MONGODB_DISPONIVEL = True
except ImportError as e:
    logger.warning(f"Serviços MongoDB não disponíveis: {e}")
    MONGODB_DISPONIVEL = False


def Interface_Funcionarios():
    """Interface principal de Gerenciamento de Funcionários"""

    if not MONGODB_DISPONIVEL:
        exibir_erro("MongoDB nao esta disponivel. Verifique a conexao.")
        return

    (
        MenuBuilder("GERENCIAMENTO DE FUNCIONARIOS", ICONES["funcionarios"])
        .adicionar("Listar todos os funcionarios", listar_funcionarios, ICONES["listar"])
        .adicionar("Listar funcionarios por filtro", listar_por_filtro, ICONES["buscar"])
        .adicionar("Ver detalhes de um funcionario", ver_detalhes_funcionario, ICONES["funcionario"])
        .separador()
        .adicionar("Criar novo funcionario", criar_funcionario, ICONES["criar"])
        .adicionar("Atualizar funcionario", atualizar_funcionario, ICONES["editar"])
        .adicionar("Alterar status do funcionario", alterar_status_funcionario, ICONES["atualizar"])
        .adicionar("Remover funcionario", remover_funcionario, ICONES["excluir"])
        .separador()
        .adicionar("Exibir estatisticas", exibir_estatisticas, ICONES["estatistica"])
        .adicionar("Exportar funcionarios (JSON completo)", exportar_funcionarios_json, ICONES["salvar"])
        .com_voltar("Voltar ao Menu Principal")
        .executar()
    )


# ==================== FUNÇÕES DE LISTAGEM ====================

def listar_funcionarios():
    """Lista todos os funcionários"""
    servico = FuncionarioService()

    exibir_cabecalho("LISTA DE FUNCIONARIOS")

    # Verificar se serviço está disponível
    if not servico.disponivel:
        exibir_erro("MongoDB nao esta disponivel. Verifique a conexao.")
        return

    # Opções de filtro
    filtro_opcao = pedir_selecao(
        "Filtrar por status:",
        ["Apenas ativos (padrao)", "Apenas inativos", "Todos"]
    )

    if not filtro_opcao:
        return

    filtro = {}
    if "ativos" in filtro_opcao.lower():
        filtro["status"] = StatusFuncionario.ATIVO.value
    elif "inativos" in filtro_opcao.lower():
        filtro["status"] = {"$ne": StatusFuncionario.ATIVO.value}

    try:
        logger.debug("Iniciando listar_todos...")
        resultado = servico.listar_todos(limit=500)
        logger.debug(f"Resultado recebido: tipo={type(resultado)}, valor={resultado}")

        # Verificar se resultado é válido
        if resultado is None:
            exibir_erro("Erro: resultado vazio do serviço.")
            logger.error(f"listar_todos() retornou None")
            return

        # Validar tipo de resultado
        if not isinstance(resultado, dict):
            exibir_erro(f"Erro: resultado não é dicionário (tipo: {type(resultado)})")
            logger.error(f"Tipo inesperado de resultado: {type(resultado)}")
            return

        funcionarios = resultado.get("dados", [])
        logger.debug(f"Funcionários obtidos: {len(funcionarios) if funcionarios else 0} registros")

        # Validar se funcionarios é uma lista
        if funcionarios is None:
            funcionarios = []

        # Aplicar filtro de status manualmente se necessário
        if filtro:
            if "status" in filtro:
                logger.debug(f"Aplicando filtro de status: {filtro['status']}")
                if isinstance(filtro["status"], dict):
                    # Filtrar apenas dicts válidos
                    funcionarios = [f for f in funcionarios
                                  if isinstance(f, dict) and f.get("status") != StatusFuncionario.ATIVO.value]
                else:
                    # Filtrar apenas dicts válidos
                    funcionarios = [f for f in funcionarios
                                  if isinstance(f, dict) and f.get("status") == filtro["status"]]
                logger.debug(f"Após filtro: {len(funcionarios)} funcionários")

        if not funcionarios:
            exibir_info("Nenhum funcionario encontrado.")
        else:
            # Preparar dados para tabela
            dados = []
            for idx, func in enumerate(funcionarios):
                try:
                    # Validar que func é um dicionário
                    if func is None:
                        logger.warning(f"Funcionário {idx}: valor é None")
                        continue

                    if not isinstance(func, dict):
                        logger.warning(f"Funcionário {idx} inválido (não é dict): {type(func)} = {func}")
                        continue

                    # Validar campos antes de usar
                    nome = func.get("nome")
                    lotacao = func.get("lotacao")
                    status = func.get("status")

                    # Converter None para "N/A"
                    nome = str(nome) if nome else "N/A"
                    lotacao = str(lotacao) if lotacao else "N/A"
                    status = str(status) if status else "N/A"

                    dados.append([nome, lotacao, status])
                except TypeError as e:
                    logger.error(f"Funcionário {idx}: erro de tipo - {e}")
                    logger.debug(f"  func = {func}, tipo = {type(func)}")
                    continue
                except Exception as e:
                    logger.error(f"Funcionário {idx}: erro ao processar - {e}")
                    continue

            if dados:
                exibir_tabela(
                    f"{len(funcionarios)} funcionario(s) encontrado(s)",
                    ["Nome", "Lotacao", "Status"],
                    dados
                )
            else:
                exibir_info("Nenhum funcionario válido encontrado.")

    except Exception as e:
        logger.error(f"Erro ao listar funcionarios: {e}")
        logger.debug(f"Tipo do erro: {type(e)}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        exibir_erro(f"Erro ao listar funcionarios: {e}")


def listar_por_filtro():
    """Submenu para listar funcionários por diferentes filtros"""

    (
        MenuBuilder("LISTAR FUNCIONARIOS POR FILTRO", ICONES["buscar"])
        .adicionar("Por Nome", _filtrar_por_nome, ICONES["funcionario"])
        .adicionar("Por Empresa", _filtrar_por_empresa, ICONES["empresa"])
        .adicionar("Por Lotacao", _filtrar_por_lotacao, ICONES["diretorio"])
        .adicionar("Por Contrato da Empresa", _filtrar_por_contrato, ICONES["contrato"])
        .adicionar("Por Funcao", _filtrar_por_funcao, ICONES["funcao"])
        .adicionar("Por Data de Nascimento", _filtrar_por_data_nascimento, ICONES["calendario"])
        .adicionar("Por Data de Admissao", _filtrar_por_data_admissao, ICONES["calendario"])
        .adicionar("Por Data de Demissao", _filtrar_por_data_demissao, ICONES["calendario"])
        .com_voltar("Voltar")
        .executar()
    )


def _filtrar_por_nome():
    """Filtra funcionários por nome (busca parcial)"""
    servico = FuncionarioService()

    exibir_cabecalho("FILTRAR POR NOME")

    nome = pedir_texto("Digite o nome (ou parte):")
    if not nome:
        exibir_erro("Nome nao pode ser vazio.")
        return

    try:
        # Buscar usando regex para correspondência parcial (case insensitive)
        import unicodedata
        # Normalizar o termo de busca
        nfkd = unicodedata.normalize('NFKD', nome)
        nome_normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)]).lower()

        # Buscar diretamente na coleção usando regex
        cursor = servico.colecao.find({
            "nome_normalizado": {"$regex": nome_normalizado, "$options": "i"}
        }).sort("nome", 1)

        funcionarios = list(cursor)

        if not funcionarios:
            exibir_info(f"Nenhum funcionario encontrado com nome contendo '{nome}'.")
        else:
            exibir_info(f"{len(funcionarios)} funcionario(s) encontrado(s):")
            _exibir_lista_funcionarios(funcionarios)

    except Exception as e:
        exibir_erro(f"Erro na busca: {e}")


def _filtrar_por_empresa():
    """Filtra funcionários por empresa (seleção de lista)"""
    servico_funcionario = FuncionarioService()
    servico_empresa = EmpresaService()

    exibir_cabecalho("FILTRAR POR EMPRESA")

    try:
        # Listar todas as empresas
        resultado = servico_empresa.listar_todos()
        if resultado is None or not isinstance(resultado, dict):
            exibir_aviso("Erro ao listar empresas.")
            return
        empresas = resultado.get("dados", [])

        if not empresas:
            exibir_aviso("Nenhuma empresa cadastrada.")
            return

        # Preparar opções
        opcoes_empresas = [f"{emp.get('nome', 'N/A')}" for emp in empresas]

        escolha = pedir_selecao("Selecione a empresa:", opcoes_empresas)

        if not escolha:
            return

        # Encontrar empresa selecionada
        idx = opcoes_empresas.index(escolha)
        empresa_selecionada = empresas[idx]
        empresa_id = empresa_selecionada.get("_id")
        empresa_nome = empresa_selecionada.get("nome")

        # Buscar funcionários dessa empresa
        cursor = servico_funcionario.colecao.find({
            "empresas_ids": ObjectId(str(empresa_id))
        }).sort("nome", 1)

        funcionarios = list(cursor)

        exibir_cabecalho(f"Funcionarios da empresa: {empresa_nome}")

        if not funcionarios:
            exibir_info("Nenhum funcionario encontrado nesta empresa.")
        else:
            exibir_info(f"{len(funcionarios)} funcionario(s) encontrado(s):")
            _exibir_lista_funcionarios(funcionarios)

    except Exception as e:
        exibir_erro(f"Erro na busca: {e}")


def _filtrar_por_lotacao():
    """Filtra funcionários por lotação (busca parcial)"""
    servico = FuncionarioService()

    exibir_cabecalho("FILTRAR POR LOTACAO")

    lotacao = pedir_texto("Digite a lotacao (ou parte):")
    if not lotacao:
        exibir_erro("Lotacao nao pode ser vazia.")
        return

    try:
        # Buscar usando regex
        cursor = servico.colecao.find({
            "lotacao": {"$regex": lotacao, "$options": "i"}
        }).sort("lotacao", 1)

        funcionarios = list(cursor)

        if not funcionarios:
            exibir_info(f"Nenhum funcionario encontrado na lotacao '{lotacao}'.")
        else:
            # Agrupar por lotação
            lotacoes = {}
            for func in funcionarios:
                lot = func.get("lotacao", "N/A")
                if lot not in lotacoes:
                    lotacoes[lot] = []
                lotacoes[lot].append(func)

            exibir_info(f"{len(funcionarios)} funcionario(s) encontrado(s) em {len(lotacoes)} lotacao(oes):")

            for lotacao_nome, funcs in sorted(lotacoes.items()):
                console.print(f"\n[cyan]{ICONES['empresa']} {lotacao_nome}[/cyan] ({len(funcs)} funcionario(s)):")
                for func in funcs:
                    nome = func.get("nome", "N/A")
                    status = func.get("status", "N/A")
                    console.print(f"   {ICONES['ponto']} {nome} [{status}]")

    except Exception as e:
        exibir_erro(f"Erro na busca: {e}")


def _filtrar_por_contrato():
    """Filtra funcionários por contrato da empresa (seleção de lista)"""
    servico_funcionario = FuncionarioService()
    servico_contrato = ContratoService()

    exibir_cabecalho("FILTRAR POR CONTRATO DA EMPRESA")

    try:
        # Listar todos os contratos
        contratos = servico_contrato.listar_todos()

        if not contratos:
            exibir_aviso("Nenhum contrato cadastrado.")
            return

        # Preparar opções
        opcoes_contratos = [f"{c.get('nome', 'N/A')}" for c in contratos]

        escolha = pedir_selecao("Selecione o contrato:", opcoes_contratos)

        if not escolha:
            return

        # Encontrar contrato selecionado
        idx = opcoes_contratos.index(escolha)
        contrato_selecionado = contratos[idx]
        contrato_id = contrato_selecionado.get("_id")
        contrato_nome = contrato_selecionado.get("nome")

        # Buscar funcionários
        cursor = servico_funcionario.colecao.find({
            "contrato_empresa_id": ObjectId(str(contrato_id))
        }).sort("nome", 1)

        funcionarios = list(cursor)

        exibir_cabecalho(f"Funcionarios do contrato: {contrato_nome}")

        if not funcionarios:
            exibir_info("Nenhum funcionario encontrado neste contrato.")
        else:
            exibir_info(f"{len(funcionarios)} funcionario(s) encontrado(s):")
            _exibir_lista_funcionarios(funcionarios)

    except Exception as e:
        exibir_erro(f"Erro na busca: {e}")


def _filtrar_por_funcao():
    """Filtra funcionários por função (seleção de lista)"""
    servico_funcionario = FuncionarioService()
    servico_funcao = FuncaoService()

    exibir_cabecalho("FILTRAR POR FUNCAO")

    try:
        # Listar todas as funções
        funcoes = servico_funcao.listar_todos()

        if not funcoes:
            exibir_aviso("Nenhuma funcao cadastrada.")
            return

        # Preparar opções
        opcoes_funcoes = [f"{f.get('nome', 'N/A')}" for f in funcoes]

        escolha = pedir_selecao("Selecione a funcao:", opcoes_funcoes)

        if not escolha:
            return

        # Encontrar função selecionada
        idx = opcoes_funcoes.index(escolha)
        funcao_selecionada = funcoes[idx]
        funcao_id = funcao_selecionada.get("_id")
        funcao_nome = funcao_selecionada.get("nome")

        # Buscar funcionários
        cursor = servico_funcionario.colecao.find({
            "funcao_id": ObjectId(str(funcao_id))
        }).sort("nome", 1)

        funcionarios = list(cursor)

        exibir_cabecalho(f"Funcionarios com funcao: {funcao_nome}")

        if not funcionarios:
            exibir_info("Nenhum funcionario encontrado com esta funcao.")
        else:
            exibir_info(f"{len(funcionarios)} funcionario(s) encontrado(s):")
            _exibir_lista_funcionarios(funcionarios)

    except Exception as e:
        exibir_erro(f"Erro na busca: {e}")


def _filtrar_por_data_nascimento():
    """Filtra funcionários por data de nascimento"""
    servico = FuncionarioService()

    exibir_cabecalho("FILTRAR POR DATA DE NASCIMENTO")

    opcao = pedir_selecao(
        "Opcoes de filtro:",
        [
            "Nascidos em um mes especifico (aniversariantes)",
            "Nascidos em um periodo (intervalo de datas)",
            "Nascidos em um ano especifico"
        ]
    )

    if not opcao:
        return

    try:
        from datetime import datetime

        if "mes especifico" in opcao:
            # Filtrar por mês
            mes = pedir_inteiro("Digite o mes (1-12):", minimo=1, maximo=12)

            if not mes:
                exibir_erro("Mes invalido.")
                return

            # Usa buscar_aniversariantes
            funcionarios = servico.buscar_aniversariantes(mes)

            meses_nome = ["", "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
                         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

            exibir_cabecalho(f"Aniversariantes de {meses_nome[mes]}")

            if not funcionarios:
                exibir_info("Nenhum funcionario faz aniversario neste mes.")
            else:
                exibir_info(f"{len(funcionarios)} funcionario(s) encontrado(s):")
                _exibir_lista_com_data(funcionarios, "data_nascimento")

        elif "periodo" in opcao:
            # Filtrar por período
            data_inicio = _input_data("Data inicial (YYYY-MM-DD):")
            data_fim = _input_data("Data final (YYYY-MM-DD):")

            if not data_inicio or not data_fim:
                exibir_erro("Datas invalidas.")
                return

            dt_inicio = datetime.combine(data_inicio, datetime.min.time())
            dt_fim = datetime.combine(data_fim, datetime.max.time())

            cursor = servico.colecao.find({
                "data_nascimento": {"$gte": dt_inicio, "$lte": dt_fim}
            }).sort("data_nascimento", 1)

            funcionarios = list(cursor)

            exibir_cabecalho(f"Funcionarios nascidos entre {data_inicio} e {data_fim}")

            if not funcionarios:
                exibir_info("Nenhum funcionario encontrado neste periodo.")
            else:
                exibir_info(f"{len(funcionarios)} funcionario(s) encontrado(s):")
                _exibir_lista_com_data(funcionarios, "data_nascimento")

        elif "ano especifico" in opcao:
            # Filtrar por ano
            ano = pedir_inteiro("Digite o ano (ex: 1990):")
            if not ano:
                exibir_erro("Ano invalido.")
                return

            dt_inicio = datetime(ano, 1, 1)
            dt_fim = datetime(ano, 12, 31, 23, 59, 59)

            cursor = servico.colecao.find({
                "data_nascimento": {"$gte": dt_inicio, "$lte": dt_fim}
            }).sort("data_nascimento", 1)

            funcionarios = list(cursor)

            exibir_cabecalho(f"Funcionarios nascidos em {ano}")

            if not funcionarios:
                exibir_info("Nenhum funcionario encontrado neste ano.")
            else:
                exibir_info(f"{len(funcionarios)} funcionario(s) encontrado(s):")
                _exibir_lista_com_data(funcionarios, "data_nascimento")

    except Exception as e:
        exibir_erro(f"Erro na busca: {e}")


def _filtrar_por_data_admissao():
    """Filtra funcionários por data de admissão"""
    servico = FuncionarioService()

    exibir_cabecalho("FILTRAR POR DATA DE ADMISSAO")

    opcao = pedir_selecao(
        "Opcoes de filtro:",
        [
            "Admitidos em um mes/ano especifico",
            "Admitidos em um periodo (intervalo de datas)",
            "Admitidos em um ano especifico"
        ]
    )

    if not opcao:
        return

    try:
        from datetime import datetime

        if "mes/ano especifico" in opcao:
            # Filtrar por mês/ano
            mes = pedir_inteiro("Digite o mes (1-12):", minimo=1, maximo=12)
            ano = pedir_inteiro("Digite o ano (ex: 2024):")

            if not mes or not ano:
                exibir_erro("Valores invalidos.")
                return

            # Calcular primeiro e último dia do mês
            if mes == 12:
                dt_fim = datetime(ano + 1, 1, 1)
            else:
                dt_fim = datetime(ano, mes + 1, 1)
            dt_inicio = datetime(ano, mes, 1)

            cursor = servico.colecao.find({
                "data_admissao": {"$gte": dt_inicio, "$lt": dt_fim}
            }).sort("data_admissao", 1)

            funcionarios = list(cursor)

            meses_nome = ["", "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
                         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

            exibir_cabecalho(f"Funcionarios admitidos em {meses_nome[mes]}/{ano}")

            if not funcionarios:
                exibir_info("Nenhum funcionario admitido neste periodo.")
            else:
                exibir_info(f"{len(funcionarios)} funcionario(s) encontrado(s):")
                _exibir_lista_com_data(funcionarios, "data_admissao")

        elif "periodo" in opcao:
            # Filtrar por período
            data_inicio = _input_data("Data inicial (YYYY-MM-DD):")
            data_fim = _input_data("Data final (YYYY-MM-DD):")

            if not data_inicio or not data_fim:
                exibir_erro("Datas invalidas.")
                return

            dt_inicio = datetime.combine(data_inicio, datetime.min.time())
            dt_fim = datetime.combine(data_fim, datetime.max.time())

            cursor = servico.colecao.find({
                "data_admissao": {"$gte": dt_inicio, "$lte": dt_fim}
            }).sort("data_admissao", 1)

            funcionarios = list(cursor)

            exibir_cabecalho(f"Funcionarios admitidos entre {data_inicio} e {data_fim}")

            if not funcionarios:
                exibir_info("Nenhum funcionario encontrado neste periodo.")
            else:
                exibir_info(f"{len(funcionarios)} funcionario(s) encontrado(s):")
                _exibir_lista_com_data(funcionarios, "data_admissao")

        elif "ano especifico" in opcao:
            # Filtrar por ano
            ano = pedir_inteiro("Digite o ano (ex: 2024):")
            if not ano:
                exibir_erro("Ano invalido.")
                return

            dt_inicio = datetime(ano, 1, 1)
            dt_fim = datetime(ano, 12, 31, 23, 59, 59)

            cursor = servico.colecao.find({
                "data_admissao": {"$gte": dt_inicio, "$lte": dt_fim}
            }).sort("data_admissao", 1)

            funcionarios = list(cursor)

            exibir_cabecalho(f"Funcionarios admitidos em {ano}")

            if not funcionarios:
                exibir_info("Nenhum funcionario admitido neste ano.")
            else:
                exibir_info(f"{len(funcionarios)} funcionario(s) encontrado(s):")
                _exibir_lista_com_data(funcionarios, "data_admissao")

    except Exception as e:
        exibir_erro(f"Erro na busca: {e}")


def _filtrar_por_data_demissao():
    """Filtra funcionários por data de demissão"""
    servico = FuncionarioService()

    exibir_cabecalho("FILTRAR POR DATA DE DEMISSAO")

    opcao = pedir_selecao(
        "Opcoes de filtro:",
        [
            "Demitidos em um mes/ano especifico",
            "Demitidos em um periodo (intervalo de datas)",
            "Demitidos em um ano especifico",
            "Listar todos os demitidos"
        ]
    )

    if not opcao:
        return

    try:
        from datetime import datetime

        if "mes/ano especifico" in opcao:
            # Filtrar por mês/ano
            mes = pedir_inteiro("Digite o mes (1-12):", minimo=1, maximo=12)
            ano = pedir_inteiro("Digite o ano (ex: 2024):")

            if not mes or not ano:
                exibir_erro("Valores invalidos.")
                return

            # Calcular primeiro e último dia do mês
            if mes == 12:
                dt_fim = datetime(ano + 1, 1, 1)
            else:
                dt_fim = datetime(ano, mes + 1, 1)
            dt_inicio = datetime(ano, mes, 1)

            cursor = servico.colecao.find({
                "data_demissao": {"$gte": dt_inicio, "$lt": dt_fim}
            }).sort("data_demissao", 1)

            funcionarios = list(cursor)

            meses_nome = ["", "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
                         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

            exibir_cabecalho(f"Funcionarios demitidos em {meses_nome[mes]}/{ano}")

            if not funcionarios:
                exibir_info("Nenhum funcionario demitido neste periodo.")
            else:
                exibir_info(f"{len(funcionarios)} funcionario(s) encontrado(s):")
                _exibir_lista_com_data(funcionarios, "data_demissao")

        elif "periodo" in opcao and "intervalo" in opcao:
            # Filtrar por período
            data_inicio = _input_data("Data inicial (YYYY-MM-DD):")
            data_fim = _input_data("Data final (YYYY-MM-DD):")

            if not data_inicio or not data_fim:
                exibir_erro("Datas invalidas.")
                return

            dt_inicio = datetime.combine(data_inicio, datetime.min.time())
            dt_fim = datetime.combine(data_fim, datetime.max.time())

            cursor = servico.colecao.find({
                "data_demissao": {"$gte": dt_inicio, "$lte": dt_fim}
            }).sort("data_demissao", 1)

            funcionarios = list(cursor)

            exibir_cabecalho(f"Funcionarios demitidos entre {data_inicio} e {data_fim}")

            if not funcionarios:
                exibir_info("Nenhum funcionario encontrado neste periodo.")
            else:
                exibir_info(f"{len(funcionarios)} funcionario(s) encontrado(s):")
                _exibir_lista_com_data(funcionarios, "data_demissao")

        elif "ano especifico" in opcao:
            # Filtrar por ano
            ano = pedir_inteiro("Digite o ano (ex: 2024):")
            if not ano:
                exibir_erro("Ano invalido.")
                return

            dt_inicio = datetime(ano, 1, 1)
            dt_fim = datetime(ano, 12, 31, 23, 59, 59)

            cursor = servico.colecao.find({
                "data_demissao": {"$gte": dt_inicio, "$lte": dt_fim}
            }).sort("data_demissao", 1)

            funcionarios = list(cursor)

            exibir_cabecalho(f"Funcionarios demitidos em {ano}")

            if not funcionarios:
                exibir_info("Nenhum funcionario demitido neste ano.")
            else:
                exibir_info(f"{len(funcionarios)} funcionario(s) encontrado(s):")
                _exibir_lista_com_data(funcionarios, "data_demissao")

        elif "todos os demitidos" in opcao:
            # Listar todos os demitidos
            cursor = servico.colecao.find({
                "data_demissao": {"$exists": True, "$ne": None}
            }).sort("data_demissao", -1)

            funcionarios = list(cursor)

            exibir_cabecalho("Todos os funcionarios demitidos")

            if not funcionarios:
                exibir_info("Nenhum funcionario demitido encontrado.")
            else:
                exibir_info(f"{len(funcionarios)} funcionario(s) encontrado(s):")
                _exibir_lista_com_data(funcionarios, "data_demissao")

    except Exception as e:
        exibir_erro(f"Erro na busca: {e}")


def _exibir_lista_com_data(funcionarios: List[Dict[str, Any]], campo_data: str):
    """Exibe lista de funcionários com uma coluna de data específica"""
    dados = []
    for func in funcionarios:
        nome = func.get("nome", "N/A")
        data_valor = func.get(campo_data)
        if data_valor and hasattr(data_valor, 'strftime'):
            data_str = data_valor.strftime("%d/%m/%Y")
        else:
            data_str = "N/A"
        lotacao = func.get("lotacao", "N/A")
        status = func.get("status", "N/A")

        dados.append([nome, data_str, lotacao, status])

    exibir_tabela(
        "Resultados",
        ["Nome", "Data", "Lotacao", "Status"],
        dados
    )


def ver_detalhes_funcionario():
    """Exibe detalhes completos de um funcionário"""
    exibir_cabecalho("DETALHES DO FUNCIONARIO")

    funcionario = _selecionar_funcionario("Digite o nome do funcionario para ver detalhes:")
    if not funcionario:
        return

    _exibir_detalhes_funcionario(funcionario)


# ==================== FUNÇÕES DE CRIAÇÃO ====================

def criar_funcionario():
    """Cria um novo funcionário"""
    exibir_cabecalho("CRIAR NOVO FUNCIONARIO")
    exibir_info("Preencha os dados do funcionario:")
    console.print("[dim]   (Campos com * sao obrigatorios)[/dim]\n")

    servico_funcionario = FuncionarioService()
    servico_empresa = EmpresaService()
    servico_contrato = ContratoService()
    servico_funcao = FuncaoService()
    servico_horario = HorarioService()

    # ==================== DADOS BÁSICOS ====================
    console.print("[cyan]DADOS BASICOS[/cyan]")

    # Nome (obrigatório)
    nome = pedir_texto("* Nome completo:")
    if not nome:
        exibir_erro("Nome e obrigatorio!")
        return

    # PIS (opcional)
    pis = pedir_texto("  Numero PIS (opcional):", obrigatorio=False) or None

    # CPF (opcional)
    cpf = pedir_texto("  Numero CPF (opcional):", obrigatorio=False) or None

    # Lotação (obrigatório)
    lotacao = pedir_texto("* Lotacao/Departamento:")
    if not lotacao:
        exibir_erro("Lotacao e obrigatoria!")
        return

    # ==================== TIPO DE CONTRATO ====================
    console.print("\n[cyan]TIPO DE CONTRATO DO FUNCIONARIO[/cyan]")

    tipo_contrato = pedir_selecao(
        "* Escolha o tipo:",
        ["CLT", "PJ", "Aprendiz", "Estagiario", "Intermitente"]
    )

    if not tipo_contrato:
        tipo_contrato = "CLT"

    # ==================== EMPRESA(S) ====================
    console.print("\n[cyan]EMPRESA(S)[/cyan]")

    empresas_ids = _selecionar_multiplas_empresas("Selecione a(s) empresa(s):")
    if not empresas_ids:
        exibir_erro("Pelo menos uma empresa e obrigatoria!")
        return

    # ==================== CONTRATO EMPRESA ====================
    console.print("\n[cyan]CONTRATO DA EMPRESA (com orgao/entidade)[/cyan]")

    contrato_empresa_id = _selecionar_de_lista(
        servico_contrato,
        "contrato",
        "Selecione o contrato:"
    )
    if not contrato_empresa_id:
        exibir_erro("Contrato e obrigatorio!")
        return

    # ==================== FUNÇÃO ====================
    console.print("\n[cyan]FUNCAO/CARGO[/cyan]")

    funcao_id = _selecionar_de_lista(
        servico_funcao,
        "funcao",
        "Selecione a funcao:"
    )
    if not funcao_id:
        exibir_erro("Funcao e obrigatoria!")
        return

    # ==================== HORÁRIO ====================
    console.print("\n[cyan]HORARIO DE TRABALHO[/cyan]")

    horario_id = _selecionar_de_lista(
        servico_horario,
        "horario",
        "Selecione o horario:"
    )
    if not horario_id:
        exibir_erro("Horario e obrigatorio!")
        return

    # ==================== DIRETÓRIO (opcional) ====================
    console.print("\n[cyan]DIRETORIO INTERNO (opcional)[/cyan]")
    exibir_info("Se nao selecionar, sera criado automaticamente com base no contrato.")

    servico_diretorio = DiretorioService()
    diretorio_id = _selecionar_de_lista(
        servico_diretorio,
        "diretorio",
        "Selecione o diretorio (ENTER para auto-criar):"
    )

    # ==================== DATAS (opcionais) ====================
    console.print("\n[cyan]DATAS (formato: YYYY-MM-DD, deixe vazio para pular)[/cyan]")

    data_admissao = _input_data("  Data de admissao:")
    data_nascimento = _input_data("  Data de nascimento:")

    # ==================== CONFIRMAÇÃO ====================
    exibir_cabecalho("CONFIRMAR DADOS")
    console.print(f"  Nome: [cyan]{nome}[/cyan]")
    console.print(f"  PIS: [dim]{pis or '(nao informado)'}[/dim]")
    console.print(f"  CPF: [dim]{cpf or '(nao informado)'}[/dim]")
    console.print(f"  Lotacao: [cyan]{lotacao}[/cyan]")
    console.print(f"  Tipo Contrato: [cyan]{tipo_contrato}[/cyan]")
    console.print(f"  Data Admissao: [dim]{data_admissao or '(nao informada)'}[/dim]")
    console.print(f"  Data Nascimento: [dim]{data_nascimento or '(nao informada)'}[/dim]")

    if not pedir_confirmacao("Confirma a criacao?"):
        exibir_erro("Operacao cancelada.")
        return

    # ==================== CRIAR FUNCIONÁRIO ====================
    try:
        from datetime import datetime, timezone
        import unicodedata

        # Normalizar nome
        nfkd = unicodedata.normalize('NFKD', nome)
        nome_normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)]).lower()

        documento = {
            "nome": nome,
            "nome_normalizado": nome_normalizado,
            "pis": pis,
            "cpf": cpf,
            "lotacao": lotacao,
            "contrato": tipo_contrato,
            "empresas_ids": [ObjectId(eid) for eid in empresas_ids],
            "contrato_empresa_id": ObjectId(contrato_empresa_id),
            "funcao_id": ObjectId(funcao_id),
            "horario_id": ObjectId(horario_id),
            "diretorio_id": ObjectId(diretorio_id) if diretorio_id else None,
            "status": "ativo",
            "data_admissao": datetime.combine(data_admissao, datetime.min.time()) if data_admissao else None,
            "data_nascimento": datetime.combine(data_nascimento, datetime.min.time()) if data_nascimento else None,
            "criado_em": datetime.now(timezone.utc),
            "atualizado_em": datetime.now(timezone.utc),
            "versao": 1,
            "historico_alteracoes": [{
                "acao": "criacao",
                "data": datetime.now(timezone.utc).isoformat(),
                "origem": "interface_cli"
            }]
        }

        resultado = servico_funcionario.criar_funcionario(documento)

        if resultado:
            exibir_sucesso("Funcionario criado com sucesso!")
            console.print(f"   ID: [cyan]{resultado}[/cyan]")
        else:
            exibir_erro("Falha ao criar funcionario.")

    except Exception as e:
        logger.error(f"Erro ao criar funcionário: {e}")
        exibir_erro(f"Erro ao criar funcionario: {e}")


# ==================== FUNÇÕES DE ATUALIZAÇÃO ====================

def atualizar_funcionario():
    """Atualiza dados de um funcionário existente"""
    exibir_cabecalho("ATUALIZAR FUNCIONARIO")

    funcionario = _selecionar_funcionario("Digite o nome do funcionario para atualizar:")
    if not funcionario:
        return

    funcionario_id = str(funcionario.get("_id"))

    console.print("\n[cyan]Dados atuais do funcionario:[/cyan]")
    _exibir_detalhes_funcionario(funcionario)

    opcao = pedir_selecao(
        "O que deseja atualizar?",
        [
            "Nome",
            "PIS",
            "CPF",
            "Lotacao",
            "Tipo de Contrato",
            "Empresa",
            "Contrato da Empresa",
            "Funcao",
            "Horario",
            "Diretorio Interno",
            "Data de Admissao",
            "Data de Nascimento"
        ]
    )

    if not opcao:
        return

    servico_funcionario = FuncionarioService()
    alteracoes = {}

    try:
        if opcao == "Nome":
            novo_valor = pedir_texto(f"Novo nome [{funcionario.get('nome')}]:", obrigatorio=False)
            if novo_valor:
                import unicodedata
                nfkd = unicodedata.normalize('NFKD', novo_valor)
                nome_normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)]).lower()
                alteracoes["nome"] = novo_valor
                alteracoes["nome_normalizado"] = nome_normalizado

        elif opcao == "PIS":
            novo_valor = pedir_texto(f"Novo PIS [{funcionario.get('pis', 'vazio')}]:", obrigatorio=False)
            alteracoes["pis"] = novo_valor or None

        elif opcao == "CPF":
            novo_valor = pedir_texto(f"Novo CPF [{funcionario.get('cpf', 'vazio')}]:", obrigatorio=False)
            alteracoes["cpf"] = novo_valor or None

        elif opcao == "Lotacao":
            novo_valor = pedir_texto(f"Nova lotacao [{funcionario.get('lotacao')}]:", obrigatorio=False)
            if novo_valor:
                alteracoes["lotacao"] = novo_valor

        elif opcao == "Tipo de Contrato":
            novo_tipo = pedir_selecao("Novo tipo:", ["CLT", "PJ", "Aprendiz", "Estagiario", "Intermitente"])
            if novo_tipo:
                alteracoes["contrato"] = novo_tipo

        elif opcao == "Empresa":
            # Mostrar empresas atuais
            empresas_atuais = funcionario.get("empresas_ids", [])
            if empresas_atuais:
                exibir_info("Empresas atuais do funcionario:")
                servico_empresa = EmpresaService()
                for emp_id in empresas_atuais:
                    emp = servico_empresa.buscar_por_id(str(emp_id))
                    if emp:
                        console.print(f"   {ICONES['ponto']} {emp.get('nome', 'N/A')}")

            # Selecionar múltiplas empresas
            empresas_ids = _selecionar_multiplas_empresas("Selecione as empresas (pode ser mais de uma):")
            if empresas_ids:
                alteracoes["empresas_ids"] = [ObjectId(eid) for eid in empresas_ids]

        elif opcao == "Contrato da Empresa":
            contrato_id = _selecionar_de_lista(ContratoService(), "contrato", "Novo contrato:")
            if contrato_id:
                alteracoes["contrato_empresa_id"] = ObjectId(contrato_id)

        elif opcao == "Funcao":
            funcao_id = _selecionar_de_lista(FuncaoService(), "funcao", "Nova funcao:")
            if funcao_id:
                alteracoes["funcao_id"] = ObjectId(funcao_id)

        elif opcao == "Horario":
            horario_id = _selecionar_de_lista(HorarioService(), "horario", "Novo horario:")
            if horario_id:
                alteracoes["horario_id"] = ObjectId(horario_id)

        elif opcao == "Diretorio Interno":
            diretorio_id = _selecionar_de_lista(DiretorioService(), "diretorio", "Novo diretorio:")
            if diretorio_id:
                alteracoes["diretorio_id"] = ObjectId(diretorio_id)

        elif opcao == "Data de Admissao":
            nova_data = _input_data("Nova data de admissao (YYYY-MM-DD):")
            if nova_data:
                from datetime import datetime
                alteracoes["data_admissao"] = datetime.combine(nova_data, datetime.min.time())

        elif opcao == "Data de Nascimento":
            nova_data = _input_data("Nova data de nascimento (YYYY-MM-DD):")
            if nova_data:
                from datetime import datetime
                alteracoes["data_nascimento"] = datetime.combine(nova_data, datetime.min.time())

        if alteracoes:
            # O decorador @registrar_historico busca valores anteriores automaticamente
            sucesso = servico_funcionario.atualizar(funcionario_id, alteracoes)
            if sucesso:
                exibir_sucesso("Funcionario atualizado com sucesso!")
            else:
                exibir_erro("Falha ao atualizar funcionario.")
        else:
            exibir_aviso("Nenhuma alteracao realizada.")

    except Exception as e:
        logger.error(f"Erro ao atualizar funcionário: {e}")
        exibir_erro(f"Erro: {e}")


def alterar_status_funcionario():
    """Altera o status de um funcionário"""
    exibir_cabecalho("ALTERAR STATUS DO FUNCIONARIO")

    funcionario = _selecionar_funcionario("Digite o nome do funcionario:")
    if not funcionario:
        return

    funcionario_id = str(funcionario.get("_id"))
    status_atual = funcionario.get("status", StatusFuncionario.ATIVO.value)

    console.print(f"\nFuncionario: [cyan]{funcionario.get('nome')}[/cyan]")
    console.print(f"Status atual: [yellow]{status_atual}[/yellow]")

    novo_status = pedir_selecao(
        "Novo status:",
        ["Ativo", "Inativo", "Afastado", "Demitido", "Transferido"]
    )

    if not novo_status:
        exibir_erro("Operacao cancelada.")
        return

    novo_status = novo_status.lower()

    try:
        servico = FuncionarioService()

        # O decorador @registrar_historico busca valores anteriores automaticamente
        sucesso = servico.atualizar(funcionario_id, {"status": novo_status})

        if sucesso:
            exibir_sucesso(f"Status alterado para: {novo_status}")
        else:
            exibir_erro("Falha ao alterar status.")

    except Exception as e:
        exibir_erro(f"Erro: {e}")


def remover_funcionario():
    """Remove um funcionário (marca como demitido)"""
    exibir_cabecalho("REMOVER FUNCIONARIO")
    exibir_aviso("ATENCAO: Esta operacao ira marcar o funcionario como DEMITIDO.")

    funcionario = _selecionar_funcionario("Digite o nome do funcionario:")
    if not funcionario:
        return

    funcionario_id = str(funcionario.get("_id"))
    nome = funcionario.get("nome")

    console.print(f"\n[yellow]{ICONES['aviso']} Voce esta prestes a remover o funcionario:[/yellow]")
    console.print(f"   Nome: [cyan]{nome}[/cyan]")
    console.print(f"   Lotacao: [cyan]{funcionario.get('lotacao')}[/cyan]")

    confirmacao = pedir_texto("\nDigite 'CONFIRMAR' para prosseguir:", obrigatorio=False)

    if confirmacao != "CONFIRMAR":
        exibir_erro("Operacao cancelada.")
        return

    # Solicitar data de demissão
    data_demissao = _input_data("Data de demissao (YYYY-MM-DD, ENTER para hoje):")
    if not data_demissao:
        data_demissao = date.today()

    try:
        from datetime import datetime
        servico = FuncionarioService()

        alteracoes = {
            "status": "demitido",
            "data_demissao": datetime.combine(data_demissao, datetime.min.time())
        }

        # O decorador @registrar_historico busca valores anteriores automaticamente
        sucesso = servico.atualizar(funcionario_id, alteracoes)

        if sucesso:
            exibir_sucesso(f"Funcionario {nome} marcado como DEMITIDO.")
        else:
            exibir_erro("Falha ao remover funcionario.")

    except Exception as e:
        exibir_erro(f"Erro: {e}")


# ==================== FUNÇÕES DE ESTATÍSTICAS ====================

def exibir_estatisticas():
    """Exibe estatísticas dos funcionários (OTIMIZADO com aggregation pipeline)"""
    exibir_cabecalho("ESTATISTICAS DE FUNCIONARIOS")

    try:
        servico = FuncionarioService()

        # OTIMIZADO: Usa $facet com múltiplos $group em uma única query
        stats = servico.obter_estatisticas()

        status_count = stats.get("por_status", {})
        contrato_count = stats.get("por_contrato", {})
        lotacao_list = stats.get("por_lotacao", [])

        total = sum(status_count.values())

        console.print(f"\n[cyan]{ICONES['estatistica']} Total de funcionarios: {total}[/cyan]")

        console.print("\n[cyan]Por Status:[/cyan]")
        for status, count in sorted(status_count.items()):
            console.print(f"   {ICONES['ponto']} {status}: {count}")

        console.print("\n[cyan]Por Tipo de Contrato:[/cyan]")
        for contrato, count in sorted(contrato_count.items()):
            console.print(f"   {ICONES['ponto']} {contrato}: {count}")

        console.print("\n[cyan]Por Lotacao (top 10):[/cyan]")
        for item in lotacao_list:
            lotacao = item.get("lotacao", "desconhecida")
            count = item.get("total", 0)
            console.print(f"   {ICONES['ponto']} {lotacao}: {count}")

    except Exception as e:
        exibir_erro(f"Erro ao obter estatisticas: {e}")


# ==================== FUNÇÕES AUXILIARES ====================

def _selecionar_de_lista(servico, tipo: str, mensagem: str) -> Optional[str]:
    """
    Exibe lista de itens de um serviço e permite seleção.
    Retorna o ObjectId selecionado ou None.
    """
    try:
        if tipo == "empresa":
            resultado = servico.listar_todos()
            if resultado is None or not isinstance(resultado, dict):
                exibir_aviso(f"Erro ao listar {tipo}.")
                return None
            itens = resultado.get("dados", [])
            campo_nome = "nome"
        elif tipo == "contrato":
            itens = servico.listar_todos()
            campo_nome = "nome"
        elif tipo == "funcao":
            itens = servico.listar_todos()
            campo_nome = "nome"
        elif tipo == "horario":
            itens = servico.listar_todos()
            campo_nome = "descricao"
        elif tipo == "diretorio":
            # Primeiro tenta listar ativos
            itens = servico.listar_ativos()
            if not itens:
                # Fallback: listar todos
                resultado = servico.listar_todos()
                if resultado is None or not isinstance(resultado, dict):
                    exibir_aviso(f"Erro ao listar {tipo}.")
                    return None
                itens = resultado.get("dados", [])
                if itens:
                    logger.debug(f"Usando listar_todos para diretórios: {len(itens)} encontrados")
            campo_nome = "nome"
        else:
            return None

        if not itens:
            exibir_aviso(f"Nenhum(a) {tipo} cadastrado(a).")
            criar = pedir_confirmacao(f"Deseja criar um(a) novo(a) {tipo}?")
            if criar:
                exibir_erro("Funcao ainda nao implementada. Crie pelo menu de Referencias.")
            return None

        # Para diretórios, permitir busca/filtro
        if tipo == "diretorio":
            return _selecionar_diretorio_com_busca(itens, mensagem)

        # Preparar opções
        opcoes = [f"{item.get(campo_nome, 'N/A')}" for item in itens]

        escolha = pedir_selecao(mensagem, opcoes)

        if not escolha:
            return None

        # Encontrar item selecionado
        idx = opcoes.index(escolha)
        return str(itens[idx].get("_id"))

    except Exception as e:
        logger.error(f"Erro ao listar {tipo}: {e}")
        exibir_erro(f"Erro ao listar {tipo}: {e}")
        return None


def _selecionar_diretorio_com_busca(diretorios: List[Dict[str, Any]], mensagem: str) -> Optional[str]:
    """
    Permite selecionar um diretório com opção de busca/filtro.
    Exibe nome e caminho relativo para melhor identificação.
    """
    while True:
        console.print(f"\n[cyan]{mensagem}[/cyan]")
        console.print("[dim]Opcoes:[/dim]")
        console.print("   - Digite um NUMERO para selecionar diretamente")
        console.print("   - Digite TEXTO para filtrar/buscar diretorios")
        console.print("   - Digite 'L' para listar todos")
        console.print("   - Digite '0' ou ENTER para cancelar/pular")

        console.print(f"\n[cyan]{ICONES['diretorio']} Total de diretorios disponiveis: {len(diretorios)}[/cyan]")

        escolha = pedir_texto("Digite numero, texto para buscar ou 'L' para listar:", obrigatorio=False)

        if not escolha or escolha == "0":
            return None

        if escolha.upper() == "L":
            # Listar todos os diretórios
            _exibir_lista_diretorios(diretorios)

            num = pedir_texto("Digite o numero do diretorio (0 para cancelar):", obrigatorio=False)
            if not num or num == "0":
                continue

            try:
                idx = int(num) - 1
                if 0 <= idx < len(diretorios):
                    diretorio_selecionado = diretorios[idx]
                    exibir_sucesso(f"Selecionado: {diretorio_selecionado.get('nome')} - {diretorio_selecionado.get('caminho_relativo', '')}")
                    return str(diretorio_selecionado.get("_id"))
                else:
                    exibir_erro("Numero fora do intervalo.")
            except ValueError:
                exibir_erro("Digite um numero valido.")
            continue

        # Tentar como número primeiro
        try:
            idx = int(escolha) - 1
            if 0 <= idx < len(diretorios):
                diretorio_selecionado = diretorios[idx]
                exibir_sucesso(f"Selecionado: {diretorio_selecionado.get('nome')} - {diretorio_selecionado.get('caminho_relativo', '')}")
                return str(diretorio_selecionado.get("_id"))
            else:
                exibir_erro("Numero fora do intervalo. Use 'L' para listar todos.")
                continue
        except ValueError:
            pass

        # Buscar por texto
        termo_busca = escolha.lower()
        diretorios_filtrados = [
            d for d in diretorios
            if termo_busca in d.get("nome", "").lower()
            or termo_busca in (d.get("caminho_relativo") or "").lower()
            or termo_busca in (d.get("descricao") or "").lower()
        ]

        if not diretorios_filtrados:
            exibir_erro(f"Nenhum diretorio encontrado com '{escolha}'.")
            continue

        if len(diretorios_filtrados) == 1:
            # Seleção automática
            diretorio_selecionado = diretorios_filtrados[0]
            console.print(f"\n[green]{ICONES['sucesso']} Encontrado: {diretorio_selecionado.get('nome')}[/green]")
            console.print(f"   Caminho: {diretorio_selecionado.get('caminho_relativo', 'N/A')}")
            if pedir_confirmacao("Confirma selecao?"):
                return str(diretorio_selecionado.get("_id"))
            continue

        # Exibir resultados filtrados
        exibir_info(f"{len(diretorios_filtrados)} diretorio(s) encontrado(s):")
        _exibir_lista_diretorios(diretorios_filtrados)

        num = pedir_texto("Digite o numero do diretorio (0 para nova busca):", obrigatorio=False)
        if not num or num == "0":
            continue

        try:
            idx = int(num) - 1
            if 0 <= idx < len(diretorios_filtrados):
                diretorio_selecionado = diretorios_filtrados[idx]
                exibir_sucesso(f"Selecionado: {diretorio_selecionado.get('nome')} - {diretorio_selecionado.get('caminho_relativo', '')}")
                return str(diretorio_selecionado.get("_id"))
            else:
                exibir_erro("Numero fora do intervalo.")
        except ValueError:
            exibir_erro("Digite um numero valido.")


def _exibir_lista_diretorios(diretorios: List[Dict[str, Any]]):
    """Exibe lista formatada de diretórios com nome e caminho"""
    dados = []
    for d in diretorios:
        nome = d.get("nome", "N/A")
        caminho = (d.get("caminho_relativo") or "")
        # Campo é "status" (string "ativo"/"inativo"), não booleano "ativo"
        status_valor = str(d.get("status", "ativo")).lower()
        status_ativo = status_valor in ("ativo", "true", "1", "sim", "yes")
        status = ICONES["sucesso"] if status_ativo else ICONES["erro"]
        dados.append([nome, caminho, status])

    exibir_tabela(
        "Diretorios",
        ["Nome", "Caminho Relativo", "Status"],
        dados
    )


def _selecionar_multiplas_empresas(mensagem: str) -> List[str]:
    """
    Permite selecionar múltiplas empresas de uma lista.
    Retorna lista de ObjectIds selecionados.
    """
    servico_empresa = EmpresaService()

    try:
        resultado = servico_empresa.listar_todos()
        if resultado is None or not isinstance(resultado, dict):
            exibir_erro("Erro ao listar empresas.")
            return []
        empresas = resultado.get("dados", [])

        if not empresas:
            exibir_aviso("Nenhuma empresa cadastrada.")
            return []

        console.print(f"\n[cyan]{mensagem}[/cyan]")
        console.print("[dim]Dica: Use Espaco para marcar, Enter para confirmar[/dim]\n")

        # Preparar opções para seleção múltipla
        opcoes_empresas = [f"{emp.get('nome', 'N/A')}" for emp in empresas]

        selecionadas = pedir_selecao_multipla(
            "Selecione as empresas:",
            opcoes_empresas,
            minimo=1
        )

        if not selecionadas:
            return []

        # Mapear de volta para IDs
        ids_selecionados = []
        for sel in selecionadas:
            idx = opcoes_empresas.index(sel)
            ids_selecionados.append(str(empresas[idx].get("_id")))

        exibir_sucesso(f"{len(ids_selecionados)} empresa(s) selecionada(s):")
        for sel in selecionadas:
            console.print(f"   {ICONES['ponto']} {sel}")

        return ids_selecionados

    except Exception as e:
        logger.error(f"Erro ao listar empresas: {e}")
        exibir_erro(f"Erro ao listar empresas: {e}")
        return []


def _selecionar_funcionario(mensagem: str) -> Optional[Dict[str, Any]]:
    """Busca e permite selecionar um funcionário por nome"""
    nome_busca = pedir_texto(mensagem)
    if not nome_busca:
        exibir_erro("Nome nao pode ser vazio.")
        return None

    try:
        servico = FuncionarioService()
        funcionarios = servico.buscar_todos_por_nome(nome_busca)

        if not funcionarios:
            # Tentar busca parcial usando regex
            import unicodedata
            nfkd = unicodedata.normalize('NFKD', nome_busca)
            nome_normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)]).lower()

            cursor = servico.colecao.find({
                "nome_normalizado": {"$regex": nome_normalizado, "$options": "i"}
            })
            funcionarios = list(cursor)

        if not funcionarios:
            exibir_erro(f"Nenhum funcionario encontrado com '{nome_busca}'.")
            return None

        if len(funcionarios) == 1:
            return funcionarios[0]

        # Múltiplos encontrados
        exibir_info(f"{len(funcionarios)} funcionario(s) encontrado(s):")

        opcoes = [f"{f.get('nome', 'N/A')} | {f.get('lotacao', 'N/A')} | {f.get('status', 'N/A')}" for f in funcionarios]

        escolha = pedir_selecao("Selecione o funcionario:", opcoes)

        if not escolha:
            return None

        idx = opcoes.index(escolha)
        return funcionarios[idx]

    except Exception as e:
        logger.error(f"Erro ao buscar funcionário: {e}")
        exibir_erro(f"Erro: {e}")
        return None


def _exibir_lista_funcionarios(funcionarios: List[Dict[str, Any]]):
    """Exibe lista formatada de funcionários"""
    dados = []
    for func in funcionarios:
        dados.append([
            func.get("nome", "N/A"),
            func.get("lotacao", "N/A"),
            func.get("status", "N/A")
        ])

    exibir_tabela(
        "Funcionarios",
        ["Nome", "Lotacao", "Status"],
        dados
    )


def _exibir_detalhes_funcionario(funcionario: Dict[str, Any]):
    """Exibe detalhes completos de um funcionário (OTIMIZADO com aggregation pipeline)"""

    # OTIMIZADO: Buscar funcionário com todos os relacionamentos em 1 query
    try:
        servico = FuncionarioService()
        funcionario_id = str(funcionario.get('_id'))

        # Buscar com aggregation pipeline
        func_completo = servico.buscar_com_relacionamentos(funcionario_id)

        if not func_completo:
            logger.warning(f"Funcionário {funcionario_id} não encontrado")
            func_completo = funcionario
    except Exception as e:
        logger.warning(f"Erro ao buscar relacionamentos: {e}")
        func_completo = funcionario

    # Construir conteúdo do painel
    linhas = []
    linhas.append(f"[chave]ID:[/chave] {func_completo.get('_id')}")
    linhas.append(f"[chave]Nome:[/chave] [cyan]{func_completo.get('nome')}[/cyan]")
    linhas.append(f"[chave]PIS:[/chave] {func_completo.get('pis') or '(nao informado)'}")
    linhas.append(f"[chave]CPF:[/chave] {func_completo.get('cpf') or '(nao informado)'}")
    linhas.append(f"[chave]Lotacao:[/chave] {func_completo.get('lotacao')}")
    linhas.append(f"[chave]Tipo Contrato:[/chave] {func_completo.get('contrato')}")
    linhas.append(f"[chave]Status:[/chave] [yellow]{func_completo.get('status')}[/yellow]")

    # Exibir referências (já vêm populadas do aggregation)
    try:
        funcao_info = func_completo.get("funcao_info")
        if funcao_info:
            linhas.append(f"[chave]Funcao:[/chave] {funcao_info.get('nome')}")

        horario_info = func_completo.get("horario_info")
        if horario_info:
            linhas.append(f"[chave]Horario:[/chave] {horario_info.get('descricao')}")

        contrato_info = func_completo.get("contrato_info")
        if contrato_info:
            linhas.append(f"[chave]Contrato Empresa:[/chave] {contrato_info.get('nome')}")

        diretorio_info = func_completo.get("diretorio_info")
        if diretorio_info:
            linhas.append(f"[chave]Diretorio:[/chave] {diretorio_info.get('nome')}")
        else:
            diretorio_legado = func_completo.get("diretorio_interno")
            if diretorio_legado:
                linhas.append(f"[chave]Diretorio (legado):[/chave] {diretorio_legado}")
            else:
                linhas.append(f"[chave]Diretorio:[/chave] (auto-gerado)")

        empresa_info = func_completo.get("empresa_info")
        if empresa_info:
            linhas.append(f"[chave]Empresas:[/chave] {empresa_info.get('nome')}")

    except Exception as e:
        logger.debug(f"Erro ao exibir referências: {e}")

    # Datas
    data_admissao = func_completo.get("data_admissao")
    if data_admissao:
        if hasattr(data_admissao, 'strftime'):
            linhas.append(f"[chave]Data Admissao:[/chave] {data_admissao.strftime('%d/%m/%Y')}")
        else:
            linhas.append(f"[chave]Data Admissao:[/chave] {data_admissao}")

    data_nascimento = func_completo.get("data_nascimento")
    if data_nascimento:
        if hasattr(data_nascimento, 'strftime'):
            linhas.append(f"[chave]Data Nascimento:[/chave] {data_nascimento.strftime('%d/%m/%Y')}")
        else:
            linhas.append(f"[chave]Data Nascimento:[/chave] {data_nascimento}")

    conteudo = "\n".join(linhas)
    exibir_painel(conteudo, titulo="Detalhes do Funcionario", estilo_borda="cyan")


def _input_data(mensagem: str) -> Optional[date]:
    """Solicita uma data do usuário no formato YYYY-MM-DD"""
    data_str = pedir_texto(mensagem, obrigatorio=False)
    if not data_str:
        return None

    try:
        return date.fromisoformat(data_str)
    except ValueError:
        exibir_aviso("Data invalida. Use o formato YYYY-MM-DD")
        return None


# ==================== FUNÇÕES DE EXPORTAÇÃO ====================

def exportar_funcionarios_json():
    """
    Exporta todos os funcionários para um arquivo JSON com dados completos,
    incluindo TODOS os dados relacionados das coleções vinculadas.
    """
    import json
    from datetime import datetime
    from pathlib import Path

    exibir_cabecalho("EXPORTAR FUNCIONARIOS (JSON COMPLETO)")

    exibir_info("""Esta funcao exporta todos os funcionarios com dados COMPLETOS:
   - Dados basicos do funcionario (todos os campos)
   - Empresas vinculadas (todos os dados)
   - Contrato da empresa (todos os dados)
   - Funcao (todos os dados)
   - Horario (todos os dados)
   - Diretorio (todos os dados)
   - Folhas de ponto existentes (resumo com status)
""")

    # Opções de filtro
    filtro_opcao = pedir_selecao(
        "Filtrar por status:",
        ["Apenas ativos (padrao)", "Apenas inativos", "Todos"]
    )

    if not filtro_opcao:
        filtro_opcao = "Apenas ativos (padrao)"

    # Caminho do arquivo
    exibir_info("Onde salvar o arquivo?")
    console.print("   [dim]Deixe vazio para salvar no diretorio atual[/dim]")

    caminho_input = pedir_texto("Caminho completo ou nome do arquivo:", obrigatorio=False)

    if not caminho_input:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho_input = f"funcionarios_export_{timestamp}.json"

    if not caminho_input.endswith('.json'):
        caminho_input += '.json'

    caminho = Path(caminho_input)

    try:
        exibir_info("Buscando funcionarios e dados relacionados...")

        servico_funcionario = FuncionarioService()

        # Importar serviço de folha de ponto (opcional)
        try:
            from src.services.folha_ponto_service import FolhaDePontoService
            servico_folha = FolhaDePontoService()
            folha_disponivel = True
        except:
            folha_disponivel = False

        # Montar filtro
        filtro = {}
        if "ativos" in filtro_opcao.lower():
            filtro["status"] = StatusFuncionario.ATIVO.value
        elif "inativos" in filtro_opcao.lower():
            filtro["status"] = {"$ne": StatusFuncionario.ATIVO.value}

        # OTIMIZADO: Usa exportar_com_relacionamentos()
        console.print("   [dim]Usando aggregation pipeline otimizada...[/dim]")
        funcionarios = servico_funcionario.exportar_com_relacionamentos(
            filtro=filtro,
            limit=5000
        )

        if not funcionarios:
            exibir_info("Nenhum funcionario encontrado com os filtros aplicados.")
            return

        exibir_sucesso(f"{len(funcionarios)} funcionario(s) encontrado(s)")
        exibir_info("Processando dados relacionados...")

        # Processar cada funcionário
        funcionarios_exportados = []
        total = len(funcionarios)

        for idx, func in enumerate(funcionarios, 1):
            if idx % 10 == 0:
                console.print(f"   [dim]Processando {idx}/{total}...[/dim]")

            # Dados COMPLETOS do funcionário
            func_export = {
                "_id": str(func.get("_id")),
                "nome": func.get("nome"),
                "nome_normalizado": func.get("nome_normalizado"),
                "pis": func.get("pis"),
                "cpf": func.get("cpf"),
                "lotacao": func.get("lotacao"),
                "contrato_tipo": func.get("contrato"),
                "status": func.get("status"),
                "data_admissao": _formatar_data_export(func.get("data_admissao")),
                "data_nascimento": _formatar_data_export(func.get("data_nascimento")),
                "data_demissao": _formatar_data_export(func.get("data_demissao")),
                "diretorio_interno_legado": func.get("diretorio_interno"),
                "versao": func.get("versao"),
                "criado_em": _formatar_data_export(func.get("criado_em")),
                "atualizado_em": _formatar_data_export(func.get("atualizado_em")),
                "historico_alteracoes": _formatar_historico(func.get("historico_alteracoes", [])),
            }

            # Empresas (já vêm populadas)
            empresas_detalhes = []
            empresa_info = func.get("empresa_info")

            if empresa_info:
                empresas_detalhes.append({
                    "_id": str(empresa_info.get("_id")),
                    "nome": empresa_info.get("nome"),
                    "cnpj": empresa_info.get("cnpj"),
                    "atividade": empresa_info.get("atividade"),
                    "endereco": empresa_info.get("endereco"),
                    "telefone": empresa_info.get("telefone"),
                    "email": empresa_info.get("email"),
                    "responsavel": empresa_info.get("responsavel"),
                    "status": empresa_info.get("status"),
                    "incompleto": empresa_info.get("incompleto"),
                    "criado_em": _formatar_data_export(empresa_info.get("criado_em")),
                    "atualizado_em": _formatar_data_export(empresa_info.get("atualizado_em")),
                })

            func_export["empresas"] = empresas_detalhes

            # Contrato
            contrato_info = func.get("contrato_info")
            if contrato_info:
                func_export["contrato_empresa"] = {
                    "_id": str(contrato_info.get("_id")),
                    "nome": contrato_info.get("nome"),
                    "numero_contrato": contrato_info.get("numero_contrato"),
                    "numero_processo": contrato_info.get("numero_processo"),
                    "orgao": contrato_info.get("orgao"),
                    "localidade": contrato_info.get("localidade"),
                    "inicio_vigencia": _formatar_data_export(contrato_info.get("inicio_vigencia")),
                    "fim_vigencia": _formatar_data_export(contrato_info.get("fim_vigencia")),
                    "status": contrato_info.get("status"),
                    "ordem": contrato_info.get("ordem"),
                    "auto_criado": contrato_info.get("auto_criado"),
                    "criado_em": _formatar_data_export(contrato_info.get("criado_em")),
                    "atualizado_em": _formatar_data_export(contrato_info.get("atualizado_em")),
                }
            else:
                func_export["contrato_empresa"] = None

            # Função
            funcao_info = func.get("funcao_info")
            if funcao_info:
                func_export["funcao"] = {
                    "_id": str(funcao_info.get("_id")),
                    "nome": funcao_info.get("nome"),
                    "funcao_geral": funcao_info.get("funcao_geral"),
                    "status": funcao_info.get("status"),
                    "ordem": funcao_info.get("ordem"),
                    "auto_criado": funcao_info.get("auto_criado"),
                    "criado_em": _formatar_data_export(funcao_info.get("criado_em")),
                    "atualizado_em": _formatar_data_export(funcao_info.get("atualizado_em")),
                }
            else:
                func_export["funcao"] = None

            # Horário
            horario_info = func.get("horario_info")
            if horario_info:
                func_export["horario"] = {
                    "_id": str(horario_info.get("_id")),
                    "descricao": horario_info.get("descricao"),
                    "entrada1": horario_info.get("entrada1"),
                    "saida1": horario_info.get("saida1"),
                    "entrada2": horario_info.get("entrada2"),
                    "saida2": horario_info.get("saida2"),
                    "total_horas": horario_info.get("total_horas"),
                    "dias_trabalho_mes": horario_info.get("dias_trabalho_mes"),
                    "status": horario_info.get("status"),
                    "ordem": horario_info.get("ordem"),
                    "auto_criado": horario_info.get("auto_criado"),
                    "criado_em": _formatar_data_export(horario_info.get("criado_em")),
                    "atualizado_em": _formatar_data_export(horario_info.get("atualizado_em")),
                }
            else:
                func_export["horario"] = None

            # Diretório
            diretorio_info = func.get("diretorio_info")
            if diretorio_info:
                func_export["diretorio"] = {
                    "_id": str(diretorio_info.get("_id")),
                    "nome": diretorio_info.get("nome"),
                    "descricao": diretorio_info.get("descricao"),
                    "caminho_relativo": diretorio_info.get("caminho_relativo"),
                    "contrato_id": str(diretorio_info.get("contrato_id")) if diretorio_info.get("contrato_id") else None,
                    "status": diretorio_info.get("status"),
                    "ordem": diretorio_info.get("ordem"),
                    "auto_criado": diretorio_info.get("auto_criado"),
                    "criado_em": _formatar_data_export(diretorio_info.get("criado_em")),
                    "atualizado_em": _formatar_data_export(diretorio_info.get("atualizado_em")),
                }
            else:
                diretorio_legado = func.get("diretorio_interno")
                if diretorio_legado:
                    func_export["diretorio"] = {"legado": diretorio_legado}
                else:
                    func_export["diretorio"] = None

            # Folhas de ponto
            if folha_disponivel:
                try:
                    folhas = servico_folha.listar_por_funcionario(str(func.get("_id")))
                    if folhas:
                        func_export["folhas_ponto"] = {
                            "total": len(folhas),
                            "meses": [{
                                "mes_referencia": f.get("mes_referencia"),
                                "status": f.get("status"),
                                "data_criacao": _formatar_data_export(f.get("data_criacao")),
                            } for f in folhas[:24]]
                        }
                    else:
                        func_export["folhas_ponto"] = {"total": 0, "meses": []}
                except Exception as e:
                    logger.error(f"Erro ao buscar folhas de ponto do funcionário {func.get('_id')}: {e}")
                    func_export["folhas_ponto"] = {"total": 0, "meses": []}
            else:
                func_export["folhas_ponto"] = {"total": 0, "meses": []}

            funcionarios_exportados.append(func_export)

        # Estatísticas para metadata
        estatisticas = {
            "por_status": {},
            "por_contrato_tipo": {},
            "por_funcao_geral": {},
            "por_empresa": {},
        }

        for func in funcionarios_exportados:
            status = func.get("status", "desconhecido")
            estatisticas["por_status"][status] = estatisticas["por_status"].get(status, 0) + 1

            contrato_tipo = func.get("contrato_tipo", "desconhecido")
            estatisticas["por_contrato_tipo"][contrato_tipo] = estatisticas["por_contrato_tipo"].get(contrato_tipo, 0) + 1

            funcao = func.get("funcao")
            if funcao:
                funcao_geral = funcao.get("funcao_geral") or "sem_categoria"
                estatisticas["por_funcao_geral"][funcao_geral] = estatisticas["por_funcao_geral"].get(funcao_geral, 0) + 1

            for emp in func.get("empresas", []):
                emp_nome = emp.get("nome", "desconhecida")
                estatisticas["por_empresa"][emp_nome] = estatisticas["por_empresa"].get(emp_nome, 0) + 1

        # Montar documento final
        documento_export = {
            "metadata": {
                "exportado_em": datetime.now().isoformat(),
                "total_funcionarios": len(funcionarios_exportados),
                "filtro_aplicado": {
                    "Apenas ativos (padrao)": "apenas_ativos",
                    "Apenas inativos": "apenas_inativos",
                    "Todos": "todos"
                }.get(filtro_opcao, "todos"),
                "versao_sistema": "1.0",
                "estatisticas": estatisticas
            },
            "funcionarios": funcionarios_exportados
        }

        # Salvar arquivo
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(documento_export, f, ensure_ascii=False, indent=2)

        # Calcular tamanho
        tamanho_bytes = caminho.stat().st_size
        if tamanho_bytes > 1024 * 1024:
            tamanho_str = f"{tamanho_bytes / (1024 * 1024):.2f} MB"
        elif tamanho_bytes > 1024:
            tamanho_str = f"{tamanho_bytes / 1024:.2f} KB"
        else:
            tamanho_str = f"{tamanho_bytes} bytes"

        exibir_cabecalho("EXPORTACAO CONCLUIDA COM SUCESSO!")
        console.print(f"\n[cyan]{ICONES['diretorio']} Arquivo salvo:[/cyan] {caminho.absolute()}")
        console.print(f"[cyan]{ICONES['estatistica']} Total de funcionarios:[/cyan] {len(funcionarios_exportados)}")
        console.print(f"[cyan]{ICONES['dados']} Tamanho do arquivo:[/cyan] {tamanho_str}")

        # Estatísticas resumidas
        console.print(f"\n[cyan]{ICONES['relatorio']} Estatisticas:[/cyan]")
        console.print(f"   {ICONES['ponto']} Por status: {', '.join([f'{k}: {v}' for k, v in estatisticas['por_status'].items()])}")
        console.print(f"   {ICONES['ponto']} Por contrato: {', '.join([f'{k}: {v}' for k, v in estatisticas['por_contrato_tipo'].items()])}")
        console.print(f"   {ICONES['ponto']} Empresas: {len(estatisticas['por_empresa'])} empresas diferentes")
        console.print(f"   {ICONES['ponto']} Funcoes: {len(estatisticas['por_funcao_geral'])} categorias de funcao")

        exibir_info("O arquivo JSON contem TODOS os dados de cada funcionario")
        console.print("   [dim]incluindo campos de controle, timestamps e historico.[/dim]")

    except Exception as e:
        logger.error(f"Erro ao exportar funcionários: {e}")
        exibir_erro(f"Erro ao exportar: {e}")


def _formatar_data_export(data) -> Optional[str]:
    """Formata uma data para exportação (ISO format)"""
    if data is None:
        return None
    if hasattr(data, 'isoformat'):
        return data.isoformat()
    return str(data)


def _formatar_historico(historico: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Formata o histórico de alterações para exportação JSON.
    Converte objetos datetime para strings ISO.
    """
    if not historico:
        return []

    from datetime import datetime

    historico_formatado = []
    for entrada in historico:
        entrada_formatada = {}
        for chave, valor in entrada.items():
            if isinstance(valor, datetime):
                entrada_formatada[chave] = valor.isoformat()
            elif isinstance(valor, dict):
                entrada_formatada[chave] = _formatar_dict_recursivo(valor)
            else:
                entrada_formatada[chave] = valor
        historico_formatado.append(entrada_formatada)

    return historico_formatado


def _formatar_dict_recursivo(d: Dict[str, Any]) -> Dict[str, Any]:
    """Formata recursivamente um dicionário, convertendo datetime para string."""
    from datetime import datetime

    resultado = {}
    for chave, valor in d.items():
        if isinstance(valor, datetime):
            resultado[chave] = valor.isoformat()
        elif isinstance(valor, dict):
            resultado[chave] = _formatar_dict_recursivo(valor)
        elif isinstance(valor, list):
            resultado[chave] = [
                _formatar_dict_recursivo(item) if isinstance(item, dict)
                else (item.isoformat() if isinstance(item, datetime) else item)
                for item in valor
            ]
        else:
            resultado[chave] = valor
    return resultado
