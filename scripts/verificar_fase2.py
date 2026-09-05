#!/usr/bin/env python3
"""
Verificação dos padrões de logging da Fase 2 - sem imports.
Apenas verifica padrões regex nos arquivos fonte.
"""
import re
import os
import sys

BASE = "/home/node/mega-drive/Projetos/Trabalho/MS-Automatizar"

def verificar():
    print("=" * 60)
    print("VERIFICAÇÃO DE PADRÕES DE LOGGING - FASE 2")
    print("=" * 60)
    
    erros = 0
    ok = 0
    
    # 1. Verificar que todos os arquivos têm logger import
    print("\n📋 Imports do logger V2:")
    arquivos_alvo = [
        "src/processadores/holerite_processador.py",
        "src/processadores/processador_folha_ponto.py",
        "src/processadores/envio_holerite_orquestrador.py",
        "src/processadores/envio_folha_ponto_orquestrador.py",
        "src/interface/interface_funcionarios.py",
        "src/interface/interface_empresas.py",
        "src/interface/interface_holerite.py",
        "src/interface/interface_folha_de_ponto.py",
        "src/interface/interface_configuracoes.py",
        "src/interface/interface_referencias.py",
        "src/interface/interface_envio_holerite.py",
        "src/interface/interface_envio_folha_ponto.py",
        "src/interface/menu.py",
        "src/comandos/main.py",
        "src/comandos/referencias.py",
        "src/comandos/diretorios.py",
        "src/comandos/holerite.py",
        "src/comandos/folha_de_ponto.py",
    ]
    
    for arq in arquivos_alvo:
        path = os.path.join(BASE, arq)
        with open(path, 'r') as f:
            content = f.read()
        if "from src.utils.logger_config_v2 import get_logger" in content:
            print(f"  ✅ {arq}")
            ok += 1
        else:
            print(f"  ❌ {arq} - import ausente")
            erros += 1
    
    # 2. Verificar correlation IDs nos processadores
    print("\n🔗 Correlation IDs (processadores):")
    correlation_files = {
        "src/processadores/holerite_processador.py": "logger.correlation",
        "src/processadores/processador_folha_ponto.py": "logger.correlation",
        "src/processadores/envio_holerite_orquestrador.py": "logger.correlation",
        "src/processadores/envio_folha_ponto_orquestrador.py": "logger.correlation",
    }
    
    for arq, padrao in correlation_files.items():
        path = os.path.join(BASE, arq)
        with open(path, 'r') as f:
            content = f.read()
        if re.search(padrao, content):
            print(f"  ✅ {arq}")
            ok += 1
        else:
            print(f"  ❌ {arq} - {padrao} ausente")
            erros += 1
    
    # 3. Verificar performance tracking
    print("\n⚡ Performance tracking:")
    perf_files = {
        "src/processadores/holerite_processador.py": "logger.performance",
        "src/processadores/processador_folha_ponto.py": "logger.performance",
        "src/interface/interface_funcionarios.py": "logger.performance",
        "src/interface/interface_empresas.py": "logger.performance",
        "src/comandos/referencias.py": "logger.performance",
    }
    
    for arq, padrao in perf_files.items():
        path = os.path.join(BASE, arq)
        with open(path, 'r') as f:
            content = f.read()
        if re.search(padrao, content):
            print(f"  ✅ {arq}")
            ok += 1
        else:
            print(f"  ❌ {arq} - {padrao} ausente")
            erros += 1
    
    # 4. Verificar audit trail
    print("\n📝 Audit trail:")
    audit_files = {
        "src/processadores/holerite_processador.py": "logger.audit",
        "src/interface/interface_funcionarios.py": "logger.audit",
        "src/interface/interface_empresas.py": "logger.audit",
        "src/comandos/referencias.py": "logger.audit",
        "src/comandos/diretorios.py": "logger.audit",
    }
    
    for arq, padrao in audit_files.items():
        path = os.path.join(BASE, arq)
        with open(path, 'r') as f:
            content = f.read()
        if re.search(padrao, content):
            print(f"  ✅ {arq}")
            ok += 1
        else:
            print(f"  ❌ {arq} - {padrao} ausente")
            erros += 1
    
    # 5. Verificar syntax de todos os arquivos
    print("\n🔍 Verificação de syntax:")
    import py_compile
    
    todos_arquivos = arquivos_alvo + [
        "src/services/whatsapp_service.py",
        "src/services/zoho_mail_service.py",
        "src/utils/logger_config_v2.py",
    ]
    
    for arq in todos_arquivos:
        path = os.path.join(BASE, arq)
        try:
            py_compile.compile(path, doraise=True)
            print(f"  ✅ {arq}")
            ok += 1
        except py_compile.PyCompileError as e:
            print(f"  ❌ {arq}: {e}")
            erros += 1
    
    # 6. Contar ocorrências totais
    print("\n📊 Contagem de ocorrências:")
    total_correlation = 0
    total_performance = 0
    total_audit = 0
    
    for arq in todos_arquivos:
        path = os.path.join(BASE, arq)
        with open(path, 'r') as f:
            content = f.read()
        total_correlation += len(re.findall(r'logger\.correlation\(', content))
        total_performance += len(re.findall(r'logger\.performance\(', content))
        total_audit += len(re.findall(r'logger\.audit\(', content))
    
    print(f"  🔗 Correlation IDs: {total_correlation} ocorrências")
    print(f"  ⚡ Performance tracking: {total_performance} ocorrências")
    print(f"  📝 Audit trail: {total_audit} ocorrências")
    
    # Resumo
    print("\n" + "=" * 60)
    print(f"📊 RESULTADO: {ok} OK | {erros} ERROS")
    print("=" * 60)
    
    return erros == 0


if __name__ == "__main__":
    sucesso = verificar()
    sys.exit(0 if sucesso else 1)
