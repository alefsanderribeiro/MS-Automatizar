"""
Unit tests for ConfigEnvioFolhaPontoMongoDB model.

Covers:
- Validação obrigatória (identificador, nome)
- Normalização de flags S/N (aceita S, SIM, Y, YES, 1, TRUE, X, True, 1)
- Flag booleano helper
- Nome normalizado (minúsculas, sem acentos)
- to_dict_contato (formato esperado pelo orquestrador)
- Soft delete helper (marcar_excluida)
- Builder
- Singleton no module services
"""

import pytest
from src.models.config_envio_folha_ponto_models import (
    SimNaoEnum,
    OrigemConfigEnum,
    ConfigEnvioFolhaPontoMongoDB,
    ConfigEnvioFolhaPontoBuilder,
)


def make_config(**kwargs):
    dados = {
        "identificador": "1",
        "nome": "João da Silva",
        "emails": ["joao@x.com"],
        "telefones": ["96999999999"],
        "grupos_whatsapp": ["Administrativo"],
        "enviar_email": "S",
        "enviar_whatsapp": "N",
        "enviar_grupo_whatsapp": "S",
        "enviar_impresso": "N",
        "empresa": "MS Servicos",
        "local_contrato_polo": "DSEI AMAPÁ",
        "diretorio_geral": "Z:\\04. PESSOAL\\FOLHA PONTO",
        "diretorio_especifico": "01. MS SERVIÇOS\\ADMINISTRATIVO",
    }
    dados.update(kwargs)
    return dados


class TestValidacaoObrigatoria:
    def test_identificador_obrigatorio(self):
        with pytest.raises(ValueError):
            ConfigEnvioFolhaPontoMongoDB(**make_config(identificador=""))

    def test_nome_obrigatorio(self):
        with pytest.raises(ValueError):
            ConfigEnvioFolhaPontoMongoDB(**make_config(nome=""))

    def test_validacao_sucesso(self):
        c = ConfigEnvioFolhaPontoMongoDB(**make_config())
        assert c.identificador == "1"
        assert c.nome == "João da Silva"


class TestFlags:
    @pytest.mark.parametrize("valor,esperado", [
        ("S", "S"), ("SIM", "S"), ("Y", "S"), ("YES", "S"),
        ("1", "S"), ("TRUE", "S"), ("X", "S"),
    ])
    def test_flag_sim_variacoes(self, valor, esperado):
        c = ConfigEnvioFolhaPontoMongoDB(**make_config(enviar_email=valor))
        assert c.enviar_email == esperado

    def test_flag_bool_true(self):
        c = ConfigEnvioFolhaPontoMongoDB(**make_config(enviar_whatsapp=True, enviar_grupo_whatsapp=1))
        assert c.enviar_whatsapp == "S"
        assert c.enviar_grupo_whatsapp == "S"

    def test_flag_n(self):
        c = ConfigEnvioFolhaPontoMongoDB(**make_config(enviar_email="N", enviar_whatsapp=""))
        assert c.enviar_email == "N"
        assert c.enviar_whatsapp == "N"

    def test_flag_none_vira_n(self):
        c = ConfigEnvioFolhaPontoMongoDB(**make_config(enviar_email=None))
        assert c.enviar_email == "N"

    def test_flag_default_n(self):
        dados = make_config()
        for campo in ("enviar_email", "enviar_whatsapp", "enviar_grupo_whatsapp", "enviar_impresso"):
            dados.pop(campo)
        c = ConfigEnvioFolhaPontoMongoDB(**dados)
        assert c.enviar_email == "N"
        assert c.enviar_whatsapp == "N"
        assert c.enviar_grupo_whatsapp == "N"
        assert c.enviar_impresso == "N"

    def test_flag_booleano_helper(self):
        c = ConfigEnvioFolhaPontoMongoDB(**make_config(
            enviar_email="S", enviar_whatsapp="N", enviar_grupo_whatsapp="S", enviar_impresso="N"
        ))
        assert c.flag_booleano("enviar_email") is True
        assert c.flag_booleano("enviar_whatsapp") is False
        assert c.flag_booleano("enviar_grupo_whatsapp") is True
        assert c.flag_booleano("enviar_impresso") is False


class TestNomeNormalizado:
    def test_normaliza_acentos_e_minusculas(self):
        c = ConfigEnvioFolhaPontoMongoDB(**make_config(nome="JOÃO DA SILVA"))
        assert c.nome_normalizado == "joao da silva"

    def test_normaliza_texto_classmethod(self):
        assert ConfigEnvioFolhaPontoMongoDB.normalizar_texto("DSEI Amapá") == "dsei amapa"


class TestToDictContato:
    def test_formato_orquestrador(self):
        c = ConfigEnvioFolhaPontoMongoDB(**make_config())
        d = c.to_dict_contato(1, 2025, "/tmp/folhas", ["a.pdf"])
        assert d["id"] == "1"
        assert d["nome"] == "João da Silva"
        assert d["local_contrato_polo"] == "DSEI AMAPÁ"
        assert d["diretorio_completo"] == "/tmp/folhas"
        assert d["arquivos_pdf"] == ["a.pdf"]
        assert d["emails"] == ["joao@x.com"]
        assert d["telefones"] == ["96999999999"]
        assert d["grupos_whatsapp"] == ["Administrativo"]
        # Flags convertidos para booleano
        assert d["enviar_email"] is True
        assert d["enviar_whatsapp"] is False
        assert d["enviar_grupo_whatsapp"] is True
        assert d["mes_referencia"] == 1
        assert d["ano_referencia"] == 2025

    def test_arquivos_default(self):
        c = ConfigEnvioFolhaPontoMongoDB(**make_config())
        d = c.to_dict_contato(1, 2025)
        assert d["arquivos_pdf"] == []


class TestSoftDelete:
    def test_marcar_excluida(self):
        c = ConfigEnvioFolhaPontoMongoDB(**make_config())
        c.marcar_excluida()
        assert c.excluida is True
        assert c.ativo is False
        assert c.excluida_em is not None
        assert c.versao == 2  # adicionar_historico incrementa versao

    def test_nao_duplica_exclusao(self):
        c = ConfigEnvioFolhaPontoMongoDB(**make_config())
        c.marcar_excluida()
        primeira_exclusao_em = c.excluida_em
        c.marcar_excluida()
        assert c.excluida_em == primeira_exclusao_em  # não muda


class TestBuilder:
    def test_builder_build(self):
        c = (ConfigEnvioFolhaPontoBuilder()
             .identificacao("1", "Maria")
             .contato(emails=["maria@x.com"], telefones=["1"], grupos_whatsapp=["G"])
             .flags(email="S", whatsapp="S", grupo="N", impresso="N")
             .organizacao(empresa="MS", local_contrato_polo="DSEI")
             .diretorio("/geral", "/esp")
             .origem(OrigemConfigEnum.PLANILHA)
             .build())
        assert c.nome == "Maria"
        assert c.enviar_email == "S"
        assert c.origem == OrigemConfigEnum.PLANILHA.value
        assert c.nome_normalizado == "maria"


class TestEnums:
    def test_sim_nao_enum(self):
        assert SimNaoEnum.SIM.value == "S"
        assert SimNaoEnum.NAO.value == "N"

    def test_origem_enum(self):
        assert OrigemConfigEnum.PLANILHA.value == "planilha"
        assert OrigemConfigEnum.MANUAL.value == "manual"
        assert OrigemConfigEnum.MIGRACAO.value == "migracao"
