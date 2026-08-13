"""Testes unitarios para o modulo cache_ocr_service.py"""

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch


@pytest.fixture
def mock_mongodb_pool():
    """
    Mock do MongoDBConnectionPool centralizado (padrão pós-refactor).

    O CacheOCRMongoDB agora usa o pool singleton de mongodb_connection.py em
    vez de criar um MongoClient diretamente. Este fixture:
    - Força _MONGODB_DISPONIVEL=True no módulo do serviço;
    - Patcheia MongoDBConnectionPool para retornar um pool mockado cujo
      get_database() devolve um banco (db) mockado.

    Returns:
        Tupla (mock_pool, mock_db)
    """
    mock_db = MagicMock()
    mock_client = MagicMock()
    mock_client.admin.command.return_value = {"ok": 1}

    mock_pool = MagicMock()
    mock_pool.get_database.return_value = mock_db
    mock_pool.get_client.return_value = mock_client
    mock_pool.disponivel = True

    with patch("src.services.cache_ocr_service._MONGODB_DISPONIVEL", True), \
         patch("src.services.cache_ocr_service.MongoDBConnectionPool", return_value=mock_pool):
        yield mock_pool, mock_db


class TestCacheOCRMongoDBInit:
    """Testes para inicializacao do CacheOCRMongoDB"""

    def test_init_sucesso_com_mongodb_disponivel(self, mock_env_vars, mock_mongodb_pool):
        """Testa inicializacao bem-sucedida quando MongoDB esta disponivel"""
        from src.services.cache_ocr_service import CacheOCRMongoDB
        cache = CacheOCRMongoDB()

        assert cache.disponivel is True

    def test_init_falha_conexao_mongodb(self, mock_env_vars):
        """Testa inicializacao quando MongoDB nao esta disponivel (flag desligada)"""
        with patch("src.services.cache_ocr_service._MONGODB_DISPONIVEL", False):
            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            assert cache.disponivel is False

    def test_init_falha_quando_pool_retorna_db_none(self, mock_env_vars):
        """Testa inicializacao quando o pool nao devolve banco (conexao falhou)"""
        mock_pool = MagicMock()
        mock_pool.get_database.return_value = None

        with patch("src.services.cache_ocr_service._MONGODB_DISPONIVEL", True), \
             patch("src.services.cache_ocr_service.MongoDBConnectionPool", return_value=mock_pool):
            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            assert cache.disponivel is False

    def test_disponivel_property(self, mock_env_vars, mock_mongodb_pool):
        """Testa propriedade disponivel"""
        from src.services.cache_ocr_service import CacheOCRMongoDB
        cache = CacheOCRMongoDB()

        assert isinstance(cache.disponivel, bool)


class TestCalcularHashImagem:
    """Testes para calculo de hash de imagem"""

    def test_calcular_hash_arquivo_valido(self, tmp_path, mock_env_vars, mock_mongodb_pool):
        """Testa calculo de hash para arquivo valido"""
        arquivo = tmp_path / "test_image.png"
        arquivo.write_bytes(b"conteudo de teste")

        from src.services.cache_ocr_service import CacheOCRMongoDB
        cache = CacheOCRMongoDB()

        hash_resultado = cache._calcular_hash_imagem(arquivo)

        assert hash_resultado is not None
        assert len(hash_resultado) == 64

    def test_calcular_hash_arquivo_nao_existe(self, mock_env_vars, mock_mongodb_pool):
        """Testa erro quando arquivo nao existe"""
        from src.services.cache_ocr_service import CacheOCRMongoDB
        cache = CacheOCRMongoDB()

        with pytest.raises(FileNotFoundError):
            cache._calcular_hash_imagem(Path("arquivo_inexistente.png"))

    def test_calcular_hash_arquivo_vazio(self, tmp_path, mock_env_vars, mock_mongodb_pool):
        """Testa hash de arquivo vazio"""
        arquivo = tmp_path / "empty.png"
        arquivo.write_bytes(b"")

        from src.services.cache_ocr_service import CacheOCRMongoDB
        cache = CacheOCRMongoDB()

        hash_resultado = cache._calcular_hash_imagem(arquivo)

        assert hash_resultado is not None
        assert len(hash_resultado) == 64


class TestObterOCR:
    """Testes para obter OCR do cache"""

    def test_obter_ocr_cache_hit(self, tmp_path, mock_env_vars, mock_mongodb_pool):
        """Testa obtencao de OCR quando esta no cache"""
        arquivo = tmp_path / "image.png"
        arquivo.write_bytes(b"test")

        mock_collection = MagicMock()
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

    def test_obter_ocr_cache_miss(self, tmp_path, mock_env_vars, mock_mongodb_pool):
        """Testa quando OCR nao esta no cache"""
        arquivo = tmp_path / "image.png"
        arquivo.write_bytes(b"test")

        mock_collection = MagicMock()
        mock_collection.find_one.return_value = None

        from src.services.cache_ocr_service import CacheOCRMongoDB
        cache = CacheOCRMongoDB()
        cache.colecao = mock_collection

        resultado = cache.obter_ocr(arquivo)

        assert resultado is None

    def test_obter_ocr_mongodb_indisponivel(self, tmp_path, mock_env_vars):
        """Testa quando MongoDB esta indisponivel"""
        with patch("src.services.cache_ocr_service._MONGODB_DISPONIVEL", False):
            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            arquivo = tmp_path / "image.png"
            arquivo.write_bytes(b"test")

            resultado = cache.obter_ocr(arquivo)
            assert resultado is None


class TestSalvarOCR:
    """Testes para salvar OCR no cache"""

    def test_salvar_ocr_insercao_sucesso(self, tmp_path, mock_env_vars, mock_mongodb_pool):
        """Testa salvamento bem-sucedido de novo OCR"""
        arquivo = tmp_path / "image.png"
        arquivo.write_bytes(b"test")

        mock_collection = MagicMock()
        mock_result = MagicMock()
        mock_result.upserted_id = "abc123"
        mock_result.modified_count = 1
        mock_collection.update_one.return_value = mock_result

        from src.services.cache_ocr_service import CacheOCRMongoDB
        cache = CacheOCRMongoDB()
        cache.colecao = mock_collection

        resultado = cache.salvar_ocr(arquivo, "Texto OCR")

        assert resultado is True

    def test_salvar_ocr_mongodb_indisponivel(self, tmp_path, mock_env_vars):
        """Testa salvamento quando MongoDB esta indisponivel"""
        with patch("src.services.cache_ocr_service._MONGODB_DISPONIVEL", False):
            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            arquivo = tmp_path / "image.png"
            arquivo.write_bytes(b"test")

            resultado = cache.salvar_ocr(arquivo, "Texto OCR")
            assert resultado is False


class TestObterInfoCache:
    """Testes para obter informacoes completas do cache"""

    def test_obter_info_cache_documento_encontrado(self, tmp_path, mock_env_vars, mock_mongodb_pool):
        """Testa obtencao de documento completo do cache"""
        arquivo = tmp_path / "image.png"
        arquivo.write_bytes(b"test")

        mock_collection = MagicMock()
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

    def test_obter_info_cache_documento_nao_encontrado(self, tmp_path, mock_env_vars, mock_mongodb_pool):
        """Testa quando documento nao existe no cache"""
        arquivo = tmp_path / "image.png"
        arquivo.write_bytes(b"test")

        mock_collection = MagicMock()
        mock_collection.find_one.return_value = None

        from src.services.cache_ocr_service import CacheOCRMongoDB
        cache = CacheOCRMongoDB()
        cache.colecao = mock_collection

        resultado = cache.obter_info_cache(arquivo)

        assert resultado is None


class TestListarCache:
    """Testes para listar documentos do cache"""

    def test_listar_cache_com_limite(self, mock_env_vars, mock_mongodb_pool):
        """Testa listagem com limite de documentos"""
        mock_collection = MagicMock()
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
        with patch("src.services.cache_ocr_service._MONGODB_DISPONIVEL", False):
            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            resultado = cache.listar_cache()
            assert resultado == []


class TestLimparCacheAntigo:
    """Testes para limpeza de cache antigo"""

    def test_limpar_cache_antigo_sucesso(self, mock_env_vars, mock_mongodb_pool):
        """Testa limpeza de documentos antigos"""
        mock_collection = MagicMock()
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
        with patch("src.services.cache_ocr_service._MONGODB_DISPONIVEL", False):
            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            resultado = cache.limpar_cache_antigo(dias=30)
            assert resultado == 0


class TestLimparTudo:
    """Testes para limpeza total do cache"""

    def test_limpar_tudo_sucesso(self, mock_env_vars, mock_mongodb_pool):
        """Testa limpeza de todos os documentos"""
        mock_collection = MagicMock()
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
        with patch("src.services.cache_ocr_service._MONGODB_DISPONIVEL", False):
            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            resultado = cache.limpar_tudo()
            assert resultado is False


class TestObterEstatisticas:
    """Testes para obter estatisticas do cache"""

    def test_obter_estatisticas_sucesso(self, mock_env_vars, mock_mongodb_pool):
        """Testa obtencao de estatisticas"""
        mock_collection = MagicMock()
        mock_collection.count_documents.return_value = 50

        def mock_aggregate(pipeline, **kwargs):
            if pipeline and pipeline[0].get("$group", {}).get("_id") is None:
                return [{"tamanho_total": 1024000}]
            return []
        mock_collection.aggregate.side_effect = mock_aggregate

        from src.services.cache_ocr_service import CacheOCRMongoDB
        cache = CacheOCRMongoDB()
        cache.colecao = mock_collection

        resultado = cache.obter_estatisticas()

        assert "total_documentos" in resultado
        assert resultado["total_documentos"] == 50

    def test_obter_estatisticas_mongodb_indisponivel(self, mock_env_vars):
        """Testa estatisticas quando MongoDB esta indisponivel"""
        with patch("src.services.cache_ocr_service._MONGODB_DISPONIVEL", False):
            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            resultado = cache.obter_estatisticas()

            assert resultado["total_documentos"] == 0


class TestDesconectar:
    """Testes para desconexao do MongoDB"""

    def test_desconectar_sucesso(self, mock_env_vars, mock_mongodb_pool):
        """Testa desconexao sem erros (pool centralizado gerencia conexoes)"""
        from src.services.cache_ocr_service import CacheOCRMongoDB
        cache = CacheOCRMongoDB()

        # Com pool centralizado, desconectar() apenas loga - nao deve lancar
        cache.desconectar()

    def test_desconectar_mongodb_indisponivel(self, mock_env_vars):
        """Testa desconexao quando MongoDB esta indisponivel"""
        with patch("src.services.cache_ocr_service._MONGODB_DISPONIVEL", False):
            from src.services.cache_ocr_service import CacheOCRMongoDB
            cache = CacheOCRMongoDB()

            # Nao deve lancar excecao
            cache.desconectar()
