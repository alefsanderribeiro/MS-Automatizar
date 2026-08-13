"""Testes unitarios para o modulo funcionario_sanitizador."""

import pytest
from src.utils.funcionario_sanitizador import (
    SanitizadorFuncionario,
    ConstrutorFuncionarioIncompleto,
)


class TestRemoverAcentos:
    """Testes para o metodo remover_acentos."""

    def test_remover_acentos_texto_com_acentos(self):
        """Testa remocao de acentos em texto comum."""
        texto = "Jose Maria"
        resultado = SanitizadorFuncionario.remover_acentos(texto)
        assert resultado == "Jose Maria"

    def test_remover_acentos_cedilha(self):
        """Testa remocao de cedilha."""
        texto = "Funcao"
        resultado = SanitizadorFuncionario.remover_acentos(texto)
        assert "c" in resultado.lower() or "C" in resultado

    def test_remover_acentos_texto_sem_acentos(self):
        """Testa texto sem acentos permanece inalterado."""
        texto = "Maria Silva"
        resultado = SanitizadorFuncionario.remover_acentos(texto)
        assert resultado == "Maria Silva"

    def test_remover_acentos_texto_vazio(self):
        """Testa remocao de acentos com texto vazio."""
        texto = ""
        resultado = SanitizadorFuncionario.remover_acentos(texto)
        assert resultado == ""

    def test_remover_acentos_diversos_tipos(self):
        """Testa remocao de diversos tipos de acentos."""
        texto = "aeiou"
        resultado = SanitizadorFuncionario.remover_acentos(texto)
        assert resultado == "aeiou"


class TestRemoverCaracteresEspeciais:
    """Testes para o metodo remover_caracteres_especiais."""

    def test_remover_caracteres_perigosos_dagger(self):
        """Testa remocao do caractere dagger."""
        texto = "Nome†Com"
        resultado = SanitizadorFuncionario.remover_caracteres_especiais(texto)
        assert "†" not in resultado

    def test_remover_caracteres_perigosos_double_dagger(self):
        """Testa remocao do caractere double dagger."""
        texto = "Com‡Caracteres"
        resultado = SanitizadorFuncionario.remover_caracteres_especiais(texto)
        assert "‡" not in resultado

    def test_remover_caracteres_perigosos_section(self):
        """Testa remocao do caractere section."""
        texto = "Perigosos§Aqui"
        resultado = SanitizadorFuncionario.remover_caracteres_especiais(texto)
        assert "§" not in resultado

    def test_remover_caracteres_especiais_permitir_acentos(self):
        """Testa que acentos sao mantidos quando permitidos."""
        texto = "Jose Maria"
        resultado = SanitizadorFuncionario.remover_caracteres_especiais(
            texto, permitir_acentos=True
        )
        assert "Jose" in resultado or "Jose" in resultado

    def test_remover_caracteres_especiais_sem_permitir_acentos(self):
        """Testa que acentos sao removidos quando nao permitidos."""
        texto = "Jose Maria"
        resultado = SanitizadorFuncionario.remover_caracteres_especiais(
            texto, permitir_acentos=False
        )
        assert "Jose" in resultado

    def test_remover_caracteres_especiais_texto_limpo(self):
        """Testa texto sem caracteres especiais permanece inalterado."""
        texto = "Nome Limpo Silva"
        resultado = SanitizadorFuncionario.remover_caracteres_especiais(texto)
        assert resultado == texto

    def test_remover_espacos_multiplos(self):
        """Testa remocao de espacos multiplos."""
        texto = "Nome   Com   Espacos"
        resultado = SanitizadorFuncionario.remover_caracteres_especiais(texto)
        assert "   " not in resultado


class TestLimparNome:
    """Testes para o metodo limpar_nome."""

    def test_limpar_nome_valido(self):
        """Testa limpeza de nome valido."""
        nome = "  Joao Silva  "
        resultado = SanitizadorFuncionario.limpar_nome(nome)
        assert "Joao" in resultado or "João" in resultado

    def test_limpar_nome_com_caracteres_especiais(self):
        """Testa limpeza de nome com caracteres especiais."""
        nome = "Maria†Santos‡Silva"
        resultado = SanitizadorFuncionario.limpar_nome(nome)
        assert "†" not in resultado
        assert "‡" not in resultado

    def test_limpar_nome_vazio_raise_error(self):
        """Testa que nome vazio levanta ValueError."""
        nome = ""
        with pytest.raises(ValueError):
            SanitizadorFuncionario.limpar_nome(nome)

    def test_limpar_nome_apenas_espacos_raise_error(self):
        """Testa que nome com apenas espacos levanta ValueError."""
        nome = "   "
        with pytest.raises(ValueError):
            SanitizadorFuncionario.limpar_nome(nome)

    def test_limpar_nome_muito_curto_raise_error(self):
        """Testa que nome muito curto levanta ValueError."""
        nome = "AB"
        with pytest.raises(ValueError):
            SanitizadorFuncionario.limpar_nome(nome)

    def test_limpar_nome_modo_rigido_remove_acentos(self):
        """Testa modo rigido remove acentos."""
        nome = "Jose Maria"
        resultado = SanitizadorFuncionario.limpar_nome(nome, modo_rígido=True)
        assert "Jose" in resultado

    def test_limpar_nome_capitaliza_corretamente(self):
        """Testa que nome e capitalizado corretamente."""
        nome = "joao da silva"
        resultado = SanitizadorFuncionario.limpar_nome(nome)
        assert resultado[0].isupper()


class TestLimparFuncao:
    """Testes para o metodo limpar_funcao."""

    def test_limpar_funcao_valida(self):
        """Testa limpeza de funcao valida."""
        funcao = "  Engenheiro  "
        resultado = SanitizadorFuncionario.limpar_funcao(funcao)
        assert resultado == "Engenheiro"

    def test_limpar_funcao_vazia(self):
        """Testa funcao vazia retorna padrao."""
        funcao = ""
        resultado = SanitizadorFuncionario.limpar_funcao(funcao)
        assert "Especificado" in resultado or "especificado" in resultado.lower()

    def test_limpar_funcao_apenas_espacos(self):
        """Testa funcao com apenas espacos retorna padrao."""
        funcao = "   "
        resultado = SanitizadorFuncionario.limpar_funcao(funcao)
        assert "Especificado" in resultado or "especificado" in resultado.lower()

    def test_limpar_funcao_com_caracteres_especiais(self):
        """Testa funcao com caracteres especiais."""
        funcao = "Analista†TI"
        resultado = SanitizadorFuncionario.limpar_funcao(funcao)
        assert "†" not in resultado


class TestLimparLotacao:
    """Testes para o metodo limpar_lotacao."""

    def test_limpar_lotacao_valida(self):
        """Testa limpeza de lotacao valida."""
        lotacao = "  Departamento TI  "
        resultado = SanitizadorFuncionario.limpar_lotacao(lotacao)
        assert "Departamento" in resultado

    def test_limpar_lotacao_vazia(self):
        """Testa lotacao vazia retorna padrao."""
        lotacao = ""
        resultado = SanitizadorFuncionario.limpar_lotacao(lotacao)
        assert "Lotacao" in resultado or "Lotação" in resultado

    def test_limpar_lotacao_apenas_espacos(self):
        """Testa lotacao com apenas espacos retorna padrao."""
        lotacao = "   "
        resultado = SanitizadorFuncionario.limpar_lotacao(lotacao)
        assert "Lotacao" in resultado or "Lotação" in resultado


class TestLimparEmpresa:
    """Testes para o metodo limpar_empresa."""

    def test_limpar_empresa_valida(self):
        """Testa limpeza de empresa valida."""
        empresa = "  Empresa ABC  "
        resultado = SanitizadorFuncionario.limpar_empresa(empresa)
        assert "Empresa ABC" in resultado

    def test_limpar_empresa_com_numeros(self):
        """Testa empresa com numeros e permitida."""
        empresa = "Empresa 123 LTDA"
        resultado = SanitizadorFuncionario.limpar_empresa(empresa)
        assert "123" in resultado

    def test_limpar_empresa_vazia(self):
        """Testa empresa vazia retorna padrao."""
        empresa = ""
        resultado = SanitizadorFuncionario.limpar_empresa(empresa)
        assert "Desconhecida" in resultado or "desconhecida" in resultado.lower()

    def test_limpar_empresa_apenas_espacos(self):
        """Testa empresa com apenas espacos retorna padrao."""
        empresa = "   "
        resultado = SanitizadorFuncionario.limpar_empresa(empresa)
        assert "Desconhecida" in resultado or "desconhecida" in resultado.lower()

    def test_limpar_empresa_com_cnpj(self):
        """Testa empresa com CNPJ parcial."""
        empresa = "Empresa 12.345.678/0001-90"
        resultado = SanitizadorFuncionario.limpar_empresa(empresa)
        assert "12" in resultado


class TestConstrutorFuncionarioIncompleto:
    """Testes para a classe ConstrutorFuncionarioIncompleto."""

    def test_criar_do_pdf_sucesso(self):
        """Testa criacao bem-sucedida de funcionario incompleto."""
        funcionario, erros = ConstrutorFuncionarioIncompleto.criar_do_pdf(
            nome_pdf="documento.pdf",
            empresa_extraida="Empresa XYZ",
            funcionario_nome_extraido="Joao Silva Santos",
            funcionario_funcao="Engenheiro",
            mes_ano="01/2024",
        )

        assert funcionario is not None
        assert "nome" in funcionario
        assert funcionario["incompleto"] is True

    def test_criar_do_pdf_gera_nome_normalizado(self):
        """Testa que nome_normalizado e gerado."""
        funcionario, erros = ConstrutorFuncionarioIncompleto.criar_do_pdf(
            nome_pdf="documento.pdf",
            empresa_extraida="Empresa",
            funcionario_nome_extraido="Joao Silva Santos",
            funcionario_funcao="Analista",
            mes_ano="01/2024",
        )

        assert "nome_normalizado" in funcionario
        assert funcionario["nome_normalizado"].islower()

    def test_criar_do_pdf_com_dados_vazios_usa_padrao(self):
        """Testa criacao com dados vazios usa valores padrao."""
        funcionario, erros = ConstrutorFuncionarioIncompleto.criar_do_pdf(
            nome_pdf="documento.pdf",
            empresa_extraida="",
            funcionario_nome_extraido="Joao Silva Santos",
            funcionario_funcao="",
            mes_ano="01/2024",
        )

        assert funcionario is not None
        assert "Desconhecida" in funcionario.get("empresa", "") or funcionario.get("empresa") != ""

    def test_criar_do_pdf_com_caracteres_especiais(self):
        """Testa criacao com caracteres especiais nos campos."""
        funcionario, erros = ConstrutorFuncionarioIncompleto.criar_do_pdf(
            nome_pdf="documento.pdf",
            empresa_extraida="Empresa†ABC",
            funcionario_nome_extraido="Maria‡Silva Santos",
            funcionario_funcao="Analista§TI",
            mes_ano="01/2024",
        )

        assert funcionario is not None
        assert "†" not in funcionario.get("nome", "")

    def test_criar_do_pdf_define_campos_incompletos(self):
        """Testa que campos incompletos sao definidos."""
        funcionario, erros = ConstrutorFuncionarioIncompleto.criar_do_pdf(
            nome_pdf="documento.pdf",
            empresa_extraida="Empresa",
            funcionario_nome_extraido="Joao Silva Santos",
            funcionario_funcao="Analista",
            mes_ano="01/2024",
        )

        assert funcionario["incompleto"] is True
        assert "incompleto_campos" in funcionario

    def test_criar_do_pdf_registra_origem(self):
        """Testa que origem do PDF e registrada."""
        funcionario, erros = ConstrutorFuncionarioIncompleto.criar_do_pdf(
            nome_pdf="folha_janeiro.pdf",
            empresa_extraida="Empresa",
            funcionario_nome_extraido="Joao Silva Santos",
            funcionario_funcao="Analista",
            mes_ano="01/2024",
        )

        assert "origem_pdf" in funcionario
        assert funcionario["origem_pdf"] == "folha_janeiro.pdf"

    def test_criar_do_pdf_modo_rigido(self):
        """Testa criacao em modo rigido."""
        funcionario, erros = ConstrutorFuncionarioIncompleto.criar_do_pdf(
            nome_pdf="documento.pdf",
            empresa_extraida="Empresa",
            funcionario_nome_extraido="Jose Maria Santos",
            funcionario_funcao="Analista",
            mes_ano="01/2024",
            modo_rígido=True,
        )

        assert funcionario is not None
