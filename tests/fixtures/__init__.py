"""Test fixtures and mock data.

This package contains specialized fixtures organized by domain:

- mongodb_fixtures: MongoDB mocks, service fixtures, document factories
- redis_fixtures: Redis mocks, cache service fixtures, cache key builders
- model_fixtures: Pydantic model instances and factories
- gemini_fixtures: Gemini AI service mocks and response factories
- file_fixtures: File creation, directory structures, path helpers

Global fixtures are in tests/conftest.py.
"""

# Import all fixtures to make them discoverable by pytest
from .mongodb_fixtures import *
from .redis_fixtures import *
from .model_fixtures import *
from .gemini_fixtures import *
from .file_fixtures import *
