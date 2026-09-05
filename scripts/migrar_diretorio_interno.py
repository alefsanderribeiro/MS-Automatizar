"""
Script de Migração: Converter diretorio_interno para referência ObjectId

Este script:
1. Cria a coleção 'diretorios' com base nos valores únicos de diretorio_interno
   (preservando a estrutura hierárquica: "01. MS SERVIÇOS\CENSIPAM", etc.)
2. Atualiza os funcionários para usar diretorio_id ao invés de diretorio_interno
3. Registra todas as alterações no historico_alteracoes

IMPORTANTE: Os diretórios são criados a partir dos valores de diretorio_interno
dos funcionários, NÃO dos contratos. Isso preserva a estrutura de pastas:
- 01. MS SERVIÇOS\{CONTRATO}
- 02. MADEIRA SERVIÇOS\{CONTRATO}
- 03. FOLGUISTAS

Uso:
    uv run python scripts/migrar_diretorio_interno.py

Opções:
    --dry-run    Apenas mostra o que seria feito sem alterar o banco
"""

import sys
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

import dotenv

# Adicionar path do projeto
sys.path.insert(0, '.')

from src.utils.dotenv_path import caminho_dotenv
from src.utils.logger_config import logger

try:
    from pymongo import MongoClient
    from bson import ObjectId
    MONGODB_DISPONIVEL = True
except ImportError as e:
    logger.error(f"Dependências não instaladas: {e}")
    logger.error("Execute: pip install pymongo")
    MONGODB_DISPONIVEL = False


# ==================== CONSTANTES ====================

COLLECTION_FUNCIONARIOS = "funcionarios"
COLLECTION_CONTRATOS = "contratos"
COLLECTION_DIRETORIOS = "diretorios"

# Valor padrão quando diretório não pode ser determinado
FALLBACK_DIRETORIO = "\\"


# ==================== FUNÇÕES AUXILIARES ====================

def conectar_mongodb() -> Tuple[MongoClient, str]:
    """Conecta ao MongoDB usando as credenciais do .env"""
    mongo_uri = dotenv.get_key(caminho_dotenv(), "MONGO_URI")
    db_name = dotenv.get_key(caminho_dotenv(), "MONGO_DATABASE_NAME")
    
    if not mongo_uri or not db_name:
        raise ValueError("MONGO_URI e MONGO_DATABASE_NAME devem estar configurados no .env")
    
    cliente = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    cliente.admin.command('ismaster')  # Testar conexão
    
    return cliente, db_name


def normalizar_texto(texto: str) -> str:
    """
    Normaliza texto para comparação e busca.
    Remove acentos, converte para minúsculas.
    """
    import unicodedata
    if not texto:
        return ""
    nfkd = unicodedata.normalize('NFKD', texto)
    normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)])
    return normalizado.lower().strip()


def criar_entrada_historico(acao: str, detalhes: Dict[str, Any]) -> Dict[str, Any]:
    """Cria entrada padronizada para histórico de alterações"""
    return {
        "timestamp": datetime.now(timezone.utc),
        "acao": acao,
        "origem": "migracao",
        "script": "migrar_diretorio_interno.py",
        "detalhes": detalhes
    }


# ==================== FASE 1: CRIAR DIRETÓRIOS ====================

def criar_diretorios_de_diretorio_interno(db, dry_run: bool = False) -> Dict[str, ObjectId]:
    """
    Cria diretórios baseados nos valores únicos de diretorio_interno.
    
    Isso preserva a estrutura hierárquica original:
    - 01. MS SERVIÇOS\CENSIPAM
    - 02. MADEIRA SERVIÇOS\FUNAI CACOAL
    - 03. FOLGUISTAS
    
    Returns:
        Dict mapeando diretorio_interno (string) -> diretorio_id (ObjectId)
    """
    print("\n" + "=" * 50)
    print("  FASE 1: Criando diretórios de diretorio_interno")
    print("=" * 50)
    
    col_funcionarios = db[COLLECTION_FUNCIONARIOS]
    col_diretorios = db[COLLECTION_DIRETORIOS]
    
    # Buscar todos os valores únicos de diretorio_interno
    valores_diretorio = col_funcionarios.distinct("diretorio_interno")
    
    # Filtrar valores válidos (não vazios, não None)
    valores_validos = [
        v for v in valores_diretorio 
        if v and isinstance(v, str) and v.strip() and v.strip() != "\\"
    ]
    
    print(f"\n📋 Valores únicos de diretorio_interno encontrados: {len(valores_validos)}")
    
    mapeamento: Dict[str, ObjectId] = {}
    stats = {
        "diretorios_criados": 0,
        "diretorios_existentes": 0,
        "erros": 0
    }
    
    for diretorio_interno in sorted(valores_validos):
        nome_normalizado = normalizar_texto(diretorio_interno)
        
        # Verificar se diretório já existe com este caminho_relativo
        diretorio_existente = col_diretorios.find_one({
            "caminho_relativo": diretorio_interno
        })
        
        if diretorio_existente:
            mapeamento[diretorio_interno] = diretorio_existente["_id"]
            stats["diretorios_existentes"] += 1
            print(f"  ✓ Diretório já existe: {diretorio_interno}")
            continue
        
        # Extrair nome legível (última parte do caminho)
        partes = diretorio_interno.split("\\")
        nome_exibicao = partes[-1] if partes else diretorio_interno
        
        # Gerar id_diretorio único
        id_diretorio = f"DIR-{nome_normalizado[:30].upper().replace(' ', '-').replace('\\', '-')}"
        
        # Criar novo diretório
        # NOTA: Não incluir contrato_id=None para evitar conflito com índice sparse
        novo_diretorio = {
            "id_diretorio": id_diretorio,
            "nome": nome_exibicao,
            "descricao": f"Diretório: {diretorio_interno}",
            "caminho_relativo": diretorio_interno,  # Valor original preservado
            # contrato_id omitido intencionalmente - índice sparse ignora documentos sem o campo
            "ativo": True,
            "ordem": 0,
            "nome_normalizado": nome_normalizado,
            "auto_criado": True,
            "criado_em": datetime.now(timezone.utc),
            "atualizado_em": datetime.now(timezone.utc),
            "versao": 1,
            "historico_alteracoes": [
                criar_entrada_historico(
                    "criacao",
                    {
                        "motivo": "Migração de diretorio_interno para coleção diretorios",
                        "diretorio_interno_original": diretorio_interno
                    }
                )
            ]
        }
        
        if dry_run:
            print(f"  [DRY-RUN] Criaria diretório: {diretorio_interno}")
            # Usar um ObjectId temporário para dry-run
            mapeamento[diretorio_interno] = ObjectId()
            stats["diretorios_criados"] += 1
        else:
            try:
                resultado = col_diretorios.insert_one(novo_diretorio)
                mapeamento[diretorio_interno] = resultado.inserted_id
                stats["diretorios_criados"] += 1
                print(f"  ✓ Criado diretório: {diretorio_interno}")
            except Exception as e:
                stats["erros"] += 1
                print(f"  ✗ Erro ao criar diretório para {diretorio_interno}: {e}")
    
    print(f"\n📊 Resumo Fase 1:")
    print(f"   Diretórios criados: {stats['diretorios_criados']}")
    print(f"   Diretórios existentes: {stats['diretorios_existentes']}")
    if stats['erros'] > 0:
        print(f"   ⚠️ Erros: {stats['erros']}")
    
    return mapeamento


# ==================== FASE 2: ATUALIZAR FUNCIONÁRIOS ====================

def atualizar_funcionarios(
    db, 
    mapeamento_diretorio: Dict[str, ObjectId],
    dry_run: bool = False
) -> Dict[str, int]:
    """
    Atualiza funcionários para usar diretorio_id.
    
    Para cada funcionário:
    1. Busca o diretorio_interno do funcionário
    2. Obtém o diretorio_id correspondente do mapeamento
    3. Adiciona diretorio_id ao documento
    4. Registra no histórico de alterações
    """
    print("\n" + "=" * 50)
    print("  FASE 2: Atualizando funcionários")
    print("=" * 50)
    
    col_funcionarios = db[COLLECTION_FUNCIONARIOS]
    
    stats = {
        "funcionarios_verificados": 0,
        "funcionarios_atualizados": 0,
        "funcionarios_sem_diretorio": 0,
        "funcionarios_ja_migrados": 0,
        "erros": 0
    }
    
    # Buscar todos os funcionários
    cursor = col_funcionarios.find({}, {
        "_id": 1,
        "nome": 1,
        "diretorio_interno": 1,
        "diretorio_id": 1,
        "historico_alteracoes": 1,
        "versao": 1
    })
    
    for func in cursor:
        stats["funcionarios_verificados"] += 1
        func_id = func["_id"]
        nome = func.get("nome", str(func_id))
        
        # Verificar se já foi migrado
        if func.get("diretorio_id"):
            stats["funcionarios_ja_migrados"] += 1
            continue
        
        # Obter diretorio_interno
        diretorio_interno = func.get("diretorio_interno")
        
        if not diretorio_interno or diretorio_interno.strip() == "\\" or not diretorio_interno.strip():
            stats["funcionarios_sem_diretorio"] += 1
            print(f"  ⚠️ {nome}: sem diretorio_interno válido")
            continue
        
        # Buscar diretorio_id do mapeamento
        diretorio_id = mapeamento_diretorio.get(diretorio_interno)
        
        if not diretorio_id:
            print(f"  ⚠️ {nome}: diretorio_interno '{diretorio_interno}' não tem diretório mapeado")
            stats["erros"] += 1
            continue
        
        # Preparar atualização
        historico_atual = func.get("historico_alteracoes", [])
        versao_atual = func.get("versao", 1)
        
        entrada_historico = criar_entrada_historico(
            "migracao_diretorio",
            {
                "campo_anterior": "diretorio_interno",
                "campo_novo": "diretorio_id",
                "valor_anterior": diretorio_interno,
                "valor_novo": str(diretorio_id),
                "versao_anterior": versao_atual
            }
        )
        
        historico_atualizado = historico_atual + [entrada_historico]
        
        update_doc = {
            "$set": {
                "diretorio_id": diretorio_id,
                "versao": versao_atual + 1,
                "atualizado_em": datetime.now(timezone.utc),
                "historico_alteracoes": historico_atualizado
            }
        }
        
        if dry_run:
            print(f"  [DRY-RUN] Atualizaria: {nome} → diretorio_id={diretorio_id}")
        else:
            try:
                resultado = col_funcionarios.update_one(
                    {"_id": func_id},
                    update_doc
                )
                if resultado.modified_count > 0:
                    stats["funcionarios_atualizados"] += 1
                    logger.info(f"✓ Atualizado: {nome}")
            except Exception as e:
                stats["erros"] += 1
                print(f"  ✗ Erro ao atualizar {nome}: {e}")
    
    print(f"\n📊 Resumo Fase 2:")
    print(f"   Funcionários verificados: {stats['funcionarios_verificados']}")
    print(f"   Funcionários atualizados: {stats['funcionarios_atualizados']}")
    print(f"   Já migrados: {stats['funcionarios_ja_migrados']}")
    print(f"   Sem diretório válido: {stats['funcionarios_sem_diretorio']}")
    if stats['erros'] > 0:
        print(f"   ⚠️ Erros: {stats['erros']}")
    
    return stats


# ==================== FASE 3: CRIAR ÍNDICES ====================

def criar_indices(db, dry_run: bool = False) -> None:
    """Cria índices na coleção diretorios"""
    print("\n" + "=" * 50)
    print("  FASE 3: Criando índices")
    print("=" * 50)
    
    if dry_run:
        print("  [DRY-RUN] Criaria índices:")
        print("    - nome_normalizado (único)")
        print("    - caminho_relativo (único)")
        print("    - ativo")
        return
    
    col_diretorios = db[COLLECTION_DIRETORIOS]
    
    try:
        # Índice único em nome_normalizado
        col_diretorios.create_index(
            [("nome_normalizado", 1)],
            unique=True,
            name="idx_nome_normalizado_unique"
        )
        print("  ✓ Índice criado: nome_normalizado (único)")
    except Exception as e:
        if "already exists" in str(e).lower():
            print("  ✓ Índice já existe: nome_normalizado")
        else:
            print(f"  ⚠️ Erro ao criar índice nome_normalizado: {e}")
    
    try:
        # Índice único em caminho_relativo (substitui contrato_id)
        col_diretorios.create_index(
            [("caminho_relativo", 1)],
            unique=True,
            name="idx_caminho_relativo_unique"
        )
        print("  ✓ Índice criado: caminho_relativo (único)")
    except Exception as e:
        if "already exists" in str(e).lower():
            print("  ✓ Índice já existe: caminho_relativo")
        else:
            print(f"  ⚠️ Erro ao criar índice caminho_relativo: {e}")
    
    try:
        # Índice em ativo para filtros
        col_diretorios.create_index(
            [("ativo", 1)],
            name="idx_ativo"
        )
        print("  ✓ Índice criado: ativo")
    except Exception as e:
        if "already exists" in str(e).lower():
            print("  ✓ Índice já existe: ativo")
        else:
            print(f"  ⚠️ Erro ao criar índice ativo: {e}")


# ==================== FASE 4: VERIFICAÇÃO ====================

def verificar_migracao(db) -> None:
    """Verifica integridade da migração"""
    print("\n" + "=" * 50)
    print("  FASE 4: Verificação")
    print("=" * 50)
    
    col_funcionarios = db[COLLECTION_FUNCIONARIOS]
    col_diretorios = db[COLLECTION_DIRETORIOS]
    
    # Contar funcionários com diretorio_id
    com_diretorio_id = col_funcionarios.count_documents({"diretorio_id": {"$exists": True}})
    sem_diretorio_id = col_funcionarios.count_documents({"diretorio_id": {"$exists": False}})
    total_funcionarios = col_funcionarios.count_documents({})
    
    # Contar diretórios
    total_diretorios = col_diretorios.count_documents({})
    diretorios_ativos = col_diretorios.count_documents({"ativo": True})
    
    print(f"\n📊 Estatísticas:")
    print(f"   Total de funcionários: {total_funcionarios}")
    print(f"   Com diretorio_id: {com_diretorio_id}")
    print(f"   Sem diretorio_id: {sem_diretorio_id}")
    print(f"\n   Total de diretórios: {total_diretorios}")
    print(f"   Diretórios ativos: {diretorios_ativos}")
    
    # Verificar referências órfãs
    print("\n🔍 Verificando referências...")
    
    # Funcionários com diretorio_id que não existe
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
        description="Migrar diretorio_interno para coleção diretorios"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Apenas mostra o que seria feito sem alterar o banco"
    )
    
    args = parser.parse_args()
    
    if not MONGODB_DISPONIVEL:
        print("❌ MongoDB não disponível. Instale as dependências.")
        return 1
    
    print("=" * 60)
    print("  MIGRAÇÃO: diretorio_interno → coleção diretorios")
    print("=" * 60)
    
    if args.dry_run:
        print("\n⚠️  MODO DRY-RUN: Nenhuma alteração será feita\n")
    
    try:
        cliente, db_name = conectar_mongodb()
        db = cliente[db_name]
        print(f"✓ Conectado ao banco: {db_name}")
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        return 1
    
    try:
        # Fase 1: Criar diretórios a partir de diretorio_interno
        mapeamento = criar_diretorios_de_diretorio_interno(db, dry_run=args.dry_run)
        
        # Fase 2: Atualizar funcionários
        stats = atualizar_funcionarios(db, mapeamento, dry_run=args.dry_run)
        
        # Fase 3: Criar índices
        criar_indices(db, dry_run=args.dry_run)
        
        # Fase 4: Verificação (sempre executa)
        verificar_migracao(db)
        
    except Exception as e:
        print(f"\n❌ Erro durante migração: {e}")
        logger.exception("Erro na migração")
        return 1
    finally:
        cliente.close()
    
    # Resumo final
    print("\n" + "=" * 60)
    print("  MIGRAÇÃO CONCLUÍDA")
    print("=" * 60)
    
    if args.dry_run:
        print("\n⚠️  MODO DRY-RUN: Execute sem --dry-run para aplicar as alterações")
    else:
        print("\n✅ Migração executada com sucesso!")
        print("\n📋 Próximos passos:")
        print("   1. Atualizar FuncionarioMongoDB: diretorio_interno → diretorio_id")
        print("   2. Atualizar FuncionarioService para auto-criar diretórios")
        print("   3. Atualizar FolhaDePontoService para usar DiretorioService")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
