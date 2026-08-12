"""
Componentes reutilizáveis da interface.

Fornece classes e funções para construção de menus, exibição de dados
e coleta de inputs de forma padronizada.

Uso:
    from src.interface.core.components import MenuBuilder, exibir_sucesso, pedir_texto

    # Criar menu
    MenuBuilder("Meu Menu", "📋")
        .adicionar("Opção 1", minha_funcao, "📌")
        .executar()

    # Exibir mensagens
    exibir_sucesso("Operação concluída!")

    # Coletar input
    nome = pedir_texto("Nome do usuário:")
"""

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Union

import questionary
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.box import ROUNDED

from src.interface.core.theme import console, ESTILO_QUESTIONARY, ICONES, LAYOUT


# ═══════════════════════════════════════════════════════════════
# CLASSES DE MENU
# ═══════════════════════════════════════════════════════════════


@dataclass
class OpcaoMenu:
    """
    Representa uma opção de menu.

    Attributes:
        titulo: Texto exibido para a opção.
        acao: Função a ser executada quando selecionada.
        icone: Ícone opcional exibido antes do título.
        visivel: Função que retorna se a opção deve ser exibida.
        desabilitada: Função que retorna se a opção está desabilitada.
    """

    titulo: str
    acao: Callable[[], Any]
    icone: str = ""
    visivel: Callable[[], bool] = field(default=lambda: True)
    desabilitada: Callable[[], bool] = field(default=lambda: False)

    @property
    def label(self) -> str:
        """Retorna label formatado para exibição."""
        if self.icone:
            return f"{self.icone} {self.titulo}"
        return self.titulo


class MenuBuilder:
    """
    Builder para criar menus de forma fluente.

    Exemplo:
        MenuBuilder("Menu Principal", "📋")
            .adicionar("Listar itens", listar, "📄")
            .adicionar("Criar item", criar, "➕")
            .separador()
            .adicionar("Configurações", config, "⚙️")
            .com_voltar("Sair")
            .executar()
    """

    def __init__(self, titulo: str, icone: str = ""):
        """
        Inicializa o builder de menu.

        Args:
            titulo: Título do menu.
            icone: Ícone opcional para o título.
        """
        self.titulo = titulo
        self.icone = icone or ICONES.get("menu", "")
        self.opcoes: list[Union[OpcaoMenu, str]] = []
        self.texto_voltar = "Voltar"
        self.icone_voltar = ICONES.get("voltar", "↩️")
        self.mostrar_cabecalho = True
        self.instrucao = "(Use ↑↓ para navegar, Enter para selecionar)"
        self._pausar_apos_acao = True

    def adicionar(
        self,
        titulo: str,
        acao: Callable[[], Any],
        icone: str = "",
        visivel: Callable[[], bool] = lambda: True,
        desabilitada: Callable[[], bool] = lambda: False,
    ) -> "MenuBuilder":
        """
        Adiciona opção ao menu.

        Args:
            titulo: Texto da opção.
            acao: Função a executar.
            icone: Ícone opcional.
            visivel: Função que retorna se deve exibir.
            desabilitada: Função que retorna se está desabilitada.

        Returns:
            Self para encadeamento.
        """
        self.opcoes.append(
            OpcaoMenu(
                titulo=titulo,
                acao=acao,
                icone=icone,
                visivel=visivel,
                desabilitada=desabilitada,
            )
        )
        return self

    def separador(self, texto: str = "") -> "MenuBuilder":
        """
        Adiciona separador visual.

        Args:
            texto: Texto opcional para o separador.

        Returns:
            Self para encadeamento.
        """
        self.opcoes.append(f"---{texto}---")
        return self

    def com_voltar(self, texto: str = "Voltar", icone: str = "") -> "MenuBuilder":
        """
        Define texto e ícone do botão voltar.

        Args:
            texto: Texto do botão.
            icone: Ícone opcional.

        Returns:
            Self para encadeamento.
        """
        self.texto_voltar = texto
        if icone:
            self.icone_voltar = icone
        return self

    def sem_cabecalho(self) -> "MenuBuilder":
        """
        Desativa exibição do cabeçalho.

        Returns:
            Self para encadeamento.
        """
        self.mostrar_cabecalho = False
        return self

    def com_instrucao(self, texto: str) -> "MenuBuilder":
        """
        Define texto de instrução personalizado.

        Args:
            texto: Texto de instrução.

        Returns:
            Self para encadeamento.
        """
        self.instrucao = texto
        return self

    def sem_pausa(self) -> "MenuBuilder":
        """
        Desativa pausa após executar ação.

        Returns:
            Self para encadeamento.
        """
        self._pausar_apos_acao = False
        return self

    def executar(self) -> None:
        """Executa o loop do menu."""
        while True:
            # Limpa tela e exibe cabeçalho
            if self.mostrar_cabecalho:
                limpar_tela()
                exibir_cabecalho(self.titulo, self.icone)

            # Monta choices para questionary
            choices = self._montar_choices()

            # Exibe menu
            try:
                escolha = questionary.select(
                    "Escolha uma opção:",
                    choices=choices,
                    style=ESTILO_QUESTIONARY,
                    instruction=self.instrucao,
                    qmark="",
                ).ask()
            except KeyboardInterrupt:
                # Ctrl+C = voltar
                break

            # None ou string (voltar/separador) = sair do menu
            if escolha is None or not isinstance(escolha, OpcaoMenu):
                break

            # Executa ação
            try:
                escolha.acao()
            except KeyboardInterrupt:
                exibir_aviso("Operação cancelada pelo usuário.")
            except Exception as e:
                exibir_erro(f"Erro ao executar: {e}")

            if self._pausar_apos_acao:
                pausar()

    def _montar_choices(self) -> list:
        """Monta lista de choices para questionary."""
        choices = []

        for item in self.opcoes:
            if isinstance(item, str):
                # É um separador
                texto_sep = item.replace("---", "").strip()
                if texto_sep:
                    choices.append(questionary.Separator(f"--- {texto_sep} ---"))
                else:
                    choices.append(questionary.Separator("-" * 40))
            elif isinstance(item, OpcaoMenu):
                # É uma opção
                if item.visivel():
                    if item.desabilitada():
                        choices.append(
                            questionary.Choice(
                                f"[desabilitado] {item.label}",
                                value=item,
                                disabled="Indisponível",
                            )
                        )
                    else:
                        choices.append(questionary.Choice(item.label, value=item))

        # Adiciona separador e opção de voltar
        choices.append(questionary.Separator("-" * 40))
        choices.append(
            questionary.Choice(f"{self.icone_voltar} {self.texto_voltar}", value=None)
        )

        return choices

    def executar_uma_vez(self) -> Optional[Any]:
        """
        Executa o menu uma única vez (sem loop).

        Returns:
            Resultado da ação executada ou None se voltar.
        """
        if self.mostrar_cabecalho:
            limpar_tela()
            exibir_cabecalho(self.titulo, self.icone)

        choices = self._montar_choices()

        try:
            escolha = questionary.select(
                "Escolha uma opção:",
                choices=choices,
                style=ESTILO_QUESTIONARY,
                instruction=self.instrucao,
                qmark="",
            ).ask()
        except KeyboardInterrupt:
            return None

        if escolha is None or not isinstance(escolha, OpcaoMenu):
            return None

        try:
            return escolha.acao()
        except Exception as e:
            exibir_erro(f"Erro ao executar: {e}")
            return None


# ═══════════════════════════════════════════════════════════════
# FUNÇÕES DE EXIBIÇÃO
# ═══════════════════════════════════════════════════════════════


def limpar_tela() -> None:
    """Limpa a tela do terminal."""
    if sys.platform == "win32":
        os.system("cls")
    else:
        os.system("clear")


def exibir_cabecalho(titulo: str, icone: str = "") -> None:
    """
    Exibe cabeçalho formatado com painel.

    Args:
        titulo: Título a exibir.
        icone: Ícone opcional.
    """
    titulo_completo = f"{icone} {titulo}".strip() if icone else titulo
    console.print()
    console.print(
        Panel(
            f"[titulo]{titulo_completo}[/titulo]",
            expand=False,
            border_style="cyan",
            box=ROUNDED,
            padding=(0, 2),
        )
    )
    console.print()


def exibir_sucesso(mensagem: str) -> None:
    """
    Exibe mensagem de sucesso.

    Args:
        mensagem: Texto da mensagem.
    """
    console.print(f"\n[sucesso]{ICONES['sucesso']} {mensagem}[/sucesso]")


def exibir_erro(mensagem: str) -> None:
    """
    Exibe mensagem de erro.

    Args:
        mensagem: Texto da mensagem.
    """
    console.print(f"\n[erro]{ICONES['erro']} {mensagem}[/erro]")


def exibir_aviso(mensagem: str) -> None:
    """
    Exibe mensagem de aviso.

    Args:
        mensagem: Texto da mensagem.
    """
    console.print(f"\n[aviso]{ICONES['aviso']} {mensagem}[/aviso]")


def exibir_info(mensagem: str) -> None:
    """
    Exibe mensagem informativa.

    Args:
        mensagem: Texto da mensagem.
    """
    console.print(f"\n[info]{ICONES['info']} {mensagem}[/info]")


def exibir_painel(
    conteudo: str,
    titulo: str = "",
    estilo_borda: str = "cyan",
    expandir: bool = False,
) -> None:
    """
    Exibe conteúdo em painel formatado.

    Args:
        conteudo: Texto a exibir.
        titulo: Título opcional do painel.
        estilo_borda: Cor/estilo da borda.
        expandir: Se deve expandir para largura total.
    """
    console.print()
    console.print(
        Panel(
            conteudo,
            title=titulo if titulo else None,
            border_style=estilo_borda,
            expand=expandir,
            box=ROUNDED,
        )
    )


def exibir_tabela(
    titulo: str,
    colunas: list[str],
    dados: list[list[Any]],
    mostrar_indice: bool = True,
    estilos_colunas: Optional[dict[str, str]] = None,
) -> None:
    """
    Exibe dados em tabela formatada.

    Args:
        titulo: Título da tabela.
        colunas: Lista com nomes das colunas.
        dados: Lista de listas com os dados.
        mostrar_indice: Se deve exibir coluna de índice.
        estilos_colunas: Dict com estilos por coluna.
    """
    tabela = Table(
        title=titulo,
        show_header=True,
        header_style="tabela.cabecalho",
        box=ROUNDED,
    )

    if mostrar_indice:
        tabela.add_column("#", style="tabela.indice", width=4, justify="right")

    for coluna in colunas:
        estilo = (estilos_colunas or {}).get(coluna, "tabela.linha")
        tabela.add_column(coluna, style=estilo)

    for i, linha in enumerate(dados, 1):
        valores = [str(v) if v is not None else "-" for v in linha]
        if mostrar_indice:
            tabela.add_row(str(i), *valores)
        else:
            tabela.add_row(*valores)

    console.print()
    console.print(tabela)


def exibir_resultado(
    titulo: str,
    sucesso: int,
    erros: int,
    detalhes: Optional[list[str]] = None,
) -> None:
    """
    Exibe box de resultado de operação.

    Args:
        titulo: Título do resultado.
        sucesso: Quantidade de sucessos.
        erros: Quantidade de erros.
        detalhes: Lista de detalhes adicionais.
    """
    # Define cor baseado no resultado
    if erros == 0:
        cor = "green"
    elif sucesso > erros:
        cor = "yellow"
    else:
        cor = "red"

    conteudo = f"[green]{ICONES['sucesso']} Processados: {sucesso}[/green]\n"
    conteudo += f"[red]{ICONES['erro']} Erros: {erros}[/red]"

    if detalhes:
        conteudo += "\n\n" + "\n".join(detalhes)

    console.print()
    console.print(
        Panel(
            conteudo,
            title=f"[bold]{titulo}[/bold]",
            border_style=cor,
            box=ROUNDED,
        )
    )


def exibir_com_spinner(mensagem: str, funcao: Callable[[], Any]) -> Any:
    """
    Executa função exibindo spinner de loading.

    Args:
        mensagem: Texto a exibir durante processamento.
        funcao: Função a executar.

    Returns:
        Resultado da função.
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(description=mensagem, total=None)
        return funcao()


def exibir_lista_simples(
    titulo: str,
    itens: list[str],
    icone: str = "",
) -> None:
    """
    Exibe lista simples de itens.

    Args:
        titulo: Título da lista.
        itens: Lista de strings.
        icone: Ícone para cada item.
    """
    console.print(f"\n[subtitulo]{titulo}[/subtitulo]\n")
    icone_item = icone or ICONES.get("ponto", "•")
    for item in itens:
        console.print(f"  {icone_item} {item}")


# ═══════════════════════════════════════════════════════════════
# FUNÇÕES DE INPUT
# ═══════════════════════════════════════════════════════════════


def pausar(mensagem: str = "Pressione ENTER para continuar...") -> None:
    """
    Pausa a execução até o usuário pressionar ENTER.

    Args:
        mensagem: Texto a exibir.
    """
    console.print(f"\n[dim]{mensagem}[/dim]")
    try:
        input()
    except KeyboardInterrupt:
        pass


def pedir_confirmacao(
    mensagem: str = "Confirmar operação?",
    padrao: bool = False,
) -> bool:
    """
    Pede confirmação ao usuário.

    Args:
        mensagem: Pergunta a fazer.
        padrao: Valor padrão se apenas Enter.

    Returns:
        True se confirmado, False caso contrário.
    """
    try:
        resultado = questionary.confirm(
            mensagem,
            default=padrao,
            style=ESTILO_QUESTIONARY,
        ).ask()
        return resultado if resultado is not None else False
    except KeyboardInterrupt:
        return False


def pedir_texto(
    mensagem: str,
    obrigatorio: bool = True,
    padrao: str = "",
    validador: Optional[Callable[[str], bool]] = None,
    erro_validacao: str = "Valor inválido",
    multiline: bool = False,
) -> Optional[str]:
    """
    Solicita texto do usuário.

    Args:
        mensagem: Prompt a exibir.
        obrigatorio: Se campo é obrigatório.
        padrao: Valor padrão.
        validador: Função de validação.
        erro_validacao: Mensagem se validação falhar.
        multiline: Se aceita múltiplas linhas.

    Returns:
        Texto digitado ou None se cancelado/vazio.
    """

    def validate(valor: str) -> Union[bool, str]:
        valor_limpo = valor.strip()
        if obrigatorio and not valor_limpo:
            return "Este campo é obrigatório"
        if validador and valor_limpo and not validador(valor_limpo):
            return erro_validacao
        return True

    try:
        resultado = questionary.text(
            mensagem,
            default=padrao,
            validate=validate,
            style=ESTILO_QUESTIONARY,
            multiline=multiline,
        ).ask()

        if resultado is None:
            return None

        resultado_limpo = resultado.strip()
        return resultado_limpo if resultado_limpo else None

    except KeyboardInterrupt:
        return None


def pedir_selecao(
    mensagem: str,
    opcoes: list[str],
    permitir_outro: bool = False,
    instrucao: str = "",
) -> Optional[str]:
    """
    Solicita seleção de uma lista.

    Args:
        mensagem: Prompt a exibir.
        opcoes: Lista de opções.
        permitir_outro: Se permite digitar valor não listado.
        instrucao: Texto de instrução.

    Returns:
        Opção selecionada ou None se cancelado.
    """
    if not opcoes:
        exibir_aviso("Nenhuma opção disponível.")
        return None

    choices = list(opcoes)

    if permitir_outro:
        choices.append(questionary.Separator("-" * 30))
        choices.append(questionary.Choice("✏️  Outro (digitar)", value="__OUTRO__"))

    try:
        resultado = questionary.select(
            mensagem,
            choices=choices,
            style=ESTILO_QUESTIONARY,
            instruction=instrucao or "(Use ↑↓ para navegar)",
        ).ask()
    except KeyboardInterrupt:
        return None

    if resultado == "__OUTRO__":
        return pedir_texto("Digite o valor:")

    return resultado


def pedir_selecao_multipla(
    mensagem: str,
    opcoes: list[str],
    minimo: int = 0,
    maximo: Optional[int] = None,
) -> list[str]:
    """
    Solicita seleção múltipla de uma lista.

    Args:
        mensagem: Prompt a exibir.
        opcoes: Lista de opções.
        minimo: Mínimo de seleções obrigatórias.
        maximo: Máximo de seleções permitidas.

    Returns:
        Lista de opções selecionadas.
    """
    if not opcoes:
        exibir_aviso("Nenhuma opção disponível.")
        return []

    def validate(selecionados: list) -> Union[bool, str]:
        if len(selecionados) < minimo:
            return f"Selecione pelo menos {minimo} opção(ões)"
        if maximo and len(selecionados) > maximo:
            return f"Selecione no máximo {maximo} opção(ões)"
        return True

    try:
        resultado = questionary.checkbox(
            mensagem,
            choices=opcoes,
            style=ESTILO_QUESTIONARY,
            validate=validate,
            instruction="(Espaço para marcar, Enter para confirmar)",
        ).ask()

        return resultado if resultado else []
    except KeyboardInterrupt:
        return []


def pedir_data(
    mensagem: str = "Data (DD/MM/AAAA):",
    obrigatorio: bool = True,
    padrao: str = "",
) -> Optional[str]:
    """
    Solicita data com validação de formato.

    Args:
        mensagem: Prompt a exibir.
        obrigatorio: Se campo é obrigatório.
        padrao: Valor padrão.

    Returns:
        Data no formato DD/MM/AAAA ou None.
    """
    from src.interface.core.validators import validar_data

    return pedir_texto(
        mensagem,
        obrigatorio=obrigatorio,
        padrao=padrao,
        validador=validar_data,
        erro_validacao="Formato inválido. Use DD/MM/AAAA",
    )


def pedir_cpf(
    mensagem: str = "CPF:",
    obrigatorio: bool = True,
) -> Optional[str]:
    """
    Solicita CPF com validação de formato.

    Args:
        mensagem: Prompt a exibir.
        obrigatorio: Se campo é obrigatório.

    Returns:
        CPF (apenas dígitos) ou None.
    """
    from src.interface.core.validators import validar_cpf, limpar_cpf

    resultado = pedir_texto(
        mensagem,
        obrigatorio=obrigatorio,
        validador=validar_cpf,
        erro_validacao="CPF deve ter 11 dígitos",
    )

    if resultado:
        return limpar_cpf(resultado)
    return None


def pedir_inteiro(
    mensagem: str,
    obrigatorio: bool = True,
    minimo: Optional[int] = None,
    maximo: Optional[int] = None,
    padrao: Optional[int] = None,
) -> Optional[int]:
    """
    Solicita número inteiro com validação.

    Args:
        mensagem: Prompt a exibir.
        obrigatorio: Se campo é obrigatório.
        minimo: Valor mínimo aceito.
        maximo: Valor máximo aceito.
        padrao: Valor padrão.

    Returns:
        Número inteiro ou None.
    """

    def validar(valor: str) -> bool:
        try:
            num = int(valor)
            if minimo is not None and num < minimo:
                return False
            if maximo is not None and num > maximo:
                return False
            return True
        except ValueError:
            return False

    # Monta mensagem de erro
    partes_erro = ["Digite um número inteiro"]
    if minimo is not None and maximo is not None:
        partes_erro.append(f"entre {minimo} e {maximo}")
    elif minimo is not None:
        partes_erro.append(f"maior ou igual a {minimo}")
    elif maximo is not None:
        partes_erro.append(f"menor ou igual a {maximo}")

    resultado = pedir_texto(
        mensagem,
        obrigatorio=obrigatorio,
        padrao=str(padrao) if padrao is not None else "",
        validador=validar,
        erro_validacao=" ".join(partes_erro),
    )

    if resultado:
        return int(resultado)
    return None


def pedir_mes_ano(
    mensagem: str = "Mês/Ano (MM/AAAA):",
    obrigatorio: bool = True,
) -> Optional[str]:
    """
    Solicita mês/ano com validação.

    Args:
        mensagem: Prompt a exibir.
        obrigatorio: Se campo é obrigatório.

    Returns:
        String MM/AAAA ou None.
    """
    from src.interface.core.validators import validar_mes_ano

    return pedir_texto(
        mensagem,
        obrigatorio=obrigatorio,
        validador=validar_mes_ano,
        erro_validacao="Formato inválido. Use MM/AAAA ou MM.AAAA",
    )


def pedir_caminho(
    mensagem: str = "Caminho:",
    deve_existir: bool = True,
    tipo: str = "any",  # "file", "dir", "any"
) -> Optional[str]:
    """
    Solicita caminho de arquivo ou diretório.

    Args:
        mensagem: Prompt a exibir.
        deve_existir: Se caminho deve existir.
        tipo: Tipo esperado ("file", "dir", "any").

    Returns:
        Caminho ou None.
    """
    from pathlib import Path

    def validar(valor: str) -> bool:
        if not deve_existir:
            return True

        caminho = Path(valor)
        if not caminho.exists():
            return False

        if tipo == "file" and not caminho.is_file():
            return False
        if tipo == "dir" and not caminho.is_dir():
            return False

        return True

    tipo_nome = {"file": "arquivo", "dir": "diretório", "any": "caminho"}
    erro = f"O {tipo_nome.get(tipo, 'caminho')} não existe"

    try:
        resultado = questionary.path(
            mensagem,
            style=ESTILO_QUESTIONARY,
            validate=validar if deve_existir else lambda x: True,
        ).ask()

        return resultado.strip() if resultado else None
    except KeyboardInterrupt:
        return None
    except Exception:
        # Fallback para pedir_texto se questionary.path não funcionar
        return pedir_texto(
            mensagem,
            validador=validar if deve_existir else None,
            erro_validacao=erro,
        )
