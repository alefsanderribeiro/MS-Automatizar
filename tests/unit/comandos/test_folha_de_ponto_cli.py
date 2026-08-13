"""
SMOKE TEST do CLI de `folha_de_ponto`.

Objetivo: garantir que os subcomandos de CONFIGURAÇÃO DE ENVIO
(`envio-config-*`) parseiam e executam `handle_folha_de_ponto` sem
quebrar por NameError/ImportError ou outros erros de importação de runtime.

Regressão coberta:
- `envio-config-editar` usava `List[str]` como anotação mas não tinha
  `from typing import List` -> NameError em runtime. Este teste pegaria isso.
- Cobertura de todos os subcomandos envio-config-*: criar, listar, buscar,
  editar, excluir, reativar, importar, validar, stats.

NUNCA toca em rede/banco real: o serviço `config_envio_folha_ponto_service`
é 100% mockado e `input` é substituído.
"""

import argparse
import pytest

from src.comandos.folha_de_ponto import (
    folha_de_ponto_subcommands,
    handle_folha_de_ponto,
)


# ==================== HELPERS ====================

def _montar_parser():
    """Parser de argparse real (mesma fiação do main.py) para subcomandos."""
    parser = argparse.ArgumentParser(description="teste")
    subparsers = parser.add_subparsers(dest="command")
    folha_de_ponto_subcommands(subparsers)
    return parser


# Subcomandos COM interação (input) — o mock de input precisa fornecer valores.
SUBCOMANDOS_INTERATIVOS = ("envio-config-criar", "envio-config-editar", "envio-config-excluir")

# Subcomandos sem interação de input (chamam o service direto).
SUBCOMANDOS_NAO_INTERATIVOS = (
    "envio-config-listar",
    "envio-config-buscar",
    "envio-config-reativar",
    "envio-config-importar",
    "envio-config-validar",
    "envio-config-stats",
)

# Todos os subcomandos envio-config-* que devem existir no parser.
TODOS_SUBCOMANDOS = SUBCOMANDOS_INTERATIVOS + SUBCOMANDOS_NAO_INTERATIVOS + ("envio-config-buscar",)


def _service_mock(mocker):
    """Mocka `config_envio_folha_ponto_service` no módulo-fonte (fonte da
    importação dentro do handler), disponível por padrão."""
    svc = mocker.patch(
        "src.services.config_envio_folha_ponto_service.config_envio_folha_ponto_service",
        autospec=True,
    )
    svc.disponivel = True
    # Returns padrão seguros para os handlers.
    svc.listar.return_value = []
    svc.buscar_por_id.return_value = {
        "nome": "João Teste",
        "identificador": "linha-1",
        "emails": [],
        "telefones": [],
        "grupos_whatsapp": [],
        "enviar_email": "S",
        "enviar_whatsapp": "N",
        "enviar_grupo_whatsapp": "N",
        "enviar_impresso": "N",
    }
    svc.criar.return_value = "novo_id_123"
    svc.atualizar.return_value = True
    svc.excluir.return_value = True
    svc.reativar.return_value = True
    # Buscas retornam um documento (para --buscar emitir saída).
    _doc = {
        "_id": "abc123",
        "identificador": "linha-1",
        "nome": "João Teste",
        "emails": [],
        "telefones": [],
        "grupos_whatsapp": [],
        "enviar_email": "S",
        "enviar_whatsapp": "N",
        "enviar_grupo_whatsapp": "N",
        "enviar_impresso": "N",
        "empresa": "EMPRESA",
        "local_contrato_polo": "LOCAL",
        "diretorio_geral": "/g",
        "diretorio_especifico": "/e",
        "ativo": True,
        "excluida": False,
        "origem": "planilha",
    }
    svc.buscar_por_nome.return_value = [_doc]
    svc.buscar_por_empresa.return_value = [_doc]
    svc.buscar_por_local.return_value = [_doc]
    svc.buscar_por_identificador.return_value = _doc
    svc.importar_da_planilha.return_value = {
        "total_planilha": 0, "criados": 0, "atualizados": 0,
        "pulados": 0, "erros": 0,
    }
    svc.validar.return_value = {"total_configs": 0, "valida": True, "problemas": [], "avisos": []}
    svc.contar.return_value = {"total": 0, "ativas": 0, "inativas": 0, "excluidas": 0}
    return svc


# ==================== TESTES DE PARSE (fiabilidade do argparse) ====================

class TestParseSubcomandosEnvioConfig:
    """Cada subcomando deve existir e parsear sem erro."""

    @pytest.mark.parametrize("subcomando", TODOS_SUBCOMANDOS)
    def test_parseia_subcomando(self, subcomando):
        parser = _montar_parser()
        argv = ["folha_de_ponto", subcomando]
        if subcomando in ("envio-config-editar", "envio-config-excluir", "envio-config-reativar"):
            argv.append("abc123")
        args = parser.parse_args(argv)
        assert args.command == "folha_de_ponto"
        assert args.subcommand == subcomando


# ==================== SMOKE TEST — execução dos handlers ====================

class TestSmokeHandlersEnvioConfig:
    """Chamada a handle_folha_de_ponto não pode levantar NameError/ImportError."""

    @pytest.mark.parametrize(
        "subcomando, argv_extra, inputs",
        [
            # --- interativos ---
            ("envio-config-criar", [], [
                "id-1", "João", "joao@x.com", "99999", "Grupo A",
                "S", "N", "N", "N",
                "Empresa", "Local", "/dir", "/dir2",
            ]),
            # manter tudo igual (nenhuma alteração -> "Nenhuma alteração.")
            ("envio-config-editar", ["abc123"], ["\n", "\n", "\n", "\n", "\n", "\n", "\n"]),
            ("envio-config-excluir", ["abc123"], ["SIM"]),
            # --- não-interativos (apenas service mockado) ---
            ("envio-config-listar", [], []),
            ("envio-config-listar", ["--json"], []),
            ("envio-config-buscar", ["--nome", "Joao"], []),
            ("envio-config-reativar", ["abc123"], []),
            ("envio-config-importar", [], []),
            ("envio-config-importar", ["--sobrescrever", "--marcar-removidos"], []),
            ("envio-config-validar", [], []),
            ("envio-config-stats", [], []),
        ],
    )
    def test_handler_executa_sem_erro(self, mocker, capsys, subcomando, argv_extra, inputs):
        _service_mock(mocker)
        # Substitui input() por valores sequenciais (ou Enter se vazio).
        iterator_input = iter(inputs)
        mocker.patch("builtins.input", side_effect=lambda *a: next(iterator_input, "\n"))

        parser = _montar_parser()
        argv = ["folha_de_ponto", subcomando] + argv_extra
        args = parser.parse_args(argv)

        # Deve executar sem levantar exceção (NameError/ImportError/TypeError/etc).
        handle_folha_de_ponto(args, parser)

        # Garante que produziu saída (não caiu no else que só imprime help).
        saida = capsys.readouterr().out
        assert saida.strip(), f"subcomando {subcomando} não emitiu nenhuma saída"

    def test_envio_config_editar_nao_levanta_nameerror(self, mocker, capsys):
        """Regressão direta do bug: _campos_lista usa List[str] e antes
        quebrava com NameError sem `from typing import List`."""
        svc = _service_mock(mocker)
        # Buscar_por_id retorna um documento real → entra em _campos_lista.
        svc.buscar_por_id.return_value = {
            "nome": "João Teste",
            "identificador": "linha-1",
            "emails": ["a@x.com", "b@x.com"],
            "telefones": ["111"],
            "grupos_whatsapp": [],
            "enviar_email": "S",
            "enviar_whatsapp": "N",
            "enviar_grupo_whatsapp": "N",
            "enviar_impresso": "N",
        }
        # Força alteração em emails/telefones/grupos → passa por _campos_lista
        # e _flag com valores que geram alterações, e atualizar() é chamado.
        inputs = [
            "a@x.com,novo@x.com",  # emails (diferente do atual)
            "",                    # telefones (mantém = atual, sem alteração nesse campo)
            "Grupo B",             # grupos (diferente -> vira alteracao)
            "N",                   # enviar_email (S -> N)
            "",                    # enviar_whatsapp (mantém N)
            "",                    # enviar_grupo_whatsapp (mantém N)
            "",                    # enviar_impresso (mantém N)
        ]
        iterator_input = iter(inputs)
        mocker.patch("builtins.input", side_effect=lambda *a: next(iterator_input, "\n"))

        parser = _montar_parser()
        args = parser.parse_args(["folha_de_ponto", "envio-config-editar", "abc123"])

        handle_folha_de_ponto(args, parser)  # não pode levantar NameError

        saida = capsys.readouterr().out
        assert "atualizada" in saida or "alteração" in saida

    def test_service_indisponivel_nao_quebra(self, mocker, capsys):
        """MongoDB indisponível → handler avisa e retorna sem erro."""
        svc = _service_mock(mocker)
        svc.disponivel = False

        parser = _montar_parser()
        args = parser.parse_args(["folha_de_ponto", "envio-config-listar"])
        handle_folha_de_ponto(args, parser)
        saida = capsys.readouterr().out
        assert "não disponível" in saida


# ==================== REGRESSÃO: visualizar formata período em DD/MM/YYYY ====================

from datetime import datetime


class TestVisualizarFormataPeriodo:
    """`folha_de_ponto visualizar --id` deve exibir o período em DD/MM/YYYY,
    não o ISO cru (bug: 'Período: 2026-05-01 00:00:00 a 2026-05-31 00:00:00')."""

    def test_visualizar_exibe_periodo_br(self, mocker, caplog):
        import logging

        caplog.set_level(logging.INFO, logger="APP")
        folha = {
            "_id": "abc123",
            "mes_referencia": "2026-05",
            "status": "gerada",
            "versao": 1,
            "excluida": False,
            "folha_data": {
                "nome_funcionario": "João Silva",
                "data_inicio": datetime(2026, 5, 1),
                "data_fim": datetime(2026, 5, 31, 23, 59, 59),
                "total_horas_mes": "200:00",
                "total_faltas": 0,
                "total_feriados": 0,
                "total_finais_semana": 0,
                "dias": [],
            },
        }

        svc_cls = mocker.patch(
            "src.services.folha_ponto_service.FolhaDePontoService", autospec=True
        )
        instancia = svc_cls.return_value
        instancia.disponivel = True
        instancia.buscar_por_id.return_value = folha

        parser = _montar_parser()
        args = parser.parse_args(["folha_de_ponto", "visualizar", "--id", "abc123"])
        handle_folha_de_ponto(args, parser)

        saida = caplog.text
        assert "Período:" in saida
        # Exibe DD/MM/YYYY, NÃO ISO cru (sem ' 00:00:00').
        assert "01/05/2026 a 31/05/2026" in saida
        assert "2026-05-01" not in saida
        assert "00:00:00" not in saida
