"""
Script de Migração: Feriados Excel → MongoDB

Este script importa os feriados do arquivo Excel para o MongoDB.
Também pode ser usado para sincronizar feriados de outras fontes.

Uso:
    uv run python scripts/migrar_feriados.py
    
    Ou via menu: Referências → Feriados → Importar do Excel
"""

import pandas as pd
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Any, List

from src.services.feriado_service import FeriadoService
from src.models.feriado_models import FeriadoMongoDB, TipoFeriado, StatusFeriado
from src.utils.logger_config import logger


# Mapeamento de nomes de feriados para tipos
MAPEAMENTO_TIPO_FERIADO = {
    # Feriados nacionais
    "confraternização universal": TipoFeriado.NACIONAL,
    "ano novo": TipoFeriado.NACIONAL,
    "tiradentes": TipoFeriado.NACIONAL,
    "dia do trabalhador": TipoFeriado.NACIONAL,
    "dia do trabalho": TipoFeriado.NACIONAL,
    "independência": TipoFeriado.NACIONAL,
    "nossa senhora aparecida": TipoFeriado.NACIONAL,
    "finados": TipoFeriado.NACIONAL,
    "proclamação da república": TipoFeriado.NACIONAL,
    "natal": TipoFeriado.NACIONAL,
    "consciência negra": TipoFeriado.NACIONAL,
    "zumbi": TipoFeriado.NACIONAL,
    
    # Feriados móveis (nacionais)
    "carnaval": TipoFeriado.NACIONAL,
    "quarta-feira de cinzas": TipoFeriado.NACIONAL,
    "sexta-feira santa": TipoFeriado.NACIONAL,
    "páscoa": TipoFeriado.NACIONAL,
    "corpus christi": TipoFeriado.NACIONAL,
    
    # Feriados estaduais RO
    "criação do estado": TipoFeriado.ESTADUAL,
    "dia do evangélico": TipoFeriado.ESTADUAL,
}


def detectar_tipo_feriado(nome: str) -> TipoFeriado:
    """Detecta o tipo do feriado baseado no nome"""
    if not nome:
        return TipoFeriado.NACIONAL
    
    nome_lower = nome.lower()
    
    for termo, tipo in MAPEAMENTO_TIPO_FERIADO.items():
        if termo in nome_lower:
            return tipo
    
    # Padrão: nacional
    return TipoFeriado.NACIONAL


def migrar_feriados_excel(
    caminho_excel: str = None,
    sheet_name: str = "Feriados",
    limpar_existentes: bool = False
) -> Dict[str, Any]:
    """
    Migra feriados do Excel para MongoDB
    
    Args:
        caminho_excel: Caminho do arquivo Excel (usa padrão se não fornecido)
        sheet_name: Nome da aba com feriados
        limpar_existentes: Se True, remove todos os feriados antes de importar
    
    Returns:
        Dict com estatísticas da migração
    """
    # Caminho padrão
    if not caminho_excel:
        caminho_excel = Path(__file__).parent.parent / "src" / "data" / "input" / "30.07.25 - 10.09 - Folha de Ponto - Alefe - Dados.xlsx"
    
    caminho = Path(caminho_excel)
    
    if not caminho.exists():
        logger.error(f"Arquivo não encontrado: {caminho}")
        return {"erro": "Arquivo não encontrado", "sucesso": 0, "erros": 0, "total": 0}
    
    # Inicializar serviço
    servico = FeriadoService()
    
    if not servico.disponivel:
        logger.error("MongoDB não disponível")
        return {"erro": "MongoDB não disponível", "sucesso": 0, "erros": 0, "total": 0}
    
    # Ler Excel
    try:
        df = pd.read_excel(caminho, sheet_name=sheet_name)
        logger.info(f"✓ Arquivo lido: {len(df)} linhas")
    except Exception as e:
        logger.error(f"Erro ao ler Excel: {e}")
        return {"erro": str(e), "sucesso": 0, "erros": 0, "total": 0}
    
    # Limpar existentes se solicitado
    if limpar_existentes:
        resultado = servico.listar_todos(limit=1000)
        for feriado in resultado.get("dados", []):
            servico.remover(str(feriado.get("_id")))
        logger.info("✓ Feriados existentes removidos")
    
    # Processar cada linha
    sucesso = 0
    erros = 0
    ignorados = 0
    detalhes = []
    
    # Detectar colunas (flexível para diferentes formatos)
    col_data = None
    col_nome = None
    
    for col in df.columns:
        col_upper = str(col).upper()
        if "DATA" in col_upper or "DIA" == col_upper:
            col_data = col
        if "NOME" in col_upper or "FERIADO" in col_upper or "DESCRIÇÃO" in col_upper:
            col_nome = col
    
    # Fallback para colunas específicas
    if col_data is None and "DATA" in df.columns:
        col_data = "DATA"
    if col_nome is None and "NOME FERIADO" in df.columns:
        col_nome = "NOME FERIADO"
    
    if col_data is None:
        logger.error("Coluna de data não encontrada")
        return {"erro": "Coluna de data não encontrada", "sucesso": 0, "erros": 0, "total": 0}
    
    logger.info(f"Usando colunas: data='{col_data}', nome='{col_nome}'")
    
    for idx, row in df.iterrows():
        try:
            # Obter data
            data_valor = row.get(col_data)
            
            # Pular linhas sem data válida
            if pd.isna(data_valor) or data_valor is None:
                ignorados += 1
                continue
            
            # Converter data
            if isinstance(data_valor, datetime):
                data = data_valor.date()
            elif isinstance(data_valor, date):
                data = data_valor
            elif isinstance(data_valor, str):
                try:
                    data = datetime.strptime(data_valor, "%Y-%m-%d").date()
                except:
                    data = datetime.strptime(data_valor, "%d/%m/%Y").date()
            else:
                ignorados += 1
                continue
            
            # Obter nome/descrição
            nome = row.get(col_nome, "") if col_nome else ""
            if pd.isna(nome) or not nome:
                # Usar data como nome se não houver descrição
                nome = f"Feriado {data.strftime('%d/%m/%Y')}"
            
            nome = str(nome).strip()
            
            # Detectar tipo
            tipo = detectar_tipo_feriado(nome)
            
            # Criar feriado
            feriado = FeriadoMongoDB(
                data=data,
                descricao=nome,
                tipo=tipo,
                recorrente=False,  # Feriados do Excel são para datas específicas
                auto_criado=True
            )
            
            # Salvar
            resultado = servico.criar(feriado)
            
            if resultado:
                sucesso += 1
                detalhes.append(f"✓ {data.strftime('%d/%m/%Y')} - {nome}")
            else:
                # Pode já existir
                erros += 1
                detalhes.append(f"⚠ {data.strftime('%d/%m/%Y')} - {nome} (já existe?)")
        
        except Exception as e:
            erros += 1
            detalhes.append(f"✗ Linha {idx + 2}: {e}")
    
    return {
        "sucesso": sucesso,
        "erros": erros,
        "ignorados": ignorados,
        "total": sucesso + erros,
        "detalhes": detalhes
    }


def main():
    """Execução principal do script"""
    print("\n" + "=" * 60)
    print("       MIGRAÇÃO DE FERIADOS: Excel → MongoDB")
    print("=" * 60 + "\n")
    
    # Verificar arquivo
    caminho_padrao = Path(__file__).parent.parent / "src" / "data" / "input" / "30.07.25 - 10.09 - Folha de Ponto - Alefe - Dados.xlsx"
    
    print(f"📁 Arquivo: {caminho_padrao}")
    
    if not caminho_padrao.exists():
        print("❌ Arquivo não encontrado!")
        print("\nColoque o arquivo Excel em:")
        print(f"   {caminho_padrao}")
        return
    
    # Perguntar se deseja limpar existentes
    limpar = input("\nDeseja limpar feriados existentes antes de importar? [S/N]: ").strip().upper()
    limpar_existentes = limpar == "S"
    
    if limpar_existentes:
        print("\n⚠️  ATENÇÃO: Todos os feriados serão removidos e reimportados!")
        confirma = input("Confirma? [S/N]: ").strip().upper()
        if confirma != "S":
            print("Operação cancelada.")
            return
    
    print("\n⏳ Iniciando migração...")
    
    resultado = migrar_feriados_excel(
        caminho_excel=str(caminho_padrao),
        limpar_existentes=limpar_existentes
    )
    
    print("\n" + "-" * 60)
    print("📊 RESULTADO DA MIGRAÇÃO")
    print("-" * 60)
    
    if "erro" in resultado:
        print(f"\n❌ Erro: {resultado['erro']}")
    else:
        print(f"\n✅ Importados com sucesso: {resultado['sucesso']}")
        print(f"⚠️  Erros/Duplicados: {resultado['erros']}")
        print(f"⏭️  Ignorados (sem data): {resultado['ignorados']}")
        print(f"📊 Total processado: {resultado['total']}")
        
        if resultado.get("detalhes"):
            print("\n📋 Detalhes:")
            for detalhe in resultado["detalhes"][:20]:  # Limitar a 20
                print(f"   {detalhe}")
            
            if len(resultado["detalhes"]) > 20:
                print(f"   ... e mais {len(resultado['detalhes']) - 20} itens")
    
    print("\n" + "=" * 60)
    
    # Mostrar total no MongoDB
    servico = FeriadoService()
    if servico.disponivel:
        total = servico.contar()
        print(f"📅 Total de feriados no MongoDB: {total}")
    
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
