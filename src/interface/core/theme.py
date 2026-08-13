"""
Tema centralizado para toda a interface.

Define cores, estilos e ícones padronizados que são utilizados
em todos os menus e componentes do sistema.

Uso:
    from src.interface.core.theme import console, ICONES, ESTILO_QUESTIONARY

    console.print("[sucesso]Operação concluída![/sucesso]")
    console.print(f"{ICONES['sucesso']} Tudo certo!")
"""

import sys
from rich.console import Console
from rich.theme import Theme
from questionary import Style as QStyle


# Detecta se o terminal suporta Unicode completo
def _suporta_unicode() -> bool:
    """Verifica se o terminal suporta emojis/Unicode."""
    try:
        # Tenta encodar um emoji
        "\u2705".encode(sys.stdout.encoding or "utf-8")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


_UNICODE_SUPORTADO = _suporta_unicode()


# ═══════════════════════════════════════════════════════════════
# TEMA RICH - Cores e estilos para console
# ═══════════════════════════════════════════════════════════════

TEMA_CUSTOM = Theme({
    # Títulos e cabeçalhos
    "titulo": "bold cyan",
    "subtitulo": "bold blue",
    "titulo.secundario": "bold white",

    # Status
    "sucesso": "bold green",
    "erro": "bold red",
    "aviso": "bold yellow",
    "info": "dim white",

    # Destaques
    "destaque": "bold magenta",
    "destaque.secundario": "bold cyan",
    "valor": "cyan",
    "chave": "bold white",

    # Menu
    "menu.titulo": "bold cyan on dark_blue",
    "menu.opcao": "white",
    "menu.tecla": "bold cyan",
    "menu.separador": "dim white",

    # Tabelas
    "tabela.cabecalho": "bold cyan",
    "tabela.linha": "white",
    "tabela.indice": "dim cyan",

    # Inputs
    "input.label": "bold white",
    "input.valor": "cyan",
    "input.placeholder": "dim white",

    # Painéis
    "painel.borda": "cyan",
    "painel.titulo": "bold cyan",
})

# Console global com tema aplicado
# force_terminal=True e legacy_windows=False forçam modo moderno no Windows
console = Console(
    theme=TEMA_CUSTOM,
    force_terminal=True,
    legacy_windows=False if _UNICODE_SUPORTADO else None,
)


# ═══════════════════════════════════════════════════════════════
# ESTILO QUESTIONARY - Para prompts interativos
# ═══════════════════════════════════════════════════════════════

ESTILO_QUESTIONARY = QStyle([
    # Marcador de pergunta
    ("qmark", "fg:cyan bold"),

    # Texto da pergunta
    ("question", "fg:white bold"),

    # Resposta selecionada
    ("answer", "fg:cyan"),

    # Ponteiro de seleção (>)
    ("pointer", "fg:cyan bold"),

    # Item destacado na lista
    ("highlighted", "fg:cyan bold"),

    # Item selecionado (checkbox)
    ("selected", "fg:green"),

    # Separador visual
    ("separator", "fg:#808080"),

    # Instrução (texto de ajuda)
    ("instruction", "fg:#808080 italic"),

    # Texto inválido
    ("invalid", "fg:red bold"),

    # Texto de validação
    ("validation-error", "fg:red"),
])


# ═══════════════════════════════════════════════════════════════
# ÍCONES PADRONIZADOS
# ═══════════════════════════════════════════════════════════════

# Ícones Unicode (emojis) para terminais modernos
_ICONES_UNICODE = {
    # Navegação
    "menu": "📋",
    "voltar": "↩️",
    "sair": "🚪",
    "home": "🏠",

    # Status
    "sucesso": "✅",
    "erro": "❌",
    "aviso": "⚠️",
    "info": "ℹ️",
    "pendente": "⏳",
    "processando": "⚙️",

    # Ações CRUD
    "criar": "➕",
    "editar": "✏️",
    "excluir": "🗑️",
    "listar": "📄",
    "buscar": "🔍",
    "atualizar": "🔄",
    "salvar": "💾",

    # Entidades do sistema
    "empresa": "🏢",
    "funcionario": "👤",
    "funcionarios": "👥",
    "holerite": "📑",
    "folha_ponto": "📅",
    "contrato": "📝",
    "horario": "🕐",
    "funcao": "💼",
    "diretorio": "📁",
    "feriado": "🎉",

    # Comunicação
    "email": "📧",
    "whatsapp": "💬",
    "enviar": "📤",
    "receber": "📥",

    # Configuração
    "config": "⚙️",
    "chave": "🔑",
    "banco_dados": "🗄️",
    "api": "🔌",

    # Dados
    "estatistica": "📊",
    "relatorio": "📈",
    "dados": "💾",
    "cache": "🗃️",

    # Processamento
    "processar": "⚙️",
    "ia": "🤖",
    "pdf": "📕",
    "excel": "📗",

    # Diversos
    "calendario": "📆",
    "relogio": "⏰",
    "dinheiro": "💰",
    "check": "☑️",
    "uncheck": "☐",
    "ponto": "•",
    "seta_direita": "→",
    "seta_baixo": "↓",
}

# Ícones ASCII para terminais Windows sem suporte Unicode
_ICONES_ASCII = {
    # Navegação
    "menu": "[=]",
    "voltar": "<-",
    "sair": "[X]",
    "home": "[H]",

    # Status
    "sucesso": "[OK]",
    "erro": "[X]",
    "aviso": "[!]",
    "info": "[i]",
    "pendente": "[...]",
    "processando": "[*]",

    # Ações CRUD
    "criar": "[+]",
    "editar": "[E]",
    "excluir": "[-]",
    "listar": "[L]",
    "buscar": "[?]",
    "atualizar": "[R]",
    "salvar": "[S]",

    # Entidades do sistema
    "empresa": "[E]",
    "funcionario": "[F]",
    "funcionarios": "[FF]",
    "holerite": "[H]",
    "folha_ponto": "[FP]",
    "contrato": "[C]",
    "horario": "[T]",
    "funcao": "[Fn]",
    "diretorio": "[D]",
    "feriado": "[Fe]",

    # Comunicação
    "email": "[@]",
    "whatsapp": "[W]",
    "enviar": "[>>]",
    "receber": "[<<]",

    # Configuração
    "config": "[#]",
    "chave": "[K]",
    "banco_dados": "[DB]",
    "api": "[API]",

    # Dados
    "estatistica": "[%]",
    "relatorio": "[R]",
    "dados": "[D]",
    "cache": "[C]",

    # Processamento
    "processar": "[*]",
    "ia": "[AI]",
    "pdf": "[PDF]",
    "excel": "[XLS]",

    # Diversos
    "calendario": "[Cal]",
    "relogio": "[T]",
    "dinheiro": "[$]",
    "check": "[x]",
    "uncheck": "[ ]",
    "ponto": "*",
    "seta_direita": "->",
    "seta_baixo": "v",
}

# Seleciona o conjunto de ícones baseado no suporte do terminal
ICONES = _ICONES_UNICODE if _UNICODE_SUPORTADO else _ICONES_ASCII


# ═══════════════════════════════════════════════════════════════
# CONFIGURAÇÕES DE LAYOUT
# ═══════════════════════════════════════════════════════════════

LAYOUT = {
    # Larguras
    "largura_menu": 50,
    "largura_tabela": 80,
    "largura_painel": 60,

    # Paginação
    "itens_por_pagina": 10,

    # Bordas
    "estilo_borda": "rounded",  # rounded, square, double, heavy
}
