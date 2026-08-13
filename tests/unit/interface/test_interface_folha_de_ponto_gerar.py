"""
Testes para o fluxo "Gerar folha de ponto" da interface.

Regressão de estabilidade (BUG 1): digitar data inválida no fluxo de gerar
folha NÃO pode quebrar o menu. Antes da correção, `parse_data_flexivel`
retornava `None` (não lançava exceção), então o antigo `except Exception`
nunca disparava e `data.strftime()` em `None` estourava `AttributeError`.
"""

from datetime import date

import pytest
from unittest.mock import patch

MODULE = "src.interface.interface_folha_de_ponto"


class TestGerarFolhaPontoDataInvalida:
    @patch(f"{MODULE}.exibir_painel")
    @patch(f"{MODULE}.exibir_resultado")
    @patch(f"{MODULE}.exibir_info")
    @patch(f"{MODULE}.exibir_aviso")
    @patch(f"{MODULE}._buscar_funcionarios_por_filtro", return_value=[])
    @patch(f"{MODULE}.pedir_texto", return_value="32/13/2026")  # inválida
    @patch(f"{MODULE}.pedir_selecao", return_value="Todos os funcionarios (ativos)")
    def test_data_invalida_nao_crasha_e_usa_data_atual(
        self,
        mock_selecao,
        mock_texto,
        mock_buscar,
        mock_aviso,
        mock_info,
        mock_resultado,
        mock_painel,
    ):
        # Não deve lançar nenhuma exceção (antes crashava com AttributeError).
        from src.interface.interface_folha_de_ponto import _gerar_folha_ponto
        _gerar_folha_ponto()

        # Deve avisar que a data foi invalidada e seguir com a data atual.
        mock_aviso.assert_called_once_with("Data invalida! Usando data atual.")

        # Como não há funcionários, o fluxo informa e retorna sem crash.
        mock_info.assert_any_call(
            "Nenhum funcionario encontrado com os filtros informados."
        )

    @patch(f"{MODULE}.exibir_painel")
    @patch(f"{MODULE}.exibir_resultado")
    @patch(f"{MODULE}.exibir_info")
    @patch(f"{MODULE}.exibir_aviso")
    @patch(f"{MODULE}._buscar_funcionarios_por_filtro", return_value=[])
    @patch(f"{MODULE}.pedir_texto", return_value="abc")  # texto inválido
    @patch(f"{MODULE}.pedir_selecao", return_value="Todos os funcionarios (ativos)")
    def test_texto_generico_invalido_nao_crasha(
        self,
        mock_selecao,
        mock_texto,
        mock_buscar,
        mock_aviso,
        mock_info,
        mock_resultado,
        mock_painel,
    ):
        from src.interface.interface_folha_de_ponto import _gerar_folha_ponto
        _gerar_folha_ponto()
        mock_aviso.assert_called_once_with("Data invalida! Usando data atual.")

    @patch(f"{MODULE}.exibir_painel")
    @patch(f"{MODULE}.exibir_resultado")
    @patch(f"{MODULE}.exibir_info")
    @patch(f"{MODULE}.exibir_aviso")
    @patch(f"{MODULE}._buscar_funcionarios_por_filtro", return_value=[])
    @patch(f"{MODULE}.pedir_texto", return_value="15/08/2026")  # válida
    @patch(f"{MODULE}.pedir_selecao", return_value="Todos os funcionarios (ativos)")
    def test_data_valida_nao_exibe_aviso(
        self,
        mock_selecao,
        mock_texto,
        mock_buscar,
        mock_aviso,
        mock_info,
        mock_resultado,
        mock_painel,
    ):
        from src.interface.interface_folha_de_ponto import _gerar_folha_ponto
        _gerar_folha_ponto()
        # Data válida não deve disparar o aviso de inválida.
        mock_aviso.assert_not_called()
