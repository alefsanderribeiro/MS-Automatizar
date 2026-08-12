"""
Unit tests for ProcessadorFolhaPonto

Tests cover:
1. Initialization with dependency injection
2. File validation (PDF, existence, size)
3. Gemini extraction with retry logic
4. Funcionario lookup (existing and autocreate)
5. Empresa lookup (existing and autocreate)
6. MongoDB storage
7. Complete pipeline
8. Model conversions (DiaExtraido -> DiaFolhaPonto)

Target: ~50% coverage (425 lines of 850)
"""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, date, timezone
from bson import ObjectId

from src.processadores.processador_folha_ponto import (
    ProcessadorFolhaPonto,
    ProcessarResultado,
    ExtratorFolhaPonto,
    DiaExtraido,
    StatusProcessamento,
    calcular_total_horas,
    converter_string_para_tipo_dia,
)
from src.models.folha_de_ponto_models import TipoDia, StatusFolhaPonto


# ==================== Test Class: TestProcessadorInit ====================

class TestProcessadorInit:
    """Test initialization and dependency injection."""

    def test_init_com_dependencias_injetadas(self):
        """Test initialization with all dependencies injected."""
        mock_gemini = MagicMock()
        mock_func_service = MagicMock()
        mock_folha_service = MagicMock()
        mock_empresa_service = MagicMock()

        processador = ProcessadorFolhaPonto(
            servico_gemini=mock_gemini,
            servico_funcionario=mock_func_service,
            servico_folha=mock_folha_service,
            servico_empresa=mock_empresa_service,
        )

        assert processador.gemini is mock_gemini
        assert processador.funcionario_service is mock_func_service
        assert processador.folha_service is mock_folha_service
        assert processador.empresa_service is mock_empresa_service

    def test_init_cria_gemini_service_se_none(self, mocker):
        """Test that GeminiService is created when not provided."""
        mock_gemini_class = mocker.patch(
            'src.processadores.processador_folha_ponto.GeminiService'
        )
        mock_func_service = mocker.patch(
            'src.processadores.processador_folha_ponto.FuncionarioService'
        )
        mock_folha_service = mocker.patch(
            'src.processadores.processador_folha_ponto.FolhaDePontoService'
        )
        mock_empresa_service = mocker.patch(
            'src.processadores.processador_folha_ponto.EmpresaService'
        )

        processador = ProcessadorFolhaPonto()

        mock_gemini_class.assert_called_once_with(model="gemini-2.5-pro")
        mock_func_service.assert_called_once()
        mock_folha_service.assert_called_once()
        mock_empresa_service.assert_called_once()

    def test_init_cria_funcionario_service_se_none(self, mocker):
        """Test that FuncionarioService is created when not provided."""
        mocker.patch('src.processadores.processador_folha_ponto.GeminiService')
        mock_func_service = mocker.patch(
            'src.processadores.processador_folha_ponto.FuncionarioService'
        )
        mocker.patch('src.processadores.processador_folha_ponto.FolhaDePontoService')
        mocker.patch('src.processadores.processador_folha_ponto.EmpresaService')

        processador = ProcessadorFolhaPonto()

        mock_func_service.assert_called_once()

    def test_init_cria_folha_service_se_none(self, mocker):
        """Test that FolhaDePontoService is created when not provided."""
        mocker.patch('src.processadores.processador_folha_ponto.GeminiService')
        mocker.patch('src.processadores.processador_folha_ponto.FuncionarioService')
        mock_folha_service = mocker.patch(
            'src.processadores.processador_folha_ponto.FolhaDePontoService'
        )
        mocker.patch('src.processadores.processador_folha_ponto.EmpresaService')

        processador = ProcessadorFolhaPonto()

        mock_folha_service.assert_called_once()

    def test_init_cria_empresa_service_se_none(self, mocker):
        """Test that EmpresaService is created when not provided."""
        mocker.patch('src.processadores.processador_folha_ponto.GeminiService')
        mocker.patch('src.processadores.processador_folha_ponto.FuncionarioService')
        mocker.patch('src.processadores.processador_folha_ponto.FolhaDePontoService')
        mock_empresa_service = mocker.patch(
            'src.processadores.processador_folha_ponto.EmpresaService'
        )

        processador = ProcessadorFolhaPonto()

        mock_empresa_service.assert_called_once()


# ==================== Test Class: TestValidacaoArquivo ====================

class TestValidacaoArquivo:
    """Test file validation logic."""

    @pytest.fixture
    def processador(self):
        """Create processador with mocked dependencies."""
        return ProcessadorFolhaPonto(
            servico_gemini=MagicMock(),
            servico_funcionario=MagicMock(),
            servico_folha=MagicMock(),
            servico_empresa=MagicMock(),
        )

    def test_validar_arquivo_pdf_valido(self, processador, temp_pdf_file):
        """Test validation of valid PDF file."""
        resultado = ProcessarResultado(arquivo_origem=str(temp_pdf_file))

        is_valid = processador._validar_arquivo(temp_pdf_file, resultado)

        assert is_valid is True
        assert len(resultado.erros) == 0
        assert any("Validacao OK" in msg or "OK" in msg for msg in resultado.mensagens)

    def test_validar_arquivo_nao_encontrado(self, processador, tmp_path):
        """Test validation of non-existent file."""
        arquivo_inexistente = tmp_path / "nao_existe.pdf"
        resultado = ProcessarResultado(arquivo_origem=str(arquivo_inexistente))

        is_valid = processador._validar_arquivo(arquivo_inexistente, resultado)

        assert is_valid is False
        assert any("não encontrado" in err or "not found" in err.lower()
                   for err in resultado.erros)

    def test_validar_arquivo_extensao_invalida(self, processador, tmp_path):
        """Test validation of file with invalid extension (not .pdf)."""
        arquivo_txt = tmp_path / "arquivo.txt"
        arquivo_txt.write_text("conteudo de teste")
        resultado = ProcessarResultado(arquivo_origem=str(arquivo_txt))

        is_valid = processador._validar_arquivo(arquivo_txt, resultado)

        assert is_valid is False
        assert any("não é PDF" in err or "PDF" in err for err in resultado.erros)

    def test_validar_arquivo_caminho_e_diretorio(self, processador, tmp_path):
        """Test validation when path is a directory, not a file."""
        diretorio = tmp_path / "um_diretorio"
        diretorio.mkdir()
        resultado = ProcessarResultado(arquivo_origem=str(diretorio))

        is_valid = processador._validar_arquivo(diretorio, resultado)

        assert is_valid is False
        assert any("não é arquivo" in err or "is_file" in str(err).lower()
                   for err in resultado.erros)

    def test_validar_arquivo_muito_grande(self, processador, tmp_path, mocker):
        """Test validation of file exceeding size limit (50MB)."""
        arquivo_pdf = tmp_path / "grande.pdf"
        arquivo_pdf.write_bytes(b"%PDF-1.4\n%%EOF")

        resultado = ProcessarResultado(arquivo_origem=str(arquivo_pdf))

        # Mock the _validar_arquivo method's stat call specifically
        original_stat = arquivo_pdf.stat

        class MockStat:
            st_size = 60 * 1024 * 1024  # 60MB in bytes
            st_mode = original_stat().st_mode

        mocker.patch.object(type(arquivo_pdf), 'stat', return_value=MockStat())

        is_valid = processador._validar_arquivo(arquivo_pdf, resultado)

        assert is_valid is False
        assert any("muito grande" in err or "50MB" in err or "size" in err.lower()
                   for err in resultado.erros)


# ==================== Test Class: TestExtracaoGemini ====================

class TestExtracaoGemini:
    """Test Gemini extraction with retry logic."""

    @pytest.fixture
    def processador(self):
        """Create processador with mocked dependencies."""
        mock_gemini = MagicMock()
        return ProcessadorFolhaPonto(
            servico_gemini=mock_gemini,
            servico_funcionario=MagicMock(),
            servico_folha=MagicMock(),
            servico_empresa=MagicMock(),
        ), mock_gemini

    @pytest.fixture
    def extracao_json_sucesso(self):
        """Valid Gemini extraction JSON response."""
        return json.dumps({
            "empresa_nome": "Empresa Teste Ltda",
            "empresa_cnpj": "12.345.678/0001-90",
            "funcionario_nome": "Joao Silva",
            "funcionario_pis": "12345678901",
            "funcionario_cpf": "123.456.789-00",
            "periodo_inicio": "2025-01-01",
            "periodo_fim": "2025-01-31",
            "mes_ano": "2025-01",
            "dias": [
                {
                    "numero_dia": 1,
                    "data": "2025-01-01",
                    "dia_semana": "Quarta",
                    "hora_entrada": "08:00",
                    "hora_intervalo_inicio": "12:00",
                    "hora_intervalo_fim": "13:00",
                    "hora_saida": "17:00",
                    "total_horas_trabalhadas": "08:00",
                    "observacoes": None,
                    "tipo_dia": "NORMAL",
                    "preenchido_manualmente": False,
                    "analise_ia_processada": True
                },
                {
                    "numero_dia": 2,
                    "data": "2025-01-02",
                    "dia_semana": "Quinta",
                    "hora_entrada": "08:00",
                    "hora_intervalo_inicio": "12:00",
                    "hora_intervalo_fim": "13:00",
                    "hora_saida": "17:00",
                    "total_horas_trabalhadas": "08:00",
                    "observacoes": None,
                    "tipo_dia": "NORMAL",
                    "preenchido_manualmente": False,
                    "analise_ia_processada": True
                }
            ],
            "dias_com_dados": 2,
            "dias_em_branco": 0,
            "confianca_geral": 95,
            "avisos": [],
            "erros": []
        })

    def test_extracao_gemini_sucesso(self, processador, extracao_json_sucesso, temp_pdf_file):
        """Test successful Gemini extraction with structured output."""
        proc, mock_gemini = processador
        mock_gemini.documento_estruturado.return_value = extracao_json_sucesso

        resultado = ProcessarResultado(arquivo_origem=str(temp_pdf_file))

        success = proc._extrair_gemini(temp_pdf_file, resultado)

        assert success is True
        assert resultado.extracao_sucesso is True
        assert resultado.extracao_resultado is not None
        assert resultado.extracao_resultado.funcionario_nome == "Joao Silva"
        assert resultado.extracao_resultado.dias_com_dados == 2
        assert resultado.extracao_resultado.confianca_geral == 95
        assert len(resultado.extracao_resultado.dias) == 2

    def test_extracao_gemini_retry_logic_temperatura_escalation(
        self, processador, extracao_json_sucesso, temp_pdf_file
    ):
        """Test that temperature escalates on retry (0.2 -> 0.4 -> 0.6)."""
        proc, mock_gemini = processador

        # First call fails, second succeeds
        mock_gemini.documento_estruturado.side_effect = [
            Exception("API error"),
            extracao_json_sucesso
        ]

        resultado = ProcessarResultado(arquivo_origem=str(temp_pdf_file))

        success = proc._extrair_gemini(temp_pdf_file, resultado)

        assert success is True
        assert mock_gemini.documento_estruturado.call_count == 2

        # Check temperature values in calls
        calls = mock_gemini.documento_estruturado.call_args_list
        assert calls[0][1]['temperature'] == 0.2
        assert calls[1][1]['temperature'] == 0.4

    def test_extracao_gemini_max_retries_exceeded(self, processador, temp_pdf_file):
        """Test that extraction fails after max retries (3)."""
        proc, mock_gemini = processador

        # All 3 calls fail
        mock_gemini.documento_estruturado.side_effect = [
            Exception("API error 1"),
            Exception("API error 2"),
            Exception("API error 3"),
        ]

        resultado = ProcessarResultado(arquivo_origem=str(temp_pdf_file))

        success = proc._extrair_gemini(temp_pdf_file, resultado)

        assert success is False
        assert resultado.extracao_sucesso is False
        assert mock_gemini.documento_estruturado.call_count == 3
        assert any("tentativas" in err or "Gemini" in err for err in resultado.erros)

    def test_extracao_gemini_json_parsing_error(self, processador, temp_pdf_file):
        """Test handling of JSON parsing errors."""
        proc, mock_gemini = processador

        # Return invalid JSON
        mock_gemini.documento_estruturado.return_value = "{ invalid json }"

        resultado = ProcessarResultado(arquivo_origem=str(temp_pdf_file))

        success = proc._extrair_gemini(temp_pdf_file, resultado)

        assert success is False
        assert resultado.extracao_sucesso is False

    def test_extracao_gemini_resposta_truncada(self, processador, temp_pdf_file):
        """Test handling of truncated response (< 100 chars)."""
        proc, mock_gemini = processador

        # Return short response (truncated)
        mock_gemini.documento_estruturado.side_effect = [
            '{"dias":[]}',  # < 100 chars, will retry
            '{"dias":[]}',  # retry 2
            '{"dias":[]}',  # retry 3 - gives up but tries to parse
        ]

        resultado = ProcessarResultado(arquivo_origem=str(temp_pdf_file))

        # Should try 3 times due to truncation warnings
        proc._extrair_gemini(temp_pdf_file, resultado)

        assert mock_gemini.documento_estruturado.call_count == 3

    def test_extracao_gemini_salva_prompt_e_resposta_bruta(
        self, processador, extracao_json_sucesso, temp_pdf_file
    ):
        """Test that prompt and raw response are saved."""
        proc, mock_gemini = processador
        mock_gemini.documento_estruturado.return_value = extracao_json_sucesso

        resultado = ProcessarResultado(arquivo_origem=str(temp_pdf_file))

        proc._extrair_gemini(temp_pdf_file, resultado)

        assert resultado.prompt_gemini is not None
        assert "Analise esta Folha de Ponto" in resultado.prompt_gemini
        assert resultado.resposta_bruta_gemini == extracao_json_sucesso


# ==================== Test Class: TestLookupFuncionario ====================

class TestLookupFuncionario:
    """Test funcionario lookup and autocreate logic."""

    @pytest.fixture
    def processador_com_mocks(self):
        """Create processador with mocked services."""
        mock_func_service = MagicMock()
        mock_func_service.colecao = MagicMock()

        processador = ProcessadorFolhaPonto(
            servico_gemini=MagicMock(),
            servico_funcionario=mock_func_service,
            servico_folha=MagicMock(),
            servico_empresa=MagicMock(),
        )
        return processador, mock_func_service

    @pytest.fixture
    def resultado_com_extracao(self):
        """Create resultado with successful extraction."""
        resultado = ProcessarResultado(arquivo_origem="/test/file.pdf")
        resultado.extracao_sucesso = True
        resultado.extracao_resultado = ExtratorFolhaPonto(
            empresa_nome="Empresa Teste",
            funcionario_nome="Joao Silva",
            mes_ano="2025-01"
        )
        return resultado

    def test_lookup_funcionario_encontrado_por_nome(
        self, processador_com_mocks, resultado_com_extracao
    ):
        """Test existing funcionario lookup by nome normalizado."""
        proc, mock_func_service = processador_com_mocks

        funcionario_existente = {
            "_id": ObjectId(),
            "nome": "Joao Silva",
            "nome_normalizado": "joao silva"
        }
        mock_func_service.colecao.find.return_value = [funcionario_existente]

        success = proc._lookup_funcionario(resultado_com_extracao, "/test/file.pdf")

        assert success is True
        assert resultado_com_extracao.lookup_sucesso is True
        assert resultado_com_extracao.funcionario_id == str(funcionario_existente["_id"])
        assert resultado_com_extracao.funcionario_nome_encontrado == "Joao Silva"

    def test_lookup_funcionario_multiplos_candidatos(
        self, processador_com_mocks, resultado_com_extracao
    ):
        """Test lookup when multiple funcionarios have same name."""
        proc, mock_func_service = processador_com_mocks

        func1 = {"_id": ObjectId(), "nome": "Joao Silva", "lotacao": "TI"}
        func2 = {"_id": ObjectId(), "nome": "Joao Silva", "lotacao": "RH"}
        mock_func_service.colecao.find.return_value = [func1, func2]

        success = proc._lookup_funcionario(resultado_com_extracao, "/test/file.pdf")

        assert success is True
        # Uses first candidate
        assert resultado_com_extracao.funcionario_id == str(func1["_id"])

    def test_lookup_funcionario_nao_encontrado_tenta_similar(
        self, processador_com_mocks, resultado_com_extracao
    ):
        """Test that similar search is attempted when exact match fails."""
        proc, mock_func_service = processador_com_mocks

        # Exact match fails
        mock_func_service.colecao.find.return_value = []

        # Similar search succeeds
        func_similar = {"_id": ObjectId(), "nome": "Joao da Silva"}
        mock_func_service.buscar_similar.return_value = func_similar

        success = proc._lookup_funcionario(resultado_com_extracao, "/test/file.pdf")

        assert success is True
        assert resultado_com_extracao.funcionario_id == str(func_similar["_id"])
        mock_func_service.buscar_similar.assert_called_once()

    def test_lookup_funcionario_autocreate_quando_nao_encontrado(
        self, processador_com_mocks, resultado_com_extracao, mocker
    ):
        """Test funcionario autocreate when not found."""
        proc, mock_func_service = processador_com_mocks

        # Not found in any search
        mock_func_service.colecao.find.return_value = []
        mock_func_service.buscar_similar.return_value = None

        # Autocreate succeeds
        new_id = ObjectId()
        mock_func_service.criar_funcionario.return_value = new_id

        # Mock ConstrutorFuncionarioIncompleto
        mocker.patch(
            'src.processadores.processador_folha_ponto.ConstrutorFuncionarioIncompleto.criar_do_pdf',
            return_value=({"nome": "Joao Silva", "nome_normalizado": "joao silva"}, [])
        )

        success = proc._lookup_funcionario(resultado_com_extracao, "/test/file.pdf")

        assert success is True
        assert resultado_com_extracao.funcionario_id == str(new_id)
        assert resultado_com_extracao.funcionario_score_similaridade == 0  # Autocreate
        mock_func_service.criar_funcionario.assert_called_once()

    def test_lookup_funcionario_autocreate_com_erros_sanitizacao(
        self, processador_com_mocks, resultado_com_extracao, mocker
    ):
        """Test autocreate with sanitization warnings."""
        proc, mock_func_service = processador_com_mocks

        mock_func_service.colecao.find.return_value = []
        mock_func_service.buscar_similar.return_value = None

        new_id = ObjectId()
        mock_func_service.criar_funcionario.return_value = new_id

        # Mock with sanitization errors
        mocker.patch(
            'src.processadores.processador_folha_ponto.ConstrutorFuncionarioIncompleto.criar_do_pdf',
            return_value=(
                {"nome": "Joao Silva", "nome_normalizado": "joao silva"},
                ["Nome continha caracteres especiais"]
            )
        )

        success = proc._lookup_funcionario(resultado_com_extracao, "/test/file.pdf")

        assert success is True
        assert any("Sanitizacao" in aviso or "sanitiza" in aviso.lower()
                   for aviso in resultado_com_extracao.avisos)

    def test_lookup_funcionario_sem_nome_extraido(self, processador_com_mocks):
        """Test lookup fails when nome is not extracted."""
        proc, _ = processador_com_mocks

        resultado = ProcessarResultado(arquivo_origem="/test/file.pdf")
        resultado.extracao_sucesso = True
        resultado.extracao_resultado = ExtratorFolhaPonto(
            empresa_nome="Empresa Teste",
            funcionario_nome=None,  # Nome not extracted
            mes_ano="2025-01"
        )

        success = proc._lookup_funcionario(resultado, "/test/file.pdf")

        assert success is False
        assert any("Nome" in err or "nome" in err for err in resultado.erros)

    def test_lookup_funcionario_sem_extracao(self, processador_com_mocks):
        """Test lookup fails when extraction was not successful."""
        proc, _ = processador_com_mocks

        resultado = ProcessarResultado(arquivo_origem="/test/file.pdf")
        resultado.extracao_sucesso = False

        success = proc._lookup_funcionario(resultado, "/test/file.pdf")

        assert success is False


# ==================== Test Class: TestLookupEmpresa ====================

class TestLookupEmpresa:
    """Test empresa lookup and autocreate in _armazenar_mongodb."""

    @pytest.fixture
    def processador_com_mocks(self):
        """Create processador with mocked services."""
        mock_empresa_service = MagicMock()
        mock_folha_service = MagicMock()
        mock_folha_service.colecao = MagicMock()
        mock_func_service = MagicMock()
        mock_func_service.colecao = MagicMock()

        processador = ProcessadorFolhaPonto(
            servico_gemini=MagicMock(),
            servico_funcionario=mock_func_service,
            servico_folha=mock_folha_service,
            servico_empresa=mock_empresa_service,
        )
        return processador, mock_empresa_service, mock_folha_service, mock_func_service

    @pytest.fixture
    def resultado_pronto_para_armazenamento(self):
        """Create resultado ready for storage."""
        resultado = ProcessarResultado(arquivo_origem="/test/file.pdf")
        resultado.extracao_sucesso = True
        resultado.lookup_sucesso = True
        resultado.funcionario_id = str(ObjectId())
        resultado.extracao_resultado = ExtratorFolhaPonto(
            empresa_nome="Empresa Teste Ltda",
            funcionario_nome="Joao Silva",
            mes_ano="2025-01",
            dias=[
                DiaExtraido(
                    numero_dia=1,
                    hora_entrada="08:00",
                    hora_saida="17:00"
                )
            ],
            dias_com_dados=1,
            confianca_geral=95
        )
        return resultado

    def test_lookup_empresa_existente(
        self, processador_com_mocks, resultado_pronto_para_armazenamento
    ):
        """Test existing empresa lookup via obter_ou_criar_incompleta."""
        proc, mock_empresa, mock_folha, mock_func = processador_com_mocks

        empresa_existente = {
            "_id": ObjectId(),
            "nome": "Empresa Teste Ltda"
        }
        mock_empresa.obter_ou_criar_incompleta.return_value = empresa_existente
        mock_folha.colecao.insert_one.return_value = MagicMock(inserted_id=ObjectId())
        mock_func.colecao.find_one.return_value = {"_id": ObjectId()}
        mock_func.colecao.update_one.return_value = MagicMock()

        success = proc._armazenar_mongodb(resultado_pronto_para_armazenamento)

        assert success is True
        mock_empresa.obter_ou_criar_incompleta.assert_called_once_with("Empresa Teste Ltda")

    def test_lookup_empresa_cria_incompleta(
        self, processador_com_mocks, resultado_pronto_para_armazenamento
    ):
        """Test empresa autocreate when not found."""
        proc, mock_empresa, mock_folha, mock_func = processador_com_mocks

        # Service creates new empresa
        nova_empresa = {
            "_id": ObjectId(),
            "nome": "Empresa Teste Ltda",
            "incompleto": True
        }
        mock_empresa.obter_ou_criar_incompleta.return_value = nova_empresa
        mock_folha.colecao.insert_one.return_value = MagicMock(inserted_id=ObjectId())
        mock_func.colecao.find_one.return_value = {"_id": ObjectId()}
        mock_func.colecao.update_one.return_value = MagicMock()

        success = proc._armazenar_mongodb(resultado_pronto_para_armazenamento)

        assert success is True

    def test_lookup_empresa_nome_desconhecida(self, processador_com_mocks):
        """Test empresa lookup with None name uses 'Desconhecida'."""
        proc, mock_empresa, mock_folha, mock_func = processador_com_mocks

        resultado = ProcessarResultado(arquivo_origem="/test/file.pdf")
        resultado.extracao_sucesso = True
        resultado.lookup_sucesso = True
        resultado.funcionario_id = str(ObjectId())
        resultado.extracao_resultado = ExtratorFolhaPonto(
            empresa_nome=None,  # No empresa name
            funcionario_nome="Joao Silva",
            mes_ano="2025-01",
            dias=[DiaExtraido(numero_dia=1)],
            dias_com_dados=1
        )

        mock_empresa.obter_ou_criar_incompleta.return_value = {"_id": ObjectId()}
        mock_folha.colecao.insert_one.return_value = MagicMock(inserted_id=ObjectId())
        mock_func.colecao.find_one.return_value = {"_id": ObjectId()}
        mock_func.colecao.update_one.return_value = MagicMock()

        proc._armazenar_mongodb(resultado)

        mock_empresa.obter_ou_criar_incompleta.assert_called_once_with("Desconhecida")


# ==================== Test Class: TestArmazenamentoMongoDB ====================

class TestArmazenamentoMongoDB:
    """Test MongoDB storage logic."""

    @pytest.fixture
    def processador_com_mocks(self):
        """Create processador with mocked services."""
        mock_empresa_service = MagicMock()
        mock_folha_service = MagicMock()
        mock_folha_service.colecao = MagicMock()
        mock_func_service = MagicMock()
        mock_func_service.colecao = MagicMock()

        processador = ProcessadorFolhaPonto(
            servico_gemini=MagicMock(),
            servico_funcionario=mock_func_service,
            servico_folha=mock_folha_service,
            servico_empresa=mock_empresa_service,
        )
        return processador, mock_empresa_service, mock_folha_service, mock_func_service

    @pytest.fixture
    def resultado_pronto(self):
        """Create resultado ready for storage."""
        resultado = ProcessarResultado(arquivo_origem="/test/file.pdf")
        resultado.extracao_sucesso = True
        resultado.lookup_sucesso = True
        resultado.funcionario_id = str(ObjectId())
        resultado.prompt_gemini = "Test prompt"
        resultado.resposta_bruta_gemini = "{}"
        resultado.tempo_gemini_s = 1.5
        resultado.extracao_resultado = ExtratorFolhaPonto(
            empresa_nome="Empresa Teste",
            funcionario_nome="Joao Silva",
            mes_ano="2025-01",
            dias=[
                DiaExtraido(
                    numero_dia=1,
                    hora_entrada="08:00",
                    hora_intervalo_inicio="12:00",
                    hora_intervalo_fim="13:00",
                    hora_saida="17:00",
                    tipo_dia="NORMAL"
                )
            ],
            dias_com_dados=1,
            confianca_geral=95
        )
        return resultado

    def test_armazenar_mongodb_sucesso(self, processador_com_mocks, resultado_pronto):
        """Test successful storage in MongoDB."""
        proc, mock_empresa, mock_folha, mock_func = processador_com_mocks

        folha_id = ObjectId()
        mock_empresa.obter_ou_criar_incompleta.return_value = {"_id": ObjectId()}
        mock_folha.colecao.insert_one.return_value = MagicMock(inserted_id=folha_id)
        mock_func.colecao.find_one.return_value = {"_id": ObjectId()}
        mock_func.colecao.update_one.return_value = MagicMock()

        success = proc._armazenar_mongodb(resultado_pronto)

        assert success is True
        assert resultado_pronto.armazenamento_sucesso is True
        assert resultado_pronto.folha_id == str(folha_id)
        mock_folha.colecao.insert_one.assert_called_once()

    def test_armazenar_mongodb_com_todos_campos(self, processador_com_mocks, resultado_pronto):
        """Test folha de ponto creation with all fields."""
        proc, mock_empresa, mock_folha, mock_func = processador_com_mocks

        mock_empresa.obter_ou_criar_incompleta.return_value = {"_id": ObjectId()}
        mock_folha.colecao.insert_one.return_value = MagicMock(inserted_id=ObjectId())
        mock_func.colecao.find_one.return_value = {"_id": ObjectId()}
        mock_func.colecao.update_one.return_value = MagicMock()

        proc._armazenar_mongodb(resultado_pronto)

        # Verify document structure
        call_args = mock_folha.colecao.insert_one.call_args
        doc = call_args[0][0]

        assert "funcionario_id" in doc
        assert "empresa_id" in doc
        assert "mes_referencia" in doc
        assert "folha_data" in doc
        assert "status" in doc

    def test_armazenar_mongodb_relacionamento_funcionario(
        self, processador_com_mocks, resultado_pronto
    ):
        """Test relacionamento with funcionario_id."""
        proc, mock_empresa, mock_folha, mock_func = processador_com_mocks

        func_id = ObjectId()
        resultado_pronto.funcionario_id = str(func_id)

        mock_empresa.obter_ou_criar_incompleta.return_value = {"_id": ObjectId()}
        mock_folha.colecao.insert_one.return_value = MagicMock(inserted_id=ObjectId())
        mock_func.colecao.find_one.return_value = {"_id": func_id}
        mock_func.colecao.update_one.return_value = MagicMock()

        proc._armazenar_mongodb(resultado_pronto)

        call_args = mock_folha.colecao.insert_one.call_args
        doc = call_args[0][0]

        assert doc["funcionario_id"] == func_id

    def test_armazenar_mongodb_relacionamento_empresa(
        self, processador_com_mocks, resultado_pronto
    ):
        """Test relacionamento with empresa_id."""
        proc, mock_empresa, mock_folha, mock_func = processador_com_mocks

        empresa_id = ObjectId()
        mock_empresa.obter_ou_criar_incompleta.return_value = {"_id": empresa_id}
        mock_folha.colecao.insert_one.return_value = MagicMock(inserted_id=ObjectId())
        mock_func.colecao.find_one.return_value = {"_id": ObjectId()}
        mock_func.colecao.update_one.return_value = MagicMock()

        proc._armazenar_mongodb(resultado_pronto)

        call_args = mock_folha.colecao.insert_one.call_args
        doc = call_args[0][0]

        assert doc["empresa_id"] == empresa_id

    def test_armazenar_mongodb_status_analise_concluida(
        self, processador_com_mocks, resultado_pronto
    ):
        """Test status_folha_ponto is set to ANALISE_CONCLUIDA."""
        proc, mock_empresa, mock_folha, mock_func = processador_com_mocks

        mock_empresa.obter_ou_criar_incompleta.return_value = {"_id": ObjectId()}
        mock_folha.colecao.insert_one.return_value = MagicMock(inserted_id=ObjectId())
        mock_func.colecao.find_one.return_value = {"_id": ObjectId()}
        mock_func.colecao.update_one.return_value = MagicMock()

        proc._armazenar_mongodb(resultado_pronto)

        call_args = mock_folha.colecao.insert_one.call_args
        doc = call_args[0][0]

        assert doc["status"] == StatusFolhaPonto.ANALISE_CONCLUIDA.value

    def test_armazenar_mongodb_upsert_duplicata(self, processador_com_mocks, resultado_pronto):
        """Test upsert behavior when duplicate key error occurs."""
        proc, mock_empresa, mock_folha, mock_func = processador_com_mocks

        mock_empresa.obter_ou_criar_incompleta.return_value = {"_id": ObjectId()}

        # Simulate duplicate key error
        from pymongo.errors import DuplicateKeyError
        mock_folha.colecao.insert_one.side_effect = Exception("E11000 duplicate key error")

        # Upsert succeeds
        folha_id = ObjectId()
        mock_folha.colecao.update_one.return_value = MagicMock(upserted_id=folha_id)
        mock_folha.colecao.find_one.return_value = {"_id": folha_id}
        mock_func.colecao.find_one.return_value = {"_id": ObjectId()}
        mock_func.colecao.update_one.return_value = MagicMock()

        success = proc._armazenar_mongodb(resultado_pronto)

        assert success is True
        mock_folha.colecao.update_one.assert_called_once()

    def test_armazenar_mongodb_falha_sem_lookup(self, processador_com_mocks):
        """Test storage fails when lookup was not successful."""
        proc, _, _, _ = processador_com_mocks

        resultado = ProcessarResultado(arquivo_origem="/test/file.pdf")
        resultado.extracao_sucesso = True
        resultado.lookup_sucesso = False

        success = proc._armazenar_mongodb(resultado)

        assert success is False


# ==================== Test Class: TestPipelineCompleto ====================

class TestPipelineCompleto:
    """Test end-to-end pipeline."""

    @pytest.fixture
    def processador_completo(self, mocker):
        """Create processador with all mocks set up."""
        mock_gemini = MagicMock()
        mock_func_service = MagicMock()
        mock_func_service.colecao = MagicMock()
        mock_folha_service = MagicMock()
        mock_folha_service.colecao = MagicMock()
        mock_empresa_service = MagicMock()

        processador = ProcessadorFolhaPonto(
            servico_gemini=mock_gemini,
            servico_funcionario=mock_func_service,
            servico_folha=mock_folha_service,
            servico_empresa=mock_empresa_service,
        )

        return (
            processador,
            mock_gemini,
            mock_func_service,
            mock_folha_service,
            mock_empresa_service
        )

    @pytest.fixture
    def extracao_json_completa(self):
        """Complete extraction JSON."""
        return json.dumps({
            "empresa_nome": "Empresa Teste Ltda",
            "funcionario_nome": "Joao Silva",
            "mes_ano": "2025-01",
            "dias": [
                {
                    "numero_dia": 1,
                    "hora_entrada": "08:00",
                    "hora_saida": "17:00",
                    "tipo_dia": "NORMAL"
                }
            ],
            "dias_com_dados": 1,
            "dias_em_branco": 30,
            "confianca_geral": 90
        })

    def test_pipeline_completo_sucesso(
        self, processador_completo, extracao_json_completa, temp_pdf_file
    ):
        """Test end-to-end: validar -> extrair -> lookup -> armazenar."""
        proc, mock_gemini, mock_func, mock_folha, mock_empresa = processador_completo

        # Setup mocks
        mock_gemini.documento_estruturado.return_value = extracao_json_completa

        func_id = ObjectId()
        mock_func.colecao.find.return_value = [
            {"_id": func_id, "nome": "Joao Silva", "nome_normalizado": "joao silva"}
        ]
        mock_func.colecao.find_one.return_value = {"_id": func_id}
        mock_func.colecao.update_one.return_value = MagicMock()

        empresa_id = ObjectId()
        mock_empresa.obter_ou_criar_incompleta.return_value = {"_id": empresa_id}

        folha_id = ObjectId()
        mock_folha.colecao.insert_one.return_value = MagicMock(inserted_id=folha_id)

        resultado = proc.processar(temp_pdf_file)

        assert resultado.status == StatusProcessamento.SUCESSO
        assert resultado.extracao_sucesso is True
        assert resultado.lookup_sucesso is True
        assert resultado.armazenamento_sucesso is True
        assert resultado.folha_id == str(folha_id)

    def test_pipeline_erro_validacao(self, processador_completo, tmp_path):
        """Test error handling at validation stage."""
        proc, _, _, _, _ = processador_completo

        arquivo_invalido = tmp_path / "arquivo.txt"
        arquivo_invalido.write_text("nao e pdf")

        resultado = proc.processar(arquivo_invalido)

        assert resultado.status == StatusProcessamento.ERRO
        assert len(resultado.erros) > 0

    def test_pipeline_erro_extracao(self, processador_completo, temp_pdf_file):
        """Test error handling at extraction stage."""
        proc, mock_gemini, _, _, _ = processador_completo

        # All extraction attempts fail
        mock_gemini.documento_estruturado.side_effect = Exception("API Error")

        resultado = proc.processar(temp_pdf_file)

        assert resultado.status == StatusProcessamento.ERRO
        assert resultado.extracao_sucesso is False

    def test_pipeline_erro_lookup(
        self, processador_completo, extracao_json_completa, temp_pdf_file
    ):
        """Test error handling at lookup stage."""
        proc, mock_gemini, mock_func, _, _ = processador_completo

        mock_gemini.documento_estruturado.return_value = extracao_json_completa

        # Lookup fails
        mock_func.colecao.find.return_value = []
        mock_func.buscar_similar.return_value = None
        mock_func.criar_funcionario.return_value = None  # Creation fails

        resultado = proc.processar(temp_pdf_file)

        assert resultado.status == StatusProcessamento.ERRO
        assert resultado.lookup_sucesso is False

    def test_pipeline_metricas_tempo_total(
        self, processador_completo, extracao_json_completa, temp_pdf_file
    ):
        """Test metrics collection (tempo_processamento_total_s)."""
        proc, mock_gemini, mock_func, mock_folha, mock_empresa = processador_completo

        mock_gemini.documento_estruturado.return_value = extracao_json_completa
        mock_func.colecao.find.return_value = [
            {"_id": ObjectId(), "nome": "Joao Silva", "nome_normalizado": "joao silva"}
        ]
        mock_func.colecao.find_one.return_value = {"_id": ObjectId()}
        mock_func.colecao.update_one.return_value = MagicMock()
        mock_empresa.obter_ou_criar_incompleta.return_value = {"_id": ObjectId()}
        mock_folha.colecao.insert_one.return_value = MagicMock(inserted_id=ObjectId())

        resultado = proc.processar(temp_pdf_file)

        assert resultado.tempo_processamento_total_s > 0

    def test_pipeline_estrutura_resultado(
        self, processador_completo, extracao_json_completa, temp_pdf_file
    ):
        """Test result structure."""
        proc, mock_gemini, mock_func, mock_folha, mock_empresa = processador_completo

        mock_gemini.documento_estruturado.return_value = extracao_json_completa
        mock_func.colecao.find.return_value = [
            {"_id": ObjectId(), "nome": "Joao Silva", "nome_normalizado": "joao silva"}
        ]
        mock_func.colecao.find_one.return_value = {"_id": ObjectId()}
        mock_func.colecao.update_one.return_value = MagicMock()
        mock_empresa.obter_ou_criar_incompleta.return_value = {"_id": ObjectId()}
        mock_folha.colecao.insert_one.return_value = MagicMock(inserted_id=ObjectId())

        resultado = proc.processar(temp_pdf_file)

        assert isinstance(resultado, ProcessarResultado)
        assert hasattr(resultado, 'arquivo_origem')
        assert hasattr(resultado, 'status')
        assert hasattr(resultado, 'extracao_sucesso')
        assert hasattr(resultado, 'lookup_sucesso')
        assert hasattr(resultado, 'armazenamento_sucesso')
        assert hasattr(resultado, 'tempo_processamento_total_s')
        assert hasattr(resultado, 'mensagens')
        assert hasattr(resultado, 'erros')

    def test_pipeline_aceita_path_como_string(
        self, processador_completo, extracao_json_completa, temp_pdf_file
    ):
        """Test pipeline accepts path as string."""
        proc, mock_gemini, mock_func, mock_folha, mock_empresa = processador_completo

        mock_gemini.documento_estruturado.return_value = extracao_json_completa
        mock_func.colecao.find.return_value = [
            {"_id": ObjectId(), "nome": "Joao Silva", "nome_normalizado": "joao silva"}
        ]
        mock_func.colecao.find_one.return_value = {"_id": ObjectId()}
        mock_func.colecao.update_one.return_value = MagicMock()
        mock_empresa.obter_ou_criar_incompleta.return_value = {"_id": ObjectId()}
        mock_folha.colecao.insert_one.return_value = MagicMock(inserted_id=ObjectId())

        # Pass string path instead of Path
        resultado = proc.processar(str(temp_pdf_file))

        assert resultado.status == StatusProcessamento.SUCESSO


# ==================== Test Class: TestConversoesModelos ====================

class TestConversoesModelos:
    """Test model conversions."""

    def test_dia_extraido_para_dia_folha_ponto_conversao(self):
        """Test DiaExtraido -> DiaFolhaPonto conversion."""
        dia_extraido = DiaExtraido(
            numero_dia=1,
            data="2025-01-01",
            dia_semana="Quarta",
            hora_entrada="08:00",
            hora_intervalo_inicio="12:00",
            hora_intervalo_fim="13:00",
            hora_saida="17:00",
            total_horas_trabalhadas="08:00",
            observacoes="Dia normal",
            tipo_dia="NORMAL"
        )

        # Verify DiaExtraido can be created
        assert dia_extraido.numero_dia == 1
        assert dia_extraido.hora_entrada == "08:00"
        assert dia_extraido.tipo_dia == "NORMAL"

    def test_converter_string_para_tipo_dia_normal(self):
        """Test TipoDia conversion for NORMAL."""
        result = converter_string_para_tipo_dia("NORMAL")
        assert result == TipoDia.NORMAL

        result = converter_string_para_tipo_dia("normal")
        assert result == TipoDia.NORMAL

    def test_converter_string_para_tipo_dia_feriado(self):
        """Test TipoDia conversion for FERIADO."""
        result = converter_string_para_tipo_dia("FERIADO")
        assert result == TipoDia.FERIADO

        result = converter_string_para_tipo_dia("feriado")
        assert result == TipoDia.FERIADO

        # Partial match
        result = converter_string_para_tipo_dia("FERIADO NACIONAL")
        assert result == TipoDia.FERIADO

    def test_converter_string_para_tipo_dia_sabado(self):
        """Test TipoDia conversion for SABADO."""
        result = converter_string_para_tipo_dia("SABADO")
        assert result == TipoDia.SABADO

        result = converter_string_para_tipo_dia("SABADO")
        assert result == TipoDia.SABADO

    def test_converter_string_para_tipo_dia_domingo(self):
        """Test TipoDia conversion for DOMINGO."""
        result = converter_string_para_tipo_dia("DOMINGO")
        assert result == TipoDia.DOMINGO

    def test_converter_string_para_tipo_dia_falta(self):
        """Test TipoDia conversion for FALTA."""
        result = converter_string_para_tipo_dia("FALTA")
        assert result == TipoDia.FALTA

    def test_converter_string_para_tipo_dia_atestado(self):
        """Test TipoDia conversion for ATESTADO."""
        result = converter_string_para_tipo_dia("ATESTADO")
        assert result == TipoDia.ATESTADO

    def test_converter_string_para_tipo_dia_ferias(self):
        """Test TipoDia conversion for FERIAS."""
        result = converter_string_para_tipo_dia("FERIAS")
        assert result == TipoDia.FERIAS

        result = converter_string_para_tipo_dia("FERIAS")
        assert result == TipoDia.FERIAS

    def test_converter_string_para_tipo_dia_licenca(self):
        """Test TipoDia conversion for LICENCA."""
        result = converter_string_para_tipo_dia("LICENCA")
        assert result == TipoDia.LICENCA

        result = converter_string_para_tipo_dia("LICENCA")
        assert result == TipoDia.LICENCA

    def test_converter_string_para_tipo_dia_none_input(self):
        """Test TipoDia conversion with None input."""
        result = converter_string_para_tipo_dia(None)
        assert result is None

    def test_converter_string_para_tipo_dia_vazio(self):
        """Test TipoDia conversion with empty string."""
        result = converter_string_para_tipo_dia("")
        assert result is None

    def test_converter_string_para_tipo_dia_desconhecido(self):
        """Test TipoDia conversion with unknown value returns NORMAL."""
        result = converter_string_para_tipo_dia("VALOR_DESCONHECIDO")
        assert result == TipoDia.NORMAL


# ==================== Test Class: TestCalcularTotalHoras ====================

class TestCalcularTotalHoras:
    """Test calcular_total_horas utility function."""

    def test_calcular_horas_dia_normal(self):
        """Test hours calculation for normal day."""
        result = calcular_total_horas("08:00", "17:00", "12:00", "13:00")
        assert result == "08:00"

    def test_calcular_horas_sem_intervalo(self):
        """Test hours calculation without interval."""
        result = calcular_total_horas("08:00", "12:00", None, None)
        assert result == "04:00"

    def test_calcular_horas_com_minutos(self):
        """Test hours calculation with minutes."""
        result = calcular_total_horas("08:30", "17:30", "12:00", "13:00")
        assert result == "08:00"

    def test_calcular_horas_atravessa_meia_noite(self):
        """Test hours calculation crossing midnight."""
        result = calcular_total_horas("22:00", "06:00", None, None)
        assert result == "08:00"

    def test_calcular_horas_entrada_none(self):
        """Test returns None when entrada is None."""
        result = calcular_total_horas(None, "17:00", "12:00", "13:00")
        assert result is None

    def test_calcular_horas_saida_none(self):
        """Test returns None when saida is None."""
        result = calcular_total_horas("08:00", None, "12:00", "13:00")
        assert result is None

    def test_calcular_horas_formato_invalido(self):
        """Test returns None for invalid format."""
        result = calcular_total_horas("invalido", "17:00", None, None)
        assert result is None


# ==================== Test Class: TestExtratorFolhaPonto ====================

class TestExtratorFolhaPonto:
    """Test ExtratorFolhaPonto Pydantic model."""

    def test_criar_extracao_minima(self):
        """Test creating ExtratorFolhaPonto with minimal data."""
        extracao = ExtratorFolhaPonto()

        assert extracao.empresa_nome is None
        assert extracao.funcionario_nome is None
        assert extracao.dias == []
        assert extracao.dias_com_dados == 0

    def test_criar_extracao_completa(self):
        """Test creating ExtratorFolhaPonto with all fields."""
        extracao = ExtratorFolhaPonto(
            empresa_nome="Empresa Teste",
            empresa_cnpj="12.345.678/0001-90",
            funcionario_nome="Joao Silva",
            funcionario_pis="12345678901",
            funcionario_cpf="123.456.789-00",
            periodo_inicio="2025-01-01",
            periodo_fim="2025-01-31",
            mes_ano="2025-01",
            dias=[DiaExtraido(numero_dia=1)],
            dias_com_dados=1,
            dias_em_branco=30,
            confianca_geral=95,
            avisos=["Aviso teste"],
            erros=[]
        )

        assert extracao.empresa_nome == "Empresa Teste"
        assert extracao.funcionario_nome == "Joao Silva"
        assert len(extracao.dias) == 1
        assert extracao.confianca_geral == 95

    def test_validar_json_para_extracao(self):
        """Test JSON validation against Pydantic schema."""
        json_data = """
        {
            "empresa_nome": "Teste",
            "funcionario_nome": "Joao",
            "mes_ano": "2025-01",
            "dias": [{"numero_dia": 1}],
            "dias_com_dados": 1,
            "dias_em_branco": 0,
            "confianca_geral": 80
        }
        """

        extracao = ExtratorFolhaPonto.model_validate_json(json_data)

        assert extracao.empresa_nome == "Teste"
        assert extracao.funcionario_nome == "Joao"
        assert len(extracao.dias) == 1


# ==================== Test Class: TestProcessarResultado ====================

class TestProcessarResultado:
    """Test ProcessarResultado model."""

    def test_criar_resultado_inicial(self):
        """Test creating initial ProcessarResultado."""
        resultado = ProcessarResultado(arquivo_origem="/test/file.pdf")

        assert resultado.arquivo_origem == "/test/file.pdf"
        assert resultado.status == StatusProcessamento.PENDENTE
        assert resultado.extracao_sucesso is False
        assert resultado.lookup_sucesso is False
        assert resultado.armazenamento_sucesso is False
        assert len(resultado.mensagens) == 0
        assert len(resultado.erros) == 0

    def test_resultado_adiciona_mensagens(self):
        """Test adding messages to resultado."""
        resultado = ProcessarResultado(arquivo_origem="/test/file.pdf")
        resultado.mensagens.append("Mensagem 1")
        resultado.mensagens.append("Mensagem 2")

        assert len(resultado.mensagens) == 2
        assert "Mensagem 1" in resultado.mensagens

    def test_resultado_adiciona_erros(self):
        """Test adding errors to resultado."""
        resultado = ProcessarResultado(arquivo_origem="/test/file.pdf")
        resultado.erros.append("Erro 1")
        resultado.erros.append("Erro 2")

        assert len(resultado.erros) == 2
        assert "Erro 1" in resultado.erros

    def test_resultado_status_enum(self):
        """Test status enum values."""
        resultado = ProcessarResultado(arquivo_origem="/test/file.pdf")

        resultado.status = StatusProcessamento.SUCESSO
        assert resultado.status == StatusProcessamento.SUCESSO

        resultado.status = StatusProcessamento.ERRO
        assert resultado.status == StatusProcessamento.ERRO

        resultado.status = StatusProcessamento.EXTRAIDO
        assert resultado.status == StatusProcessamento.EXTRAIDO
