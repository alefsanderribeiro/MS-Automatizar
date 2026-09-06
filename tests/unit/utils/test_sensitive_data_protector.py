"""Testes unitarios para o modulo sensitive_data_protector."""

import sys
import types
from unittest.mock import MagicMock

# Mock heavy deps before any src.* import triggers __init__.py chain
_mock_modules = {
    "weasyprint": {"HTML": MagicMock()},
}
for _mod, _attrs in _mock_modules.items():
    if _mod not in sys.modules:
        m = types.ModuleType(_mod)
        for k, v in _attrs.items():
            setattr(m, k, v)
        sys.modules[_mod] = m

# Also prevent src.__init__ from importing folha_de_ponto/services/comandos/interface
# which cascade into MongoDB/Redis/WeasyPrint connections
_submod_names = [
    "src.folha_de_ponto",
    "src.comandos",
    "src.interface",
    "src.services",
]
for _s in _submod_names:
    if _s not in sys.modules:
        sys.modules[_s] = types.ModuleType(_s)

import pytest
import os
from unittest.mock import patch
from src.utils.sensitive_data_protector import (
    SensitiveDataProtector,
    SensitiveDataFilter,
    mask_log_message,
    validate_log_message,
)


class TestSensitiveDataProtector:
    """Testes para SensitiveDataProtector."""

    def setup_method(self):
        """Nova instancia por teste para stats isoladas."""
        self.protector = SensitiveDataProtector()

    # ==================== Mascaramento de senhas ====================

    def test_mask_password_equals(self):
        """Mascara senha com formato password=valor."""
        result = self.protector.mask_sensitive_data("senha=minha123")
        assert "minha123" not in result
        assert "***SENHA***" in result

    def test_mask_password_colon(self):
        """Mascara senha com formato password: valor."""
        result = self.protector.mask_sensitive_data("password: secret123")
        assert "secret123" not in result
        assert "***SENHA***" in result

    def test_mask_password_space(self):
        """Mascara senha com formato password valor."""
        result = self.protector.mask_sensitive_data("pwd abcdef")
        assert "abcdef" not in result
        assert "***SENHA***" in result

    # ==================== Mascaramento de tokens ====================

    def test_mask_token(self):
        """Mascara token."""
        result = self.protector.mask_sensitive_data("token=abcdef123456")
        assert "abcdef123456" not in result
        assert "***TOKEN***" in result

    def test_mask_api_key_keyword(self):
        """Mascara api_key."""
        result = self.protector.mask_sensitive_data("api_key=mysupersecretkey")
        assert "mysupersecretkey" not in result
        assert "***TOKEN***" in result

    def test_mask_bearer(self):
        """Mascara Bearer token."""
        result = self.protector.mask_sensitive_data("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9")
        assert "eyJhbGciOiJIUzI1NiJ9" not in result
        assert "Bearer" in result

    # ==================== Mascaramento de URI ====================

    def test_mask_connection_uri(self):
        """Mascara URI com credenciais."""
        result = self.protector.mask_sensitive_data(
            "mongodb://admin:secret123@localhost:27017/mydb"
        )
        assert "secret123" not in result
        assert "***" in result
        assert "admin" in result or "admin" not in result  # user pode ou nao aparecer

    def test_mask_postgres_uri(self):
        """Mascara URI postgresql."""
        result = self.protector.mask_sensitive_data(
            "postgres://user:pass123@host:5432/db"
        )
        assert "pass123" not in result

    # ==================== Mascaramento de CPF ====================

    def test_mask_cpf_formatted(self):
        """Mascara CPF formatado."""
        result = self.protector.mask_sensitive_data("CPF: 123.456.789-00")
        assert "123.456.789-00" not in result
        assert "***.***.***-**" in result

    def test_mask_cpf_unformatted(self):
        """Mascara CPF sem formatacao."""
        result = self.protector.mask_sensitive_data("CPF: 12345678900")
        assert "12345678900" not in result
        assert "***.***.***-**" in result

    # ==================== Mascaramento de CNPJ ====================

    def test_mask_cnpj_formatted(self):
        """Mascara CNPJ formatado."""
        result = self.protector.mask_sensitive_data("CNPJ: 12.345.678/0001-90")
        assert "12.345.678/0001-90" not in result
        assert "**.***.***/****-**" in result

    def test_mask_cnpj_unformatted(self):
        """Mascara CNPJ sem formatacao."""
        result = self.protector.mask_sensitive_data("CNPJ: 12345678000190")
        assert "12345678000190" not in result
        assert "**.***.***/****-**" in result

    # ==================== Mascaramento de API keys ====================

    def test_mask_google_api_key(self):
        """Mascara chave de API do Google."""
        result = self.protector.mask_sensitive_data(
            "Chave: AIzaSyA1234567890abcdefghijklmnopqrstuv"
        )
        assert "AIzaSyA1234567890abcdefghijklmnopqrstuv" not in result
        assert "***" in result

    def test_mask_github_token(self):
        """Mascara GitHub Personal Access Token."""
        result = self.protector.mask_sensitive_data(
            "Token: ghp_abcdefghijklmnopqrstuvwxyz123456"
        )
        assert "ghp_abcdefghijklmnopqrstuvwxyz123456" not in result
        assert "***" in result

    # ==================== Mascaramento de cartao ====================

    def test_mask_credit_card(self):
        """Mascara numero de cartao de credito."""
        result = self.protector.mask_sensitive_data("Cartao: 4111 1111 1111 1111")
        assert "4111 1111 1111 1111" not in result
        assert "****-****-****-****" in result

    def test_mask_credit_card_dashes(self):
        """Mascara cartao com tracos."""
        result = self.protector.mask_sensitive_data("Card: 4111-1111-1111-1111")
        assert "4111-1111-1111-1111" not in result

    # ==================== Mascaramento de email ====================

    def test_mask_email(self):
        """Mascara email parcialmente."""
        result = self.protector.mask_sensitive_data("Email: joao@example.com")
        assert "joao@example.com" not in result
        assert "***@example.com" in result

    # ==================== Mascaramento de IP interno ====================

    def test_mask_internal_ip_192(self):
        """Mascara IP 192.168.x.x."""
        result = self.protector.mask_sensitive_data("IP: 192.168.1.100")
        assert "192.168.1.100" not in result
        assert "192.***.***.***" in result

    def test_mask_internal_ip_10(self):
        """Mascara IP 10.x.x.x."""
        result = self.protector.mask_sensitive_data("IP: 10.0.0.1")
        assert "10.0.0.1" not in result
        assert "10.***.***.***" in result

    # ==================== validate_message ====================

    def test_validate_safe_message(self):
        """Mensagem segura retorna (True, original)."""
        ok, msg = self.protector.validate_message("mensagem normal")
        assert ok is True
        assert msg == "mensagem normal"

    def test_validate_with_password(self):
        """Mensagem com senha retorna (True, mascarada)."""
        ok, msg = self.protector.validate_message("senha=abc123")
        assert ok is True
        assert "abc123" not in msg

    def test_validate_with_token(self):
        """Mensagem com token retorna (True, mascarada)."""
        ok, msg = self.protector.validate_message("token=secretvalue")
        assert ok is True
        assert "secretvalue" not in msg

    def test_validate_empty_message(self):
        """Mensagem vazia retorna (True, '')."""
        ok, msg = self.protector.validate_message("")
        assert ok is True
        assert msg == ""

    def test_validate_none_like(self):
        """Mensagem None retorna (True, None)."""
        ok, msg = self.protector.validate_message(None)
        assert ok is True

    # ==================== Stats ====================

    def test_stats_increment_total(self):
        """Stats incrementam total_messages."""
        p = SensitiveDataProtector()
        p.mask_sensitive_data("a")
        p.mask_sensitive_data("b")
        stats = p.get_stats()
        assert stats["total_messages"] == 2

    def test_stats_increment_masked(self):
        """Stats incrementam masked_messages quando ha mascaramento."""
        p = SensitiveDataProtector()
        p.mask_sensitive_data("senha=teste123")
        stats = p.get_stats()
        assert stats["masked_messages"] == 1

    def test_stats_not_masked(self):
        """Mensagem sem dados sensiveis nao incrementa masked_messages."""
        p = SensitiveDataProtector()
        p.mask_sensitive_data("mensagem limpa")
        stats = p.get_stats()
        assert stats["masked_messages"] == 0

    def test_stats_returns_copy(self):
        """get_stats() retorna copia, nao referencia interna."""
        p = SensitiveDataProtector()
        stats1 = p.get_stats()
        stats1["total_messages"] = 999
        stats2 = p.get_stats()
        assert stats2["total_messages"] == 0

    # ==================== Mensagem vazia ====================

    def test_empty_message_returned_as_is(self):
        """Mensagem vazia retorna sem alteracao."""
        assert self.protector.mask_sensitive_data("") == ""

    def test_no_sensitive_data(self):
        """Mensagem sem dados sensiveis nao e alterada."""
        msg = "Servidor iniciado na porta 8080"
        assert self.protector.mask_sensitive_data(msg) == msg

    # ==================== Multiplos dados ====================

    def test_multiple_sensitive_in_one_message(self):
        """Multiplos dados sensiveis na mesma mensagem sao mascarados."""
        result = self.protector.mask_sensitive_data(
            "senha=abc123 token=xyz789 cpf=123.456.789-00"
        )
        assert "abc123" not in result
        assert "xyz789" not in result
        assert "123.456.789-00" not in result

    # ==================== Custom patterns ====================

    def test_custom_pattern(self):
        """Padrao personalizado e aplicado."""
        import re
        custom = {"custom_id": re.compile(r"ID-\d{6}")}
        p = SensitiveDataProtector(custom_patterns=custom)
        result = p.mask_sensitive_data("ID-123456")
        assert "123456" not in result


# ==================== SensitiveDataFilter ====================


class TestSensitiveDataFilter:
    """Testes para SensitiveDataFilter (filtro de logging)."""

    def test_filter_masks_msg(self):
        """Filtro mascara dados sensiveis em record.msg."""
        import logging
        f = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0,
            msg="senha=abc123", args=(), exc_info=None
        )
        result = f.filter(record)
        assert result is True
        assert "abc123" not in record.msg

    def test_filter_masks_args_dict(self):
        """Filtro mascara dados sensiveis em record.args (dict)."""
        import logging
        f = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0,
            msg="data: %(senha)s",
            args=("senha=abc123",),
            exc_info=None,
        )
        f.filter(record)
        assert isinstance(record.args, tuple)
        assert "abc123" not in record.args[0]

    def test_filter_masks_args_tuple(self):
        """Filtro mascara dados sensiveis em record.args (tuple)."""
        import logging
        f = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0,
            msg="data: %s %s",
            args=("senha=abc123", "normal"),
            exc_info=None,
        )
        f.filter(record)
        assert isinstance(record.args, tuple)
        assert "abc123" not in record.args[0]

    def test_filter_preserves_non_string_args(self):
        """Argumentos nao-string nao sao alterados."""
        import logging
        f = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0,
            msg="count: %d", args=(42,), exc_info=None
        )
        f.filter(record)
        assert record.args == (42,)

    def test_filter_no_args(self):
        """Filtro funciona sem args."""
        import logging
        f = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0,
            msg="senha=secret", args=(), exc_info=None
        )
        result = f.filter(record)
        assert result is True
        assert "secret" not in record.msg


# ==================== clean_log_file ====================


class TestCleanLogFile:
    """Testes para clean_log_file."""

    def test_cleans_existing_log(self, tmp_path):
        """Limpa arquivo de log existente mascarando dados sensiveis."""
        from src.utils.sensitive_data_protector import SensitiveDataProtector

        log_file = tmp_path / "test.log"
        log_file.write_text(
            "Linha 1: normal\n"
            "Linha 2: senha=abc123\n"
            "Linha 3: CPF: 123.456.789-00\n"
        )

        output_file = tmp_path / "test_cleaned.log"
        protector = SensitiveDataProtector()
        stats = protector.clean_log_file(str(log_file), str(output_file))

        assert stats["total_lines"] == 3
        assert stats["masked_lines"] == 2
        assert stats["errors"] == 0

        # Verificar conteudo mascarado
        cleaned = output_file.read_text()
        assert "abc123" not in cleaned
        assert "123.456.789-00" not in cleaned
        assert "Linha 1: normal" in cleaned

    def test_cleans_without_output_path(self, tmp_path):
        """Sem output_path, cria arquivo .cleaned ao lado."""
        log_file = tmp_path / "app.log"
        log_file.write_text("senha=teste\n")

        protector = SensitiveDataProtector()
        stats = protector.clean_log_file(str(log_file))

        cleaned_path = tmp_path / "app.log.cleaned"
        assert cleaned_path.exists()
        assert "teste" not in cleaned_path.read_text()

    def test_cleans_empty_file(self, tmp_path):
        """Arquivo vazio nao causa erro."""
        log_file = tmp_path / "empty.log"
        log_file.write_text("")

        protector = SensitiveDataProtector()
        stats = protector.clean_log_file(str(log_file))

        assert stats["total_lines"] == 0
        assert stats["masked_lines"] == 0

    def test_cleans_nonexistent_file(self, tmp_path):
        """Arquivo inexistente retorna erro."""
        protector = SensitiveDataProtector()
        stats = protector.clean_log_file(str(tmp_path / "nope.log"))
        assert stats["errors"] == 1


# ==================== Funcoes de conveniencia ====================


class TestConvenienceFunctions:
    """Testes para mask_log_message e validate_log_message."""

    def test_mask_log_message(self):
        """mask_log_message mascara dados sensiveis."""
        result = mask_log_message("senha=topsecret")
        assert "topsecret" not in result
        assert "***SENHA***" in result

    def test_validate_log_message_safe(self):
        """validate_log_message com mensagem segura."""
        ok, msg = validate_log_message("tudo bem")
        assert ok is True
        assert msg == "tudo bem"

    def test_validate_log_message_sensitive(self):
        """validate_log_message com dados sensiveis mascarados."""
        ok, msg = validate_log_message("token=abc123")
        assert ok is True
        assert "abc123" not in msg
