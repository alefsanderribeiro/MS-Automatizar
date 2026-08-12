"""
Unit tests for the central cache key builders (src/services/cache_keys.py).

Garante que LEITURA e INVALIDAÇÃO usem sempre o MESMO padrão de chave — a
regra de ouro para evitar cache *stale* por divergência de chave.
"""
import pytest

from src.services import cache_keys


# ==================== normalizar_nome ====================

class TestNormalizarNome:
    def test_remove_acentos_e_minusculas(self):
        assert cache_keys.normalizar_nome("Administrativo") == "administrativo"
        assert cache_keys.normalizar_nome("Análise de Sistemas") == "analise de sistemas"

    def test_trim(self):
        assert cache_keys.normalizar_nome("  Motorista  ") == "motorista"

    def test_vazio(self):
        assert cache_keys.normalizar_nome("") == ""
        assert cache_keys.normalizar_nome(None) == ""


# ==================== padrão por entidade ====================

def test_empresa_key_e_prefixo():
    assert cache_keys.empresa_key("abc123") == "empresas:abc123"
    assert cache_keys.empresas_prefix() == "empresas:*"


def test_contrato_key_e_prefixo():
    assert cache_keys.contrato_key("c1") == "contratos:c1"
    assert cache_keys.contratos_prefix() == "contratos:*"


def test_diretorio_keys_e_prefixo():
    assert cache_keys.diretorio_key("d1") == "diretorios:d1"
    assert cache_keys.diretorio_por_contrato_key("c2") == "diretorios:contrato:c2"
    assert cache_keys.diretorios_prefix() == "diretorios:*"


def test_funcao_key_e_prefixo():
    assert cache_keys.funcao_key("f1") == "funcoes:f1"
    assert cache_keys.funcoes_prefix() == "funcoes:*"


def test_horario_key_e_prefixo():
    assert cache_keys.horario_key("h1") == "horarios:h1"
    assert cache_keys.horarios_prefix() == "horarios:*"


def test_feriado_keys():
    assert cache_keys.feriados_ano_key(2025) == "feriados:2025"
    assert cache_keys.feriados_ano_mes_key(2025, 8) == "feriados:2025-08"
    assert cache_keys.feriados_prefix() == "feriados:*"


def test_template_keys():
    assert cache_keys.template_key("t1") == "templates:t1"
    assert cache_keys.template_nome_key("holerite") == "templates:nome:holerite"
    assert cache_keys.template_tipo_key("whatsapp_grupo") == "templates:tipo:whatsapp_grupo"
    assert cache_keys.templates_prefix() == "templates:*"


def test_grupo_wa_keys():
    assert cache_keys.grupo_wa_key("WhatsApp-Alefe", "grupo x") == "grupos_wa:WhatsApp-Alefe:grupo x"
    assert cache_keys.grupos_wa_prefix() == "grupos_wa:*"
    assert cache_keys.grupos_wa_device_prefix("WhatsApp-Alefe") == "grupos_wa:WhatsApp-Alefe:*"


# ==================== consistência leitura ↔ invalidação ====================

def test_leitura_e_invalidacao_do_mesmo_registro_batem():
    """A chave de leitura de um ID deve ser invalidável pela chave do mesmo ID."""
    import re
    for _id, key_builder, prefix in [
        ("abc", cache_keys.empresa_key, cache_keys.empresas_prefix()),
        ("abc", cache_keys.contrato_key, cache_keys.contratos_prefix()),
        ("abc", cache_keys.diretorio_key, cache_keys.diretorios_prefix()),
        ("abc", cache_keys.funcao_key, cache_keys.funcoes_prefix()),
        ("abc", cache_keys.horario_key, cache_keys.horarios_prefix()),
    ]:
        key = key_builder(_id)
        # A chave individual casa com o prefixo de invalidação {entidade}:*
        regex = re.compile(f"^{prefix.replace('*', '.*')}$")
        assert regex.match(key), (
            f"Chave de leitura '{key}' não é invalidável pelo padrão '{prefix}'"
        )
