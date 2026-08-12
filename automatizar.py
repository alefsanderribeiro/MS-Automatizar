import sys
import os

# Adiciona o diretório atual ao path para garantir que os imports funcionem
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.comandos.main import start_command

def main():
    try:
        start_command()
    except Exception as e:
        print(f"Erro ao executar comando: {e}")
        input("Pressione Enter para sair...")
        return

# TODO: Adicionar funções para poder criar empresas, funcionários e folhas de ponto via linha de comando ou no menu.
# TODO: Parar de usar a planilha excel para os dados e usar somente o banco de dados mongodb.
# TODO: Implementar testes automatizados para os novos serviços e utilitários adicionados.
# TODO: Documentar as novas funcionalidades no README e criar exemplos de uso.
# TODO: Adicionar logging para monitorar operações críticas, especialmente interações com o MongoDB.


if __name__ == "__main__":
    print("Iniciando MS-Automatizar...")
    main()