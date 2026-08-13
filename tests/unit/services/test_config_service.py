"""
Unit tests for ConfigService (src.services.config_service)

Covers:
- Dataclasses / Enums (ModoOperacao, TipoConfiguracao, ConfigItem)
- __init__ / _carregar_configs
- obter (config conhecida, desconhecida, valor padrão)
- definir (sucesso, LOG_LEVEL, erro)
- remover (sucesso, erro)
- listar_por_tipo / listar_todas
- validar (ok, obrigatoria faltando, aviso de API)
- obter_modo_operacao / usar_mongodb / usar_excel (todos os enums + inválido)
- obter_mongo_uri / obter_mongo_database (padrões)
- criar_arquivo_env_se_necessario (existe, cria, erro)
- exibir_valor (sensível, padrão, não configurado, normal)
- obter_config_service / obter_config / definir_config (módulo)
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from src.services.config_service import (
    ConfigService,
    obter_config_service,
    obter_config,
    definir_config,
    ModoOperacao,
    TipoConfiguracao,
    ConfigItem,
)


@pytest.fixture
def svc(mocker):
    """ConfigService com dotenv e env mocks."""
    mocker.patch("src.services.config_service.caminho_dotenv",
                 return_value="/tmp/.env-teste")
    mocker.patch("os.getenv", return_value=None)  # env vazio por padrão
    s = ConfigService()
    return s


# ==================== Enums / Dataclass ====================

class TestModelos:
    def test_modo_operacao_valores(self):
        assert ModoOperacao.MONGODB_ONLY.value == "mongodb"
        assert ModoOperacao.EXCEL_ONLY.value == "excel"
        assert ModoOperacao.AMBOS.value == "ambos"

    def test_tipo_config_valores(self):
        assert TipoConfiguracao.MONGODB.value == "mongodb"
        assert TipoConfiguracao.API.value == "api"
        assert TipoConfiguracao.SISTEMA.value == "sistema"
        assert TipoConfiguracao.ONEDRIVE.value == "onedrive"

    def test_config_item_defaults(self):
        c = ConfigItem(chave="X", valor="1", tipo=TipoConfiguracao.SISTEMA, descricao="d")
        assert c.obrigatorio is False
        assert c.valor_padrao is None
        assert c.sensivel is False

    def test_config_sensivel_e_obrigatorio(self):
        c = ConfigItem("K", "v", TipoConfiguracao.API, "d", True, "padrao", True)
        assert c.obrigatorio is True
        assert c.valor_padrao == "padrao"
        assert c.sensivel is True


# ==================== Inicialização ====================

class TestInicializacao:
    def test_init_carrega_do_env(self, svc, mocker):
        # MONGO_URI presente no env -> carregado
        mocker.patch("os.getenv", side_effect=lambda k: {"MONGO_URI": "abc"}.get(k))
        svc._carregar_configs()
        assert svc.CONFIGS_DISPONIVEIS["MONGO_URI"].valor == "abc"

    def test_init_env_path(self, svc):
        assert svc.env_path == "/tmp/.env-teste"

    def test_configs_registradas(self, svc):
        assert "MONGO_URI" in svc.CONFIGS_DISPONIVEIS
        assert "KEY_API_GEMINI" in svc.CONFIGS_DISPONIVEIS
        assert "MODO_OPERACAO" in svc.CONFIGS_DISPONIVEIS
        assert "ONEDRIVE_URL_DADOS" in svc.CONFIGS_DISPONIVEIS


# ==================== obter ====================

class TestObter:
    def test_obter_com_valor(self, svc, mocker):
        mocker.patch("os.getenv", return_value="uri")
        svc._carregar_configs()  # recarrega para ler o env
        assert svc.obter("MONGO_URI") == "uri"

    def test_obter_valor_ou_padrao(self, svc):
        # env vazio -> usa valor_padrao
        assert svc.obter("MONGO_URI") == "mongodb://localhost:27017"

    def test_obter_chave_desconhecida(self, svc, mocker):
        mocker.patch("os.getenv", return_value="env_val")
        assert svc.obter("CHAVE_ALEATORIA") == "env_val"

    def test_obter_sem_padrao_retorna_none(self, svc):
        assert svc.obter("DIRETORIO_SAIDA") is None


# ==================== definir ====================

class TestDefinir:
    def test_definir_sucesso(self, svc, mocker):
        set_key = mocker.patch("dotenv.set_key")
        mocker.patch.object(svc.CONFIGS_DISPONIVEIS["MONGO_URI"], "valor", None)
        assert svc.definir("MONGO_URI", "nova-uri") is True
        set_key.assert_called_once_with("/tmp/.env-teste", "MONGO_URI", "nova-uri")
        assert "MONGO_URI" in os.environ
        assert svc.CONFIGS_DISPONIVEIS["MONGO_URI"].valor == "nova-uri"

    def test_definir_log_level_atualiza_logger(self, svc, mocker):
        mocker.patch("dotenv.set_key")
        import src.services.config_service as mod
        atualizar_nivel = mocker.patch.object(mod.logger, "atualizar_nivel")
        assert svc.definir("LOG_LEVEL", "DEBUG") is True
        atualizar_nivel.assert_called_once_with("DEBUG")

    def test_definir_erro(self, svc, mocker):
        mocker.patch("dotenv.set_key", side_effect=Exception("boom"))
        assert svc.definir("MONGO_URI", "x") is False


# ==================== remover ====================

class TestRemover:
    def test_remover_sucesso(self, svc, mocker):
        unset = mocker.patch("dotenv.unset_key")
        svc.CONFIGS_DISPONIVEIS["MONGO_URI"].valor = "algum"
        assert svc.remover("MONGO_URI") is True
        unset.assert_called_once_with("/tmp/.env-teste", "MONGO_URI")
        assert svc.CONFIGS_DISPONIVEIS["MONGO_URI"].valor is None

    def test_remover_do_os_environ(self, svc, mocker):
        mocker.patch("dotenv.unset_key")
        os.environ["MONGO_URI"] = "x"
        assert svc.remover("MONGO_URI") is True
        assert "MONGO_URI" not in os.environ

    def test_remover_erro(self, svc, mocker):
        mocker.patch("dotenv.unset_key", side_effect=Exception("boom"))
        assert svc.remover("MONGO_URI") is False


# ==================== listar ====================

class TestListar:
    def test_listar_por_tipo(self, svc):
        api = svc.listar_por_tipo(TipoConfiguracao.API)
        assert all(c.tipo == TipoConfiguracao.API for c in api)
        assert any(c.chave == "KEY_API_GEMINI" for c in api)

    def test_listar_por_tipo_mongodb(self, svc):
        mongodb = svc.listar_por_tipo(TipoConfiguracao.MONGODB)
        assert any(c.chave == "MONGO_URI" for c in mongodb)

    def test_listar_todas(self, svc, mocker):
        carregar = mocker.patch.object(svc, "_carregar_configs")
        todas = svc.listar_todas()
        carregar.assert_called_once()
        assert "MONGO_URI" in todas


# ==================== validar ====================

class TestValidar:
    def test_validar_ok(self, svc, mocker):
        # MONGO_URI e MONGO_DATABASE_NAME definidos (obrigatórios)
        mocker.patch("os.getenv", side_effect=lambda k: {
            "MONGO_URI": "uri", "MONGO_DATABASE_NAME": "db"
        }.get(k))
        res = svc.validar()
        assert res["valido"] is True
        assert res["erros"] == []

    def test_validar_obrigatoria_faltando(self, svc):
        # Injeita uma config obrigatória SEM valor padrão para exercitar o erro
        svc.CONFIGS_DISPONIVEIS["NOVA_OBRIGATORIA"] = ConfigItem(
            chave="NOVA_OBRIGATORIA", valor=None,
            tipo=TipoConfiguracao.SISTEMA, descricao="d", obrigatorio=True,
        )
        res = svc.validar()
        assert res["valido"] is False
        assert any("NOVA_OBRIGATORIA" in e for e in res["erros"])

    def test_validar_obrigatoria_com_padrao_satisfaz(self, svc):
        # MONGO_URI tem valor padrão -> mesmo sem env, não é erro
        res = svc.validar()
        assert not any("MONGO_URI" in e for e in res["erros"])

    def test_validar_aviso_api(self, svc):
        res = svc.validar()
        assert any("KEY_API_GEMINI" in a for a in res["avisos"])


# ==================== modo de operação ====================

class TestModoOperacao:
    def test_modo_mongodb(self, svc, mocker):
        mocker.patch.object(svc, "obter", return_value="mongodb")
        assert svc.obter_modo_operacao() == ModoOperacao.MONGODB_ONLY
        assert svc.usar_mongodb() is True
        assert svc.usar_excel() is False

    def test_modo_excel(self, svc, mocker):
        mocker.patch.object(svc, "obter", return_value="excel")
        assert svc.usar_mongodb() is False
        assert svc.usar_excel() is True

    def test_modo_ambos(self, svc, mocker):
        mocker.patch.object(svc, "obter", return_value="ambos")
        assert svc.usar_mongodb() is True
        assert svc.usar_excel() is True

    def test_modo_invalido_fallback_mongodb(self, svc, mocker):
        mocker.patch.object(svc, "obter", return_value="modo-invalido")
        assert svc.obter_modo_operacao() == ModoOperacao.MONGODB_ONLY

    def test_modo_none_fallback(self, svc, mocker):
        mocker.patch.object(svc, "obter", return_value=None)
        assert svc.obter_modo_operacao() == ModoOperacao.MONGODB_ONLY


# ==================== helpers mongo ====================

class TestHelpersMongo:
    def test_mongo_uri_padrao(self, svc, mocker):
        mocker.patch.object(svc, "obter", return_value=None)
        assert svc.obter_mongo_uri() == "mongodb://localhost:27017"

    def test_mongo_uri_definida(self, svc, mocker):
        mocker.patch.object(svc, "obter", return_value="mongodb://x")
        assert svc.obter_mongo_uri() == "mongodb://x"

    def test_mongo_database_padrao(self, svc, mocker):
        mocker.patch.object(svc, "obter", return_value=None)
        assert svc.obter_mongo_database() == "MS_Automatizar"

    def test_mongo_database_definida(self, svc, mocker):
        mocker.patch.object(svc, "obter", return_value="meu_db")
        assert svc.obter_mongo_database() == "meu_db"


# ==================== criar arquivo .env ====================

class TestCriarArquivoEnv:
    def test_ja_existe(self, svc, mocker):
        mocker.patch("os.path.exists", return_value=True)
        assert svc.criar_arquivo_env_se_necessario() is False

    def test_cria_arquivo(self, svc, mocker):
        mocker.patch("os.path.exists", return_value=False)
        abrir = mocker.patch("builtins.open", new_callable=MagicMock)
        assert svc.criar_arquivo_env_se_necessario() is True
        abrir.assert_called_once()

    def test_erro_ao_criar(self, svc, mocker):
        mocker.patch("os.path.exists", return_value=False)
        mocker.patch("builtins.open", side_effect=Exception("boom"))
        assert svc.criar_arquivo_env_se_necessario() is False


# ==================== exibir_valor ====================

class TestExibirValor:
    def test_sem_valor_nem_padrao(self):
        c = ConfigItem("K", None, TipoConfiguracao.SISTEMA, "d")
        s = ConfigService.__new__(ConfigService)
        assert s.exibir_valor(c) == "(não configurado)"

    def test_sem_valor_com_padrao(self):
        c = ConfigItem("K", None, TipoConfiguracao.SISTEMA, "d", valor_padrao="p")
        s = ConfigService.__new__(ConfigService)
        assert s.exibir_valor(c) == "(padrão: p)"

    def test_sensivel_curto(self):
        c = ConfigItem("K", "12345", TipoConfiguracao.API, "d", sensivel=True)
        s = ConfigService.__new__(ConfigService)
        assert s.exibir_valor(c) == "****"

    def test_sensivel_longo_mascarado(self):
        c = ConfigItem("K", "abcdefghijkl", TipoConfiguracao.API, "d", sensivel=True)
        s = ConfigService.__new__(ConfigService)
        assert s.exibir_valor(c) == "abcd...ijkl"

    def test_valor_normal(self):
        c = ConfigItem("K", "visivel", TipoConfiguracao.SISTEMA, "d")
        s = ConfigService.__new__(ConfigService)
        assert s.exibir_valor(c) == "visivel"


# ==================== funções de módulo ====================

class TestFuncoesModulo:
    def test_obter_config_service_singleton(self, mocker):
        mocker.patch("src.services.config_service.caminho_dotenv",
                     return_value="/tmp/.env-mod")
        import src.services.config_service as mod
        mod._config_service = None
        s1 = obter_config_service()
        s2 = obter_config_service()
        assert s1 is s2

    def test_obter_config(self, mocker):
        import src.services.config_service as mod
        inst = MagicMock()
        inst.obter.return_value = "v"
        mod._config_service = inst
        assert obter_config("MONGO_URI") == "v"
        inst.obter.assert_called_once_with("MONGO_URI")

    def test_definir_config(self, mocker):
        import src.services.config_service as mod
        inst = MagicMock()
        inst.definir.return_value = True
        mod._config_service = inst
        assert definir_config("MONGO_URI", "x") is True
        inst.definir.assert_called_once_with("MONGO_URI", "x")
