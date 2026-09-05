#!/usr/bin/env python3
"""
Script para Limpar Logs Existentes e Remover Dados Sensíveis

Este script:
1. Remove dados sensíveis de logs existentes
2. Cria backups dos arquivos originais
3. Gera relatório de limpeza
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime


# ==================== PADRÕES DE DADOS SENSÍVEIS ====================

SENSITIVE_PATTERNS = {
    # Senhas em URIs
    'uri_password': re.compile(r'(mongodb|mysql|postgres|redis)://([^:]+):([^@]+)@', re.IGNORECASE),
    
    # Senhas em mensagens
    'password_message': re.compile(r'(password|senha|pwd|pass)[\s:=]+[^\s,;]+', re.IGNORECASE),
    
    # Tokens
    'token': re.compile(r'(token|api_key|apikey|secret|credential)[\s:=]+[^\s,;]+', re.IGNORECASE),
    
    # Documentos brasileiros
    'cpf': re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b'),
    'cnpj': re.compile(r'\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b'),
    
    # Chaves de API
    'api_key': re.compile(r'(AIza[A-Za-z0-9_-]{35}|ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{48})'),
}


def mask_line(line: str) -> str:
    """Mascara dados sensíveis em uma linha"""
    masked = line
    
    # Mascarar senhas em URIs
    masked = re.sub(
        r'(mongodb|mysql|postgres|redis)://([^:]+):([^@]+)@',
        r'\1://\2:***@',
        masked
    )
    
    # Mascarar senhas em mensagens
    masked = re.sub(
        r'(password|senha|pwd|pass)[\s:=]+[^\s,;]+',
        r'\1=***',
        masked,
        flags=re.IGNORECASE
    )
    
    # Mascarar tokens
    masked = re.sub(
        r'(token|api_key|apikey|secret|credential)[\s:=]+[^\s,;]+',
        r'\1=***',
        masked,
        flags=re.IGNORECASE
    )
    
    # Mascarar CPFs
    masked = re.sub(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b', '***.***.***-**', masked)
    
    # Mascarar CNPJs
    masked = re.sub(r'\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b', '**.***.***/****-**', masked)
    
    # Mascarar chaves de API
    masked = re.sub(r'(AIza[A-Za-z0-9_-]{35})', 'AIza***', masked)
    masked = re.sub(r'(ghp_[A-Za-z0-9]{36})', 'ghp_***', masked)
    masked = re.sub(r'(sk-[A-Za-z0-9]{48})', 'sk-***', masked)
    
    return masked


def clean_log_file(file_path: Path, backup: bool = True) -> dict:
    """Limpa um arquivo de log"""
    stats = {
        'total_lines': 0,
        'masked_lines': 0,
        'backup_path': None
    }
    
    try:
        # Ler arquivo
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        stats['total_lines'] = len(lines)
        
        # Criar backup se solicitado
        if backup:
            backup_path = file_path.with_suffix('.log.backup')
            shutil.copy2(file_path, backup_path)
            stats['backup_path'] = str(backup_path)
        
        # Processar cada linha
        cleaned_lines = []
        for line in lines:
            cleaned = mask_line(line)
            if cleaned != line:
                stats['masked_lines'] += 1
            cleaned_lines.append(cleaned)
        
        # Salvar arquivo limpo
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(cleaned_lines)
        
        return stats
        
    except Exception as e:
        print(f"❌ Erro ao processar {file_path}: {e}")
        return stats


def main():
    """Função principal"""
    
    print("=" * 70)
    print("🧹 LIMPEZA DE LOGS - REMOÇÃO DE DADOS SENSÍVEIS")
    print("=" * 70)
    print(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 70)
    
    # Diretórios de log
    log_dirs = [
        'logs',
        'logs/audit',
        'logs/performance',
        'logs/modules'
    ]
    
    # Estatísticas totais
    total_stats = {
        'files_processed': 0,
        'total_lines': 0,
        'masked_lines': 0,
        'backups_created': 0
    }
    
    # Processar cada diretório
    for log_dir in log_dirs:
        if not os.path.exists(log_dir):
            print(f"\n⚠️  Diretório não encontrado: {log_dir}")
            continue
        
        print(f"\n📁 Processando: {log_dir}")
        
        # Encontrar arquivos de log
        log_files = list(Path(log_dir).glob("*.log"))
        
        if not log_files:
            print(f"   Nenhum arquivo de log encontrado")
            continue
        
        for log_file in sorted(log_files):
            print(f"   📄 {log_file.name}...", end=" ")
            
            stats = clean_log_file(log_file, backup=True)
            
            total_stats['files_processed'] += 1
            total_stats['total_lines'] += stats['total_lines']
            total_stats['masked_lines'] += stats['masked_lines']
            
            if stats['masked_lines'] > 0:
                print(f"✅ {stats['masked_lines']} linhas mascaradas")
                total_stats['backups_created'] += 1
            else:
                print(f"✅ Limpo")
    
    # Relatório final
    print("\n" + "=" * 70)
    print("📊 RELATÓRIO FINAL DE LIMPEZA")
    print("=" * 70)
    print(f"  Arquivos processados: {total_stats['files_processed']}")
    print(f"  Total de linhas: {total_stats['total_lines']}")
    print(f"  Linhas mascaradas: {total_stats['masked_lines']}")
    print(f"  Backups criados: {total_stats['backups_created']}")
    print("=" * 70)
    
    # Salvar relatório
    report_path = Path('logs') / f'limpeza_{datetime.now().strftime("%d-%m-%Y_%H-%M")}.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"Relatório de Limpeza - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write(f"{'='*50}\n\n")
        f.write(f"Arquivos processados: {total_stats['files_processed']}\n")
        f.write(f"Total de linhas: {total_stats['total_lines']}\n")
        f.write(f"Linhas mascaradas: {total_stats['masked_lines']}\n")
        f.write(f"Backups criados: {total_stats['backups_created']}\n")
    
    print(f"\n📄 Relatório salvo em: {report_path}")


if __name__ == "__main__":
    main()
