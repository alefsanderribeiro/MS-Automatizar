"""
Script de Migracao: Planilha de Contatos -> MongoDB
Responsabilidades:
- Ler planilha Excel de contatos
- Para cada linha, criar documento na colecao contatos_folha_ponto
- Salvar TODOS os campos necessarios para o envio de folhas de ponto
"""

import os
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Adicionar o diretorio do projeto ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.dotenv_path import caminho_dotenv
from src.utils.logger_config_v2 import get_logger

logger = get_logger("migracao_contatos")

# Valores que significam "Sim" (mesmo do PlanilhaContatosService)
VALORES_SIM = ["S", "SIM", "YES", "Y", "1", "TRUE", "X"]


def valor_booleano(valor) -> bool:
    """Converte valor para booleano"""
    if pd.isna(valor) or valor is None:
        return False
    return str(valor).strip().upper() in VALORES_SIM


def parsear_lista(valor) -> list:
    """Parseia valor separado por , ou ; em lista"""
    if pd.isna(valor) or not valor:
        return []

    texto = str(valor).strip()

    if ";" in texto:
        itens = texto.split(";")
    else:
        itens = texto.split(",")

    return [item.strip() for item in itens if item.strip()]


def migrar(planilha_path: str, dry_run: bool = False, sobrescrever: bool = False):
    """
    Migra contatos da planilha para o MongoDB
    
    Args:
        planilha_path: Caminho da planilha Excel
        dry_run: Se True, apenas mostra o que seria feito sem salvar
        sobrescrever: Se True, sobrescreve contatos existentes com mesmo ID
    """
    logger.info(f"Iniciando migracao de planilha: {planilha_path}")

    # Verificar se planilha existe
    if not os.path.exists(planilha_path):
        logger.error(f"Planilha nao encontrada: {planilha_path}")
        return False

    try:
        # Conectar ao MongoDB
        from pymongo import MongoClient
        from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

        env_path = caminho_dotenv()
        load_dotenv(env_path, override=True)

        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DATABASE_NAME", "MS_Automatizar")

        cliente = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        cliente.admin.command('ping')  # Testar conexao

        db = cliente[db_name]
        colecao = db["contatos_folha_ponto"]

        # Criar indice unico por funcionario_id
        colecao.create_index("funcionario_id", unique=True, sparse=True)

        logger.info(f"Conectado ao MongoDB: {db_name}")

        # Carregar planilha
        df = pd.read_excel(planilha_path, sheet_name=0, dtype=str)
        df.columns = df.columns.str.strip().str.upper()
        df = df.fillna("")

        logger.info(f"Planilha carregada: {len(df)} linhas")

        # Verificar colunas
        colunas_necessarias = [
            "ID", "NOME COMPLETO", "EMAIL", "TELEFONE", "GRUPO WHATSAPP",
            "ENVIAR EMAIL", "ENVIAR WHATSAPP", "ENVIAR GRUPO WHATSAPP",
            "ENVIAR IMPRESSO", "EMPRESA", "LOCAL - CONTRATO - POLO",
            "DIRETORIO GERAL", "DIRETORIO ESPECIFICO"
        ]

        colunas_faltando = [col for col in colunas_necessarias if col not in df.columns]

        if colunas_faltando:
            logger.error(f"Colunas faltando na planilha: {', '.join(colunas_faltando)}")
            return False

        # Contadores
        total = len(df)
        migrados = 0
        erros = 0
        pulados = 0

        logger.info(f"Processando {total} contatos...")

        for idx, row in df.iterrows():
            try:
                # ID do contato (usar como chave)
                contato_id = str(row.get("ID", "")).strip()

                if not contato_id:
                    logger.warning(f"Linha {idx + 2}: Sem ID, pulando")
                    pulados += 1
                    continue

                # Verificar se ja existe (se nao sobrescrever)
                if not sobrescrever:
                    existente = colecao.find_one({"funcionario_id": contato_id})
                    if existente:
                        logger.debug(f"Contato {contato_id} ja existe, pulando")
                        pulados += 1
                        continue

                # Montar documento
                documento = {
                    "funcionario_id": contato_id,
                    "nome": str(row.get("NOME COMPLETO", "")).strip(),
                    "email": str(row.get("EMAIL", "")).strip(),
                    "telefone": str(row.get("TELEFONE", "")).strip(),
                    "grupo_whatsapp": str(row.get("GRUPO WHATSAPP", "")).strip(),

                    # Flags de envio
                    "enviar_email": valor_booleano(row.get("ENVIAR EMAIL")),
                    "enviar_whatsapp": valor_booleano(row.get("ENVIAR WHATSAPP")),
                    "enviar_grupo_whatsapp": valor_booleano(row.get("ENVIAR GRUPO WHATSAPP")),
                    "enviar_impresso": valor_booleano(row.get("ENVIAR IMPRESSO")),

                    # Dados de localizacao
                    "empresa": str(row.get("EMPRESA", "")).strip(),
                    "local_contrato_polo": str(row.get("LOCAL - CONTRATO - POLO", "")).strip(),

                    # Diretorios
                    "diretorio_geral": str(row.get("DIRETORIO GERAL", "")).strip(),
                    "diretorio_especifico": str(row.get("DIRETORIO ESPECIFICO", "")).strip(),

                    # Metadados
                    "origem": "migracao_planilha",
                    "data_migracao": datetime.utcnow(),
                    "linha_planilha_original": idx + 2
                }

                if dry_run:
                    logger.info(f"[DRY RUN] Migraria: {contato_id} - {documento['nome']}")
                    migrados += 1
                    continue

                # Inserir ou atualizar no MongoDB
                if sobrescrever:
                    # Atualizar existente ou inserir novo
                    resultado = colecao.update_one(
                        {"funcionario_id": contato_id},
                        {"$set": documento},
                        upsert=True
                    )
                    if resultado.upserted_id:
                        logger.debug(f"Inserido: {contato_id} - {documento['nome']}")
                    else:
                        logger.debug(f"Atualizado: {contato_id} - {documento['nome']}")
                else:
                    # Inserir novo
                    colecao.insert_one(documento)
                    logger.debug(f"Inserido: {contato_id} - {documento['nome']}")

                migrados += 1

                # Log de progresso a cada 10 registros
                if migrados % 10 == 0:
                    logger.info(f"Progresso: {migrados}/{total} migrados")

            except Exception as e:
                logger.error(f"Erro ao processar linha {idx + 2}: {e}")
                erros += 1
                continue

        # Relatorio final
        logger.info("=" * 50)
        logger.info("RELATORIO DE MIGRACAO")
        logger.info("=" * 50)
        logger.info(f"Total de linhas na planilha: {total}")
        logger.info(f"Migrados com sucesso: {migrados}")
        logger.info(f"Pulados (existentes): {pulados}")
        logger.info(f"Erros: {erros}")
        logger.info("=" * 50)

        return True

    except Exception as e:
        logger.error(f"Erro durante a migracao: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Funcao principal"""
    import argparse

    parser = argparse.ArgumentParser(description="Migrar contatos da planilha para MongoDB")
    parser.add_argument(
        "--planilha",
        type=str,
        help="Caminho da planilha Excel (padrao: usa PLANILHA_CONTATOS_PATH do .env)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas mostra o que seria feito sem salvar"
    )
    parser.add_argument(
        "--sobrescrever",
        action="store_true",
        help="Sobrescreve contatos existentes com mesmo ID"
    )

    args = parser.parse_args()

    # Carregar variaveis de ambiente
    env_path = caminho_dotenv()
    load_dotenv(env_path, override=True)

    # Determinar caminho da planilha
    planilha_path = args.planilha or os.getenv("PLANILHA_CONTATOS_PATH")

    if not planilha_path:
        base_dir = Path(__file__).parent.parent
        planilha_path = str(base_dir / "src" / "data" / "models" / "Planilha de Contatos - Folhas de Ponto.xlsx")
        logger.info(f"Usando caminho padrao da planilha: {planilha_path}")

    # Executar migracao
    sucesso = migrar(
        planilha_path=planilha_path,
        dry_run=args.dry_run,
        sobrescrever=args.sobrescrever
    )

    if sucesso:
        logger.info("Migracao concluida com sucesso!")
    else:
        logger.error("Migracao falhou!")
        sys.exit(1)


if __name__ == "__main__":
    main()
