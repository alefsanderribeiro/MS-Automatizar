"""File-related test fixtures."""

import pytest
from pathlib import Path
from typing import Dict, Any
import tempfile
import os


# ==================== Temporary File Fixtures ====================

@pytest.fixture
def temp_pdf_file(temp_directory):
    """
    Creates a temporary PDF file for testing.

    Returns:
        Path to temporary PDF file (auto-cleanup)
    """
    pdf_path = temp_directory / "test_file.pdf"

    # Create minimal valid PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000314 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
407
%%EOF"""

    pdf_path.write_bytes(pdf_content)
    return pdf_path


@pytest.fixture
def temp_excel_file(temp_directory):
    """
    Creates a temporary Excel file for testing.

    Returns:
        Path to temporary Excel file
    """
    excel_path = temp_directory / "test_file.xlsx"

    # Create minimal Excel file using openpyxl
    try:
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws["A1"] = "Nome"
        ws["B1"] = "PIS"
        ws["A2"] = "João Silva"
        ws["B2"] = "12345678901"
        wb.save(excel_path)
    except ImportError:
        # Fallback: create empty file
        excel_path.touch()

    return excel_path


@pytest.fixture
def temp_json_file(temp_directory):
    """
    Creates a temporary JSON file for testing.

    Returns:
        Path to temporary JSON file
    """
    import json

    json_path = temp_directory / "test_file.json"

    test_data = {
        "funcionarios": [
            {"nome": "João Silva", "pis": "12345678901"},
            {"nome": "Maria Santos", "pis": "98765432109"}
        ]
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(test_data, f, indent=2, ensure_ascii=False)

    return json_path


@pytest.fixture
def temp_text_file(temp_directory):
    """
    Creates a temporary text file for testing.

    Returns:
        Path to temporary text file
    """
    text_path = temp_directory / "test_file.txt"

    content = """Arquivo de teste
Linha 2
Linha 3 com acentuação: áéíóú
"""

    text_path.write_text(content, encoding="utf-8")
    return text_path


# ==================== Directory Fixtures ====================

@pytest.fixture
def temp_directory(tmp_path):
    """
    Temporary directory fixture for file operations.

    Returns:
        Path to temporary directory (auto-cleanup)
    """
    return tmp_path


@pytest.fixture
def temp_directory_structure(temp_directory):
    """
    Creates a temporary directory structure for testing.

    Returns:
        Dictionary with paths to different directories
    """
    structure = {
        "root": temp_directory,
        "input": temp_directory / "input",
        "output": temp_directory / "output",
        "cache": temp_directory / "cache",
        "logs": temp_directory / "logs"
    }

    # Create all directories
    for path in structure.values():
        path.mkdir(exist_ok=True)

    return structure


@pytest.fixture
def temp_nested_directories(temp_directory):
    """
    Creates nested directory structure for testing.

    Returns:
        Path to root with nested subdirectories
    """
    nested = temp_directory / "empresa1" / "funcionarios" / "folhas_ponto"
    nested.mkdir(parents=True, exist_ok=True)

    return temp_directory


# ==================== File Path Fixtures ====================

@pytest.fixture
def sample_file_paths(temp_directory):
    """
    Factory for generating file paths for testing.

    Usage:
        def test_example(sample_file_paths):
            paths = sample_file_paths(count=3, extension=".pdf")
    """
    def _generate_paths(count: int = 1, extension: str = ".pdf") -> list:
        return [
            temp_directory / f"file_{i}{extension}"
            for i in range(count)
        ]

    return _generate_paths


@pytest.fixture
def absolute_path_converter():
    """
    Helper for converting relative paths to absolute.

    Usage:
        def test_example(absolute_path_converter):
            abs_path = absolute_path_converter("data/file.pdf")
    """
    def _to_absolute(relative_path: str) -> Path:
        return Path(relative_path).resolve()

    return _to_absolute


# ==================== File Content Factories ====================

@pytest.fixture
def pdf_content_factory():
    """
    Factory for creating PDF content variations.

    Usage:
        def test_example(pdf_content_factory):
            content = pdf_content_factory(text="Folha de Ponto - Janeiro 2025")
    """
    def _create_pdf_content(text: str = "Test PDF") -> bytes:
        # Minimal valid PDF with custom text
        return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(""" + text.encode('utf-8') + b""") Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000314 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
407
%%EOF"""

    return _create_pdf_content


@pytest.fixture
def excel_content_factory():
    """
    Factory for creating Excel content variations.

    Usage:
        def test_example(excel_content_factory, temp_directory):
            path = excel_content_factory(
                temp_directory / "test.xlsx",
                data={"Nome": ["João", "Maria"], "PIS": ["111", "222"]}
            )
    """
    def _create_excel(file_path: Path, data: Dict[str, list]) -> Path:
        try:
            from openpyxl import Workbook

            wb = Workbook()
            ws = wb.active

            # Write headers
            for col_idx, header in enumerate(data.keys(), start=1):
                ws.cell(row=1, column=col_idx, value=header)

            # Write data
            for row_idx in range(len(next(iter(data.values())))):
                for col_idx, values in enumerate(data.values(), start=1):
                    ws.cell(row=row_idx + 2, column=col_idx, value=values[row_idx])

            wb.save(file_path)
            return file_path

        except ImportError:
            # Fallback: create empty file
            file_path.touch()
            return file_path

    return _create_excel


# ==================== File Validation Helpers ====================

@pytest.fixture
def file_exists_checker():
    """
    Helper for checking if files exist.

    Usage:
        def test_example(file_exists_checker):
            assert file_exists_checker("path/to/file.pdf")
    """
    def _check_exists(file_path: str) -> bool:
        return Path(file_path).exists()

    return _check_exists


@pytest.fixture
def file_size_getter():
    """
    Helper for getting file size.

    Usage:
        def test_example(file_size_getter):
            size = file_size_getter("path/to/file.pdf")
    """
    def _get_size(file_path: str) -> int:
        return Path(file_path).stat().st_size

    return _get_size
