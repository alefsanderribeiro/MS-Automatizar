#!/usr/bin/env python3
"""
Sistema de Proteção de Dados Sensíveis nos Logs

Este módulo implementa:
1. Mascaramento automático de dados sensíveis
2. Limpeza de logs existentes
3. Validação de logs antes de gravar
4. Configuração de campos protegidos
"""

import re
import os
from typing import Dict, List, Optional, Any
from datetime import datetime


class SensitiveDataProtector:
    """
    Protetor de dados sensíveis para logs.
    
    Funcionalidades:
    - Mascaramento de senhas, tokens, CPFs, CNPJs
    - Validação de mensagens antes de gravar
    - Limpeza de logs existentes
    - Configuração flexível de campos protegidos
    """
    
    # Padrões de dados sensíveis
    SENSITIVE_PATTERNS = {
        # Senhas e credenciais
        'password': re.compile(r'(password|senha|pwd|pass)[\s:=]+[^\s,;]+', re.IGNORECASE),
        'token': re.compile(r'(token|api_key|apikey|secret|credential)[\s:=]+[^\s,;]+', re.IGNORECASE),
        'bearer': re.compile(r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', re.IGNORECASE),
        
        # URI de conexão com credenciais
        'connection_uri': re.compile(r'(mongodb|mysql|postgres|redis)://[^\s]+:[^\s]+@[^\s]+', re.IGNORECASE),
        
        # Documentos brasileiros
        'cpf': re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b'),
        'cnpj': re.compile(r'\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b'),
        'pis': re.compile(r'\b\d{3}\.?\d{5}\.?\d{2}-?\d{1}\b'),
        'rg': re.compile(r'\b\d{1,2}\.?\d{3}\.?\d{3}-?\d{1}\b'),
        
        # Cartões
        'credit_card': re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),
        
        # E-mails (opcional)
        'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        
        # IPs internos
        'internal_ip': re.compile(r'\b(192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b'),
        
        # Chaves de API
        'api_key': re.compile(r'(AIza[A-Za-z0-9_-]{35}|ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{48})'),
    }
    
    # Mapeamento de substituição
    MASK_MAP = {
        'password': '***SENHA***',
        'token': '***TOKEN***',
        'bearer': 'Bearer ***',
        'connection_uri': lambda m: re.sub(r'://([^:]+):[^@]+@', r'://\1:***@', m.group()),
        'cpf': '***.***.***-**',
        'cnpj': '**.***.***/****-**',
        'pis': '***.*****.**-*',
        'rg': '**.***.***-*',
        'credit_card': '****-****-****-****',
        'email': lambda m: m.group()[:2] + '***@' + m.group().split('@')[1],
        'internal_ip': lambda m: m.group().split('.')[0] + '.***.***.***',
        'api_key': lambda m: m.group()[:6] + '***',
    }
    
    def __init__(self, custom_patterns: Dict[str, re.Pattern] = None):
        """
        Inicializa o protetor de dados sensíveis.
        
        Args:
            custom_patterns: Padrões personalizados adicionais
        """
        self.patterns = self.SENSITIVE_PATTERNS.copy()
        if custom_patterns:
            self.patterns.update(custom_patterns)
        
        # Estatísticas
        self.stats = {
            'total_messages': 0,
            'masked_messages': 0,
            'blocked_messages': 0
        }
    
    def mask_sensitive_data(self, message: str) -> str:
        """
        Mascara dados sensíveis em uma mensagem.
        
        Args:
            message: Mensagem original
            
        Returns:
            Mensagem com dados sensíveis mascarados
        """
        if not message:
            return message
        
        self.stats['total_messages'] += 1
        masked = message
        was_masked = False
        
        for pattern_name, pattern in self.patterns.items():
            matches = pattern.finditer(masked)
            for match in matches:
                # Obter substituição
                replacement = self.MASK_MAP.get(pattern_name, '***')
                
                # Aplicar substituição
                if callable(replacement):
                    new_text = replacement(match)
                else:
                    new_text = replacement
                
                # Substituir na mensagem
                masked = masked[:match.start()] + new_text + masked[match.end():]
                was_masked = True
        
        if was_masked:
            self.stats['masked_messages'] += 1
        
        return masked
    
    def validate_message(self, message: str) -> tuple[bool, str]:
        """
        Valida se uma mensagem contém dados sensíveis críticos.
        
        Args:
            message: Mensagem para validar
            
        Returns:
            Tuple (é_seguro, mensagem_processada)
        """
        if not message:
            return True, message
        
        # Verificar se tem dados muito sensíveis
        critical_patterns = [
            self.SENSITIVE_PATTERNS['connection_uri'],
            self.SENSITIVE_PATTERNS['password'],
            self.SENSITIVE_PATTERNS['token'],
        ]
        
        for pattern in critical_patterns:
            if pattern.search(message):
                # Mascarar em vez de bloquear
                masked = self.mask_sensitive_data(message)
                return True, masked
        
        return True, message
    
    def clean_log_file(self, file_path: str, output_path: str = None) -> Dict[str, int]:
        """
        Limpa dados sensíveis de um arquivo de log.
        
        Args:
            file_path: Caminho do arquivo de log
            output_path: Caminho do arquivo de saída (opcional)
            
        Returns:
            Estatísticas da limpeza
        """
        stats = {
            'total_lines': 0,
            'masked_lines': 0,
            'errors': 0
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            stats['total_lines'] = len(lines)
            
            # Processar cada linha
            cleaned_lines = []
            for line in lines:
                cleaned = self.mask_sensitive_data(line)
                if cleaned != line:
                    stats['masked_lines'] += 1
                cleaned_lines.append(cleaned)
            
            # Salvar arquivo limpo
            if output_path is None:
                output_path = file_path + '.cleaned'
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.writelines(cleaned_lines)
            
            print(f"✅ Arquivo limpo: {output_path}")
            print(f"   Linhas processadas: {stats['total_lines']}")
            print(f"   Linhas mascaradas: {stats['masked_lines']}")
            
        except Exception as e:
            print(f"❌ Erro ao limpar arquivo: {e}")
            stats['errors'] += 1
        
        return stats
    
    def get_stats(self) -> Dict[str, int]:
        """Retorna estatísticas de uso"""
        return self.stats.copy()


# Instância global
sensitive_protector = SensitiveDataProtector()


def mask_log_message(message: str) -> str:
    """Função de conveniência para mascarar mensagens"""
    return sensitive_protector.mask_sensitive_data(message)


def validate_log_message(message: str) -> tuple[bool, str]:
    """Função de conveniência para validar mensagens"""
    return sensitive_protector.validate_message(message)


# ==================== FILTRO DE LOGGING ====================

class SensitiveDataFilter:
    """Filtro de logging que mascara dados sensíveis"""
    
    def __init__(self):
        self.protector = SensitiveDataProtector()
    
    def filter(self, record) -> bool:
        """Filtra e mascara dados sensíveis no record"""
        if isinstance(record.msg, str):
            record.msg = self.protector.mask_sensitive_data(record.msg)
        
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self.protector.mask_sensitive_data(str(v)) 
                    if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self.protector.mask_sensitive_data(str(arg))
                    if isinstance(arg, str) else arg
                    for arg in record.args
                )
        
        return True
