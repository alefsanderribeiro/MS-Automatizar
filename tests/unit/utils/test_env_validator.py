"""
Testes Unitários para o módulo env_validator

Testa validação de variáveis de ambiente, incluindo:
- Validadores de formato
- Classes de configuração
- Validação de ambiente completo
- Funções de conveniência
"""

import os
import pytest
from typing import List
from unittest.mock import patch, MagicMock

from src.utils.env_validator import (
    validar_mongo_uri,
    validar_api_key,
    validar_nome_banco,
    NivelVariavel,
    VariavelConfig,
    AmbienteInvalidoError,
    ValidadorAmbiente,
    validar_ambiente,
    verificar_ambiente_startup,
    obter_variavel,
    VARIAVEIS_AMBIENTE
)


# =============================================================================
# TestValidarMongoUri - URIs válidas/inválidas
# =============================================================================

class TestValidarMongoUri:
    """Testes para validador de URI do MongoDB"""

    def test_uri_valida_mongodb(self):
        """Testa URI válida com mongodb://"""
        valido, mensagem = validar_mongo_uri("mongodb://localhost:27017")
        assert valido is True
        assert mensagem == "OK"

    def test_uri_valida_mongodb_srv(self):
        """Testa URI válida com mongodb+srv://"""
        valido, mensagem = validar_mongo_uri("mongodb+srv://cluster.mongodb.net")
        assert valido is True
        assert mensagem == "OK"

    def test_uri_vazia(self):
        """Testa URI vazia"""
        valido, mensagem = validar_mongo_uri("")
        assert valido is False
        assert "vazia" in mensagem.lower()

    def test_uri_sem_prefixo(self):
        """Testa URI sem prefixo correto"""
        valido, mensagem = validar_mongo_uri("localhost:27017")
        assert valido is False
        assert "mongodb://" in mensagem or "mongodb+srv://" in mensagem

    def test_uri_prefixo_invalido(self):
        """Testa URI com prefixo inválido"""
        valido, mensagem = validar_mongo_uri("mysql://localhost:3306")
        assert valido is False
        assert "mongodb://" in mensagem or "mongodb+srv://" in mensagem


# =============================================================================
# TestValidarApiKey - chaves válidas/curtas/vazias
# =============================================================================

class TestValidarApiKey:
    """Testes para validador de API key"""

    def test_api_key_valida(self):
        """Testa API key válida"""
        valido, mensagem = validar_api_key("1234567890abcdef")
        assert valido is True
        assert mensagem == "OK"

    def test_api_key_minima(self):
        """Testa API key com tamanho mínimo (10 caracteres)"""
        valido, mensagem = validar_api_key("1234567890")
        assert valido is True
        assert mensagem == "OK"

    def test_api_key_curta(self):
        """Testa API key muito curta"""
        valido, mensagem = validar_api_key("123456789")
        assert valido is False
        assert "curta" in mensagem.lower()
        assert "10" in mensagem

    def test_api_key_vazia(self):
        """Testa API key vazia"""
        valido, mensagem = validar_api_key("")
        assert valido is False
        assert "vazia" in mensagem.lower()

    def test_api_key_com_espacos(self):
        """Testa API key com espaços (válida se >= 10 chars)"""
        valido, mensagem = validar_api_key("12 34 56 78 90")
        assert valido is True
        assert mensagem == "OK"


# =============================================================================
# TestValidarNomeBanco - nomes válidos/com caracteres especiais
# =============================================================================

class TestValidarNomeBanco:
    """Testes para validador de nome de banco"""

    def test_nome_valido(self):
        """Testa nome válido"""
        valido, mensagem = validar_nome_banco("MS_Automatizar")
        assert valido is True
        assert mensagem == "OK"

    def test_nome_alfanumerico(self):
        """Testa nome alfanumérico"""
        valido, mensagem = validar_nome_banco("banco123")
        assert valido is True
        assert mensagem == "OK"

    def test_nome_vazio(self):
        """Testa nome vazio"""
        valido, mensagem = validar_nome_banco("")
        assert valido is False
        assert "vazio" in mensagem.lower()

    def test_nome_com_barra(self):
        """Testa nome com barra"""
        valido, mensagem = validar_nome_banco("banco/teste")
        assert valido is False
        assert "caracteres inválidos" in mensagem.lower()

    def test_nome_com_ponto(self):
        """Testa nome com ponto"""
        valido, mensagem = validar_nome_banco("banco.db")
        assert valido is False
        assert "caracteres inválidos" in mensagem.lower()

    def test_nome_com_dolar(self):
        """Testa nome com cifrão"""
        valido, mensagem = validar_nome_banco("banco$")
        assert valido is False
        assert "caracteres inválidos" in mensagem.lower()


# =============================================================================
# TestNivelVariavel - valores do enum
# =============================================================================

class TestNivelVariavel:
    """Testes para enum NivelVariavel"""

    def test_nivel_obrigatoria(self):
        """Testa nível OBRIGATORIA"""
        assert NivelVariavel.OBRIGATORIA.value == "obrigatória"

    def test_nivel_recomendada(self):
        """Testa nível RECOMENDADA"""
        assert NivelVariavel.RECOMENDADA.value == "recomendada"

    def test_nivel_opcional(self):
        """Testa nível OPCIONAL"""
        assert NivelVariavel.OPCIONAL.value == "opcional"

    def test_todos_niveis_presentes(self):
        """Testa que todos os níveis esperados existem"""
        niveis = [e.name for e in NivelVariavel]
        assert "OBRIGATORIA" in niveis
        assert "RECOMENDADA" in niveis
        assert "OPCIONAL" in niveis


# =============================================================================
# TestVariavelConfig - dataclass
# =============================================================================

class TestVariavelConfig:
    """Testes para dataclass VariavelConfig"""

    def test_criacao_minima(self):
        """Testa criação com campos mínimos"""
        var = VariavelConfig(
            nome="TEST_VAR",
            nivel=NivelVariavel.OBRIGATORIA,
            descricao="Teste"
        )
        assert var.nome == "TEST_VAR"
        assert var.nivel == NivelVariavel.OBRIGATORIA
        assert var.descricao == "Teste"
        assert var.valor_padrao is None
        assert var.validador is None
        assert var.exemplo is None

    def test_criacao_completa(self):
        """Testa criação com todos os campos"""
        var = VariavelConfig(
            nome="TEST_VAR",
            nivel=NivelVariavel.RECOMENDADA,
            descricao="Teste completo",
            valor_padrao="default",
            validador=validar_api_key,
            exemplo="exemplo123"
        )
        assert var.nome == "TEST_VAR"
        assert var.nivel == NivelVariavel.RECOMENDADA
        assert var.descricao == "Teste completo"
        assert var.valor_padrao == "default"
        assert var.validador == validar_api_key
        assert var.exemplo == "exemplo123"


# =============================================================================
# TestAmbienteInvalidoError - Exception customizada
# =============================================================================

class TestAmbienteInvalidoError:
    """Testes para exceção AmbienteInvalidoError"""

    def test_criacao_basica(self):
        """Testa criação básica da exceção"""
        erro = AmbienteInvalidoError("Ambiente inválido")
        assert str(erro) == "Ambiente inválido"
        assert erro.mensagem == "Ambiente inválido"
        assert erro.variaveis_faltando == []

    def test_criacao_com_variaveis(self):
        """Testa criação com lista de variáveis faltando"""
        erro = AmbienteInvalidoError(
            "Ambiente inválido",
            variaveis_faltando=["VAR1", "VAR2"]
        )
        assert erro.mensagem == "Ambiente inválido"
        assert erro.variaveis_faltando == ["VAR1", "VAR2"]


# =============================================================================
# TestValidadorAmbiente - validar com/sem strict
# =============================================================================

class TestValidadorAmbiente:
    """Testes para classe ValidadorAmbiente"""

    @pytest.fixture
    def variaveis_teste(self):
        """Fixture com variáveis de teste"""
        return [
            VariavelConfig(
                nome="VAR_OBRIGATORIA",
                nivel=NivelVariavel.OBRIGATORIA,
                descricao="Variável obrigatória",
                validador=validar_api_key
            ),
            VariavelConfig(
                nome="VAR_RECOMENDADA",
                nivel=NivelVariavel.RECOMENDADA,
                descricao="Variável recomendada"
            ),
            VariavelConfig(
                nome="VAR_OPCIONAL",
                nivel=NivelVariavel.OPCIONAL,
                descricao="Variável opcional",
                valor_padrao="padrao"
            )
        ]

    def test_init_com_variaveis_customizadas(self, variaveis_teste):
        """Testa inicialização com variáveis customizadas"""
        with patch('src.utils.env_validator.caminho_dotenv'), \
             patch('dotenv.load_dotenv'):
            validador = ValidadorAmbiente(variaveis=variaveis_teste)
            assert len(validador.variaveis) == 3
            assert validador.variaveis[0].nome == "VAR_OBRIGATORIA"

    def test_init_sem_variaveis(self):
        """Testa inicialização sem variáveis (usa padrão)"""
        with patch('src.utils.env_validator.caminho_dotenv'), \
             patch('dotenv.load_dotenv'):
            validador = ValidadorAmbiente()
            assert validador.variaveis == VARIAVEIS_AMBIENTE

    def test_validar_ambiente_valido(self, variaveis_teste, monkeypatch):
        """Testa validação com ambiente válido"""
        monkeypatch.setenv("VAR_OBRIGATORIA", "1234567890abc")
        monkeypatch.setenv("VAR_RECOMENDADA", "valor")

        with patch('src.utils.env_validator.caminho_dotenv'), \
             patch('dotenv.load_dotenv'):
            validador = ValidadorAmbiente(variaveis=variaveis_teste)
            resultado = validador.validar()

            assert resultado["valido"] is True
            assert len(resultado["erros"]) == 0

    def test_validar_obrigatoria_ausente(self, variaveis_teste):
        """Testa validação com obrigatória ausente"""
        with patch('src.utils.env_validator.caminho_dotenv'), \
             patch('dotenv.load_dotenv'), \
             patch.dict(os.environ, {}, clear=True):
            validador = ValidadorAmbiente(variaveis=variaveis_teste)
            resultado = validador.validar()

            assert resultado["valido"] is False
            assert len(resultado["erros"]) > 0
            assert any("VAR_OBRIGATORIA" in erro for erro in resultado["erros"])

    def test_validar_strict_recomendada_ausente(self, variaveis_teste):
        """Testa validação strict com recomendada ausente"""
        with patch('src.utils.env_validator.caminho_dotenv'), \
             patch('dotenv.load_dotenv'), \
             patch.dict(os.environ, {"VAR_OBRIGATORIA": "1234567890abc"}, clear=True):
            validador = ValidadorAmbiente(variaveis=variaveis_teste)
            resultado = validador.validar(strict=True)

            assert resultado["valido"] is False
            assert any("VAR_RECOMENDADA" in erro for erro in resultado["erros"])

    def test_validar_nao_strict_recomendada_ausente(self, variaveis_teste):
        """Testa validação não-strict com recomendada ausente"""
        with patch('src.utils.env_validator.caminho_dotenv'), \
             patch('dotenv.load_dotenv'), \
             patch.dict(os.environ, {"VAR_OBRIGATORIA": "1234567890abc"}, clear=True):
            validador = ValidadorAmbiente(variaveis=variaveis_teste)
            resultado = validador.validar(strict=False)

            assert resultado["valido"] is True
            assert len(resultado["avisos"]) > 0
            assert any("VAR_RECOMENDADA" in aviso for aviso in resultado["avisos"])


# =============================================================================
# TestValidarVariavel - variáveis presentes/ausentes/com padrão
# =============================================================================

class TestValidarVariavel:
    """Testes para método _validar_variavel"""

    @pytest.fixture
    def validador(self):
        """Fixture com validador básico"""
        with patch('src.utils.env_validator.caminho_dotenv'), \
             patch('dotenv.load_dotenv'):
            return ValidadorAmbiente(variaveis=[])

    def test_variavel_presente_valida(self, validador, monkeypatch):
        """Testa variável presente e válida"""
        monkeypatch.setenv("TEST_VAR", "1234567890abc")

        var_config = VariavelConfig(
            nome="TEST_VAR",
            nivel=NivelVariavel.OBRIGATORIA,
            descricao="Teste",
            validador=validar_api_key
        )

        resultado = validador._validar_variavel(var_config)

        assert resultado["presente"] is True
        assert resultado["valido"] is True
        assert resultado["valor_atual"] == "1234567890abc"

    def test_variavel_ausente_com_padrao(self, validador):
        """Testa variável ausente com valor padrão"""
        with patch.dict(os.environ, {}, clear=True):
            var_config = VariavelConfig(
                nome="TEST_VAR",
                nivel=NivelVariavel.OPCIONAL,
                descricao="Teste",
                valor_padrao="default123"
            )

            resultado = validador._validar_variavel(var_config)

            assert resultado["presente"] is False
            assert resultado["usando_padrao"] is True
            assert resultado["valor_padrao"] == "default123"

    def test_variavel_ausente_sem_padrao(self, validador):
        """Testa variável ausente sem valor padrão"""
        with patch.dict(os.environ, {}, clear=True):
            var_config = VariavelConfig(
                nome="TEST_VAR",
                nivel=NivelVariavel.OBRIGATORIA,
                descricao="Teste"
            )

            resultado = validador._validar_variavel(var_config)

            assert resultado["presente"] is False
            assert resultado["usando_padrao"] is False

    def test_variavel_invalida(self, validador, monkeypatch):
        """Testa variável com valor inválido"""
        monkeypatch.setenv("TEST_VAR", "abc")  # Muito curta para API key

        var_config = VariavelConfig(
            nome="TEST_VAR",
            nivel=NivelVariavel.OBRIGATORIA,
            descricao="Teste",
            validador=validar_api_key
        )

        resultado = validador._validar_variavel(var_config)

        assert resultado["presente"] is True
        assert resultado["valido"] is False
        assert resultado["erro"] is not None


# =============================================================================
# TestObterResumo - formatação do resumo
# =============================================================================

class TestObterResumo:
    """Testes para método obter_resumo"""

    def test_resumo_contem_titulo(self, monkeypatch):
        """Testa que resumo contém título"""
        monkeypatch.setenv("VAR_OBRIGATORIA", "1234567890abc")

        variaveis = [
            VariavelConfig(
                nome="VAR_OBRIGATORIA",
                nivel=NivelVariavel.OBRIGATORIA,
                descricao="Teste"
            )
        ]

        with patch('src.utils.env_validator.caminho_dotenv'), \
             patch('dotenv.load_dotenv'):
            validador = ValidadorAmbiente(variaveis=variaveis)
            resumo = validador.obter_resumo()

            assert "VALIDAÇÃO DE AMBIENTE" in resumo
            assert "=" in resumo

    def test_resumo_com_erros(self):
        """Testa resumo quando há erros"""
        variaveis = [
            VariavelConfig(
                nome="VAR_OBRIGATORIA",
                nivel=NivelVariavel.OBRIGATORIA,
                descricao="Teste"
            )
        ]

        with patch('src.utils.env_validator.caminho_dotenv'), \
             patch('dotenv.load_dotenv'), \
             patch.dict(os.environ, {}, clear=True):
            validador = ValidadorAmbiente(variaveis=variaveis)
            resumo = validador.obter_resumo()

            assert "ERROS" in resumo
            assert "❌" in resumo

    def test_resumo_com_avisos(self, monkeypatch):
        """Testa resumo quando há avisos"""
        monkeypatch.setenv("VAR_OBRIGATORIA", "1234567890abc")

        variaveis = [
            VariavelConfig(
                nome="VAR_OBRIGATORIA",
                nivel=NivelVariavel.OBRIGATORIA,
                descricao="Teste obrigatória",
                validador=validar_api_key
            ),
            VariavelConfig(
                nome="VAR_RECOMENDADA",
                nivel=NivelVariavel.RECOMENDADA,
                descricao="Teste recomendada"
            )
        ]

        with patch('src.utils.env_validator.caminho_dotenv'), \
             patch('dotenv.load_dotenv'):
            validador = ValidadorAmbiente(variaveis=variaveis)
            resumo = validador.obter_resumo()

            assert "AVISOS" in resumo
            assert "⚠️" in resumo


# =============================================================================
# TestValidarAmbiente - função de conveniência
# =============================================================================

class TestValidarAmbiente:
    """Testes para função validar_ambiente"""

    def test_retorna_true_quando_valido(self, monkeypatch):
        """Testa que retorna True quando ambiente é válido"""
        # Configurar todas as variáveis obrigatórias
        monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
        monkeypatch.setenv("MONGO_DATABASE_NAME", "test_db")

        with patch('src.utils.env_validator.caminho_dotenv'), \
             patch('dotenv.load_dotenv'):
            resultado = validar_ambiente()
            assert resultado is True

    def test_retorna_false_quando_invalido(self):
        """Testa que retorna False quando ambiente é inválido"""
        with patch('src.utils.env_validator.caminho_dotenv'), \
             patch('dotenv.load_dotenv'), \
             patch.dict(os.environ, {}, clear=True):
            resultado = validar_ambiente()
            assert resultado is False

    @patch('src.utils.env_validator.logger')
    def test_exibir_resumo_true(self, mock_logger, monkeypatch):
        """Testa exibição de resumo quando exibir_resumo=True"""
        monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
        monkeypatch.setenv("MONGO_DATABASE_NAME", "test_db")

        with patch('src.utils.env_validator.caminho_dotenv'), \
             patch('dotenv.load_dotenv'):
            validar_ambiente(exibir_resumo=True)

            # Deve ter chamado logger.info com o resumo
            assert mock_logger.info.called


# =============================================================================
# TestVerificarAmbienteStartup - exibe avisos
# =============================================================================

class TestVerificarAmbienteStartup:
    """Testes para função verificar_ambiente_startup"""

    @patch('src.utils.env_validator.logger')
    def test_exibe_avisos_quando_invalido(self, mock_logger):
        """Testa que exibe avisos quando ambiente é inválido"""
        with patch('src.utils.env_validator.caminho_dotenv'), \
             patch('dotenv.load_dotenv'), \
             patch.dict(os.environ, {}, clear=True):
            verificar_ambiente_startup()

            # Deve ter chamado logger.warning
            assert mock_logger.warning.called

    @patch('src.utils.env_validator.logger')
    def test_nao_bloqueia_execucao(self, mock_logger):
        """Testa que não levanta exceção (não bloqueia)"""
        with patch('src.utils.env_validator.caminho_dotenv'), \
             patch('dotenv.load_dotenv'), \
             patch.dict(os.environ, {}, clear=True):
            # Não deve levantar exceção
            verificar_ambiente_startup()


# =============================================================================
# TestObterVariavel - fallback para padrão
# =============================================================================

class TestObterVariavel:
    """Testes para função obter_variavel"""

    def test_retorna_valor_existente(self, monkeypatch):
        """Testa que retorna valor quando variável existe"""
        monkeypatch.setenv("TEST_VAR", "valor_teste")

        resultado = obter_variavel("TEST_VAR")
        assert resultado == "valor_teste"

    def test_retorna_padrao_config_quando_ausente(self):
        """Testa que retorna padrão da config quando ausente"""
        with patch.dict(os.environ, {}, clear=True):
            # MONGO_URI tem valor padrão na configuração
            resultado = obter_variavel("MONGO_URI")
            assert resultado == "mongodb://localhost:27017"

    def test_retorna_padrao_fornecido_quando_ausente(self):
        """Testa que retorna padrão fornecido quando ausente"""
        with patch.dict(os.environ, {}, clear=True):
            resultado = obter_variavel("VAR_INEXISTENTE", padrao="meu_padrao")
            assert resultado == "meu_padrao"

    def test_retorna_none_quando_sem_padrao(self):
        """Testa que retorna None quando não há padrão"""
        with patch.dict(os.environ, {}, clear=True):
            # KEY_API_GEMINI não tem valor padrão na configuração
            resultado = obter_variavel("KEY_API_GEMINI")
            assert resultado is None

    def test_ignora_valor_vazio(self):
        """Testa que valor vazio é tratado como ausente"""
        with patch.dict(os.environ, {"TEST_VAR": ""}, clear=True):
            resultado = obter_variavel("TEST_VAR", padrao="padrao")
            assert resultado == "padrao"
