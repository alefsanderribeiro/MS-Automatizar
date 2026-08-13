from src.utils.data_utils import parse_data_flexivel


def bool_type(string):
    """Interpreta um valor como booleano (uso em argparse).

    Aceita: "true"/"True"/"1"/"yes"/"sim" → True
            "false"/"False"/"0"/"no"/"nao"/"não" → False
    Qualquer outro valor levanta ValueError (pra argparse reportar erro).
    """
    if isinstance(string, bool):
        return string
    texto = str(string).strip().lower()
    if texto in ("true", "1", "yes", "sim", "verdadeiro", "v"):
        return True
    if texto in ("false", "0", "no", "nao", "não", "falso", "f"):
        return False
    raise ValueError(f"Valor booleano inválido: {string!r}")


def date_type(string):
    """Interpreta um valor como data (uso em argparse).

    Aceita tanto DD/MM/YYYY (padrão brasileiro, ex: 15/08/2026) quanto
    YYYY-MM-DD (ISO, ex: 2026-08-15) para não quebrar scripts existentes.
    Retorna um objeto `date`.
    """
    valor = parse_data_flexivel(string, retornar_date=True)
    if valor is None:
        raise ValueError(
            f"Data inválida: {string!r}. Use DD/MM/YYYY (ex: 15/08/2026) "
            "ou YYYY-MM-DD (ex: 2026-08-15)."
        )
    return valor

def list_type(string):
    if "," in string:
        return [str(x.strip(r"[]' ")) for x in string.split(',')]
    else:
        return string
