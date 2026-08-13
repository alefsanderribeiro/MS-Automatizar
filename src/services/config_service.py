"""
Serviço de Configurações

Este módulo gerencia a leitura e escrita de configurações no arquivo .env
e fornece uma interface centralizada para todas as configurações do sistema.
"""

import os
from typing import Optional, Dict, Any, List
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

import dotenv
from src.utils.dotenv_path import caminho_dotenv
from src.utils.logger_config import logger


class ModoOperacao(Enum):
    """Modos de operação do sistema"""
    MONGODB_ONLY = "mongodb"
    EXCEL_ONLY = "excel"
    AMBOS = "ambos"


class TipoConfiguracao(Enum):
    """Tipos de configuração"""
    MONGODB = "mongodb"
    API = "api"
    SISTEMA = "sistema"
    ONEDRIVE = "onedrive"


@dataclass
class ConfigItem:
    """Item de configuração"""
    chave: str
    valor: Optional[str]
    tipo: TipoConfiguracao
    descricao: str
    obrigatorio: bool = False
    valor_padrao: Optional[str] = None
    sensivel: bool = False  # Oculta o valor na exibição


class ConfigService:
    """
    Serviço centralizado para gerenciar configurações do sistema.
    
    Permite ler e escrever configurações no arquivo .env,
    além de fornecer validação e valores padrão.
    """
    
    # Definição de todas as configurações do sistema
    CONFIGS_DISPONIVEIS: Dict[str, ConfigItem] = {
        # MongoDB
        "MONGO_URI": ConfigItem(
            chave="MONGO_URI",
            valor=None,
            tipo=TipoConfiguracao.MONGODB,
            descricao="URI de conexão com MongoDB",
            obrigatorio=True,
            valor_padrao="mongodb://localhost:27017",
            sensivel=True
        ),
        "MONGO_DATABASE_NAME": ConfigItem(
            chave="MONGO_DATABASE_NAME",
            valor=None,
            tipo=TipoConfiguracao.MONGODB,
            descricao="Nome do banco de dados MongoDB",
            obrigatorio=True,
            valor_padrao="MS_Automatizar"
        ),
        "MONGO_MAX_POOL_SIZE": ConfigItem(
            chave="MONGO_MAX_POOL_SIZE",
            valor=None,
            tipo=TipoConfiguracao.MONGODB,
            descricao="Tamanho máximo do pool de conexões",
            valor_padrao="100"
        ),
        "MONGO_MIN_POOL_SIZE": ConfigItem(
            chave="MONGO_MIN_POOL_SIZE",
            valor=None,
            tipo=TipoConfiguracao.MONGODB,
            descricao="Tamanho mínimo do pool de conexões",
            valor_padrao="10"
        ),
        
        # APIs de IA
        "KEY_API_GEMINI": ConfigItem(
            chave="KEY_API_GEMINI",
            valor=None,
            tipo=TipoConfiguracao.API,
            descricao="Chave de API do Google Gemini (para análise de PDFs)",
            sensivel=True
        ),
        "KEY_API_MISTRAL": ConfigItem(
            chave="KEY_API_MISTRAL",
            valor=None,
            tipo=TipoConfiguracao.API,
            descricao="Chave de API do Mistral AI (alternativa)",
            sensivel=True
        ),
        
        # Sistema
        "MODO_OPERACAO": ConfigItem(
            chave="MODO_OPERACAO",
            valor=None,
            tipo=TipoConfiguracao.SISTEMA,
            descricao="Modo de operação: mongodb, excel ou ambos",
            valor_padrao="mongodb"
        ),
        "LOG_LEVEL": ConfigItem(
            chave="LOG_LEVEL",
            valor=None,
            tipo=TipoConfiguracao.SISTEMA,
            descricao="Nível de log: DEBUG, INFO, WARNING, ERROR",
            valor_padrao="INFO"
        ),
        "DIRETORIO_SAIDA": ConfigItem(
            chave="DIRETORIO_SAIDA",
            valor=None,
            tipo=TipoConfiguracao.SISTEMA,
            descricao="Diretório padrão para salvar arquivos gerados"
        ),
        
        # OneDrive
        "ONEDRIVE_URL_DADOS": ConfigItem(
            chave="ONEDRIVE_URL_DADOS",
            valor=None,
            tipo=TipoConfiguracao.ONEDRIVE,
            descricao="URL da planilha de dados no OneDrive"
        ),
        "ONEDRIVE_URL_MODELOS": ConfigItem(
            chave="ONEDRIVE_URL_MODELOS",
            valor=None,
            tipo=TipoConfiguracao.ONEDRIVE,
            descricao="URL da planilha de modelos no OneDrive"
        ),
    }
    
    def __init__(self):
        """Inicializa o serviço de configurações"""
        self.env_path = caminho_dotenv()
        self._carregar_configs()
    
    def _carregar_configs(self) -> None:
        """Carrega todas as configurações do arquivo .env"""
        dotenv.load_dotenv(self.env_path)
        
        for chave, config in self.CONFIGS_DISPONIVEIS.items():
            valor = os.getenv(chave)
            config.valor = valor
    
    def obter(self, chave: str) -> Optional[str]:
        """
        Obtém o valor de uma configuração.
        
        Args:
            chave: Nome da configuração
            
        Returns:
            Valor da configuração ou valor padrão se não definido
        """
        if chave in self.CONFIGS_DISPONIVEIS:
            config = self.CONFIGS_DISPONIVEIS[chave]
            return config.valor or config.valor_padrao
        return os.getenv(chave)
    
    def definir(self, chave: str, valor: str) -> bool:
        """
        Define o valor de uma configuração e salva no .env
        
        Args:
            chave: Nome da configuração
            valor: Novo valor
            
        Returns:
            True se salvou com sucesso
        """
        try:
            # Atualizar no arquivo .env
            dotenv.set_key(self.env_path, chave, valor)
            
            # Atualizar em memória
            if chave in self.CONFIGS_DISPONIVEIS:
                self.CONFIGS_DISPONIVEIS[chave].valor = valor
            
            # Atualizar no ambiente
            os.environ[chave] = valor
            
            # Se for LOG_LEVEL, atualizar o logger em tempo real
            if chave == "LOG_LEVEL":
                logger.atualizar_nivel(valor)
            
            logger.info(f"✓ Configuração '{chave}' atualizada")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao salvar configuração '{chave}': {e}")
            return False
    
    def remover(self, chave: str) -> bool:
        """
        Remove uma configuração do .env
        
        Args:
            chave: Nome da configuração
            
        Returns:
            True se removeu com sucesso
        """
        try:
            dotenv.unset_key(self.env_path, chave)
            
            if chave in self.CONFIGS_DISPONIVEIS:
                self.CONFIGS_DISPONIVEIS[chave].valor = None
            
            if chave in os.environ:
                del os.environ[chave]
            
            logger.info(f"✓ Configuração '{chave}' removida")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao remover configuração '{chave}': {e}")
            return False
    
    def listar_por_tipo(self, tipo: TipoConfiguracao) -> List[ConfigItem]:
        """
        Lista todas as configurações de um tipo específico.
        
        Args:
            tipo: Tipo de configuração
            
        Returns:
            Lista de configurações do tipo especificado
        """
        return [
            config for config in self.CONFIGS_DISPONIVEIS.values()
            if config.tipo == tipo
        ]
    
    def listar_todas(self) -> Dict[str, ConfigItem]:
        """
        Retorna todas as configurações.
        
        Returns:
            Dicionário com todas as configurações
        """
        # Recarregar para garantir valores atualizados
        self._carregar_configs()
        return self.CONFIGS_DISPONIVEIS
    
    def validar(self) -> Dict[str, Any]:
        """
        Valida todas as configurações.
        
        Returns:
            Dicionário com resultado da validação:
            {
                "valido": bool,
                "erros": List[str],
                "avisos": List[str]
            }
        """
        self._carregar_configs()
        
        resultado = {
            "valido": True,
            "erros": [],
            "avisos": []
        }
        
        for chave, config in self.CONFIGS_DISPONIVEIS.items():
            valor = config.valor or config.valor_padrao
            
            if config.obrigatorio and not valor:
                resultado["valido"] = False
                resultado["erros"].append(
                    f"❌ {chave}: Configuração obrigatória não definida"
                )
            elif not config.obrigatorio and not valor:
                if config.tipo in [TipoConfiguracao.API]:
                    resultado["avisos"].append(
                        f"⚠️ {chave}: Não configurado - {config.descricao}"
                    )
        
        return resultado
    
    def obter_modo_operacao(self) -> ModoOperacao:
        """
        Obtém o modo de operação atual do sistema.
        
        Returns:
            ModoOperacao: Modo de operação configurado
        """
        modo = self.obter("MODO_OPERACAO") or "mongodb"
        try:
            return ModoOperacao(modo.lower())
        except ValueError:
            return ModoOperacao.MONGODB_ONLY
    
    def usar_mongodb(self) -> bool:
        """Verifica se deve usar MongoDB"""
        modo = self.obter_modo_operacao()
        return modo in [ModoOperacao.MONGODB_ONLY, ModoOperacao.AMBOS]
    
    def usar_excel(self) -> bool:
        """Verifica se deve usar Excel"""
        modo = self.obter_modo_operacao()
        return modo in [ModoOperacao.EXCEL_ONLY, ModoOperacao.AMBOS]
    
    def obter_mongo_uri(self) -> str:
        """Obtém a URI do MongoDB"""
        return self.obter("MONGO_URI") or "mongodb://localhost:27017"
    
    def obter_mongo_database(self) -> str:
        """Obtém o nome do banco de dados"""
        return self.obter("MONGO_DATABASE_NAME") or "MS_Automatizar"
    
    def criar_arquivo_env_se_necessario(self) -> bool:
        """
        Cria arquivo .env com valores padrão se não existir.
        
        Returns:
            True se criou arquivo, False se já existia
        """
        if os.path.exists(self.env_path):
            return False
        
        try:
            conteudo = [
                "# Configurações do MS-Automatizar",
                "# Gerado automaticamente",
                "",
                "# ==================== MongoDB ====================",
                "MONGO_URI=mongodb://localhost:27017",
                "MONGO_DATABASE_NAME=MS_Automatizar",
                "MONGO_MAX_POOL_SIZE=100",
                "MONGO_MIN_POOL_SIZE=10",
                "",
                "# ==================== APIs de IA ====================",
                "KEY_API_GEMINI=",
                "KEY_API_MISTRAL=",
                "",
                "# ==================== Sistema ====================",
                "# Modo de operação: mongodb, excel ou ambos",
                "MODO_OPERACAO=mongodb",
                "LOG_LEVEL=INFO",
                "DIRETORIO_SAIDA=",
                "",
                "# ==================== OneDrive ====================",
                "ONEDRIVE_URL_DADOS=",
                "ONEDRIVE_URL_MODELOS=",
                ""
            ]
            
            with open(self.env_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(conteudo))
            
            logger.info(f"✓ Arquivo .env criado em: {self.env_path}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao criar arquivo .env: {e}")
            return False
    
    def exibir_valor(self, config: ConfigItem) -> str:
        """
        Retorna o valor formatado para exibição.
        Oculta valores sensíveis.
        
        Args:
            config: Item de configuração
            
        Returns:
            Valor formatado para exibição
        """
        valor = config.valor
        
        if not valor:
            if config.valor_padrao:
                return f"(padrão: {config.valor_padrao})"
            return "(não configurado)"
        
        if config.sensivel:
            if len(valor) > 8:
                return f"{valor[:4]}...{valor[-4:]}"
            return "****"
        
        return valor


# Instância global para uso em todo o sistema
_config_service: Optional[ConfigService] = None


def obter_config_service() -> ConfigService:
    """
    Obtém a instância global do serviço de configurações.
    
    Returns:
        Instância do ConfigService
    """
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service


def obter_config(chave: str) -> Optional[str]:
    """
    Função de conveniência para obter uma configuração.
    
    Args:
        chave: Nome da configuração
        
    Returns:
        Valor da configuração
    """
    return obter_config_service().obter(chave)


def definir_config(chave: str, valor: str) -> bool:
    """
    Função de conveniência para definir uma configuração.
    
    Args:
        chave: Nome da configuração
        valor: Novo valor
        
    Returns:
        True se salvou com sucesso
    """
    return obter_config_service().definir(chave, valor)
