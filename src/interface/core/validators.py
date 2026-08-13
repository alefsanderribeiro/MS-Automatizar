"""
Validadores reutilizáveis para inputs da interface.

Funções de validação que podem ser usadas com pedir_texto()
e outros componentes de input.

Uso:
    from src.interface.core.validators import validar_cpf, validar_email

    cpf = pedir_texto("CPF:", validador=validar_cpf)
    email = pedir_texto("E-mail:", validador=validar_email)
"""

import re
from datetime import datetime
from typing import Optional


def validar_email(valor: str) -> bool:
    """
    Valida formato básico de e-mail.

    Args:
        valor: String a validar.

    Returns:
        True se formato válido, False caso contrário.

    Exemplos:
        >>> validar_email("teste@email.com")
        True
        >>> validar_email("invalido")
        False
    """
    if not valor:
        return False
    padrao = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(padrao, valor.strip()))


def validar_cpf(valor: str) -> bool:
    """
    Valida formato de CPF (apenas formato, não dígitos verificadores).

    Aceita formatos:
    - 12345678901 (apenas números)
    - 123.456.789-01 (formatado)

    Args:
        valor: String a validar.

    Returns:
        True se formato válido (11 dígitos), False caso contrário.
    """
    if not valor:
        return False
    cpf_limpo = re.sub(r"\D", "", valor)
    return len(cpf_limpo) == 11


def validar_cnpj(valor: str) -> bool:
    """
    Valida formato de CNPJ (apenas formato, não dígitos verificadores).

    Aceita formatos:
    - 12345678000199 (apenas números)
    - 12.345.678/0001-99 (formatado)

    Args:
        valor: String a validar.

    Returns:
        True se formato válido (14 dígitos), False caso contrário.
    """
    if not valor:
        return False
    cnpj_limpo = re.sub(r"\D", "", valor)
    return len(cnpj_limpo) == 14


def validar_telefone(valor: str) -> bool:
    """
    Valida formato de telefone brasileiro.

    Aceita formatos com 10 ou 11 dígitos:
    - 6932221234 (fixo)
    - 69999991234 (celular)
    - (69) 3222-1234
    - (69) 99999-1234

    Args:
        valor: String a validar.

    Returns:
        True se formato válido, False caso contrário.
    """
    if not valor:
        return False
    tel_limpo = re.sub(r"\D", "", valor)
    return len(tel_limpo) in (10, 11)


def validar_data(valor: str) -> bool:
    """
    Valida formato de data DD/MM/AAAA.

    Args:
        valor: String a validar.

    Returns:
        True se formato válido e data existe, False caso contrário.

    Exemplos:
        >>> validar_data("25/12/2024")
        True
        >>> validar_data("31/02/2024")
        False  # Fevereiro não tem 31 dias
    """
    if not valor:
        return False

    if not re.match(r"^\d{2}/\d{2}/\d{4}$", valor.strip()):
        return False

    try:
        datetime.strptime(valor.strip(), "%d/%m/%Y")
        return True
    except ValueError:
        return False


def validar_mes_ano(valor: str) -> bool:
    """
    Valida formato de mês/ano: MM/AAAA ou MM.AAAA.

    Args:
        valor: String a validar.

    Returns:
        True se formato válido, False caso contrário.

    Exemplos:
        >>> validar_mes_ano("12/2024")
        True
        >>> validar_mes_ano("01.2025")
        True
        >>> validar_mes_ano("13/2024")
        False  # Mês inválido
    """
    if not valor:
        return False

    if not re.match(r"^\d{2}[./]\d{4}$", valor.strip()):
        return False

    # Extrai mês e ano
    partes = re.split(r"[./]", valor.strip())
    mes = int(partes[0])
    ano = int(partes[1])

    # Valida ranges
    if mes < 1 or mes > 12:
        return False
    if ano < 1900 or ano > 2100:
        return False

    return True


def validar_hora(valor: str) -> bool:
    """
    Valida formato de hora HH:MM.

    Args:
        valor: String a validar.

    Returns:
        True se formato válido, False caso contrário.

    Exemplos:
        >>> validar_hora("08:30")
        True
        >>> validar_hora("25:00")
        False  # Hora inválida
    """
    if not valor:
        return False

    if not re.match(r"^\d{2}:\d{2}$", valor.strip()):
        return False

    partes = valor.strip().split(":")
    hora = int(partes[0])
    minuto = int(partes[1])

    return 0 <= hora <= 23 and 0 <= minuto <= 59


def validar_inteiro_positivo(valor: str) -> bool:
    """
    Valida se é um número inteiro positivo.

    Args:
        valor: String a validar.

    Returns:
        True se inteiro positivo, False caso contrário.
    """
    if not valor:
        return False
    try:
        return int(valor.strip()) > 0
    except ValueError:
        return False


def validar_inteiro_nao_negativo(valor: str) -> bool:
    """
    Valida se é um número inteiro não negativo (>= 0).

    Args:
        valor: String a validar.

    Returns:
        True se inteiro >= 0, False caso contrário.
    """
    if not valor:
        return False
    try:
        return int(valor.strip()) >= 0
    except ValueError:
        return False


def validar_decimal(valor: str) -> bool:
    """
    Valida se é um número decimal válido.

    Aceita vírgula ou ponto como separador decimal.

    Args:
        valor: String a validar.

    Returns:
        True se decimal válido, False caso contrário.
    """
    if not valor:
        return False
    try:
        float(valor.strip().replace(",", "."))
        return True
    except ValueError:
        return False


def parse_data(valor: str, formato: str = "%d/%m/%Y") -> Optional[datetime]:
    """
    Converte string para datetime.

    Args:
        valor: String com a data.
        formato: Formato da data (padrão: DD/MM/AAAA).

    Returns:
        Objeto datetime ou None se conversão falhar.

    Exemplos:
        >>> parse_data("25/12/2024")
        datetime.datetime(2024, 12, 25, 0, 0)
        >>> parse_data("invalido")
        None
    """
    if not valor:
        return None
    try:
        return datetime.strptime(valor.strip(), formato)
    except ValueError:
        return None


def parse_mes_ano(valor: str) -> Optional[tuple[int, int]]:
    """
    Converte string MM/AAAA ou MM.AAAA para tupla (mes, ano).

    Args:
        valor: String com mês/ano.

    Returns:
        Tupla (mes, ano) ou None se conversão falhar.

    Exemplos:
        >>> parse_mes_ano("12/2024")
        (12, 2024)
        >>> parse_mes_ano("01.2025")
        (1, 2025)
    """
    if not validar_mes_ano(valor):
        return None

    partes = re.split(r"[./]", valor.strip())
    return (int(partes[0]), int(partes[1]))


def formatar_cpf(cpf: str) -> str:
    """
    Formata CPF para exibição: 123.456.789-01.

    Args:
        cpf: CPF em qualquer formato.

    Returns:
        CPF formatado ou string original se inválido.
    """
    cpf_limpo = re.sub(r"\D", "", cpf)
    if len(cpf_limpo) != 11:
        return cpf
    return f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}"


def formatar_cnpj(cnpj: str) -> str:
    """
    Formata CNPJ para exibição: 12.345.678/0001-99.

    Args:
        cnpj: CNPJ em qualquer formato.

    Returns:
        CNPJ formatado ou string original se inválido.
    """
    cnpj_limpo = re.sub(r"\D", "", cnpj)
    if len(cnpj_limpo) != 14:
        return cnpj
    return f"{cnpj_limpo[:2]}.{cnpj_limpo[2:5]}.{cnpj_limpo[5:8]}/{cnpj_limpo[8:12]}-{cnpj_limpo[12:]}"


def formatar_telefone(telefone: str) -> str:
    """
    Formata telefone para exibição: (69) 99999-1234.

    Args:
        telefone: Telefone em qualquer formato.

    Returns:
        Telefone formatado ou string original se inválido.
    """
    tel_limpo = re.sub(r"\D", "", telefone)

    if len(tel_limpo) == 11:
        return f"({tel_limpo[:2]}) {tel_limpo[2:7]}-{tel_limpo[7:]}"
    elif len(tel_limpo) == 10:
        return f"({tel_limpo[:2]}) {tel_limpo[2:6]}-{tel_limpo[6:]}"

    return telefone


def limpar_cpf(cpf: str) -> str:
    """
    Remove formatação do CPF, retornando apenas dígitos.

    Args:
        cpf: CPF em qualquer formato.

    Returns:
        CPF apenas com dígitos.
    """
    return re.sub(r"\D", "", cpf)


def limpar_cnpj(cnpj: str) -> str:
    """
    Remove formatação do CNPJ, retornando apenas dígitos.

    Args:
        cnpj: CNPJ em qualquer formato.

    Returns:
        CNPJ apenas com dígitos.
    """
    return re.sub(r"\D", "", cnpj)


def limpar_telefone(telefone: str) -> str:
    """
    Remove formatação do telefone, retornando apenas dígitos.

    Args:
        telefone: Telefone em qualquer formato.

    Returns:
        Telefone apenas com dígitos.
    """
    return re.sub(r"\D", "", telefone)
