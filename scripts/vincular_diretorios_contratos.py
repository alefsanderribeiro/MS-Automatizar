"""
Script para Vincular Diretórios aos Contratos

Este script atualiza os diretórios para incluir o contrato_id correspondente
baseado no nome do contrato que aparece no caminho_relativo do diretório.

Estrutura dos diretórios:
- 01. MS SERVIÇOS\{CONTRATO}\{LOTAÇÃO}
- 02. MADEIRA SERVIÇOS\{CONTRATO}\{LOTAÇÃO}
- 03. FOLGUISTAS

O script identifica o contrato pelo nome e vincula ao diretório.

Uso:
    uv run python scripts/vincular_diretorios_contratos.py

Opções:
    --dry-run    Apenas mostra o que seria feito sem alterar o banco
"""

import sys
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

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

COLLECTION_DIRETORIOS = "diretorios"
COLLECTION_CONTRATOS = "contratos"


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
    """Normaliza texto para comparação."""
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
        "origem": "script",
        "script": "vincular_diretorios_contratos.py",
        "detalhes": detalhes
    }


def extrair_nome_contrato(caminho_relativo: str) -> Optional[str]:
    """
    Extrai o nome do contrato a partir do caminho_relativo.
    
    Exemplos:
        "01. MS SERVIÇOS\\CENSIPAM" -> "CENSIPAM"
        "01. MS SERVIÇOS\\DSEI JAVARI - COZINHA" -> "DSEI JAVARI"
        "01. MS SERVIÇOS\\FUNAI CACOAL" -> "FUNAI CACOAL"
        "01. MS SERVIÇOS\\DSEI PVH - BARQUEIROS\\PORTO VELHO" -> "DSEI PVH"
        "03. FOLGUISTAS" -> None (não tem contrato específico)
    """
    if not caminho_relativo:
        return None
    
    partes = caminho_relativo.split("\\")
    
    # Se só tem uma parte (ex: "03. FOLGUISTAS"), não tem contrato
    if len(partes) < 2:
        return None
    
    # Pegar a segunda parte (após a empresa)
    nome_contrato = partes[1]
    
    # Retornar o nome completo para que o mapeamento especial possa tratá-lo
    return nome_contrato.strip()


# Mapeamento manual para casos especiais
MAPEAMENTO_ESPECIAL = {
    "DSEI VILHENA CC": "DSEI VILHENA - CACOAL",
    "DSEI VILHENA CC - MOTORISTAS": "DSEI VILHENA - CACOAL",
    "DSEI VILHENA MT": "DSEI VILHENA - MT",
    "DSEI VILHENA MT - MOTORISTAS": "DSEI VILHENA - MT",
    "TCE - PVH": "TCE LIMPEZA",
    "DSEI AM": "DSEI MANAUS",
    "DSEI AM - LIMPEZA": "DSEI MANAUS",
    "FUNASA - AP": "FUNASA AMAPA",
    "POUPEX - AC": "POUPEX ACRE",
    "POUPEX - PVH": "POUPEX PVH",
}


def carregar_contratos(db) -> Dict[str, ObjectId]:
    """
    Carrega todos os contratos e cria um mapeamento nome_normalizado -> _id
    """
    col_contratos = db[COLLECTION_CONTRATOS]
    contratos = list(col_contratos.find({}, {"_id": 1, "nome": 1}))
    
    mapeamento = {}
    for contrato in contratos:
        nome = contrato.get("nome", "")
        if nome:
            nome_norm = normalizar_texto(nome)
            mapeamento[nome_norm] = contrato["_id"]
            # Também adicionar versões alternativas
            # Ex: "DSEI PVH" também pode aparecer como "DSEI PORTO VELHO"
    
    return mapeamento


def buscar_contrato_por_nome(
    nome_contrato: str, 
    mapeamento_contratos: Dict[str, ObjectId],
    db
) -> Optional[ObjectId]:
    """
    Busca o contrato_id pelo nome do contrato.
    Tenta match exato primeiro, depois busca parcial.
    """
    if not nome_contrato:
        return None
    
    # Verificar mapeamento especial primeiro (case insensitive)
    nome_upper = nome_contrato.upper()
    nome_mapeado = MAPEAMENTO_ESPECIAL.get(nome_upper, nome_contrato)
    
    # Remover sufixos para busca
    sufixos_remover = [
        " - COZINHA",
        " - MOTORISTA",
        " - MOTORISTAS", 
        " - LIMPEZA",
        " - LAVANDERIA",
        " - ADMINISTRATIVO",
        " - BARQUEIROS",
    ]
    
    nome_busca = nome_mapeado
    for sufixo in sufixos_remover:
        if sufixo in nome_busca.upper():
            nome_busca = nome_busca.upper().replace(sufixo, "")
            break
    
    nome_norm = normalizar_texto(nome_busca)
    
    # Tentar match exato primeiro
    if nome_norm in mapeamento_contratos:
        return mapeamento_contratos[nome_norm]
    
    # Tentar match parcial (contrato contém o nome ou vice-versa)
    for contrato_nome, contrato_id in mapeamento_contratos.items():
        if nome_norm in contrato_nome or contrato_nome in nome_norm:
            return contrato_id
    
    # Buscar diretamente no banco com regex
    col_contratos = db[COLLECTION_CONTRATOS]
    import re
    regex = re.compile(re.escape(nome_busca), re.IGNORECASE)
    contrato = col_contratos.find_one({"nome": {"$regex": regex}})
    
    if contrato:
        return contrato["_id"]
    
    return None


# ==================== FUNÇÃO PRINCIPAL ====================

def vincular_diretorios_contratos(db, dry_run: bool = False) -> Dict[str, int]:
    """
    Vincula cada diretório ao seu contrato correspondente.
    """
    print("\n" + "=" * 60)
    print("  VINCULAÇÃO: Diretórios → Contratos")
    print("=" * 60)
    
    col_diretorios = db[COLLECTION_DIRETORIOS]
    
    # Carregar mapeamento de contratos
    mapeamento_contratos = carregar_contratos(db)
    print(f"\n📋 Contratos carregados: {len(mapeamento_contratos)}")
    
    for nome, _id in sorted(mapeamento_contratos.items()):
        print(f"    - {nome}")
    
    stats = {
        "diretorios_verificados": 0,
        "diretorios_atualizados": 0,
        "diretorios_ja_vinculados": 0,
        "diretorios_sem_contrato": 0,
        "contrato_nao_encontrado": 0,
    }
    
    # Buscar todos os diretórios
    diretorios = list(col_diretorios.find({}))
    
    print(f"\n📂 Diretórios a processar: {len(diretorios)}")
    print("\n" + "-" * 60)
    
    for diretorio in diretorios:
        stats["diretorios_verificados"] += 1
        
        dir_id = diretorio["_id"]
        caminho = diretorio.get("caminho_relativo", "")
        contrato_atual = diretorio.get("contrato_id")
        
        # Verificar se já está vinculado
        if contrato_atual:
            stats["diretorios_ja_vinculados"] += 1
            print(f"  ✓ Já vinculado: {caminho}")
            continue
        
        # Extrair nome do contrato do caminho
        nome_contrato = extrair_nome_contrato(caminho)
        
        if not nome_contrato:
            stats["diretorios_sem_contrato"] += 1
            print(f"  ⚠️ Sem contrato identificável: {caminho}")
            continue
        
        # Buscar contrato_id
        contrato_id = buscar_contrato_por_nome(nome_contrato, mapeamento_contratos, db)
        
        if not contrato_id:
            stats["contrato_nao_encontrado"] += 1
            print(f"  ❌ Contrato não encontrado: {caminho}")
            print(f"      Buscado: '{nome_contrato}'")
            continue
        
        # Atualizar diretório
        if dry_run:
            print(f"  [DRY-RUN] Vincularia: {caminho} → contrato_id={contrato_id}")
            stats["diretorios_atualizados"] += 1
        else:
            try:
                # Preparar atualização
                historico_atual = diretorio.get("historico_alteracoes", [])
                versao_atual = diretorio.get("versao", 1)
                
                entrada_historico = criar_entrada_historico(
                    "vinculacao_contrato",
                    {
                        "contrato_id": str(contrato_id),
                        "nome_contrato_extraido": nome_contrato,
                    }
                )
                
                resultado = col_diretorios.update_one(
                    {"_id": dir_id},
                    {
                        "$set": {
                            "contrato_id": contrato_id,
                            "versao": versao_atual + 1,
                            "atualizado_em": datetime.now(timezone.utc),
                        },
                        "$push": {
                            "historico_alteracoes": entrada_historico
                        }
                    }
                )
                
                if resultado.modified_count > 0:
                    stats["diretorios_atualizados"] += 1
                    print(f"  ✓ Vinculado: {caminho} → {nome_contrato}")
                    
            except Exception as e:
                print(f"  ✗ Erro ao vincular {caminho}: {e}")
    
    # Resumo
    print("\n" + "=" * 60)
    print("  RESUMO")
    print("=" * 60)
    print(f"\n📊 Estatísticas:")
    print(f"   Diretórios verificados: {stats['diretorios_verificados']}")
    print(f"   Diretórios atualizados: {stats['diretorios_atualizados']}")
    print(f"   Já vinculados: {stats['diretorios_ja_vinculados']}")
    print(f"   Sem contrato (ex: FOLGUISTAS): {stats['diretorios_sem_contrato']}")
    print(f"   Contrato não encontrado: {stats['contrato_nao_encontrado']}")
    
    return stats


def criar_indice_contrato_id(db, dry_run: bool = False) -> None:
    """Cria índice (não único) em contrato_id para melhor performance"""
    print("\n" + "=" * 60)
    print("  ÍNDICES")
    print("=" * 60)
    
    if dry_run:
        print("  [DRY-RUN] Criaria índice: contrato_id (não único)")
        return
    
    col_diretorios = db[COLLECTION_DIRETORIOS]
    
    try:
        col_diretorios.create_index(
            [("contrato_id", 1)],
            sparse=True,
            name="idx_contrato_id"
        )
        print("  ✓ Índice criado: contrato_id (sparse, não único)")
    except Exception as e:
        if "already exists" in str(e).lower():
            print("  ✓ Índice já existe: contrato_id")
        else:
            print(f"  ⚠️ Erro ao criar índice: {e}")


# ==================== MAIN ====================

def main():
    parser = argparse.ArgumentParser(
        description="Vincular diretórios aos contratos correspondentes"
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
    print("  VINCULAÇÃO: Diretórios → Contratos")
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
        # Vincular diretórios aos contratos
        stats = vincular_diretorios_contratos(db, dry_run=args.dry_run)
        
        # Criar índice
        criar_indice_contrato_id(db, dry_run=args.dry_run)
        
    except Exception as e:
        print(f"\n❌ Erro durante execução: {e}")
        logger.exception("Erro na vinculação")
        return 1
    finally:
        cliente.close()
    
    # Resumo final
    print("\n" + "=" * 60)
    if args.dry_run:
        print("⚠️  MODO DRY-RUN: Execute sem --dry-run para aplicar")
    else:
        print("✅ Vinculação concluída!")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
