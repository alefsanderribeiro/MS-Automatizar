"""
Unit tests for PlanilhaHoleritesService

Covers:
- Init / disponivel / planilha_path
- _obter_caminho_padrao
- carregar (pandas mock: sucesso, colunas faltando, arquivo não existe, pandas indisponível, exceção)
- _valor_booleano / _parsear_lista
- montar_diretorio_completo
- listar_arquivos_pdf (real dirs)
- iterar_contatos (linha válida, sem canal ativo, mês/ano da coluna, mês/ano por parâmetro, erro na linha)
- obter_contato_por_id
- listar_resumo
- validar_planilha
- contar_envios_pendentes
- contar_pdfs_total
- Singleton
"""

import pytest
from unittest.mock import MagicMock, patch
import os

from src.services.planilha_holerites_service import (
    PlanilhaHoleritesService,
    planilha_holerites_service,
    TipoEnvioHolerite,
)


def make_row(**kwargs):
    """Factory de linha (dict) com todas as colunas.

    Aceita as chaves com underscore (ex: NOME_COMPLETO, ENVIAR_EMAIL) e
    traduz para as chaves reais da planilha ("NOME COMPLETO", "ENVIAR EMAIL"),
    já que o service lê as colunas com espaços/acentos.
    """
    row = {
        "ID": "1",
        "NOME COMPLETO": "João Silva",
        "EMAIL": "a@b.com",
        "TELEFONE": "(96) 99999-9999",
        "GRUPO WHATSAPP": "Admin",
        "ENVIAR EMAIL": "S",
        "ENVIAR WHATSAPP": "S",
        "ENVIAR GRUPO WHATSAPP": "N",
        "EMPRESA": "MS",
        "MÊS REFERÊNCIA": "1",
        "ANO REFERÊNCIA": "2025",
        "DIRETÓRIO GERAL": "/tmp/holerites",
        "DIRETÓRIO ESPECÍFICO": "",
        "LOCAL - CONTRATO - POLO": "DSEI",
    }
    for chave, valor in kwargs.items():
        # Normaliza chave com underscore para a coluna real (espaços/acentos).
        coluna = chave.replace("_", " ")
        if coluna in row:
            row[coluna] = valor
        else:
            row[chave] = valor
    return row


def make_df(*rows):
    """Cria um DataFrame-like (dict) que nos testes funciona como pandas."""
    return type("FakeDF", (), {"iterrows": lambda self: iter(list(enumerate(rows)))})()


def make_len_df(*rows):
    """Cria um DataFrame-like com suporte a len() (usado por validar_planilha)."""
    def iterrows(self):
        return iter(list(enumerate(rows)))

    def __len__(self):
        return len(rows)

    return type("FakeLenDF", (), {"iterrows": iterrows, "__len__": __len__})()


@pytest.fixture
def service():
    return PlanilhaHoleritesService.__new__(PlanilhaHoleritesService)


# ==================== Inicialização ====================

class TestInicializacao:
    def test_singleton(self):
        assert isinstance(planilha_holerites_service, PlanilhaHoleritesService)

    def test_init_default_path(self, mocker):
        mocker.patch("dotenv.get_key", return_value=None)
        service = PlanilhaHoleritesService()
        assert "planilha_holerites.xlsx" in service.planilha_path

    def test_init_path_explicito(self):
        service = PlanilhaHoleritesService("/tmp/x.xlsx")
        assert service.planilha_path == "/tmp/x.xlsx"

    def test_propriedade_disponivel_quando_pandas(self, service):
        with patch("src.services.planilha_holerites_service.PANDAS_DISPONIVEL", True):
            service._disponivel = True
            assert service.disponivel is True

    def test_obter_caminho_padrao_env(self, mocker, monkeypatch):
        monkeypatch.setenv("PLANILHA_HOLERITES_PATH", "/tmp/custom.xlsx")
        mocker.patch("os.getenv", return_value="/tmp/custom.xlsx")
        s = PlanilhaHoleritesService.__new__(PlanilhaHoleritesService)
        assert s._obter_caminho_padrao() == "/tmp/custom.xlsx"


# ==================== carregar ====================

class TestCarregar:
    def test_pandas_indisponivel(self, service, mocker):
        mocker.patch("os.path.exists", return_value=True)
        with patch("src.services.planilha_holerites_service.PANDAS_DISPONIVEL", False):
            service._disponivel = False
            assert service.carregar() is False

    def test_arquivo_nao_existe(self, service, mocker):
        service._planilha_path = "/tmp/nao_existe_xyz.xlsx"
        mocker.patch("os.path.exists", return_value=False)
        service._disponivel = True
        assert service.carregar() is False

    def test_carregar_sucesso(self, service, mocker):
        service._planilha_path = "/tmp/existe.xlsx"
        mocker.patch("os.path.exists", return_value=True)
        import pandas as pd
        df_real = pd.DataFrame([{
            "ID": "1", "NOME COMPLETO": "João", "EMAIL": "a@b.com",
            "TELEFONE": "96999999999", "GRUPO WHATSAPP": "Admin",
            "ENVIAR EMAIL": "S", "ENVIAR WHATSAPP": "S",
            "ENVIAR GRUPO WHATSAPP": "N", "EMPRESA": "MS",
            "MÊS REFERÊNCIA": "1", "ANO REFERÊNCIA": "2025",
            "DIRETÓRIO GERAL": "/tmp/holerites", "DIRETÓRIO ESPECÍFICO": "",
            "LOCAL - CONTRATO - POLO": "DSEI",
        }])
        mocker.patch("src.services.planilha_holerites_service.pd.read_excel",
                     return_value=df_real.copy())
        service._disponivel = True
        assert service.carregar() is True
        assert service._df is not None

    def test_carregar_colunas_faltando(self, service, mocker):
        mocker.patch("os.path.exists", return_value=True)
        import pandas as pd
        df_real = pd.DataFrame([{"ID": "1", "NOME COMPLETO": "João"}])
        mocker.patch("src.services.planilha_holerites_service.pd.read_excel",
                     return_value=df_real)
        service._disponivel = True
        service._planilha_path = "/tmp/existe.xlsx"
        assert service.carregar() is False

    def test_carregar_excecao(self, service, mocker):
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("src.services.planilha_holerites_service.pd.read_excel",
                     side_effect=Exception("boom"))
        service._disponivel = True
        service._planilha_path = "/tmp/existe.xlsx"
        assert service.carregar() is False


# ==================== Helpers ====================

class TestHelpers:
    def test_valor_booleano(self, service):
        assert service._valor_booleano("S") is True
        assert service._valor_booleano("x") is True
        assert service._valor_booleano("N") is False
        assert service._valor_booleano(None) is False
        assert service._valor_booleano(20) is False

    def test_parsear_lista_por_ponto_virgula(self, service):
        assert service._parsear_lista("a; b;c") == ["a", "b", "c"]

    def test_parsear_lista_por_virgula(self, service):
        assert service._parsear_lista("a, b") == ["a", "b"]

    def test_parsear_lista_vazia(self, service):
        assert service._parsear_lista("") == []
        assert service._parsear_lista(None) == []
        assert service._parsear_lista("  ") == []


# ==================== montar_diretorio_completo ====================

class TestMontarDiretorio:
    def test_com_mes_ano(self):
        s = PlanilhaHoleritesService.__new__(PlanilhaHoleritesService)
        cam = s.montar_diretorio_completo("/base", "espec", 1, 2025)
        assert os.path.join("01.2025", "espec") in cam.replace("\\", "/").replace("/base/", "")

    def test_sem_mes_ano(self):
        s = PlanilhaHoleritesService.__new__(PlanilhaHoleritesService)
        cam = s.montar_diretorio_completo("/base", "espec")
        assert cam == os.path.join("/base", "espec")

    def test_sem_especifico(self):
        s = PlanilhaHoleritesService.__new__(PlanilhaHoleritesService)
        cam = s.montar_diretorio_completo("/base", mes=12, ano=2025)
        assert cam == os.path.join("/base", "2025", "12.2025")

    def test_soma_numeric(self):
        s = PlanilhaHoleritesService.__new__(PlanilhaHoleritesService)
        cam = s.montar_diretorio_completo("/base", mes=7, ano=2025)
        assert cam == os.path.join("/base", "2025", "07.2025")


# ==================== listar_arquivos_pdf ====================

class TestListarArquivosPdf:
    def test_diretorio_nao_existe(self, service):
        assert service.listar_arquivos_pdf("/tmp/nao_existe_dir_xyz") == []

    def test_lista_pdfs_recursivo(self, service, tmp_path):
        (tmp_path / "Recibo de Pagamento - João.pdf").write_bytes(b"%PDF")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "Recibo de Pagamento - Maria.pdf").write_bytes(b"%PDF")
        (sub / "outro.pdf").write_bytes(b"%PDF")  # prefixo diferente -> ignorado

        arquivos = service.listar_arquivos_pdf(str(tmp_path))
        assert len(arquivos) == 2
        assert all(f.endswith(".pdf") for f in arquivos)
        assert all("Recibo de Pagamento" in os.path.basename(f) for f in arquivos)

    def test_prefixo_personalizado(self, service, tmp_path):
        (tmp_path / "Holerite - João.pdf").write_bytes(b"%PDF")
        arquivos = service.listar_arquivos_pdf(str(tmp_path), prefixo="Holerite")
        assert len(arquivos) == 1

    def test_sem_arquivos(self, service, tmp_path):
        arquivos = service.listar_arquivos_pdf(str(tmp_path))
        assert arquivos == []

    def test_excecao_rglob(self, service, mocker):
        mocker.patch("pathlib.Path.exists", return_value=True)
        mocker.patch("pathlib.Path.rglob", side_effect=Exception("boom"))
        assert service.listar_arquivos_pdf("/tmp/x") == []


# ==================== iterar_contatos ====================

class TestIterarContatos:
    def test_df_none_chama_carregar_falha(self, service, mocker):
        service._df = None
        mocker.patch.object(service, "carregar", return_value=False)
        assert list(service.iterar_contatos()) == []

    def test_linha_sem_canal_ativo(self, service):
        service._df = [None]
        service._df = MagicMock()

        class FakeDF:
            rows = [make_row(ENVIAR_EMAIL="N", ENVIAR_WHATSAPP="N", ENVIAR_GRUPO_WHATSAPP="N")]

            def __init__(self, rows=None, default=None):
                self._rows = rows or default

            def iterrows(self):
                for i, r in enumerate(self._rows):
                    yield i, r

        fdf = FakeDF([make_row(ENVIAR_EMAIL="N", ENVIAR_WHATSAPP="N", ENVIAR_GRUPO_WHATSAPP="N")])
        service._df = fdf
        assert list(service.iterar_contatos()) == []

    def test_linha_valida(self, service, tmp_path):
        # Com mês/ano 1/2025 o diretório real é {tmp}/2025/01.2025
        diretorio = tmp_path / "2025" / "01.2025"
        diretorio.mkdir(parents=True)
        (diretorio / "Recibo de Pagamento - João.pdf").write_bytes(b"%PDF")
        row = make_row(DIRETÓRIO_GERAL=str(tmp_path), DIRETÓRIO_ESPECÍFICO="")
        fdf = type("FDF", (), {"iterrows": lambda self: iter([(0, row)])})()
        service._df = fdf
        contatos = list(service.iterar_contatos(1, 2025))
        assert len(contatos) == 1
        c = contatos[0]
        assert c["nome"] == "João Silva"
        assert c["emails"] == ["a@b.com"]
        assert c["enviar_email"] is True
        assert c["tipo_envio"] == TipoEnvioHolerite.PLANILHA.value
        assert len(c["arquivos_pdf"]) == 1

    def test_mes_ano_da_coluna(self, service, tmp_path):
        (tmp_path / "Recibo de Pagamento - João.pdf").write_bytes(b"%PDF")
        row = make_row(DIRETÓRIO_GERAL=str(tmp_path), MÊS_REFERÊNCIA="5", ANO_REFERÊNCIA="2024")
        fdf = type("FDF", (), {"iterrows": lambda self: iter([(0, row)])})()
        service._df = fdf
        contatos = list(service.iterar_contatos())  # sem param -> usa coluna
        assert contatos[0]["mes_referencia"] == 5
        assert contatos[0]["ano_referencia"] == 2024

    def test_mes_ano_invalidos_coluna(self, service, tmp_path):
        (tmp_path / "Recibo de Pagamento - João.pdf").write_bytes(b"%PDF")
        row = make_row(DIRETÓRIO_GERAL=str(tmp_path), MÊS_REFERÊNCIA="abc", ANO_REFERÊNCIA="xyz")
        fdf = type("FDF", (), {"iterrows": lambda self: iter([(0, row)])})()
        service._df = fdf
        contatos = list(service.iterar_contatos())
        assert contatos[0]["mes_referencia"] is None
        assert contatos[0]["ano_referencia"] is None

    def test_erro_na_linha(self, service):
        # Linha que levanta exceção deve ser pulada
        class RowRaises(dict):
            def get(self, key, default=None):
                raise Exception("boom")

        fdf = type("FDF", (), {"iterrows": lambda self: iter([(0, RowRaises())])})()
        service._df = fdf
        assert list(service.iterar_contatos(1, 2025)) == []


# ==================== obter_contato_por_id ====================

class TestObterContatoPorId:
    def test_encontra(self, service):
        contato = make_row(ID="42", NOME_COMPLETO="Maria")
        fdf = type("FDF", (), {"iterrows": lambda self: iter([(0, contato)])})()
        service._df = fdf
        c = service.obter_contato_por_id("42")
        assert c is not None
        assert c["nome"] == "Maria"

    def test_nao_encontra(self, service):
        contato = make_row(ID="42")
        fdf = type("FDF", (), {"iterrows": lambda self: iter([(0, contato)])})()
        service._df = fdf
        assert service.obter_contato_por_id("999") is None


# ==================== listar_resumo / validar / contar ====================

class TestResumoValidacaoContagem:
    def test_listar_resumo(self, service):
        row = make_row(NOME_COMPLETO="Maria")
        fdf = type("FDF", (), {"iterrows": lambda self: iter([(0, row)])})()
        service._df = fdf
        resumo = service.listar_resumo()
        assert len(resumo) == 1
        assert resumo[0]["nome"] == "Maria"
        assert resumo[0]["enviar_email"] == "✓"

    def test_listar_resumo_df_none(self, service, mocker):
        service._df = None
        mocker.patch.object(service, "carregar", return_value=False)
        assert service.listar_resumo() == []

    def test_validar_planilha_ok(self, service):
        row = make_row()  # tudo preenchido
        service._df = make_len_df(row)
        res = service.validar_planilha()
        assert res["valida"] is True
        assert res["problemas"] == []

    def test_validar_planilha_problemas(self, service):
        # Ativa grupo também para validar a checagem de GRUPO WHATSAPP
        row = make_row(EMAIL="", TELEFONE="", GRUPO_WHATSAPP="",
                       ENVIAR_GRUPO_WHATSAPP="S")
        service._df = make_len_df(row)
        res = service.validar_planilha()
        assert res["valida"] is False
        assert any("EMAIL" in p for p in res["problemas"])
        assert any("TELEFONE" in p for p in res["problemas"])
        assert any("GRUPO WHATSAPP" in p for p in res["problemas"])

    def test_validar_planilha_sem_diretorio(self, service):
        row = make_row(DIRETÓRIO_GERAL="")
        service._df = make_len_df(row)
        res = service.validar_planilha()
        assert res["valida"] is False
        assert any("DIRETÓRIO GERAL" in p for p in res["problemas"])

    def test_validar_planilha_df_none(self, service, mocker):
        service._df = None
        mocker.patch.object(service, "carregar", return_value=False)
        res = service.validar_planilha()
        assert res["valida"] is False

    def test_contar_envios_pendentes(self, service):
        rows = [make_row(ENVIAR_EMAIL="S", ENVIAR_WHATSAPP="S", ENVIAR_GRUPO_WHATSAPP="N"),
                make_row(ENVIAR_EMAIL="N", ENVIAR_WHATSAPP="S", ENVIAR_GRUPO_WHATSAPP="S")]
        fdf = type("FDF", (), {"iterrows": lambda self: list(enumerate(rows)).__iter__()})()
        service._df = fdf
        contagem = service.contar_envios_pendentes()
        assert contagem == {"email": 1, "whatsapp": 2, "grupo_whatsapp": 1}

    def test_contar_envios_pdf_df_none(self, service, mocker):
        service._df = None
        mocker.patch.object(service, "carregar", return_value=False)
        assert service.contar_envios_pendentes() == {}

    def test_contar_pdfs_total(self, service, tmp_path):
        diretorio = tmp_path / "2025" / "01.2025"
        diretorio.mkdir(parents=True)
        (diretorio / "Recibo de Pagamento - A.pdf").write_bytes(b"%PDF")
        (diretorio / "Recibo de Pagamento - B.pdf").write_bytes(b"%PDF")
        row = make_row(DIRETÓRIO_GERAL=str(tmp_path))
        fdf = type("FDF", (), {"iterrows": lambda self: iter([(0, row)])})()
        service._df = fdf
        assert service.contar_pdfs_total(1, 2025) == 2
