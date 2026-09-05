"""
Guia de Migração: Logger V1 → V2

Este arquivo mostra como migrar do logger antigo para o novo.
"""

# ============================================================
# ANTES (Logger V1 - Atual)
# ============================================================

# 1. Importação antiga
from src.utils.logger_config import logger

# 2. Uso básico
logger.info("Mensagem simples")
logger.error("Erro occurred")
logger.debug("Debug info")

# 3. Sem audit trail
# 4. Sem performance tracking
# 5. Sem correlation ID
# 6. Sem separação por módulo


# ============================================================
# DEPOIS (Logger V2 - Novo)
# ============================================================

# 1. Importação nova
from src.utils.logger_config_v2 import get_logger

# 2. Obter logger para módulo
logger = get_logger("funcionario")  # Cria logs separados em logs/modules/funcionario.log

# 3. Uso básico (mesmo que antes, mas com extras)
logger.info("Mensagem simples")
logger.error("Erro occurred")
logger.debug("Debug info", extra_dado="valor")

# 4. AUDIT TRAIL - Rastrear operações críticas
logger.audit(
    action="FUNCIONARIO_CRIADO",
    target="funcionario:12345",
    changes={
        "nome": "João Silva",
        "cpf": "123.456.789-00",
        "lotacao": "TI"
    },
    user="admin"
)

logger.audit(
    action="FUNCIONARIO_ATUALIZADO",
    target="funcionario:12345",
    changes={
        "campo": "lotacao",
        "de": "TI",
        "para": "RH"
    }
)

# 5. PERFORMANCE TRACKING
with logger.performance("buscar_funcionarios"):
    # Operação que quer medir
    resultado = collection.find_one({"nome": "João"})

# 6. CORRELATION ID - Rastrear operação ponta a ponta
with logger.correlation("processar_holerite_batch") as corr_id:
    logger.info("Iniciando batch", correlation_id=corr_id)
    logger.info("Processando arquivo 1")
    logger.info("Processando arquivo 2")
    logger.info("Batch concluído")

# 7. DECORADOR - Logging automático
from src.utils.logger_config_v2 import log_execution

@log_execution(module="funcionario", audit=True, audit_action="CRIAR_FUNCIONARIO")
def criar_funcionario(dados):
    # Código da função
    return {"id": 12345}

# 8. AUDIT DIRETO (sem logger)
from src.utils.logger_config_v2 import audit_log

audit_log(
    action="EMPRESA_CRIADA",
    target="empresa:6925...",
    changes={"nome": "Nova Empresa"}
)


# ============================================================
# MIGRAÇÃO PASSO A PASSO
# ============================================================

"""
PASSO 1: Atualizar importações em TODOS os arquivos:

    # DE:
    from src.utils.logger_config import logger
    
    # PARA:
    from src.utils.logger_config_v2 import get_logger

PASSO 2: Adicionar nome do módulo em cada arquivo:

    # DE:
    logger.info("Mensagem")
    
    # PARA:
    logger = get_logger("nome_do_modulo")
    logger.info("Mensagem")

PASSO 3: Adicionar audit trail em operações CRUD:

    # Em cada serviço que faz insert/update/delete:
    logger.audit(
        action="FUNCIONARIO_CRIADO",
        target=f"funcionario:{id}",
        changes=dados
    )

PASSO 4: Adicionar performance tracking em queries:

    # Em cada query MongoDB:
    with logger.performance("buscar_por_nome"):
        resultado = collection.find_one({"nome": nome})

PASSO 5: Adicionar correlation IDs em fluxos:

    # Em cada processamento em lote:
    with logger.correlation("processar_batch") as corr_id:
        # Todo o código aqui compartilha o mesmo ID
        pass

PASSO 6: Configurar .env:

    LOG_LEVEL=INFO
    LOG_FILE_LEVEL=DEBUG
    LOG_AUDIT_ENABLED=true
    LOG_PERFORMANCE_ENABLED=true
    LOG_MODULES=mongodb,holerite,folha_ponto,whatsapp,empresa,funcionario

PASSO 7: Limpar logger antigo (opcional):

    # O logger antigo pode ser mantido para compatibilidade
    # ou removido após migração completa
"""


# ============================================================
# EXEMPLO DE MIGRAÇÃO EM SERVICE
# ============================================================

"""
EXEMPLO: funcionario_service.py

ANTES:
-------
from src.utils.logger_config import logger

class FuncionarioService:
    def criar_funcionario(self, dados):
        logger.info(f"Criando funcionário: {dados['nome']}")
        resultado = self.colecao.insert_one(dados)
        logger.info(f"Funcionário criado: {resultado.inserted_id}")
        return resultado.inserted_id

    def buscar_por_nome(self, nome):
        logger.debug(f"Buscando por nome: {nome}")
        return self.colecao.find_one({"nome": nome})


DEPOIS:
-------
from src.utils.logger_config_v2 import get_logger

class FuncionarioService:
    def __init__(self):
        self.logger = get_logger("funcionario")
    
    def criar_funcionario(self, dados):
        self.logger.info(f"Criando funcionário: {dados['nome']}")
        
        # Audit trail
        self.logger.audit(
            action="FUNCIONARIO_CRIADO",
            target=f"funcionario:novo",
            changes=dados
        )
        
        # Performance tracking
        with self.logger.performance("inserir_funcionario_mongodb"):
            resultado = self.colecao.insert_one(dados)
        
        self.logger.info(f"Funcionário criado: {resultado.inserted_id}")
        return resultado.inserted_id

    def buscar_por_nome(self, nome):
        self.logger.debug(f"Buscando por nome: {nome}")
        
        with self.logger.performance("buscar_por_nome"):
            return self.colecao.find_one({"nome": nome})
"""


# ============================================================
# ARQUIVOS QUE PRECISAM SER ATUALIZADOS
# ============================================================

"""
Lista de todos os arquivos que usam o logger antigo e precisam ser migrados:

SERVICES (14 arquivos):
- src/services/funcionario_service.py
- src/services/empresa_service.py
- src/services/contrato_service.py
- src/services/holerite_service.py
- src/services/folha_ponto_service.py
- src/services/diretorio_service.py
- src/services/funcao_service.py
- src/services/horario_service.py
- src/services/cache_ocr_service.py
- src/services/cache_service.py
- src/services/contato_funcionario_service.py
- src/services/grupo_whatsapp_service.py
- src/services/template_mensagem_service.py
- src/services/mongodb_connection.py

PROCESSADORES (4 arquivos):
- src/processadores/holerite_processador.py
- src/processadores/processador_folha_ponto.py
- src/processadores/envio_holerite_orquestrador.py
- src/processadores/envio_folha_ponto_orquestrador.py

INTERFACE (8 arquivos):
- src/interface/interface_funcionarios.py
- src/interface/interface_empresas.py
- src/interface/interface_holerite.py
- src/interface/interface_folha_de_ponto.py
- src/interface/interface_configuracoes.py
- src/interface/interface_referencias.py
- src/interface/interface_envio_holerite.py
- src/interface/interface_envio_folha_ponto.py

COMANDOS (4 arquivos):
- src/comandos/diretorios.py
- src/comandos/folha_de_ponto.py
- src/comandos/holerite.py
- src/comandos/referencias.py

UTILS (6 arquivos):
- src/utils/env_validator.py
- src/utils/funcionario_sanitizador.py
- src/utils/pdf_conversor.py
- src/utils/retry_utils.py
- src/utils/telefone_utils.py
- src/utils/logger_config.py (próprio)

OUTROS (3 arquivos):
- src/folha_de_ponto.py
- src/holerite.py
- src/services/historico_decorators.py

TOTAL: 39 arquivos para migrar
"""
