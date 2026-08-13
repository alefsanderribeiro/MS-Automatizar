"""
Unit tests for EnvioFolhaPontoOrquestrador

Covers:
- ResultadoEnvio / RelatorioEnvio dataclasses
- verificar_servicos
- sincronizar_grupos_whatsapp (todos os caminhos)
- _preprocessar_grupos_por_empresa
- _enviar_email / _enviar_whatsapp_individual / _enviar_whatsapp_grupo
- _registrar_envio (sucesso / parcial / erro)
- executar (happy path, dry_run, contatos sem PDF, serviço desconectado)
- executar_retry
- Singleton
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from src.processadores.envio_folha_ponto_orquestrador import (
    EnvioFolhaPontoOrquestrador,
    envio_folha_ponto_orquestrador,
    ResultadoEnvio,
    RelatorioEnvio,
    MESES_EXTENSO,
)
from src.models.envio_folha_ponto_models import (
    TipoEnvioEnum,
    StatusEnvioEnum,
)
from src.models.template_mensagem_models import TipoTemplateEnum


# ==================== Dataclasses / Singleton ====================

class TestDataclasses:
    def test_singleton_existe(self):
        assert isinstance(envio_folha_ponto_orquestrador, EnvioFolhaPontoOrquestrador)

    def test_resultado_envio_campos(self):
        r = ResultadoEnvio(
            tipo=TipoEnvioEnum.EMAIL,
            sucesso=True,
            destinatario="a@b.com",
            arquivos=["x.pdf"],
            mensagem="ok",
            detalhes={"k": 1},
        )
        assert r.tipo == TipoEnvioEnum.EMAIL
        assert r.sucesso is True
        assert r.arquivos == ["x.pdf"]

    def test_relatorio_duracao_sem_fim(self):
        r = RelatorioEnvio(mes=1, ano=2025)
        assert r.duracao_segundos() == 0

    def test_relatorio_duracao_com_fim(self):
        r = RelatorioEnvio(mes=1, ano=2025)
        r.fim = datetime.now(timezone.utc)
        assert r.duracao_segundos() >= 0

    def test_meses_extenso(self):
        assert MESES_EXTENSO[1] == "Janeiro"
        assert MESES_EXTENSO[12] == "Dezembro"


# ==================== Fixtures ====================

@pytest.fixture
def orquestrador(mocker):
    """Orquestrador com todos os services singleton mockados."""
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

    # Defaults
    planilha.disponivel = True
    planilha.carregar.return_value = True
    # Por padrão, o MongoDB de configs fica INDISPONÍVEL para que os testes
    # existentes caiam no fallback da planilha (comportamento anterior).
    configs.disponivel = False
    configs.listar_ativos_para_envio.return_value = []
    envio.disponivel = True
    template.disponivel = True
    grupo.disponivel = True
    zoho.disponivel = True
    whatsapp.disponivel = True
    empresa.disponivel = True

    whatsapp.verificar_status.return_value = {"conectado": True}
    zoho.verificar_conexao.return_value = {
        "token_valido": True,
        "configurado": True,
    }

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
    """Factory de contato de planilha."""
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
        "enviar_whatsapp": True,
        "enviar_grupo_whatsapp": True,
    }
    c.update(kwargs)
    return c


# ==================== verificar_servicos ====================

class TestVerificarServicos:
    def test_todos_disponiveis(self, orquestrador):
        m = orquestrador
        status = m["orq"].verificar_servicos()
        assert status["whatsapp_conectado"] is True
        assert status["zoho_mail_conectado"] is True
        m["whatsapp"].verificar_status.assert_called_once()
        m["zoho"].verificar_conexao.assert_called_once()

    def test_whatsapp_indisponivel(self, orquestrador):
        m = orquestrador
        m["whatsapp"].disponivel = False
        status = m["orq"].verificar_servicos()
        assert status["whatsapp_conectado"] is False
        m["whatsapp"].verificar_status.assert_not_called()

    def test_zoho_indisponivel(self, orquestrador):
        m = orquestrador
        m["zoho"].disponivel = False
        status = m["orq"].verificar_servicos()
        assert status["zoho_mail_conectado"] is False
        assert status["zoho_mail_configurado"] is False
        m["zoho"].verificar_conexao.assert_not_called()

    def test_callbacks_progresso(self, orquestrador):
        m = orquestrador
        chamadas = []
        m["orq"].definir_callback_progresso(
            lambda msg, at, tot: chamadas.append((msg, at, tot))
        )
        m["orq"].verificar_servicos()
        assert any("Verificando serviços" in msg for msg, _, _ in chamadas)

    def test_reportar_sem_callback(self, orquestrador):
        # Não deve levantar quando callback None
        m = orquestrador
        m["orq"]._reportar_progresso("teste", 1, 2)
        assert True


# ==================== sincronizar_grupos_whatsapp ====================

class TestSincronizarGrupos:
    def test_whatsapp_indisponivel(self, orquestrador):
        m = orquestrador
        m["whatsapp"].disponivel = False
        res = m["orq"].sincronizar_grupos_whatsapp()
        assert res == {"criados": 0, "atualizados": 0, "inativos": 0}

    def test_whatsapp_nao_conectado(self, orquestrador):
        m = orquestrador
        m["whatsapp"].verificar_status.return_value = {"conectado": False}
        res = m["orq"].sincronizar_grupos_whatsapp()
        assert res == {"criados": 0, "atualizados": 0, "inativos": 0}

    def test_sem_dispositivos(self, orquestrador):
        m = orquestrador
        m["whatsapp"].listar_dispositivos.return_value = []
        res = m["orq"].sincronizar_grupos_whatsapp()
        assert res["criados"] == 0

    def test_nenhum_dispositivo_logado(self, orquestrador):
        m = orquestrador
        m["whatsapp"].listar_dispositivos.return_value = [
            {"id": "d1", "display_name": "X", "state": "disconnected"}
        ]
        res = m["orq"].sincronizar_grupos_whatsapp()
        assert res["criados"] == 0

    def test_sincroniza_grupos(self, orquestrador):
        m = orquestrador
        m["whatsapp"].listar_dispositivos.return_value = [
            {"id": "d1", "display_name": "WhatsApp-Alefe", "state": "logged_in"}
        ]
        m["whatsapp"].listar_grupos.return_value = [{"nome": "Admin", "jid": "123@g.us"}]
        m["grupo"].sincronizar_com_api.return_value = {
            "criados": 2, "atualizados": 1, "inativos": 0
        }
        res = m["orq"].sincronizar_grupos_whatsapp()
        assert res == {"criados": 2, "atualizados": 1, "inativos": 0}
        m["grupo"].sincronizar_com_api.assert_called_once()

    def test_dispositivo_sem_id(self, orquestrador):
        m = orquestrador
        m["whatsapp"].listar_dispositivos.return_value = [
            {"display_name": "X", "state": "logged_in"}
        ]
        res = m["orq"].sincronizar_grupos_whatsapp()
        assert res["criados"] == 0

    def test_grupos_vazio(self, orquestrador):
        m = orquestrador
        m["whatsapp"].listar_dispositivos.return_value = [
            {"id": "d1", "state": "logged_in"}
        ]
        m["whatsapp"].listar_grupos.return_value = []
        res = m["orq"].sincronizar_grupos_whatsapp()
        assert res["criados"] == 0


# ==================== _preprocessar_grupos_por_empresa ====================

class TestPreprocessarGrupos:
    def test_sem_empresas(self, orquestrador):
        m = orquestrador
        res = m["orq"]._preprocessar_grupos_por_empresa([{"nome": "X"}])
        assert res == {}

    def test_empresa_sem_device(self, orquestrador):
        m = orquestrador
        m["empresa"].buscar_por_nome_ou_simplificado.return_value = {"nome": "MS"}
        res = m["orq"]._preprocessar_grupos_por_empresa([make_contato()])
        assert res == {"MS Servicos": {}}

    def test_empresa_sem_id_interno(self, orquestrador):
        m = orquestrador
        m["empresa"].buscar_por_nome_ou_simplificado.return_value = {
            "nome": "MS", "whatsapp_device_id": "jid"
        }
        m["whatsapp"].obter_id_dispositivo_por_jid.return_value = None
        res = m["orq"]._preprocessar_grupos_por_empresa([make_contato()])
        assert res == {"MS Servicos": {}}

    def test_empresa_com_grupos(self, orquestrador):
        m = orquestrador
        m["empresa"].buscar_por_nome_ou_simplificado.return_value = {
            "nome": "MS", "whatsapp_device_id": "jid"
        }
        m["whatsapp"].obter_id_dispositivo_por_jid.return_value = "WhatsApp-Alefe"
        m["grupo"].listar_para_exibicao.return_value = [
            {"nome": "Administrativo", "jid": "123@g.us"}
        ]
        res = m["orq"]._preprocessar_grupos_por_empresa([make_contato()])
        assert "MS Servicos" in res
        assert res["MS Servicos"]["administrativo"] == "123@g.us"

    def test_erro_no_preprocessamento(self, orquestrador):
        m = orquestrador
        m["empresa"].buscar_por_nome_ou_simplificado.side_effect = Exception("boom")
        res = m["orq"]._preprocessar_grupos_por_empresa([make_contato()])
        assert res == {"MS Servicos": {}}


# ==================== _montar_contexto_template ====================

class TestMontarContexto:
    def test_contexto_basico(self, orquestrador):
        m = orquestrador
        ctx = m["orq"]._montar_contexto_template(make_contato())
        assert ctx["mes_extenso"] == "Janeiro"
        assert ctx["nome"] == "João Silva"
        assert ctx["mes"] == 1

    def test_contexto_mes_invalido(self, orquestrador):
        m = orquestrador
        c = make_contato(mes_referencia=99)
        ctx = m["orq"]._montar_contexto_template(c)
        assert ctx["mes_extenso"] == "99"


# ==================== Envios por canal ====================

class TestEnviarEmail:
    def test_sem_emails(self, orquestrador):
        m = orquestrador
        r = m["orq"]._enviar_email(make_contato(emails=[]))
        assert r.sucesso is False
        assert "Nenhum e-mail" in r.mensagem

    def test_sem_arquivos(self, orquestrador):
        m = orquestrador
        r = m["orq"]._enviar_email(make_contato(arquivos_pdf=[]))
        assert r.sucesso is False
        assert "Nenhum arquivo" in r.mensagem

    def test_template_nao_renderiza(self, orquestrador):
        m = orquestrador
        m["template"].renderizar_por_tipo.return_value = None
        r = m["orq"]._enviar_email(make_contato())
        assert r.sucesso is False

    def test_envio_sucesso(self, orquestrador):
        m = orquestrador
        m["template"].renderizar_por_tipo.return_value = {
            "assunto": "Folha", "mensagem": "Olá"
        }
        m["zoho"].enviar_email.return_value = {"sucesso": True, "mensagem": "ok", "detalhes": {}}
        r = m["orq"]._enviar_email(make_contato())
        assert r.sucesso is True
        m["template"].renderizar_por_tipo.assert_called_once_with(TipoTemplateEnum.EMAIL, m["orq"]._montar_contexto_template(make_contato()))

    def test_envio_falha(self, orquestrador):
        m = orquestrador
        m["template"].renderizar_por_tipo.return_value = {
            "assunto": "Folha", "mensagem": "Olá"
        }
        m["zoho"].enviar_email.return_value = {"sucesso": False, "mensagem": "falhou", "detalhes": {}}
        r = m["orq"]._enviar_email(make_contato())
        assert r.sucesso is False


class TestEnviarWhatsAppIndividual:
    def test_sem_telefones(self, orquestrador):
        m = orquestrador
        r = m["orq"]._enviar_whatsapp_individual(make_contato(telefones=[]))
        assert r.sucesso is False

    def test_sem_arquivos(self, orquestrador):
        m = orquestrador
        r = m["orq"]._enviar_whatsapp_individual(make_contato(arquivos_pdf=[]))
        assert r.sucesso is False

    def test_envio_sucesso(self, orquestrador):
        m = orquestrador
        m["template"].renderizar_por_tipo.return_value = {"mensagem": "Olá"}
        m["whatsapp"].enviar_multiplos_arquivos.return_value = {
            "sucesso": True, "parcial": False, "mensagem": "ok"
        }
        r = m["orq"]._enviar_whatsapp_individual(make_contato())
        assert r.sucesso is True

    def test_envio_parcial(self, orquestrador):
        m = orquestrador
        m["template"].renderizar_por_tipo.return_value = {"mensagem": "Olá"}
        # 2 telefones, só 1 com sucesso
        m["whatsapp"].enviar_multiplos_arquivos.side_effect = [
            {"sucesso": True, "parcial": False, "mensagem": "ok"},
            {"sucesso": False, "parcial": True, "mensagem": "parcial"},
        ]
        r = m["orq"]._enviar_whatsapp_individual(
            make_contato(telefones=["1", "2"])
        )
        assert r.sucesso is False  # não todos
        assert "1/2" in r.mensagem

    def test_envio_empresa_sem_device(self, orquestrador):
        m = orquestrador
        m["template"].renderizar_por_tipo.return_value = {"mensagem": "Olá"}
        m["whatsapp"].enviar_multiplos_arquivos.return_value = {
            "sucesso": True, "parcial": False, "mensagem": "ok"
        }
        m["empresa"].buscar_por_nome_ou_simplificado.return_value = {"nome": "MS"}
        r = m["orq"]._enviar_whatsapp_individual(make_contato())
        assert r.sucesso is True

    def test_envio_erro_busca_empresa(self, orquestrador):
        m = orquestrador
        m["template"].renderizar_por_tipo.return_value = {"mensagem": "Olá"}
        m["whatsapp"].enviar_multiplos_arquivos.return_value = {
            "sucesso": True, "parcial": False, "mensagem": "ok"
        }
        m["empresa"].buscar_por_nome_ou_simplificado.side_effect = Exception("boom")
        r = m["orq"]._enviar_whatsapp_individual(make_contato())
        assert r.sucesso is True


class TestEnviarWhatsAppGrupo:
    def test_sem_grupos(self, orquestrador):
        m = orquestrador
        r = m["orq"]._enviar_whatsapp_grupo(make_contato(grupos_whatsapp=[]))
        assert r.sucesso is False

    def test_sem_arquivos(self, orquestrador):
        m = orquestrador
        r = m["orq"]._enviar_whatsapp_grupo(make_contato(arquivos_pdf=[]))
        assert r.sucesso is False

    def test_sem_device_id_interno(self, orquestrador):
        m = orquestrador
        m["empresa"].buscar_por_nome_ou_simplificado.return_value = {
            "nome": "MS", "whatsapp_device_id": "jid"
        }
        m["whatsapp"].obter_id_dispositivo_por_jid.return_value = None
        r = m["orq"]._enviar_whatsapp_grupo(make_contato())
        assert r.sucesso is False
        assert "sem dispositivo" in r.mensagem.lower()

    def test_envio_grupo_nao_encontrado(self, orquestrador):
        m = orquestrador
        m["empresa"].buscar_por_nome_ou_simplificado.return_value = {
            "nome": "MS", "whatsapp_device_id": "jid"
        }
        m["whatsapp"].obter_id_dispositivo_por_jid.return_value = "WhatsApp-Alefe"
        # cache vazio e banco não encontra
        m["grupo"].obter_jid_por_nome.return_value = None
        r = m["orq"]._enviar_whatsapp_grupo(make_contato())
        assert r.sucesso is False
        assert "nao encontrado" in r.detalhes["resultados"][0]["mensagem"]

    def test_envio_grupo_sucesso_cache(self, orquestrador):
        m = orquestrador
        m["empresa"].buscar_por_nome_ou_simplificado.return_value = {
            "nome": "MS Servicos", "whatsapp_device_id": "jid"
        }
        m["whatsapp"].obter_id_dispositivo_por_jid.return_value = "WhatsApp-Alefe"
        m["whatsapp"].enviar_multiplos_arquivos.return_value = {
            "sucesso": True, "parcial": False, "mensagem": "ok"
        }
        # Cache pré-processado com grupo
        m["orq"]._cache_grupos_por_empresa = {"MS Servicos": {"administrativo": "123@g.us"}}
        r = m["orq"]._enviar_whatsapp_grupo(make_contato())
        assert r.sucesso is True

    def test_envio_grupo_fallback_banco(self, orquestrador):
        m = orquestrador
        m["empresa"].buscar_por_nome_ou_simplificado.return_value = {
            "nome": "MS Servicos", "whatsapp_device_id": "jid"
        }
        m["whatsapp"].obter_id_dispositivo_por_jid.return_value = "WhatsApp-Alefe"
        m["whatsapp"].enviar_multiplos_arquivos.return_value = {
            "sucesso": True, "parcial": False, "mensagem": "ok"
        }
        # Cache vazio -> fallback busca no banco
        m["grupo"].obter_jid_por_nome.return_value = "123@g.us"
        m["orq"]._cache_grupos_por_empresa = {"MS Servicos": {}}
        r = m["orq"]._enviar_whatsapp_grupo(make_contato())
        assert r.sucesso is True
        m["grupo"].obter_jid_por_nome.assert_called_once()

    def test_envio_grupo_match_parcial_cache(self, orquestrador):
        m = orquestrador
        m["empresa"].buscar_por_nome_ou_simplificado.return_value = {
            "nome": "MS Servicos", "whatsapp_device_id": "jid"
        }
        m["whatsapp"].obter_id_dispositivo_por_jid.return_value = "WhatsApp-Alefe"
        m["whatsapp"].enviar_multiplos_arquivos.return_value = {
            "sucesso": True, "parcial": False, "mensagem": "ok"
        }
        # nome cache é substring do procurado
        m["orq"]._cache_grupos_por_empresa = {"MS Servicos": {"admin": "123@g.us"}}
        r = m["orq"]._enviar_whatsapp_grupo(make_contato())
        assert r.sucesso is True


# ==================== _registrar_envio ====================

class TestRegistrarEnvio:
    def test_registrar_sucesso(self, orquestrador):
        m = orquestrador
        r = ResultadoEnvio(
            tipo=TipoEnvioEnum.EMAIL, sucesso=True, destinatario="a@b.com"
        )
        m["envio"].registrar_envio.return_value = "abc123"
        ret = m["orq"]._registrar_envio(make_contato(), r)
        assert ret == "abc123"

    def test_registrar_parcial(self, orquestrador):
        m = orquestrador
        r = ResultadoEnvio(
            tipo=TipoEnvioEnum.WHATSAPP_INDIVIDUAL,
            sucesso=True,
            destinatario="1",
            detalhes={"resultados": [{"parcial": True}]},
        )
        m["envio"].registrar_envio.return_value = "x"
        m["orq"]._registrar_envio(make_contato(), r)
        # chamado com dados; status PARCIAL
        chamado = m["envio"].registrar_envio.call_args[0][0]
        assert chamado["status"] == StatusEnvioEnum.PARCIAL.value

    def test_registrar_erro(self, orquestrador):
        m = orquestrador
        r = ResultadoEnvio(
            tipo=TipoEnvioEnum.EMAIL, sucesso=False, destinatario="a@b.com",
            mensagem="falhou",
        )
        m["orq"]._registrar_envio(make_contato(), r)
        chamado = m["envio"].registrar_envio.call_args[0][0]
        assert chamado["status"] == StatusEnvioEnum.ERRO.value

    def test_registrar_exception(self, orquestrador):
        m = orquestrador
        m["envio"].registrar_envio.side_effect = Exception("boom")
        r = ResultadoEnvio(
            tipo=TipoEnvioEnum.EMAIL, sucesso=True, destinatario="a@b.com"
        )
        assert m["orq"]._registrar_envio(make_contato(), r) is None


# ==================== executar ====================

class TestExecutar:
    def test_falha_carregar_planilha(self, orquestrador):
        m = orquestrador
        m["planilha"].carregar.return_value = False
        rel = m["orq"].executar(1, 2025)
        assert rel.total_contatos == 0
        assert rel.erros  # tem erro de falha planilha

    def test_dry_run_sem_contatos(self, orquestrador):
        m = orquestrador
        m["planilha"].carregar.return_value = True
        m["planilha"].iterar_contatos.return_value = iter([])
        rel = m["orq"].executar(1, 2025, dry_run=True)
        assert rel.total_contatos == 0

    def test_contato_sem_arquivos(self, orquestrador):
        m = orquestrador
        m["planilha"].carregar.return_value = True
        m["planilha"].iterar_contatos.return_value = iter(
            [make_contato(arquivos_pdf=[])]
        )
        rel = m["orq"].executar(1, 2025)
        assert rel.total_contatos == 1
        assert rel.total_envios == 0  # pulado por sem arquivos

    def test_envio_email_servico_desconectado(self, orquestrador):
        m = orquestrador
        m["planilha"].carregar.return_value = True
        m["planilha"].iterar_contatos.return_value = iter([make_contato()])
        # Zoho desconectado -> email pulado, mas whatsapp conectado
        m["zoho"].verificar_conexao.return_value = {
            "token_valido": False, "configurado": False
        }
        m["envio"].registrar_envio.return_value = "x"
        m["template"].renderizar_por_tipo.return_value = {"mensagem": "oi"}
        m["whatsapp"].enviar_multiplos_arquivos.return_value = {
            "sucesso": True, "parcial": False, "mensagem": "ok"
        }
        rel = m["orq"].executar(1, 2025)
        # email não enviado por zoho desligado; loga warning
        assert rel.total_envios >= 1

    def test_executar_envia_todos_os_canais(self, orquestrador):
        m = orquestrador
        m["planilha"].carregar.return_value = True
        m["planilha"].iterar_contatos.return_value = iter([make_contato()])
        m["envio"].registrar_envio.return_value = "x"
        m["template"].renderizar_por_tipo.return_value = {
            "assunto": "Folha", "mensagem": "oi"
        }
        m["zoho"].enviar_email.return_value = {"sucesso": True, "mensagem": "ok", "detalhes": {}}
        m["whatsapp"].enviar_multiplos_arquivos.return_value = {
            "sucesso": True, "parcial": False, "mensagem": "ok"
        }
        m["empresa"].buscar_por_nome_ou_simplificado.return_value = {
            "nome": "MS Servicos", "whatsapp_device_id": "jid"
        }
        m["whatsapp"].obter_id_dispositivo_por_jid.return_value = "WhatsApp-Alefe"
        m["grupo"].obter_jid_por_nome.return_value = "123@g.us"

        rel = m["orq"].executar(1, 2025)
        assert rel.total_envios == 3  # email + whatsapp individual + grupo
        assert rel.enviados_sucesso == 3
        assert rel.por_tipo[TipoEnvioEnum.EMAIL.value]["sucesso"] == 1

    def test_executar_filtro_contatos_ids(self, orquestrador):
        m = orquestrador
        m["planilha"].carregar.return_value = True
        m["planilha"].iterar_contatos.return_value = iter(
            [make_contato(), make_contato(id="c2")]
        )
        rel = m["orq"].executar(1, 2025, contatos_ids=["c1"])
        assert rel.total_contatos == 1

    def test_executar_erro_whatsapp(self, orquestrador):
        m = orquestrador
        m["planilha"].carregar.return_value = True
        m["planilha"].iterar_contatos.return_value = iter([make_contato()])
        m["envio"].registrar_envio.return_value = "x"
        m["template"].renderizar_por_tipo.return_value = {"mensagem": "oi"}
        m["zoho"].enviar_email.return_value = {"sucesso": False, "mensagem": "falhou", "detalhes": {}}
        m["whatsapp"].enviar_multiplos_arquivos.return_value = {
            "sucesso": False, "parcial": False, "mensagem": "erro"
        }
        m["empresa"].buscar_por_nome_ou_simplificado.return_value = {
            "nome": "MS Servicos", "whatsapp_device_id": "jid"
        }
        m["whatsapp"].obter_id_dispositivo_por_jid.return_value = "WhatsApp-Alefe"
        m["grupo"].obter_jid_por_nome.return_value = "123@g.us"
        m["whatsapp"].verificar_status.return_value = {"conectado": True}

        rel = m["orq"].executar(1, 2025)
        assert rel.enviados_erro >= 1
        assert rel.erros  # tem erros registrados


class TestExecutarRetry:
    def test_sem_pendentes(self, orquestrador):
        m = orquestrador
        m["envio"].buscar_pendentes_retry.return_value = []
        rel = m["orq"].executar_retry()
        assert rel.total_envios == 0

    def test_com_pendentes(self, orquestrador):
        m = orquestrador
        m["envio"].buscar_pendentes_retry.return_value = [
            {"tipo_envio": "email", "local_contrato_polo": "DSEI", "tentativas": 1}
        ]
        rel = m["orq"].executar_retry(max_tentativas=3)
        assert rel.total_envios == 1

    def test_max_tentativas_default(self, orquestrador):
        m = orquestrador
        m["envio"].buscar_pendentes_retry.return_value = []
        m["orq"]._config_retry_max_tentativas = 3
        m["orq"].executar_retry()
        m["envio"].buscar_pendentes_retry.assert_called_once_with(3)
