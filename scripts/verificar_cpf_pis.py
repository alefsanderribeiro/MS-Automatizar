"""
Script para atualizar CPF e PIS no MongoDB usando a planilha de cadastro.

A planilha usada é:
    src/data/models/Cadastro dos Empregados.xlsx

O script busca funcionários pelo campo `nome_normalizado` no MongoDB.
Se encontrar exatamente um documento, atualiza `cpf` e `pis`.
Caso contrário, salva um relatório para revisão manual.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import dotenv
import pandas as pd

# adicionar caminho do projeto para garantir imports locais
sys.path.insert(0, ".")

from src.services.funcionario_service import FuncionarioService
from src.utils.dotenv_path import caminho_dotenv
from src.utils.logger_config import logger


PLANILHA_PATH = Path(__file__).resolve().parent.parent / "src" / "data" / "models" / "Cadastro dos Empregados.xlsx"
RELATORIO_PATH = Path(__file__).resolve().parent / "relatorio_atualizacao_cpf_pis.csv"
COLUNA_NOME = "NOME"
COLUNA_CPF = "CPF"
COLUNA_PIS = "PIS"


def normalizar_texto(texto: Optional[str]) -> str:
    """Normaliza texto para comparação de nomes."""
    if texto is None:
        return ""
    import unicodedata

    valor = str(texto).strip()
    nfkd = unicodedata.normalize("NFKD", valor)
    sem_acentos = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return sem_acentos.lower()


def limpar_valor(texto: Optional[str]) -> Optional[str]:
    """Limpa valor string e retorna None quando vazio."""
    if texto is None:
        return None
    valor = str(texto).strip()
    return valor if valor else None


def carregar_planilha(path: Path) -> pd.DataFrame:
    """Carrega a planilha de cadastro e valida as colunas obrigatórias."""
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    df = pd.read_excel(path, dtype=str, keep_default_na=False)
    colunas_obrigatorias = {COLUNA_NOME, COLUNA_CPF, COLUNA_PIS}

    if not colunas_obrigatorias.issubset(set(df.columns)):
        raise ValueError(
            f"Planilha deve conter as colunas: {', '.join(colunas_obrigatorias)}"
        )

    return df

def carregar_nomes_excel(df: pd.DataFrame) -> set[str]:
    """Retorna conjunto de nomes normalizados presentes na planilha."""
    return {normalizar_texto(nome) for nome in df[COLUNA_NOME].astype(str).tolist() if nome.strip()}


def gerar_relatorio_funcionarios_nao_na_planilha(
    nomes_excel_normalizados: set[str],
    service: FuncionarioService,
    caminho: Path
) -> None:
    """Gera relatório de funcionários do MongoDB que não existem na planilha."""
    itens: list[dict[str, Any]] = []

    cursor = service.colecao.find({}, {"nome": 1, "nome_normalizado": 1, "cpf": 1, "pis": 1, "status": 1, "status_cadastro": 1})
    for doc in cursor:
        nome_normalizado = doc.get("nome_normalizado", "")
        if nome_normalizado not in nomes_excel_normalizados:
            itens.append({
                "id_funcionario": str(doc.get("_id")),
                "nome": doc.get("nome"),
                "nome_normalizado": nome_normalizado,
                "cpf": doc.get("cpf"),
                "pis": doc.get("pis"),
                "status": doc.get("status"),
                "status_cadastro": doc.get("status_cadastro"),
            })

    if itens:
        pd.DataFrame(itens).to_csv(caminho, index=False, encoding="utf-8-sig")
        logger.info(f"Relatório de funcionários do MongoDB sem correspondência no Excel gerado em: {caminho}")
    else:
        logger.info("Nenhum funcionário do MongoDB ficou fora da planilha Excel.")

def gerar_relatorio(resultados: List[Dict[str, Any]], caminho: Path) -> None:
    """Salva relatório CSV com as linhas não atualizadas ou com problemas."""
    relatorio_df = pd.DataFrame(resultados)
    relatorio_df.to_csv(caminho, index=False, encoding="utf-8-sig")
    logger.info(f"Relatório gerado em: {caminho}")


def verificar_cpf_pis() -> None:
    """Verifica CPF e PIS de funcionários no MongoDB."""
    logger.info("Iniciando verificação de CPF/PIS")

    dotenv_path = caminho_dotenv()
    dotenv.load_dotenv(dotenv_path)

    if not PLANILHA_PATH.exists():
        logger.error(f"Arquivo Excel não encontrado: {PLANILHA_PATH}")
        return

    service = FuncionarioService()
    if not service.disponivel:
        logger.error("MongoDB não disponível. Verifique a conexão.")
        return

    todos = service.listar_todos(limit=10000)
    
    # aplica um filtro onde o CPF e o PIS são vazios
    for func in todos.get("dados", []):
        
        if func["cpf"] or func["pis"] :
            continue
        else:            
            print(func["nome"])        

        

        #pis = func["pis"] 
        #print(pis)
    
    #{'_id': ObjectId('69251cb31e46d8b5d64afd19'), 'nome': 'CLICIENE ALVES DOS SANTOS', 'pis': '16447059374', 'cpf': '02431320260', 'lotacao': 'TCE', 'contrato': 'CLT', 'empresas_ids': [ObjectId('6924fbe1b032922775364409')], 'data_nascimento': datetime.datetime(1991, 10, 18, 0, 0), 'data_admissao': datetime.datetime(2024, 3, 1, 0, 0), 'data_demissao': None, 'status': 'ativo', 'nome_normalizado': 'cliciene alves dos santos', 'criado_em': datetime.datetime(2025, 11, 25, 3, 4, 19, 192000), 'atualizado_em': datetime.datetime(2026, 4, 15, 18, 25, 2, 284000), 'versao': 10, 'historico_alteracoes': [{'timestamp': datetime.datetime(2025, 11, 25, 3, 4, 19, 192000), 'acao': 'Funcionário criado automaticamente durante geração de folha de ponto', 'versao_anterior': 1, 'versao_nova': 2, 'detalhes': {'origem': 'planilha_excel', 'id_funcionario_planilha': 577, 'etapa': 'auto_cadastro'}}, {'timestamp': datetime.datetime(2025, 11, 25, 12, 42, 45, 856000), 'acao': 'Migração de strings para ObjectIds', 'detalhes': {'contrato_str': 'TCE LIMPEZA', 'horario_str': 'Segunda à Sexta-feira: 07:00 às 17:00 Intervalo: 12:00 às 13:00', 'funcao_str': 'SERVENTE DE LIMPEZA', 'contrato_id': '6925a3fef0d6b51ffd30ea56', 'horario_id': '6925a3fef0d6b51ffd30ea67', 'funcao_id': '6925a3fef0d6b51ffd30ea88'}}, {'timestamp': datetime.datetime(2025, 11, 28, 3, 3, 50, 902000), 'acao': 'migracao_diretorio', 'origem': 'migracao', 'script': 'migrar_diretorio_interno.py', 'detalhes': {'campo_anterior': 'diretorio_interno', 'campo_novo': 'diretorio_id', 'valor_anterior': '01. MS SERVIÇOS\\TCE - PVH', 'valor_novo': '69291116813b3df7b5335dbc', 'versao_anterior': 2}}, {'timestamp': datetime.datetime(2025, 11, 28, 3, 31, 23, 473000), 'acao': 'reversao_migracao', 'origem': 'migracao_reversao', 'script': 'reverter_e_recriar_diretorios.py', 'detalhes': {'motivo': 'Reversão da migração de diretório para recriar com estrutura correta'}}, {'timestamp': datetime.datetime(2025, 11, 28, 3, 43, 26, 584000), 'acao': 'migracao_diretorio', 'origem': 'migracao', 'script': 'migrar_diretorio_interno.py', 'detalhes': {'campo_anterior': 'diretorio_interno', 'campo_novo': 'diretorio_id', 'valor_anterior': '01. MS SERVIÇOS\\TCE - PVH', 'valor_novo': '69291a5d5a81b5eba95c48c4', 'versao_anterior': 3}}, {'timestamp': datetime.datetime(2026, 1, 12, 17, 26, 44, 46000), 'acao': 'Dados atualizados via interface de linha de comando', 'origem': 'interface_cli', 'detalhes': {'campos_alterados': ['data_nascimento'], 'valores_anteriores': {'data_nascimento': None}, 'valores_novos': {'data_nascimento': '1991-10-18T00:00:00'}}}, {'timestamp': datetime.datetime(2026, 1, 12, 17, 28, 5, 12000), 'acao': 'Dados atualizados via interface de linha de comando', 'origem': 'interface_cli', 'detalhes': {'campos_alterados': ['contrato_empresa_id'], 'valores_anteriores': {'contrato_empresa_id': '6925a3fef0d6b51ffd30ea56'}, 'valores_novos': {'contrato_empresa_id': '6925a3fef0d6b51ffd30ea56'}}}, {'timestamp': datetime.datetime(2026, 1, 12, 17, 28, 17, 586000), 'acao': 'Dados atualizados via interface de linha de comando', 'origem': 'interface_cli', 'detalhes': {'campos_alterados': ['lotacao'], 'valores_anteriores': {'lotacao': 'TCE - ESCOLA SUPERIOR DE CONTAS'}, 'valores_novos': {'lotacao': 'TCE'}}}, {'timestamp': datetime.datetime(2026, 1, 12, 17, 29, 10, 466000), 'acao': 'Dados atualizados via interface de linha de comando', 'origem': 'interface_cli', 'detalhes': {'campos_alterados': ['lotacao'], 'valores_anteriores': {'lotacao': 'TCE'}, 'valores_novos': {'lotacao': 'TCE - ESCOLA SUPERIOR DE CONTAS'}}}, {'timestamp': datetime.datetime(2026, 1, 12, 17, 42, 44, 473000), 'acao': 'Dados atualizados via interface de linha de comando', 'origem': 'interface_cli', 'detalhes': {'campos_alterados': ['lotacao'], 'valores_anteriores': {'lotacao': 'TCE - ESCOLA SUPERIOR DE CONTAS'}, 'valores_novos': {'lotacao': 'TCE'}}}, {'timestamp': datetime.datetime(2026, 4, 15, 18, 25, 2, 284000), 'acao': 'Dados atualizados via interface de linha de comando', 'origem': 'interface_cli', 'detalhes': {'campos_alterados': ['cpf', 'pis'], 'valores_anteriores': {'cpf': '', 'pis': None}, 'valores_novos': {'cpf': '02431320260', 'pis': '16447059374'}}}], 'diretorio_interno': '01. MS SERVIÇOS\\TCE - PVH', 'contrato_empresa_id': ObjectId('6925a3fef0d6b51ffd30ea56'), 'funcao_id': ObjectId('6925a3fef0d6b51ffd30ea88'), 'horario_id': ObjectId('6925a3fef0d6b51ffd30ea67'), 'diretorio_id': ObjectId('69291a5d5a81b5eba95c48c4'), 'status_cadastro': 'incompleto'}], 'total': 556, 'skip': 0, 'limit': 100, 'paginas': 6, 'pagina_atual': 1}
    
    #print(todos)

    
    #gerar_relatorio_funcionarios_nao_na_planilha(
    #nomes_excel_normalizados,
    #service,
    #Path(__file__).resolve().parent / "relatorio_funcionarios_mongodb_sem_excel.csv"
#)   
    
    #logger.info("Gerado a planilha de funcionários do MongoDB sem correspondência no Excel.")

if __name__ == "__main__":
    verificar_cpf_pis()
    
