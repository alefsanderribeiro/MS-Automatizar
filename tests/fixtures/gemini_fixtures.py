"""Gemini AI service fixtures for testing."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any, Optional
import json


# ==================== Gemini Response Fixtures ====================

@pytest.fixture
def gemini_folha_ponto_response():
    """
    Typical Gemini API response for folha de ponto analysis.

    Returns:
        Mock response object with folha de ponto data
    """
    response_data = {
        "dias_analisados": 20,
        "taxa_preenchimento": 85.5,
        "dias": [
            {
                "numero_dia": 1,
                "hora_entrada": "08:00",
                "hora_intervalo_inicio": "12:00",
                "hora_intervalo_fim": "13:00",
                "hora_saida": "17:00",
                "total_horas_trabalhadas": "08:00",
                "tipo_dia": "NORMAL"
            },
            {
                "numero_dia": 2,
                "hora_entrada": "08:00",
                "hora_intervalo_inicio": "12:00",
                "hora_intervalo_fim": "13:00",
                "hora_saida": "17:00",
                "total_horas_trabalhadas": "08:00",
                "tipo_dia": "NORMAL"
            }
        ],
        "total_horas_mes": "160:00",
        "total_faltas": 0,
        "avisos": [],
        "erros": []
    }

    response = MagicMock()
    response.text = json.dumps(response_data)
    response.status_code = 200

    return response


@pytest.fixture
def gemini_holerite_response():
    """
    Typical Gemini API response for holerite OCR extraction.

    Returns:
        Mock response object with holerite data
    """
    response_data = {
        "funcionario": {
            "nome": "JOÃO SILVA",
            "pis": "12345678901",
            "cpf": "123.456.789-00",
            "funcao": "ANALISTA DE SISTEMAS",
            "lotacao": "TI"
        },
        "empresa": {
            "nome": "MORAES & SANTOS CONSULTORIA LTDA",
            "cnpj": "12.345.678/0001-90"
        },
        "periodo": {
            "mes_referencia": "2025-01",
            "data_pagamento": "2025-02-05"
        },
        "valores": {
            "salario_base": 5000.00,
            "total_vencimentos": 5500.00,
            "total_descontos": 1200.00,
            "liquido": 4300.00
        }
    }

    response = MagicMock()
    response.text = json.dumps(response_data)
    response.status_code = 200

    return response


@pytest.fixture
def gemini_error_response():
    """
    Gemini API error response.

    Returns:
        Mock response object with error
    """
    response = MagicMock()
    response.text = json.dumps({"error": "API quota exceeded"})
    response.status_code = 429

    return response


# ==================== Gemini Service Mocks ====================

@pytest.fixture
def mock_gemini_service():
    """
    Mock Gemini AI service with retry logic.

    Returns:
        Mock service with analyze_document and extract_data methods
    """
    service = MagicMock()

    # Mock analyze_document method
    async def mock_analyze_document(
        file_path: str,
        prompt: str,
        retry_count: int = 3
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "data": {
                "dias_analisados": 20,
                "taxa_preenchimento": 85.5
            },
            "tokens_used": 1500,
            "model": "gemini-2.5-flash-lite"
        }

    # Mock extract_data method
    async def mock_extract_data(
        file_path: str,
        extraction_type: str = "holerite"
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "data": {
                "funcionario": {
                    "nome": "JOÃO SILVA",
                    "pis": "12345678901"
                },
                "empresa": {
                    "nome": "EMPRESA TESTE",
                    "cnpj": "12.345.678/0001-90"
                }
            }
        }

    service.analyze_document = mock_analyze_document
    service.extract_data = mock_extract_data

    return service


@pytest.fixture
def mock_gemini_service_with_retry():
    """
    Mock Gemini service that simulates retry behavior.

    Returns:
        Mock service that fails first 2 attempts, succeeds on 3rd
    """
    service = MagicMock()

    # Counter for tracking retry attempts
    attempt_count = {"count": 0}

    async def mock_analyze_with_retry(
        file_path: str,
        prompt: str,
        retry_count: int = 3
    ) -> Dict[str, Any]:
        attempt_count["count"] += 1

        # Fail first 2 attempts
        if attempt_count["count"] < 3:
            raise ConnectionError("Gemini API timeout")

        # Success on 3rd attempt
        return {
            "success": True,
            "data": {"dias_analisados": 20},
            "attempt": attempt_count["count"]
        }

    service.analyze_document = mock_analyze_with_retry
    service._attempt_count = attempt_count  # Expose for testing

    return service


@pytest.fixture
def mock_gemini_service_failure():
    """
    Mock Gemini service that always fails.

    Returns:
        Mock service that raises exceptions on all calls
    """
    service = MagicMock()

    async def mock_analyze_failure(*args, **kwargs):
        raise Exception("Gemini API error: Model not available")

    service.analyze_document = mock_analyze_failure
    service.extract_data = mock_analyze_failure

    return service


# ==================== Gemini Response Factories ====================

@pytest.fixture
def gemini_response_factory():
    """
    Factory for creating custom Gemini responses.

    Usage:
        def test_example(gemini_response_factory):
            response = gemini_response_factory(
                success=True,
                data={"dias_analisados": 15}
            )
    """
    def _create_response(
        success: bool = True,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        tokens_used: int = 1000,
        model: str = "gemini-2.5-flash-lite"
    ) -> Dict[str, Any]:
        response = {
            "success": success,
            "model": model,
            "tokens_used": tokens_used
        }

        if success:
            response["data"] = data or {}
        else:
            response["error"] = error or "Unknown error"

        return response

    return _create_response


@pytest.fixture
def gemini_folha_ponto_factory():
    """
    Factory for creating folha de ponto Gemini responses with variations.

    Usage:
        def test_example(gemini_folha_ponto_factory):
            response = gemini_folha_ponto_factory(dias_analisados=25)
    """
    def _create_folha_response(
        dias_analisados: int = 20,
        taxa_preenchimento: float = 85.5,
        total_horas_mes: str = "160:00",
        avisos: list = None,
        erros: list = None
    ) -> Dict[str, Any]:
        return {
            "dias_analisados": dias_analisados,
            "taxa_preenchimento": taxa_preenchimento,
            "total_horas_mes": total_horas_mes,
            "avisos": avisos or [],
            "erros": erros or []
        }

    return _create_folha_response


@pytest.fixture
def gemini_holerite_factory():
    """
    Factory for creating holerite extraction responses.

    Usage:
        def test_example(gemini_holerite_factory):
            response = gemini_holerite_factory(
                funcionario_nome="João Silva",
                empresa_nome="Teste Corp"
            )
    """
    def _create_holerite_response(
        funcionario_nome: str = "JOÃO SILVA",
        funcionario_pis: str = "12345678901",
        empresa_nome: str = "EMPRESA TESTE LTDA",
        empresa_cnpj: str = "12.345.678/0001-90",
        mes_referencia: str = "2025-01",
        salario_base: float = 5000.00
    ) -> Dict[str, Any]:
        return {
            "funcionario": {
                "nome": funcionario_nome,
                "pis": funcionario_pis
            },
            "empresa": {
                "nome": empresa_nome,
                "cnpj": empresa_cnpj
            },
            "periodo": {
                "mes_referencia": mes_referencia
            },
            "valores": {
                "salario_base": salario_base
            }
        }

    return _create_holerite_response


# ==================== Prompt Template Fixtures ====================

@pytest.fixture
def gemini_prompt_templates():
    """
    Sample Gemini prompt templates.

    Returns:
        Dictionary of prompt templates for different use cases
    """
    return {
        "folha_ponto": """
            Analise o arquivo de folha de ponto e extraia:
            - Dias preenchidos com horários de entrada/saída
            - Total de horas trabalhadas
            - Faltas e observações

            Retorne em formato JSON.
        """,
        "holerite": """
            Extraia os dados do holerite:
            - Nome do funcionário e PIS
            - Nome da empresa e CNPJ
            - Valores de salário e descontos

            Retorne em formato JSON estruturado.
        """,
        "ocr_simple": """
            Extraia todo o texto visível do documento.
            Preserve a formatação e estrutura.
        """
    }
