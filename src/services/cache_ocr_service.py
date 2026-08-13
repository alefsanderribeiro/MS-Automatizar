"""
Serviço de Cache OCR com MongoDB
Armazena hashes de imagens e resultados de OCR em MongoDB
Reduz chamadas desnecessárias ao OCR para mesmas imagens

Este módulo também re-exporta os serviços de outros módulos para
manter compatibilidade com código legado.
"""

import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import dotenv

from src.utils.logger_config import logger
from src.utils.dotenv_path import caminho_dotenv
from src.services.mongodb_connection import MongoDBConnectionPool, retry_mongodb, medir_tempo

# Re-exportar serviços de outros módulos para compatibilidade
from src.services.folha_ponto_service import (
    FolhaDePontoService,
    ResultadoSalvamento,
    folha_de_ponto_service,
    MONGODB_DISPONIVEL
)
from src.services.funcionario_service import (
    FuncionarioService,
    funcionario_service
)
from src.services.empresa_service import (
    EmpresaService,
    empresa_service
)

try:
    from pymongo import ASCENDING
    _MONGODB_DISPONIVEL = True
except ImportError:
    _MONGODB_DISPONIVEL = False
    logger.warning("PyMongo não instalado. Instale com: pip install pymongo")


class CacheOCRMongoDB:
    """
    Gerencia cache de OCR usando MongoDB
    
    Armazena:
    - Hash SHA256 da imagem
    - Resultado do OCR
    - Data/hora do processamento
    - Nome do arquivo (para referência)
    
    Benefícios:
    - Evita OCR duplicado de mesmas imagens
    - Persiste dados entre execuções
    - Fácil consulta e estatísticas
    - Escalável
    """
    
    def __init__(self, collection_name: str = "cache_ocr"):
        """
        Inicializa serviço de cache OCR usando pool centralizado.

        Args:
            collection_name: Nome da coleção para cache
        """
        # Armazenar informações do .env para referência
        self.mongo_uri = dotenv.get_key(caminho_dotenv(), "MONGO_URI") or "mongodb://localhost:27017"
        self.db_name = dotenv.get_key(caminho_dotenv(), "MONGO_DATABASE_NAME") or "MS_Automatizar"
        self.collection_name = collection_name

        if not _MONGODB_DISPONIVEL:
            logger.error(
                "MongoDB não disponível. "
                "Instale PyMongo com: pip install pymongo"
            )
            self.pool = None
            self.db = None
            self.colecao = None
            self._disponivel = False
            return

        try:
            # Usar pool centralizado
            self.pool = MongoDBConnectionPool()
            self.db = self.pool.get_database()

            if self.db is None:
                logger.error("Banco de dados não disponível no pool MongoDB")
                self._disponivel = False
                return

            self.colecao = self.db[collection_name]

            # Criar índices para melhor performance
            self._criar_indices()
            
            self._disponivel = True
            logger.debug(
                f"✓ CacheOCRMongoDB inicializado (usando pool centralizado)"
            )

        except Exception as e:
            logger.error(f"✗ Erro ao inicializar CacheOCRMongoDB: {e}")
            self.pool = None
            self.db = None
            self.colecao = None
            self._disponivel = False
    
    @property
    def disponivel(self) -> bool:
        """Verifica se MongoDB está disponível"""
        return self._disponivel
    
    def _criar_indices(self) -> None:
        """Cria índices na coleção para melhor performance"""
        try:
            # Índice no hash da imagem (busca rápida)
            self.colecao.create_index([("hash_imagem", ASCENDING)], unique=True)
            logger.debug("✓ Índices criados em MongoDB")
        except Exception as e:
            logger.warning(f"Erro ao criar índices: {e}")
    
    def _calcular_hash_imagem(self, imagem_path: Path) -> str:
        """
        Calcula hash SHA256 da imagem
        
        Args:
            imagem_path: Caminho para o arquivo de imagem
        
        Returns:
            Hash SHA256 em hexadecimal
        """
        imagem_path = Path(imagem_path)
        
        if not imagem_path.exists():
            raise FileNotFoundError(f"Imagem não encontrada: {imagem_path}")
        
        try:
            sha256_hash = hashlib.sha256()
            
            # Ler arquivo em chunks para não carregá-lo todo na memória
            with open(imagem_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            
            hash_resultado = sha256_hash.hexdigest()
            logger.debug(f"Hash calculado para {imagem_path.name}: {hash_resultado}")
            
            return hash_resultado
        
        except Exception as e:
            logger.error(f"Erro ao calcular hash: {e}")
            raise
    
    def obter_ocr(self, imagem_path: Path) -> Optional[str]:
        """
        Obtém resultado do OCR do cache se existir
        
        Args:
            imagem_path: Caminho para a imagem
        
        Returns:
            Texto do OCR se encontrado no cache, None caso contrário
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível, cache desabilitado")
            return None
        
        try:
            imagem_path = Path(imagem_path)
            hash_imagem = self._calcular_hash_imagem(imagem_path)
            
            # Buscar no cache
            documento = self.colecao.find_one({"hash_imagem": hash_imagem})
            
            if documento:
                logger.info(
                    f"✓ CACHE HIT: {imagem_path.name} "
                    f"(armazenado em {documento['data_criacao']})"
                )
                return documento.get("resultado_ocr")
            else:
                logger.debug(f"✗ Cache miss para {imagem_path.name}")
                return None
        
        except Exception as e:
            logger.error(f"Erro ao buscar OCR em cache: {e}")
            return None
    
    def salvar_ocr(self, imagem_path: Path, resultado_ocr: str) -> bool:
        """
        Salva resultado do OCR em cache
        
        Args:
            imagem_path: Caminho para a imagem
            resultado_ocr: Texto extraído pelo OCR
        
        Returns:
            True se salvo com sucesso, False caso contrário
        """
        if not self.disponivel:
            logger.warning("MongoDB não disponível, cache desabilitado")
            return False
        
        try:
            imagem_path = Path(imagem_path)
            hash_imagem = self._calcular_hash_imagem(imagem_path)
            
            documento = {
                "hash_imagem": hash_imagem,
                "nome_arquivo": imagem_path.name,
                "caminho_arquivo": str(imagem_path),
                "resultado_ocr": resultado_ocr,
                "data_criacao": datetime.now(timezone.utc),
                "tamanho_arquivo": imagem_path.stat().st_size
            }
            
            # Inserir ou atualizar
            resultado = self.colecao.update_one(
                {"hash_imagem": hash_imagem},
                {"$set": documento},
                upsert=True
            )
            
            if resultado.upserted_id or resultado.modified_count > 0:
                logger.info(
                    f"✓ OCR armazenado em cache: {imagem_path.name} "
                    f"(hash: {hash_imagem[:12]}...)"
                )
                return True
            else:
                logger.debug("Documento já existia no cache")
                return True
        
        except Exception as e:
            logger.error(f"Erro ao salvar OCR em cache: {e}")
            return False
    
    def obter_info_cache(self, imagem_path: Path) -> Optional[Dict[str, Any]]:
        """
        Obtém informações completas do documento em cache
        
        Args:
            imagem_path: Caminho para a imagem
        
        Returns:
            Dicionário com informações do cache ou None
        """
        if not self.disponivel:
            return None
        
        try:
            imagem_path = Path(imagem_path)
            hash_imagem = self._calcular_hash_imagem(imagem_path)
            
            documento = self.colecao.find_one(
                {"hash_imagem": hash_imagem},
                {"_id": 0}  # Excluir ID do MongoDB
            )
            
            return documento
        
        except Exception as e:
            logger.error(f"Erro ao obter info do cache: {e}")
            return None
    
    def listar_cache(self, limite: int = 10) -> list:
        """
        Lista últimos documentos adicionados ao cache
        
        Args:
            limite: Número máximo de documentos a retornar
        
        Returns:
            Lista de documentos
        """
        if not self.disponivel:
            return []
        
        try:
            documentos = list(
                self.colecao.find(
                    {},
                    {"_id": 0}
                ).sort("data_criacao", -1).limit(limite)
            )
            return documentos
        
        except Exception as e:
            logger.error(f"Erro ao listar cache: {e}")
            return []
    
    def limpar_cache_antigo(self, dias: int = 30) -> int:
        """
        Remove documentos de cache mais antigos que N dias
        
        Args:
            dias: Número de dias (padrão: 30)
        
        Returns:
            Número de documentos removidos
        """
        if not self.disponivel:
            return 0
        
        try:
            from datetime import timedelta
            
            data_limite = datetime.now(timezone.utc) - timedelta(days=dias)
            
            resultado = self.colecao.delete_many(
                {"data_criacao": {"$lt": data_limite}}
            )
            
            logger.info(f"✓ Cache limpo: {resultado.deleted_count} documentos removidos")
            return resultado.deleted_count
        
        except Exception as e:
            logger.error(f"Erro ao limpar cache: {e}")
            return 0
    
    def limpar_tudo(self) -> bool:
        """
        Limpa todo o cache (remove todos os documentos da coleção)
        
        Returns:
            True se bem-sucedido
        """
        if not self.disponivel:
            return False
        
        try:
            resultado = self.colecao.delete_many({})
            logger.info(f"✓ Cache limpo completamente: {resultado.deleted_count} documentos removidos")
            return True
        
        except Exception as e:
            logger.error(f"Erro ao limpar cache: {e}")
            return False
    
    def obter_estatisticas(self) -> Dict[str, Any]:
        """
        Retorna estatísticas do cache
        
        Returns:
            Dicionário com estatísticas
        """
        if not self.disponivel:
            return {
                'status': 'MongoDB indisponível',
                'total_documentos': 0,
                'tamanho_total_mb': 0
            }
        
        try:
            total_documentos = self.colecao.count_documents({})
            
            # Calcular tamanho total das imagens
            pipeline = [
                {
                    "$group": {
                        "_id": None,
                        "tamanho_total": {"$sum": "$tamanho_arquivo"}
                    }
                }
            ]
            
            resultado = list(self.colecao.aggregate(pipeline))
            tamanho_total = resultado[0]['tamanho_total'] if resultado else 0
            
            # Contar documentos por nome de arquivo (para análise)
            pipeline_nomes = [
                {
                    "$group": {
                        "_id": "$nome_arquivo",
                        "count": {"$sum": 1}
                    }
                }
            ]
            
            nomes_count = {
                doc['_id']: doc['count'] 
                for doc in self.colecao.aggregate(pipeline_nomes)
            }
            
            stats = {
                'status': 'OK' if self.disponivel else 'Erro',
                'total_documentos': total_documentos,
                'tamanho_total_mb': round(tamanho_total / (1024 * 1024), 2),
                'banco_dados': self.db_name,
                'colecao': self.collection_name,
                'arquivos_unicos': len(nomes_count),
                'mongo_uri': self.mongo_uri
            }
            
            logger.info(f"Estatísticas do cache: {total_documentos} documentos, {stats['tamanho_total_mb']} MB")
            return stats
        
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {
                'status': 'Erro ao obter estatísticas',
                'erro': str(e)
            }
    
    def desconectar(self) -> None:
        """Desconecta do MongoDB (não necessário com pool centralizado)"""
        logger.debug("desconectar() chamado - pool centralizado gerencia conexões")


# Instância global do cache
cache_ocr = CacheOCRMongoDB() if _MONGODB_DISPONIVEL else None
