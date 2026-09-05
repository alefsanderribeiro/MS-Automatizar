"""
Utilitários centralizados para operações MongoDB.

Este módulo fornece funções auxiliares para buscar dados relacionados
em diferentes coleções do MongoDB, evitando duplicação de código.

Utiliza os serviços existentes (FuncaoService, HorarioService, etc.)
ao invés de criar conexões diretas com o MongoDB.
"""

from typing import Optional, Dict, Any, List
from src.utils.logger_config_v2 import get_logger


# Logger do módulo
logger = get_logger("mongodb")

# Cache dos serviços para evitar reinicialização
_services_cache = {}


def _get_funcao_service():
    """Retorna instância cacheada do FuncaoService"""
    if 'funcao' not in _services_cache:
        try:
            from src.services.funcao_service import FuncaoService
            _services_cache['funcao'] = FuncaoService()
        except Exception as e:
            logger.error(f"Erro ao inicializar FuncaoService: {e}")
            return None
    return _services_cache['funcao']


def _get_horario_service():
    """Retorna instância cacheada do HorarioService"""
    if 'horario' not in _services_cache:
        try:
            from src.services.horario_service import HorarioService
            _services_cache['horario'] = HorarioService()
        except Exception as e:
            logger.error(f"Erro ao inicializar HorarioService: {e}")
            return None
    return _services_cache['horario']


def _get_contrato_service():
    """Retorna instância cacheada do ContratoService"""
    if 'contrato' not in _services_cache:
        try:
            from src.services.contrato_service import ContratoService
            _services_cache['contrato'] = ContratoService()
        except Exception as e:
            logger.error(f"Erro ao inicializar ContratoService: {e}")
            return None
    return _services_cache['contrato']


def _get_funcionario_service():
    """Retorna instância cacheada do FuncionarioService"""
    if 'funcionario' not in _services_cache:
        try:
            from src.services.funcionario_service import FuncionarioService
            _services_cache['funcionario'] = FuncionarioService()
        except Exception as e:
            logger.error(f"Erro ao inicializar FuncionarioService: {e}")
            return None
    return _services_cache['funcionario']


def _get_empresa_service():
    """Retorna instância cacheada do EmpresaService"""
    if 'empresa' not in _services_cache:
        try:
            from src.services.empresa_service import EmpresaService
            _services_cache['empresa'] = EmpresaService()
        except Exception as e:
            logger.error(f"Erro ao inicializar EmpresaService: {e}")
            return None
    return _services_cache['empresa']


def _get_folha_ponto_service():
    """Retorna instância cacheada do FolhaDePontoService"""
    if 'folha_ponto' not in _services_cache:
        try:
            from src.services.folha_ponto_service import FolhaDePontoService
            _services_cache['folha_ponto'] = FolhaDePontoService()
        except Exception as e:
            logger.error(f"Erro ao inicializar FolhaDePontoService: {e}")
            return None
    return _services_cache['folha_ponto']


# ==================== FUNÇÕES DE BUSCA ====================

def buscar_nome_funcao(funcao_id) -> str:
    """
    Busca o nome da função pelo ObjectId.
    
    Args:
        funcao_id: ObjectId da função (string ou ObjectId)
    
    Returns:
        Nome da função ou "N/A" se não encontrada
    """
    if not funcao_id:
        return "N/A"
    
    try:
        service = _get_funcao_service()
        if service and service.disponivel:
            # Converter para string se for ObjectId
            funcao_id_str = str(funcao_id)
            funcao_doc = service.buscar_por_id(funcao_id_str)
            if funcao_doc:
                return funcao_doc.get('nome', 'N/A')
        return "N/A"
    except Exception as e:
        logger.debug(f"Erro ao buscar nome da função: {e}")
        return "N/A"


def buscar_nome_horario(horario_id) -> str:
    """
    Busca o nome do horário pelo ObjectId.
    
    Args:
        horario_id: ObjectId do horário (string ou ObjectId)
    
    Returns:
        Nome do horário ou "N/A" se não encontrado
    """
    if not horario_id:
        return "N/A"
    
    try:
        service = _get_horario_service()
        if service and service.disponivel:
            horario_id_str = str(horario_id)
            horario_doc = service.buscar_por_id(horario_id_str)
            if horario_doc:
                return horario_doc.get('descricao', 'N/A')
        return "N/A"
    except Exception as e:
        logger.debug(f"Erro ao buscar nome do horário: {e}")
        return "N/A"


def buscar_nome_contrato(contrato_id) -> str:
    """
    Busca o nome do contrato pelo ObjectId.
    
    Args:
        contrato_id: ObjectId do contrato (string ou ObjectId)
    
    Returns:
        Nome do contrato ou "N/A" se não encontrado
    """
    if not contrato_id:
        return "N/A"
    
    try:
        service = _get_contrato_service()
        if service and service.disponivel:
            contrato_id_str = str(contrato_id)
            contrato_doc = service.buscar_por_id(contrato_id_str)
            if contrato_doc:
                return contrato_doc.get('nome', 'N/A')
        return "N/A"
    except Exception as e:
        logger.debug(f"Erro ao buscar nome do contrato: {e}")
        return "N/A"


def buscar_funcionario(funcionario_id) -> Optional[Dict[str, Any]]:
    """
    Busca dados completos do funcionário pelo ObjectId.
    
    Args:
        funcionario_id: ObjectId do funcionário (string ou ObjectId)
    
    Returns:
        Dicionário com dados do funcionário ou None
    """
    if not funcionario_id:
        return None
    
    try:
        service = _get_funcionario_service()
        if service and service.disponivel:
            return service.buscar_por_object_id(funcionario_id)
        return None
    except Exception as e:
        logger.debug(f"Erro ao buscar funcionário: {e}")
        return None


def buscar_empresa(empresa_id) -> Optional[Dict[str, Any]]:
    """
    Busca dados da empresa pelo ObjectId.
    
    Args:
        empresa_id: ObjectId da empresa (string ou ObjectId)
    
    Returns:
        Dicionário com dados da empresa ou None
    """
    if not empresa_id:
        return None
    
    try:
        service = _get_empresa_service()
        if service and service.disponivel:
            empresa_id_str = str(empresa_id)
            return service.buscar_por_id(empresa_id_str)
        return None
    except Exception as e:
        logger.debug(f"Erro ao buscar empresa: {e}")
        return None


def buscar_folha_existente(funcionario_id, empresa_id, mes_referencia: str) -> Optional[Dict[str, Any]]:
    """
    Busca folha de ponto existente no MongoDB.
    
    Args:
        funcionario_id: ObjectId do funcionário
        empresa_id: ObjectId da empresa
        mes_referencia: Mês de referência (YYYY-MM)
    
    Returns:
        Documento da folha ou None se não existir
    """
    try:
        from bson import ObjectId
        
        service = _get_folha_ponto_service()
        if not service or not service.disponivel:
            return None
        
        # Converter para ObjectId se necessário
        if isinstance(funcionario_id, str):
            funcionario_id = ObjectId(funcionario_id)
        if isinstance(empresa_id, str):
            empresa_id = ObjectId(empresa_id)
        
        return service.colecao.find_one({
            "funcionario_id": funcionario_id,
            "empresa_id": empresa_id,
            "mes_referencia": mes_referencia
        })
    except Exception as e:
        logger.error(f"Erro ao buscar folha existente: {e}")
        return None


def listar_funcionarios_por_filtro(filtro: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Lista funcionários conforme filtro especificado.
    
    Args:
        filtro: Dicionário com filtros MongoDB (opcional)
    
    Returns:
        Lista de funcionários
    """
    try:
        service = _get_funcionario_service()
        if not service or not service.disponivel:
            return []
        
        filtro = filtro or {"status": "ativo"}
        return list(service.colecao.find(filtro).sort("nome", 1))
    except Exception as e:
        logger.error(f"Erro ao listar funcionários: {e}")
        return []


def buscar_contratos_por_nome(nomes: List[str]) -> List:
    """
    Busca IDs de contratos pelo nome (case-insensitive).
    
    Args:
        nomes: Lista de nomes de contratos
    
    Returns:
        Lista de ObjectIds dos contratos encontrados
    """
    try:
        service = _get_contrato_service()
        if not service or not service.disponivel:
            return []
        
        contrato_ids = []
        for nome in nomes:
            contrato_doc = service.colecao.find_one({"nome": {"$regex": nome, "$options": "i"}})
            if contrato_doc:
                contrato_ids.append(contrato_doc['_id'])
        return contrato_ids
    except Exception as e:
        logger.error(f"Erro ao buscar contratos por nome: {e}")
        return []


# ==================== FUNÇÕES DE FORMATAÇÃO ====================

def formatar_data(data_obj) -> str:
    """
    Formata uma data para exibição.
    
    Args:
        data_obj: Objeto datetime ou string
    
    Returns:
        String formatada (dd/mm/yyyy HH:MM) ou "N/A"
    """
    if hasattr(data_obj, 'strftime'):
        return data_obj.strftime('%d/%m/%Y %H:%M')
    return str(data_obj) if data_obj else "N/A"


def limpar_cache_services():
    """Limpa o cache de serviços (útil para testes)"""
    global _services_cache
    _services_cache = {}
