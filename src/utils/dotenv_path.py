import dotenv as dt
from pathlib import Path

def caminho_dotenv() -> str: 
    "Retorna o caminho do arquivo .env no projeto"
    BASE_PATH = Path(__file__).resolve().parent.parent.parent
    a = BASE_PATH / ".env"
    a.touch()
    caminho = dt.find_dotenv()
    return caminho


def dotenv():
    
    return dt