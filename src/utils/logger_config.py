import logging
import os
import re
from datetime import datetime
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Mapeamento de níveis de log
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}

# Remover emojis para compatibilidade com PowerShell
def remover_emojis(texto: str) -> str:
    """Remove emojis da mensagem para evitar problemas de encoding no PowerShell"""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"  # dingbats
        "\u3030"
        "]+", re.UNICODE)
    return emoji_pattern.sub(r'', texto)

class EmojiRemovalFilter(logging.Filter):
    """Filtro de logging que remove emojis"""
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = remover_emojis(str(record.msg))
        if isinstance(record.args, dict):
            for key, val in record.args.items():
                record.args[key] = remover_emojis(str(val))
        elif isinstance(record.args, tuple):
            record.args = tuple(remover_emojis(str(arg)) for arg in record.args)
        return True


def _obter_nivel_log() -> int:
    """Obtém o nível de log da variável de ambiente"""
    nivel_str = os.getenv("LOG_LEVEL", "INFO").upper().strip().strip('"').strip("'")
    return LOG_LEVELS.get(nivel_str, logging.INFO)


class Logger:
    def __init__(self):
        # Criar diretório de logs se não existir
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
        os.makedirs(log_dir, exist_ok=True)

        # Configurar nome do arquivo de log com data
        log_file = os.path.join(log_dir, f'app_{datetime.now().strftime("%d-%m-%Y")}.log')

        # Configurar o logger
        self.logger = logging.getLogger('APP')
        self.logger.setLevel(logging.DEBUG)  # Logger aceita tudo, handlers filtram

        # Evitar duplicação de handlers
        if not self.logger.handlers:
            # Configurar formato do log
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            
            # Criar filtro para remover emojis
            emoji_filter = EmojiRemovalFilter()

            # Handler para arquivo (sempre DEBUG para ter histórico completo)
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            file_handler.addFilter(emoji_filter)
            file_handler.set_name('file_handler')

            # Handler para console (respeita configuração do usuário)
            console_handler = logging.StreamHandler()
            console_handler.setLevel(_obter_nivel_log())  # Lê do .env
            console_handler.setFormatter(formatter)
            console_handler.addFilter(emoji_filter)
            console_handler.set_name('console_handler')

            # Adicionar handlers ao logger
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    def atualizar_nivel(self, nivel: str | None = None):
        """
        Atualiza o nível de log do console handler.
        Se nivel não for fornecido, recarrega do .env
        """
        if nivel is None:
            # Recarregar do .env
            load_dotenv(override=True)
            nivel_int = _obter_nivel_log()
        else:
            nivel_int = LOG_LEVELS.get(nivel.upper(), logging.INFO)
        
        # Encontrar e atualizar o console handler
        for handler in self.logger.handlers:
            if handler.get_name() == 'console_handler':
                handler.setLevel(nivel_int)
                break

    def debug(self, message: str):
        self.logger.debug(message)

    def info(self, message: str):
        self.logger.info(message)

    def warning(self, message: str):
        self.logger.warning(message)

    def error(self, message: str):
        self.logger.error(message)

    def critical(self, message: str):
        self.logger.critical(message)

# Criar instância global do logger
logger = Logger()
