"""
Módulo de Serviços para MongoDB

Serviços disponíveis:
- FuncionarioService: Gerencia funcionários
- EmpresaService: Gerencia empresas
- FolhaDePontoService: Gerencia folhas de ponto
- FuncaoService: Gerencia funções/cargos
- HorarioService: Gerencia horários de trabalho
- ContratoService: Gerencia contratos
- CacheOCRMongoDB: Cache para resultados de OCR
- MongoDBConnectionPool: Pool de conexões singleton

Decoradores e Utilitários de Histórico:
- registrar_historico: Decorador para registro automático de histórico
- HistoricoMixin: Mixin com métodos auxiliares para histórico

Utilitários:
- verificar_conexao_mongodb: Health check do MongoDB
- retry_mongodb: Decorador para retry automático
- medir_tempo: Context manager para métricas
"""

from src.services.funcionario_service import FuncionarioService, funcionario_service
from src.services.empresa_service import EmpresaService, empresa_service
from src.services.folha_ponto_service import FolhaDePontoService, folha_de_ponto_service, ResultadoSalvamento
from src.services.funcao_service import FuncaoService
from src.services.horario_service import HorarioService
from src.services.contrato_service import ContratoService
from src.services.diretorio_service import DiretorioService
from src.services.cache_ocr_service import CacheOCRMongoDB, cache_ocr
from src.services.cache_service import CacheService, cache_service
from src.services.historico_decorators import registrar_historico, HistoricoMixin

# Connection Pool e utilitários
from src.services.mongodb_connection import (
    MongoDBConnectionPool,
    mongodb_pool,
    verificar_conexao_mongodb,
    obter_database,
    obter_collection,
    retry_mongodb,
    medir_tempo
)

# Services de Envio de Folhas de Ponto
from src.services.template_mensagem_service import TemplateMensagemService, template_mensagem_service
from src.services.grupo_whatsapp_service import GrupoWhatsAppService, grupo_whatsapp_service
from src.services.envio_folha_ponto_service import EnvioFolhaPontoService, envio_folha_ponto_service
from src.services.zoho_mail_service import ZohoMailService, zoho_mail_service
from src.services.whatsapp_service import WhatsAppService, whatsapp_service
from src.services.planilha_contatos_service import PlanilhaContatosService, planilha_contatos_service

__all__ = [
    # Funcionário
    'FuncionarioService',
    'funcionario_service',
    # Empresa
    'EmpresaService',
    'empresa_service',
    # Folha de Ponto
    'FolhaDePontoService',
    'folha_de_ponto_service',
    'ResultadoSalvamento',
    # Função
    'FuncaoService',
    # Horário
    'HorarioService',
    # Contrato
    'ContratoService',
    # Diretório
    'DiretorioService',
    # Cache OCR
    'CacheOCRMongoDB',
    'cache_ocr',
    # Histórico - Decoradores e Mixin
    'registrar_historico',
    'HistoricoMixin',
    # Connection Pool
    'MongoDBConnectionPool',
    'mongodb_pool',
    'verificar_conexao_mongodb',
    'obter_database',
    'obter_collection',
    'retry_mongodb',
    'medir_tempo',
    # Envio de Folhas de Ponto
    'TemplateMensagemService',
    'template_mensagem_service',
    'GrupoWhatsAppService',
    'grupo_whatsapp_service',
    'EnvioFolhaPontoService',
    'envio_folha_ponto_service',
    'ZohoMailService',
    'zoho_mail_service',
    'WhatsAppService',
    'whatsapp_service',
    'PlanilhaContatosService',
    'planilha_contatos_service',
]
