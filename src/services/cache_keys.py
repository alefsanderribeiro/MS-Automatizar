"""
Formadores centralizados de chaves de cache (Redis + memória).

Esquema de chaves padronizado para garantir que LEITURA e INVALIDAÇÃO usem
SEMPRE o MESMO padrão (evita cache *stale* por chave divergente):

    {entidade}:{id}                -> registro individual  ex: "funcoes:507f..."
    {entidade}:all                 -> lista completa       ex: "funcoes:all"
    {entidade}:ativos              -> lista de ativos      ex: "funcoes:ativos"
    {entidade}:{nome_normalizado}  -> lookup por nome      ex: "funcoes:analista"
    {entidade}:{ano}               -> agregado por ano     ex: "feriados:2025"
    {entidade}:{ano}-{mes}         -> agregado por mês     ex: "feriados:2025-08"

Regra de ouro: toda leitura de ``{prefixo}:...`` deve ser invalidável
escaneando ``{prefixo}:*``. Cada entidade fornece:

- ``{entidade}_key(id)``           -> chave de um registro
- ``{entidade}_all_key()``         -> chave da lista completa (quando cacheada)
- ``{entidade}_prefix()``          -> padrão de invalidação em massa "{entidade}:*"
"""

import os
import unicodedata


def ttl_padrao() -> int:
    """Retorna o TTL padrão (segundos) lido de CACHE_TTL (default 300s)."""
    return int(os.getenv("CACHE_TTL", "300"))


def normalizar_nome(texto: str) -> str:
    """
    Normaliza texto para uso em chave de cache por nome.

    Remove acentos, converte para minúsculas e faz trim — garante que a
    MESMA entrada sempre gere a MESMA chave entre escrita e leitura.
    """
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


# ==================== empresas ====================

def empresa_key(empresa_id) -> str:
    return f"empresas:{empresa_id}"


def empresas_prefix() -> str:
    return "empresas:*"


# ==================== contratos ====================

def contrato_key(contrato_id) -> str:
    return f"contratos:{contrato_id}"


def contratos_prefix() -> str:
    return "contratos:*"


# ==================== diretórios ====================

def diretorio_key(diretorio_id) -> str:
    return f"diretorios:{diretorio_id}"


def diretorio_por_contrato_key(contrato_id) -> str:
    return f"diretorios:contrato:{contrato_id}"


def diretorios_prefix() -> str:
    return "diretorios:*"


# ==================== funções ====================

def funcao_key(funcao_id) -> str:
    return f"funcoes:{funcao_id}"


def funcoes_prefix() -> str:
    return "funcoes:*"


# ==================== horários ====================

def horario_key(horario_id) -> str:
    return f"horarios:{horario_id}"


def horarios_prefix() -> str:
    return "horarios:*"


# ==================== feriados ====================

def feriados_ano_key(ano: int) -> str:
    return f"feriados:{ano}"


def feriados_ano_mes_key(ano: int, mes: int) -> str:
    return f"feriados:{ano}-{mes:02d}"


def feriado_periodo_key(data_inicio, data_fim) -> str:
    início = data_inicio.strftime("%Y-%m-%d") if hasattr(data_inicio, "strftime") else str(data_inicio)
    fim = data_fim.strftime("%Y-%m-%d") if hasattr(data_fim, "strftime") else str(data_fim)
    return f"feriados:periodo:{início}_{fim}"


def feriados_prefix() -> str:
    return "feriados:*"


# ==================== templates de mensagem ====================

def template_key(template_id) -> str:
    return f"templates:{template_id}"


def template_nome_key(nome_normalizado: str) -> str:
    return f"templates:nome:{nome_normalizado}"


def template_tipo_key(tipo: str) -> str:
    return f"templates:tipo:{tipo}"


def templates_prefix() -> str:
    return "templates:*"


# ==================== grupos WhatsApp ====================

def grupo_wa_key(device_id: str, nome_normalizado: str) -> str:
    return f"grupos_wa:{device_id}:{nome_normalizado}"


def grupos_wa_prefix() -> str:
    return "grupos_wa:*"


def grupos_wa_device_prefix(device_id: str) -> str:
    return f"grupos_wa:{device_id}:*"
