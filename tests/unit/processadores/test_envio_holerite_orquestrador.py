"""
Unit tests for EnvioHoleriteOrquestrador

Covers:
- Dataclasses ResultadoEnvioHolerite / RelatorioEnvioHolerite
- Singleton / init
- verificar_servicos
- _montar_contexto_template (competência válida e inválida)
- _enviar_email / _enviar_whatsapp / _enviar_whatsapp_grupo
- enviar_via_planilha (happy path, simulação, sem PDFs, planilha não carrega)
- enviar_via_mongodb (happy path, sem pendentes, arquivo não encontrado,
  sem email/whatsapp cadastrado, simulação)
- obter_estatisticas_competencia
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from pathlib import Path

from src.processadores.envio_holerite_orquestrador import (
    EnvioHoleriteOrquestrador,
    envio_holerite_orquestrador,
    ResultadoEnvioHolerite,
    RelatorioEnvioHolerite,
    TipoEnvioEnum,
    MESES_EXTENSO,
)
from src.models.template_mensagem_models import TipoTemplateEnum


# ==================== Dataclasses / Singleton ====================

class TestDataclasses:
    def test_singleton_existe(self):
        assert isinstance(envio_holerite_orquestrador, EnvioHoleriteOrquestrador)

    def test_resultado_campos(self):
        r = ResultadoEnvioHolerite(
            tipo=TipoEnvioEnum.EMAIL,
            sucesso=True,
            destinatario="a@b.com",
            holerite_id="h1",
            arquivo="x.pdf",
            mensagem="ok",
        )
        assert r.tipo == TipoEnvioEnum.EMAIL
        assert r.sucesso is True
        assert r.holerite_id == "h1"

    def test_relatorio_duracao(self):
        r = RelatorioEnvioHolerite("01/2025", "planilha")
        assert r.duracao_segundos() == 0
        r.fim = datetime.now(timezone.utc)
        assert r.duracao_segundos() >= 0

    def test_meses_extenso(self):
        assert MESES_EXTENSO[6] == "Junho"


# ==================== Fixtures ====================

@pytest.fixture
def orquestrador(mocker, tmp_path):
    """Orquestrador com services mockados e um PDF temporário."""
    # PDF temporário para cenários de arquivo
    pdf_path = tmp_path / "holerite_joao.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    planilha = mocker.patch(
        "src.processadores.envio_holerite_orquestrador.planilha_holerites_service"
    )
    holerite = mocker.patch(
        "src.processadores.envio_holerite_orquestrador.holerite_service"
    )
    contato = mocker.patch(
        "src.processadores.envio_holerite_orquestrador.contato_funcionario_service"
    )
    empresa = mocker.patch(
        "src.processadores.envio_holerite_orquestrador.empresa_service"
    )
    template = mocker.patch(
        "src.processadores.envio_holerite_orquestrador.template_mensagem_service"
    )
    grupo = mocker.patch(
        "src.processadores.envio_holerite_orquestrador.grupo_whatsapp_service"
    )
    whatsapp = mocker.patch(
        "src.processadores.envio_holerite_orquestrador.whatsapp_service"
    )
    zoho = mocker.patch(
        "src.processadores.envio_holerite_orquestrador.zoho_mail_service"
    )
    mocker.patch(
        "src.processadores.envio_holerite_orquestrador.obter_config_retry",
        return_value=(3, 5),
    )
    mocker.patch(
        "src.processadores.envio_holerite_orquestrador.FuncionarioService"
    )
    import src.processadores.envio_holerite_orquestrador as mod
    _orig_wa = mod.WHATSAPP_DISPONIVEL
    _orig_zo = mod.ZOHO_DISPONIVEL
    mod.WHATSAPP_DISPONIVEL = True
    mod.ZOHO_DISPONIVEL = True

    planilha.disponivel = True
    holerite.disponivel = True
    contato.disponivel = True
    empresa.disponivel = True
    template.disponivel = True

    whatsapp.verificar_status.return_value = {"conectado": True}
    zoho.verificar_conexao.return_value = {"token_valido": True}

    return {
        "planilha": planilha,
        "holerite": holerite,
        "contato": contato,
        "empresa": empresa,
        "template": template,
        "grupo": grupo,
        "whatsapp": whatsapp,
        "zoho": zoho,
        "orq": EnvioHoleriteOrquestrador(),
        "pdf": str(pdf_path),
    }


# ==================== verificar_servicos ====================

class TestVerificarServicos:
    def test_todos_disponiveis(self, orquestrador):
        m = orquestrador
        status = m["orq"].verificar_servicos()
        assert status["whatsapp_conectado"] is True
        assert status["zoho_mail_conectado"] is True

    def test_whatsapp_indisponivel(self, orquestrador):
        m = orquestrador
        import src.processadores.envio_holerite_orquestrador as mod
        orig = mod.WHATSAPP_DISPONIVEL
        mod.WHATSAPP_DISPONIVEL = False
        try:
            status = m["orq"].verificar_servicos()
            assert status["whatsapp"] is False
        finally:
            mod.WHATSAPP_DISPONIVEL = orig

    def test_verificar_whatsapp_exception(self, orquestrador):
        m = orquestrador
        m["whatsapp"].verificar_status.side_effect = Exception("down")
        status = m["orq"].verificar_servicos()
        assert status["whatsapp_conectado"] is False

    def test_verificar_zoho_exception(self, orquestrador):
        m = orquestrador
        m["zoho"].verificar_conexao.side_effect = Exception("down")
        status = m["orq"].verificar_servicos()
        assert status["zoho_mail_conectado"] is False


# ==================== _montar_contexto_template ====================

class TestMontarContexto:
    def test_competencia_valida(self, orquestrador):
        m = orquestrador
        ctx = m["orq"]._montar_contexto_template(
            "João", "02/2025", empresa_nome="MS"
        )
        assert ctx["mes"] == 2
        assert ctx["ano"] == 2025
        assert ctx["mes_extenso"] == "Fevereiro"
        assert ctx["funcionario_nome"] == "João"
        assert ctx["nome"] == "João"
        assert ctx["empresa"] == "MS"

    def test_competencia_invalida(self, orquestrador):
        m = orquestrador
        ctx = m["orq"]._montar_contexto_template("João", "formato-errado")
        assert ctx["mes"] == 0
        assert ctx["ano"] == 0
        assert ctx["mes_extenso"] == "formato-errado"

    def test_dados_extras_merge(self, orquestrador):
        m = orquestrador
        ctx = m["orq"]._montar_contexto_template(
            "João", "01/2025", dados_extras={"local": "DSEI"}
        )
        assert ctx["local"] == "DSEI"


# ==================== _enviar_email ====================

class TestEnviarEmail:
    def test_sem_destinatarios(self, orquestrador):
        m = orquestrador
        r = m["orq"]._enviar_email([], ["a.pdf"], {})
        assert r.sucesso is False
        assert "Nenhum e-mail" in r.mensagem

    def test_sem_arquivos(self, orquestrador):
        m = orquestrador
        r = m["orq"]._enviar_email(["a@b.com"], [], {})
        assert r.sucesso is False
        assert "Nenhum arquivo" in r.mensagem

    def test_template_fallback_default(self, orquestrador):
        m = orquestrador
        m["template"].renderizar_por_tipo.return_value = None
        m["zoho"].enviar_email.return_value = {
            "sucesso": True, "mensagem": "ok", "detalhes": {}
        }
        r = m["orq"]._enviar_email(
            ["a@b.com"], ["x.pdf"],
            {"local": "DSEI", "mes_referencia": 1, "ano_referencia": 2025, "mes_extenso": "Janeiro"}
        )
        assert r.sucesso is True
        args = m["zoho"].enviar_email.call_args
        kwargs = args[1] if args and len(args) > 1 else {}
        assert "01/2025" in kwargs.get("assunto", "")
        assert "DSEI" in kwargs.get("assunto", "")

    def test_envio_sucesso_com_template(self, orquestrador):
        m = orquestrador
        m["template"].renderizar_por_tipo.return_value = {
            "assunto": "Recibo", "mensagem": "Olá"
        }
        m["zoho"].enviar_email.return_value = {
            "sucesso": True, "mensagem": "ok", "detalhes": {}
        }
        r = m["orq"]._enviar_email(["a@b.com"], ["x.pdf"], {})
        assert r.sucesso is True
        assert r.arquivo == "x.pdf"

    def test_envio_falha(self, orquestrador):
        m = orquestrador
        m["template"].renderizar_por_tipo.return_value = {
            "assunto": "Recibo", "mensagem": "Olá"
        }
        m["zoho"].enviar_email.return_value = {
            "sucesso": False, "mensagem": "erro", "detalhes": {}
        }
        r = m["orq"]._enviar_email(["a@b.com"], ["x.pdf"], {})
        assert r.sucesso is False


# ==================== _enviar_whatsapp ====================

class TestEnviarWhatsApp:
    def test_sem_telefone(self, orquestrador):
        m = orquestrador
        r = m["orq"]._enviar_whatsapp("", ["x.pdf"], {})
        assert r.sucesso is False
        assert "Nenhum telefone" in r.mensagem

    def test_sem_arquivos(self, orquestrador):
        m = orquestrador
        r = m["orq"]._enviar_whatsapp("96999", [], {})
        assert r.sucesso is False
        assert "Nenhum arquivo" in r.mensagem

    def test_template_fallback(self, orquestrador):
        m = orquestrador
        m["template"].renderizar_por_tipo.return_value = None
        m["whatsapp"].enviar_multiplos_arquivos.return_value = {
            "sucesso": True, "parcial": False, "mensagem": "ok"
        }
        r = m["orq"]._enviar_whatsapp(
            "96999", ["x.pdf"],
            {"funcionario_nome": "João", "mes_extenso": "Janeiro", "ano_referencia": 2025}
        )
        assert r.sucesso is True
        assert r.mensagem == "Enviado com sucesso"

    def test_envio_com_empresa_service(self, orquestrador):
        m = orquestrador
        m["template"].renderizar_por_tipo.return_value = {"mensagem": "oi"}
        m["empresa"].disponivel = True
        m["empresa"].buscar_por_nome_ou_simplificado.return_value = {
            "nome": "MS", "whatsapp_device_id": "jid"
        }
        m["whatsapp"].enviar_multiplos_arquivos.return_value = {
            "sucesso": True, "parcial": False, "mensagem": "ok"
        }
        r = m["orq"]._enviar_whatsapp(
            "96999", ["x.pdf"], {"empresa": "MS"}
        )
        assert r.sucesso is True

    def test_envio_erro_busca_empresa(self, orquestrador):
        m = orquestrador
        m["template"].renderizar_por_tipo.return_value = {"mensagem": "oi"}
        m["empresa"].buscar_por_nome_ou_simplificado.side_effect = Exception("boom")
        m["whatsapp"].enviar_multiplos_arquivos.return_value = {
            "sucesso": False, "parcial": False, "mensagem": "erro"
        }
        r = m["orq"]._enviar_whatsapp("96999", ["x.pdf"], {"empresa": "MS"})
        assert r.sucesso is False
        assert r.mensagem == "Falha no envio"


# ==================== _enviar_whatsapp_grupo ====================

class TestEnviarWhatsAppGrupo:
    def test_grupo_nao_encontrado(self, orquestrador):
        m = orquestrador
        m["grupo"].buscar_por_nome.return_value = None
        r = m["orq"]._enviar_whatsapp_grupo("Admin", ["x.pdf"], {})
        assert r.sucesso is False
        assert "não encontrado" in r.mensagem

    def test_grupo_sem_jid(self, orquestrador):
        m = orquestrador
        m["grupo"].buscar_por_nome.return_value = {"nome": "Admin"}
        r = m["orq"]._enviar_whatsapp_grupo("Admin", ["x.pdf"], {})
        assert r.sucesso is False
        assert "JID" in r.mensagem

    def test_grupo_sucesso(self, orquestrador):
        m = orquestrador
        m["grupo"].buscar_por_nome.return_value = {"jid": "123@g.us"}
        m["template"].renderizar_por_tipo.return_value = {"mensagem": "oi"}
        m["whatsapp"].enviar_multiplos_arquivos.return_value = {
            "sucesso": True, "parcial": False, "mensagem": "ok"
        }
        r = m["orq"]._enviar_whatsapp_grupo("Admin", ["x.pdf"], {})
        assert r.sucesso is True
        # is_grupo true, destinatario é o jid
        kwargs = m["whatsapp"].enviar_multiplos_arquivos.call_args[1]
        assert kwargs["is_grupo"] is True
        assert kwargs["destinatario"] == "123@g.us"

    def test_grupo_falha(self, orquestrador):
        m = orquestrador
        m["grupo"].buscar_por_nome.return_value = {"jid": "123@g.us"}
        m["whatsapp"].enviar_multiplos_arquivos.return_value = {
            "sucesso": False, "parcial": False, "mensagem": "erro"
        }
        r = m["orq"]._enviar_whatsapp_grupo("Admin", ["x.pdf"], {})
        assert r.sucesso is False


# ==================== enviar_via_planilha ====================

def make_pl_contato(**kwargs):
    c = {
        "nome": "João",
        "empresa": "MS",
        "local": "DSEI",
        "mes_referencia": 1,
        "ano_referencia": 2025,
        "emails": ["a@b.com"],
        "telefones": ["96999"],
        "grupos_whatsapp": ["Admin"],
        "arquivos_pdf": ["/tmp/h.pdf"],
        "enviar_email": True,
        "enviar_whatsapp": True,
        "enviar_grupo_whatsapp": True,
    }
    c.update(kwargs)
    return c


class TestEnviarViaPlanilha:
    def test_planilha_nao_carrega(self, orquestrador):
        m = orquestrador
        m["planilha"].carregar.return_value = False
        rel = m["orq"].enviar_via_planilha(1, 2025)
        assert rel.total_holerites == 0
        assert rel.erros

    def test_simulacao(self, orquestrador):
        m = orquestrador
        m["planilha"].carregar.return_value = True
        m["planilha"].iterar_contatos.return_value = iter([make_pl_contato()])
        rel = m["orq"].enviar_via_planilha(1, 2025, apenas_simular=True)
        assert rel.total_holerites == 1
        assert rel.total_envios == 0  # simulação não conta envios reais
        m["zoho"].enviar_email.assert_not_called()

    def test_contato_sem_pdf(self, orquestrador):
        m = orquestrador
        m["planilha"].carregar.return_value = True
        m["planilha"].iterar_contatos.return_value = iter(
            [make_pl_contato(arquivos_pdf=[])]
        )
        rel = m["orq"].enviar_via_planilha(1, 2025)
        assert rel.total_holerites == 1
        assert rel.total_envios == 0

    def test_happy_path(self, orquestrador):
        m = orquestrador
        m["planilha"].carregar.return_value = True
        m["planilha"].iterar_contatos.return_value = iter([make_pl_contato()])
        m["template"].renderizar_por_tipo.return_value = {
            "assunto": "Recibo", "mensagem": "oi"
        }
        m["zoho"].enviar_email.return_value = {"sucesso": True, "mensagem": "ok", "detalhes": {}}
        m["whatsapp"].enviar_multiplos_arquivos.return_value = {
            "sucesso": True, "parcial": False, "mensagem": "ok"
        }
        m["grupo"].buscar_por_nome.return_value = {"jid": "123@g.us"}

        rel = m["orq"].enviar_via_planilha(1, 2025)
        assert rel.total_holerites == 1
        assert rel.total_envios == 3  # email + whatsapp + grupo
        assert rel.enviados_sucesso == 3

    def test_envios_com_erro(self, orquestrador):
        m = orquestrador
        m["planilha"].carregar.return_value = True
        m["planilha"].iterar_contatos.return_value = iter([make_pl_contato()])
        m["template"].renderizar_por_tipo.return_value = {"assunto": "R", "mensagem": "oi"}
        m["zoho"].enviar_email.return_value = {"sucesso": False, "mensagem": "erro email", "detalhes": {}}
        m["whatsapp"].enviar_multiplos_arquivos.return_value = {
            "sucesso": False, "parcial": False, "mensagem": "erro"
        }
        m["grupo"].buscar_por_nome.return_value = {"jid": "123@g.us"}

        rel = m["orq"].enviar_via_planilha(1, 2025)
        assert rel.enviados_erro == 3
        assert len(rel.erros) == 3

    def test_sem_canais_ativos(self, orquestrador):
        m = orquestrador
        m["planilha"].carregar.return_value = True
        m["planilha"].iterar_contatos.return_value = iter([
            make_pl_contato(enviar_email=False, enviar_whatsapp=False, enviar_grupo_whatsapp=False)
        ])
        rel = m["orq"].enviar_via_planilha(1, 2025)
        assert rel.total_holerites == 1
        assert rel.total_envios == 0


# ==================== enviar_via_mongodb ====================

def make_holerite(arquivo, funcionario_id="f1", **kwargs):
    h = {
        "_id": "h123",
        "funcionario_id": funcionario_id,
        "funcionario_nome": "João",
        "empresa_nome": "MS",
        "contrato_nome": "DSEI",
        "arquivo": {"caminho": arquivo},
    }
    h.update(kwargs)
    return h


class TestEnviarViaMongoDB:
    def test_sem_pendentes(self, orquestrador):
        m = orquestrador
        m["holerite"].listar_pendentes_envio.return_value = []
        rel = m["orq"].enviar_via_mongodb("01/2025")
        assert rel.total_holerites == 0

    def test_arquivo_nao_encontrado(self, orquestrador):
        m = orquestrador
        m["holerite"].listar_pendentes_envio.return_value = [
            make_holerite("/tmp/nao_existe.pdf")
        ]
        rel = m["orq"].enviar_via_mongodb("01/2025")
        assert rel.total_holerites == 1
        assert len(rel.erros) == 1
        assert "Arquivo não encontrado" in rel.erros[0]["erro"]

    def test_happy_path_ambos_canais(self, orquestrador):
        m = orquestrador
        m["holerite"].listar_pendentes_envio.return_value = [
            make_holerite(orquestrador["pdf"])
        ]
        m["contato"].obter_contatos_batch.return_value = {
            "f1": {"email": "a@b.com", "whatsapp": "96999"}
        }
        m["template"].renderizar_por_tipo.return_value = {
            "assunto": "R", "mensagem": "oi"
        }
        m["zoho"].enviar_email.return_value = {"sucesso": True, "mensagem": "ok", "detalhes": {}}
        m["whatsapp"].enviar_multiplos_arquivos.return_value = {
            "sucesso": True, "parcial": False, "mensagem": "ok"
        }

        rel = m["orq"].enviar_via_mongodb("01/2025")
        assert rel.total_holerites == 1
        assert rel.total_envios == 2
        assert rel.enviados_sucesso == 2
        # registrar_envio chamado para ambos os canais
        assert m["holerite"].registrar_envio.call_count == 2

    def test_simulacao(self, orquestrador):
        m = orquestrador
        m["holerite"].listar_pendentes_envio.return_value = [
            make_holerite(orquestrador["pdf"])
        ]
        m["contato"].obter_contatos_batch.return_value = {
            "f1": {"email": "a@b.com", "whatsapp": "96999"}
        }
        rel = m["orq"].enviar_via_mongodb("01/2025", apenas_simular=True)
        assert rel.total_holerites == 1
        assert rel.total_envios == 0
        m["holerite"].registrar_envio.assert_not_called()

    def test_sem_contatos_cadastrados(self, orquestrador):
        m = orquestrador
        m["holerite"].listar_pendentes_envio.return_value = [
            make_holerite(orquestrador["pdf"])
        ]
        m["contato"].obter_contatos_batch.return_value = {}  # sem contatos
        rel = m["orq"].enviar_via_mongodb("01/2025")
        assert rel.total_holerites == 1
        assert rel.total_envios == 0  # sem email/whatsapp cadastrado

    def test_erro_registrar_envio(self, orquestrador):
        m = orquestrador
        m["holerite"].listar_pendentes_envio.return_value = [
            make_holerite(orquestrador["pdf"])
        ]
        m["contato"].obter_contatos_batch.return_value = {
            "f1": {"email": "a@b.com", "whatsapp": "96999"}
        }
        m["template"].renderizar_por_tipo.return_value = {"assunto": "R", "mensagem": "oi"}
        m["zoho"].enviar_email.return_value = {"sucesso": False, "mensagem": "erro", "detalhes": {}}
        m["whatsapp"].enviar_multiplos_arquivos.return_value = {
            "sucesso": False, "parcial": False, "mensagem": "erro"
        }
        rel = m["orq"].enviar_via_mongodb("01/2025")
        assert rel.enviados_erro == 2
        assert len(rel.erros) == 2

    def test_erro_busca_contatos_batch(self, orquestrador):
        m = orquestrador
        m["holerite"].listar_pendentes_envio.return_value = [
            make_holerite(orquestrador["pdf"])
        ]
        m["contato"].obter_contatos_batch.side_effect = Exception("boom")
        m["template"].renderizar_por_tipo.return_value = {"mensagem": "oi"}
        m["whatsapp"].enviar_multiplos_arquivos.return_value = {
            "sucesso": True, "parcial": False, "mensagem": "ok"
        }
        # sem contatos (map vazio) -> sem envios
        rel = m["orq"].enviar_via_mongodb("01/2025")
        assert rel.total_holerites == 1


# ==================== obter_estatisticas_competencia ====================

class TestEstatisticas:
    def test_estatisticas(self, orquestrador):
        m = orquestrador
        m["holerite"].contar_por_status.return_value = {
            "pendente": 2, "enviado": 5, "erro": 1
        }
        stats = m["orq"].obter_estatisticas_competencia("01/2025")
        assert stats["competencia"] == "01/2025"
        assert stats["total"] == 8
        assert stats["pendentes"] == 2
        assert stats["enviados"] == 5
        assert stats["erros"] == 1
