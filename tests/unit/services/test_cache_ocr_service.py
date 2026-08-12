"""Testes unitarios para o modulo cache_ocr_service.py"""

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch


class TestCacheOCRMongoDBInit:
    """Testes para inicializacao do CacheOCRMongoDB"""

    def test_init_sucesso_com_mongodb_disponivel(self, mock_env_vars):
        """Testa inicializacao bem-sucedida quando MongoDB esta disponivel"""
        with patch("src.services.cache_ocr_service.MONGODB_DISPONIVEL", True) as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_instance.__getitem__.return_value = mock_db

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            assert cache.disponivel is True

    def test_init_falha_conexao_mongodb(self, mock_env_vars):
        """Testa inicializacao quando MongoDB nao esta disponivel"""
        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            from pymongo.errors import ConnectionFailure
            mock_client.side_effect = ConnectionFailure("Erro de conexao")

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            assert cache.disponivel is False

    def test_disponivel_property(self, mock_env_vars):
        """Testa propriedade disponivel"""
        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_instance.__getitem__.return_value = mock_db

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            assert isinstance(cache.disponivel, bool)


class TestCalcularHashImagem:
    """Testes para calculo de hash de imagem"""

    def test_calcular_hash_arquivo_valido(self, tmp_path, mock_env_vars):
        """Testa calculo de hash para arquivo valido"""
        arquivo = tmp_path / "test_image.png"
        arquivo.write_bytes(b"conteudo de teste")

        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}
            mock_db = MagicMock()
            mock_instance.__getitem__.return_value = mock_db

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            hash_resultado = cache._calcular_hash_imagem(arquivo)

            assert hash_resultado is not None
            assert len(hash_resultado) == 64

    def test_calcular_hash_arquivo_nao_existe(self, mock_env_vars):
        """Testa erro quando arquivo nao existe"""
        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}
            mock_db = MagicMock()
            mock_instance.__getitem__.return_value = mock_db

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            with pytest.raises(FileNotFoundError):
                cache._calcular_hash_imagem(Path("arquivo_inexistente.png"))

    def test_calcular_hash_arquivo_vazio(self, tmp_path, mock_env_vars):
        """Testa hash de arquivo vazio"""
        arquivo = tmp_path / "empty.png"
        arquivo.write_bytes(b"")

        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}
            mock_db = MagicMock()
            mock_instance.__getitem__.return_value = mock_db

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            hash_resultado = cache._calcular_hash_imagem(arquivo)

            assert hash_resultado is not None
            assert len(hash_resultado) == 64


class TestObterOCR:
    """Testes para obter OCR do cache"""

    def test_obter_ocr_cache_hit(self, tmp_path, mock_env_vars):
        """Testa obtencao de OCR quando esta no cache"""
        arquivo = tmp_path / "image.png"
        arquivo.write_bytes(b"test")

        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection

            mock_doc = {
                "hash_imagem": "abc123",
                "resultado_ocr": "Texto extraido",
                "data_criacao": datetime.now(timezone.utc)
            }
            mock_collection.find_one.return_value = mock_doc

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()
            cache.colecao = mock_collection

            resultado = cache.obter_ocr(arquivo)

            assert resultado == "Texto extraido"

    def test_obter_ocr_cache_miss(self, tmp_path, mock_env_vars):
        """Testa quando OCR nao esta no cache"""
        arquivo = tmp_path / "image.png"
        arquivo.write_bytes(b"test")

        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection
            mock_collection.find_one.return_value = None

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()
            cache.colecao = mock_collection

            resultado = cache.obter_ocr(arquivo)

            assert resultado is None

    def test_obter_ocr_mongodb_indisponivel(self, tmp_path, mock_env_vars):
        """Testa quando MongoDB esta indisponivel"""
        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            from pymongo.errors import ConnectionFailure
            mock_client.side_effect = ConnectionFailure("Erro")

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            arquivo = tmp_path / "image.png"
            arquivo.write_bytes(b"test")

            resultado = cache.obter_ocr(arquivo)
            assert resultado is None


class TestSalvarOCR:
    """Testes para salvar OCR no cache"""

    def test_salvar_ocr_insercao_sucesso(self, tmp_path, mock_env_vars):
        """Testa salvamento bem-sucedido de novo OCR"""
        arquivo = tmp_path / "image.png"
        arquivo.write_bytes(b"test")

        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection

            mock_result = MagicMock()
            mock_result.upserted_id = "abc123"
            mock_collection.update_one.return_value = mock_result

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()
            cache.colecao = mock_collection

            resultado = cache.salvar_ocr(arquivo, "Texto OCR")

            assert resultado is True

    def test_salvar_ocr_mongodb_indisponivel(self, tmp_path, mock_env_vars):
        """Testa salvamento quando MongoDB esta indisponivel"""
        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            from pymongo.errors import ConnectionFailure
            mock_client.side_effect = ConnectionFailure("Erro")

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            arquivo = tmp_path / "image.png"
            arquivo.write_bytes(b"test")

            resultado = cache.salvar_ocr(arquivo, "Texto OCR")
            assert resultado is False


class TestObterInfoCache:
    """Testes para obter informacoes completas do cache"""

    def test_obter_info_cache_documento_encontrado(self, tmp_path, mock_env_vars):
        """Testa obtencao de documento completo do cache"""
        arquivo = tmp_path / "image.png"
        arquivo.write_bytes(b"test")

        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection

            mock_doc = {
                "hash_imagem": "abc123",
                "resultado_ocr": "Texto",
                "data_criacao": datetime.now(timezone.utc)
            }
            mock_collection.find_one.return_value = mock_doc

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()
            cache.colecao = mock_collection

            resultado = cache.obter_info_cache(arquivo)

            assert resultado is not None
            assert "hash_imagem" in resultado

    def test_obter_info_cache_documento_nao_encontrado(self, tmp_path, mock_env_vars):
        """Testa quando documento nao existe no cache"""
        arquivo = tmp_path / "image.png"
        arquivo.write_bytes(b"test")

        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection
            mock_collection.find_one.return_value = None

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()
            cache.colecao = mock_collection

            resultado = cache.obter_info_cache(arquivo)

            assert resultado is None


class TestListarCache:
    """Testes para listar documentos do cache"""

    def test_listar_cache_com_limite(self, mock_env_vars):
        """Testa listagem com limite de documentos"""
        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection

            mock_cursor = MagicMock()
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.limit.return_value = [{"hash_imagem": "abc1"}]
            mock_collection.find.return_value = mock_cursor

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()
            cache.colecao = mock_collection

            resultado = cache.listar_cache(limite=2)

            assert isinstance(resultado, list)

    def test_listar_cache_mongodb_indisponivel(self, mock_env_vars):
        """Testa listagem quando MongoDB esta indisponivel"""
        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            from pymongo.errors import ConnectionFailure
            mock_client.side_effect = ConnectionFailure("Erro")

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            resultado = cache.listar_cache()
            assert resultado == []


class TestLimparCacheAntigo:
    """Testes para limpeza de cache antigo"""

    def test_limpar_cache_antigo_sucesso(self, mock_env_vars):
        """Testa limpeza de documentos antigos"""
        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection

            mock_result = MagicMock()
            mock_result.deleted_count = 5
            mock_collection.delete_many.return_value = mock_result

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()
            cache.colecao = mock_collection

            resultado = cache.limpar_cache_antigo(dias=30)

            assert resultado == 5

    def test_limpar_cache_antigo_mongodb_indisponivel(self, mock_env_vars):
        """Testa limpeza quando MongoDB esta indisponivel"""
        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            from pymongo.errors import ConnectionFailure
            mock_client.side_effect = ConnectionFailure("Erro")

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            resultado = cache.limpar_cache_antigo(dias=30)
            assert resultado == 0


class TestLimparTudo:
    """Testes para limpeza total do cache"""

    def test_limpar_tudo_sucesso(self, mock_env_vars):
        """Testa limpeza de todos os documentos"""
        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection

            mock_result = MagicMock()
            mock_result.deleted_count = 100
            mock_collection.delete_many.return_value = mock_result

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()
            cache.colecao = mock_collection

            resultado = cache.limpar_tudo()

            assert resultado is True

    def test_limpar_tudo_mongodb_indisponivel(self, mock_env_vars):
        """Testa limpeza quando MongoDB esta indisponivel"""
        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            from pymongo.errors import ConnectionFailure
            mock_client.side_effect = ConnectionFailure("Erro")

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            resultado = cache.limpar_tudo()
            assert resultado is False


class TestObterEstatisticas:
    """Testes para obter estatisticas do cache"""

    def test_obter_estatisticas_sucesso(self, mock_env_vars):
        """Testa obtencao de estatisticas"""
        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection

            mock_collection.count_documents.return_value = 50
            mock_collection.aggregate.return_value = [{"tamanho_total": 1024000}]

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()
            cache.colecao = mock_collection

            resultado = cache.obter_estatisticas()

            assert "total_documentos" in resultado
            assert resultado["total_documentos"] == 50

    def test_obter_estatisticas_mongodb_indisponivel(self, mock_env_vars):
        """Testa estatisticas quando MongoDB esta indisponivel"""
        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            from pymongo.errors import ConnectionFailure
            mock_client.side_effect = ConnectionFailure("Erro")

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            resultado = cache.obter_estatisticas()

            assert resultado["total_documentos"] == 0


class TestDesconectar:
    """Testes para desconexao do MongoDB"""

    def test_desconectar_sucesso(self, mock_env_vars):
        """Testa desconexao bem-sucedida"""
        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_instance.__getitem__.return_value = mock_db

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            cache.desconectar()

            mock_instance.close.assert_called_once()

    def test_desconectar_mongodb_indisponivel(self, mock_env_vars):
        """Testa desconexao quando MongoDB esta indisponivel"""
        with patch("src.services.cache_ocr_service.MongoClient") as mock_client:
            from pymongo.errors import ConnectionFailure
            mock_client.side_effect = ConnectionFailure("Erro")

            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            # Nao deve lancar excecao
            cache.desconectar()
