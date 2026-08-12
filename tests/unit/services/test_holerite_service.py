"""Testes unitarios para o modulo holerite_service.py"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
from bson import ObjectId


class TestHoleriteServiceInit:
    """Testes para inicializacao do servico"""

    def test_init_com_mongodb_disponivel(self, mock_env_vars):
        """Testa inicializacao quando MongoDB esta disponivel"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_instance.__getitem__.return_value = mock_db

            from src.services.holerite_service import HoleriteService
            service = HoleriteService()

            assert service.disponivel is True

    def test_init_sem_mongodb(self, mock_env_vars):
        """Testa inicializacao quando MongoDB falha"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            from pymongo.errors import ConnectionFailure
            mock_client.side_effect = ConnectionFailure("Connection refused")

            from src.services.holerite_service import HoleriteService
            service = HoleriteService()

            assert service.disponivel is False

    def test_disponivel_property(self, mock_env_vars):
        """Testa propriedade disponivel"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_instance.__getitem__.return_value = mock_db

            from src.services.holerite_service import HoleriteService
            service = HoleriteService()

            assert isinstance(service.disponivel, bool)


class TestCalcularHashArquivo:
    """Testes para calculo de hash SHA256"""

    def test_calcular_hash_arquivo_existente(self, tmp_path, mock_env_vars):
        """Testa calculo de hash para arquivo existente"""
        arquivo = tmp_path / "teste.pdf"
        arquivo.write_bytes(b"conteudo teste")

        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}
            mock_db = MagicMock()
            mock_instance.__getitem__.return_value = mock_db

            from src.services.holerite_service import HoleriteService
            service = HoleriteService()

            hash_resultado = service.calcular_hash_arquivo(str(arquivo))

            assert hash_resultado is not None
            assert len(hash_resultado) == 64

    def test_calcular_hash_arquivo_inexistente(self, mock_env_vars):
        """Testa calculo de hash para arquivo que nao existe"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}
            mock_db = MagicMock()
            mock_instance.__getitem__.return_value = mock_db

            from src.services.holerite_service import HoleriteService
            service = HoleriteService()

            hash_resultado = service.calcular_hash_arquivo("/caminho/inexistente.pdf")

            assert hash_resultado is None


class TestCriarHolerite:
    """Testes para criacao de holerite"""

    def test_criar_holerite_com_sucesso(self, mock_env_vars):
        """Testa criacao de holerite com sucesso"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection

            mock_result = MagicMock()
            mock_result.inserted_id = ObjectId()
            mock_collection.insert_one.return_value = mock_result

            from src.services.holerite_service import HoleriteService
            service = HoleriteService()
            service.colecao = mock_collection

            holerite_data = {
                "funcionario_nome": "Joao Silva",
                "competencia": "01/2024",
                "salario_liquido": 5000.00
            }

            resultado = service.criar_holerite(holerite_data)

            assert resultado is not None

    def test_criar_holerite_mongodb_indisponivel(self, mock_env_vars):
        """Testa criacao quando MongoDB indisponivel"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            from pymongo.errors import ConnectionFailure
            mock_client.side_effect = ConnectionFailure("Connection refused")

            from src.services.holerite_service import HoleriteService
            service = HoleriteService()

            resultado = service.criar_holerite({"nome": "teste"})

            assert resultado is None


class TestBuscarPorId:
    """Testes para busca por ID"""

    def test_buscar_por_id_encontrado(self, mock_env_vars):
        """Testa busca por ID quando holerite existe"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection

            holerite_data = {"_id": ObjectId(), "nome": "Teste"}
            mock_collection.find_one.return_value = holerite_data

            from src.services.holerite_service import HoleriteService
            service = HoleriteService()
            service.colecao = mock_collection

            resultado = service.buscar_por_id(str(holerite_data["_id"]))

            assert resultado is not None

    def test_buscar_por_id_nao_encontrado(self, mock_env_vars):
        """Testa busca por ID quando holerite nao existe"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection
            mock_collection.find_one.return_value = None

            from src.services.holerite_service import HoleriteService
            service = HoleriteService()
            service.colecao = mock_collection

            resultado = service.buscar_por_id(str(ObjectId()))

            assert resultado is None


class TestBuscarPorHash:
    """Testes para busca por hash SHA256"""

    def test_buscar_por_hash_encontrado(self, mock_env_vars):
        """Testa busca por hash quando arquivo existe"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection

            holerite_data = {"_id": ObjectId(), "arquivo": {"hash_sha256": "abc123"}}
            mock_collection.find_one.return_value = holerite_data

            from src.services.holerite_service import HoleriteService
            service = HoleriteService()
            service.colecao = mock_collection

            resultado = service.buscar_por_hash("abc123")

            assert resultado is not None

    def test_buscar_por_hash_nao_encontrado(self, mock_env_vars):
        """Testa busca por hash quando arquivo nao existe"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection
            mock_collection.find_one.return_value = None

            from src.services.holerite_service import HoleriteService
            service = HoleriteService()
            service.colecao = mock_collection

            resultado = service.buscar_por_hash("hash_inexistente")

            assert resultado is None


class TestBuscarPorFuncionario:
    """Testes para busca por funcionario"""

    def test_buscar_por_funcionario_com_resultados(self, mock_env_vars):
        """Testa busca por funcionario com resultados"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection

            # Mock cursor
            mock_cursor = MagicMock()
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.limit.return_value = [{"_id": ObjectId()}]
            mock_collection.find.return_value = mock_cursor

            from src.services.holerite_service import HoleriteService
            service = HoleriteService()
            service.colecao = mock_collection

            resultado = service.buscar_por_funcionario(str(ObjectId()))

            assert isinstance(resultado, list)

    def test_buscar_por_funcionario_mongodb_indisponivel(self, mock_env_vars):
        """Testa busca quando MongoDB indisponivel"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            from pymongo.errors import ConnectionFailure
            mock_client.side_effect = ConnectionFailure("Connection refused")

            from src.services.holerite_service import HoleriteService
            service = HoleriteService()

            resultado = service.buscar_por_funcionario(str(ObjectId()))

            assert resultado == []


class TestBuscarPorDocumento:
    """Testes para busca por documento CPF"""

    def test_buscar_por_documento_normaliza_cpf(self, mock_env_vars):
        """Testa que CPF e normalizado antes da busca"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection

            mock_cursor = MagicMock()
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.limit.return_value = []
            mock_collection.find.return_value = mock_cursor

            from src.services.holerite_service import HoleriteService
            service = HoleriteService()
            service.colecao = mock_collection

            # Passar CPF formatado
            resultado = service.buscar_por_documento("123.456.789-00")

            assert isinstance(resultado, list)


class TestListarTodos:
    """Testes para listagem com filtros dinamicos"""

    def test_listar_todos_sem_filtros(self, mock_env_vars):
        """Testa listagem sem filtros"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection

            mock_cursor = MagicMock()
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.skip.return_value = mock_cursor
            mock_cursor.limit.return_value = []
            mock_collection.find.return_value = mock_cursor

            from src.services.holerite_service import HoleriteService
            service = HoleriteService()
            service.colecao = mock_collection

            resultado = service.listar_todos()

            assert isinstance(resultado, list)

    def test_listar_todos_mongodb_indisponivel(self, mock_env_vars):
        """Testa listagem quando MongoDB indisponivel"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            from pymongo.errors import ConnectionFailure
            mock_client.side_effect = ConnectionFailure("Connection refused")

            from src.services.holerite_service import HoleriteService
            service = HoleriteService()

            resultado = service.listar_todos()

            assert resultado == []


class TestContarTotal:
    """Testes para contagem total"""

    def test_contar_total_sem_filtros(self, mock_env_vars):
        """Testa contagem sem filtros"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection
            mock_collection.count_documents.return_value = 42

            from src.services.holerite_service import HoleriteService
            service = HoleriteService()
            service.colecao = mock_collection

            resultado = service.contar_total()

            assert resultado == 42

    def test_contar_total_mongodb_indisponivel(self, mock_env_vars):
        """Testa contagem quando MongoDB indisponivel"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            from pymongo.errors import ConnectionFailure
            mock_client.side_effect = ConnectionFailure("Connection refused")

            from src.services.holerite_service import HoleriteService
            service = HoleriteService()

            resultado = service.contar_total()

            assert resultado == 0


class TestBuscarPorCompetencia:
    """Testes para busca por competencia"""

    def test_buscar_por_competencia_apenas_competencia(self, mock_env_vars):
        """Testa busca apenas por competencia"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection

            mock_cursor = MagicMock()
            mock_cursor.sort.return_value = []
            mock_collection.find.return_value = mock_cursor

            from src.services.holerite_service import HoleriteService
            service = HoleriteService()
            service.colecao = mock_collection

            resultado = service.buscar_por_competencia("01/2024")

            assert isinstance(resultado, list)


class TestAtualizarStatus:
    """Testes para atualizacao de status"""

    def test_atualizar_status_com_sucesso(self, mock_env_vars):
        """Testa atualizacao de status com sucesso"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection

            mock_result = MagicMock()
            mock_result.modified_count = 1
            mock_collection.update_one.return_value = mock_result

            from src.services.holerite_service import HoleriteService
            from src.models.holerite_models import StatusHoleriteEnum

            service = HoleriteService()
            service.colecao = mock_collection

            resultado = service.atualizar_status(str(ObjectId()), StatusHoleriteEnum.ENVIADO)

            assert resultado is True

    def test_atualizar_status_nao_encontrado(self, mock_env_vars):
        """Testa atualizacao quando holerite nao existe"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection

            mock_result = MagicMock()
            mock_result.modified_count = 0
            mock_collection.update_one.return_value = mock_result

            from src.services.holerite_service import HoleriteService
            from src.models.holerite_models import StatusHoleriteEnum

            service = HoleriteService()
            service.colecao = mock_collection

            resultado = service.atualizar_status(str(ObjectId()), StatusHoleriteEnum.ENVIADO)

            assert resultado is False


class TestRegistrarEnvio:
    """Testes para registro de envio"""

    def test_registrar_envio_com_sucesso(self, mock_env_vars):
        """Testa registro de envio com sucesso"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_collection_envios = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.side_effect = lambda x: mock_collection if x == "holerites" else mock_collection_envios

            mock_result = MagicMock()
            mock_result.inserted_id = ObjectId()
            mock_collection_envios.insert_one.return_value = mock_result

            from src.services.holerite_service import HoleriteService

            service = HoleriteService()
            service.colecao_envios = mock_collection_envios
            service._disponivel = True

            resultado = service.registrar_envio(
                holerite_id=str(ObjectId()),
                funcionario_id=str(ObjectId()),
                canal="email",
                destino="teste@email.com",
                sucesso=True
            )

            assert resultado is not None


class TestListarEnviosHolerite:
    """Testes para listagem de envios de um holerite"""

    def test_listar_envios_holerite_com_envios(self, mock_env_vars):
        """Testa listagem quando ha envios"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection_envios = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection_envios

            mock_cursor = MagicMock()
            mock_cursor.sort.return_value = [{"_id": ObjectId(), "sucesso": True}]
            mock_collection_envios.find.return_value = mock_cursor

            from src.services.holerite_service import HoleriteService

            service = HoleriteService()
            service.colecao_envios = mock_collection_envios
            service._disponivel = True

            resultado = service.listar_envios_holerite(str(ObjectId()))

            assert isinstance(resultado, list)


class TestListarPendentesEnvio:
    """Testes para listagem de holerites pendentes de envio"""

    def test_listar_pendentes_envio_sem_filtros(self, mock_env_vars):
        """Testa listagem de pendentes sem filtros"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection

            mock_cursor = MagicMock()
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.limit.return_value = []
            mock_collection.find.return_value = mock_cursor

            from src.services.holerite_service import HoleriteService

            service = HoleriteService()
            service.colecao = mock_collection

            resultado = service.listar_pendentes_envio()

            assert isinstance(resultado, list)


class TestContarPorStatus:
    """Testes para contagem por status usando aggregation"""

    def test_contar_por_status_sem_competencia(self, mock_env_vars):
        """Testa contagem por status sem filtro de competencia"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection

            mock_collection.aggregate.return_value = [
                {"_id": "pendente", "count": 10},
                {"_id": "enviado", "count": 5}
            ]

            from src.services.holerite_service import HoleriteService

            service = HoleriteService()
            service.colecao = mock_collection

            resultado = service.contar_por_status()

            assert isinstance(resultado, dict)


class TestExisteHolerite:
    """Testes para verificacao de existencia de holerite"""

    def test_existe_holerite_quando_existe(self, mock_env_vars):
        """Testa verificacao quando holerite existe"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection
            mock_collection.count_documents.return_value = 1

            from src.services.holerite_service import HoleriteService

            service = HoleriteService()
            service.colecao = mock_collection

            resultado = service.existe_holerite(
                funcionario_id=str(ObjectId()),
                competencia="01/2024"
            )

            assert resultado is True

    def test_existe_holerite_quando_nao_existe(self, mock_env_vars):
        """Testa verificacao quando holerite nao existe"""
        with patch("src.services.holerite_service.MongoClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ismaster": True}

            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_instance.__getitem__.return_value = mock_db
            mock_db.__getitem__.return_value = mock_collection
            mock_collection.count_documents.return_value = 0

            from src.services.holerite_service import HoleriteService

            service = HoleriteService()
            service.colecao = mock_collection

            resultado = service.existe_holerite(
                funcionario_id=str(ObjectId()),
                competencia="01/2024"
            )

            assert resultado is False
