"""
Unit tests for HoleriteProcessador

Tests cover:
1. Initialization with dependency injection
2. Disponibilidade check (Gemini + Services)
3. Hash calculation (SHA256)
4. File validation (PDF, existence)
5. Gemini extraction with retry logic
6. Funcionario lookup (by CPF) and autocreate
7. Empresa lookup and autocreate
8. MongoDB storage
9. Hash duplicate detection
10. Directory processing
11. Statistics tracking
12. Complete pipeline

Target: 50%+ coverage (~211 lines of 426)

Nota: os "KNOWN CODE BUGS" abaixo foram corrigidos no código atual
(processador usa `funcionario_cpf`, `empresa_razao_social`, `mes_referencia`/`ano_referencia`
e `HoleriteMongoDB.from_extracao` com objetos ArquivoHolerite/ProcessamentoHolerite).
Os testes antes pulados por esses bugs foram reativados e adaptados ao comportamento atual.
"""

import pytest
import json
import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock, call
from datetime import datetime, timezone
from bson import ObjectId

from src.processadores.holerite_processador import (
    HoleriteProcessador,
    ResultadoProcessamentoHolerite,
)
from src.models.holerite_models import (
    HoleriteExtracaoSchema,
    HoleriteMongoDB,
    ItemHoleriteExtracao,
    StatusHoleriteEnum,
    TipoFolhaEnum,
)


# ==================== Test Class: TestHoleriteProcessadorInit ====================

class TestHoleriteProcessadorInit:
    """Test initialization and dependency injection."""

    def test_init_com_todas_dependencias_injetadas(self):
        """Test initialization with all services injected."""
        mock_gemini = MagicMock()
        mock_holerite_service = MagicMock()
        mock_funcionario_service = MagicMock()
        mock_contato_service = MagicMock()
        mock_empresa_service = MagicMock()

        processador = HoleriteProcessador(
            gemini_service=mock_gemini,
            holerite_service=mock_holerite_service,
            funcionario_service=mock_funcionario_service,
            contato_service=mock_contato_service,
            empresa_service=mock_empresa_service,
        )

        assert processador.gemini is mock_gemini
        assert processador.holerite_service is mock_holerite_service
        assert processador.funcionario_service is mock_funcionario_service
        assert processador.contato_service is mock_contato_service
        assert processador.empresa_service is mock_empresa_service

    def test_init_cria_servicos_se_none(self, mocker):
        """Test that services are created when not provided."""
        mock_gemini_class = mocker.patch(
            'src.processadores.holerite_processador.GeminiService'
        )
        mock_holerite_class = mocker.patch(
            'src.processadores.holerite_processador.HoleriteService'
        )
        mock_funcionario_class = mocker.patch(
            'src.processadores.holerite_processador.FuncionarioService'
        )
        mock_contato_class = mocker.patch(
            'src.processadores.holerite_processador.ContatoFuncionarioService'
        )
        mock_empresa_class = mocker.patch(
            'src.processadores.holerite_processador.EmpresaService'
        )

        processador = HoleriteProcessador()

        mock_gemini_class.assert_called_once()
        mock_holerite_class.assert_called_once()
        mock_funcionario_class.assert_called_once()
        mock_contato_class.assert_called_once()
        mock_empresa_class.assert_called_once()

    def test_init_gemini_none_quando_nao_disponivel(self, mocker):
        """Test that gemini is None when GEMINI_DISPONIVEL is False."""
        mocker.patch('src.processadores.holerite_processador.GEMINI_DISPONIVEL', False)

        processador = HoleriteProcessador(
            gemini_service=None,
            holerite_service=MagicMock(),
            funcionario_service=MagicMock(),
            contato_service=MagicMock(),
            empresa_service=MagicMock(),
        )

        assert processador.gemini is None

    def test_init_estatisticas_zeradas(self):
        """Test that statistics counters are initialized to zero."""
        processador = HoleriteProcessador(
            gemini_service=MagicMock(),
            holerite_service=MagicMock(),
            funcionario_service=MagicMock(),
            contato_service=MagicMock(),
            empresa_service=MagicMock(),
        )

        assert processador.total_processados == 0
        assert processador.total_sucesso == 0
        assert processador.total_falhas == 0


# ==================== Test Class: TestDisponivel ====================

class TestDisponivel:
    """Test disponivel property."""

    def test_disponivel_quando_todos_servicos_ok(self):
        """Test disponivel returns True when all services are available."""
        mock_gemini = MagicMock()
        mock_holerite_service = MagicMock()
        mock_holerite_service.disponivel = True
        mock_funcionario_service = MagicMock()
        mock_funcionario_service.disponivel = True

        processador = HoleriteProcessador(
            gemini_service=mock_gemini,
            holerite_service=mock_holerite_service,
            funcionario_service=mock_funcionario_service,
            contato_service=MagicMock(),
            empresa_service=MagicMock(),
        )

        assert processador.disponivel is True

    def test_disponivel_false_quando_gemini_none(self, mocker):
        """Test disponivel returns False when Gemini is None."""
        # Prevent auto-creation of GeminiService
        mocker.patch('src.processadores.holerite_processador.GEMINI_DISPONIVEL', False)

        mock_holerite_service = MagicMock()
        mock_holerite_service.disponivel = True
        mock_funcionario_service = MagicMock()
        mock_funcionario_service.disponivel = True

        processador = HoleriteProcessador(
            gemini_service=None,
            holerite_service=mock_holerite_service,
            funcionario_service=mock_funcionario_service,
            contato_service=MagicMock(),
            empresa_service=MagicMock(),
        )

        assert processador.disponivel is False

    def test_disponivel_false_quando_holerite_service_indisponivel(self):
        """Test disponivel returns False when holerite_service is unavailable."""
        mock_gemini = MagicMock()
        mock_holerite_service = MagicMock()
        mock_holerite_service.disponivel = False
        mock_funcionario_service = MagicMock()
        mock_funcionario_service.disponivel = True

        processador = HoleriteProcessador(
            gemini_service=mock_gemini,
            holerite_service=mock_holerite_service,
            funcionario_service=mock_funcionario_service,
            contato_service=MagicMock(),
            empresa_service=MagicMock(),
        )

        assert processador.disponivel is False

    def test_disponivel_false_quando_funcionario_service_indisponivel(self):
        """Test disponivel returns False when funcionario_service is unavailable."""
        mock_gemini = MagicMock()
        mock_holerite_service = MagicMock()
        mock_holerite_service.disponivel = True
        mock_funcionario_service = MagicMock()
        mock_funcionario_service.disponivel = False

        processador = HoleriteProcessador(
            gemini_service=mock_gemini,
            holerite_service=mock_holerite_service,
            funcionario_service=mock_funcionario_service,
            contato_service=MagicMock(),
            empresa_service=MagicMock(),
        )

        assert processador.disponivel is False


# ==================== Test Class: TestCalcularHashArquivo ====================

class TestCalcularHashArquivo:
    """Test calcular_hash_arquivo method."""

    @pytest.fixture
    def processador(self):
        """Create processador with mocked services."""
        return HoleriteProcessador(
            gemini_service=MagicMock(),
            holerite_service=MagicMock(),
            funcionario_service=MagicMock(),
            contato_service=MagicMock(),
            empresa_service=MagicMock(),
        )

    def test_calcular_hash_arquivo_valido(self, processador, temp_pdf_file):
        """Test hash calculation for valid file."""
        hash_result = processador.calcular_hash_arquivo(temp_pdf_file)

        assert hash_result is not None
        assert len(hash_result) == 64  # SHA256 hex digest length

    def test_calcular_hash_arquivo_reproduzivel(self, processador, temp_pdf_file):
        """Test that hash is reproducible for same file."""
        hash1 = processador.calcular_hash_arquivo(temp_pdf_file)
        hash2 = processador.calcular_hash_arquivo(temp_pdf_file)

        assert hash1 == hash2

    def test_calcular_hash_arquivo_inexistente(self, processador, tmp_path):
        """Test hash calculation returns None for non-existent file."""
        arquivo_inexistente = tmp_path / "nao_existe.pdf"

        hash_result = processador.calcular_hash_arquivo(arquivo_inexistente)

        assert hash_result is None

    def test_calcular_hash_diferentes_para_conteudos_diferentes(self, processador, tmp_path):
        """Test that different files produce different hashes."""
        arquivo1 = tmp_path / "file1.pdf"
        arquivo2 = tmp_path / "file2.pdf"
        arquivo1.write_bytes(b"%PDF-1.4\nContent A\n%%EOF")
        arquivo2.write_bytes(b"%PDF-1.4\nContent B\n%%EOF")

        hash1 = processador.calcular_hash_arquivo(arquivo1)
        hash2 = processador.calcular_hash_arquivo(arquivo2)

        assert hash1 != hash2


# ==================== Test Class: TestProcessarArquivoValidacoes ====================

class TestProcessarArquivoValidacoes:
    """Test file validation in processar_arquivo."""

    @pytest.fixture
    def processador_disponivel(self):
        """Create processador with all services available."""
        mock_gemini = MagicMock()
        mock_holerite_service = MagicMock()
        mock_holerite_service.disponivel = True
        mock_funcionario_service = MagicMock()
        mock_funcionario_service.disponivel = True

        return HoleriteProcessador(
            gemini_service=mock_gemini,
            holerite_service=mock_holerite_service,
            funcionario_service=mock_funcionario_service,
            contato_service=MagicMock(),
            empresa_service=MagicMock(),
        )

    def test_processar_arquivo_nao_disponivel(self, mocker):
        """Test processar_arquivo fails when processador is not disponivel."""
        # Prevent auto-creation of GeminiService
        mocker.patch('src.processadores.holerite_processador.GEMINI_DISPONIVEL', False)

        mock_holerite_service = MagicMock()
        mock_holerite_service.disponivel = False  # Service not available
        mock_funcionario_service = MagicMock()
        mock_funcionario_service.disponivel = True

        processador = HoleriteProcessador(
            gemini_service=None,  # Gemini indisponível
            holerite_service=mock_holerite_service,
            funcionario_service=mock_funcionario_service,
            contato_service=MagicMock(),
            empresa_service=MagicMock(),
        )

        resultado = processador.processar_arquivo(Path("/test/file.pdf"))

        assert resultado.sucesso is False
        assert "não disponível" in resultado.erro or "indisponível" in resultado.erro

    def test_processar_arquivo_nao_existe(self, processador_disponivel, tmp_path):
        """Test processar_arquivo fails when file does not exist."""
        arquivo_inexistente = tmp_path / "nao_existe.pdf"

        resultado = processador_disponivel.processar_arquivo(arquivo_inexistente)

        assert resultado.sucesso is False
        assert "não encontrado" in resultado.erro

    def test_processar_arquivo_nao_pdf(self, processador_disponivel, tmp_path):
        """Test processar_arquivo fails when file is not PDF."""
        arquivo_txt = tmp_path / "arquivo.txt"
        arquivo_txt.write_text("Não é PDF")

        resultado = processador_disponivel.processar_arquivo(arquivo_txt)

        assert resultado.sucesso is False
        assert "não é PDF" in resultado.erro

    def test_processar_arquivo_aceita_path_como_string(self, processador_disponivel, temp_pdf_file):
        """Test processar_arquivo accepts path as string."""
        processador_disponivel.holerite_service.buscar_por_hash = MagicMock(return_value=None)
        processador_disponivel.gemini.documento_estruturado = MagicMock(side_effect=Exception("Test"))

        resultado = processador_disponivel.processar_arquivo(str(temp_pdf_file))

        # Should convert to Path and proceed with validation
        assert isinstance(resultado, ResultadoProcessamentoHolerite)


# ==================== Test Class: TestProcessarArquivoExtracao ====================

class TestProcessarArquivoExtracao:
    """Test Gemini extraction in processar_arquivo."""

    @pytest.fixture
    def processador_com_mocks(self):
        """Create processador with mocked services."""
        mock_gemini = MagicMock()
        mock_holerite_service = MagicMock()
        mock_holerite_service.disponivel = True
        mock_holerite_service.buscar_por_hash = MagicMock(return_value=None)
        mock_funcionario_service = MagicMock()
        mock_funcionario_service.disponivel = True

        processador = HoleriteProcessador(
            gemini_service=mock_gemini,
            holerite_service=mock_holerite_service,
            funcionario_service=mock_funcionario_service,
            contato_service=MagicMock(),
            empresa_service=MagicMock(),
        )
        return processador, mock_gemini

    @pytest.fixture
    def extracao_json_valida(self):
        """Valid Gemini extraction JSON - Note: code expects 'competencia' attribute."""
        extracao_dict = {
            "empresa_razao_social": "Empresa Teste Ltda",
            "empresa_cnpj": "12.345.678/0001-90",
            "funcionario_nome": "João Silva",
            "funcionario_cpf": "12345678900",
            "tipo_folha": "Folha Mensal",
            "mes_referencia_texto": "Janeiro de 2025",
            "mes_referencia": 1,
            "ano_referencia": 2025,
            "vencimentos": [
                {
                    "codigo": 100,
                    "descricao": "Salário Base",
                    "referencia": "1,00",
                    "valor": 5000.00
                }
            ],
            "total_vencimentos": 5000.00,
            "descontos": [
                {
                    "codigo": 998,
                    "descricao": "INSS",
                    "referencia": "8%",
                    "valor": 400.00
                }
            ],
            "total_descontos": 400.00,
            "valor_liquido": 4600.00
        }
        return json.dumps(extracao_dict)

    def test_processar_arquivo_extracao_sucesso(
        self, processador_com_mocks, extracao_json_valida, temp_pdf_file
    ):
        """Test successful extraction with Gemini.

        Note: Full pipeline will fail due to bug in line 239 (extracao.competencia doesn't exist).
        This test verifies that extraction parsing works and data is captured.
        """
        processador, mock_gemini = processador_com_mocks
        mock_gemini.documento_estruturado.return_value = extracao_json_valida

        resultado = processador.processar_arquivo(temp_pdf_file)

        # Extraction should parse successfully but fail at logging due to missing competencia
        assert resultado.extracao is not None
        assert resultado.extracao.funcionario_nome == "João Silva"
        assert resultado.extracao_json is not None
        # tempo_extracao_s may be 0 if exception happens during extraction attempt
        # Will have error due to code bug at line 239
        #assert "competencia" in resultado.erro.lower()

    def test_processar_arquivo_extracao_retry_logic(
        self, processador_com_mocks, extracao_json_valida, temp_pdf_file
    ):
        """Test extraction retry logic (max 2 attempts).

        Note: Will fail at post-extraction due to code bug, but retry logic works.
        """
        processador, mock_gemini = processador_com_mocks

        # First call fails, second succeeds
        mock_gemini.documento_estruturado.side_effect = [
            Exception("API Error"),
            extracao_json_valida
        ]

        resultado = processador.processar_arquivo(temp_pdf_file)

        # Verify retry happened
        assert mock_gemini.documento_estruturado.call_count == 2
        # Extraction parsed but fails at post-processing
        assert resultado.extracao is not None

    def test_processar_arquivo_extracao_max_tentativas_excedidas(
        self, processador_com_mocks, temp_pdf_file
    ):
        """Test extraction fails after max_tentativas."""
        processador, mock_gemini = processador_com_mocks

        # All attempts fail
        mock_gemini.documento_estruturado.side_effect = [
            Exception("Error 1"),
            Exception("Error 2")
        ]

        resultado = processador.processar_arquivo(temp_pdf_file, max_tentativas=2)

        assert resultado.sucesso is False
        assert "Falha na extração" in resultado.erro
        assert mock_gemini.documento_estruturado.call_count == 2

    def test_processar_arquivo_extracao_resposta_curta(
        self, processador_com_mocks, extracao_json_valida, temp_pdf_file
    ):
        """Test extraction retry when response is too short."""
        processador, mock_gemini = processador_com_mocks

        # Short response triggers retry
        mock_gemini.documento_estruturado.side_effect = [
            '{"empresa_razao_social": "Test"}',  # < 50 chars
            extracao_json_valida
        ]

        processador.funcionario_service.criar_ou_buscar_por_documento = MagicMock(
            return_value={'_id': ObjectId()}
        )
        processador.empresa_service.buscar_por_nome = MagicMock(return_value=None)
        processador.holerite_service.criar_holerite = MagicMock(return_value=ObjectId())
        processador.contato_service.criar_ou_atualizar = MagicMock()

        resultado = processador.processar_arquivo(temp_pdf_file, max_tentativas=2)

        assert mock_gemini.documento_estruturado.call_count == 2

    def test_processar_arquivo_temperatura_customizada(
        self, processador_com_mocks, extracao_json_valida, temp_pdf_file
    ):
        """Test that custom temperatura is passed to Gemini."""
        processador, mock_gemini = processador_com_mocks
        mock_gemini.documento_estruturado.return_value = extracao_json_valida

        processador.funcionario_service.criar_ou_buscar_por_documento = MagicMock(
            return_value={'_id': ObjectId()}
        )
        processador.empresa_service.buscar_por_nome = MagicMock(return_value=None)
        processador.holerite_service.criar_holerite = MagicMock(return_value=ObjectId())
        processador.contato_service.criar_ou_atualizar = MagicMock()

        processador.processar_arquivo(temp_pdf_file, temperatura=0.5)

        call_args = mock_gemini.documento_estruturado.call_args
        assert call_args[1]['temperature'] == 0.5


# ==================== Test Class: TestProcessarArquivoLookup ====================

class TestProcessarArquivoLookup:
    """Test funcionario and empresa lookup in processar_arquivo."""

    @pytest.fixture
    def processador_com_extracao_ok(self, mocker):
        """Create processador with successful extraction mocked."""
        mock_gemini = MagicMock()
        mock_holerite_service = MagicMock()
        mock_holerite_service.disponivel = True
        mock_holerite_service.buscar_por_hash = MagicMock(return_value=None)
        mock_funcionario_service = MagicMock()
        mock_funcionario_service.disponivel = True
        mock_empresa_service = MagicMock()

        processador = HoleriteProcessador(
            gemini_service=mock_gemini,
            holerite_service=mock_holerite_service,
            funcionario_service=mock_funcionario_service,
            contato_service=MagicMock(),
            empresa_service=mock_empresa_service,
        )

        # Mock successful extraction
        extracao_json = json.dumps({
            "empresa_razao_social": "Empresa Teste",
            "empresa_cnpj": "12.345.678/0001-90",
            "funcionario_nome": "João Silva",
            "funcionario_cpf": "12345678900",
            "tipo_folha": "Folha Mensal",
            "mes_referencia_texto": "Janeiro de 2025",
            "mes_referencia": 1,
            "ano_referencia": 2025,
            "vencimentos": [],
            "total_vencimentos": 5000.00,
            "descontos": [],
            "total_descontos": 400.00,
            "valor_liquido": 4600.00
        })
        mock_gemini.documento_estruturado.return_value = extracao_json

        return processador

    def test_processar_arquivo_busca_funcionario_por_cpf(
        self, processador_com_extracao_ok, temp_pdf_file
    ):
        """Test funcionario lookup by CPF."""
        func_id = ObjectId()
        processador_com_extracao_ok.funcionario_service.criar_ou_buscar_por_documento = MagicMock(
            return_value={'_id': func_id, 'status_cadastro': 'completo'}
        )
        processador_com_extracao_ok.empresa_service.buscar_por_nome_ou_simplificado = MagicMock(return_value=None)
        processador_com_extracao_ok.holerite_service.criar_holerite = MagicMock(return_value=ObjectId())
        processador_com_extracao_ok.contato_service.criar_ou_atualizar = MagicMock()

        resultado = processador_com_extracao_ok.processar_arquivo(temp_pdf_file)

        processador_com_extracao_ok.funcionario_service.criar_ou_buscar_por_documento.assert_called_once()
        assert resultado.funcionario_id == str(func_id)

    def test_processar_arquivo_cria_novo_funcionario(
        self, processador_com_extracao_ok, temp_pdf_file
    ):
        """Test funcionario autocreate when not found."""
        func_id = ObjectId()
        processador_com_extracao_ok.funcionario_service.criar_ou_buscar_por_documento = MagicMock(
            return_value={'_id': func_id, 'status_cadastro': 'incompleto'}  # Newly created
        )
        processador_com_extracao_ok.empresa_service.buscar_por_nome_ou_simplificado = MagicMock(return_value=None)
        processador_com_extracao_ok.holerite_service.criar_holerite = MagicMock(return_value=ObjectId())
        processador_com_extracao_ok.contato_service.criar_ou_atualizar = MagicMock()

        resultado = processador_com_extracao_ok.processar_arquivo(temp_pdf_file)

        assert resultado.funcionario_criado is True
        assert "Novo funcionário criado" in str(resultado.mensagens)

    def test_processar_arquivo_sem_cpf_busca_por_nome(
        self, processador_com_extracao_ok, temp_pdf_file
    ):
        """Test holerite without CPF still attempts lookup by normalized name.

        Comportamento atual: mesmo sem CPF, se houver nome do funcionário o
        processador chama criar_ou_buscar_por_documento com documento vazio.
        """
        func_id = ObjectId()
        processador_com_extracao_ok.funcionario_service.criar_ou_buscar_por_documento = MagicMock(
            return_value={'_id': func_id, 'status_cadastro': 'completo'}
        )
        processador_com_extracao_ok.empresa_service.buscar_por_nome_ou_simplificado = MagicMock(return_value=None)
        processador_com_extracao_ok.holerite_service.criar_holerite = MagicMock(return_value=ObjectId())
        processador_com_extracao_ok.contato_service.criar_ou_atualizar = MagicMock()

        # Extraction without CPF
        extracao_json = json.dumps({
            "empresa_razao_social": "Empresa Teste",
            "empresa_cnpj": "12.345.678/0001-90",
            "funcionario_nome": "João Silva",
            "funcionario_cpf": None,  # No CPF
            "tipo_folha": "Folha Mensal",
            "mes_referencia_texto": "Janeiro de 2025",
            "mes_referencia": 1,
            "ano_referencia": 2025,
            "vencimentos": [],
            "total_vencimentos": 5000.00,
            "descontos": [],
            "total_descontos": 400.00,
            "valor_liquido": 4600.00
        })
        processador_com_extracao_ok.gemini.documento_estruturado.return_value = extracao_json

        resultado = processador_com_extracao_ok.processar_arquivo(temp_pdf_file)

        # Sem CPF, a busca é feita pelo nome normalizado com documento vazio
        processador_com_extracao_ok.funcionario_service.criar_ou_buscar_por_documento.assert_called_once()
        assert processador_com_extracao_ok.funcionario_service.criar_ou_buscar_por_documento.call_args[1]['documento'] == ""
        assert resultado.funcionario_id == str(func_id)

    def test_processar_arquivo_busca_empresa_por_nome(
        self, processador_com_extracao_ok, temp_pdf_file
    ):
        """Test empresa lookup by name."""
        empresa_id = ObjectId()
        processador_com_extracao_ok.funcionario_service.criar_ou_buscar_por_documento = MagicMock(
            return_value={'_id': ObjectId(), 'status_cadastro': 'completo'}
        )
        processador_com_extracao_ok.empresa_service.buscar_por_nome_ou_simplificado = MagicMock(
            return_value={'_id': empresa_id, 'nome': 'Empresa Teste'}
        )
        processador_com_extracao_ok.holerite_service.criar_holerite = MagicMock(return_value=ObjectId())
        processador_com_extracao_ok.contato_service.criar_ou_atualizar = MagicMock()

        resultado = processador_com_extracao_ok.processar_arquivo(temp_pdf_file)

        processador_com_extracao_ok.empresa_service.buscar_por_nome_ou_simplificado.assert_called_once()
        assert resultado.empresa_id == str(empresa_id)

    def test_processar_arquivo_usa_empresa_id_fornecido(
        self, processador_com_extracao_ok, temp_pdf_file
    ):
        """Test that provided empresa_id is used instead of lookup."""
        empresa_id = str(ObjectId())
        processador_com_extracao_ok.funcionario_service.criar_ou_buscar_por_documento = MagicMock(
            return_value={'_id': ObjectId(), 'status_cadastro': 'completo'}
        )
        processador_com_extracao_ok.holerite_service.criar_holerite = MagicMock(return_value=ObjectId())
        processador_com_extracao_ok.contato_service.criar_ou_atualizar = MagicMock()

        resultado = processador_com_extracao_ok.processar_arquivo(temp_pdf_file, empresa_id=empresa_id)

        # Should not call buscar_por_nome_ou_simplificado
        processador_com_extracao_ok.empresa_service.buscar_por_nome_ou_simplificado.assert_not_called()
        assert resultado.empresa_id == empresa_id


# ==================== Test Class: TestProcessarArquivoArmazenamento ====================

class TestProcessarArquivoArmazenamento:
    """Test MongoDB storage in processar_arquivo."""

    @pytest.fixture
    def processador_completo_mock(self, mocker):
        """Processador with full mocking up to storage."""
        mock_gemini = MagicMock()
        mock_holerite_service = MagicMock()
        mock_holerite_service.disponivel = True
        mock_holerite_service.buscar_por_hash = MagicMock(return_value=None)
        mock_funcionario_service = MagicMock()
        mock_funcionario_service.disponivel = True
        mock_contato_service = MagicMock()

        processador = HoleriteProcessador(
            gemini_service=mock_gemini,
            holerite_service=mock_holerite_service,
            funcionario_service=mock_funcionario_service,
            contato_service=mock_contato_service,
            empresa_service=MagicMock(),
        )

        # Mock extraction
        extracao_json = json.dumps({
            "empresa_razao_social": "Empresa Teste",
            "empresa_cnpj": "12.345.678/0001-90",
            "funcionario_nome": "João Silva",
            "funcionario_cpf": "12345678900",
            "tipo_folha": "Folha Mensal",
            "mes_referencia_texto": "Janeiro de 2025",
            "mes_referencia": 1,
            "ano_referencia": 2025,
            "vencimentos": [],
            "total_vencimentos": 5000.00,
            "descontos": [],
            "total_descontos": 400.00,
            "valor_liquido": 4600.00
        })
        mock_gemini.documento_estruturado.return_value = extracao_json

        return processador

    def test_processar_arquivo_salva_holerite_no_mongodb(
        self, processador_completo_mock, temp_pdf_file
    ):
        """Test that holerite is saved to MongoDB."""
        holerite_id = ObjectId()
        processador_completo_mock.funcionario_service.criar_ou_buscar_por_documento = MagicMock(
            return_value={'_id': ObjectId(), 'status_cadastro': 'completo'}
        )
        # Empresa válida para o pipeline completar até o armazenamento
        processador_completo_mock.empresa_service.buscar_por_nome_ou_simplificado = MagicMock(
            return_value={'_id': ObjectId(), 'nome': 'Empresa Teste'}
        )
        processador_completo_mock.holerite_service.criar_holerite = MagicMock(return_value=holerite_id)
        processador_completo_mock.contato_service.criar_ou_atualizar = MagicMock()

        resultado = processador_completo_mock.processar_arquivo(temp_pdf_file)

        processador_completo_mock.holerite_service.criar_holerite.assert_called_once()
        assert resultado.holerite_id == str(holerite_id)
        assert resultado.sucesso is True

    def test_processar_arquivo_falha_salvar_retorna_erro(
        self, processador_completo_mock, temp_pdf_file
    ):
        """Test error handling when MongoDB save fails."""
        processador_completo_mock.funcionario_service.criar_ou_buscar_por_documento = MagicMock(
            return_value={'_id': ObjectId(), 'status_cadastro': 'completo'}
        )
        processador_completo_mock.empresa_service.buscar_por_nome_ou_simplificado = MagicMock(
            return_value={'_id': ObjectId(), 'nome': 'Empresa Teste'}
        )
        processador_completo_mock.holerite_service.criar_holerite = MagicMock(return_value=None)  # Save fails

        resultado = processador_completo_mock.processar_arquivo(temp_pdf_file)

        assert resultado.sucesso is False
        assert resultado.erro == "Falha ao salvar holerite no MongoDB"

    def test_processar_arquivo_cria_contatos_funcionario(
        self, processador_completo_mock, temp_pdf_file, mocker
    ):
        """Test that funcionario contacts are created/updated."""
        func_id = ObjectId()
        processador_completo_mock.funcionario_service.criar_ou_buscar_por_documento = MagicMock(
            return_value={'_id': func_id, 'status_cadastro': 'completo'}
        )
        processador_completo_mock.empresa_service.buscar_por_nome_ou_simplificado = MagicMock(
            return_value={'_id': ObjectId(), 'nome': 'Empresa Teste'}
        )
        processador_completo_mock.holerite_service.criar_holerite = MagicMock(return_value=ObjectId())

        # Mock criar_contato_de_holerite
        mock_criar_contato = mocker.patch(
            'src.processadores.holerite_processador.criar_contato_de_holerite',
            return_value=[MagicMock(), MagicMock()]  # 2 contacts
        )

        resultado = processador_completo_mock.processar_arquivo(temp_pdf_file)

        mock_criar_contato.assert_called_once()
        assert processador_completo_mock.contato_service.criar_ou_atualizar.call_count == 2
        assert "2 contato(s) criado(s)" in str(resultado.mensagens)

    def test_processar_arquivo_atualiza_estatisticas_sucesso(
        self, processador_completo_mock, temp_pdf_file
    ):
        """Test that statistics are updated on success."""
        processador_completo_mock.funcionario_service.criar_ou_buscar_por_documento = MagicMock(
            return_value={'_id': ObjectId(), 'status_cadastro': 'completo'}
        )
        processador_completo_mock.empresa_service.buscar_por_nome_ou_simplificado = MagicMock(
            return_value={'_id': ObjectId(), 'nome': 'Empresa Teste'}
        )
        processador_completo_mock.holerite_service.criar_holerite = MagicMock(return_value=ObjectId())
        processador_completo_mock.contato_service.criar_ou_atualizar = MagicMock()

        processador_completo_mock.processar_arquivo(temp_pdf_file)

        assert processador_completo_mock.total_processados == 1
        assert processador_completo_mock.total_sucesso == 1
        assert processador_completo_mock.total_falhas == 0

    def test_processar_arquivo_atualiza_estatisticas_falha(
        self, processador_completo_mock, temp_pdf_file
    ):
        """Test that statistics are updated on failure."""
        processador_completo_mock.funcionario_service.criar_ou_buscar_por_documento = MagicMock(
            return_value={'_id': ObjectId(), 'status_cadastro': 'completo'}
        )
        processador_completo_mock.empresa_service.buscar_por_nome_ou_simplificado = MagicMock(
            return_value={'_id': ObjectId(), 'nome': 'Empresa Teste'}
        )
        processador_completo_mock.holerite_service.criar_holerite = MagicMock(side_effect=Exception("DB Error"))

        processador_completo_mock.processar_arquivo(temp_pdf_file)

        assert processador_completo_mock.total_falhas == 1


# ==================== Test Class: TestProcessarArquivoHashDuplicado ====================

class TestProcessarArquivoHashDuplicado:
    """Test duplicate detection via hash."""

    @pytest.fixture
    def processador_mock(self):
        """Create processador with basic mocks."""
        mock_gemini = MagicMock()
        mock_holerite_service = MagicMock()
        mock_holerite_service.disponivel = True
        mock_funcionario_service = MagicMock()
        mock_funcionario_service.disponivel = True

        return HoleriteProcessador(
            gemini_service=mock_gemini,
            holerite_service=mock_holerite_service,
            funcionario_service=mock_funcionario_service,
            contato_service=MagicMock(),
            empresa_service=MagicMock(),
        )

    def test_processar_arquivo_detecta_duplicata_por_hash(
        self, processador_mock, temp_pdf_file
    ):
        """Test duplicate detection when hash already exists."""
        holerite_existente_id = ObjectId()
        func_id = ObjectId()
        processador_mock.holerite_service.buscar_por_hash = MagicMock(
            return_value={'_id': holerite_existente_id, 'funcionario_id': func_id}
        )

        resultado = processador_mock.processar_arquivo(temp_pdf_file)

        assert resultado.sucesso is True
        assert resultado.holerite_id == str(holerite_existente_id)
        assert resultado.funcionario_id == str(func_id)
        assert "já processado anteriormente" in str(resultado.mensagens)

    def test_processar_arquivo_continua_se_hash_nao_existe(
        self, processador_mock, temp_pdf_file
    ):
        """Test processing continues when hash is not found."""
        processador_mock.holerite_service.buscar_por_hash = MagicMock(return_value=None)
        processador_mock.gemini.documento_estruturado = MagicMock(side_effect=Exception("Test"))

        resultado = processador_mock.processar_arquivo(temp_pdf_file)

        # Should attempt extraction (which fails with our mock)
        processador_mock.gemini.documento_estruturado.assert_called()


# ==================== Test Class: TestProcessarDiretorio ====================

class TestProcessarDiretorio:
    """Test processar_diretorio method."""

    @pytest.fixture
    def processador_mock(self):
        """Create processador with basic mocks."""
        mock_gemini = MagicMock()
        mock_holerite_service = MagicMock()
        mock_holerite_service.disponivel = True
        mock_funcionario_service = MagicMock()
        mock_funcionario_service.disponivel = True

        return HoleriteProcessador(
            gemini_service=mock_gemini,
            holerite_service=mock_holerite_service,
            funcionario_service=mock_funcionario_service,
            contato_service=MagicMock(),
            empresa_service=MagicMock(),
        )

    def test_processar_diretorio_nao_existe(self, processador_mock, tmp_path):
        """Test processar_diretorio returns empty list for non-existent directory."""
        diretorio_inexistente = tmp_path / "nao_existe"

        resultados = processador_mock.processar_diretorio(diretorio_inexistente)

        assert resultados == []

    def test_processar_diretorio_sem_pdfs(self, processador_mock, tmp_path):
        """Test processar_diretorio returns empty list when no PDFs found."""
        diretorio_vazio = tmp_path / "vazio"
        diretorio_vazio.mkdir()

        resultados = processador_mock.processar_diretorio(diretorio_vazio)

        assert resultados == []

    def test_processar_diretorio_processa_todos_pdfs(
        self, processador_mock, tmp_path, mocker
    ):
        """Test processar_diretorio processes all PDFs in directory."""
        # Create test PDFs
        pdf1 = tmp_path / "Recibo de Pagamento - Funcionario A.pdf"
        pdf2 = tmp_path / "Recibo de Pagamento - Funcionario B.pdf"
        pdf1.write_bytes(b"%PDF-1.4\n%%EOF")
        pdf2.write_bytes(b"%PDF-1.4\n%%EOF")

        # Mock processar_arquivo
        mock_resultado = ResultadoProcessamentoHolerite(arquivo="test.pdf", sucesso=True)
        processador_mock.processar_arquivo = MagicMock(return_value=mock_resultado)

        resultados = processador_mock.processar_diretorio(tmp_path, recursivo=False)

        assert len(resultados) == 2
        assert processador_mock.processar_arquivo.call_count == 2

    def test_processar_diretorio_recursivo(self, processador_mock, tmp_path, mocker):
        """Test processar_diretorio with recursivo=True."""
        # Create nested structure
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        pdf1 = tmp_path / "Recibo de Pagamento - Funcionario A.pdf"
        pdf2 = subdir / "Recibo de Pagamento - Funcionario B.pdf"
        pdf1.write_bytes(b"%PDF-1.4\n%%EOF")
        pdf2.write_bytes(b"%PDF-1.4\n%%EOF")

        mock_resultado = ResultadoProcessamentoHolerite(arquivo="test.pdf", sucesso=True)
        processador_mock.processar_arquivo = MagicMock(return_value=mock_resultado)

        resultados = processador_mock.processar_diretorio(tmp_path, recursivo=True)

        assert len(resultados) == 2

    def test_processar_diretorio_nao_recursivo(self, processador_mock, tmp_path):
        """Test processar_diretorio with recursivo=False."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        pdf1 = tmp_path / "Recibo de Pagamento - Funcionario A.pdf"
        pdf2 = subdir / "Recibo de Pagamento - Funcionario B.pdf"
        pdf1.write_bytes(b"%PDF-1.4\n%%EOF")
        pdf2.write_bytes(b"%PDF-1.4\n%%EOF")

        mock_resultado = ResultadoProcessamentoHolerite(arquivo="test.pdf", sucesso=True)
        processador_mock.processar_arquivo = MagicMock(return_value=mock_resultado)

        resultados = processador_mock.processar_diretorio(tmp_path, recursivo=False)

        # Should only find pdf1
        assert len(resultados) == 1

    def test_processar_diretorio_aplica_empresa_id_todos(
        self, processador_mock, tmp_path
    ):
        """Test that empresa_id is applied to all files."""
        pdf1 = tmp_path / "Recibo de Pagamento - Funcionario A.pdf"
        pdf1.write_bytes(b"%PDF-1.4\n%%EOF")

        empresa_id = str(ObjectId())
        mock_resultado = ResultadoProcessamentoHolerite(arquivo="test.pdf", sucesso=True)
        processador_mock.processar_arquivo = MagicMock(return_value=mock_resultado)

        processador_mock.processar_diretorio(tmp_path, empresa_id=empresa_id)

        # Check that empresa_id was passed
        call_args = processador_mock.processar_arquivo.call_args
        assert call_args[1]['empresa_id'] == empresa_id

    def test_processar_diretorio_aceita_path_como_string(
        self, processador_mock, tmp_path
    ):
        """Test processar_diretorio accepts path as string."""
        pdf1 = tmp_path / "Recibo de Pagamento - Funcionario A.pdf"
        pdf1.write_bytes(b"%PDF-1.4\n%%EOF")

        mock_resultado = ResultadoProcessamentoHolerite(arquivo="test.pdf", sucesso=True)
        processador_mock.processar_arquivo = MagicMock(return_value=mock_resultado)

        resultados = processador_mock.processar_diretorio(str(tmp_path))

        assert len(resultados) == 1


# ==================== Test Class: TestObterEstatisticas ====================

class TestObterEstatisticas:
    """Test obter_estatisticas method."""

    @pytest.fixture
    def processador(self):
        """Create processador."""
        return HoleriteProcessador(
            gemini_service=MagicMock(),
            holerite_service=MagicMock(),
            funcionario_service=MagicMock(),
            contato_service=MagicMock(),
            empresa_service=MagicMock(),
        )

    def test_obter_estatisticas_inicial(self, processador):
        """Test statistics are zero initially."""
        stats = processador.obter_estatisticas()

        assert stats['total_processados'] == 0
        assert stats['total_sucesso'] == 0
        assert stats['total_falhas'] == 0
        assert stats['taxa_sucesso'] == 0

    def test_obter_estatisticas_apos_processamento(self, processador):
        """Test statistics after processing."""
        processador.total_processados = 10
        processador.total_sucesso = 8
        processador.total_falhas = 2

        stats = processador.obter_estatisticas()

        assert stats['total_processados'] == 10
        assert stats['total_sucesso'] == 8
        assert stats['total_falhas'] == 2
        assert stats['taxa_sucesso'] == 80.0

    def test_obter_estatisticas_taxa_sucesso_calculo(self, processador):
        """Test taxa_sucesso calculation."""
        processador.total_processados = 4
        processador.total_sucesso = 3

        stats = processador.obter_estatisticas()

        assert stats['taxa_sucesso'] == 75.0


# ==================== Test Class: TestResultadoProcessamentoHolerite ====================

class TestResultadoProcessamentoHolerite:
    """Test ResultadoProcessamentoHolerite dataclass."""

    def test_criar_resultado_inicial(self):
        """Test creating initial resultado."""
        resultado = ResultadoProcessamentoHolerite(arquivo="/test/file.pdf")

        assert resultado.arquivo == "/test/file.pdf"
        assert resultado.sucesso is False
        assert resultado.erro is None
        assert resultado.extracao is None
        assert resultado.holerite_id is None
        assert resultado.funcionario_id is None
        assert resultado.empresa_id is None
        assert resultado.funcionario_criado is False
        assert resultado.tempo_extracao_s == 0.0
        assert resultado.tempo_total_s == 0.0
        assert len(resultado.mensagens) == 0

    def test_resultado_pode_armazenar_extracao(self):
        """Test that resultado can store extracao."""
        resultado = ResultadoProcessamentoHolerite()

        extracao = HoleriteExtracaoSchema(
            empresa_razao_social="Empresa Teste",
            empresa_cnpj="12.345.678/0001-90",
            funcionario_nome="João Silva",
            tipo_folha="Folha Mensal",
            mes_referencia_texto="Janeiro 2025",
            mes_referencia=1,
            ano_referencia=2025,
            total_vencimentos=5000.0,
            total_descontos=400.0,
            valor_liquido=4600.0
        )
        resultado.extracao = extracao

        assert resultado.extracao.funcionario_nome == "João Silva"

    def test_resultado_adiciona_mensagens(self):
        """Test adding mensagens to resultado."""
        resultado = ResultadoProcessamentoHolerite()
        resultado.mensagens.append("Mensagem 1")
        resultado.mensagens.append("Mensagem 2")

        assert len(resultado.mensagens) == 2

    def test_resultado_armazena_tempo_metricas(self):
        """Test storing time metrics."""
        resultado = ResultadoProcessamentoHolerite()
        resultado.tempo_extracao_s = 2.5
        resultado.tempo_total_s = 5.0

        assert resultado.tempo_extracao_s == 2.5
        assert resultado.tempo_total_s == 5.0
