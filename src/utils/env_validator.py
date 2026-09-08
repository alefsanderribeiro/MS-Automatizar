"""
Validador de Variáveis de Ambiente

Este módulo valida se todas as variáveis de ambiente necessárias
estão configuradas antes de iniciar a aplicação.

Características:
- Validação de variáveis obrigatórias e opcionais
- Mensagens de erro claras
- Suporte a valores padrão
- Validação de formato (URLs, emails, etc.)
"""

import os
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import dotenv
from src.utils.dotenv_path import caminho_dotenv
from src.utils.logger_config_v2 import get_logger

logger = get_logger("env")


class NivelVariavel(Enum):
    """Nível de importância da variável"""
    OBRIGATORIA = "obrigatória"
    RECOMENDADA = "recomendada"
    OPCIONAL = "opcional"


@dataclass
class VariavelConfig:
    """Configuração de uma variável de ambiente"""
    nome: str
    nivel: NivelVariavel
    descricao: str
    valor_padrao: Optional[str] = None
    validador: Optional[callable] = None  # Função de validação
    exemplo: Optional[str] = None


# =============================================================================
# Validadores de formato
# =============================================================================

def validar_mongo_uri(valor: str) -> Tuple[bool, str]:
    """Valida formato de URI do MongoDB"""
    if not valor:
        return False, "URI vazia"
    
    # Padrões aceitos: mongodb://, mongodb+srv://
    if not (valor.startswith("mongodb://") or valor.startswith("mongodb+srv://")):
        return False, "URI deve começar com 'mongodb://' ou 'mongodb+srv://'"
    
    return True, "OK"


def validar_api_key(valor: str) -> Tuple[bool, str]:
    """Valida formato básico de API key"""
    if not valor:
        return False, "API key vazia"
    
    if len(valor) < 10:
        return False, "API key muito curta (mínimo 10 caracteres)"
    
    return True, "OK"


def validar_nome_banco(valor: str) -> Tuple[bool, str]:
    """Valida nome do banco de dados"""
    if not valor:
        return False, "Nome do banco vazio"
    
    # MongoDB não aceita alguns caracteres especiais
    if re.search(r'[/\\. "$*<>:|?]', valor):
        return False, "Nome do banco contém caracteres inválidos"
    
    return True, "OK"


# =============================================================================
# Configuração das variáveis
# =============================================================================

VARIAVEIS_AMBIENTE: List[VariavelConfig] = [
    # MongoDB
    VariavelConfig(
        nome="MONGO_URI",
        nivel=NivelVariavel.OBRIGATORIA,
        descricao="URI de conexão com MongoDB",
        valor_padrao="mongodb://localhost:27017",
        validador=validar_mongo_uri,
        exemplo="mongodb://localhost:27017"
    ),
    VariavelConfig(
        nome="MONGO_DATABASE_NAME",
        nivel=NivelVariavel.OBRIGATORIA,
        descricao="Nome do banco de dados MongoDB",
        valor_padrao="MS_Automatizar",
        validador=validar_nome_banco,
        exemplo="MS_Automatizar"
    ),
    VariavelConfig(
        nome="MONGO_MAX_POOL_SIZE",
        nivel=NivelVariavel.OPCIONAL,
        descricao="Tamanho máximo do pool de conexões",
        valor_padrao="10",
        exemplo="10"
    ),
    VariavelConfig(
        nome="MONGO_MIN_POOL_SIZE",
        nivel=NivelVariavel.OPCIONAL,
        descricao="Tamanho mínimo do pool de conexões",
        valor_padrao="2",
        exemplo="2"
    ),
    
    # APIs de IA
    VariavelConfig(
        nome="KEY_API_GEMINI",
        nivel=NivelVariavel.RECOMENDADA,
        descricao="Chave de API do Google Gemini",
        validador=validar_api_key,
        exemplo="AIza..."
    ),
    VariavelConfig(
        nome="KEY_API_MISTRAL",
        nivel=NivelVariavel.OPCIONAL,
        descricao="Chave de API do Mistral AI",
        validador=validar_api_key,
        exemplo="..."
    ),
]


# =============================================================================
# Classes de exceção
# =============================================================================

class AmbienteInvalidoError(Exception):
    """Exceção para ambiente inválido"""
    
    def __init__(self, mensagem: str, variaveis_faltando: List[str] = None):
        self.mensagem = mensagem
        self.variaveis_faltando = variaveis_faltando or []
        super().__init__(mensagem)


# =============================================================================
# Validador principal
# =============================================================================

class ValidadorAmbiente:
    """
    Validador de variáveis de ambiente.
    
    Uso:
        validador = ValidadorAmbiente()
        resultado = validador.validar()
        
        if not resultado["valido"]:
            print(resultado["erros"])
    """
    
    def __init__(self, variaveis: List[VariavelConfig] = None):
        """
        Inicializa o validador.
        
        Args:
            variaveis: Lista de variáveis para validar (usa padrão se não fornecido)
        """
        self.variaveis = variaveis or VARIAVEIS_AMBIENTE
        self._carregar_env()
    
    def _carregar_env(self) -> None:
        """Carrega variáveis do arquivo .env"""
        try:
            env_path = caminho_dotenv()
            dotenv.load_dotenv(env_path)
        except Exception as e:
            logger.warning(f"Erro ao carregar .env: {e}")
    
    def validar(self, strict: bool = False) -> Dict[str, Any]:
        """
        Valida todas as variáveis de ambiente.
        
        Args:
            strict: Se True, considera recomendadas como obrigatórias
        
        Returns:
            Dicionário com resultado da validação:
            {
                "valido": bool,
                "erros": List[str],
                "avisos": List[str],
                "variaveis": Dict[str, Dict]
            }
        """
        resultado = {
            "valido": True,
            "erros": [],
            "avisos": [],
            "variaveis": {}
        }
        
        for var_config in self.variaveis:
            var_resultado = self._validar_variavel(var_config)
            resultado["variaveis"][var_config.nome] = var_resultado
            
            if not var_resultado["presente"]:
                if var_config.nivel == NivelVariavel.OBRIGATORIA:
                    resultado["valido"] = False
                    resultado["erros"].append(
                        f"❌ {var_config.nome}: Variável obrigatória não definida. "
                        f"{var_config.descricao}"
                    )
                elif var_config.nivel == NivelVariavel.RECOMENDADA:
                    if strict:
                        resultado["valido"] = False
                        resultado["erros"].append(
                            f"❌ {var_config.nome}: Variável recomendada não definida. "
                            f"{var_config.descricao}"
                        )
                    else:
                        resultado["avisos"].append(
                            f"⚠️ {var_config.nome}: Variável recomendada não definida. "
                            f"Algumas funcionalidades podem não funcionar."
                        )
            
            elif not var_resultado["valido"]:
                if var_config.nivel == NivelVariavel.OBRIGATORIA:
                    resultado["valido"] = False
                    resultado["erros"].append(
                        f"❌ {var_config.nome}: {var_resultado['erro']}"
                    )
                else:
                    resultado["avisos"].append(
                        f"⚠️ {var_config.nome}: {var_resultado['erro']}"
                    )
        
        return resultado
    
    def _validar_variavel(self, var_config: VariavelConfig) -> Dict[str, Any]:
        """
        Valida uma variável individual.
        
        Args:
            var_config: Configuração da variável
        
        Returns:
            Dicionário com resultado da validação
        """
        valor = os.getenv(var_config.nome)
        
        resultado = {
            "presente": valor is not None and valor != "",
            "valido": True,
            "valor_atual": valor,
            "valor_padrao": var_config.valor_padrao,
            "usando_padrao": False,
            "erro": None
        }
        
        # Se não presente, verificar valor padrão
        if not resultado["presente"]:
            if var_config.valor_padrao:
                resultado["usando_padrao"] = True
                valor = var_config.valor_padrao
            else:
                return resultado
        
        # Validar formato se houver validador
        if var_config.validador and valor:
            valido, mensagem = var_config.validador(valor)
            resultado["valido"] = valido
            if not valido:
                resultado["erro"] = mensagem
        
        return resultado
    
    def obter_resumo(self) -> str:
        """
        Retorna um resumo legível da validação.
        
        Returns:
            String formatada com o resumo
        """
        resultado = self.validar()
        
        linhas = [
            "=" * 50,
            "📋 VALIDAÇÃO DE AMBIENTE",
            "=" * 50,
            ""
        ]
        
        # Erros
        if resultado["erros"]:
            linhas.append("🔴 ERROS:")
            for erro in resultado["erros"]:
                linhas.append(f"   {erro}")
            linhas.append("")
        
        # Avisos
        if resultado["avisos"]:
            linhas.append("🟡 AVISOS:")
            for aviso in resultado["avisos"]:
                linhas.append(f"   {aviso}")
            linhas.append("")
        
        # Resumo
        total = len(self.variaveis)
        presentes = sum(1 for v in resultado["variaveis"].values() if v["presente"])
        usando_padrao = sum(1 for v in resultado["variaveis"].values() if v["usando_padrao"])
        
        linhas.extend([
            "📊 RESUMO:",
            f"   Total de variáveis: {total}",
            f"   Configuradas: {presentes}",
            f"   Usando padrão: {usando_padrao}",
            f"   Faltando: {total - presentes - usando_padrao}",
            "",
            f"{'✅ Ambiente válido' if resultado['valido'] else '❌ Ambiente inválido'}",
            "=" * 50
        ])
        
        return "\n".join(linhas)


# =============================================================================
# Funções de conveniência
# =============================================================================

def validar_ambiente(strict: bool = False, exibir_resumo: bool = False) -> bool:
    """
    Valida o ambiente e retorna se está válido.
    
    Args:
        strict: Se True, considera recomendadas como obrigatórias
        exibir_resumo: Se True, exibe resumo no logger
    
    Returns:
        True se ambiente está válido
    """
    validador = ValidadorAmbiente()
    resultado = validador.validar(strict=strict)
    
    if exibir_resumo:
        resumo = validador.obter_resumo()
        if resultado["valido"]:
            logger.info(resumo)
        else:
            logger.error(resumo)
    
    # Log de erros e avisos
    for erro in resultado["erros"]:
        logger.error(erro)
    
    for aviso in resultado["avisos"]:
        logger.warning(aviso)
    
    return resultado["valido"]


def verificar_ambiente_startup() -> None:
    """
    Verifica o ambiente no startup da aplicação.
    Exibe avisos mas não bloqueia a execução.
    """
    validador = ValidadorAmbiente()
    resultado = validador.validar()
    
    if not resultado["valido"]:
        logger.warning(
            "⚠️ Algumas variáveis de ambiente obrigatórias não estão configuradas. "
            "Funcionalidades podem estar limitadas."
        )
        for erro in resultado["erros"]:
            logger.warning(erro)
    
    for aviso in resultado["avisos"]:
        logger.info(aviso)


def obter_variavel(nome: str, padrao: str = None) -> Optional[str]:
    """
    Obtém uma variável de ambiente com valor padrão.
    
    Args:
        nome: Nome da variável
        padrao: Valor padrão se não encontrada
    
    Returns:
        Valor da variável ou padrão
    """
    valor = os.getenv(nome)
    
    if valor is None or valor == "":
        # Buscar nas configurações padrão
        for var_config in VARIAVEIS_AMBIENTE:
            if var_config.nome == nome:
                return var_config.valor_padrao or padrao
        return padrao
    
    return valor
