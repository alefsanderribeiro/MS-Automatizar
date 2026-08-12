# MS-Automatizar Test Suite

This directory contains the complete test infrastructure for the MS-Automatizar project.

## Directory Structure

```
tests/
├── __init__.py                 # Test suite package marker
├── conftest.py                 # Pytest configuration and shared fixtures
├── fixtures/                   # Reusable test fixtures and mock data
│   └── __init__.py
├── unit/                       # Unit tests (pure, isolated tests)
│   ├── __init__.py
│   ├── services/              # Tests for services module
│   │   └── __init__.py
│   ├── processadores/         # Tests for processadores module
│   │   └── __init__.py
│   └── utils/                 # Tests for utils module
│       └── __init__.py
└── README.md                   # This file
```

## Getting Started

### Install Test Dependencies

```bash
pip install -r requirements-test.txt
```

### Run All Tests

```bash
pytest
```

### Run Tests with Coverage Report

```bash
pytest --cov=src --cov-report=html:coverage_html
```

Coverage report will be generated in `coverage_html/` directory.

### Run Specific Test Category

```bash
# Run only unit tests
pytest tests/unit/

# Run only services tests
pytest tests/unit/services/

# Run tests by marker
pytest -m unit
pytest -m integration
```

### Run Tests with Verbose Output

```bash
pytest -v
```

## Test Markers

Tests can be marked with pytest markers for selective execution:

- `@pytest.mark.unit` - Pure unit tests (no I/O, mocking all dependencies)
- `@pytest.mark.integration` - Integration tests (test multiple components together)
- `@pytest.mark.slow` - Tests that take more than 1 second

Example usage:

```python
@pytest.mark.unit
def test_my_function():
    assert True
```

## Test Structure Best Practices

### Unit Tests

Unit tests should:
- Test a single function or method in isolation
- Mock all external dependencies (database, API calls, file I/O)
- Be fast (< 100ms each)
- Have clear, descriptive names
- Use the `@pytest.mark.unit` decorator

Location: `tests/unit/{module_name}/test_{file_name}.py`

Example:

```python
import pytest
from unittest.mock import Mock

@pytest.mark.unit
def test_process_data_with_valid_input():
    # Setup
    mock_db = Mock()
    from src.services.data_processor import DataProcessor
    processor = DataProcessor(db=mock_db)

    # Act
    result = processor.process({'key': 'value'})

    # Assert
    assert result is not None
    mock_db.save.assert_called_once()
```

### Fixtures

Place reusable fixtures in `tests/fixtures/` or `tests/conftest.py`:

```python
# tests/fixtures/__init__.py or conftest.py
import pytest

@pytest.fixture
def sample_data():
    return {'id': 1, 'name': 'Test'}
```

Use in tests:

```python
@pytest.mark.unit
def test_with_fixture(sample_data):
    assert sample_data['id'] == 1
```

## Configuration

Test behavior is configured in `pytest.ini`:

- **testpaths**: Directory where tests are discovered
- **python_files**: Pattern for test files (`test_*.py`)
- **python_classes**: Pattern for test classes (`Test*`)
- **python_functions**: Pattern for test functions (`test_*`)
- **addopts**: Default command-line options
- **markers**: Available pytest markers
- **filterwarnings**: Ignore specific deprecation warnings

## Coverage

The project enforces a **minimum 50% code coverage** (`--cov-fail-under=50`).

Coverage reports include:
- Terminal output with missing lines
- HTML report in `coverage_html/` directory

To view the HTML report:

```bash
open coverage_html/index.html  # macOS
xdg-open coverage_html/index.html  # Linux
start coverage_html/index.html  # Windows
```

## Writing Your First Test

1. Create a test file in the appropriate directory under `tests/unit/`
2. Name it `test_*.py`
3. Import the module you're testing
4. Write a test function starting with `test_`
5. Use assertions to verify behavior

Example: `tests/unit/utils/test_validators.py`

```python
import pytest
from src.utils.validators import validate_email

@pytest.mark.unit
def test_validate_email_with_valid_address():
    assert validate_email("user@example.com") is True

@pytest.mark.unit
def test_validate_email_with_invalid_address():
    assert validate_email("invalid") is False
```

## Useful Plugins

The test suite includes these pytest plugins:

- **pytest-mock**: Enhanced mocking with `mocker` fixture
- **pytest-cov**: Code coverage reporting
- **pytest-asyncio**: Async/await test support
- **freezegun**: Time mocking for time-dependent tests
- **faker**: Generate realistic test data

## Continuous Integration

Tests should pass before commits:

```bash
# Run all tests with coverage
pytest --cov=src --cov-fail-under=50
```

This command:
- Runs all tests
- Generates coverage report
- Fails if coverage drops below 50%

## Debugging Tests

### Run a Single Test

```bash
pytest tests/unit/services/test_cache.py::test_cache_miss
```

### Show Print Output

```bash
pytest -s
```

### Stop at First Failure

```bash
pytest -x
```

### Run Last Failed Test

```bash
pytest --lf
```

### Drop into Debugger on Failure

```bash
pytest --pdb
```

## Common Issues

### ModuleNotFoundError

Ensure the project root is in PYTHONPATH:

```bash
# From project root
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$(pwd)"
pytest
```

Or use pytest from the project root directory.

### Import Issues with src/

If tests can't import from `src/`, add to `conftest.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
```

---

For more information, see [pytest documentation](https://docs.pytest.org/).
