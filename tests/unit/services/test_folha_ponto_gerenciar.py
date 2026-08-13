"""
Unit tests for Fase 1 do upgrade de Folha de Ponto: Gerenciar Folhas Geradas.

Cobre as operações aprovadas pelo Alef:
- Visualizar (buscar_por_id)
- Buscar por NOME do funcionário (+ período/status)
- Excluir (SOFT DELETE: marca excluida=True, nunca remove do banco,
  preserva histórico/envios)
- Editar (recalcula totais, regenera PDF, incrementa versao, adiciona historico)

Também cobre o recalculador compartilhado `recalcular_totais_folha` e o
fluxo `Folha_de_Ponto.editar_folha`.
"""

import pytest
from unittest.mock import MagicMock, patch
from bson import ObjectId
from datetime import datetime, date, timezone
from typing import Dict, Any, List

from src.services.folha_ponto_service import FolhaDePontoService
from src.processadores.processador_folha_ponto import (
    recalcular_totais_folha,
    calcular_total_horas,
)


# ==================== Constantes ====================

SAMPLE_OBJECT_ID = ObjectId("507f1f77bcf86cd799439011")
SAMPLE_OBJECT_ID_2 = ObjectId("507f1f77bcf86cd799439012")
SAMPLE_FOLHA_ID = ObjectId("507f1f77bcf86cd799439013")


# ==================== Helpers ====================

def create_mock_cursor(results: List[Dict[str, Any]]):
    """Create a mock MongoDB cursor with chainable methods."""
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.__iter__ = MagicMock(return_value=iter(results))
    cursor.__list__ = results
    return cursor


def criar_folha_doc(
    funcionario_id=None,
    empresa_id=None,
    mes_referencia: str = "2025-01",
    status: str = "preenchida",
    nome_funcionario: str = "João Silva",
    excluida: bool = False,
    versao: int = 1,
    **kwargs,
) -> Dict[str, Any]:
    """Factory para documentos de folha de ponto."""
    import unicodedata
    nfkd = unicodedata.normalize('NFKD', nome_funcionario)
    nome_normalizado = ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()

    doc = {
        "_id": SAMPLE_FOLHA_ID,
        "funcionario_id": funcionario_id or SAMPLE_OBJECT_ID,
        "empresa_id": empresa_id or SAMPLE_OBJECT_ID_2,
        "mes_referencia": mes_referencia,
        "lotacao": "TI",
        "funcao": "Analista",
        "status": status,
        "data_criacao": datetime.now(timezone.utc),
        "data_atualizacao": datetime.now(timezone.utc),
        "folha_data": {
            "mes_referencia": mes_referencia,
            "data_inicio": date(2025, 1, 1),
            "data_fim": date(2025, 1, 31),
            "nome_funcionario": nome_funcionario,
            "nome_normalizado": nome_normalizado,
            "total_horas_mes": "160:00",
            "total_faltas": 0,
            "total_feriados": 0,
            "total_finais_semana": 8,
            "dias": [],
        },
        "caminho_arquivo_gerado": f"/tmp/folhas/{nome_funcionario}.pdf",
        "versao": versao,
        "historico_alteracoes": [],
        "excluida": excluida,
        "data_exclusao": None,
        "motivo_exclusao": None,
    }
    doc.update(kwargs)
    return doc


# ==================== Fixtures ====================

@pytest.fixture
def mock_colecao():
    """Mock MongoDB collection with all operations."""
    colecao = MagicMock()
    colecao.find_one = MagicMock(return_value=None)
    colecao.find = MagicMock(return_value=create_mock_cursor([]))
    colecao.insert_one = MagicMock(return_value=MagicMock(inserted_id=ObjectId()))
    colecao.update_one = MagicMock(return_value=MagicMock(modified_count=1, matched_count=1))
    colecao.replace_one = MagicMock(return_value=MagicMock(modified_count=1))
    colecao.delete_one = MagicMock(return_value=MagicMock(deleted_count=1))
    colecao.aggregate = MagicMock(return_value=iter([]))
    colecao.count_documents = MagicMock(return_value=0)
    colecao.create_index = MagicMock()
    colecao.drop_index = MagicMock()
    return colecao


@pytest.fixture
def mock_db(mock_colecao):
    """Mock MongoDB database que resolve coleções por nome."""
    collections = {
        "funcionarios": MagicMock(),
        "funcoes": MagicMock(),
        "envios_folhas_de_ponto": MagicMock(),
    }
    db = MagicMock()

    def _getitem(nome):
        if nome == "folha_de_ponto":
            return mock_colecao
        return collections.get(nome, mock_colecao)

    db.__getitem__.side_effect = _getitem
    db._collections = collections
    return db


@pytest.fixture
def servico_folha(mock_db, mock_colecao):
    """Cria FolhaDePontoService sem rodar o __init__ (coleção mockada)."""
    # O serviço acessa o banco via self.colecao.database
    mock_colecao.database = mock_db
    service = FolhaDePontoService.__new__(FolhaDePontoService)
    service.db = mock_db
    service.colecao = mock_colecao
    service._disponivel = True
    return service


# ==================== Visualizar: buscar_por_id ====================

@pytest.mark.unit
class TestBuscarPorId:
    """buscar_por_id — visualizar uma folha pelo ObjectId."""

    def test_buscar_por_id_encontrada(self, servico_folha, mock_colecao):
        folha = criar_folha_doc()
        mock_colecao.find_one.return_value = folha

        resultado = servico_folha.buscar_por_id(str(SAMPLE_FOLHA_ID))

        assert resultado is not None
        assert resultado["_id"] == SAMPLE_FOLHA_ID
        mock_colecao.find_one.assert_called_once_with({"_id": SAMPLE_FOLHA_ID})

    def test_buscar_por_id_nao_encontrada(self, servico_folha, mock_colecao):
        mock_colecao.find_one.return_value = None

        resultado = servico_folha.buscar_por_id(str(SAMPLE_FOLHA_ID))

        assert resultado is None

    def test_buscar_por_id_indisponivel(self, servico_folha):
        servico_folha._disponivel = False

        resultado = servico_folha.buscar_por_id(str(SAMPLE_FOLHA_ID))

        assert resultado is None

    def test_buscar_por_id_id_invalido(self, servico_folha):
        """ObjectId inválido não deve estourar exceção."""
        resultado = servico_folha.buscar_por_id("id-invalido-###")

        assert resultado is None


# ==================== Buscar por NOME do funcionário ====================

@pytest.mark.unit
class TestBuscarPorNomeFuncionario:
    """buscar_por_nome_funcionario — busca por NOME (+ mês/status)."""

    def test_busca_por_nome_retorna_lista(self, servico_folha, mock_colecao, mock_db):
        folhas = [criar_folha_doc(nome_funcionario="João Silva")]
        mock_colecao.find.return_value = create_mock_cursor(folhas)

        # Resolução nome -> funcionario_id retorna vazio
        col_funcionarios = mock_db._collections["funcionarios"]
        col_funcionarios.find.return_value = create_mock_cursor([])

        resultado = servico_folha.buscar_por_nome_funcionario(nome="João")

        assert len(resultado) == 1
        assert resultado[0]["folha_data"]["nome_funcionario"] == "João Silva"

        # O filtro deve conter busca por nome_normalizado (regex) — compatível com acentos
        filtro = mock_colecao.find.call_args[0][0]
        assert "$or" in filtro
        or_clauses = filtro["$or"]
        assert any("folha_data.nome_normalizado" in c for c in or_clauses)
        assert "excluida" in filtro
        assert filtro["excluida"] == {"$ne": True}

    def test_busca_por_nome_resolve_ids_funcionarios(
        self, servico_folha, mock_colecao, mock_db
    ):
        """Busca também resolve nome -> ObjectIds na coleção de funcionários."""
        folhas = [criar_folha_doc(nome_funcionario="Maria Santos")]
        mock_colecao.find.return_value = create_mock_cursor(folhas)

        col_funcionarios = mock_db._collections["funcionarios"]
        col_funcionarios.find.return_value = create_mock_cursor(
            [{"_id": SAMPLE_OBJECT_ID}]
        )

        resultado = servico_folha.buscar_por_nome_funcionario(nome="Maria")

        assert len(resultado) == 1
        filtro = mock_colecao.find.call_args[0][0]
        or_clauses = filtro["$or"]
        assert any("funcionario_id" in c for c in or_clauses)

    def test_busca_por_nome_com_mes_e_status(
        self, servico_folha, mock_colecao, mock_db
    ):
        folhas = [criar_folha_doc(mes_referencia="2025-01", status="preenchida")]
        mock_colecao.find.return_value = create_mock_cursor(folhas)
        col_funcionarios = mock_db._collections["funcionarios"]
        col_funcionarios.find.return_value = create_mock_cursor([])

        resultado = servico_folha.buscar_por_nome_funcionario(
            nome="João",
            mes_referencia="2025-01",
            status="preenchida",
        )

        assert len(resultado) == 1
        filtro = mock_colecao.find.call_args[0][0]
        assert filtro["mes_referencia"] == "2025-01"
        assert filtro["status"] == "preenchida"

    def test_busca_inclui_excluidas(self, servico_folha, mock_colecao, mock_db):
        folhas = [criar_folha_doc(excluida=True)]
        mock_colecao.find.return_value = create_mock_cursor(folhas)
        col_funcionarios = mock_db._collections["funcionarios"]
        col_funcionarios.find.return_value = create_mock_cursor([])

        servico_folha.buscar_por_nome_funcionario(nome="João", incluir_excluidas=True)

        filtro = mock_colecao.find.call_args[0][0]
        assert "excluida" not in filtro

    def test_busca_nome_vazio(self, servico_folha, mock_colecao):
        resultado = servico_folha.buscar_por_nome_funcionario(nome="   ")

        assert resultado == []
        mock_colecao.find.assert_not_called()

    def test_busca_indisponivel(self, servico_folha):
        servico_folha._disponivel = False

        resultado = servico_folha.buscar_por_nome_funcionario(nome="João")

        assert resultado == []

    def test_busca_por_nome_com_acentos_match_real(self, servico_folha, mock_colecao, mock_db):
        """Confirma que busca por 'joao' encontra 'João' via nome_normalizado."""
        # Folha com nome acentuado gravado no banco
        folhas = [criar_folha_doc(nome_funcionario="João da Silva")]
        mock_colecao.find.return_value = create_mock_cursor(folhas)
        col_funcionarios = mock_db._collections["funcionarios"]
        col_funcionarios.find.return_value = create_mock_cursor([])

        resultado = servico_folha.buscar_por_nome_funcionario(nome="joao")

        assert len(resultado) == 1
        assert resultado[0]["folha_data"]["nome_funcionario"] == "João da Silva"

        # Verificar que o filtro normaliza o termo e busca em nome_normalizado
        filtro = mock_colecao.find.call_args[0][0]
        or_clauses = filtro["$or"]
        nome_norm_clause = [c for c in or_clauses if "folha_data.nome_normalizado" in c][0]
        regex_pattern = nome_norm_clause["folha_data.nome_normalizado"]["$regex"]
        # O termo buscado foi "joao" (normalizado, sem acentos). re.escape("joao") => "joao"
        assert regex_pattern == "joao"

    def test_busca_por_nome_varios_acentos(self, servico_folha, mock_colecao, mock_db):
        """Nomes com acentos variados (José, Sérgio, Ângela) são encontrados."""
        for nome_banco, termo_busca in [
            ("José da Costa", "jose"),
            ("Sérgio Ramos", "sergio"),
            ("Ângela Maria", "angela"),
            ("Ãngela Maria", "angela"),
        ]:
            mock_colecao.reset_mock()
            mock_db._collections["funcionarios"].reset_mock()

            folhas = [criar_folha_doc(nome_funcionario=nome_banco)]
            mock_colecao.find.return_value = create_mock_cursor(folhas)
            mock_db._collections["funcionarios"].find.return_value = create_mock_cursor([])

            resultado = servico_folha.buscar_por_nome_funcionario(nome=termo_busca)
            assert len(resultado) == 1, f"Deveria encontrar '{nome_banco}' com termo '{termo_busca}'"



# ==================== Excluir (SOFT DELETE) ====================

@pytest.mark.unit
class TestSoftDelete:
    """marcar_excluida — soft delete preserva o registro e o envio."""

    def test_soft_delete_marca_flag_e_nao_remove(
        self, servico_folha, mock_colecao, mock_db
    ):
        """Registro PERMANECE no banco com flag excluida=True (nunca delete_one)."""
        folha = criar_folha_doc(versao=2)
        mock_colecao.find_one.return_value = folha
        mock_colecao.update_one.return_value = MagicMock(modified_count=1, matched_count=1)

        resultado = servico_folha.marcar_excluida(str(SAMPLE_FOLHA_ID), motivo="Gerada errada")

        assert resultado is True
        # NUNCA chama delete_one (não remove do banco)
        mock_colecao.delete_one.assert_not_called()

        # update_one com $set: excluida=True + versao incrementada
        args = mock_colecao.update_one.call_args
        filtro = args[0][0]
        update = args[0][1]
        assert filtro == {"_id": SAMPLE_FOLHA_ID}
        assert update["$set"]["excluida"] is True
        assert update["$set"]["motivo_exclusao"] == "Gerada errada"
        assert update["$set"]["versao"] == 3  # 2 -> 3
        assert "data_exclusao" in update["$set"]

    def test_soft_delete_adiciona_historico(
        self, servico_folha, mock_colecao
    ):
        folha = criar_folha_doc(versao=1)
        mock_colecao.find_one.return_value = folha
        mock_colecao.update_one.return_value = MagicMock(modified_count=1, matched_count=1)

        servico_folha.marcar_excluida(str(SAMPLE_FOLHA_ID), motivo="teste")

        update = mock_colecao.update_one.call_args[0][1]
        historico = update["$set"]["historico_alteracoes"]
        assert len(historico) == 1
        assert historico[0]["acao"] == "Folha excluída (soft delete)"
        assert historico[0]["versao_anterior"] == 1
        assert historico[0]["versao_nova"] == 2
        assert historico[0]["detalhes"] == {"motivo": "teste"}

    def test_soft_delete_preserva_envio_registrado(
        self, servico_folha, mock_colecao, mock_db
    ):
        """
        Envio registrado NÃO é perdido: após o soft delete, a folha continua
        no banco (com flag) e verificar_folha_enviada ainda encontra o envio.
        """
        folha = criar_folha_doc(
            caminho_arquivo_gerado="/tmp/folhas/João Silva.pdf",
            mes_referencia="2025-01",
        )
        mock_colecao.find_one.return_value = folha
        mock_colecao.update_one.return_value = MagicMock(modified_count=1, matched_count=1)

        # Envio registrado na coleção de envios
        col_envios = mock_db._collections["envios_folhas_de_ponto"]
        col_envios.find_one.return_value = {
            "_id": ObjectId(),
            "tipo_envio": "email",
            "arquivos_enviados": ["João Silva.pdf"],
            "mes_referencia": 1,
            "ano_referencia": 2025,
        }

        # Soft delete
        resultado = servico_folha.marcar_excluida(str(SAMPLE_FOLHA_ID))
        assert resultado is True

        # Folha continua no banco com flag (não foi removida)
        mock_colecao.delete_one.assert_not_called()

        # O envio registrado continua sendo encontrado
        ainda_enviada = servico_folha.verificar_folha_enviada(str(SAMPLE_FOLHA_ID))
        assert ainda_enviada is True

    def test_soft_delete_ja_excluida(self, servico_folha, mock_colecao):
        folha = criar_folha_doc(excluida=True)
        mock_colecao.find_one.return_value = folha

        resultado = servico_folha.marcar_excluida(str(SAMPLE_FOLHA_ID))

        assert resultado is True
        mock_colecao.update_one.assert_not_called()

    def test_soft_delete_folha_nao_encontrada(self, servico_folha, mock_colecao):
        mock_colecao.find_one.return_value = None

        resultado = servico_folha.marcar_excluida(str(SAMPLE_FOLHA_ID))

        assert resultado is False

    def test_soft_delete_indisponivel(self, servico_folha):
        servico_folha._disponivel = False

        resultado = servico_folha.marcar_excluida(str(SAMPLE_FOLHA_ID))

        assert resultado is False


# ==================== Enviada: verificar_folha_enviada ====================

@pytest.mark.unit
class TestVerificarFolhaEnviada:
    """verificar_folha_enviada — detecta se a folha já foi enviada."""

    def test_enviada_por_arquivo(self, servico_folha, mock_colecao, mock_db):
        folha = criar_folha_doc(caminho_arquivo_gerado="/tmp/folhas/João Silva.pdf")
        mock_colecao.find_one.return_value = folha
        col_envios = mock_db._collections["envios_folhas_de_ponto"]
        col_envios.find_one.return_value = {"_id": ObjectId()}

        resultado = servico_folha.verificar_folha_enviada(str(SAMPLE_FOLHA_ID))

        assert resultado is True
        filtro_envio = col_envios.find_one.call_args[0][0]
        assert "$or" in filtro_envio

    def test_nao_enviada(self, servico_folha, mock_colecao, mock_db):
        folha = criar_folha_doc()
        mock_colecao.find_one.return_value = folha
        col_envios = mock_db._collections["envios_folhas_de_ponto"]
        col_envios.find_one.return_value = None

        resultado = servico_folha.verificar_folha_enviada(str(SAMPLE_FOLHA_ID))

        assert resultado is False

    def test_folha_nao_existe(self, servico_folha, mock_colecao):
        mock_colecao.find_one.return_value = None

        resultado = servico_folha.verificar_folha_enviada(str(SAMPLE_FOLHA_ID))

        assert resultado is False


# ==================== Editar: atualizar_folha (versão + histórico) ====================

@pytest.mark.unit
class TestAtualizarFolha:
    """atualizar_folha — salva edição com versão incrementada e histórico."""

    def test_atualizar_incrementa_versao_e_historico(
        self, servico_folha, mock_colecao
    ):
        folha = criar_folha_doc(versao=4, historico_alteracoes=[])
        mock_colecao.find_one.return_value = folha
        mock_colecao.update_one.return_value = MagicMock(modified_count=1, matched_count=1)

        resultado = servico_folha.atualizar_folha(
            str(SAMPLE_FOLHA_ID),
            {"folha_data": {"total_horas_mes": "170:00"}},
            acao="Folha editada manualmente",
            detalhes_historico={"dias_alterados": [1]},
        )

        assert resultado is True
        update = mock_colecao.update_one.call_args[0][1]
        assert update["$set"]["versao"] == 5  # 4 -> 5
        assert update["$set"]["folha_data"] == {"total_horas_mes": "170:00"}
        historico = update["$set"]["historico_alteracoes"]
        assert len(historico) == 1
        assert historico[0]["acao"] == "Folha editada manualmente"
        assert historico[0]["versao_anterior"] == 4
        assert historico[0]["versao_nova"] == 5

    def test_atualizar_nao_encontrada(self, servico_folha, mock_colecao):
        mock_colecao.find_one.return_value = None

        resultado = servico_folha.atualizar_folha(
            str(SAMPLE_FOLHA_ID), {"folha_data": {}}
        )

        assert resultado is False

    def test_atualizar_indisponivel(self, servico_folha):
        servico_folha._disponivel = False

        resultado = servico_folha.atualizar_folha(
            str(SAMPLE_FOLHA_ID), {"folha_data": {}}
        )

        assert resultado is False



# ==================== Recalculador compartilhado ====================

@pytest.mark.unit
class TestRecalcularTotais:
    """recalcular_totais_folha — MESMO cálculo da geração, reutilizado na edição."""

    def test_recalcula_totais_dicts(self):
        dias = [
            {"numero_dia": 1, "tipo_dia": "NORMAL", "dia_semana": "Quarta",
             "total_horas_trabalhadas": "08:00"},
            {"numero_dia": 2, "tipo_dia": "FALTA", "dia_semana": "Quinta",
             "total_horas_trabalhadas": None},
            {"numero_dia": 3, "tipo_dia": "FERIADO", "dia_semana": "Sexta",
             "total_horas_trabalhadas": None},
            {"numero_dia": 4, "tipo_dia": "SÁBADO", "dia_semana": "Sábado",
             "total_horas_trabalhadas": None},
            {"numero_dia": 5, "tipo_dia": "DOMINGO", "dia_semana": "Domingo",
             "total_horas_trabalhadas": None},
            {"numero_dia": 6, "tipo_dia": "NORMAL", "dia_semana": "Segunda",
             "total_horas_trabalhadas": "07:30"},
        ]

        totais = recalcular_totais_folha(dias)

        assert totais["total_horas_mes"] == "15:30"  # 08:00 + 07:30
        assert totais["total_faltas"] == 1
        assert totais["total_feriados"] == 1
        assert totais["total_finais_semana"] == 2

    def test_recalcula_sem_dias(self):
        totais = recalcular_totais_folha([])

        assert totais["total_horas_mes"] == "00:00"
        assert totais["total_faltas"] == 0
        assert totais["total_feriados"] == 0
        assert totais["total_finais_semana"] == 0

    def test_calcular_total_horas_dia(self):
        assert calcular_total_horas("08:00", "17:00", "12:00", "13:00") == "08:00"
        assert calcular_total_horas(None, "17:00", None, None) is None
        assert calcular_total_horas("08:00", "17:00", None, None) == "09:00"


# ==================== Editar folha (fluxo completo) ====================

@pytest.mark.unit
class TestEditarFolha:
    """Folha_de_Ponto.editar_folha — recalcula, regenera PDF, versão + histórico."""

    def _criar_fp_mock(self, servico_folha, folha):
        """Cria instância Folha_de_Ponto com serviços mockados."""
        from src.folha_de_ponto import Folha_de_Ponto

        fp = Folha_de_Ponto.__new__(Folha_de_Ponto)
        gerador = MagicMock()
        gerador.servico_folha_ponto = servico_folha
        fp.gerador_folha_ponto = gerador
        fp.html_template = MagicMock()
        fp.html_converter = MagicMock()
        # Mock do regenerador de PDF (retorna caminho)
        fp.regenerar_pdf_folha = MagicMock(return_value="/tmp/folhas/João Silva.pdf")
        return fp

    def _folha_com_dias(self):
        folha = criar_folha_doc(versao=1)
        folha["folha_data"]["dias"] = [
            {
                "numero_dia": 1,
                "hora_entrada": "08:00",
                "hora_saida": "17:00",
                "hora_intervalo_inicio": "12:00",
                "hora_intervalo_fim": "13:00",
                "tipo_dia": "NORMAL",
                "observacoes": None,
                "total_horas_trabalhadas": "08:00",
            },
            {
                "numero_dia": 2,
                "hora_entrada": None,
                "hora_saida": None,
                "hora_intervalo_inicio": None,
                "hora_intervalo_fim": None,
                "tipo_dia": "FALTA",
                "observacoes": "Faltou",
                "total_horas_trabalhadas": None,
            },
        ]
        return folha

    def test_editar_recalcula_totais(self, servico_folha, mock_colecao):
        folha = self._folha_com_dias()
        mock_colecao.find_one.return_value = folha
        mock_colecao.update_one.return_value = MagicMock(modified_count=1, matched_count=1)
        fp = self._criar_fp_mock(servico_folha, folha)

        resultado = fp.editar_folha(
            folha_id=str(SAMPLE_FOLHA_ID),
            dias_editados=[
                {"numero_dia": 2, "hora_entrada": "09:00", "hora_saida": "18:00",
                 "hora_intervalo_inicio": "12:00", "hora_intervalo_fim": "13:00",
                 "tipo_dia": "NORMAL"},
            ],
            atualizar_pdf=True,
        )

        assert resultado is not None
        assert resultado["status"] == "sucesso"
        assert resultado["versao"] == 2  # versão incrementada
        assert resultado["dias_alterados"] == [2]

        # Recalculo: dia 1 (08:00) + dia 2 (09:00-18:00 c/ 1h intervalo = 08:00) = 16:00
        totais = resultado["totais"]
        assert totais["total_horas_mes"] == "16:00"
        assert totais["total_faltas"] == 0  # FALTA removida

    def test_editar_regenera_pdf_e_salva_caminho(self, servico_folha, mock_colecao):
        folha = self._folha_com_dias()
        mock_colecao.find_one.return_value = folha
        mock_colecao.update_one.return_value = MagicMock(modified_count=1, matched_count=1)
        fp = self._criar_fp_mock(servico_folha, folha)

        resultado = fp.editar_folha(
            folha_id=str(SAMPLE_FOLHA_ID),
            dias_editados=[{"numero_dia": 1, "observacoes": "Corrigido"}],
            atualizar_pdf=True,
        )

        # PDF regenerado automaticamente
        fp.regenerar_pdf_folha.assert_called_once()
        assert resultado["caminho_pdf"] == "/tmp/folhas/João Silva.pdf"

        # O caminho do PDF é persistido junto com a folha_data
        dados_salvos = mock_colecao.update_one.call_args[0][1]["$set"]
        assert dados_salvos["caminho_arquivo_gerado"] == "/tmp/folhas/João Silva.pdf"

    def test_editar_adiciona_historico(self, servico_folha, mock_colecao):
        folha = self._folha_com_dias()
        mock_colecao.find_one.return_value = folha
        mock_colecao.update_one.return_value = MagicMock(modified_count=1, matched_count=1)
        fp = self._criar_fp_mock(servico_folha, folha)

        fp.editar_folha(
            folha_id=str(SAMPLE_FOLHA_ID),
            dias_editados=[{"numero_dia": 1, "hora_entrada": "07:00"}],
            atualizar_pdf=False,
        )

        update = mock_colecao.update_one.call_args[0][1]
        assert update["$set"]["versao"] == 2
        historico = update["$set"]["historico_alteracoes"]
        assert len(historico) == 1
        assert historico[0]["acao"] == "Folha editada manualmente"
        assert historico[0]["versao_anterior"] == 1
        assert historico[0]["versao_nova"] == 2

    def test_editar_sem_pdf(self, servico_folha, mock_colecao):
        """atualizar_pdf=False: não chama regenerador."""
        folha = self._folha_com_dias()
        mock_colecao.find_one.return_value = folha
        mock_colecao.update_one.return_value = MagicMock(modified_count=1, matched_count=1)
        fp = self._criar_fp_mock(servico_folha, folha)

        resultado = fp.editar_folha(
            folha_id=str(SAMPLE_FOLHA_ID),
            dias_editados=[{"numero_dia": 1, "observacoes": "x"}],
            atualizar_pdf=False,
        )

        fp.regenerar_pdf_folha.assert_not_called()
        assert resultado["status"] == "sucesso"
        assert resultado["caminho_pdf"] is None

    def test_editar_folha_excluida_bloqueada(self, servico_folha, mock_colecao):
        folha = self._folha_com_dias()
        folha["excluida"] = True
        mock_colecao.find_one.return_value = folha
        fp = self._criar_fp_mock(servico_folha, folha)

        resultado = fp.editar_folha(
            folha_id=str(SAMPLE_FOLHA_ID),
            dias_editados=[{"numero_dia": 1, "observacoes": "x"}],
        )

        assert resultado["status"] == "bloqueada"
        mock_colecao.update_one.assert_not_called()

    def test_editar_folha_nao_encontrada(self, servico_folha, mock_colecao):
        mock_colecao.find_one.return_value = None
        fp = self._criar_fp_mock(servico_folha, None)

        resultado = fp.editar_folha(
            folha_id=str(SAMPLE_FOLHA_ID),
            dias_editados=[{"numero_dia": 1, "observacoes": "x"}],
        )

        assert resultado is None


    def test_editar_limpar_horario_com_string_vazia(self, servico_folha, mock_colecao):
        """Enviar limpar_campos com hora_entrada deve definir como None e recalcular."""
        folha = self._folha_com_dias()
        mock_colecao.find_one.return_value = folha
        mock_colecao.update_one.return_value = MagicMock(modified_count=1, matched_count=1)
        fp = self._criar_fp_mock(servico_folha, folha)

        resultado = fp.editar_folha(
            folha_id=str(SAMPLE_FOLHA_ID),
            dias_editados=[
                {
                    "numero_dia": 1,
                    "limpar_campos": ["hora_entrada"],
                },
            ],
            atualizar_pdf=False,
        )

        assert resultado is not None
        assert resultado["status"] == "sucesso"

        # Dia 1 tinha hora_entrada="08:00" e hora_saida="17:00"
        # Após limpar hora_entrada, total_horas_trabalhadas deve ser None (sem entrada)
        update = mock_colecao.update_one.call_args[0][1]
        dias_salvos = update["$set"]["folha_data"]["dias"]
        dia1 = next(d for d in dias_salvos if d["numero_dia"] == 1)
        assert dia1["hora_entrada"] is None
        assert dia1["total_horas_trabalhadas"] is None  # sem entrada = sem total

    def test_editar_limpar_todos_horarios(self, servico_folha, mock_colecao):
        """Limpar todos os horários de um dia deve zerar o total."""
        folha = self._folha_com_dias()
        mock_colecao.find_one.return_value = folha
        mock_colecao.update_one.return_value = MagicMock(modified_count=1, matched_count=1)
        fp = self._criar_fp_mock(servico_folha, folha)

        resultado = fp.editar_folha(
            folha_id=str(SAMPLE_FOLHA_ID),
            dias_editados=[
                {
                    "numero_dia": 1,
                    "limpar_campos": ["hora_entrada", "hora_saida", "hora_intervalo_inicio", "hora_intervalo_fim"],
                },
            ],
            atualizar_pdf=False,
        )

        assert resultado["status"] == "sucesso"
        update = mock_colecao.update_one.call_args[0][1]
        dias_salvos = update["$set"]["folha_data"]["dias"]
        dia1 = next(d for d in dias_salvos if d["numero_dia"] == 1)
        assert dia1["hora_entrada"] is None
        assert dia1["hora_saida"] is None
        assert dia1["hora_intervalo_inicio"] is None
        assert dia1["hora_intervalo_fim"] is None
        assert dia1["total_horas_trabalhadas"] is None
        # Totais: dia 1 sem horas + dia 2 FALTA = 0 horas total
        assert resultado["totais"]["total_horas_mes"] == "00:00"

    def test_editar_limpar_e_definir_novos_horarios(self, servico_folha, mock_colecao):
        """Limpar horários antigos e definir novos deve usar os novos valores."""
        folha = self._folha_com_dias()
        mock_colecao.find_one.return_value = folha
        mock_colecao.update_one.return_value = MagicMock(modified_count=1, matched_count=1)
        fp = self._criar_fp_mock(servico_folha, folha)

        resultado = fp.editar_folha(
            folha_id=str(SAMPLE_FOLHA_ID),
            dias_editados=[
                {
                    "numero_dia": 1,
                    # limpa intervalo, define novos valores de entrada/saída
                    "limpar_campos": ["hora_intervalo_inicio", "hora_intervalo_fim"],
                    "hora_entrada": "09:00",
                    "hora_saida": "19:00",
                },
            ],
            atualizar_pdf=False,
        )

        assert resultado["status"] == "sucesso"
        update = mock_colecao.update_one.call_args[0][1]
        dias_salvos = update["$set"]["folha_data"]["dias"]
        dia1 = next(d for d in dias_salvos if d["numero_dia"] == 1)
        assert dia1["hora_entrada"] == "09:00"
        assert dia1["hora_saida"] == "19:00"
        # intervalo limpo
        assert dia1["hora_intervalo_inicio"] is None
        assert dia1["hora_intervalo_fim"] is None
        # 09:00-19:00 sem intervalo = 10:00
        assert dia1["total_horas_trabalhadas"] == "10:00"


# ==================== Regenerar PDF (caminho real, sem mock) ====================

@pytest.mark.unit
class TestRegenerarPdfReal:
    """regenerar_pdf_folha + _montar_contexto_html_editado reais."""

    def _criar_fp_sem_mock(self, servico_folha):
        """Folha_de_Ponto com serviços mockados, mas SEM mockar regenerar_pdf."""
        from src.folha_de_ponto import Folha_de_Ponto

        fp = Folha_de_Ponto.__new__(Folha_de_Ponto)
        gerador = MagicMock()
        gerador.servico_folha_ponto = servico_folha
        gerador.servico_funcionario = MagicMock()
        gerador.servico_funcionario.buscar_por_object_id.return_value = {"nome": "João Silva"}
        gerador.servico_empresa = MagicMock()
        gerador.servico_empresa.buscar_por_id.return_value = {
            "nome": "Empresa Teste", "atividade": "TI", "endereco": "Rua A", "cnpj": "123"
        }
        fp.gerador_folha_ponto = gerador

        fp.html_template = MagicMock()
        fp.html_template.render.return_value = "<html>folha</html>"
        fp.html_converter = MagicMock()

        fp.processador_folha_ponto = MagicMock()
        fp.processador_folha_ponto.feriados = None

        fp.gerenciador_diretorios = MagicMock()
        return fp

    def _folha_completa(self):
        folha = criar_folha_doc()
        folha["folha_data"]["dias"] = [
            {
                "numero_dia": 1,
                "hora_entrada": "08:00",
                "hora_saida": "17:00",
                "hora_intervalo_inicio": "12:00",
                "hora_intervalo_fim": "13:00",
                "tipo_dia": "NORMAL",
                "observacoes": None,
                "total_horas_trabalhadas": "08:00",
            },
            {
                "numero_dia": 2,
                "hora_entrada": None,
                "hora_saida": None,
                "hora_intervalo_inicio": None,
                "hora_intervalo_fim": None,
                "tipo_dia": "FALTA",
                "observacoes": "Faltou",
                "total_horas_trabalhadas": None,
            },
        ]
        return folha

    def test_montar_contexto_html_editado(self):
        """Monta contexto com dias editados (horários, faltas, observações)."""
        from src.folha_de_ponto import Folha_de_Ponto

        fp = Folha_de_Ponto.__new__(Folha_de_Ponto)
        fp.processador_folha_ponto = MagicMock()
        fp.processador_folha_ponto.feriados = None

        folha = self._folha_completa()
        contexto = fp._montar_contexto_html_editado(
            folha, date(2025, 1, 15),
            funcionario={"nome": "João Silva"},
            empresa={"nome": "Empresa Teste", "atividade": "TI", "endereco": "Rua A", "cnpj": "123"},
        )

        assert contexto["FP"]["id"] == str(SAMPLE_FOLHA_ID)
        assert contexto["periodo"]["inicio"] == "01/01/2025"
        assert contexto["periodo"]["fim"] == "31/01/2025"
        assert contexto["funcionario"]["nome"] == "João Silva"
        assert contexto["empresa"]["nome"] == "Empresa Teste"
        assert len(contexto["dias"]) == 31

        # Dia 1 com horários
        dia1 = next(d for d in contexto["dias"] if d["dia_numero"] == "01")
        assert dia1["entrada"] == "08:00"
        assert dia1["termino"] == "17:00"
        # Dia 2 (FALTA) vira observação
        dia2 = next(d for d in contexto["dias"] if d["dia_numero"] == "02")
        assert "FALTA" in dia2["observacoes"]

    def test_regenerar_pdf_com_diretorio_destino(self, servico_folha):
        fp = self._criar_fp_sem_mock(servico_folha)
        folha = self._folha_completa()

        caminho = fp.regenerar_pdf_folha(folha, diretorio_destino="/tmp/fp_dest")

        assert caminho is not None
        assert "folha_2025-01_" in caminho
        fp.html_converter.salvar_html_como_pdf.assert_called_once()
        fp.html_template.render.assert_called_once()

    def test_regenerar_pdf_usando_caminho_existente(self, servico_folha):
        fp = self._criar_fp_sem_mock(servico_folha)
        folha = self._folha_completa()
        folha["caminho_arquivo_gerado"] = "/tmp/folhas_existentes/João Silva.pdf"

        caminho = fp.regenerar_pdf_folha(folha)

        assert caminho == "/tmp/folhas_existentes/João Silva.pdf"
        fp.html_converter.salvar_html_como_pdf.assert_called_once()

    def test_regenerar_pdf_sem_template(self, servico_folha):
        fp = self._criar_fp_sem_mock(servico_folha)
        fp.html_template = None

        caminho = fp.regenerar_pdf_folha(self._folha_completa())

        assert caminho is None

    def test_regenerar_pdf_sem_funcionario_empresa(self, servico_folha):
        fp = self._criar_fp_sem_mock(servico_folha)
        folha = criar_folha_doc()
        folha.pop("funcionario_id")
        folha.pop("empresa_id")

        caminho = fp.regenerar_pdf_folha(folha)

        assert caminho is None

    def test_editar_com_pdf_real(self, servico_folha, mock_colecao):
        """Fluxo completo: editar_folha usa regenerar_pdf_folha REAL (não mock)."""
        from src.folha_de_ponto import Folha_de_Ponto

        folha = self._folha_completa()
        mock_colecao.find_one.return_value = folha
        mock_colecao.update_one.return_value = MagicMock(modified_count=1, matched_count=1)

        fp = self._criar_fp_sem_mock(servico_folha)

        resultado = fp.editar_folha(
            folha_id=str(SAMPLE_FOLHA_ID),
            dias_editados=[{"numero_dia": 2, "hora_entrada": "09:00", "hora_saida": "18:00"}],
            atualizar_pdf=True,
        )

        assert resultado is not None
        assert resultado["status"] == "sucesso"
        assert resultado["versao"] == 2
        assert resultado["caminho_pdf"] is not None
        # PDF real foi gerado (converter chamado)
        fp.html_converter.salvar_html_como_pdf.assert_called_once()

    def test_editar_com_observacoes_gerais(self, servico_folha, mock_colecao):
        from src.folha_de_ponto import Folha_de_Ponto

        folha = self._folha_completa()
        mock_colecao.find_one.return_value = folha
        mock_colecao.update_one.return_value = MagicMock(modified_count=1, matched_count=1)

        fp = self._criar_fp_sem_mock(servico_folha)

        resultado = fp.editar_folha(
            folha_id=str(SAMPLE_FOLHA_ID),
            dias_editados=[{"numero_dia": 1, "observacoes": "Corrigido"}],
            observacoes_gerais="Revisado pelo RH",
            atualizar_pdf=False,
        )

        assert resultado["status"] == "sucesso"
        dados_salvos = mock_colecao.update_one.call_args[0][1]["$set"]
        assert dados_salvos["folha_data"]["observacoes_gerais"] == "Revisado pelo RH"
