# Test Fixture Usage Examples

Practical examples demonstrating how to use the comprehensive fixture system.

## Table of Contents

1. [Basic Service Testing](#basic-service-testing)
2. [MongoDB Operations](#mongodb-operations)
3. [Redis Caching](#redis-caching)
4. [Model Testing](#model-testing)
5. [Gemini AI Testing](#gemini-ai-testing)
6. [File Processing](#file-processing)
7. [Integration Tests](#integration-tests)

---

## Basic Service Testing

### Example 1: Testing FuncionarioService CRUD Operations

```python
import pytest
from bson import ObjectId
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_buscar_funcionario_por_id(funcionario_service_with_mock, funcionario_dict):
    """Test finding funcionario by ID."""
    service, mock_collection, _ = funcionario_service_with_mock

    # Mock database response
    funcionario_id = ObjectId()
    funcionario_dict["_id"] = funcionario_id
    mock_collection.find_one.return_value = funcionario_dict

    # Execute
    result = await service.buscar_por_id(funcionario_id)

    # Verify
    assert result is not None
    assert result["nome"] == "João Silva"
    mock_collection.find_one.assert_called_once()


@pytest.mark.asyncio
async def test_criar_funcionario(funcionario_service_with_mock):
    """Test creating new funcionario."""
    service, mock_collection, _ = funcionario_service_with_mock

    # Mock insert
    new_id = ObjectId()
    mock_collection.insert_one.return_value = MagicMock(inserted_id=new_id)

    # Execute
    data = {
        "nome": "Maria Santos",
        "pis": "98765432109",
        "status": "ativo"
    }
    result = await service.criar(data)

    # Verify
    assert result == new_id
    mock_collection.insert_one.assert_called_once()
```

### Example 2: Testing EmpresaService

```python
@pytest.mark.asyncio
async def test_listar_empresas_ativas(empresa_service_with_mock, empresa_document_factory):
    """Test listing active empresas."""
    from tests.conftest import mock_cursor

    service, mock_collection, _ = empresa_service_with_mock

    # Create sample empresas
    empresas = [
        empresa_document_factory(nome="Empresa 1", status="ativa"),
        empresa_document_factory(nome="Empresa 2", status="ativa")
    ]

    # Mock find
    mock_collection.find.return_value = mock_cursor(empresas)

    # Execute
    result = await service.listar_ativas()

    # Verify
    assert len(result) == 2
    assert all(emp["status"] == "ativa" for emp in result)
```

---

## MongoDB Operations

### Example 3: Testing Aggregation Pipeline

```python
@pytest.mark.asyncio
async def test_agregacao_funcionarios_por_status(
    funcionario_service_with_mock,
    mock_aggregation_result
):
    """Test aggregating funcionarios by status."""
    service, mock_collection, _ = funcionario_service_with_mock

    # Mock aggregation
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    results = [
        {"_id": "ativo", "count": 15},
        {"_id": "inativo", "count": 3}
    ]

    cursor = mock_aggregation_result(pipeline, results)
    mock_collection.aggregate.return_value = cursor

    # Execute
    result = await service.contar_por_status()

    # Verify
    assert result["ativo"] == 15
    assert result["inativo"] == 3
```

### Example 4: Testing Cursor Chaining

```python
@pytest.mark.asyncio
async def test_buscar_funcionarios_paginado(funcionario_service_with_mock):
    """Test paginated search with sorting."""
    from tests.conftest import mock_cursor

    service, mock_collection, _ = funcionario_service_with_mock

    # Mock paginated results
    funcionarios = [{"nome": f"Func {i}"} for i in range(10)]
    cursor = mock_cursor(funcionarios)
    mock_collection.find.return_value = cursor

    # Execute
    result = await service.buscar_paginado(page=2, per_page=10)

    # Verify cursor chaining
    cursor.sort.assert_called()
    cursor.skip.assert_called_with(10)
    cursor.limit.assert_called_with(10)
```

---

## Redis Caching

### Example 5: Testing Cache Hit/Miss

```python
@pytest.mark.asyncio
async def test_cache_hit(mock_redis_connection, cached_funcionario_factory):
    """Test cache hit scenario."""
    redis = mock_redis_connection

    # Set cached data
    cached_data = cached_funcionario_factory(nome="João", pis="12345")
    await redis.set("func:12345", cached_data)

    # Verify retrieval
    result = await redis.get("func:12345")
    assert result is not None
    assert "João" in result


@pytest.mark.asyncio
async def test_cache_miss_with_database_fallback(
    funcionario_service_with_mock,
    mock_redis_connection
):
    """Test cache miss falls back to database."""
    service, mock_collection, _ = funcionario_service_with_mock

    # Cache miss
    await mock_redis_connection.delete("func:123")

    # Database has the data
    mock_collection.find_one.return_value = {
        "_id": ObjectId(),
        "nome": "João"
    }

    # Execute
    result = await service.buscar_com_cache("123")

    # Verify database was queried
    mock_collection.find_one.assert_called_once()
```

### Example 6: Testing Cache Invalidation

```python
@pytest.mark.asyncio
async def test_invalidar_cache(mock_cache_service):
    """Test cache invalidation."""
    service, redis = mock_cache_service

    # Set multiple keys
    await redis.set("func:1", "data1")
    await redis.set("func:2", "data2")
    await redis.set("empresa:1", "data3")

    # Invalidate funcionario cache
    await service.invalidate_pattern("func:*")

    # Verify
    assert await redis.exists("func:1") == 0
    assert await redis.exists("empresa:1") == 1
```

---

## Model Testing

### Example 7: Testing Model Validation

```python
def test_funcionario_validacao_nome_vazio():
    """Test that empty name raises validation error."""
    from src.models.funcionario_models import FuncionarioMongoDB
    import pytest

    with pytest.raises(ValueError, match="Nome não pode ser vazio"):
        FuncionarioMongoDB(nome="", pis="12345")


def test_funcionario_is_cadastro_completo(funcionario_completo, funcionario_incompleto):
    """Test cadastro completion check."""
    assert funcionario_completo.is_cadastro_completo() is True
    assert funcionario_incompleto.is_cadastro_completo() is False
```

### Example 8: Testing Model Methods

```python
def test_funcionario_adicionar_empresa(funcionario_completo, sample_object_id):
    """Test adding empresa to funcionario."""
    empresa_id = sample_object_id

    # Add empresa
    funcionario_completo.adicionar_empresa(empresa_id)

    # Verify
    assert empresa_id in funcionario_completo.empresas_ids
    assert len(funcionario_completo.historico_alteracoes) > 0


def test_empresa_marcar_como_completa(empresa_incompleta):
    """Test marking empresa as complete."""
    assert empresa_incompleta.incompleto is True
    assert empresa_incompleta.status == "em_construcao"

    # Mark complete
    empresa_incompleta.marcar_como_completa()

    # Verify
    assert empresa_incompleta.incompleto is False
    assert empresa_incompleta.status == "ativa"
```

### Example 9: Using Factories for Variations

```python
def test_funcionario_factory_variations(funcionario_factory):
    """Test creating different funcionario scenarios."""
    # Complete funcionario
    func_completo = funcionario_factory(
        nome="João",
        status="ativo",
        status_cadastro="completo",
        lotacao="TI"
    )
    assert func_completo.is_cadastro_completo() is True

    # Incomplete funcionario
    func_incompleto = funcionario_factory(
        nome="Maria",
        status_cadastro="incompleto"
    )
    assert func_incompleto.is_cadastro_completo() is False

    # Pendente revisão
    func_revisao = funcionario_factory(
        nome="Carlos",
        status_cadastro="pendente_revisao"
    )
    assert func_revisao.status_cadastro == "pendente_revisao"
```

---

## Gemini AI Testing

### Example 10: Testing Gemini Service

```python
@pytest.mark.asyncio
async def test_gemini_analyze_folha_ponto(mock_gemini_service, temp_pdf_file):
    """Test Gemini folha ponto analysis."""
    # Execute
    result = await mock_gemini_service.analyze_document(
        str(temp_pdf_file),
        "Analyze folha de ponto"
    )

    # Verify
    assert result["success"] is True
    assert "data" in result
    assert result["model"] == "gemini-2.5-flash-lite"


@pytest.mark.asyncio
async def test_gemini_retry_behavior(mock_gemini_service_with_retry):
    """Test Gemini retry logic."""
    # Execute (will fail twice, succeed on 3rd)
    result = await mock_gemini_service_with_retry.analyze_document(
        "test.pdf",
        "Extract data"
    )

    # Verify retry happened
    assert result["attempt"] == 3
    assert result["success"] is True
```

### Example 11: Testing Response Parsing

```python
def test_parse_gemini_folha_response(gemini_folha_ponto_response):
    """Test parsing Gemini folha ponto response."""
    import json

    data = json.loads(gemini_folha_ponto_response.text)

    assert data["dias_analisados"] == 20
    assert data["taxa_preenchimento"] == 85.5
    assert len(data["dias"]) == 2
    assert data["total_horas_mes"] == "160:00"


def test_gemini_response_factory_custom(gemini_response_factory):
    """Test creating custom Gemini responses."""
    response = gemini_response_factory(
        success=True,
        data={"custom_field": "value"},
        tokens_used=1500
    )

    assert response["success"] is True
    assert response["data"]["custom_field"] == "value"
    assert response["tokens_used"] == 1500
```

---

## File Processing

### Example 12: Testing PDF Processing

```python
def test_process_pdf_file(temp_pdf_file):
    """Test PDF file processing."""
    assert temp_pdf_file.exists()
    assert temp_pdf_file.suffix == ".pdf"
    assert temp_pdf_file.stat().st_size > 0

    # Read content
    content = temp_pdf_file.read_bytes()
    assert b"%PDF" in content


def test_pdf_content_factory(pdf_content_factory, temp_directory):
    """Test creating custom PDF content."""
    content = pdf_content_factory("Folha de Ponto - Janeiro 2025")

    # Save to file
    pdf_path = temp_directory / "custom.pdf"
    pdf_path.write_bytes(content)

    assert pdf_path.exists()
    assert b"Folha de Ponto" in pdf_path.read_bytes()
```

### Example 13: Testing Directory Operations

```python
def test_organize_files(temp_directory_structure):
    """Test file organization in directories."""
    # Get directories
    input_dir = temp_directory_structure["input"]
    output_dir = temp_directory_structure["output"]

    # Create file in input
    test_file = input_dir / "test.pdf"
    test_file.write_text("content")

    # Verify structure
    assert test_file.exists()
    assert output_dir.exists()


def test_nested_directory_creation(temp_nested_directories):
    """Test nested directory structure."""
    empresa_dir = temp_nested_directories / "empresa1"
    funcionarios_dir = empresa_dir / "funcionarios"
    folhas_dir = funcionarios_dir / "folhas_ponto"

    assert folhas_dir.exists()
    assert folhas_dir.is_dir()
```

---

## Integration Tests

### Example 14: End-to-End Folha Ponto Creation

```python
@pytest.mark.asyncio
async def test_criar_folha_ponto_completo(
    folha_ponto_service_with_mock,
    funcionario_document_factory,
    empresa_document_factory,
    dia_folha_factory
):
    """Test complete folha ponto creation flow."""
    service, mock_collection, _ = folha_ponto_service_with_mock

    # Setup
    funcionario = funcionario_document_factory(nome="João")
    empresa = empresa_document_factory(nome="Empresa X")

    # Create dias
    dias = [dia_folha_factory(numero_dia=i, preenchido=True) for i in range(1, 21)]

    # Mock insert
    mock_collection.insert_one.return_value = MagicMock(inserted_id=ObjectId())

    # Execute
    folha_data = {
        "funcionario_id": funcionario["_id"],
        "empresa_id": empresa["_id"],
        "mes_referencia": "2025-01",
        "dias": dias
    }

    result = await service.criar(folha_data)

    # Verify
    assert result is not None
    mock_collection.insert_one.assert_called_once()
```

### Example 15: Testing Complete Workflow with Cache

```python
@pytest.mark.asyncio
async def test_buscar_funcionario_workflow(
    funcionario_service_with_mock,
    mock_redis_connection,
    funcionario_document_factory,
    cached_funcionario_factory,
    cache_key_builder
):
    """Test complete funcionario lookup workflow with cache."""
    service, mock_collection, _ = funcionario_service_with_mock
    redis = mock_redis_connection

    funcionario_id = ObjectId()
    cache_key = cache_key_builder("func", id=str(funcionario_id))

    # First call - cache miss, database hit
    funcionario = funcionario_document_factory(_id=funcionario_id)
    mock_collection.find_one.return_value = funcionario

    result1 = await service.buscar_com_cache(str(funcionario_id))
    assert result1 is not None

    # Cache the result
    cached = cached_funcionario_factory(**funcionario)
    await redis.set(cache_key, cached)

    # Second call - cache hit
    result2 = await redis.get(cache_key)
    assert result2 is not None
    assert funcionario["nome"] in result2
```

---

## Best Practices Demonstrated

### 1. Arrange-Act-Assert Pattern

```python
@pytest.mark.asyncio
async def test_example(funcionario_service_with_mock):
    # ARRANGE
    service, mock_collection, _ = funcionario_service_with_mock
    mock_collection.find_one.return_value = {"nome": "João"}

    # ACT
    result = await service.buscar_por_nome("João")

    # ASSERT
    assert result["nome"] == "João"
```

### 2. Using Factories for Data Variation

```python
def test_multiple_scenarios(funcionario_factory):
    scenarios = [
        ("ativo", "completo"),
        ("inativo", "completo"),
        ("ativo", "incompleto")
    ]

    for status, cadastro in scenarios:
        func = funcionario_factory(status=status, status_cadastro=cadastro)
        # Test each scenario
```

### 3. Parametrized Tests with Fixtures

```python
@pytest.mark.parametrize("status,expected", [
    ("ativo", True),
    ("inativo", False),
    ("afastado", False)
])
def test_is_funcionario_ativo(funcionario_factory, status, expected):
    func = funcionario_factory(status=status)
    assert func.is_ativo() == expected
```

---

## Running the Examples

```bash
# Run all examples
uv run python -m pytest tests/ -v --no-cov

# Run specific example
uv run python -m pytest tests/test_service.py::test_criar_funcionario -v

# Run with coverage
uv run python -m pytest tests/ --cov=src --cov-report=html
```
