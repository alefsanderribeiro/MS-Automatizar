"""
Configurações de URLs para acesso às planilhas no OneDrive/Microsoft 365
"""

# URLs dos arquivos Excel compartilhados
URLS_ONEDRIVE = {
    "dados": "https://1drv.ms/x/s!SEU_SHARE_TOKEN",  # Coloque a URL do arquivo Excel compartilhado
    "modelos": None  # Colocar aqui a URL do arquivo de modelos (opcional)
}

# Exemplo de uso:
# URLS_ONEDRIVE = {
#     "dados": "https://1drv.ms/x/s!Exemplo123456",
#     "modelos": "https://empresa-my.sharepoint.com/:x:/g/personal/usuario/arquivo.xlsx"
# }

# Configurações de timeout
TIMEOUT_CONEXAO = 30  # segundos - mantido em 30 para downloads completos

# Configuração padrão
USAR_ONLINE_POR_PADRAO = True  # Sempre usar online por padrão
