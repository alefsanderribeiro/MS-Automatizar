"""
Decoradores e utilitários para registro automático de histórico de alterações

Fornece:
- @registrar_historico: Decorador para métodos de atualização em services
- HistoricoMixin: Mixin com métodos auxiliares para histórico

Uso:
    from src.services.historico_decorators import registrar_historico, HistoricoMixin

    
    class MeuService(HistoricoMixin):
        @registrar_historico(campos_rastrear=["nome", "status", "email"])
        def atualizar(self, object_id: str, alteracoes: dict, **kwargs) -> bool:
            # Lógica de atualização
            ...
"""

from functools import wraps
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timezone

from src.utils.logger_config_v2 import get_logger

logger = get_logger("historico")

def registrar_historico(
    campos_rastrear: Optional[List[str]] = None,
    origem_padrao: str = "interface_cli"
):
    """
    Decorador que automatiza o registro de histórico em operações de atualização.
    
    O decorador:
    1. Busca os valores anteriores do documento antes da atualização
    2. Executa a função de atualização original
    3. Registra a entrada de histórico com valores anteriores e novos
    
    Args:
        campos_rastrear: Lista de campos a monitorar. Se None, rastreia todos os campos alterados.
        origem_padrao: Origem padrão da alteração (pode ser sobrescrito via kwargs)
    
    Requisitos da função decorada:
        - Deve ser um método de uma classe que tenha:
            - self.colecao: Coleção MongoDB
            - self.disponivel: Propriedade que indica se MongoDB está conectado
        - Primeiro argumento deve ser object_id (string)
        - Segundo argumento deve ser alteracoes (dict)
        - Pode aceitar kwargs: origem, registrar_historico
    
    Exemplo:
        @registrar_historico(campos_rastrear=["nome", "email", "telefone"])
        def atualizar(self, object_id: str, alteracoes: dict, **kwargs) -> bool:
            # Apenas atualiza os campos - o decorador cuida do histórico
            resultado = self.colecao.update_one(
                {"_id": ObjectId(object_id)}
                {"$set": alteracoes}

            if resultado and resultado.modified_count > 0:
                self.logger.audit(
                    action="REGISTRO_ATUALIZADO",
                    target=f"{self.collection_name}",
                    changes={'operacao': 'update'}
            )
            return resultado.modified_count > 0
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, object_id: str, alteracoes: Dict[str, Any], **kwargs) -> Any:
            from bson.objectid import ObjectId
            
            # Verificar se deve registrar histórico (pode ser desabilitado)
            should_register = kwargs.pop('registrar_historico', True)
            origem = kwargs.pop('origem', origem_padrao)
            
            # Se não deve registrar, apenas executa a função original
            if not should_register:
                return func(self, object_id, alteracoes, **kwargs)
            
            # Verificar disponibilidade do MongoDB
            if not getattr(self, 'disponivel', False):
                logger.warning("MongoDB não disponível para registrar histórico")
                return func(self, object_id, alteracoes, **kwargs)
            
            try:
                # Converter object_id para ObjectId
                try:
                    obj_id = ObjectId(object_id)
                except Exception as e:
                    logger.warning(f"ObjectId inválido: {object_id}. Erro: {e}")
                    return False
                
                # 1. BUSCAR VALORES ANTERIORES
                colecao = getattr(self, 'colecao', None)
                if colecao is None:
                    logger.error("Serviço não possui atributo 'colecao'")
                    return func(self, object_id, alteracoes, **kwargs)
                
                documento_anterior = colecao.find_one({"_id": obj_id})
                if not documento_anterior:
                    logger.warning(f"Documento não encontrado para histórico: {object_id}")
                    return func(self, object_id, alteracoes, **kwargs)
                
                # Extrair valores anteriores dos campos que serão alterados
                campos_a_rastrear = campos_rastrear or list(alteracoes.keys())
                valores_anteriores = {}
                
                for campo in campos_a_rastrear:
                    if campo in alteracoes:  # Só rastreia se está sendo alterado
                        valor_anterior = documento_anterior.get(campo)
                        # Converter ObjectId para string para serialização
                        if hasattr(valor_anterior, '__str__') and type(valor_anterior).__name__ == 'ObjectId':
                            valores_anteriores[campo] = str(valor_anterior)
                        elif isinstance(valor_anterior, list):
                            # Converter lista de ObjectIds
                            valores_anteriores[campo] = [
                                str(v) if type(v).__name__ == 'ObjectId' else v 
                                for v in valor_anterior
                            ]
                        elif isinstance(valor_anterior, datetime):
                            valores_anteriores[campo] = valor_anterior.isoformat()
                        else:
                            valores_anteriores[campo] = valor_anterior
                
                # 2. ADICIONAR METADADOS À ALTERAÇÃO
                alteracoes_com_meta = alteracoes.copy()
                alteracoes_com_meta['atualizado_em'] = datetime.now(timezone.utc)
                
                # 3. CONSTRUIR OPERAÇÃO DE UPDATE COM HISTÓRICO
                acoes_por_origem = {
                    "interface_cli": "Dados atualizados via interface de linha de comando",
                    "excel": "Dados atualizados via sincronização com planilha Excel",
                    "api": "Dados atualizados via API",
                    "sistema": "Dados atualizados automaticamente pelo sistema",
                    "importacao": "Dados atualizados via importação de dados",
                    "migracao": "Dados atualizados via migração de sistema"
                }
                acao = acoes_por_origem.get(origem, f"Dados atualizados via {origem}")
                
                # Preparar valores novos para registro (convertendo tipos especiais)
                valores_novos = {}
                for k, v in alteracoes.items():
                    if k == 'atualizado_em':
                        continue
                    if hasattr(v, '__str__') and type(v).__name__ == 'ObjectId':
                        valores_novos[k] = str(v)
                    elif isinstance(v, list):
                        valores_novos[k] = [
                            str(item) if type(item).__name__ == 'ObjectId' else item 
                            for item in v
                        ]
                    elif isinstance(v, datetime):
                        valores_novos[k] = v.isoformat()
                    else:
                        valores_novos[k] = v
                
                entrada_historico = {
                    "timestamp": datetime.now(timezone.utc),  # DateTime nativo do MongoDB
                    "acao": acao,
                    "origem": origem,
                    "detalhes": {
                        "campos_alterados": list(alteracoes.keys()),
                        "valores_anteriores": valores_anteriores,
                        "valores_novos": valores_novos
                    }
                }
                
                # 4. EXECUTAR UPDATE COM HISTÓRICO
                update_ops = {
                    "$set": alteracoes_com_meta,
                    "$push": {"historico_alteracoes": entrada_historico},
                    "$inc": {"versao": 1}
                }
                
                resultado = colecao.update_one({"_id": obj_id}, update_ops)
                
                if resultado.modified_count > 0:
                    campos_str = ", ".join([k for k in alteracoes.keys() if k != 'atualizado_em'])
                    logger.info(f"✓ Documento {object_id} atualizado com histórico - campos: {campos_str}")
                    return True
                else:
                    logger.debug(f"Documento {object_id} sem alterações")
                    return False
                    
            except Exception as e:
                logger.error(f"Erro no decorador registrar_historico: {e}")
                # Em caso de erro, tenta executar a função original
                return func(self, object_id, alteracoes, **kwargs)
        
        return wrapper
    return decorator


class HistoricoMixin:
    """
    Mixin que adiciona métodos auxiliares para manipulação de histórico.
    
    Adicione esta mixin às suas classes de serviço para ter acesso a:
    - atualizar_com_historico: Método genérico para atualização com histórico automático
    - obter_historico: Retorna o histórico de alterações de um documento
    - limpar_historico: Remove entradas antigas do histórico
    
    Requisitos:
        - A classe deve ter self.colecao (coleção MongoDB)
        - A classe deve ter self.disponivel (propriedade booleana)
    
    Exemplo:
        class MeuService(HistoricoMixin):
            def __init__(self):

        self.logger = get_logger("historico")
                self.colecao = ...
                self.disponivel = True
            
            # Agora você pode usar:
            # self.atualizar_com_historico(id, {"campo": "novo_valor"}, origem="api")
    """
    
    def atualizar_com_historico(
        self,
        object_id: str,
        alteracoes: Dict[str, Any],
        origem: str = "interface_cli",
        campos_rastrear: Optional[List[str]] = None
    ) -> bool:
        """
        Atualiza um documento e registra automaticamente o histórico.
        
        Este método:
        1. Busca os valores anteriores do documento
        2. Aplica as alterações
        3. Registra a entrada no historico_alteracoes
        
        Args:
            object_id: ID do documento (string do ObjectId)
            alteracoes: Dicionário com campos a atualizar
            origem: Origem da alteração (interface_cli, excel, api, sistema, etc.)
            campos_rastrear: Lista específica de campos a rastrear. Se None, rastreia todos.
        
        Returns:
            True se atualização foi bem-sucedida, False caso contrário
        """
        from bson.objectid import ObjectId
        
        if not getattr(self, 'disponivel', False):
            logger.warning("MongoDB não disponível para atualização")
            return False
        
        colecao = getattr(self, 'colecao', None)
        if colecao is None:
            logger.error("Serviço não possui atributo 'colecao'")
            return False
        
        try:
            # Converter object_id
            try:
                obj_id = ObjectId(object_id)
            except Exception as e:
                logger.warning(f"ObjectId inválido: {object_id}. Erro: {e}")
                return False
            
            # 1. Buscar documento atual para capturar valores anteriores
            documento_atual = colecao.find_one({"_id": obj_id})
            if not documento_atual:
                logger.warning(f"Documento não encontrado: {object_id}")
                return False
            
            # 2. Capturar valores anteriores
            campos_a_rastrear = campos_rastrear or list(alteracoes.keys())
            valores_anteriores = {}
            
            for campo in campos_a_rastrear:
                if campo in alteracoes:
                    valor = documento_atual.get(campo)
                    # Serializar tipos especiais
                    if type(valor).__name__ == 'ObjectId':
                        valores_anteriores[campo] = str(valor)
                    elif isinstance(valor, list):
                        valores_anteriores[campo] = [
                            str(v) if type(v).__name__ == 'ObjectId' else v 
                            for v in valor
                        ]
                    elif isinstance(valor, datetime):
                        valores_anteriores[campo] = valor.isoformat()
                    else:
                        valores_anteriores[campo] = valor
            
            # 3. Preparar alterações com timestamp
            alteracoes_final = alteracoes.copy()
            alteracoes_final['atualizado_em'] = datetime.now(timezone.utc)
            
            # 4. Preparar valores novos para log
            valores_novos = {}
            for k, v in alteracoes.items():
                if type(v).__name__ == 'ObjectId':
                    valores_novos[k] = str(v)
                elif isinstance(v, list):
                    valores_novos[k] = [
                        str(item) if type(item).__name__ == 'ObjectId' else item 
                        for item in v
                    ]
                elif isinstance(v, datetime):
                    valores_novos[k] = v.isoformat()
                else:
                    valores_novos[k] = v
            
            # 5. Criar entrada de histórico
            acoes_por_origem = {
                "interface_cli": "Dados atualizados via interface de linha de comando",
                "excel": "Dados atualizados via sincronização com planilha Excel",
                "api": "Dados atualizados via API",
                "sistema": "Dados atualizados automaticamente pelo sistema",
                "importacao": "Dados atualizados via importação de dados",
                "migracao": "Dados atualizados via migração de sistema"
            }
            
            entrada_historico = {
                "timestamp": datetime.now(timezone.utc),  # DateTime nativo do MongoDB
                "acao": acoes_por_origem.get(origem, f"Dados atualizados via {origem}"),
                "origem": origem,
                "detalhes": {
                    "campos_alterados": list(alteracoes.keys()),
                    "valores_anteriores": valores_anteriores,
                    "valores_novos": valores_novos
                }
            }
            
            # 6. Executar update atômico
            resultado = colecao.update_one(
                {"_id": obj_id},
                {
                    "$set": alteracoes_final,
                    "$push": {"historico_alteracoes": entrada_historico},
                    "$inc": {"versao": 1}
                }
            )
            if resultado.modified_count > 0:
                campos_str = ", ".join([k for k in alteracoes.keys()])
                logger.info(f"✓ Documento {object_id} atualizado com histórico - campos: {campos_str}")
                return True
            else:
                logger.debug(f"Documento {object_id} sem alterações efetivas")
                return False
                
        except Exception as e:
            logger.error(f"Erro em atualizar_com_historico: {e}")
            return False
    
    def obter_historico(self, object_id: str, limite: int = 50) -> List[Dict[str, Any]]:
        """
        Retorna o histórico de alterações de um documento.
        
        Args:
            object_id: ID do documento
            limite: Número máximo de entradas a retornar (mais recentes primeiro)
        
        Returns:
            Lista de entradas de histórico, ordenadas do mais recente ao mais antigo
        """
        from bson.objectid import ObjectId
        
        if not getattr(self, 'disponivel', False):
            return []
        
        colecao = getattr(self, 'colecao', None)
        if colecao is None:
            return []
        
        try:
            obj_id = ObjectId(object_id)
            doc = colecao.find_one(
                {"_id": obj_id},
                {"historico_alteracoes": {"$slice": -limite}}
            )
            
            if doc and "historico_alteracoes" in doc:
                # Retornar em ordem reversa (mais recente primeiro)
                return list(reversed(doc["historico_alteracoes"]))
            return []
            
        except Exception as e:
            logger.error(f"Erro ao obter histórico: {e}")
            return []
    
    def limpar_historico_antigo(
        self, 
        object_id: str, 
        manter_ultimos: int = 100
    ) -> bool:
        """
        Remove entradas antigas do histórico, mantendo apenas as N mais recentes.
        
        Útil para evitar que o array de histórico cresça indefinidamente.
        
        Args:
            object_id: ID do documento
            manter_ultimos: Quantidade de entradas recentes a manter
        
        Returns:
            True se operação bem-sucedida
        """
        from bson.objectid import ObjectId
        
        if not getattr(self, 'disponivel', False):
            return False
        
        colecao = getattr(self, 'colecao', None)
        if colecao is None:
            return False
        
        try:
            obj_id = ObjectId(object_id)
            
            # Buscar documento atual
            doc = colecao.find_one({"_id": obj_id}, {"historico_alteracoes": 1})
            if not doc or "historico_alteracoes" not in doc:
                return True  # Nada para limpar
            
            historico = doc["historico_alteracoes"]
            if len(historico) <= manter_ultimos:
                return True  # Não precisa limpar
            
            # Manter apenas os últimos N
            historico_reduzido = historico[-manter_ultimos:]
            
            resultado = colecao.update_one(
                {"_id": obj_id},
                {"$set": {"historico_alteracoes": historico_reduzido}}
            )
            
            removidos = len(historico) - manter_ultimos
            logger.info(f"✓ Histórico limpo: {removidos} entradas removidas de {object_id}")
            return resultado.modified_count > 0
            
        except Exception as e:
            logger.error(f"Erro ao limpar histórico: {e}")
            return False
