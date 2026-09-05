"""
Script de Migração: Converter timestamps de string para DateTime nativo

Este script percorre todas as coleções do MongoDB e converte os campos 
'timestamp' dentro de 'historico_alteracoes' de string ISO para DateTime nativo.

Uso:
    uv run python scripts/migrar_timestamps_historico.py

Opções:
    --dry-run    Apenas mostra o que seria feito sem alterar o banco
    --collection <nome>  Migrar apenas uma coleção específica
"""

import sys
import argparse
from datetime import datetime, timezone
from typing import List, Dict, Any

import dotenv

# Adicionar path do projeto
sys.path.insert(0, '.')

from src.utils.dotenv_path import caminho_dotenv
from src.utils.logger_config import logger

try:
    from pymongo import MongoClient
    from dateutil import parser as date_parser
    MONGODB_DISPONIVEL = True
except ImportError as e:
    logger.error(f"Dependências não instaladas: {e}")
    logger.error("Execute: pip install pymongo python-dateutil")
    MONGODB_DISPONIVEL = False


def conectar_mongodb() -> MongoClient:
    """Conecta ao MongoDB usando as credenciais do .env"""
    mongo_uri = dotenv.get_key(caminho_dotenv(), "MONGO_URI")
    db_name = dotenv.get_key(caminho_dotenv(), "MONGO_DATABASE_NAME")
    
    if not mongo_uri or not db_name:
        raise ValueError("MONGO_URI e MONGO_DATABASE_NAME devem estar configurados no .env")
    
    cliente = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    cliente.admin.command('ismaster')  # Testar conexão
    
    return cliente, db_name


def converter_timestamp_string_para_datetime(timestamp_str: str) -> datetime:
    """
    Converte uma string de timestamp para datetime.
    Suporta formatos ISO 8601 e variações.
    """
    if isinstance(timestamp_str, datetime):
        return timestamp_str  # Já é datetime
    
    if not isinstance(timestamp_str, str):
        return None
    
    try:
        # Tentar parse ISO 8601
        return date_parser.isoparse(timestamp_str)
    except Exception:
        try:
            # Fallback para outros formatos
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except Exception:
            logger.warning(f"Não foi possível converter timestamp: {timestamp_str}")
            return None


def migrar_colecao(db, collection_name: str, dry_run: bool = False) -> Dict[str, int]:
    """
    Migra os timestamps de uma coleção específica.
    
    Returns:
        Dict com estatísticas: documentos_verificados, documentos_atualizados, erros
    """
    colecao = db[collection_name]
    stats = {
        "documentos_verificados": 0,
        "documentos_atualizados": 0,
        "timestamps_convertidos": 0,
        "erros": 0
    }
    
    # Buscar documentos que têm historico_alteracoes
    cursor = colecao.find(
        {"historico_alteracoes": {"$exists": True, "$ne": []}},
        {"_id": 1, "historico_alteracoes": 1, "nome": 1}
    )
    
    for doc in cursor:
        stats["documentos_verificados"] += 1
        doc_id = doc["_id"]
        historico = doc.get("historico_alteracoes", [])
        nome = doc.get("nome", str(doc_id))
        
        # Verificar se precisa de migração
        historico_atualizado = []
        precisou_atualizar = False
        
        for entrada in historico:
            entrada_nova = entrada.copy()
            timestamp = entrada.get("timestamp")
            
            # Se timestamp é string, converter
            if isinstance(timestamp, str):
                dt = converter_timestamp_string_para_datetime(timestamp)
                if dt:
                    entrada_nova["timestamp"] = dt
                    precisou_atualizar = True
                    stats["timestamps_convertidos"] += 1
            
            historico_atualizado.append(entrada_nova)
        
        # Atualizar documento se necessário
        if precisou_atualizar:
            if dry_run:
                print(f"  [DRY-RUN] Atualizaria: {nome} ({len([e for e in historico if isinstance(e.get('timestamp'), str)])} timestamps)")
            else:
                try:
                    resultado = colecao.update_one(
                        {"_id": doc_id},
                        {"$set": {"historico_alteracoes": historico_atualizado}}
                    )
                    if resultado.modified_count > 0:
                        stats["documentos_atualizados"] += 1
                        logger.info(f"✓ Atualizado: {nome}")
                except Exception as e:
                    stats["erros"] += 1
                    logger.error(f"✗ Erro ao atualizar {nome}: {e}")
    
    return stats


def listar_colecoes_com_historico(db) -> List[str]:
    """Lista todas as coleções que podem ter historico_alteracoes"""
    colecoes = db.list_collection_names()
    
    colecoes_com_historico = []
    for nome in colecoes:
        # Verificar se a coleção tem documentos com historico_alteracoes
        if db[nome].find_one({"historico_alteracoes": {"$exists": True}}):
            colecoes_com_historico.append(nome)
    
    return colecoes_com_historico


def main():
    parser = argparse.ArgumentParser(
        description="Migrar timestamps de string para DateTime no MongoDB"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Apenas mostra o que seria feito sem alterar o banco"
    )
    parser.add_argument(
        "--collection",
        type=str,
        help="Migrar apenas uma coleção específica"
    )
    
    args = parser.parse_args()
    
    if not MONGODB_DISPONIVEL:
        print("❌ MongoDB/dateutil não disponível. Instale as dependências.")
        return 1
    
    print("=" * 60)
    print("  MIGRAÇÃO: Timestamps String → DateTime")
    print("=" * 60)
    
    if args.dry_run:
        print("\n⚠️  MODO DRY-RUN: Nenhuma alteração será feita\n")
    
    try:
        cliente, db_name = conectar_mongodb()
        db = cliente[db_name]
        print(f"✓ Conectado ao banco: {db_name}\n")
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        return 1
    
    # Listar coleções a migrar
    if args.collection:
        colecoes = [args.collection]
        print(f"📋 Migrando coleção específica: {args.collection}\n")
    else:
        colecoes = listar_colecoes_com_historico(db)
        print(f"📋 Coleções com histórico encontradas: {len(colecoes)}")
        for c in colecoes:
            print(f"   • {c}")
        print()
    
    # Estatísticas totais
    totais = {
        "documentos_verificados": 0,
        "documentos_atualizados": 0,
        "timestamps_convertidos": 0,
        "erros": 0
    }
    
    # Migrar cada coleção
    for colecao in colecoes:
        print(f"\n{'─' * 40}")
        print(f"📁 Processando: {colecao}")
        print(f"{'─' * 40}")
        
        stats = migrar_colecao(db, colecao, dry_run=args.dry_run)
        
        print(f"   Documentos verificados: {stats['documentos_verificados']}")
        print(f"   Timestamps convertidos: {stats['timestamps_convertidos']}")
        print(f"   Documentos atualizados: {stats['documentos_atualizados']}")
        if stats['erros'] > 0:
            print(f"   ⚠️ Erros: {stats['erros']}")
        
        for key in totais:
            totais[key] += stats[key]
    
    # Resumo final
    print("\n" + "=" * 60)
    print("  RESUMO DA MIGRAÇÃO")
    print("=" * 60)
    print(f"  Total de coleções processadas: {len(colecoes)}")
    print(f"  Total de documentos verificados: {totais['documentos_verificados']}")
    print(f"  Total de timestamps convertidos: {totais['timestamps_convertidos']}")
    print(f"  Total de documentos atualizados: {totais['documentos_atualizados']}")
    if totais['erros'] > 0:
        print(f"  ⚠️ Total de erros: {totais['erros']}")
    
    if args.dry_run:
        print("\n⚠️  MODO DRY-RUN: Execute sem --dry-run para aplicar as alterações")
    else:
        print("\n✅ Migração concluída!")
    
    cliente.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
