"""
Utilitários de Retry com Logging
Decorator para retry automático com configuração via .env
"""

import time
import functools
from typing import Callable, Any, Optional, Type, Tuple
import dotenv

from src.utils.logger_config import logger
from src.utils.dotenv_path import caminho_dotenv


def obter_config_retry() -> Tuple[int, int]:
    """
    Obtém configuração de retry do .env
    
    Returns:
        Tupla (max_tentativas, delay_segundos)
    """
    try:
        env_path = caminho_dotenv()
        max_tentativas = int(dotenv.get_key(env_path, "ENVIO_MAX_TENTATIVAS") or "3")
        delay_segundos = int(dotenv.get_key(env_path, "ENVIO_RETRY_DELAY_SECONDS") or "5")
        return max_tentativas, delay_segundos
    except Exception as e:
        logger.warning(f"Erro ao ler config de retry do .env, usando padrões: {e}")
        return 3, 5


def retry_com_log(
    tentativas: Optional[int] = None,
    delay: Optional[int] = None,
    excecoes: Tuple[Type[Exception], ...] = (Exception,),
    msg_contexto: str = ""
) -> Callable:
    """
    Decorator para retry automático com logging
    
    Lê configuração do .env se não especificado:
    - ENVIO_MAX_TENTATIVAS (default: 3)
    - ENVIO_RETRY_DELAY_SECONDS (default: 5)
    
    Args:
        tentativas: Número máximo de tentativas (None = usar .env)
        delay: Segundos entre tentativas (None = usar .env)
        excecoes: Tupla de exceções para capturar
        msg_contexto: Contexto adicional para mensagens de log
    
    Returns:
        Decorator configurado
    
    Exemplo:
        @retry_com_log(msg_contexto="Envio de email")
        def enviar_email(destinatario, mensagem):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Obter configuração
            config_tentativas, config_delay = obter_config_retry()
            max_tent = tentativas if tentativas is not None else config_tentativas
            delay_seg = delay if delay is not None else config_delay
            
            contexto = f" ({msg_contexto})" if msg_contexto else ""
            nome_func = func.__name__
            
            ultima_excecao = None
            
            for tentativa in range(1, max_tent + 1):
                try:
                    logger.debug(f"Executando {nome_func}{contexto} - Tentativa {tentativa}/{max_tent}")
                    resultado = func(*args, **kwargs)
                    
                    if tentativa > 1:
                        logger.info(f"✓ {nome_func}{contexto} - Sucesso na tentativa {tentativa}")
                    
                    return resultado
                    
                except excecoes as e:
                    ultima_excecao = e
                    
                    if tentativa < max_tent:
                        logger.warning(
                            f"⚠ {nome_func}{contexto} - Tentativa {tentativa}/{max_tent} falhou: {str(e)}"
                        )
                        logger.info(f"  Aguardando {delay_seg}s antes da próxima tentativa...")
                        time.sleep(delay_seg)
                    else:
                        logger.error(
                            f"✗ {nome_func}{contexto} - Todas as {max_tent} tentativas falharam. "
                            f"Último erro: {str(e)}"
                        )
            
            # Propagar última exceção após esgotar tentativas
            raise ultima_excecao
        
        return wrapper
    return decorator


def retry_simples(
    func: Callable,
    tentativas: int = 3,
    delay: int = 5,
    excecoes: Tuple[Type[Exception], ...] = (Exception,),
    msg_contexto: str = ""
) -> Any:
    """
    Executa função com retry (versão não-decorator)
    
    Args:
        func: Função a ser executada (callable sem argumentos)
        tentativas: Número máximo de tentativas
        delay: Segundos entre tentativas
        excecoes: Tupla de exceções para capturar
        msg_contexto: Contexto adicional para mensagens de log
    
    Returns:
        Resultado da função
    
    Raises:
        Última exceção capturada após esgotar tentativas
    
    Exemplo:
        resultado = retry_simples(
            lambda: enviar_email(dest, msg),
            tentativas=3,
            msg_contexto="Envio para João"
        )
    """
    contexto = f" ({msg_contexto})" if msg_contexto else ""
    ultima_excecao = None
    
    for tentativa in range(1, tentativas + 1):
        try:
            logger.debug(f"Executando função{contexto} - Tentativa {tentativa}/{tentativas}")
            resultado = func()
            
            if tentativa > 1:
                logger.info(f"✓ Função{contexto} - Sucesso na tentativa {tentativa}")
            
            return resultado
            
        except excecoes as e:
            ultima_excecao = e
            
            if tentativa < tentativas:
                logger.warning(
                    f"⚠ Função{contexto} - Tentativa {tentativa}/{tentativas} falhou: {str(e)}"
                )
                logger.info(f"  Aguardando {delay}s antes da próxima tentativa...")
                time.sleep(delay)
            else:
                logger.error(
                    f"✗ Função{contexto} - Todas as {tentativas} tentativas falharam. "
                    f"Último erro: {str(e)}"
                )
    
    raise ultima_excecao


class RetryContextManager:
    """
    Context Manager para operações com retry
    
    Exemplo:
        with RetryContextManager(tentativas=3, msg_contexto="Upload arquivo") as ctx:
            for tentativa in ctx:
                try:
                    fazer_upload()
                    break  # Sucesso, sair do loop
                except Exception as e:
                    ctx.registrar_erro(e)
            
            if not ctx.sucesso:
                print(f"Falhou após {ctx.tentativas_realizadas} tentativas")
    """
    
    def __init__(
        self,
        tentativas: Optional[int] = None,
        delay: Optional[int] = None,
        msg_contexto: str = ""
    ):
        config_tentativas, config_delay = obter_config_retry()
        self.max_tentativas = tentativas if tentativas is not None else config_tentativas
        self.delay = delay if delay is not None else config_delay
        self.msg_contexto = msg_contexto
        
        self.tentativa_atual = 0
        self.sucesso = False
        self.ultimo_erro: Optional[Exception] = None
        self.erros: list[Exception] = []
    
    def __enter__(self) -> 'RetryContextManager':
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.sucesso and self.erros:
            contexto = f" ({self.msg_contexto})" if self.msg_contexto else ""
            logger.error(
                f"✗ Operação{contexto} - Falhou após {self.tentativa_atual} tentativas. "
                f"Último erro: {self.ultimo_erro}"
            )
        return False  # Não suprimir exceções
    
    def __iter__(self):
        return self
    
    def __next__(self) -> int:
        if self.sucesso:
            raise StopIteration
        
        if self.tentativa_atual >= self.max_tentativas:
            raise StopIteration
        
        # Aguardar delay entre tentativas (exceto primeira)
        if self.tentativa_atual > 0 and self.delay > 0:
            contexto = f" ({self.msg_contexto})" if self.msg_contexto else ""
            logger.info(f"  Aguardando {self.delay}s antes da próxima tentativa{contexto}...")
            time.sleep(self.delay)
        
        self.tentativa_atual += 1
        return self.tentativa_atual
    
    def registrar_erro(self, erro: Exception) -> None:
        """Registra um erro de tentativa"""
        self.ultimo_erro = erro
        self.erros.append(erro)
        
        contexto = f" ({self.msg_contexto})" if self.msg_contexto else ""
        logger.warning(
            f"⚠ Operação{contexto} - Tentativa {self.tentativa_atual}/{self.max_tentativas} "
            f"falhou: {str(erro)}"
        )
    
    def marcar_sucesso(self) -> None:
        """Marca operação como bem sucedida"""
        self.sucesso = True
        
        if self.tentativa_atual > 1:
            contexto = f" ({self.msg_contexto})" if self.msg_contexto else ""
            logger.info(f"✓ Operação{contexto} - Sucesso na tentativa {self.tentativa_atual}")
    
    @property
    def tentativas_realizadas(self) -> int:
        """Número de tentativas realizadas"""
        return self.tentativa_atual
    
    @property
    def pode_continuar(self) -> bool:
        """Verifica se ainda pode tentar"""
        return not self.sucesso and self.tentativa_atual < self.max_tentativas
