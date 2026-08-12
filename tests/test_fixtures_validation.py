"""Validation tests to ensure all fixtures work correctly."""

import pytest
from bson import ObjectId
from datetime import datetime, date


# ==================== Global Fixtures Tests ====================

def test_sample_object_id(sample_object_id):
    """Test sample_object_id fixture."""
    assert isinstance(sample_object_id, ObjectId)
    assert str(sample_object_id) == "507f1f77bcf86cd799439011"


def test_sample_object_ids(sample_object_ids):
    """Test sample_object_ids factory fixture."""
    ids = sample_object_ids(5)
    assert len(ids) == 5
    assert all(isinstance(obj_id, ObjectId) for obj_id in ids)


def test_mock_collection(mock_collection):
    """Test mock_collection fixture."""
    assert hasattr(mock_collection, "find_one")
    assert hasattr(mock_collection, "find")
    assert hasattr(mock_collection, "insert_one")
    assert hasattr(mock_collection, "update_one")
    assert hasattr(mock_collection, "delete_one")
    assert hasattr(mock_collection, "aggregate")


def test_mock_redis(mock_redis):
    """Test mock_redis fixture."""
    assert hasattr(mock_redis, "get")
    assert hasattr(mock_redis, "set")
    assert hasattr(mock_redis, "delete")
    assert hasattr(mock_redis, "keys")


def test_funcionario_dict(funcionario_dict):
    """Test funcionario_dict fixture."""
    assert funcionario_dict["nome"] == "João Silva"
    assert funcionario_dict["status"] == "ativo"
    assert funcionario_dict["status_cadastro"] == "completo"


def test_empresa_dict(empresa_dict):
    """Test empresa_dict fixture."""
    assert empresa_dict["nome"] == "Moraes & Santos Consultoria"
    assert empresa_dict["status"] == "ativa"
    assert empresa_dict["incompleto"] is False


def test_folha_ponto_dict(folha_ponto_dict):
    """Test folha_ponto_dict fixture."""
    assert folha_ponto_dict["mes_referencia"] == "2025-01"
    assert folha_ponto_dict["status"] == "preenchida"
    assert isinstance(folha_ponto_dict["funcionario_id"], ObjectId)


# ==================== MongoDB Fixtures Tests ====================

def test_funcionario_document_factory(funcionario_document_factory):
    """Test funcionario document factory."""
    doc = funcionario_document_factory(nome="Test User", status="ativo")
    assert doc["nome"] == "Test User"
    assert doc["status"] == "ativo"
    assert "_id" in doc
    assert isinstance(doc["_id"], ObjectId)


def test_empresa_document_factory(empresa_document_factory):
    """Test empresa document factory."""
    doc = empresa_document_factory(nome="Test Corp", status="ativa")
    assert doc["nome"] == "Test Corp"
    assert doc["status"] == "ativa"
    assert "_id" in doc


def test_folha_ponto_document_factory(folha_ponto_document_factory):
    """Test folha ponto document factory."""
    doc = folha_ponto_document_factory(mes_referencia="2025-02")
    assert doc["mes_referencia"] == "2025-02"
    assert "funcionario_id" in doc
    assert "empresa_id" in doc


# ==================== Redis Fixtures Tests ====================

@pytest.mark.asyncio
async def test_mock_redis_connection(mock_redis_connection):
    """Test detailed Redis connection mock."""
    await mock_redis_connection.set("test_key", "test_value")
    value = await mock_redis_connection.get("test_key")
    assert value == "test_value"

    # Test storage inspection
    assert "test_key" in mock_redis_connection._storage


@pytest.mark.asyncio
async def test_mock_redis_unavailable(mock_redis_unavailable):
    """Test Redis unavailable scenario."""
    with pytest.raises(ConnectionError):
        await mock_redis_unavailable.get("test_key")


def test_cache_key_builder(cache_key_builder):
    """Test cache key builder."""
    key = cache_key_builder("funcionario", id=123, status="ativo")
    assert "funcionario" in key
    assert "id:123" in key
    assert "status:ativo" in key


# ==================== Model Fixtures Tests ====================

def test_funcionario_completo(funcionario_completo):
    """Test complete funcionario fixture."""
    assert funcionario_completo.nome == "João Silva"
    assert funcionario_completo.status_cadastro == "completo"
    assert funcionario_completo.is_cadastro_completo() is True


def test_funcionario_incompleto(funcionario_incompleto):
    """Test incomplete funcionario fixture."""
    assert funcionario_incompleto.nome == "Maria Santos"
    assert funcionario_incompleto.status_cadastro == "incompleto"
    assert funcionario_incompleto.is_cadastro_completo() is False


def test_empresa_completa(empresa_completa):
    """Test complete empresa fixture."""
    assert empresa_completa.nome == "Moraes & Santos Consultoria"
    assert empresa_completa.status == "ativa"
    assert empresa_completa.incompleto is False


def test_empresa_incompleta(empresa_incompleta):
    """Test incomplete empresa fixture."""
    assert empresa_incompleta.nome == "Empresa Teste Ltda"
    assert empresa_incompleta.status == "em_construcao"
    assert empresa_incompleta.incompleto is True


def test_folha_ponto_sample(folha_ponto_sample):
    """Test sample folha de ponto fixture."""
    assert folha_ponto_sample.mes_referencia == "2025-01"
    assert folha_ponto_sample.status == "preenchida"
    assert len(folha_ponto_sample.folha_data.dias) == 2


def test_funcionario_factory(funcionario_factory):
    """Test funcionario factory."""
    func = funcionario_factory(nome="Factory Test", status="ativo")
    assert func.nome == "Factory Test"
    assert func.status == "ativo"


def test_empresa_factory(empresa_factory):
    """Test empresa factory."""
    emp = empresa_factory(nome="Factory Corp", status="ativa")
    assert emp.nome == "Factory Corp"
    assert emp.status == "ativa"


def test_dia_folha_factory(dia_folha_factory):
    """Test dia folha factory."""
    dia = dia_folha_factory(numero_dia=5, tipo_dia="FERIADO")
    assert dia.numero_dia == 5
    assert dia.tipo_dia == "FERIADO"


# ==================== Gemini Fixtures Tests ====================

def test_gemini_folha_ponto_response(gemini_folha_ponto_response):
    """Test Gemini folha ponto response fixture."""
    assert gemini_folha_ponto_response.status_code == 200
    import json
    data = json.loads(gemini_folha_ponto_response.text)
    assert data["dias_analisados"] == 20
    assert data["taxa_preenchimento"] == 85.5


def test_gemini_holerite_response(gemini_holerite_response):
    """Test Gemini holerite response fixture."""
    assert gemini_holerite_response.status_code == 200
    import json
    data = json.loads(gemini_holerite_response.text)
    assert "funcionario" in data
    assert "empresa" in data


@pytest.mark.asyncio
async def test_mock_gemini_service(mock_gemini_service):
    """Test mock Gemini service."""
    result = await mock_gemini_service.analyze_document(
        "test.pdf",
        "Extract data"
    )
    assert result["success"] is True
    assert "data" in result


def test_gemini_response_factory(gemini_response_factory):
    """Test Gemini response factory."""
    response = gemini_response_factory(
        success=True,
        data={"test": "data"}
    )
    assert response["success"] is True
    assert response["data"]["test"] == "data"


# ==================== File Fixtures Tests ====================

def test_temp_pdf_file(temp_pdf_file):
    """Test temporary PDF file fixture."""
    assert temp_pdf_file.exists()
    assert temp_pdf_file.suffix == ".pdf"
    assert temp_pdf_file.stat().st_size > 0


def test_temp_directory(temp_directory):
    """Test temporary directory fixture."""
    assert temp_directory.exists()
    assert temp_directory.is_dir()


def test_temp_directory_structure(temp_directory_structure):
    """Test directory structure fixture."""
    assert "root" in temp_directory_structure
    assert "input" in temp_directory_structure
    assert "output" in temp_directory_structure
    assert temp_directory_structure["input"].exists()


def test_sample_file_paths(sample_file_paths):
    """Test file paths factory."""
    paths = sample_file_paths(count=3, extension=".pdf")
    assert len(paths) == 3
    assert all(p.suffix == ".pdf" for p in paths)


def test_absolute_path_converter(absolute_path_converter):
    """Test absolute path converter."""
    abs_path = absolute_path_converter("data/test.pdf")
    assert abs_path.is_absolute()


# ==================== Environment Fixtures Tests ====================

def test_mock_env_vars(mock_env_vars):
    """Test environment variables fixture."""
    import os
    assert os.getenv("MONGO_URI") == "mongodb://localhost:27017test_db"
    assert os.getenv("ENV") == "test"
