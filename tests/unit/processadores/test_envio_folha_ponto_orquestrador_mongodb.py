"""
Unit tests for EnvioFolhaPontoOrquestrador using MongoDB as config source.

Covers a transição planilha -> MongoDB:
- _carregar_contatos com MongoDB disponível (usa Mongo)
- _carregar_contatos com MongoDB vazio (fallback planilha)
- _carregar_contatos com MongoDB indisponível (fallback planilha)
- _carregar_contatos com usar_mongodb=False (força planilha)
- executar com fonte MongoDB (happy path / contatos sem PDF)
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from src.processadores.envio_folha_ponto_orquestrador import (
    EnvioFolhaPontoOrquestrador,
    RelatorioEnvio,
)
from src.models.envio_folha_ponto_models import TipoEnvioEnum


@pytest.fixture
def orquestrador(mocker):
    """Orquestrador com services mockados; configs (Mongo) disponível por padrão."""
    planilha = mocker.patch(
        "src.processadores.envio_folha_ponto_orquestrador.planilha_contatos_service"
    )
    configs = mocker.patch(
        "src.processadores.envio_folha_ponto_orquestrador.config_envio_folha_ponto_service"
    )
    envio = mocker.patch(
        "src.processadores.envio_folha_ponto_orquestrador.envio_folha_ponto_service"
    )
    template = mocker.patch(
        "src.processadores.envio_folha_ponto_orquestrador.template_mensagem_service"
    )
    grupo = mocker.patch(
        "src.processadores.envio_folha_ponto_orquestrador.grupo_whatsapp_service"
    )
    zoho = mocker.patch(
        "src.processadores.envio_folha_ponto_orquestrador.zoho_mail_service"
    )
    whatsapp = mocker.patch(
        "src.processadores.envio_folha_ponto_orquestrador.whatsapp_service"
    )
    empresa = mocker.patch(
        "src.processadores.envio_folha_ponto_orquestrador.empresa_service"
    )
    mocker.patch(
        "src.processadores.envio_folha_ponto_orquestrador.obter_config_retry",
        return_value=(3, 5),
    )

    planilha.disponivel = True
    planilha.carregar.return_value = True
    planilha.iterar_contatos.return_value = iter([])
    configs.disponivel = True
    configs.listar_ativos_para_envio.return_value = []
    envio.disponivel = True
    template.disponivel = True
    grupo.disponivel = True
    zoho.disponivel = True
    whatsapp.disponivel = True
    empresa.disponivel = True

    whatsapp.verificar_status.return_value = {"conectado": True}
    zoho.verificar_conexao.return_value = {"token_valido": True, "configurado": True}

    return {
        "planilha": planilha,
        "configs": configs,
        "envio": envio,
        "template": template,
        "grupo": grupo,
        "zoho": zoho,
        "whatsapp": whatsapp,
        "empresa": empresa,
        "orq": EnvioFolhaPontoOrquestrador(),
    }


def make_contato(**kwargs):
    c = {
        "id": "c1",
        "nome": "João Silva",
        "local_contrato_polo": "DSEI AMAPÁ",
        "empresa": "MS Servicos",
        "mes_referencia": 1,
        "ano_referencia": 2025,
        "emails": ["joao@x.com"],
        "telefones": ["96999999999"],
        "grupos_whatsapp": ["Administrativo"],
        "arquivos_pdf": ["/tmp/folha_joao.pdf"],
        "enviar_email": True,
        "enviar_whatsapp": False,
        "enviar_grupo_whatsapp": False,
    }
    c.update(kwargs)
    return c


# ==================== _carregar_contatos ====================

class TestCarregarContatos:
    def test_usar_mongodb_disponivel(self, orquestrador):
        m = orquestrador
        contato = make_contato()
        m["configs"].listar_ativos_para_envio.return_value = [contato]

        contatos, fonte = m["orq"]._carregar_contatos(1, 2025, usar_mongodb=True)
        assert fonte == "mongodb"
        assert contatos == [contato]
        m["configs"].listar_ativos_para_envio.assert_called_once_with(1, 2025)
        m["planilha"].carregar.assert_not_called()

    def test_mongodb_vazio_fallback_planilha(self, orquestrador):
        m = orquestrador
        m["configs"].listar_ativos_para_envio.return_value = []
        contato = make_contato()
        m["planilha"].iterar_contatos.return_value = iter([contato])

        contatos, fonte = m["orq"]._carregar_contatos(1, 2025, usar_mongodb=True)
        assert fonte == "planilha"
        assert contatos == [contato]

    def test_mongodb_indisponivel_fallback_planilha(self, orquestrador):
        m = orquestrador
        m["configs"].disponivel = False
        contato = make_contato()
        m["planilha"].iterar_contatos.return_value = iter([contato])

        contatos, fonte = m["orq"]._carregar_contatos(1, 2025, usar_mongodb=True)
        assert fonte == "planilha"
        assert contatos == [contato]

    def test_forcar_planilha(self, orquestrador):
        m = orquestrador
        contato = make_contato()
        m["planilha"].iterar_contatos.return_value = iter([contato])

        contatos, fonte = m["orq"]._carregar_contatos(1, 2025, usar_mongodb=False)
        assert fonte == "planilha"
        assert contatos == [contato]
        m["configs"].listar_ativos_para_envio.assert_not_called()

    def test_planilha_falha(self, orquestrador):
        m = orquestrador
        m["configs"].disponivel = False
        m["planilha"].carregar.return_value = False

        contatos, fonte = m["orq"]._carregar_contatos(1, 2025, usar_mongodb=True)
        assert contatos is None
        assert fonte is None


# ==================== executar com fonte MongoDB ====================

class TestExecutarComMongoDB:
    def test_executar_fonte_mongodb_envia(self, orquestrador):
        m = orquestrador
        contato = make_contato()
        m["configs"].listar_ativos_para_envio.return_value = [contato]
        m["envio"].registrar_envio.return_value = "x"
        m["template"].renderizar_por_tipo.return_value = {"assunto": "Folha", "mensagem": "oi"}
        m["zoho"].enviar_email.return_value = {"sucesso": True, "mensagem": "ok", "detalhes": {}}

        rel = m["orq"].executar(1, 2025)
        assert rel.total_contatos == 1
        assert rel.total_envios == 1  # só email ativo (whatsapp/grupo = False)
        assert rel.enviados_sucesso == 1
        assert rel.por_tipo[TipoEnvioEnum.EMAIL.value]["sucesso"] == 1
        # Não foi para a planilha
        m["planilha"].carregar.assert_not_called()

    def test_executar_contato_sem_arquivos(self, orquestrador):
        m = orquestrador
        m["configs"].listar_ativos_para_envio.return_value = [
            make_contato(arquivos_pdf=[])
        ]
        rel = m["orq"].executar(1, 2025)
        assert rel.total_contatos == 1
        assert rel.total_envios == 0  # pulado por sem arquivos

    def test_executar_mongodb_vazio_usa_planilha(self, orquestrador):
        m = orquestrador
        m["configs"].listar_ativos_para_envio.return_value = []
        m["planilha"].iterar_contatos.return_value = iter([make_contato()])
        m["envio"].registrar_envio.return_value = "x"
        m["template"].renderizar_por_tipo.return_value = {"assunto": "Folha", "mensagem": "oi"}
        m["zoho"].enviar_email.return_value = {"sucesso": True, "mensagem": "ok", "detalhes": {}}

        rel = m["orq"].executar(1, 2025)
        assert rel.total_contatos == 1
        m["planilha"].carregar.assert_called_once()

    def test_executar_forca_planilha(self, orquestrador):
        m = orquestrador
        m["configs"].listar_ativos_para_envio.return_value = [make_contato()]
        m["planilha"].iterar_contatos.return_value = iter([make_contato()])
        m["envio"].registrar_envio.return_value = "x"
        m["template"].renderizar_por_tipo.return_value = {"assunto": "Folha", "mensagem": "oi"}
        m["zoho"].enviar_email.return_value = {"sucesso": True, "mensagem": "ok", "detalhes": {}}

        rel = m["orq"].executar(1, 2025, usar_mongodb=False)
        assert rel.total_contatos == 1
        m["configs"].listar_ativos_para_envio.assert_not_called()
        m["planilha"].carregar.assert_called_once()

    def test_executar_fonte_indisponivel_erro(self, orquestrador):
        m = orquestrador
        m["configs"].disponivel = False
        m["planilha"].carregar.return_value = False

        rel = m["orq"].executar(1, 2025)
        assert rel.total_contatos == 0
        assert rel.erros  # registro de erro de carregamento

    def test_verificar_servicos_inclui_configs(self, orquestrador):
        m = orquestrador
        status = m["orq"].verificar_servicos()
        assert status["mongodb_config_envios"] is True
