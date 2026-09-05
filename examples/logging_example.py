"""
Exemplo de uso do novo sistema de log.

Este arquivo demonstra TODAS as funcionalidades do logger v2.
Execute com: python examples/logging_example.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.logger_config_v2 import get_logger, audit_log, performance_log, log_execution


def exemplo_basico():
    """Exemplo de log básico"""
    logger = get_logger("exemplo")
    
    logger.debug("Esta é uma mensagem de debug", extra_dado="valor")
    logger.info("Processamento iniciado", arquivo="recibo.pdf")
    logger.warning("Atenção: dados incompletos", campo="cpf")
    logger.error("Erro ao processar", erro_codigo=500)
    logger.critical("Falha crítica no sistema")


def exemplo_audit_trail():
    """Exemplo de audit trail"""
    logger = get_logger("exemplo")
    
    # Criar funcionário
    logger.audit(
        action="FUNCIONARIO_CRIADO",
        target="funcionario:12345",
        changes={
            "nome": "João Silva",
            "cpf": "123.456.789-00",
            "lotacao": "TI",
            "contrato": "CLT"
        },
        user="admin"
    )
    
    # Atualizar funcionário
    logger.audit(
        action="FUNCIONARIO_ATUALIZADO",
        target="funcionario:12345",
        changes={
            "campo_alterado": "lotacao",
            "valor_anterior": "TI",
            "valor_novo": "RH"
        },
        user="admin"
    )
    
    # Deletar funcionário (soft delete)
    logger.audit(
        action="FUNCIONARIO_INATIVADO",
        target="funcionario:12345",
        changes={
            "status_anterior": "ativo",
            "status_novo": "inativo",
            "motivo": "Desligamento"
        },
        user="sistema"
    )


def exemplo_performance():
    """Exemplo de performance tracking"""
    logger = get_logger("exemplo")
    
    # Simular operação lenta
    with logger.performance("buscar_funcionarios"):
        import time
        time.sleep(0.1)  # Simular query
        resultado = [{"nome": "João"}, {"nome": "Maria"}]
    
    # Simular operação rápida
    with logger.performance("validar_dados"):
        time.sleep(0.01)
    
    # Ver estatísticas
    stats = logger.get_performance_stats()
    print("\n📊 Estatísticas de Performance:")
    for op, data in stats.items():
        print(f"  {op}: {data['count']} ops, média {data['avg_ms']}ms")


def exemplo_correlation_id():
    """Exemplo de correlation ID para rastreamento"""
    logger = get_logger("exemplo")
    
    # Todas as operações dentro do context manager compartilham o mesmo ID
    with logger.correlation("processar_holerite_batch") as corr_id:
        logger.info("Iniciando processamento do batch")
        logger.info("Lendo arquivos PDF", total=10)
        logger.info("Processando arquivo 1/10", arquivo="recibo_001.pdf")
        logger.info("Processando arquivo 2/10", arquivo="recibo_002.pdf")
        logger.info("Batch concluído com sucesso", processados=10, erros=0)


def exemplo_decorador():
    """Exemplo usando decorador para logging automático"""
    
    @log_execution(module="exemplo", audit=True, audit_action="CRIAR_REGISTRO")
    def criar_registro(dados):
        """Função com logging automático"""
        # Simular criação
        return {"id": 123, **dados}
    
    @log_execution(module="exemplo", performance=True)
    def processar_dados(lista):
        """Função com performance tracking"""
        import time
        time.sleep(0.05)
        return [item * 2 for item in lista]
    
    # Usar funções
    resultado1 = criar_registro({"nome": "Teste", "valor": 100})
    resultado2 = processar_dados([1, 2, 3, 4, 5])


def exemplo_audit_direto():
    """Exemplo de audit log direto (sem logger)"""
    
    # Função de conveniência
    audit_log(
        action="EMPRESA_CRIADA",
        target="empresa:6925...",
        changes={"nome": "Nova Empresa LTDA", "cnpj": "12.345.678/0001-90"}
    )


def exemplo_modulos_separados():
    """Exemplo de logs separados por módulo"""
    
    # Cada módulo tem seu próprio arquivo de log
    logger_mongo = get_logger("mongodb")
    logger_holerite = get_logger("holerite")
    logger_whatsapp = get_logger("whatsapp")
    
    logger_mongo.info("Conexão estabelecida", host="localhost", port=27017)
    logger_holerite.info("Holerite processado", arquivo="recibo.pdf", funcionario="João")
    logger_whatsapp.info("Mensagem enviada", grupo="Equipe TI", status="entregue")


def exemplo_completo():
    """Exemplo completo simulando um fluxo real"""
    
    logger = get_logger("fluxo_completo")
    
    # 1. Iniciar fluxo com correlation ID
    with logger.correlation("fluxo_cadastro_funcionario") as corr_id:
        
        # 2. Audit: Funcionário criado
        logger.audit(
            action="FUNCIONARIO_CRIADO",
            target="funcionario:1700",
            changes={
                "nome": "KAIDJI JABOTI",
                "data_nascimento": "21/05/2003",
                "data_admissao": "17/08/2026",
                "status": "ativo",
                "codigo_funcionario": 1700
            }
        )
        
        # 3. Performance: Buscar contrato
        with logger.performance("buscar_contrato"):
            import time
            time.sleep(0.02)
            contrato = {"nome": "DSEI PARINTINS", "status": "ativo"}
        
        # 4. Audit: Vincular a contrato
        logger.audit(
            action="FUNCIONARIO_VINCULADO_CONTRATO",
            target="funcionario:1700",
            changes={
                "contrato_anterior": None,
                "contrato_novo": "DSEI PARINTINS",
                "contrato_id": "6925a3fef0d6b51ffd30ea40"
            }
        )
        
        # 5. Audit: Atualizar dados
        logger.audit(
            action="FUNCIONARIO_ATUALIZADO",
            target="funcionario:1700",
            changes={
                "data_nascimento": {"anterior": None, "novo": "21/05/2003"},
                "data_admissao": {"anterior": None, "novo": "17/08/2026"},
                "codigo_funcionario": {"anterior": None, "novo": 1700}
            }
        )
        
        # 6. Performance: Salvar no MongoDB
        with logger.performance("salvar_funcionario_mongodb"):
            time.sleep(0.03)
        
        # 7. Log de sucesso
        logger.info("Funcionário cadastrado com sucesso", 
                   funcionario_id=1700, nome="KAIDJI JABOTI")
        
        # 8. Ver estatísticas
        stats = logger.get_performance_stats()
        print("\n📊 Estatísticas do Fluxo:")
        print(f"  Total de operações: {sum(s['count'] for s in stats.values())}")
        print(f"  Tempo total: {sum(s['avg_ms'] * s['count'] for s in stats.values()):.1f}ms")


if __name__ == "__main__":
    print("=" * 70)
    print("📝 EXEMPLOS DO SISTEMA DE LOG V2")
    print("=" * 70)
    
    print("\n1️⃣  Exemplo Básico...")
    exemplo_basico()
    
    print("\n2️⃣  Exemplo Audit Trail...")
    exemplo_audit_trail()
    
    print("\n3️⃣  Exemplo Performance...")
    exemplo_performance()
    
    print("\n4️⃣  Exemplo Correlation ID...")
    exemplo_correlation_id()
    
    print("\n5️⃣  Exemplo Decorador...")
    exemplo_decorador()
    
    print("\n6️⃣  Exemplo Audit Direto...")
    exemplo_audit_direto()
    
    print("\n7️⃣  Exemplo Módulos Separados...")
    exemplo_modulos_separados()
    
    print("\n8️⃣  Exemplo Completo...")
    exemplo_completo()
    
    print("\n" + "=" * 70)
    print("✅ Todos os exemplos executados!")
    print("=" * 70)
    print("\n📁 Verifique os logs em:")
    print("   - logs/app_*.log (geral)")
    print("   - logs/errors_*.log (erros)")
    print("   - logs/audit/audit_*.log (audit trail)")
    print("   - logs/performance/performance_*.log (métricas)")
    print("   - logs/modules/*.log (por módulo)")
