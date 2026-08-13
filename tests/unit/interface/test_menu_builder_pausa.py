"""
Testes do MenuBuilder: pausa única por ação e navegação sem ENTER fantasma.

Cobre a correção de dois bugs de navegação da CLI:
  BUG 1 - Pausa dupla: as funções de ação chamam pausar() internamente e o
          MenuBuilder.executar() também pausava, gerando dois "Pressione ENTER".
  BUG 2 - ENTER fantasma: ao retornar de um submenu o menu pai pausava de
          forma desnecessária com a tela já redesenhadada.
"""
import types
from unittest import mock

import pytest

from src.interface.core import components
from src.interface.core.components import MenuBuilder, OpcaoMenu


@pytest.fixture(autouse=True)
def reset_estado_global():
    """Garante estado limpo do módulo entre testes."""
    components._pausou_na_acao = False
    components._profundidade_menu = 0
    components._submenus_executados = 0
    yield
    components._pausou_na_acao = False
    components._profundidade_menu = 0
    components._submenus_executados = 0


class _SelectFake:
    """Substitui questionary.select(...).ask() controlando as escolhas."""

    def __init__(self, escolhas):
        self._escolhas = list(escolhas)
        self._i = 0

    def ask(self):
        if self._i < len(self._escolhas):
            valor = self._escolhas[self._i]
            self._i += 1
            return valor
        return None


def _rodar_menu(acoes, pai=True):
    """
    Executa um menu com o loop real, devolvendo o log de pausas.

    `acoes` é uma lista de callables. Cada uma é adicionada como opção. O
    mock do questionary faz o menu executar a primeira ação e depois
    "Voltar" (None), encerrando o loop.

    Returns:
        (pause_log, opcao_menu): log das mensagens de pausa e o builder.
    """
    pause_log = []

    def fake_pausar(msg="Pressione ENTER para continuar..."):
        pause_log.append(msg)
        components._pausou_na_acao = True

    menu = MenuBuilder("MENU")
    for nome, acao in acoes:
        menu.adicionar(nome, acao)
    menu.com_voltar("Voltar")

    reais = [
        c.value for c in menu._montar_choices() if isinstance(c.value, OpcaoMenu)
    ]
    fake_select = _SelectFake([reais[0], None]) if reais else _SelectFake([None])

    with mock.patch.object(components, "pausar", side_effect=fake_pausar):
        with mock.patch.object(
            components.questionary, "select",
            return_value=fake_select,
        ):
            with mock.patch.object(components, "input", side_effect=lambda *a, **k: ""):
                menu.executar()

    return pause_log, menu


def test_pausa_unica_quando_acao_pausa_internamente():
    """BUG 1: ação que já chama pausar() não deve gerar 2ª pausa do menu."""
    def acao():
        components.pausar()

    pause_log, _ = _rodar_menu([("Ação", acao)])
    assert len(pause_log) == 1
    assert pause_log[0] == "Pressione ENTER para continuar..."


def test_pausa_quando_acao_nao_pausa():
    """Ação sem pausa interna: o MenuBuilder é responsável pela pausa única."""
    pause_log, _ = _rodar_menu([("Ação", lambda: None)])
    assert len(pause_log) == 1


def test_pausa_duplice_em_acoes_sequenciais():
    """
    Duas ações que pausam internamente, executadas em sequência, geram
    exatamente uma pausa cada (sem acúmulo).
    """
    def acao():
        components.pausar()

    def acao2():
        components.pausar()

    # Executar duas ações em sequência: fake devolve acao, depois acao2,
    # depois None (Voltar).
    menu = MenuBuilder("MENU")
    menu.adicionar("A1", acao)
    menu.adicionar("A2", acao2)
    menu.com_voltar("Voltar")

    pause_log = []
    reais = [
        c.value for c in menu._montar_choices() if isinstance(c.value, OpcaoMenu)
    ]
    fake_select = _SelectFake([reais[0], reais[1], None])

    def fake_pausar(msg="Pressione ENTER para continuar..."):
        pause_log.append(msg)
        components._pausou_na_acao = True

    with mock.patch.object(components, "pausar", side_effect=fake_pausar):
        with mock.patch.object(
            components.questionary, "select", return_value=fake_select
        ):
            with mock.patch.object(components, "input", side_effect=lambda *a, **k: ""):
                menu.executar()

    assert len(pause_log) == 2  # uma por ação executada


def test_retorno_de_submenu_sem_enter_fantasma():
    """
    BUG 2: quando a ação abre um submenu que executa uma sub-ação (que pausa)
    e retorna (Voltar), o menu pai NÃO adiciona uma pausa fantasma.
    """
    def _abrir_submenu():
        # Simula a execução de um menu aninhado: incrementa profundidade e
        # contador de submenus, executa uma sub-ação que pausa e retorna.
        components._profundidade_menu += 1
        components._submenus_executados += 1
        try:
            components.pausar()  # sub-ação pausa internamente
        finally:
            components._profundidade_menu -= 1

    pause_log, _ = _rodar_menu([("Submenu", _abrir_submenu)])
    # A única pausa vem da sub-ação; o menu pai não pausa (sem fantasma).
    assert len(pause_log) == 1


def test_submenu_que_nao_pausa_nem_fantasma():
    """
    Se a ação abre um submenu e o usuário volta sem nenhuma ação interna
    (Ctrl+C / Voltar direto), nem o pai nem o submenu pausam.
    """
    def _abrir_submenu():
        components._profundidade_menu += 1
        components._submenus_executados += 1
        components._profundidade_menu -= 1

    # _abrir_submenu apenas navega: não chama pausar().
    # Mesmo assim o pai detecta o aninhamento e não pausa.
    menu = MenuBuilder("MENU")
    menu.adicionar("Submenu", _abrir_submenu)
    menu.com_voltar("Voltar")

    pause_log = []
    reais = [
        c.value for c in menu._montar_choices() if isinstance(c.value, OpcaoMenu)
    ]
    fake_select = _SelectFake([reais[0], None])

    def fake_pausar(msg="Pressione ENTER para continuar..."):
        pause_log.append(msg)
        components._pausou_na_acao = True

    with mock.patch.object(components, "pausar", side_effect=fake_pausar):
        with mock.patch.object(
            components.questionary, "select", return_value=fake_select
        ):
            with mock.patch.object(components, "input", side_effect=lambda *a, **k: ""):
                menu.executar()

    assert pause_log == []


def test_sem_pausa_configurada_respeitada():
    """Menu com .sem_pausa() nunca pausa, mesmo com ação sem pausa interna."""
    menu = MenuBuilder("MENU").sem_pausa()
    menu.adicionar("Ação", lambda: None)
    menu.com_voltar("Voltar")

    pause_log = []
    reais = [
        c.value for c in menu._montar_choices() if isinstance(c.value, OpcaoMenu)
    ]
    fake_select = _SelectFake([reais[0], None])

    def fake_pausar(msg="Pressione ENTER para continuar..."):
        pause_log.append(msg)
        components._pausou_na_acao = True

    with mock.patch.object(components, "pausar", side_effect=fake_pausar):
        with mock.patch.object(
            components.questionary, "select", return_value=fake_select
        ):
            with mock.patch.object(components, "input", side_effect=lambda *a, **k: ""):
                menu.executar()

    assert pause_log == []
