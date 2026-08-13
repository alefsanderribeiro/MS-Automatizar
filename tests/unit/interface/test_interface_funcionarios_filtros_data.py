"""
Testes para os títulos dos filtros por data na interface de Funcionários.

Regressão (BUG 2): o usuário digita DD/MM/YYYY, mas o título do filtro por
período exibia ISO (ex: 2026-08-15). Deve exibir DD/MM/YYYY.
"""

from datetime import date

import pytest
from unittest.mock import MagicMock, patch

MODULE = "src.interface.interface_funcionarios"


def _cursor_vazio():
    """Cursor com resultados vazios: list(cursor) == []."""
    class CursoVazio(list):
        def sort(self, *args, **kwargs):
            return self
    return CursoVazio()


class TestCabecalhosFiltroPorData:
    @patch(f"{MODULE}._exibir_lista_com_data")
    @patch(f"{MODULE}.exibir_info")
    @patch(f"{MODULE}.exibir_cabecalho")
    @patch(f"{MODULE}._input_data", side_effect=[date(2026, 1, 1), date(2026, 8, 15)])
    @patch(
        f"{MODULE}.FuncionarioService",
    )
    def test_cabecalho_nascimento_dd_mm_yyyy(
        self, mock_var, mock_input_data, mock_cabecalho, mock_info, mock_lista
    ):
        # Mock do serviço: colecao.find retorna cursor vazio.
        servico = MagicMock()
        servico.colecao.find.return_value = _cursor_vazio()
        mock_var.return_value = servico

        from src.interface.interface_funcionarios import _filtrar_por_data_nascimento
        with patch(f"{MODULE}.pedir_selecao", return_value="Nascidos em um periodo (intervalo de datas)"):
            _filtrar_por_data_nascimento()

        # O cabeçalho deve exibir DD/MM/YYYY, não ISO.
        mock_cabecalho.assert_called_once_with(
            "Funcionarios nascidos entre 01/01/2026 e 15/08/2026"
        )

    @patch(f"{MODULE}._exibir_lista_com_data")
    @patch(f"{MODULE}.exibir_info")
    @patch(f"{MODULE}.exibir_cabecalho")
    @patch(f"{MODULE}._input_data", side_effect=[date(2026, 1, 1), date(2026, 8, 15)])
    @patch(f"{MODULE}.FuncionarioService")
    def test_cabecalho_admissao_dd_mm_yyyy(
        self, mock_var, mock_input_data, mock_cabecalho, mock_info, mock_lista
    ):
        servico = MagicMock()
        servico.colecao.find.return_value = _cursor_vazio()
        mock_var.return_value = servico

        from src.interface.interface_funcionarios import _filtrar_por_data_admissao
        with patch(f"{MODULE}.pedir_selecao", return_value="Admitidos em um periodo (intervalo de datas)"):
            _filtrar_por_data_admissao()

        mock_cabecalho.assert_called_once_with(
            "Funcionarios admitidos entre 01/01/2026 e 15/08/2026"
        )

    @patch(f"{MODULE}._exibir_lista_com_data")
    @patch(f"{MODULE}.exibir_info")
    @patch(f"{MODULE}.exibir_cabecalho")
    @patch(f"{MODULE}._input_data", side_effect=[date(2026, 1, 1), date(2026, 8, 15)])
    @patch(f"{MODULE}.FuncionarioService")
    def test_cabecalho_demissao_dd_mm_yyyy(
        self, mock_var, mock_input_data, mock_cabecalho, mock_info, mock_lista
    ):
        servico = MagicMock()
        servico.colecao.find.return_value = _cursor_vazio()
        mock_var.return_value = servico

        from src.interface.interface_funcionarios import _filtrar_por_data_demissao
        with patch(f"{MODULE}.pedir_selecao", return_value="Demitidos em um periodo (intervalo de datas)"):
            _filtrar_por_data_demissao()

        mock_cabecalho.assert_called_once_with(
            "Funcionarios demitidos entre 01/01/2026 e 15/08/2026"
        )
