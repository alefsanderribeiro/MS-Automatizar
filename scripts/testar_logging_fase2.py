#!/usr/bin/env python3
"""
Script de teste para verificar se o Sistema de Log V2 funciona corretamente
após a Fase 2 de implementação.

Uso:
    cd /home/node/mega-drive/Projetos/Trabalho/MS-Automatizar
    python scripts/testar_logging_fase2.py
"""

import sys
import os

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def testar_imports():
    """Testa se todos os módulos podem ser importados"""
    print("=" * 60)
    print("TESTE 1: Verificando imports do logger")
    print("=" * 60)
    
    erros = []
    
    try:
        from src.utils.logger_config_v2 import get_logger
        logger = get_logger("teste")
        print("  ✅ get_logger importado com sucesso")
    except Exception as e:
        erros.append(f"get_logger: {e}")
        print(f"  ❌ get_logger: {e}")
    
    # Testar import de cada módulo
    modulos = [
        ("src.processadores.holerite_processador", "HoleriteProcessador"),
        ("src.processadores.processador_folha_ponto", "ProcessadorFolhaPonto"),
        ("src.processadores.envio_holerite_orquestrador", "EnvioHoleriteOrquestrador"),
        ("src.processadores.envio_folha_ponto_orquestrador", "EnvioFolhaPontoOrquestrador"),
        ("src.comandos.main", "start_command"),
        ("src.comandos.referencias", "listar_contratos"),
        ("src.comandos.diretorios", "listar_diretorios"),
        ("src.comandos.holerite", "holerite_subcommands"),
        ("src.comandos.folha_de_ponto", "folha_de_ponto_subcommands"),
        ("src.interface.menu", "init_interface"),
        ("src.interface.interface_funcionarios", "Interface_Funcionarios"),
        ("src.interface.interface_empresas", "Interface_Empresas"),
        ("src.interface.interface_holerite", "Interface_Holerite"),
        ("src.interface.interface_folha_de_ponto", "Interface_Folha_de_Ponto"),
        ("src.interface.interface_configuracoes", "Interface_Configuracoes"),
        ("src.interface.interface_referencias", "Interface_Referencias"),
        ("src.interface.interface_envio_holerite", "iniciar_menu_envio_holerite"),
        ("src.interface.interface_envio_folha_ponto", "iniciar_menu_envio"),
    ]
    
    for modulo, atributo in modulos:
        try:
            mod = __import__(modulo, fromlist=[atributo])
            print(f"  ✅ {modulo}")
        except Exception as e:
            erros.append(f"{modulo}: {e}")
            print(f"  ❌ {modulo}: {e}")
    
    return len(erros) == 0


def testar_funcionalidades_logger():
    """Testa as funcionalidades do logger V2"""
    print("\n" + "=" * 60)
    print("TESTE 2: Funcionalidades do Logger V2")
    print("=" * 60)
    
    from src.utils.logger_config_v2 import get_logger
    
    logger = get_logger("teste_funcionalidades")
    
    # Teste 1: Log básico
    try:
        logger.info("Teste de log básico")
        print("  ✅ Log básico funciona")
    except Exception as e:
        print(f"  ❌ Log básico: {e}")
        return False
    
    # Teste 2: Performance tracking
    try:
        with logger.performance("teste_operacao"):
            import time
            time.sleep(0.01)
        print("  ✅ Performance tracking funciona")
    except Exception as e:
        print(f"  ❌ Performance tracking: {e}")
        return False
    
    # Teste 3: Correlation ID
    try:
        with logger.correlation("teste_fluxo") as corr_id:
            assert corr_id is not None
            assert len(corr_id) > 0
            logger.info("Dentro do correlation", correlation_id=corr_id)
        print("  ✅ Correlation ID funciona")
    except Exception as e:
        print(f"  ❌ Correlation ID: {e}")
        return False
    
    # Teste 4: Audit trail
    try:
        logger.audit("TESTE_AUDIT", target="teste:123", changes={"campo": "valor"})
        print("  ✅ Audit trail funciona")
    except Exception as e:
        print(f"  ❌ Audit trail: {e}")
        return False
    
    # Teste 5: Performance stats
    try:
        stats = logger.get_performance_stats("teste_operacao")
        assert stats["count"] >= 1
        print(f"  ✅ Performance stats: {stats['count']} registros, média {stats.get('avg_ms', 0):.2f}ms")
    except Exception as e:
        print(f"  ❌ Performance stats: {e}")
        return False
    
    return True


def testar_logger_modulos():
    """Testa se cada módulo tem logger configurado"""
    print("\n" + "=" * 60)
    print("TESTE 3: Loggers por módulo")
    print("=" * 60)
    
    from src.utils.logger_config_v2 import get_logger
    
    modulos_esperados = [
        "holerite",
        "folha_ponto",
        "interface",
        "comando",
        "whatsapp",
        "email",
    ]
    
    todos_ok = True
    for modulo in modulos_esperados:
        try:
            logger = get_logger(modulo)
            logger.info(f"Teste do módulo {modulo}")
            print(f"  ✅ Logger '{modulo}' funciona")
        except Exception as e:
            print(f"  ❌ Logger '{modulo}': {e}")
            todos_ok = False
    
    return todos_ok


def testar_novos_recursos():
    """Testa se os novos recursos (audit, correlation, performance) estão presentes"""
    print("\n" + "=" * 60)
    print("TESTE 4: Novos recursos nos arquivos modificados")
    print("=" * 60)
    
    import inspect
    from src.utils.logger_config_v2 import get_logger
    
    # Verificar se os métodos audit, performance e correlation existem
    logger = get_logger("teste")
    
    recursos = {
        "audit": hasattr(logger, 'audit'),
        "performance": hasattr(logger, 'performance'),
        "correlation": hasattr(logger, 'correlation'),
        "get_performance_stats": hasattr(logger, 'get_performance_stats'),
    }
    
    for recurso, existe in recursos.items():
        if existe:
            print(f"  ✅ {recurso} disponível")
        else:
            print(f"  ❌ {recurso} NÃO encontrado")
    
    return all(recursos.values())


def verificar_padroes_logging():
    """Verifica se os padrões de logging foram aplicados corretamente"""
    print("\n" + "=" * 60)
    print("TESTE 5: Padrões de logging nos arquivos")
    print("=" * 60)
    
    import re
    
    padroes = {
        "src/processadores/holerite_processador.py": [
            (r"logger\.correlation\(", "correlation ID"),
            (r"logger\.performance\(", "performance tracking"),
            (r"logger\.audit\(", "audit trail"),
        ],
        "src/processadores/processador_folha_ponto.py": [
            (r"logger\.correlation\(", "correlation ID"),
            (r"logger\.performance\(", "performance tracking"),
        ],
        "src/processadores/envio_holerite_orquestrador.py": [
            (r"logger\.correlation\(", "correlation ID"),
        ],
        "src/processadores/envio_folha_ponto_orquestrador.py": [
            (r"logger\.correlation\(", "correlation ID"),
        ],
        "src/interface/interface_funcionarios.py": [
            (r"logger\.performance\(", "performance tracking"),
            (r"logger\.audit\(", "audit trail"),
        ],
        "src/interface/interface_empresas.py": [
            (r"logger\.performance\(", "performance tracking"),
            (r"logger\.audit\(", "audit trail"),
        ],
        "src/comandos/referencias.py": [
            (r"logger\.audit\(", "audit trail"),
            (r"logger\.performance\(", "performance tracking"),
        ],
        "src/comandos/diretorios.py": [
            (r"logger\.audit\(", "audit trail"),
        ],
    }
    
    todos_ok = True
    for arquivo, padroes_lista in padroes.items():
        try:
            with open(arquivo, 'r') as f:
                conteudo = f.read()
            
            for padrao, nome in padroes_lista:
                if re.search(padrao, conteudo):
                    print(f"  ✅ {arquivo}: {nome}")
                else:
                    print(f"  ❌ {arquivo}: {nome} NÃO encontrado")
                    todos_ok = False
        except FileNotFoundError:
            print(f"  ⚠️ Arquivo não encontrado: {arquivo}")
            todos_ok = False
    
    return todos_ok


def main():
    """Executa todos os testes"""
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    print("\n🧪 TESTES DO SISTEMA DE LOG V2 - FASE 2")
    print("=" * 60)
    
    resultados = []
    
    resultados.append(("Imports", testar_imports()))
    resultados.append(("Funcionalidades Logger", testar_funcionalidades_logger()))
    resultados.append(("Loggers por módulo", testar_logger_modulos()))
    resultados.append(("Novos recursos", testar_novos_recursos()))
    resultados.append(("Padrões de logging", verificar_padroes_logging()))
    
    # Resumo
    print("\n" + "=" * 60)
    print("📊 RESUMO DOS TESTES")
    print("=" * 60)
    
    todos_passaram = True
    for nome, passou in resultados:
        status = "✅ PASSOU" if passou else "❌ FALHOU"
        print(f"  {status} - {nome}")
        if not passou:
            todos_passaram = False
    
    print("\n" + "=" * 60)
    if todos_passaram:
        print("🎉 TODOS OS TESTES PASSARAM!")
    else:
        print("⚠️ ALGUNS TESTES FALHARAM - Verifique os erros acima")
    print("=" * 60)
    
    return 0 if todos_passaram else 1


if __name__ == "__main__":
    sys.exit(main())
