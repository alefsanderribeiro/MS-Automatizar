"""
Script para REVERTER migração e RECRIAR diretórios baseados no campo diretorio_interno original.

Este script:
1. Remove todos os diretórios criados pela migração anterior
2. Remove o campo diretorio_id dos funcionários
3. Cria novos diretórios baseados nos valores únicos de diretorio_interno
4. Atualiza os funcionários com o novo diretorio_id correspondente

A estrutura original é: "01. MS SERVIÇOS\CENSIPAM", "02. MADEIRA SERVIÇOS\FUNAI CACOAL", etc.

Uso:
    uv run python scripts/reverter_e_recriar_diretorios.py --dry-run
    uv run python scripts/reverter_e_recriar_diretorios.py
"""

import sys
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import unicodedata

import dotenv

# Adicionar path do projeto
sys.path.insert(0, '.')

from src.utils.dotenv_path import caminho_dotenv
from src.utils.logger_config import logger

try:
    from pymongo import MongoClient, ASCENDING
    from bson import ObjectId
    MONGODB_DISPONIVEL = True
except ImportError as e:
    logger.error(f"Dependências não instaladas: {e}")
    MONGODB_DISPONIVEL = False


# ==================== CONSTANTES ====================

COLLECTION_FUNCIONARIOS = "funcionarios"
COLLECTION_DIRETORIOS = "diretorios"


# ==================== FUNÇÕES AUXILIARES ====================

def conectar_mongodb():
    """Conecta ao MongoDB usando as credenciais do .env"""
    mongo_uri = dotenv.get_key(caminho_dotenv(), "MONGO_URI")
    db_name = dotenv.get_key(caminho_dotenv(), "MONGO_DATABASE_NAME")
    
    if not mongo_uri or not db_name:
        raise ValueError("MONGO_URI e MONGO_DATABASE_NAME devem estar configurados no .env")
    
    cliente = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    cliente.admin.command('ismaster')
    
    return cliente, db_name


def normalizar_texto(texto: str) -> str:
    """Normaliza texto para busca"""
    if not texto:
        return ""
    nfkd = unicodedata.normalize('NFKD', texto)
    normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)])
    return normalizado.lower().strip()


def criar_entrada_historico(acao: str, detalhes: Dict[str, Any]) -> Dict[str, Any]:
    """Cria entrada padronizada para histórico"""
    return {
        "timestamp": datetime.now(timezone.utc),
        "acao": acao,
        "origem": "migracao_reversao",
        "script": "reverter_e_recriar_diretorios.py",
        "detalhes": detalhes
    }


# ==================== FASE 1: LIMPAR MIGRAÇÃO ANTERIOR ====================

def limpar_migracao_anterior(db, dry_run: bool = False) -> Dict[str, int]:
    """
    Remove diretórios criados e limpa diretorio_id dos funcionários
    """
    print("\n" + "=" * 60)
    print("  FASE 1: Limpando migração anterior")
    print("=" * 60)
    
    col_diretorios = db[COLLECTION_DIRETORIOS]
    col_funcionarios = db[COLLECTION_FUNCIONARIOS]
    
    stats = {
        "diretorios_removidos": 0,
        "funcionarios_limpos": 0
    }
    
    # Contar diretórios atuais
    total_diretorios = col_diretorios.count_documents({})
    print(f"\n📊 Diretórios atuais: {total_diretorios}")
    
    # Contar funcionários com diretorio_id
    func_com_diretorio_id = col_funcionarios.count_documents({"diretorio_id": {"$exists": True}})
    print(f"📊 Funcionários com diretorio_id: {func_com_diretorio_id}")
    
    if dry_run:
        print(f"\n[DRY-RUN] Removeria {total_diretorios} diretórios")
        print(f"[DRY-RUN] Limparia diretorio_id de {func_com_diretorio_id} funcionários")
        stats["diretorios_removidos"] = total_diretorios
        stats["funcionarios_limpos"] = func_com_diretorio_id
    else:
        # Remover todos os diretórios
        resultado_dir = col_diretorios.delete_many({})
        stats["diretorios_removidos"] = resultado_dir.deleted_count
        print(f"✓ Removidos {stats['diretorios_removidos']} diretórios")
        
        # Remover diretorio_id dos funcionários
        resultado_func = col_funcionarios.update_many(
            {"diretorio_id": {"$exists": True}},
            {
                "$unset": {"diretorio_id": ""},
                "$push": {
                    "historico_alteracoes": criar_entrada_historico(
                        "reversao_migracao",
                        {"motivo": "Reversão da migração de diretório para recriar com estrutura correta"}
                    )
                }
            }
        )
        stats["funcionarios_limpos"] = resultado_func.modified_count
        print(f"✓ Limpado diretorio_id de {stats['funcionarios_limpos']} funcionários")
    
    return stats


# ==================== FASE 2: CRIAR DIRETÓRIOS BASEADOS EM diretorio_interno ====================

def criar_diretorios_de_diretorio_interno(db, dry_run: bool = False) -> Dict[str, ObjectId]:
    """
    Cria diretórios baseados nos valores únicos de diretorio_interno.
    
    Returns:
        Dict mapeando diretorio_interno (string) -> diretorio_id (ObjectId)
    """
    print("\n" + "=" * 60)
    print("  FASE 2: Criando diretórios de diretorio_interno")
    print("=" * 60)
    
    col_funcionarios = db[COLLECTION_FUNCIONARIOS]
    col_diretorios = db[COLLECTION_DIRETORIOS]
    
    # Buscar valores únicos de diretorio_interno
    valores_unicos = col_funcionarios.distinct("diretorio_interno")
    valores_unicos = [v for v in valores_unicos if v and v.strip()]  # Remover vazios/None
    valores_unicos = sorted(valores_unicos)
    
    print(f"\n📋 Valores únicos de diretorio_interno: {len(valores_unicos)}")
    
    mapeamento: Dict[str, ObjectId] = {}
    stats = {
        "diretorios_criados": 0,
        "erros": 0
    }
    
    for idx, valor in enumerate(valores_unicos, 1):
        nome_normalizado = normalizar_texto(valor)
        
        # Extrair informações do caminho (ex: "01. MS SERVIÇOS\CENSIPAM")
        partes = valor.split("\\")
        empresa_prefixo = partes[0] if len(partes) > 0 else valor
        subdiretorio = partes[1] if len(partes) > 1 else ""
        
        # Criar documento do diretório
        novo_diretorio = {
            "id_diretorio": f"DIR-{idx:03d}",
            "nome": valor,  # Nome completo: "01. MS SERVIÇOS\CENSIPAM"
            "descricao": f"Diretório: {valor}",
            "caminho_relativo": valor,  # Caminho completo para uso no sistema de arquivos
            "empresa_prefixo": empresa_prefixo,  # Ex: "01. MS SERVIÇOS"
            "subdiretorio": subdiretorio,  # Ex: "CENSIPAM"
            "contrato_id": None,  # Não associado a contrato específico
            "ativo": True,
            "ordem": idx,
            "nome_normalizado": nome_normalizado,
            "auto_criado": False,
            "criado_em": datetime.now(timezone.utc),
            "atualizado_em": datetime.now(timezone.utc),
            "versao": 1,
            "historico_alteracoes": [
                criar_entrada_historico(
                    "criacao",
                    {
                        "motivo": "Criação baseada em diretorio_interno original",
                        "valor_original": valor
                    }
                )
            ]
        }
        
        if dry_run:
            print(f"  [{idx:02d}] [DRY-RUN] Criaria: {valor}")
            mapeamento[valor] = ObjectId()  # ObjectId temporário
        else:
            try:
                resultado = col_diretorios.insert_one(novo_diretorio)
                mapeamento[valor] = resultado.inserted_id
                stats["diretorios_criados"] += 1
                print(f"  [{idx:02d}] ✓ Criado: {valor}")
            except Exception as e:
                stats["erros"] += 1
                print(f"  [{idx:02d}] ✗ Erro: {valor} - {e}")
    
    print(f"\n📊 Resumo Fase 2:")
    print(f"   Diretórios criados: {stats['diretorios_criados']}")
    if stats['erros'] > 0:
        print(f"   ⚠️ Erros: {stats['erros']}")
    
    return mapeamento


# ==================== FASE 3: ATUALIZAR FUNCIONÁRIOS ====================

def atualizar_funcionarios(
    db, 
    mapeamento: Dict[str, ObjectId],
    dry_run: bool = False
) -> Dict[str, int]:
    """
    Atualiza funcionários com o novo diretorio_id baseado no diretorio_interno.
    """
    print("\n" + "=" * 60)
    print("  FASE 3: Atualizando funcionários")
    print("=" * 60)
    
    col_funcionarios = db[COLLECTION_FUNCIONARIOS]
    
    stats = {
        "funcionarios_atualizados": 0,
        "funcionarios_sem_diretorio_interno": 0,
        "erros": 0
    }
    
    # Buscar todos os funcionários com diretorio_interno
    cursor = col_funcionarios.find(
        {"diretorio_interno": {"$exists": True, "$ne": None, "$ne": ""}},
        {"_id": 1, "nome": 1, "diretorio_interno": 1}
    )
    
    for func in cursor:
        func_id = func["_id"]
        nome = func.get("nome", str(func_id))
        diretorio_interno = func.get("diretorio_interno", "").strip()
        
        if not diretorio_interno:
            stats["funcionarios_sem_diretorio_interno"] += 1
            continue
        
        # Buscar diretorio_id correspondente
        diretorio_id = mapeamento.get(diretorio_interno)
        
        if not diretorio_id:
            print(f"  ⚠️ {nome}: diretorio_interno '{diretorio_interno}' não mapeado")
            stats["erros"] += 1
            continue
        
        if dry_run:
            print(f"  [DRY-RUN] Atualizaria: {nome} → {diretorio_interno}")
        else:
            try:
                resultado = col_funcionarios.update_one(
                    {"_id": func_id},
                    {
                        "$set": {
                            "diretorio_id": diretorio_id,
                            "atualizado_em": datetime.now(timezone.utc)
                        },
                        "$inc": {"versao": 1},
                        "$push": {
                            "historico_alteracoes": criar_entrada_historico(
                                "vinculacao_diretorio",
                                {
                                    "diretorio_interno": diretorio_interno,
                                    "diretorio_id": str(diretorio_id)
                                }
                            )
                        }
                    }
                )
                if resultado.modified_count > 0:
                    stats["funcionarios_atualizados"] += 1
            except Exception as e:
                stats["erros"] += 1
                print(f"  ✗ Erro ao atualizar {nome}: {e}")
    
    # Contar funcionários sem diretorio_interno
    sem_dir_interno = col_funcionarios.count_documents({
        "$or": [
            {"diretorio_interno": {"$exists": False}},
            {"diretorio_interno": None},
            {"diretorio_interno": ""}
        ]
    })
    stats["funcionarios_sem_diretorio_interno"] = sem_dir_interno
    
    print(f"\n📊 Resumo Fase 3:")
    print(f"   Funcionários atualizados: {stats['funcionarios_atualizados']}")
    print(f"   Sem diretorio_interno: {stats['funcionarios_sem_diretorio_interno']}")
    if stats['erros'] > 0:
        print(f"   ⚠️ Erros: {stats['erros']}")
    
    return stats


# ==================== FASE 4: CRIAR ÍNDICES ====================

def criar_indices(db, dry_run: bool = False) -> None:
    """Cria índices na coleção diretorios"""
    print("\n" + "=" * 60)
    print("  FASE 4: Criando índices")
    print("=" * 60)
    
    if dry_run:
        print("  [DRY-RUN] Criaria índices")
        return
    
    col_diretorios = db[COLLECTION_DIRETORIOS]
    
    try:
        # Remover índices antigos que podem conflitar
        try:
            col_diretorios.drop_index("idx_contrato_id_unico")
        except:
            pass
        try:
            col_diretorios.drop_index("idx_contrato_id_unique")
        except:
            pass
        
        # Índice único em nome_normalizado
        col_diretorios.create_index(
            [("nome_normalizado", ASCENDING)],
            unique=True,
            name="idx_nome_normalizado_unique"
        )
        print("  ✓ Índice criado: nome_normalizado (único)")
        
        # Índice em empresa_prefixo para buscas
        col_diretorios.create_index(
            [("empresa_prefixo", ASCENDING)],
            name="idx_empresa_prefixo"
        )
        print("  ✓ Índice criado: empresa_prefixo")
        
        # Índice em ativo
        col_diretorios.create_index(
            [("ativo", ASCENDING)],
            name="idx_ativo"
        )
        print("  ✓ Índice criado: ativo")
        
    except Exception as e:
        print(f"  ⚠️ Erro ao criar índices: {e}")


# ==================== FASE 5: VERIFICAÇÃO ====================

def verificar_resultado(db) -> None:
    """Verifica o resultado da migração"""
    print("\n" + "=" * 60)
    print("  FASE 5: Verificação")
    print("=" * 60)
    
    col_funcionarios = db[COLLECTION_FUNCIONARIOS]
    col_diretorios = db[COLLECTION_DIRETORIOS]
    
    # Estatísticas
    total_diretorios = col_diretorios.count_documents({})
    total_funcionarios = col_funcionarios.count_documents({})
    com_diretorio_id = col_funcionarios.count_documents({"diretorio_id": {"$exists": True}})
    sem_diretorio_id = col_funcionarios.count_documents({"diretorio_id": {"$exists": False}})
    
    print(f"\n📊 Estatísticas:")
    print(f"   Total de diretórios: {total_diretorios}")
    print(f"   Total de funcionários: {total_funcionarios}")
    print(f"   Com diretorio_id: {com_diretorio_id}")
    print(f"   Sem diretorio_id: {sem_diretorio_id}")
    
    # Listar diretórios por empresa
    print("\n📁 Diretórios por empresa:")
    
    pipeline = [
        {"$group": {"_id": "$empresa_prefixo", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    
    for grupo in col_diretorios.aggregate(pipeline):
        print(f"   {grupo['_id']}: {grupo['count']} diretórios")
    
    # Verificar referências órfãs
    print("\n🔍 Verificando referências...")
    
    pipeline = [
        {"$match": {"diretorio_id": {"$exists": True}}},
        {
            "$lookup": {
                "from": COLLECTION_DIRETORIOS,
                "localField": "diretorio_id",
                "foreignField": "_id",
                "as": "diretorio"
            }
        },
        {"$match": {"diretorio": {"$size": 0}}},
        {"$count": "orfaos"}
    ]
    
    resultado = list(col_funcionarios.aggregate(pipeline))
    orfaos = resultado[0]["orfaos"] if resultado else 0
    
    if orfaos > 0:
        print(f"   ⚠️ Funcionários com diretorio_id órfão: {orfaos}")
    else:
        print("   ✓ Todas as referências estão válidas")


# ==================== MAIN ====================

def main():
    parser = argparse.ArgumentParser(
        description="Reverter migração e recriar diretórios baseados em diretorio_interno"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Apenas mostra o que seria feito sem alterar o banco"
    )
    
    args = parser.parse_args()
    
    if not MONGODB_DISPONIVEL:
        print("❌ MongoDB não disponível")
        return 1
    
    print("=" * 70)
    print("  REVERSÃO E RECRIAÇÃO DE DIRETÓRIOS")
    print("  Baseado nos valores originais de diretorio_interno")
    print("=" * 70)
    
    if args.dry_run:
        print("\n⚠️  MODO DRY-RUN: Nenhuma alteração será feita\n")
    else:
        print("\n⚠️  ATENÇÃO: Esta operação irá APAGAR todos os diretórios existentes!")
        confirma = input("   Deseja continuar? (s/N): ").strip().lower()
        if confirma != 's':
            print("Operação cancelada.")
            return 0
    
    try:
        cliente, db_name = conectar_mongodb()
        db = cliente[db_name]
        print(f"\n✓ Conectado ao banco: {db_name}")
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        return 1
    
    try:
        # Fase 1: Limpar migração anterior
        limpar_migracao_anterior(db, dry_run=args.dry_run)
        
        # Fase 2: Criar diretórios baseados em diretorio_interno
        mapeamento = criar_diretorios_de_diretorio_interno(db, dry_run=args.dry_run)
        
        # Fase 3: Atualizar funcionários
        atualizar_funcionarios(db, mapeamento, dry_run=args.dry_run)
        
        # Fase 4: Criar índices
        criar_indices(db, dry_run=args.dry_run)
        
        # Fase 5: Verificação
        if not args.dry_run:
            verificar_resultado(db)
        
    except Exception as e:
        print(f"\n❌ Erro durante operação: {e}")
        logger.exception("Erro na reversão/recriação")
        return 1
    finally:
        cliente.close()
    
    # Resumo final
    print("\n" + "=" * 70)
    print("  OPERAÇÃO CONCLUÍDA")
    print("=" * 70)
    
    if args.dry_run:
        print("\n⚠️  MODO DRY-RUN: Execute sem --dry-run para aplicar as alterações")
    else:
        print("\n✅ Diretórios recriados com sucesso!")
        print("\n📋 Estrutura criada:")
        print("   - 01. MS SERVIÇOS\\...")
        print("   - 02. MADEIRA SERVIÇOS\\...")
        print("   - 03. FOLGUISTAS")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
