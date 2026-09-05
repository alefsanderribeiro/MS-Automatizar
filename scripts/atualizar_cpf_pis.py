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


def atualizar_cpf_pis() -> None:
    """Atualiza CPF e PIS de funcionários no MongoDB a partir da planilha."""
    logger.info("Iniciando atualização de CPF/PIS a partir da planilha")

    dotenv_path = caminho_dotenv()
    dotenv.load_dotenv(dotenv_path)

    if not PLANILHA_PATH.exists():
        logger.error(f"Arquivo Excel não encontrado: {PLANILHA_PATH}")
        return

    service = FuncionarioService()
    if not service.disponivel:
        logger.error("MongoDB não disponível. Verifique a conexão.")
        return

    df = carregar_planilha(PLANILHA_PATH)
    nomes_excel_normalizados = carregar_nomes_excel(df)

    relatorio: List[Dict[str, Any]] = []
    atualizados = 0
    sem_alteracao = 0
    nao_encontrados = 0
    duplicados = 0

    for _, linha in df.iterrows():
        nome_excel = limpar_valor(linha[COLUNA_NOME])
        cpf_excel = limpar_valor(linha[COLUNA_CPF])
        pis_excel = limpar_valor(linha[COLUNA_PIS])

        if not nome_excel:
            relatorio.append(
                {
                    "nome_excel": nome_excel,
                    "cpf_excel": cpf_excel,
                    "pis_excel": pis_excel,
                    "status": "nome_vazio",
                    "motivo": "Campo NOME vazio"
                }
            )
            continue

        candidatos = service.buscar_todos_por_nome(nome_excel)

        if len(candidatos) == 0:
            nao_encontrados += 1
            relatorio.append(
                {
                    "nome_excel": nome_excel,
                    "cpf_excel": cpf_excel,
                    "pis_excel": pis_excel,
                    "status": "nao_encontrado",
                    "motivo": "Nenhum funcionário com nome_normalizado correspondente"
                }
            )
            continue

        if len(candidatos) > 1:
            duplicados += 1
            relatorio.append(
                {
                    "nome_excel": nome_excel,
                    "cpf_excel": cpf_excel,
                    "pis_excel": pis_excel,
                    "status": "duplicado",
                    "motivo": f"{len(candidatos)} funcionários com o mesmo nome_normalizado",
                    "ids_encontrados": [str(item["_id"]) for item in candidatos]
                }
            )
            continue

        funcionario = candidatos[0]
        alteracoes: Dict[str, Optional[str]] = {}

        if cpf_excel and cpf_excel != funcionario.get("cpf"):
            alteracoes["cpf"] = cpf_excel

        if pis_excel and pis_excel != funcionario.get("pis"):
            alteracoes["pis"] = pis_excel

        if not alteracoes:
            sem_alteracao += 1
            relatorio.append(
                {
                    "nome_excel": nome_excel,
                    "cpf_excel": cpf_excel,
                    "pis_excel": pis_excel,
                    "status": "sem_alteracao",
                    "motivo": "CPF/PIS já estão iguais aos dados do banco",
                    "id_funcionario": str(funcionario["_id"])
                }
            )
            continue

        atualizado = service.atualizar(str(funcionario["_id"]), alteracoes)
        if atualizado:
            atualizados += 1
            relatorio.append(
                {
                    "nome_excel": nome_excel,
                    "cpf_excel": cpf_excel,
                    "pis_excel": pis_excel,
                    "status": "atualizado",
                    "id_funcionario": str(funcionario["_id"]),
                    "alteracoes": alteracoes
                }
            )
        else:
            relatorio.append(
                {
                    "nome_excel": nome_excel,
                    "cpf_excel": cpf_excel,
                    "pis_excel": pis_excel,
                    "status": "falha_atualizacao",
                    "id_funcionario": str(funcionario["_id"]),
                    "alteracoes": alteracoes
                }
            )

    gerar_relatorio(relatorio, RELATORIO_PATH)

    logger.info("Resumo da execução:")
    logger.info(f"  atualizados: {atualizados}")
    logger.info(f"  sem alteração: {sem_alteracao}")
    logger.info(f"  não encontrados: {nao_encontrados}")
    logger.info(f"  duplicados: {duplicados}")

    
    gerar_relatorio_funcionarios_nao_na_planilha(
    nomes_excel_normalizados,
    service,
    Path(__file__).resolve().parent / "relatorio_funcionarios_mongodb_sem_excel.csv"
)   
    
    logger.info("Gerado a planilha de funcionários do MongoDB sem correspondência no Excel.")

if __name__ == "__main__":
    atualizar_cpf_pis()
    
