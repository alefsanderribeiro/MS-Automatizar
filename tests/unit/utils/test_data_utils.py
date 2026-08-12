"""Testes para `src.utils.data_utils`.

Cobre o utilitário central de conversão/formatação de datas:
- parse_data_flexivel: DD/MM/YYYY, YYYY-MM-DD, ambíguo, inválido, datetime.
- formatar_data_br: exibição sempre em DD/MM/YYYY.
- formatar_data_hora_br, date_para_datetime_inicio/fim.
"""

from datetime import date, datetime

import pytest

from src.utils.data_utils import (
    parse_data_flexivel,
    formatar_data_br,
    formatar_data_hora_br,
    date_para_datetime_inicio,
    date_para_datetime_fim,
)


# ==================== parse_data_flexivel ====================

class TestParseDataFlexivel:
    def test_formato_brasileiro_dd_mm_yyyy(self):
        resultado = parse_data_flexivel("15/08/2026")
        assert isinstance(resultado, datetime)
        assert resultado == datetime(2026, 8, 15, 0, 0)

    def test_formato_iso_yyyy_mm_dd(self):
        resultado = parse_data_flexivel("2026-08-15")
        assert resultado == datetime(2026, 8, 15, 0, 0)

    def test_formato_ambiguo_interpretado_dia_mes_ano(self):
        # 01/02/2026 -> 1 de fevereiro (padrão brasileiro DD/MM/YYYY)
        resultado = parse_data_flexivel("01/02/2026")
        assert resultado == datetime(2026, 2, 1, 0, 0)

    def test_retorna_date_quando_solicitado(self):
        resultado = parse_data_flexivel("02/12/2025", retornar_date=True)
        assert isinstance(resultado, date)
        assert resultado == date(2025, 12, 2)

    def test_iso_retorna_date_quando_solicitado(self):
        resultado = parse_data_flexivel("2025-12-02", retornar_date=True)
        assert resultado == date(2025, 12, 2)

    def test_datetime_com_hora_iso(self):
        resultado = parse_data_flexivel("2026-08-15T09:30:00")
        assert resultado == datetime(2026, 8, 15, 9, 30, 0)

    def test_datetime_com_hora_br(self):
        resultado = parse_data_flexivel("15/08/2026 09:30")
        assert resultado == datetime(2026, 8, 15, 9, 30, 0)

    def test_caracteres_espaco(self):
        resultado = parse_data_flexivel("  15/08/2026  ")
        assert resultado == datetime(2026, 8, 15, 0, 0)

    def test_valor_vazio_retorna_none(self):
        assert parse_data_flexivel("") is None
        assert parse_data_flexivel("   ") is None
        assert parse_data_flexivel(None) is None

    def test_valor_invalido_retorna_none(self):
        assert parse_data_flexivel("abc") is None
        assert parse_data_flexivel("32/13/2026") is None
        assert parse_data_flexivel("2026-13-45") is None
        assert parse_data_flexivel("15/08") is None

    def test_ano_bissexto(self):
        # 29/02/2024 é bissexto -> válido
        assert parse_data_flexivel("29/02/2024") == datetime(2024, 2, 29, 0, 0)
        # 29/02/2025 não é bissexto -> inválido
        assert parse_data_flexivel("29/02/2025") is None

    def test_iso_digitos_unicos_aceito(self):
        # BUG 3: ISO com 1 dígito em dia/mês (2026-8-5) deve ser aceito.
        assert parse_data_flexivel("2026-8-5") == datetime(2026, 8, 5, 0, 0)
        assert parse_data_flexivel("2026-08-5") == datetime(2026, 8, 5, 0, 0)
        assert parse_data_flexivel("2026-8-15") == datetime(2026, 8, 15, 0, 0)
        assert parse_data_flexivel("2026-8-5", retornar_date=True) == date(2026, 8, 5)

    def test_ano_dois_digitos_br_aceito(self):
        # BUG 4: 15/08/26 -> 15/08/2026
        assert parse_data_flexivel("15/08/26") == datetime(2026, 8, 15, 0, 0)
        assert parse_data_flexivel("01/12/99") == datetime(1999, 12, 1, 0, 0)

    def test_formato_americano_invertido_recusado(self):
        # BUG 4: 2026/08/15 (barras no estilo americano) é recusado.
        assert parse_data_flexivel("2026/08/15") is None


# ==================== formatar_data_br ====================

class TestFormatarDataBr:
    def test_date_objeto(self):
        assert formatar_data_br(date(2026, 8, 15)) == "15/08/2026"

    def test_datetime_objeto(self):
        assert formatar_data_br(datetime(2026, 8, 15, 10, 30)) == "15/08/2026"

    def test_string_iso(self):
        assert formatar_data_br("2026-08-15") == "15/08/2026"

    def test_string_datetime_iso(self):
        assert formatar_data_br("2026-08-15T09:30:00") == "15/08/2026"

    def test_string_ja_em_dd_mm_yyyy(self):
        assert formatar_data_br("15/08/2026") == "15/08/2026"

    def test_none_retorna_vazio(self):
        assert formatar_data_br(None) == ""

    def test_valor_nao_interpretavel_retorna_original(self):
        assert formatar_data_br("qualquer-coisa") == "qualquer-coisa"


# ==================== formatar_data_hora_br ====================

class TestFormatarDataHoraBr:
    def test_datetime_com_hora(self):
        assert formatar_data_hora_br(datetime(2026, 8, 15, 9, 30)) == "15/08/2026 09:30"

    def test_date_sem_hora(self):
        assert formatar_data_hora_br(date(2026, 8, 15)) == "15/08/2026"

    def test_none(self):
        assert formatar_data_hora_br(None) == ""


# ==================== conversões para datetime (queries Mongo) ====================

class TestConversoesDatetimeMongo:
    def test_date_para_datetime_inicio(self):
        resultado = date_para_datetime_inicio(date(2026, 8, 15))
        assert resultado == datetime(2026, 8, 15, 0, 0)

    def test_date_para_datetime_fim(self):
        resultado = date_para_datetime_fim(date(2026, 8, 15))
        assert resultado.hour == 23 and resultado.minute == 59 and resultado.second == 59
        assert resultado.date() == date(2026, 8, 15)

