"""
Unit tests para o bloco "Gerenciar Folhas Geradas" da interface.

Cobre as 4 ações aprovadas pelo Alef no nível da interface:
- Visualizar folha já gerada
- Buscar por nome do funcionário
- Excluir (soft delete com aviso de já-enviada)
- Editar (com aviso de rastreabilidade)

E também a exibição formatada de uma folha existente.
"""

import pytest
from unittest.mock import MagicMock, patch
from bson import ObjectId
from datetime import datetime, timezone
from typing import Dict, Any

SAMPLE_FOLHA_ID = ObjectId("507f1f77bcf86cd799439013")
SAMPLE_FUNC_ID = ObjectId("507f1f77bcf86cd799439011")


def criar_folha_interface(
    excluida: bool = False,
    versao: int = 2,
    com_historico: bool = True,
    com_analise_ia: bool = False,
    enviada: bool = False,
) -> Dict[str, Any]:
    """Factory de folha para testes de interface."""
    folha = {
        "_id": SAMPLE_FOLHA_ID,
        "funcionario_id": SAMPLE_FUNC_ID,
        "empresa_id": ObjectId("507f1f77bcf86cd799439012"),
        "mes_referencia": "2025-01",
        "status": "preenchida",
        "versao": versao,
        "excluida": excluida,
        "motivo_exclusao": "teste" if excluida else None,
        "caminho_arquivo_gerado": "/tmp/folhas/João Silva.pdf",
        "data_criacao": datetime.now(timezone.utc),
        "data_atualizacao": datetime.now(timezone.utc),
        "historico_alteracoes": (
            [
                {
                    "timestamp": "2025-01-02T10:00:00",
                    "acao": "Folha editada manualmente",
                    "versao_anterior": 1,
                    "versao_nova": 2,
                    "detalhes": {},
                }
            ]
            if com_historico
            else []
        ),
        "folha_data": {
            "mes_referencia": "2025-01",
            "data_inicio": "2025-01-01",
            "data_fim": "2025-01-31",
            "nome_funcionario": "João Silva",
            "total_horas_mes": "160:00",
            "total_faltas": 1,
            "total_feriados": 0,
            "total_finais_semana": 8,
            "dias": [
                {
                    "numero_dia": 1,
                    "data": "2025-01-01",
                    "entrada": "08:00",
                    "saida": "17:00",
                    "trabalhado": True,
                    "falta": False,
                    "feriado": False,
                    "fim_de_semana": False,
                    "observacao": "",
                },
                {
                    "numero_dia": 2,
                    "data": "2025-01-02",
                    "entrada": "-",
                    "saida": "-",
                    "trabalhado": False,
                    "falta": True,
                    "feriado": False,
                    "fim_de_semana": False,
                    "observacao": "Faltou sem justificativa",
                },
            ],
            "analise_ia_concluida": com_analise_ia,
            "analise_ia": {"observacoes": "Análise OK"} if com_analise_ia else None,
        },
    }
    return folha


def _servico_mock(folha=None, folhas=None, enviada=False):
    """Cria um mock de serviço de folha de ponto."""
    servico = MagicMock()
    servico.disponivel = True
    servico.buscar_por_id.return_value = folha
    servico.buscar_por_nome_funcionario.return_value = folhas or []
    servico.verificar_folha_enviada.return_value = enviada
    servico.marcar_excluida.return_value = True
    servico.atualizar_folha.return_value = True
    return servico


# ==================== Exibir dados de folha existente ====================

@pytest.mark.unit
class TestExibirDadosFolhaExistente:
    """_exibir_dados_folha_existente — exibição formatada de uma folha."""

    def test_exibe_dados_completos(self):
        from src.interface.interface_folha_de_ponto import _exibir_dados_folha_existente

        folha = criar_folha_interface()
        funcionario = {
            "nome": "João Silva",
            "lotacao": "TI",
            "funcao_id": ObjectId(),
            "horario_id": ObjectId(),
            "contrato_empresa_id": ObjectId(),
            "status": "ativo",
        }

        with patch("src.interface.interface_folha_de_ponto.buscar_nome_funcao", return_value="Analista"), \
             patch("src.interface.interface_folha_de_ponto.buscar_nome_horario", return_value="08h-17h"), \
             patch("src.interface.interface_folha_de_ponto.buscar_nome_contrato", return_value="CENSIPAM"), \
             patch("src.interface.interface_folha_de_ponto.buscar_empresa", return_value={"nome": "Empresa X", "cnpj": "123"}), \
             patch("src.interface.interface_folha_de_ponto.exibir_painel") as mock_painel, \
             patch("src.interface.interface_folha_de_ponto.exibir_tabela") as mock_tabela:

            _exibir_dados_folha_existente(folha, funcionario)

        # Pelo menos 3 painéis (funcionário, empresa, folha) + resumo
        assert mock_painel.call_count >= 4
        # Tabela com os dias
        mock_tabela.assert_called_once()

    def test_exibe_sem_empresa(self):
        """Empresa ausente cai no fallback com o ID da empresa."""
        from src.interface.interface_folha_de_ponto import _exibir_dados_folha_existente

        folha = criar_folha_interface()
        with patch("src.interface.interface_folha_de_ponto.buscar_empresa", return_value=None), \
             patch("src.interface.interface_folha_de_ponto.buscar_nome_funcao", return_value="N/A"), \
             patch("src.interface.interface_folha_de_ponto.buscar_nome_horario", return_value="N/A"), \
             patch("src.interface.interface_folha_de_ponto.buscar_nome_contrato", return_value="N/A"), \
             patch("src.interface.interface_folha_de_ponto.exibir_painel") as mock_painel, \
             patch("src.interface.interface_folha_de_ponto.exibir_tabela"):

            _exibir_dados_folha_existente(folha, {"nome": "João Silva"})

        assert mock_painel.call_count >= 3

    def test_exibe_com_analise_ia(self):
        from src.interface.interface_folha_de_ponto import _exibir_dados_folha_existente

        folha = criar_folha_interface(com_analise_ia=True)
        with patch("src.interface.interface_folha_de_ponto.buscar_empresa", return_value=None), \
             patch("src.interface.interface_folha_de_ponto.buscar_nome_funcao", return_value="N/A"), \
             patch("src.interface.interface_folha_de_ponto.buscar_nome_horario", return_value="N/A"), \
             patch("src.interface.interface_folha_de_ponto.buscar_nome_contrato", return_value="N/A"), \
             patch("src.interface.interface_folha_de_ponto.exibir_painel") as mock_painel, \
             patch("src.interface.interface_folha_de_ponto.exibir_tabela"):

            _exibir_dados_folha_existente(folha, {"nome": "João Silva"})

        # Painel extra de análise IA
        assert mock_painel.call_count >= 5


# ==================== Detalhes completos (versão/histórico) ====================

@pytest.mark.unit
class TestExibirDetalhesFolhaCompleta:
    """_exibir_detalhes_folha_completa — inclui versão, histórico e soft delete."""

    def test_com_historico(self):
        from src.interface.interface_folha_de_ponto import _exibir_detalhes_folha_completa

        folha = criar_folha_interface()

        with patch("src.interface.interface_folha_de_ponto.buscar_funcionario", return_value={"nome": "João Silva"}), \
             patch("src.interface.interface_folha_de_ponto._exibir_dados_folha_existente") as mock_exibir, \
             patch("src.interface.interface_folha_de_ponto.exibir_painel") as mock_painel, \
             patch("src.interface.interface_folha_de_ponto.exibir_tabela") as mock_tabela:

            _exibir_detalhes_folha_completa(folha)

        mock_exibir.assert_called_once()
        mock_painel.assert_called_once()
        # Tabela do histórico
        mock_tabela.assert_called_once()

    def test_sem_historico(self):
        from src.interface.interface_folha_de_ponto import _exibir_detalhes_folha_completa

        folha = criar_folha_interface(com_historico=False)

        with patch("src.interface.interface_folha_de_ponto.buscar_funcionario", return_value=None), \
             patch("src.interface.interface_folha_de_ponto._exibir_dados_folha_existente"), \
             patch("src.interface.interface_folha_de_ponto.exibir_painel"), \
             patch("src.interface.interface_folha_de_ponto.exibir_tabela") as mock_tabela:

            _exibir_detalhes_folha_completa(folha)

        # Sem histórico: nenhuma tabela
        mock_tabela.assert_not_called()


# ==================== Buscar por nome ====================

@pytest.mark.unit
class TestBuscarFolhasPorNome:
    """_buscar_folhas_por_nome — busca com nome + filtros opcionais."""

    def test_sem_servico(self):
        from src.interface.interface_folha_de_ponto import _buscar_folhas_por_nome

        with patch("src.interface.interface_folha_de_ponto._obter_servico_folha", return_value=None), \
             patch("src.interface.interface_folha_de_ponto.exibir_erro") as mock_erro:

            resultado = _buscar_folhas_por_nome(nome="João")

        assert resultado == []
        mock_erro.assert_called_once()

    def test_busca_com_nome_e_filtros(self):
        from src.interface.interface_folha_de_ponto import _buscar_folhas_por_nome

        folhas = [criar_folha_interface()]
        servico = _servico_mock(folhas=folhas)
        servico.buscar_por_nome_funcionario.return_value = folhas

        with patch("src.interface.interface_folha_de_ponto._obter_servico_folha", return_value=servico), \
             patch("src.interface.interface_folha_de_ponto.pedir_texto", side_effect=["2025-02"]) as mock_texto, \
             patch("src.interface.interface_folha_de_ponto.pedir_selecao", return_value="preenchida"):

            resultado = _buscar_folhas_por_nome(nome="João")

        assert len(resultado) == 1
        mock_texto.assert_called_once()
        servico.buscar_por_nome_funcionario.assert_called_once_with(
            nome="João", mes_referencia="2025-02", status="preenchida"
        )

    def test_nome_pedido_ao_usuario(self):
        from src.interface.interface_folha_de_ponto import _buscar_folhas_por_nome

        servico = _servico_mock(folhas=[])
        with patch("src.interface.interface_folha_de_ponto._obter_servico_folha", return_value=servico), \
             patch("src.interface.interface_folha_de_ponto.pedir_texto", side_effect=["Maria", None]) as mock_texto, \
             patch("src.interface.interface_folha_de_ponto.pedir_selecao", return_value="Todos"):

            _buscar_folhas_por_nome()

        # Nome pedido + mês (None) — dois pedidos de texto
        assert mock_texto.call_count == 2
        servico.buscar_por_nome_funcionario.assert_called_once_with(
            nome="Maria", mes_referencia=None, status=None
        )


# ==================== Visualizar ====================

@pytest.mark.unit
class TestVisualizarFolhaGerada:
    """_visualizar_folha_gerada — seleção por ID ou busca por nome."""

    def test_sem_servico(self):
        from src.interface.interface_folha_de_ponto import _visualizar_folha_gerada

        with patch("src.interface.interface_folha_de_ponto._obter_servico_folha", return_value=None), \
             patch("src.interface.interface_folha_de_ponto.exibir_erro") as mock_erro:

            _visualizar_folha_gerada()

        mock_erro.assert_called_once()

    def test_visualizar_por_id(self):
        from src.interface.interface_folha_de_ponto import _visualizar_folha_gerada

        folha = criar_folha_interface()
        servico = _servico_mock(folha=folha)

        with patch("src.interface.interface_folha_de_ponto._obter_servico_folha", return_value=servico), \
             patch("src.interface.interface_folha_de_ponto.pedir_selecao", return_value="Informar ID da folha"), \
             patch("src.interface.interface_folha_de_ponto.pedir_texto", return_value=str(SAMPLE_FOLHA_ID)), \
             patch("src.interface.interface_folha_de_ponto._exibir_detalhes_folha_completa") as mock_detalhes, \
             patch("src.interface.interface_folha_de_ponto.pausar") as mock_pausar:

            _visualizar_folha_gerada()

        servico.buscar_por_id.assert_called_once_with(str(SAMPLE_FOLHA_ID))
        mock_detalhes.assert_called_once()
        mock_pausar.assert_called_once()

    def test_visualizar_id_nao_encontrado(self):
        from src.interface.interface_folha_de_ponto import _visualizar_folha_gerada

        servico = _servico_mock(folha=None)

        with patch("src.interface.interface_folha_de_ponto._obter_servico_folha", return_value=servico), \
             patch("src.interface.interface_folha_de_ponto.pedir_selecao", return_value="Informar ID da folha"), \
             patch("src.interface.interface_folha_de_ponto.pedir_texto", return_value=str(SAMPLE_FOLHA_ID)), \
             patch("src.interface.interface_folha_de_ponto.exibir_erro") as mock_erro:

            _visualizar_folha_gerada()

        mock_erro.assert_called_once()

    def test_visualizar_cancelado(self):
        from src.interface.interface_folha_de_ponto import _visualizar_folha_gerada

        servico = _servico_mock(folha=criar_folha_interface())

        with patch("src.interface.interface_folha_de_ponto._obter_servico_folha", return_value=servico), \
             patch("src.interface.interface_folha_de_ponto.pedir_selecao", return_value=None):

            _visualizar_folha_gerada()  # não deve lançar

        servico.buscar_por_id.assert_not_called()


# ==================== Excluir (soft delete) ====================

@pytest.mark.unit
class TestExcluirFolhaGerada:
    """_excluir_folha_gerada — soft delete com aviso de já-enviada."""

    def test_excluir_confirmado(self):
        from src.interface.interface_folha_de_ponto import _excluir_folha_gerada

        folha = criar_folha_interface()
        servico = _servico_mock(folha=folha, enviada=False)

        with patch("src.interface.interface_folha_de_ponto._obter_servico_folha", return_value=servico), \
             patch("src.interface.interface_folha_de_ponto.pedir_selecao", return_value="Informar ID da folha"), \
             patch("src.interface.interface_folha_de_ponto.pedir_texto", side_effect=[str(SAMPLE_FOLHA_ID), "Gerada errada"]), \
             patch("src.interface.interface_folha_de_ponto.pedir_confirmacao", return_value=True), \
             patch("src.interface.interface_folha_de_ponto.exibir_sucesso") as mock_sucesso:

            _excluir_folha_gerada()

        servico.marcar_excluida.assert_called_once_with(str(SAMPLE_FOLHA_ID), motivo="Gerada errada")
        mock_sucesso.assert_called_once()

    def test_excluir_ja_enviada_com_aviso(self):
        """Folha já ENVIADA: aviso + confirmação, soft delete preserva envio."""
        from src.interface.interface_folha_de_ponto import _excluir_folha_gerada

        folha = criar_folha_interface()
        servico = _servico_mock(folha=folha, enviada=True)

        with patch("src.interface.interface_folha_de_ponto._obter_servico_folha", return_value=servico), \
             patch("src.interface.interface_folha_de_ponto.pedir_selecao", return_value="Informar ID da folha"), \
             patch("src.interface.interface_folha_de_ponto.pedir_texto", side_effect=[str(SAMPLE_FOLHA_ID), None]), \
             patch("src.interface.interface_folha_de_ponto.pedir_confirmacao", return_value=True), \
             patch("src.interface.interface_folha_de_ponto.exibir_aviso") as mock_aviso, \
             patch("src.interface.interface_folha_de_ponto.exibir_sucesso"):

            _excluir_folha_gerada()

        # Aviso de envio registrado foi exibido
        mock_aviso.assert_called()
        servico.marcar_excluida.assert_called_once_with(str(SAMPLE_FOLHA_ID), motivo=None)

    def test_excluir_cancelado(self):
        from src.interface.interface_folha_de_ponto import _excluir_folha_gerada

        folha = criar_folha_interface()
        servico = _servico_mock(folha=folha)

        with patch("src.interface.interface_folha_de_ponto._obter_servico_folha", return_value=servico), \
             patch("src.interface.interface_folha_de_ponto.pedir_selecao", return_value="Informar ID da folha"), \
             patch("src.interface.interface_folha_de_ponto.pedir_texto", return_value=str(SAMPLE_FOLHA_ID)), \
             patch("src.interface.interface_folha_de_ponto.pedir_confirmacao", return_value=False):

            _excluir_folha_gerada()

        servico.marcar_excluida.assert_not_called()

    def test_excluir_ja_excluida(self):
        from src.interface.interface_folha_de_ponto import _excluir_folha_gerada

        folha = criar_folha_interface(excluida=True)
        servico = _servico_mock(folha=folha)

        with patch("src.interface.interface_folha_de_ponto._obter_servico_folha", return_value=servico), \
             patch("src.interface.interface_folha_de_ponto.pedir_selecao", return_value="Informar ID da folha"), \
             patch("src.interface.interface_folha_de_ponto.pedir_texto", return_value=str(SAMPLE_FOLHA_ID)), \
             patch("src.interface.interface_folha_de_ponto.exibir_aviso") as mock_aviso:

            _excluir_folha_gerada()

        mock_aviso.assert_called_once()
        servico.marcar_excluida.assert_not_called()

    def test_excluir_falha(self):
        from src.interface.interface_folha_de_ponto import _excluir_folha_gerada

        folha = criar_folha_interface()
        servico = _servico_mock(folha=folha)
        servico.marcar_excluida.return_value = False

        with patch("src.interface.interface_folha_de_ponto._obter_servico_folha", return_value=servico), \
             patch("src.interface.interface_folha_de_ponto.pedir_selecao", return_value="Informar ID da folha"), \
             patch("src.interface.interface_folha_de_ponto.pedir_texto", return_value=str(SAMPLE_FOLHA_ID)), \
             patch("src.interface.interface_folha_de_ponto.pedir_confirmacao", return_value=True), \
             patch("src.interface.interface_folha_de_ponto.exibir_erro") as mock_erro:

            _excluir_folha_gerada()

        mock_erro.assert_called_once()


# ==================== Editar ====================

@pytest.mark.unit
class TestEditarFolhaGerada:
    """_editar_folha_gerada — edição com recálculo/PDF/versão."""

    def test_sem_servico(self):
        from src.interface.interface_folha_de_ponto import _editar_folha_gerada

        with patch("src.interface.interface_folha_de_ponto._obter_servico_folha", return_value=None), \
             patch("src.interface.interface_folha_de_ponto.exibir_erro") as mock_erro:

            _editar_folha_gerada()

        mock_erro.assert_called_once()

    def test_editar_cancelado_sem_edicoes(self):
        """Usuário digita 'sair' sem informar edições → cancelamento."""
        from src.interface.interface_folha_de_ponto import _editar_folha_gerada

        folha = criar_folha_interface()
        servico = _servico_mock(folha=folha)

        with patch("src.interface.interface_folha_de_ponto._obter_servico_folha", return_value=servico), \
             patch("src.interface.interface_folha_de_ponto.pedir_selecao", return_value="Informar ID da folha"), \
             patch("src.interface.interface_folha_de_ponto.pedir_texto", return_value=str(SAMPLE_FOLHA_ID)), \
             patch("src.interface.interface_folha_de_ponto._exibir_dados_folha_existente"), \
             patch("src.interface.interface_folha_de_ponto.exibir_aviso") as mock_aviso:

            # Primeiro pedir_texto do dia retorna 'sair'
            with patch("src.interface.interface_folha_de_ponto.pedir_texto") as mock_texto:
                mock_texto.side_effect = [str(SAMPLE_FOLHA_ID), "sair"]
                _editar_folha_gerada()

        mock_aviso.assert_called_once()
        servico.atualizar_folha.assert_not_called()

    def test_editar_folha_excluida_bloqueada(self):
        from src.interface.interface_folha_de_ponto import _editar_folha_gerada

        folha = criar_folha_interface(excluida=True)
        servico = _servico_mock(folha=folha)

        with patch("src.interface.interface_folha_de_ponto._obter_servico_folha", return_value=servico), \
             patch("src.interface.interface_folha_de_ponto.pedir_selecao", return_value="Informar ID da folha"), \
             patch("src.interface.interface_folha_de_ponto.pedir_texto", return_value=str(SAMPLE_FOLHA_ID)), \
             patch("src.interface.interface_folha_de_ponto.exibir_erro") as mock_erro:

            _editar_folha_gerada()

        mock_erro.assert_called_once()


# ==================== Submenu ====================

@pytest.mark.unit
class TestGerenciarFolhasGeradas:
    """_gerenciar_folhas_geradas — monta o submenu com as 4 ações."""

    def test_monta_menu_com_4_acoes(self):
        from src.interface.interface_folha_de_ponto import _gerenciar_folhas_geradas

        with patch("src.interface.interface_folha_de_ponto.MenuBuilder") as MockMB:
            instancia = MockMB.return_value
            instancia.adicionar.return_value = instancia
            instancia.com_voltar.return_value = instancia

            _gerenciar_folhas_geradas()

        # 4 ações: visualizar, buscar, excluir, editar
        assert instancia.adicionar.call_count == 4
        instancia.executar.assert_called_once()
