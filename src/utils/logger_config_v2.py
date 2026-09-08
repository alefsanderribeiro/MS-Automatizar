"""
Sistema de Log Completo - MS-Automatizar
=========================================

Sistema de logging que rastreia TODAS as operações do sistema:
- CRUD completo (Create, Read, Update, Delete)
- Performance de queries e processamentos
- Audit trail para operações críticas
- Correlation IDs para rastreamento ponta a ponta
- Métricas de sistema
- Rotação automática de arquivos
- Formato JSON para importação em ferramentas de análise

CONFIGURAÇÃO:
    LOG_LEVEL=DEBUG          # Nível mínimo para console
    LOG_FILE_LEVEL=DEBUG     # Nível mínimo para arquivo
    LOG_AUDIT_ENABLED=true   # Habilitar audit trail
    LOG_PERFORMANCE_ENABLED=true  # Habilitar métricas de performance
    LOG_JSON_FORMAT=false    # Formato JSON para arquivos
    LOG_ROTATION_SIZE=10     # MB por arquivo antes de rotacionar
    LOG_RETENTION_DAYS=30    # Dias para manter arquivos antigos

USO:
    from src.utils.logger_config_v2 import get_logger
    
    logger = get_logger("meu_modulo")
    
    # Log básico
    logger.info("Processando holerite", arquivo="recibo.pdf")
    
    # Audit trail (operações críticas)
    logger.audit("FUNCIONARIO_CRIADO", 
                 funcionario="João Silva",
                 codigo=12345,
                 campos={"nome": "João Silva", "cpf": "123.456.789-00"})
    
    # Performance tracking
    with logger.performance("buscar_funcionario"):
        resultado = collection.find_one({"nome": "João"})
    
    # Correlation ID para rastreamento
    with logger.correlation("processar_holerite_batch") as corr_id:
        logger.info("Iniciando processamento", correlation_id=corr_id)
"""

import logging
import logging.handlers
import os
import json
import time
import uuid
import traceback
import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Union, Callable
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
import re

# Importar protetor de dados sensíveis
try:
    from src.utils.sensitive_data_protector import SensitiveDataProtector, SensitiveDataFilter
    SENSITIVE_PROTECTOR_AVAILABLE = True
except ImportError:
    SENSITIVE_PROTECTOR_AVAILABLE = False


# ==================== CONFIGURAÇÃO ====================

class LogConfig:
    """Configuração centralizada do sistema de log"""
    
    def __init__(self):
        self._load_from_env()
    
    def _load_from_env(self):
        """Carrega configurações do .env"""
        from dotenv import load_dotenv
        load_dotenv()
        
        # Níveis de log
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
        self.LOG_FILE_LEVEL = os.getenv("LOG_FILE_LEVEL", "DEBUG").upper()
        self.LOG_CONSOLE_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
        
        # Funcionalidades
        self.AUDIT_ENABLED = os.getenv("LOG_AUDIT_ENABLED", "true").lower() == "true"
        self.PERFORMANCE_ENABLED = os.getenv("LOG_PERFORMANCE_ENABLED", "true").lower() == "true"
        self.JSON_FORMAT = os.getenv("LOG_JSON_FORMAT", "false").lower() == "true"
        self.CORRELATION_ENABLED = os.getenv("LOG_CORRELATION_ENABLED", "true").lower() == "true"
        
        # Rotação e retenção
        self.ROTATION_SIZE_MB = int(os.getenv("LOG_ROTATION_SIZE", "10"))
        self.RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "30"))
        self.MAX_BACKUP_COUNT = int(os.getenv("LOG_MAX_BACKUPS", "10"))
        
        # Diretórios
        self.LOG_DIR = os.getenv("LOG_DIR", "logs")
        self.AUDIT_LOG_DIR = os.getenv("LOG_AUDIT_DIR", "logs/audit")
        self.PERFORMANCE_LOG_DIR = os.getenv("LOG_PERF_DIR", "logs/performance")
        self.MODULE_LOG_DIR = os.getenv("LOG_MODULE_DIR", "logs/modules")
        
        # Módulos habilitados para log separado
        self.MODULE_LOGS = os.getenv("LOG_MODULES", 
            "mongodb,holerite,folha_ponto,whatsapp,empresa,funcionario").split(",")


# ==================== FORMATTERS ====================

class StructuredFormatter(logging.Formatter):
    """Formatador estruturado para logs legíveis com proteção de dados sensíveis"""
    
    def __init__(self):
        super().__init__()
        # Inicializar protetor de dados sensíveis
        if SENSITIVE_PROTECTOR_AVAILABLE:
            self.sensitive_protector = SensitiveDataProtector()
        else:
            self.sensitive_protector = None
    
    def format(self, record):
        # Timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
        
        # Level com cor (para console)
        level = record.levelname.ljust(8)
        
        # Módulo
        module = getattr(record, 'module', record.name.split('.')[-1])
        
        # Correlation ID
        correlation_id = getattr(record, 'correlation_id', None)
        corr_str = f" [{correlation_id[:8]}]" if correlation_id else ""
        
        # Audit flag
        is_audit = getattr(record, 'is_audit', False)
        audit_str = " [AUDIT]" if is_audit else ""
        
        # Performance
        duration_ms = getattr(record, 'duration_ms', None)
        perf_str = f" ({duration_ms:.1f}ms)" if duration_ms is not None else ""
        
        # Mensagem (com proteção de dados sensíveis)
        msg = record.getMessage()
        if self.sensitive_protector:
            msg = self.sensitive_protector.mask_sensitive_data(msg)
        
        # Extras estruturados (com proteção)
        extras = getattr(record, 'extras', {})
        extras_str = ""
        if extras:
            if self.sensitive_protector:
                extras = {k: self.sensitive_protector.mask_sensitive_data(str(v)) for k, v in extras.items()}
            extras_parts = [f"{k}={v}" for k, v in extras.items()]
            extras_str = " | " + " ".join(extras_parts)
        
        # Formato final
        return f"{timestamp} - {level} - [{module}]{corr_str}{audit_str}{perf_str} {msg}{extras_str}"


class JSONFormatter(logging.Formatter):
    """Formatador JSON para importação em ferramentas de análise"""
    
    def format(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "module": getattr(record, 'module', record.name.split('.')[-1]),
            "message": record.getMessage(),
            "logger": record.name,
        }
        
        # Correlation ID
        correlation_id = getattr(record, 'correlation_id', None)
        if correlation_id:
            log_entry["correlation_id"] = correlation_id
        
        # Audit
        if getattr(record, 'is_audit', False):
            log_entry["is_audit"] = True
            log_entry["audit_action"] = getattr(record, 'audit_action', None)
            log_entry["audit_target"] = getattr(record, 'audit_target', None)
        
        # Performance
        duration_ms = getattr(record, 'duration_ms', None)
        if duration_ms is not None:
            log_entry["duration_ms"] = round(duration_ms, 2)
        
        # Extras
        extras = getattr(record, 'extras', {})
        if extras:
            log_entry["extras"] = extras
        
        # Exception
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Source location
        log_entry["source"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName
        }
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)


class AuditFormatter(logging.Formatter):
    """Formatador especializado para audit trail com proteção de dados sensíveis"""
    
    def __init__(self):
        super().__init__()
        # Inicializar protetor de dados sensíveis
        if SENSITIVE_PROTECTOR_AVAILABLE:
            self.sensitive_protector = SensitiveDataProtector()
        else:
            self.sensitive_protector = None
    
    def format(self, record):
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
        
        action = getattr(record, 'audit_action', 'UNKNOWN')
        target = getattr(record, 'audit_target', 'UNKNOWN')
        user = getattr(record, 'audit_user', 'system')
        changes = getattr(record, 'audit_changes', {})
        
        # Mascarar dados sensíveis nas mudanças
        if self.sensitive_protector and changes:
            changes = {k: self.sensitive_protector.mask_sensitive_data(str(v)) for k, v in changes.items()}
        
        changes_str = json.dumps(changes, ensure_ascii=False, default=str) if changes else "{}"
        
        return f"{timestamp} | {action:30s} | {target:30s} | user={user} | {changes_str}"


# ==================== PERFORMANCE TRACKER ====================

class PerformanceTracker:
    """Rastreador de performance para operações"""
    
    def __init__(self):
        self._metrics: Dict[str, list] = {}
        self._lock = threading.Lock()
    
    def record(self, operation: str, duration_ms: float, success: bool = True, 
               details: Optional[Dict] = None):
        """Registra uma métrica de performance"""
        with self._lock:
            if operation not in self._metrics:
                self._metrics[operation] = []
            
            self._metrics[operation].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_ms": round(duration_ms, 2),
                "success": success,
                "details": details or {}
            })
    
    def get_stats(self, operation: Optional[str] = None) -> Dict:
        """Retorna estatísticas de performance"""
        with self._lock:
            if operation:
                metrics = self._metrics.get(operation, [])
                if not metrics:
                    return {"operation": operation, "count": 0}
                
                durations = [m["duration_ms"] for m in metrics]
                successes = [m for m in metrics if m["success"]]
                
                return {
                    "operation": operation,
                    "count": len(metrics),
                    "success_count": len(successes),
                    "failure_count": len(metrics) - len(successes),
                    "avg_ms": round(sum(durations) / len(durations), 2),
                    "min_ms": round(min(durations), 2),
                    "max_ms": round(max(durations), 2),
                    "p95_ms": round(sorted(durations)[int(len(durations) * 0.95)] if len(durations) > 1 else durations[0], 2),
                    "success_rate": round(len(successes) / len(metrics) * 100, 2)
                }
            else:
                return {op: self.get_stats(op) for op in self._metrics.keys()}


# ==================== CORRELATION MANAGER ====================

class CorrelationManager:
    """Gerenciador de correlation IDs para rastreamento"""
    
    _local = threading.local()
    
    @classmethod
    def generate_id(cls) -> str:
        """Gera um novo correlation ID"""
        return str(uuid.uuid4())[:12]
    
    @classmethod
    def get_current(cls) -> Optional[str]:
        """Retorna o correlation ID atual"""
        return getattr(cls._local, 'current_id', None)
    
    @classmethod
    def set_current(cls, correlation_id: str):
        """Define o correlation ID atual"""
        cls._local.current_id = correlation_id
    
    @classmethod
    def clear(cls):
        """Limpa o correlation ID atual"""
        cls._local.current_id = None


# ==================== LOGGER PRINCIPAL ====================

class SystemLogger:
    """
    Logger principal do sistema com rastreamento completo.
    
    Funcionalidades:
    - Log básico (debug, info, warning, error, critical)
    - Audit trail para operações CRUD
    - Performance tracking
    - Correlation IDs
    - Múltiplos destinos (arquivo, console, audit, performance)
    - Rotação automática
    - Formato JSON opcional
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton thread-safe"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.config = LogConfig()
        self.performance_tracker = PerformanceTracker()
        self.correlation_manager = CorrelationManager()
        
        # Criar diretórios
        self._create_directories()
        
        # Configurar loggers
        self._setup_loggers()
        
        self._initialized = True
    
    def _create_directories(self):
        """Cria todos os diretórios de log"""
        dirs = [
            self.config.LOG_DIR,
            self.config.AUDIT_LOG_DIR,
            self.config.PERFORMANCE_LOG_DIR,
            self.config.MODULE_LOG_DIR,
        ]
        for dir_path in dirs:
            os.makedirs(dir_path, exist_ok=True)
    
    def _setup_loggers(self):
        """Configura todos os loggers e handlers"""
        
        # Logger principal
        self.main_logger = logging.getLogger('MS_AUTOMATIZAR')
        self.main_logger.setLevel(logging.DEBUG)
        self.main_logger.handlers = []  # Limpar handlers existentes
        
        # Logger de audit
        self.audit_logger = logging.getLogger('MS_AUTOMATIZAR.AUDIT')
        self.audit_logger.setLevel(logging.DEBUG)
        self.audit_logger.handlers = []
        self.audit_logger.propagate = False
        
        # Logger de performance
        self.perf_logger = logging.getLogger('MS_AUTOMATIZAR.PERFORMANCE')
        self.perf_logger.setLevel(logging.DEBUG)
        self.perf_logger.handlers = []
        self.perf_logger.propagate = False
        
        # Configurar handlers do logger principal
        self._setup_main_handlers()
        
        # Configurar handlers de audit
        self._setup_audit_handlers()
        
        # Configurar handlers de performance
        self._setup_performance_handlers()
    
    def _setup_main_handlers(self):
        """Configura handlers do logger principal com proteção de dados sensíveis"""
        
        today = datetime.now().strftime("%d-%m-%Y")
        
        # Adicionar filtro de dados sensíveis se disponível
        sensitive_filter = SensitiveDataFilter() if SENSITIVE_PROTECTOR_AVAILABLE else None
        
        # 1. Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, self.config.LOG_CONSOLE_LEVEL))
        console_handler.setFormatter(StructuredFormatter())
        console_handler.set_name('console')
        if sensitive_filter:
            console_handler.addFilter(sensitive_filter)
        self.main_logger.addHandler(console_handler)
        
        # 2. Arquivo principal (rotação por tamanho)
        main_log_path = os.path.join(self.config.LOG_DIR, f'app_{today}.log')
        file_handler = logging.handlers.RotatingFileHandler(
            main_log_path,
            maxBytes=self.config.ROTATION_SIZE_MB * 1024 * 1024,
            backupCount=self.config.MAX_BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, self.config.LOG_FILE_LEVEL))
        file_handler.setFormatter(StructuredFormatter() if not self.config.JSON_FORMAT else JSONFormatter())
        file_handler.set_name('file_main')
        if sensitive_filter:
            file_handler.addFilter(sensitive_filter)
        self.main_logger.addHandler(file_handler)
        
        # 3. Arquivo de erros
        error_log_path = os.path.join(self.config.LOG_DIR, f'errors_{today}.log')
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_path,
            maxBytes=self.config.ROTATION_SIZE_MB * 1024 * 1024,
            backupCount=self.config.MAX_BACKUP_COUNT,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(StructuredFormatter() if not self.config.JSON_FORMAT else JSONFormatter())
        error_handler.set_name('file_errors')
        if sensitive_filter:
            error_handler.addFilter(sensitive_filter)
        self.main_logger.addHandler(error_handler)
        
        # 4. Handlers por módulo
        for module_name in self.config.MODULE_LOGS:
            module_name = module_name.strip()
            if module_name:
                module_log_path = os.path.join(self.config.MODULE_LOG_DIR, f'{module_name}_{today}.log')
                module_handler = logging.handlers.RotatingFileHandler(
                    module_log_path,
                    maxBytes=self.config.ROTATION_SIZE_MB * 1024 * 1024,
                    backupCount=self.config.MAX_BACKUP_COUNT,
                    encoding='utf-8'
                )
                module_handler.setLevel(logging.DEBUG)
                module_handler.setFormatter(StructuredFormatter())
                module_handler.set_name(f'module_{module_name}')
                # Filtros
                module_handler.addFilter(ModuleFilter(module_name))
                if sensitive_filter:
                    module_handler.addFilter(sensitive_filter)
                self.main_logger.addHandler(module_handler)
    
    def _setup_audit_handlers(self):
        """Configura handlers de audit trail"""
        if not self.config.AUDIT_ENABLED:
            return
        
        today = datetime.now().strftime("%d-%m-%Y")
        
        # Arquivo de audit
        audit_path = os.path.join(self.config.AUDIT_LOG_DIR, f'audit_{today}.log')
        audit_handler = logging.handlers.RotatingFileHandler(
            audit_path,
            maxBytes=self.config.ROTATION_SIZE_MB * 1024 * 1024,
            backupCount=self.config.MAX_BACKUP_COUNT * 2,  # Manter mais backups de audit
            encoding='utf-8'
        )
        audit_handler.setLevel(logging.DEBUG)
        audit_handler.setFormatter(AuditFormatter())
        audit_handler.set_name('audit_file')
        self.audit_logger.addHandler(audit_handler)
        
        # Console de audit (apenas warnings e erros)
        audit_console = logging.StreamHandler()
        audit_console.setLevel(logging.WARNING)
        audit_console.setFormatter(AuditFormatter())
        audit_console.set_name('audit_console')
        self.audit_logger.addHandler(audit_console)
    
    def _setup_performance_handlers(self):
        """Configura handlers de performance"""
        if not self.config.PERFORMANCE_ENABLED:
            return
        
        today = datetime.now().strftime("%d-%m-%Y")
        
        # Arquivo de performance
        perf_path = os.path.join(self.config.PERFORMANCE_LOG_DIR, f'performance_{today}.log')
        perf_handler = logging.handlers.RotatingFileHandler(
            perf_path,
            maxBytes=self.config.ROTATION_SIZE_MB * 1024 * 1024,
            backupCount=self.config.MAX_BACKUP_COUNT,
            encoding='utf-8'
        )
        perf_handler.setLevel(logging.DEBUG)
        perf_handler.setFormatter(JSONFormatter())
        perf_handler.set_name('performance_file')
        self.perf_logger.addHandler(perf_handler)
    
    # ==================== MÉTODOS PÚBLICOS ====================
    
    def get_logger(self, module: str) -> 'ModuleLogger':
        """Retorna um logger para um módulo específico"""
        return ModuleLogger(module, self)
    
    def debug(self, message: str, module: str = None, **kwargs):
        """Log de debug"""
        self._log(logging.DEBUG, message, module, **kwargs)
    
    def info(self, message: str, module: str = None, **kwargs):
        """Log de info"""
        self._log(logging.INFO, message, module, **kwargs)
    
    def warning(self, message: str, module: str = None, **kwargs):
        """Log de warning"""
        self._log(logging.WARNING, message, module, **kwargs)
    
    def error(self, message: str, module: str = None, exc_info: bool = False, **kwargs):
        """Log de error"""
        self._log(logging.ERROR, message, module, exc_info=exc_info, **kwargs)
    
    def critical(self, message: str, module: str = None, exc_info: bool = False, **kwargs):
        """Log de critical"""
        self._log(logging.CRITICAL, message, module, exc_info=exc_info, **kwargs)
    
    def audit(self, action: str, target: str, changes: Dict = None, 
              user: str = "system", module: str = None, **kwargs):
        """
        Registra operação de audit trail.
        
        Args:
            action: Ação realizada (ex: FUNCIONARIO_CRIADO, EMPRESA_ATUALIZADA)
            target: Alvo da ação (ex: "funcionario:12345", "empresa:6925...")
            changes: Mudanças realizadas (dict com campos alterados)
            user: Usuário que realizou a ação
            module: Módulo de origem
        """
        if not self.config.AUDIT_ENABLED:
            return
        
        extra = {
            'is_audit': True,
            'audit_action': action,
            'audit_target': target,
            'audit_user': user,
            'audit_changes': changes or {},
            'extras': kwargs
        }
        
        # Log no audit logger
        audit_record = self.audit_logger.makeRecord(
            name='MS_AUTOMATIZAR.AUDIT',
            level=logging.INFO,
            fn='', lno=0, msg=f"{action} -> {target}",
            args=(), exc_info=None
        )
        for key, value in extra.items():
            setattr(audit_record, key, value)
        self.audit_logger.handle(audit_record)
        
        # También log no logger principal
        self._log(logging.INFO, f"[AUDIT] {action} -> {target}", module, 
                  is_audit=True, audit_action=action, audit_target=target, 
                  audit_changes=changes, **kwargs)
    
    def performance(self, operation: str, module: str = None):
        """
        Context manager para rastrear performance de operações.
        
        Usage:
            with logger.performance("buscar_funcionario"):
                resultado = collection.find_one({"nome": "João"})
        """
        return PerformanceContext(self, operation, module)
    
    def correlation(self, operation: str):
        """
        Context manager para correlation ID.
        
        Usage:
            with logger.correlation("processar_batch") as corr_id:
                logger.info("Iniciando", correlation_id=corr_id)
        """
        return CorrelationContext(self, operation)
    
    def get_performance_stats(self, operation: Optional[str] = None) -> Dict:
        """Retorna estatísticas de performance"""
        return self.performance_tracker.get_stats(operation)
    
    def cleanup_old_logs(self):
        """Remove logs antigos baseado na retenção configurada"""
        cutoff_date = datetime.now() - timedelta(days=self.config.RETENTION_DAYS)
        
        for log_dir in [self.config.LOG_DIR, self.config.AUDIT_LOG_DIR, 
                       self.config.PERFORMANCE_LOG_DIR, self.config.MODULE_LOG_DIR]:
            if not os.path.exists(log_dir):
                continue
            
            for file_path in Path(log_dir).glob("*.log*"):
                if file_path.is_file():
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_date:
                        file_path.unlink()
                        self.info(f"Log antigo removido: {file_path.name}", module="cleanup")
    
    # ==================== MÉTODOS INTERNOS ====================
    
    def _log(self, level: int, message: str, module: str = None, 
             exc_info: bool = False, **kwargs):
        """Método interno para registrar logs com proteção de dados sensíveis"""
        
        # Determinar logger
        logger = self.main_logger
        
        # Adicionar correlation ID se disponível
        correlation_id = kwargs.pop('correlation_id', None) or self.correlation_manager.get_current()
        
        # Mascarar dados sensíveis na mensagem
        if SENSITIVE_PROTECTOR_AVAILABLE:
            protector = SensitiveDataProtector()
            message = protector.mask_sensitive_data(message)
        
        # Criar record
        record = logger.makeRecord(
            name=logger.name,
            level=level,
            fn='', lno=0, msg=message,
            args=(), exc_info=exc_info if exc_info else None
        )
        
        # Adicionar extras
        if correlation_id:
            record.correlation_id = correlation_id
        if module:
            record.module = module
        
        # Adicionar extras extras (com proteção)
        extras = {k: v for k, v in kwargs.items() if k not in ['is_audit', 'audit_action', 'audit_target', 'audit_changes']}
        if extras and SENSITIVE_PROTECTOR_AVAILABLE:
            protector = SensitiveDataProtector()
            extras = {k: protector.mask_sensitive_data(str(v)) for k, v in extras.items()}
        if extras:
            record.extras = extras
        
        # Handle
        logger.handle(record)


class ModuleFilter(logging.Filter):
    """Filtro para logs de módulo específico"""
    
    def __init__(self, module_name: str):
        super().__init__()
        self.module_name = module_name
    
    def filter(self, record):
        module = getattr(record, 'module', None)
        return module == self.module_name


class PerformanceContext:
    """Context manager para performance tracking"""
    
    def __init__(self, logger: SystemLogger, operation: str, module: str = None):
        self.logger = logger
        self.operation = operation
        self.module = module
        self.start_time = None
        self.duration_ms = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            self.duration_ms = (time.perf_counter() - self.start_time) * 1000
            success = exc_type is None
            
            # Registrar métrica
            self.logger.performance_tracker.record(
                self.operation, self.duration_ms, success,
                {"module": self.module, "exception": str(exc_val) if exc_val else None}
            )
            
            # Log
            level = logging.INFO if success else logging.WARNING
            self.logger._log(
                level,
                f"Performance: {self.operation}",
                self.module,
                duration_ms=self.duration_ms,
                success=success
            )
        
        return False  # Não suprimir exceções


class CorrelationContext:
    """Context manager para correlation IDs"""
    
    def __init__(self, logger: SystemLogger, operation: str):
        self.logger = logger
        self.operation = operation
        self.correlation_id = None
    
    def __enter__(self):
        self.previous_id = CorrelationManager.get_current()
        self.correlation_id = CorrelationManager.generate_id()
        CorrelationManager.set_current(self.correlation_id)
        
        self.logger.info(
            f"Iniciando: {self.operation}",
            correlation_id=self.correlation_id
        )
        
        return self.correlation_id
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.error(
                f"Erro em: {self.operation}",
                correlation_id=self.correlation_id,
                exc_info=True
            )
        else:
            self.logger.info(
                f"Concluído: {self.operation}",
                correlation_id=self.correlation_id
            )
        
        CorrelationManager.set_current(self.previous_id)
        return False


class ModuleLogger:
    """Logger wrapper para módulo específico"""
    
    def __init__(self, module_name: str, system_logger: SystemLogger):
        self.module = module_name
        self.system_logger = system_logger
    
    def debug(self, message: str, **kwargs):
        self.system_logger.debug(message, module=self.module, **kwargs)
    
    def info(self, message: str, **kwargs):
        self.system_logger.info(message, module=self.module, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self.system_logger.warning(message, module=self.module, **kwargs)
    
    def error(self, message: str, exc_info: bool = False, **kwargs):
        self.system_logger.error(message, module=self.module, exc_info=exc_info, **kwargs)
    
    def critical(self, message: str, exc_info: bool = False, **kwargs):
        self.system_logger.critical(message, module=self.module, exc_info=exc_info, **kwargs)
    
    def audit(self, action: str, target: str, changes: Dict = None, user: str = "system", **kwargs):
        self.system_logger.audit(action, target, changes, user, module=self.module, **kwargs)
    
    def performance(self, operation: str):
        return self.system_logger.performance(operation, self.module)
    
    def correlation(self, operation: str):
        return self.system_logger.correlation(operation)
    
    def get_performance_stats(self, operation: Optional[str] = None) -> Dict:
        """Retorna estatísticas de performance"""
        return self.system_logger.get_performance_stats(operation)


# ==================== FUNÇÕES DE CONVENIÊNCIA ====================

def get_logger(module: str = None) -> Union[SystemLogger, ModuleLogger]:
    """
    Função principal para obter logger.
    
    Usage:
        # Logger global
        logger = get_logger()
        logger.info("Mensagem global")
        
        # Logger para módulo específico
        logger = get_logger("funcionario")
        logger.info("Funcionário criado", codigo=12345)
    """
    system_logger = SystemLogger()
    
    if module:
        return ModuleLogger(module, system_logger)
    return system_logger


def audit_log(action: str, target: str, changes: Dict = None, user: str = "system"):
    """
    Função de conveniência para audit log.
    
    Usage:
        audit_log("FUNCIONARIO_CRIADO", "funcionario:12345", 
                  changes={"nome": "João Silva", "cpf": "123.456.789-00"})
    """
    SystemLogger().audit(action, target, changes, user)


def performance_log(operation: str):
    """
    Função de conveniência para performance tracking.
    
    Usage:
        with performance_log("buscar_funcionario"):
            resultado = collection.find_one({"nome": "João"})
    """
    return PerformanceContext(SystemLogger(), operation)


# ==================== DECORADORES ====================

def log_execution(module: str = None, audit: bool = False, 
                  audit_action: str = None, performance: bool = True):
    """
    Decorador para logging automático de funções.
    
    Usage:
        @log_execution(module="funcionario", audit=True, audit_action="CRIAR_FUNCIONARIO")
        def criar_funcionario(dados):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(module or func.__module__.split('.')[-1])
            func_name = func.__qualname__
            
            # Performance tracking
            start_time = time.perf_counter() if performance else None
            
            try:
                # Log de entrada (debug)
                logger.debug(f"Executando: {func_name}", 
                           args=str(args)[:200], kwargs=str(kwargs)[:200])
                
                # Executar função
                result = func(*args, **kwargs)
                
                # Performance
                if performance and start_time:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    logger.debug(f"Concluído: {func_name}", duration_ms=round(duration_ms, 2))
                
                # Audit (se habilitado)
                if audit and audit_action:
                    target = f"{func_name}:{str(result)[:50] if result else 'void'}"
                    changes = {"args": str(args)[:200], "result": str(result)[:200]}
                    logger.audit(audit_action, target, changes)
                
                return result
                
            except Exception as e:
                # Log de erro
                logger.error(f"Erro em: {func_name}", exc_info=True, 
                           error=str(e), error_type=type(e).__name__)
                raise
        
        return wrapper
    return decorator


# ==================== INSTÂNCIA GLOBAL ====================

# Logger global para uso direto
logger = get_logger()
