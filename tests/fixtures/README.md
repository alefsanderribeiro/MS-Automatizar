# Test Fixtures Documentation

Comprehensive test fixtures for MS-Automatizar project, organized by domain.

## Table of Contents

- [Global Fixtures](#global-fixtures) (`tests/conftest.py`)
- [MongoDB Fixtures](#mongodb-fixtures) (`mongodb_fixtures.py`)
- [Redis Fixtures](#redis-fixtures) (`redis_fixtures.py`)
- [Model Fixtures](#model-fixtures) (`model_fixtures.py`)
- [Gemini AI Fixtures](#gemini-ai-fixtures) (`gemini_fixtures.py`)
- [File Fixtures](#file-fixtures) (`file_fixtures.py`)

---

## Global Fixtures

Located in `tests/conftest.py`. Automatically available to all tests.

### ObjectId Fixtures

#### `sample_object_id`
Returns a fixed valid ObjectId for testing.

```python
def test_example(sample_object_id):
    assert str(sample_object_id) == "507f1f77bcf86cd799439011"
```

#### `sample_object_ids`
Factory fixture that generates multiple ObjectIds.

```python
def test_example(sample_object_ids):
    ids = sample_object_ids(count=5)  # Get 5 ObjectIds
    assert len(ids) == 5
```

### MongoDB Mocks

#### `mock_collection`
Mock MongoDB collection with CRUD operations.

```python
def test_example(mock_collection):
    # Mock returns
    mock_collection.find_one.return_value = {"_id": ObjectId(), "nome": "João"}

    result = await mock_collection.find_one({"nome": "João"})
    assert result["nome"] == "João"
```

Methods available:
- `find_one` (AsyncMock)
- `find` (returns mock cursor)
- `insert_one` (AsyncMock)
- `update_one` (AsyncMock)
- `delete_one` (AsyncMock)
- `aggregate` (returns mock cursor)
- `count_documents` (AsyncMock)

#### `mock_database`
Mock MongoDB database.

```python
def test_example(mock_database):
    collection = mock_database["funcionarios"]
```

#### `mock_mongo_client`
Mock Motor (async MongoDB) client.

```python
def test_example(mock_mongo_client):
    db = mock_mongo_client["MS_Automatizar"]
    collection = db["funcionarios"]
```

#### `mock_cursor(results)`
Helper function for creating mock cursors with chaining.

```python
from tests.conftest import mock_cursor

results = [{"nome": "João"}, {"nome": "Maria"}]
cursor = mock_cursor(results)

# Supports chaining
cursor.sort("nome", 1).skip(10).limit(5)
```

### Redis Mocks

#### `mock_redis`
Basic async Redis mock.

```python
@pytest.mark.asyncio
async def test_example(mock_redis):
    await mock_redis.set("key", "value")
    value = await mock_redis.get("key")
```

Methods available:
- `get`, `set`, `delete`
- `keys`, `scan_iter`
- `exists`, `expire`
- `ping`

### Environment Variables

#### `mock_env_vars`
Mock environment variables with defaults.

```python
def test_example(mock_env_vars):
    # Default env vars already set
    assert os.getenv("MONGO_URI") == "mongodb://localhost:27017test_db"

    # Set custom vars
    mock_env_vars({
        "GEMINI_API_KEY": "custom_key"
    })
```

Default variables set:
- `MONGO_URI`: mongodb://localhost:27017test_db
- `REDIS_ENABLED`: false
- `GEMINI_API_KEY`: test_api_key_12345
- `ENV`: test
- `LOG_LEVEL`: DEBUG

### Pydantic Model Dictionaries

#### `funcionario_dict`
Complete funcionario data as dictionary.

```python
def test_example(funcionario_dict):
    assert funcionario_dict["nome"] == "João Silva"
    assert funcionario_dict["status"] == "ativo"
```

#### `funcionario_incompleto_dict`
Minimal funcionario (autocreate scenario).

#### `empresa_dict`
Complete empresa data.

#### `empresa_incompleta_dict`
Minimal empresa (autocreate scenario).

#### `folha_ponto_dict`
Complete folha de ponto with sample dias.

### File Fixtures (Basic)

#### `temp_directory`
Temporary directory (auto-cleanup).

```python
def test_example(temp_directory):
    file_path = temp_directory / "test.txt"
    file_path.write_text("content")
```

#### `temp_pdf_file`
Minimal valid PDF file for testing.

```python
def test_example(temp_pdf_file):
    assert temp_pdf_file.exists()
    assert temp_pdf_file.suffix == ".pdf"
```

---

## MongoDB Fixtures

Located in `tests/fixtures/mongodb_fixtures.py`.

### Aggregation

#### `mock_aggregation_result`
Factory for creating aggregation result cursors.

```python
def test_example(mock_aggregation_result):
    pipeline = [{"$match": {"status": "ativo"}}]
    results = [{"_id": ObjectId(), "nome": "João"}]
    cursor = mock_aggregation_result(pipeline, results)
```

### Service Fixtures with Mocks

#### `funcionario_service_with_mock`
FuncionarioService with injected mocks.

```python
def test_example(funcionario_service_with_mock):
    service, mock_collection, mock_redis = funcionario_service_with_mock

    # Mock behavior
    mock_collection.find_one.return_value = {"nome": "João"}

    # Use service
    result = await service.buscar_por_id(ObjectId())
```

#### `empresa_service_with_mock`
EmpresaService with injected mocks.

#### `folha_ponto_service_with_mock`
FolhaPontoService with injected mocks.

### Document Factories

#### `funcionario_document_factory`
Factory for creating funcionario documents with variations.

```python
def test_example(funcionario_document_factory):
    # Complete funcionario
    func = funcionario_document_factory(
        nome="João Silva",
        status="ativo",
        status_cadastro="completo"
    )

    # Incomplete funcionario
    func_inc = funcionario_document_factory(
        nome="Maria",
        status_cadastro="incompleto"
    )
```

#### `empresa_document_factory`
Factory for creating empresa documents.

```python
def test_example(empresa_document_factory):
    emp = empresa_document_factory(
        nome="Teste Corp",
        status="ativa",
        cnpj="12.345.678/0001-90"
    )
```

#### `folha_ponto_document_factory`
Factory for creating folha de ponto documents.

```python
def test_example(folha_ponto_document_factory):
    folha = folha_ponto_document_factory(
        funcionario_id=ObjectId(),
        empresa_id=ObjectId(),
        mes_referencia="2025-01"
    )
```

---

## Redis Fixtures

Located in `tests/fixtures/redis_fixtures.py`.

### Detailed Redis Mock

#### `mock_redis_connection`
Redis mock with in-memory storage simulation.

```python
@pytest.mark.asyncio
async def test_example(mock_redis_connection):
    await mock_redis_connection.set("key1", "value1")
    value = await mock_redis_connection.get("key1")

    # Inspect storage
    assert "key1" in mock_redis_connection._storage
```

#### `mock_redis_unavailable`
Redis connection failure scenario.

```python
@pytest.mark.asyncio
async def test_example(mock_redis_unavailable):
    with pytest.raises(ConnectionError):
        await mock_redis_unavailable.get("key")
```

### Cache Helpers

#### `cache_key_builder`
Helper for building consistent cache keys.

```python
def test_example(cache_key_builder):
    key = cache_key_builder("funcionario", id=123, status="ativo")
    # Returns: "funcionario:id:123:status:ativo"
```

#### `cached_funcionario_factory`
Factory for creating cached funcionario JSON data.

```python
def test_example(cached_funcionario_factory):
    cached = cached_funcionario_factory(nome="João", pis="12345")
    # Returns JSON string ready for Redis
```

#### `cached_empresa_factory`
Factory for creating cached empresa JSON data.

### Cache Service Mocks

#### `mock_cache_service`
CacheService with mocked Redis backend.

```python
def test_example(mock_cache_service):
    service, redis_mock = mock_cache_service

    await service.set("key", "value")
    value = await service.get("key")
```

#### `mock_cache_service_disabled`
CacheService with caching disabled.

---

## Model Fixtures

Located in `tests/fixtures/model_fixtures.py`.

### Funcionario Fixtures

#### `funcionario_completo`
Complete FuncionarioMongoDB instance.

```python
def test_example(funcionario_completo):
    assert funcionario_completo.nome == "João Silva"
    assert funcionario_completo.is_cadastro_completo() is True
```

#### `funcionario_incompleto`
Incomplete FuncionarioMongoDB (autocreate).

```python
def test_example(funcionario_incompleto):
    assert funcionario_incompleto.status_cadastro == "incompleto"
```

#### `funcionario_pendente_revisao`
Funcionario marked for review.

#### `funcionario_factory`
Factory for creating funcionario instances.

```python
def test_example(funcionario_factory):
    func = funcionario_factory(
        nome="Test User",
        status="ativo",
        status_cadastro="completo",
        lotacao="RH"
    )
```

### Empresa Fixtures

#### `empresa_completa`
Complete EmpresaMongoDB instance.

#### `empresa_incompleta`
Incomplete EmpresaMongoDB (autocreate).

#### `empresa_factory`
Factory for creating empresa instances.

```python
def test_example(empresa_factory):
    emp = empresa_factory(
        nome="Test Corp",
        status="ativa",
        cnpj="12.345.678/0001-90"
    )
```

### Folha de Ponto Fixtures

#### `folha_ponto_sample`
FolhaDePontoMongoDB with filled dias.

```python
def test_example(folha_ponto_sample):
    assert folha_ponto_sample.mes_referencia == "2025-01"
    assert len(folha_ponto_sample.folha_data.dias) == 2
```

#### `folha_ponto_vazia`
Empty FolhaDePontoMongoDB (just created).

#### `dia_folha_factory`
Factory for creating DiaFolhaPonto instances.

```python
def test_example(dia_folha_factory):
    # Empty day
    dia = dia_folha_factory(numero_dia=1, tipo_dia="NORMAL")

    # Filled day
    dia = dia_folha_factory(
        numero_dia=2,
        tipo_dia="NORMAL",
        preenchido=True,
        hora_entrada="08:00",
        hora_saida="17:00"
    )
```

---

## Gemini AI Fixtures

Located in `tests/fixtures/gemini_fixtures.py`.

### Response Fixtures

#### `gemini_folha_ponto_response`
Typical Gemini response for folha de ponto analysis.

```python
def test_example(gemini_folha_ponto_response):
    import json
    data = json.loads(gemini_folha_ponto_response.text)
    assert data["dias_analisados"] == 20
```

#### `gemini_holerite_response`
Typical Gemini response for holerite OCR.

#### `gemini_error_response`
Gemini API error response (429 quota exceeded).

### Service Mocks

#### `mock_gemini_service`
Mock Gemini service with successful responses.

```python
@pytest.mark.asyncio
async def test_example(mock_gemini_service):
    result = await mock_gemini_service.analyze_document(
        "test.pdf",
        "Extract data"
    )
    assert result["success"] is True
```

#### `mock_gemini_service_with_retry`
Mock service that simulates retry behavior.

```python
@pytest.mark.asyncio
async def test_example(mock_gemini_service_with_retry):
    # Fails first 2 attempts, succeeds on 3rd
    result = await mock_gemini_service_with_retry.analyze_document(
        "test.pdf", "prompt"
    )
    assert result["attempt"] == 3
```

#### `mock_gemini_service_failure`
Mock service that always fails.

### Response Factories

#### `gemini_response_factory`
Factory for custom Gemini responses.

```python
def test_example(gemini_response_factory):
    response = gemini_response_factory(
        success=True,
        data={"dias_analisados": 15},
        tokens_used=1200
    )
```

#### `gemini_folha_ponto_factory`
Factory for folha ponto analysis responses.

```python
def test_example(gemini_folha_ponto_factory):
    response = gemini_folha_ponto_factory(
        dias_analisados=25,
        taxa_preenchimento=90.0
    )
```

#### `gemini_holerite_factory`
Factory for holerite extraction responses.

#### `gemini_prompt_templates`
Sample prompt templates.

```python
def test_example(gemini_prompt_templates):
    prompt = gemini_prompt_templates["folha_ponto"]
```

---

## File Fixtures

Located in `tests/fixtures/file_fixtures.py`.

### File Creation

#### `temp_pdf_file`
Creates temporary PDF with valid structure.

#### `temp_excel_file`
Creates temporary Excel file (requires openpyxl).

#### `temp_json_file`
Creates temporary JSON file with sample data.

#### `temp_text_file`
Creates temporary text file with UTF-8 content.

### Directory Structures

#### `temp_directory_structure`
Creates organized directory structure.

```python
def test_example(temp_directory_structure):
    input_dir = temp_directory_structure["input"]
    output_dir = temp_directory_structure["output"]
    cache_dir = temp_directory_structure["cache"]
```

#### `temp_nested_directories`
Creates nested directory tree.

```python
def test_example(temp_nested_directories):
    # Creates: root/empresa1/funcionarios/folhas_ponto
    assert (temp_nested_directories / "empresa1" / "funcionarios").exists()
```

### Path Helpers

#### `sample_file_paths`
Factory for generating file paths.

```python
def test_example(sample_file_paths):
    paths = sample_file_paths(count=5, extension=".pdf")
```

#### `absolute_path_converter`
Converts relative to absolute paths.

#### `file_exists_checker`
Helper for checking file existence.

#### `file_size_getter`
Helper for getting file sizes.

### Content Factories

#### `pdf_content_factory`
Factory for PDF content variations.

```python
def test_example(pdf_content_factory):
    content = pdf_content_factory(text="Folha de Ponto - Janeiro 2025")
```

#### `excel_content_factory`
Factory for Excel content.

```python
def test_example(excel_content_factory, temp_directory):
    path = excel_content_factory(
        temp_directory / "test.xlsx",
        data={
            "Nome": ["João", "Maria"],
            "PIS": ["111", "222"]
        }
    )
```

---

## Usage Examples

### Testing a Service Method

```python
@pytest.mark.asyncio
async def test_criar_funcionario(funcionario_service_with_mock):
    service, mock_collection, _ = funcionario_service_with_mock

    # Mock insert
    mock_collection.insert_one.return_value = MagicMock(
        inserted_id=ObjectId()
    )

    # Test
    result = await service.criar({
        "nome": "João Silva",
        "pis": "12345678901"
    })

    assert result is not None
```

### Testing with Cache

```python
@pytest.mark.asyncio
async def test_cache_funcionario(
    mock_cache_service,
    cached_funcionario_factory
):
    service, redis_mock = mock_cache_service

    # Set cached data
    cached = cached_funcionario_factory(nome="João")
    await redis_mock.set("func:123", cached)

    # Verify retrieval
    result = await service.get("func:123")
    assert "João" in result
```

### Testing File Processing

```python
def test_process_pdf(temp_pdf_file, mock_gemini_service):
    # Process PDF
    result = process_document(temp_pdf_file, mock_gemini_service)
    assert result["success"] is True
```

---

## Running Validation Tests

```bash
# Run all fixture validation tests
uv run python -m pytest tests/test_fixtures_validation.py -v --no-cov

# Run specific test
uv run python -m pytest tests/test_fixtures_validation.py::test_funcionario_completo -v --no-cov
```

---

## Best Practices

1. **Use Factories for Variations**: Use factory fixtures when you need multiple variations of test data.

2. **Mock at Service Level**: Use service fixtures (`funcionario_service_with_mock`) to test service logic without database.

3. **Isolate Tests**: Each test should be independent. Use fixtures to ensure clean state.

4. **Async Tests**: Mark async tests with `@pytest.mark.asyncio`.

5. **Cleanup**: Temp files/directories are auto-cleaned by pytest's `tmp_path`.

6. **Environment**: Use `mock_env_vars` to avoid dependency on real env variables.

---

## Contributing

When adding new fixtures:

1. Add to appropriate file (`mongodb_fixtures.py`, `model_fixtures.py`, etc.)
2. Document with docstring and type hints
3. Add validation test in `test_fixtures_validation.py`
4. Update this README with usage examples

---

## Fixture Dependency Graph

```
conftest.py (Global)
├── ObjectId fixtures
├── MongoDB mocks → mongodb_fixtures.py
├── Redis mocks → redis_fixtures.py
├── Model dictionaries → model_fixtures.py
└── File helpers → file_fixtures.py

mongodb_fixtures.py
├── Aggregation factories
├── Service fixtures (depend on mock_collection, mock_redis)
└── Document factories

redis_fixtures.py
├── Redis connection mocks
├── Cache key builders
└── Cache service fixtures

model_fixtures.py
├── Funcionario fixtures
├── Empresa fixtures
└── Folha de Ponto fixtures

gemini_fixtures.py
├── Response fixtures
├── Service mocks
└── Response factories

file_fixtures.py
├── Temp file creation
├── Directory structures
└── Content factories
```
