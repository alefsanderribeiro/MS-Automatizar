"""Pydantic model fixtures for testing."""

import pytest
from bson import ObjectId
from datetime import datetime, date, timezone, timedelta
from typing import List


# ==================== Funcionario Fixtures ====================

@pytest.fixture
def funcionario_completo():
    """
    Complete funcionario instance with all required fields.

    Returns:
        FuncionarioMongoDB instance with complete data
    """
    from src.models.funcionario_models import (
        FuncionarioMongoDB,
        TipoContrato,
        StatusFuncionario,
        StatusCadastro
    )

    return FuncionarioMongoDB(
        nome="João Silva",
        pis="12345678901",
        cpf="123.456.789-00",
        lotacao="TI",
        contrato=TipoContrato.CLT,
        contrato_empresa_id=ObjectId(),
        horario_id=ObjectId(),
        funcao_id=ObjectId(),
        diretorio_id=ObjectId(),
        empresas_ids=[ObjectId()],
        data_nascimento=date(1990, 1, 15),
        data_admissao=date(2020, 1, 15),
        status=StatusFuncionario.ATIVO,
        status_cadastro=StatusCadastro.COMPLETO
    )


@pytest.fixture
def funcionario_incompleto():
    """
    Incomplete funcionario instance (autocreate scenario).

    Returns:
        FuncionarioMongoDB instance with minimal data
    """
    from src.models.funcionario_models import (
        FuncionarioMongoDB,
        StatusFuncionario,
        StatusCadastro
    )

    return FuncionarioMongoDB(
        nome="Maria Santos",
        pis="98765432109",
        cpf="987.654.321-00",
        status=StatusFuncionario.ATIVO,
        status_cadastro=StatusCadastro.INCOMPLETO,
        empresas_ids=[]
    )


@pytest.fixture
def funcionario_pendente_revisao():
    """
    Funcionario marked for review.

    Returns:
        FuncionarioMongoDB instance with pendente_revisao status
    """
    from src.models.funcionario_models import (
        FuncionarioMongoDB,
        StatusFuncionario,
        StatusCadastro
    )

    func = FuncionarioMongoDB(
        nome="Carlos Oliveira",
        pis="55555555555",
        status=StatusFuncionario.ATIVO,
        status_cadastro=StatusCadastro.PENDENTE_REVISAO,
        empresas_ids=[]
    )

    func.marcar_pendente_revisao("Dados inconsistentes detectados")
    return func


@pytest.fixture
def funcionario_factory():
    """
    Factory for creating funcionario instances with variations.

    Usage:
        def test_example(funcionario_factory):
            func = funcionario_factory(nome="João", status="ativo")
    """
    def _create_funcionario(
        nome: str = "Funcionário Teste",
        status: str = "ativo",
        status_cadastro: str = "completo",
        **kwargs
    ):
        from src.models.funcionario_models import (
            FuncionarioMongoDB,
            FuncionarioBuilder,
            TipoContrato,
            StatusFuncionario,
            StatusCadastro
        )

        builder = FuncionarioBuilder()
        builder.set_identificacao(
            nome=nome,
            pis=kwargs.get("pis", "12345678901"),
            cpf=kwargs.get("cpf", "123.456.789-00")
        )

        if status_cadastro == "completo":
            builder.set_contratacao(
                lotacao=kwargs.get("lotacao", "TI"),
                contrato=TipoContrato.CLT,
                contrato_empresa_id=kwargs.get("contrato_empresa_id", ObjectId()),
                horario_id=kwargs.get("horario_id", ObjectId()),
                funcao_id=kwargs.get("funcao_id", ObjectId()),
                data_admissao=kwargs.get("data_admissao", date.today())
            )
            builder.set_status_cadastro(StatusCadastro.COMPLETO)
        else:
            builder.set_status_cadastro(StatusCadastro.INCOMPLETO)

        builder.set_status(StatusFuncionario(status))

        return builder.build()

    return _create_funcionario


# ==================== Empresa Fixtures ====================

@pytest.fixture
def empresa_completa():
    """
    Complete empresa instance with all data.

    Returns:
        EmpresaMongoDB instance with complete data
    """
    from src.models.empresa_models import (
        EmpresaMongoDB,
        EmpresaBuilder,
        StatusEmpresa
    )

    return (EmpresaBuilder()
        .set_nome("Solucoes Dinamicas Consultoria")
        .set_cnpj("12.345.678/0001-90")
        .set_atividade("Consultoria em TI")
        .set_endereco("Rua A, 123 - São Paulo, SP")
        .set_contato("(11) 9999-9999", "contato@solucoesdinamicas.com.br")
        .set_responsavel("João Pereira")
        .set_status(StatusEmpresa.ATIVA)
        .set_nome_sigla("M&S")
        .set_nome_simplificado("Solucoes Dinamicas")
        .build()
    )


@pytest.fixture
def empresa_incompleta():
    """
    Incomplete empresa instance (autocreate scenario).

    Returns:
        EmpresaMongoDB instance with minimal data
    """
    from src.models.empresa_models import (
        EmpresaBuilder,
        StatusEmpresa
    )

    return (EmpresaBuilder()
        .set_nome("Empresa Teste Ltda")
        .marcar_como_incompleta()
        .build()
    )


@pytest.fixture
def empresa_factory():
    """
    Factory for creating empresa instances with variations.

    Usage:
        def test_example(empresa_factory):
            emp = empresa_factory(nome="Teste Corp", status="ativa")
    """
    def _create_empresa(
        nome: str = "Empresa Teste",
        status: str = "ativa",
        incompleto: bool = False,
        **kwargs
    ):
        from src.models.empresa_models import (
            EmpresaBuilder,
            StatusEmpresa
        )

        builder = EmpresaBuilder().set_nome(nome)

        if incompleto:
            builder.marcar_como_incompleta()
        else:
            builder.set_status(StatusEmpresa(status))

            if kwargs.get("cnpj"):
                builder.set_cnpj(kwargs["cnpj"])
            if kwargs.get("atividade"):
                builder.set_atividade(kwargs["atividade"])
            if kwargs.get("endereco"):
                builder.set_endereco(kwargs["endereco"])

        return builder.build()

    return _create_empresa


# ==================== Folha de Ponto Fixtures ====================

@pytest.fixture
def folha_ponto_sample():
    """
    Sample folha de ponto with dias preenchidos.

    Returns:
        FolhaDePontoMongoDB instance with sample data
    """
    from src.models.folha_de_ponto_models import (
        FolhaDePontoMongoDB,
        FolhaDePontoData,
        DiaFolhaPonto,
        DiaSemana,
        TipoDia,
        StatusFolhaPonto
    )

    # Create sample days
    dias = [
        DiaFolhaPonto(
            numero_dia=1,
            data=datetime(2025, 1, 1),
            dia_semana=DiaSemana.QUARTA,
            hora_entrada="08:00",
            hora_intervalo_inicio="12:00",
            hora_intervalo_fim="13:00",
            hora_saida="17:00",
            total_horas_trabalhadas="08:00",
            tipo_dia=TipoDia.NORMAL,
            preenchido_manualmente=True,
            analise_ia_processada=False
        ),
        DiaFolhaPonto(
            numero_dia=2,
            data=datetime(2025, 1, 2),
            dia_semana=DiaSemana.QUINTA,
            hora_entrada="08:00",
            hora_intervalo_inicio="12:00",
            hora_intervalo_fim="13:00",
            hora_saida="17:00",
            total_horas_trabalhadas="08:00",
            tipo_dia=TipoDia.NORMAL,
            preenchido_manualmente=True,
            analise_ia_processada=False
        )
    ]

    folha_data = FolhaDePontoData(
        mes_referencia="2025-01",
        data_inicio=date(2025, 1, 1),
        data_fim=date(2025, 1, 31),
        dias=dias,
        total_horas_mes="160:00",
        total_faltas=0,
        total_feriados=2,
        total_finais_semana=8,
        preenchimento_concluido=True,
        analise_ia_concluida=False
    )

    return FolhaDePontoMongoDB(
        funcionario_id=ObjectId(),
        empresa_id=ObjectId(),
        mes_referencia="2025-01",
        folha_data=folha_data,
        caminho_arquivo_gerado=r"C:\output\folha_2025_01.pdf",
        status=StatusFolhaPonto.PREENCHIDA
    )


@pytest.fixture
def folha_ponto_vazia():
    """
    Empty folha de ponto (just created, no dias filled).

    Returns:
        FolhaDePontoMongoDB instance with empty dias
    """
    from src.models.folha_de_ponto_models import (
        FolhaDePontoMongoDB,
        FolhaDePontoData,
        StatusFolhaPonto
    )

    folha_data = FolhaDePontoData(
        mes_referencia="2025-01",
        data_inicio=date(2025, 1, 1),
        data_fim=date(2025, 1, 31),
        dias=[],
        preenchimento_concluido=False,
        analise_ia_concluida=False
    )

    return FolhaDePontoMongoDB(
        funcionario_id=ObjectId(),
        empresa_id=ObjectId(),
        mes_referencia="2025-01",
        folha_data=folha_data,
        status=StatusFolhaPonto.CRIADA
    )


@pytest.fixture
def dia_folha_factory():
    """
    Factory for creating DiaFolhaPonto instances.

    Usage:
        def test_example(dia_folha_factory):
            dia = dia_folha_factory(numero_dia=1, tipo_dia="FERIADO")
    """
    def _create_dia(
        numero_dia: int = 1,
        tipo_dia: str = "NORMAL",
        preenchido: bool = False,
        **kwargs
    ):
        from src.models.folha_de_ponto_models import (
            DiaFolhaPonto,
            DiaSemana,
            TipoDia
        )

        return DiaFolhaPonto(
            numero_dia=numero_dia,
            data=kwargs.get("data", datetime(2025, 1, numero_dia)),
            dia_semana=kwargs.get("dia_semana", DiaSemana.SEGUNDA),
            hora_entrada=kwargs.get("hora_entrada") if preenchido else None,
            hora_intervalo_inicio=kwargs.get("hora_intervalo_inicio") if preenchido else None,
            hora_intervalo_fim=kwargs.get("hora_intervalo_fim") if preenchido else None,
            hora_saida=kwargs.get("hora_saida") if preenchido else None,
            total_horas_trabalhadas=kwargs.get("total_horas_trabalhadas") if preenchido else None,
            observacoes=kwargs.get("observacoes"),
            tipo_dia=TipoDia(tipo_dia),
            preenchido_manualmente=preenchido,
            analise_ia_processada=kwargs.get("analise_ia_processada", False)
        )

    return _create_dia
