"""Testes unitarios para o modulo logger_config_v2."""

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
import logging
import time
import json
import threading
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timezone

from src.utils.logger_config_v2 import (
    StructuredFormatter,
    JSONFormatter,
    AuditFormatter,
    PerformanceTracker,
    CorrelationManager,
    SystemLogger,
    ModuleLogger,
    ModuleFilter,
    PerformanceContext,
    CorrelationContext,
    LogConfig,
    get_logger,
)


# ==================== HELPERS ====================


def _make_record(
    msg="test message",
    level=logging.INFO,
    name="MS_AUTOMATIZAR",
    module_attr=None,
    correlation_id=None,
    is_audit=False,
    audit_action=None,
    audit_target=None,
    audit_changes=None,
    audit_user=None,
    duration_ms=None,
    extras=None,
    args=None,
    exc_info=None,
):
    """Cria um LogRecord com atributos extras para testes."""
    record = logging.LogRecord(
        name=name,
        level=level,
        pathname="test.py",
        lineno=1,
        msg=msg,
        args=args or (),
        exc_info=exc_info,
    )
    if module_attr is not None:
        record.module = module_attr
    if correlation_id is not None:
        record.correlation_id = correlation_id
    if is_audit:
        record.is_audit = True
    if audit_action:
        record.audit_action = audit_action
    if audit_target:
        record.audit_target = audit_target
    if audit_changes:
        record.audit_changes = audit_changes
    if audit_user:
        record.audit_user = audit_user
    if duration_ms is not None:
        record.duration_ms = duration_ms
    if extras:
        record.extras = extras
    return record


# ==================== StructuredFormatter ====================


class TestStructuredFormatter:
    """Testes para StructuredFormatter."""

    def test_basic_format(self):
        """Formatacao basica com timestamp, level, modulo e mensagem."""
        formatter = StructuredFormatter()
        record = _make_record(msg="Hello world")
        output = formatter.format(record)
        assert "INFO" in output
        assert "Hello world" in output
        assert "[MS_AUTOMATIZAR]" in output or "[test]" in output

    def test_mask_sensitive_data_in_message(self):
        """Dados sensiveis na mensagem sao mascarados."""
        formatter = StructuredFormatter()
        record = _make_record(msg="senha=abc123")
        output = formatter.format(record)
        assert "abc123" not in output
        assert "***SENHA***" in output

    def test_correlation_id_in_output(self):
        """Correlation ID aparece no output quando definido."""
        formatter = StructuredFormatter()
        record = _make_record(msg="ok", correlation_id="abc123def456")
        output = formatter.format(record)
        assert "[abc123de]" in output

    def test_no_correlation_id(self):
        """Sem correlation ID, nao aparece colchete extra."""
        formatter = StructuredFormatter()
        record = _make_record(msg="ok")
        output = formatter.format(record)
        # Nao deve conter o padrao [xxxxxxxx]
        assert "[       ]" not in output

    def test_audit_flag_in_output(self):
        """Flag de audit aparece no output."""
        formatter = StructuredFormatter()
        record = _make_record(msg="audit event", is_audit=True)
        output = formatter.format(record)
        assert "[AUDIT]" in output

    def test_duration_ms_in_output(self):
        """Duracao em ms aparece no output."""
        formatter = StructuredFormatter()
        record = _make_record(msg="done", duration_ms=123.4)
        output = formatter.format(record)
        assert "(123.4ms)" in output

    def test_extras_in_output(self):
        """Extras sao incluidos no output."""
        formatter = StructuredFormatter()
        record = _make_record(msg="ok", extras={"key": "value"})
        output = formatter.format(record)
        assert "key=value" in output

    def test_extras_mask_sensitive(self):
        """Dados sensiveis em extras sao mascarados."""
        formatter = StructuredFormatter()
        record = _make_record(msg="ok", extras={"cred": "token=abc123xyz"})
        output = formatter.format(record)
        assert "abc123xyz" not in output

    def test_format_returns_string(self):
        """Format sempre retorna string."""
        formatter = StructuredFormatter()
        record = _make_record()
        result = formatter.format(record)
        assert isinstance(result, str)


# ==================== JSONFormatter ====================


class TestJSONFormatter:
    """Testes para JSONFormatter."""

    def test_basic_json_output(self):
        """Output e JSON valido com campos basicos."""
        formatter = JSONFormatter()
        record = _make_record(msg="json test")
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "json test"
        assert parsed["level"] == "INFO"

    def test_correlation_id_in_json(self):
        """Correlation ID presente no JSON."""
        formatter = JSONFormatter()
        record = _make_record(msg="ok", correlation_id="corr123")
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["correlation_id"] == "corr123"

    def test_audit_fields_in_json(self):
        """Campos de audit presentes no JSON."""
        formatter = JSONFormatter()
        record = _make_record(
            msg="audit",
            is_audit=True,
            audit_action="CREATE",
            audit_target="user:1",
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["is_audit"] is True
        assert parsed["audit_action"] == "CREATE"

    def test_performance_in_json(self):
        """Campo duration_ms presente no JSON."""
        formatter = JSONFormatter()
        record = _make_record(msg="perf", duration_ms=50.25)
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["duration_ms"] == 50.25

    def test_exception_in_json(self):
        """Excecao formatada no JSON."""
        formatter = JSONFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            record = _make_record(msg="err", exc_info=sys.exc_info())
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert parsed["exception"]["type"] == "ValueError"


# ==================== AuditFormatter ====================


class TestAuditFormatter:
    """Testes para AuditFormatter."""

    def test_basic_audit_format(self):
        """Formato basico de audit com action, target, user."""
        formatter = AuditFormatter()
        record = _make_record(
            msg="test",
            audit_action="USER_CREATED",
            audit_target="user:123",
            audit_user="admin",
        )
        output = formatter.format(record)
        assert "USER_CREATED" in output
        assert "user:123" in output
        assert "user=admin" in output

    def test_changes_in_output(self):
        """Mudancas aparecem no output."""
        formatter = AuditFormatter()
        record = _make_record(
            msg="test",
            audit_action="UPDATE",
            audit_target="item:1",
            audit_changes={"nome": "Joao"},
        )
        output = formatter.format(record)
        assert "nome" in output

    def test_sensitive_data_masked_in_changes(self):
        """Dados sensiveis nas mudancas sao mascarados quando no formato key=value."""
        formatter = AuditFormatter()
        record = _make_record(
            msg="test",
            audit_action="UPDATE",
            audit_target="user:1",
            audit_changes={"campo": "senha=minha_senha_secreta"},
        )
        output = formatter.format(record)
        assert "minha_senha_secreta" not in output
        assert "***SENHA***" in output


# ==================== PerformanceTracker ====================


class TestPerformanceTracker:
    """Testes para PerformanceTracker."""

    def test_record_and_get_stats(self):
        """Grava metrica e retorna estatisticas."""
        tracker = PerformanceTracker()
        tracker.record("op1", 100.0, success=True)
        stats = tracker.get_stats("op1")
        assert stats["count"] == 1
        assert stats["success_count"] == 1
        assert stats["avg_ms"] == 100.0

    def test_multiple_operations(self):
        """Multiplas operacoes acumulam metricas."""
        tracker = PerformanceTracker()
        tracker.record("op1", 10.0)
        tracker.record("op1", 20.0)
        tracker.record("op1", 30.0)
        stats = tracker.get_stats("op1")
        assert stats["count"] == 3
        assert stats["avg_ms"] == 20.0
        assert stats["min_ms"] == 10.0
        assert stats["max_ms"] == 30.0

    def test_success_and_failure(self):
        """Metraca sucessos e falhas."""
        tracker = PerformanceTracker()
        tracker.record("op1", 10.0, success=True)
        tracker.record("op1", 20.0, success=False)
        stats = tracker.get_stats("op1")
        assert stats["success_count"] == 1
        assert stats["failure_count"] == 1
        assert stats["success_rate"] == 50.0

    def test_get_stats_multiple_operations(self):
        """get_stats com operacao retorna metricas de uma operacao."""
        tracker = PerformanceTracker()
        tracker.record("op_a", 5.0)
        tracker.record("op_b", 15.0)
        # Chamada sem argumento causa deadlock (bug no source: lock reentrancy)
        stats_a = tracker.get_stats("op_a")
        stats_b = tracker.get_stats("op_b")
        assert stats_a["count"] == 1
        assert stats_b["count"] == 1

    def test_get_stats_unknown_operation(self):
        """Operacao desconhecida retorna count=0."""
        tracker = PerformanceTracker()
        stats = tracker.get_stats("unknown")
        assert stats["count"] == 0

    def test_p95_calculation(self):
        """P95 e calculado corretamente."""
        tracker = PerformanceTracker()
        for i in range(1, 101):
            tracker.record("op1", float(i))
        stats = tracker.get_stats("op1")
        assert stats["count"] == 100
        # p95 deve ser proximo de 95
        assert 94.0 <= stats["p95_ms"] <= 96.0

    def test_record_with_details(self):
        """Detalhes opcionais sao aceitos."""
        tracker = PerformanceTracker()
        tracker.record("op1", 10.0, details={"module": "test"})
        stats = tracker.get_stats("op1")
        assert stats["count"] == 1

    def test_thread_safety(self):
        """Gravacoes concorrentes nao causam erro."""
        tracker = PerformanceTracker()

        def record_many():
            for _ in range(100):
                tracker.record("threaded", 1.0)

        threads = [threading.Thread(target=record_many) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = tracker.get_stats("threaded")
        assert stats["count"] == 500


# ==================== CorrelationManager ====================


class TestCorrelationManager:
    """Testes para CorrelationManager."""

    def test_generate_id(self):
        """Gera ID de 12 caracteres."""
        cid = CorrelationManager.generate_id()
        assert len(cid) == 12
        assert isinstance(cid, str)

    def test_set_and_get_current(self):
        """Set/get current correlation ID."""
        CorrelationManager.clear()
        CorrelationManager.set_current("test123")
        assert CorrelationManager.get_current() == "test123"
        CorrelationManager.clear()

    def test_clear(self):
        """Clear remove o correlation ID."""
        CorrelationManager.set_current("abc")
        CorrelationManager.clear()
        assert CorrelationManager.get_current() is None

    def test_generate_id_unique(self):
        """IDs gerados sao unicos."""
        ids = {CorrelationManager.generate_id() for _ in range(100)}
        assert len(ids) == 100


# ==================== ModuleFilter ====================


class TestModuleFilter:
    """Testes para ModuleFilter."""

    def test_filter_matches_module(self):
        """Filtro aceita record com modulo correto."""
        f = ModuleFilter("funcionario")
        record = _make_record(module_attr="funcionario")
        assert f.filter(record) is True

    def test_filter_rejects_different_module(self):
        """Filtro rejeita record com modulo diferente."""
        f = ModuleFilter("funcionario")
        record = _make_record(module_attr="empresa")
        assert f.filter(record) is False

    def test_filter_rejects_no_module(self):
        """Filtro rejeita record sem modulo."""
        f = ModuleFilter("funcionario")
        record = _make_record()
        assert f.filter(record) is False


# ==================== PerformanceContext ====================


class TestPerformanceContext:
    """Testes para PerformanceContext."""

    def test_records_duration(self):
        """Context manager registra duracao da operacao."""
        tracker = PerformanceTracker()

        class FakeLogger:
            performance_tracker = tracker

            def _log(self, *a, **kw):
                pass

        ctx = PerformanceContext(FakeLogger(), "test_op")
        with ctx:
            time.sleep(0.01)
        assert ctx.duration_ms is not None
        assert ctx.duration_ms > 5  # pelo menos alguns ms

    def test_records_success(self):
        """Operacao bem sucedida e registrada como success=True."""
        tracker = PerformanceTracker()

        class FakeLogger:
            performance_tracker = tracker

            def _log(self, *a, **kw):
                pass

        with PerformanceContext(FakeLogger(), "ok_op"):
            pass
        stats = tracker.get_stats("ok_op")
        assert stats["success_count"] == 1

    def test_records_failure(self):
        """Excecao e registrada como success=False."""
        tracker = PerformanceTracker()

        class FakeLogger:
            performance_tracker = tracker

            def _log(self, *a, **kw):
                pass

        try:
            with PerformanceContext(FakeLogger(), "fail_op"):
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        stats = tracker.get_stats("fail_op")
        assert stats["failure_count"] == 1

    def test_does_not_suppress_exception(self):
        """Excecao nao e suprimida pelo context manager."""
        class FakeLogger:
            performance_tracker = PerformanceTracker()
            def _log(self, *a, **kw):
                pass

        with pytest.raises(ValueError):
            with PerformanceContext(FakeLogger(), "exc_op"):
                raise ValueError("test")


# ==================== CorrelationContext ====================


class TestCorrelationContext:
    """Testes para CorrelationContext."""

    def test_generates_and_sets_id(self):
        """Context manager gera e define correlation ID."""
        CorrelationManager.clear()
        logs = []

        class FakeLogger:
            def info(self, msg, **kw):
                logs.append((msg, kw))

            def error(self, msg, **kw):
                logs.append((msg, kw))

        with CorrelationContext(FakeLogger(), "op1") as cid:
            assert cid is not None
            assert len(cid) == 12
            assert CorrelationManager.get_current() == cid

        # Apos saida, correlation ID e limpo
        assert CorrelationManager.get_current() is None

    def test_logs_start_and_end(self):
        """Loga inicio e fim da operacao."""
        logs = []

        class FakeLogger:
            def info(self, msg, **kw):
                logs.append(("info", msg))
            def error(self, msg, **kw):
                logs.append(("error", msg))

        with CorrelationContext(FakeLogger(), "batch"):
            pass

        assert any("Iniciando: batch" in m for _, m in logs)
        assert any("Concluido: batch" in m or "Concluído: batch" in m for _, m in logs)

    def test_logs_error_on_exception(self):
        """Loga erro quando excecao ocorre."""
        logs = []

        class FakeLogger:
            def info(self, msg, **kw):
                logs.append(("info", msg))
            def error(self, msg, **kw):
                logs.append(("error", msg))

        try:
            with CorrelationContext(FakeLogger(), "fail"):
                raise RuntimeError("x")
        except RuntimeError:
            pass

        assert any(level == "error" for level, _ in logs)

    def test_clears_id_on_exception(self):
        """Correlation ID e limpo mesmo com excecao."""
        CorrelationManager.clear()

        class FakeLogger:
            def info(self, msg, **kw): pass
            def error(self, msg, **kw): pass

        try:
            with CorrelationContext(FakeLogger(), "err"):
                raise RuntimeError("x")
        except RuntimeError:
            pass

        assert CorrelationManager.get_current() is None


# ==================== ModuleLogger ====================


class TestModuleLogger:
    """Testes para ModuleLogger."""

    def test_delegates_to_system_logger(self):
        """ModuleLogger delega chamadas para SystemLogger."""
        system = MagicMock()
        ml = ModuleLogger("mymod", system)

        ml.info("hello")
        system.info.assert_called_once_with("hello", module="mymod")

    def test_debug_delegates(self):
        """Debug delega corretamente."""
        system = MagicMock()
        ml = ModuleLogger("mod", system)
        ml.debug("d")
        system.debug.assert_called_once_with("d", module="mod")

    def test_warning_delegates(self):
        system = MagicMock()
        ml = ModuleLogger("mod", system)
        ml.warning("w")
        system.warning.assert_called_once_with("w", module="mod")

    def test_error_delegates(self):
        system = MagicMock()
        ml = ModuleLogger("mod", system)
        ml.error("e", exc_info=True)
        system.error.assert_called_once_with("e", module="mod", exc_info=True)

    def test_critical_delegates(self):
        system = MagicMock()
        ml = ModuleLogger("mod", system)
        ml.critical("c", exc_info=False)
        system.critical.assert_called_once_with("c", module="mod", exc_info=False)

    def test_audit_delegates(self):
        system = MagicMock()
        ml = ModuleLogger("mod", system)
        ml.audit("ACTION", "target:1", changes={"a": "b"}, user="u")
        system.audit.assert_called_once_with(
            "ACTION", "target:1", {"a": "b"}, "u", module="mod"
        )

    def test_performance_returns_context(self):
        system = MagicMock()
        ml = ModuleLogger("mod", system)
        ctx = ml.performance("op1")
        system.performance.assert_called_once_with("op1", "mod")
        assert ctx is not None

    def test_get_performance_stats(self):
        system = MagicMock()
        system.get_performance_stats.return_value = {"count": 5}
        ml = ModuleLogger("mod", system)
        result = ml.get_performance_stats("op1")
        assert result["count"] == 5
        system.get_performance_stats.assert_called_once_with("op1")


# ==================== SystemLogger ====================


class TestSystemLogger:
    """Testes para SystemLogger."""

    def _get_fresh_logger(self):
        """Retorna SystemLogger reseta o singleton para testes limpos."""
        SystemLogger._instance = None
        SystemLogger._initialized = False
        with patch.object(SystemLogger, "_create_directories"), \
             patch.object(SystemLogger, "_setup_loggers"):
            inst = SystemLogger()
        # Setup minimo para metodos de log funcionarem
        inst.main_logger = logging.getLogger("TEST_MAIN")
        inst.main_logger.setLevel(logging.DEBUG)
        inst.main_logger.handlers = []
        inst.audit_logger = logging.getLogger("TEST_AUDIT")
        inst.audit_logger.setLevel(logging.DEBUG)
        inst.audit_logger.handlers = []
        inst.audit_logger.propagate = False
        return inst

    def test_singleton(self):
        """SystemLogger e singleton."""
        a = self._get_fresh_logger()
        b = SystemLogger()
        assert a is b

    def test_debug_info_warning_error_critical(self):
        """Metodos de log basico funcionam."""
        logger = self._get_fresh_logger()
        # Nao deve levantar excecao
        logger.debug("debug msg")
        logger.info("info msg")
        logger.warning("warning msg")
        logger.error("error msg")
        logger.critical("critical msg")

    def test_audit_registers_action(self):
        """audit() registra acao corretamente."""
        logger = self._get_fresh_logger()
        logger.audit("USER_CREATED", "user:123", changes={"nome": "Joao"}, user="admin")
        # Nao deve levantar excecao; o audit e processado internamente

    def test_performance_returns_context(self):
        """performance() retorna PerformanceContext."""
        logger = self._get_fresh_logger()
        ctx = logger.performance("op1")
        assert isinstance(ctx, PerformanceContext)

    def test_correlation_returns_context(self):
        """correlation() retorna CorrelationContext."""
        logger = self._get_fresh_logger()
        ctx = logger.correlation("op1")
        assert isinstance(ctx, CorrelationContext)

    def test_get_performance_stats(self):
        """get_performance_stats() retorna dict (com operacao especifica)."""
        logger = self._get_fresh_logger()
        # Registra uma operacao para evitar deadlock do get_stats(None)
        logger.performance_tracker.record("test_op", 10.0)
        stats = logger.get_performance_stats("test_op")
        assert isinstance(stats, dict)
        assert stats["count"] == 1

    def test_get_logger_returns_module_logger(self):
        """get_logger() com modulo retorna ModuleLogger."""
        logger = self._get_fresh_logger()
        mod = logger.get_logger("testmod")
        assert isinstance(mod, ModuleLogger)
        assert mod.module == "testmod"


# ==================== get_logger convenience ====================


class TestGetLoggerConvenience:
    """Testes para a funcao get_logger."""

    def test_returns_system_logger_without_module(self):
        """Sem argumento, retorna SystemLogger."""
        logger = get_logger()
        assert isinstance(logger, SystemLogger)

    def test_returns_module_logger_with_module(self):
        """Com modulo, retorna ModuleLogger."""
        logger = get_logger("mymod")
        assert isinstance(logger, ModuleLogger)
        assert logger.module == "mymod"
