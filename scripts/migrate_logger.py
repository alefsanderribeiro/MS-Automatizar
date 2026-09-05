#!/usr/bin/env python3
"""
Script de Migração Automatizado: Logger V1 → V2

Este script migra automaticamente todos os arquivos do projeto
do logger antigo para o novo sistema de logging v2.

Uso:
    python scripts/migrate_logger.py
    python scripts/migrate_logger.py --dry-run  # Apenas mostra mudanças
    python scripts/migrate_logger.py --file src/services/funcionario_service.py  # Migrar arquivo específico
"""

import os
import re
import sys
import argparse
from pathlib import Path
from typing import List, Tuple, Dict

# ==================== CONFIGURAÇÃO ====================

PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"

# Mapeamento de módulos para arquivos de log
MODULE_MAPPING = {
    # Services
    "src/services/funcionario_service.py": "funcionario",
    "src/services/empresa_service.py": "empresa",
    "src/services/contrato_service.py": "contrato",
    "src/services/holerite_service.py": "holerite",
    "src/services/folha_ponto_service.py": "folha_ponto",
    "src/services/diretorio_service.py": "diretorio",
    "src/services/funcao_service.py": "funcao",
    "src/services/horario_service.py": "horario",
    "src/services/cache_ocr_service.py": "mongodb",
    "src/services/cache_service.py": "cache",
    "src/services/contato_funcionario_service.py": "contato",
    "src/services/grupo_whatsapp_service.py": "whatsapp",
    "src/services/template_mensagem_service.py": "template",
    "src/services/mongodb_connection.py": "mongodb",
    "src/services/mongodb_utils.py": "mongodb",
    "src/services/historico_decorators.py": "historico",
    "src/services/analise_ai_service.py": "ia",
    "src/services/config_service.py": "config",
    "src/services/planilha_contatos_service.py": "planilha",
    "src/services/planilha_holerites_service.py": "planilha",
    "src/services/envio_folha_ponto_service.py": "envio",
    "src/services/feriado_service.py": "feriado",
    "src/services/whatsapp_service.py": "whatsapp",
    "src/services/zoho_mail_service.py": "email",
    
    # Processadores
    "src/processadores/holerite_processador.py": "holerite",
    "src/processadores/processador_folha_ponto.py": "folha_ponto",
    "src/processadores/envio_holerite_orquestrador.py": "holerite",
    "src/processadores/envio_folha_ponto_orquestrador.py": "folha_ponto",
    
    # Interface
    "src/interface/interface_funcionarios.py": "interface",
    "src/interface/interface_empresas.py": "interface",
    "src/interface/interface_holerite.py": "interface",
    "src/interface/interface_folha_de_ponto.py": "interface",
    "src/interface/interface_configuracoes.py": "interface",
    "src/interface/interface_referencias.py": "interface",
    "src/interface/interface_envio_holerite.py": "interface",
    "src/interface/interface_envio_folha_ponto.py": "interface",
    "src/interface/menu.py": "interface",
    
    # Comandos
    "src/comandos/diretorios.py": "comando",
    "src/comandos/folha_de_ponto.py": "comando",
    "src/comandos/holerite.py": "comando",
    "src/comandos/referencias.py": "comando",
    
    # Utils
    "src/utils/env_validator.py": "validacao",
    "src/utils/funcionario_sanitizador.py": "sanitizacao",
    "src/utils/pdf_conversor.py": "pdf",
    "src/utils/retry_utils.py": "retry",
    "src/utils/telefone_utils.py": "telefone",
    "src/utils/__init__.py": "utils",
    
    # Outros
    "src/folha_de_ponto.py": "folha_ponto",
    "src/holerite.py": "holerite",
}


# ==================== FUNÇÕES DE MIGRAÇÃO ====================

def detectar_imports_antigos(content: str) -> List[str]:
    """Detecta todas as importações do logger antigo"""
    patterns = [
        r'from src\.utils\.logger_config import\s+(.+)',
        r'import src\.utils\.logger_config',
    ]
    
    imports = []
    for pattern in patterns:
        matches = re.findall(pattern, content)
        imports.extend(matches)
    
    return imports


def detectar_usos_logger(content: str) -> Dict[str, int]:
    """Detecta usos do logger no código"""
    usages = {
        'logger.debug': len(re.findall(r'logger\.debug\(', content)),
        'logger.info': len(re.findall(r'logger\.info\(', content)),
        'logger.warning': len(re.findall(r'logger\.warning\(', content)),
        'logger.error': len(re.findall(r'logger\.error\(', content)),
        'logger.critical': len(re.findall(r'logger\.critical\(', content)),
    }
    return usages


def detectar_operacoes_crud(content: str) -> Dict[str, int]:
    """Detecta operações CRUD que precisam de audit trail"""
    crud = {
        'insert_one': len(re.findall(r'\.insert_one\(', content)),
        'update_one': len(re.findall(r'\.update_one\(', content)),
        'delete_one': len(re.findall(r'\.delete_one\(', content)),
        'find_one': len(re.findall(r'\.find_one\(', content)),
        'find': len(re.findall(r'\.find\(', content)),
    }
    return crud


def migrar_imports(content: str, module_name: str) -> str:
    """Migra as importações do logger antigo para o novo"""
    
    # Padrão para importações antigas
    old_import_patterns = [
        r'from src\.utils\.logger_config import\s+logger\s*\n?',
        r'from src\.utils\.logger_config import\s+(\w+)\s*,\s*(\w+)\s*\n?',
        r'import src\.utils\.logger_config\s*\n?',
    ]
    
    # Nova importação
    new_import = f"from src.utils.logger_config_v2 import get_logger\n"
    
    # Remover importações antigas
    content_new = content
    for pattern in old_import_patterns:
        content_new = re.sub(pattern, '', content_new)
    
    # Adicionar nova importação após outros imports
    # Encontrar última linha de importação
    lines = content_new.split('\n')
    last_import_line = 0
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            last_import_line = i
        elif stripped and not stripped.startswith('#') and not stripped.startswith('"""') and not stripped.startswith("'''"):
            if last_import_line > 0:
                break
    
    # Inserir nova importação
    lines.insert(last_import_line + 1, new_import)
    content_new = '\n'.join(lines)
    
    return content_new


def adicionar_logger_modulo(content: str, module_name: str, file_path: str) -> str:
    """Adiciona inicialização do logger com nome do módulo"""
    
    # Verificar se já tem get_logger
    if 'get_logger(' in content:
        return content
    
    # Encontrar primeira classe ou função
    class_pattern = r'(class\s+\w+.*?:)'
    func_pattern = r'(def\s+__init__\s*\(self.*?\):)'
    
    # Para classes com __init__
    class_match = re.search(class_pattern, content)
    init_match = re.search(func_pattern, content)
    
    if class_match and init_match:
        # Adicionar self.logger no __init__
        init_pos = init_match.start()
        init_line_end = content.find('\n', init_pos)
        
        # Encontrar o corpo do __init__ (após a linha de def)
        body_start = init_line_end + 1
        
        # Adicionar self.logger = get_logger("module")
        logger_init = f'\n        self.logger = get_logger("{module_name}")\n'
        
        # Verificar se já tem self.logger
        if 'self.logger' not in content:
            content = content[:body_start] + logger_init + content[body_start:]
    
    # Para módulos sem classe (funções soltas)
    elif 'logger.' in content and 'self.logger' not in content:
        # Adicionar logger no nível do módulo
        # Encontrar após imports
        lines = content.split('\n')
        last_import = 0
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('import ') or stripped.startswith('from '):
                last_import = i
            elif stripped and not stripped.startswith('#') and not stripped.startswith('"""') and i > last_import + 1:
                if not stripped.startswith('def ') and not stripped.startswith('class '):
                    continue
                break
        
        # Inicializar logger após imports
        logger_line = f'\n# Logger do módulo\nlogger = get_logger("{module_name}")\n'
        lines.insert(last_import + 2, logger_line)
        content = '\n'.join(lines)
    
    return content


def adicionar_audit_trail(content: str) -> str:
    """Adiciona audit trail em operações CRUD"""
    
    # Padrões para detectar operações CRUD
    insert_pattern = r'(\s*)(resultado\s*=\s*self\.colecao\.insert_one\((\w+)\))'
    update_pattern = r'(\s*)(resultado\s*=\s*self\.colecao\.update_one\(([^)]+)\))'
    delete_pattern = r'(\s*)(resultado\s*=\s*self\.colecao\.delete_one\(([^)]+)\))'
    
    # Para insert_one
    def adicionar_audit_insert(match):
        indent = match.group(1)
        original = match.group(2)
        var_name = match.group(3)
        
        audit_code = f"""{indent}{original}
{indent}if resultado and resultado.inserted_id:
{indent}    self.logger.audit(
{indent}        action="REGISTRO_CRIADO",
{indent}        target=f"{{self.collection_name}}:{{resultado.inserted_id}}",
{indent}        changes={{'dados': str({var_name})[:200]}}
{indent}    )"""
        
        return audit_code
    
    content = re.sub(insert_pattern, adicionar_audit_insert, content)
    
    # Para update_one
    def adicionar_audit_update(match):
        indent = match.group(1)
        original = match.group(2)
        
        audit_code = f"""{indent}{original}
{indent}if resultado and resultado.modified_count > 0:
{indent}    self.logger.audit(
{indent}        action="REGISTRO_ATUALIZADO",
{indent}        target=f"{{self.collection_name}}",
{indent}        changes={{'operacao': 'update'}}
{indent}    )"""
        
        return audit_code
    
    content = re.sub(update_pattern, adicionar_audit_update, content)
    
    return content


def adicionar_performance_tracking(content: str) -> str:
    """Adiciona performance tracking em queries MongoDB"""
    
    # Padrão para find_one
    find_one_pattern = r'(\s*)(resultado\s*=\s*self\.colecao\.find_one\(([^)]+)\))'
    
    def adicionar_perf_find(match):
        indent = match.group(1)
        original = match.group(2)
        
        perf_code = f"""{indent}with self.logger.performance("buscar_registro"):
{indent}    {original}"""
        
        return perf_code
    
    # Apenas adicionar se não já tem performance tracking
    if 'with self.logger.performance(' not in content:
        content = re.sub(find_one_pattern, adicionar_perf_find, content)
    
    return content


def migrar_arquivo(file_path: Path, dry_run: bool = False) -> Tuple[bool, str]:
    """Migra um arquivo individual"""
    
    # Determinar caminho relativo
    rel_path = file_path.relative_to(PROJECT_ROOT)
    rel_path_str = str(rel_path)
    
    # Obter nome do módulo
    module_name = MODULE_MAPPING.get(rel_path_str, "app")
    
    # Ler conteúdo
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return False, f"Erro ao ler arquivo: {e}"
    
    # Verificar se já foi migrado
    if 'from src.utils.logger_config_v2 import' in content:
        return True, "Já migrado"
    
    # Verificar se usa o logger antigo
    if 'from src.utils.logger_config import' not in content:
        return True, "Não usa logger antigo"
    
    # Detectar estado atual
    imports_antigos = detectar_imports_antigos(content)
    usos_logger = detectar_usos_logger(content)
    operacoes_crud = detectar_operacoes_crud(content)
    
    print(f"\n{'='*60}")
    print(f"📄 Migrando: {rel_path_str}")
    print(f"   Módulo: {module_name}")
    print(f"   Imports antigos: {imports_antigos}")
    print(f"   Usos de logger: {usos_logger}")
    print(f"   Operações CRUD: {operacoes_crud}")
    
    # Aplicar migrações
    new_content = content
    
    # 1. Migrar imports
    new_content = migrar_imports(new_content, module_name)
    
    # 2. Adicionar logger do módulo
    new_content = adicionar_logger_modulo(new_content, module_name, rel_path_str)
    
    # 3. Adicionar audit trail (se tiver operações CRUD)
    if any(v > 0 for v in operacoes_crud.values()):
        print(f"   → Adicionando audit trail para operações CRUD")
        new_content = adicionar_audit_trail(new_content)
    
    # 4. Adicionar performance tracking (se tiver queries)
    if operacoes_crud.get('find_one', 0) > 0 or operacoes_crud.get('find', 0) > 0:
        print(f"   → Adicionando performance tracking")
        new_content = adicionar_performance_tracking(new_content)
    
    # Salvar
    if dry_run:
        print(f"   [DRY RUN] Alterações não salvas")
        return True, "Dry run"
    
    try:
        file_path.write_text(new_content, encoding='utf-8')
        print(f"   ✅ Migrado com sucesso")
        return True, "Migrado"
    except Exception as e:
        return False, f"Erro ao salvar: {e}"


def migrar_todos(dry_run: bool = False, arquivo_especifico: str = None):
    """Migra todos os arquivos do projeto"""
    
    print("=" * 70)
    print("🔄 MIGRAÇÃO DO SISTEMA DE LOG: V1 → V2")
    print("=" * 70)
    
    # Coletar arquivos para migrar
    arquivos = []
    
    if arquivo_especifico:
        arquivos = [PROJECT_ROOT / arquivo_especifico]
    else:
        for root, dirs, files in os.walk(SRC_DIR):
            # Ignorar __pycache__
            dirs[:] = [d for d in dirs if d != '__pycache__']
            
            for file in files:
                if file.endswith('.py'):
                    arquivos.append(Path(root) / file)
    
    # Estatísticas
    total = len(arquivos)
    migrados = 0
    erros = 0
    ja_migrados = 0
    nao_usa_logger = 0
    
    print(f"\n📊 Total de arquivos: {total}")
    
    # Migrar cada arquivo
    for arquivo in sorted(arquivos):
        sucesso, msg = migrar_arquivo(arquivo, dry_run)
        
        if sucesso:
            if msg == "Já migrado":
                ja_migrados += 1
            elif msg == "Não usa logger antigo":
                nao_usa_logger += 1
            else:
                migrados += 1
        else:
            erros += 1
            print(f"   ❌ Erro: {msg}")
    
    # Relatório final
    print("\n" + "=" * 70)
    print("📊 RELATÓRIO FINAL DA MIGRAÇÃO")
    print("=" * 70)
    print(f"  Total de arquivos:      {total}")
    print(f"  ✅ Migrados:            {migrados}")
    print(f"  ⏭️  Já migrados:         {ja_migrados}")
    print(f"  ⏭️  Não usam logger:     {nao_usa_logger}")
    print(f"  ❌ Erros:                {erros}")
    print("=" * 70)


# ==================== MAIN ====================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migra logger antigo para novo")
    parser.add_argument("--dry-run", action="store_true", help="Apenas mostra mudanças sem salvar")
    parser.add_argument("--file", type=str, help="Migrar arquivo específico")
    
    args = parser.parse_args()
    
    migrar_todos(dry_run=args.dry_run, arquivo_especifico=args.file)
