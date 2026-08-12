from datetime import datetime


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
    return datetime.strptime(string, '%Y-%m-%d').date()

def list_type(string):
    if "," in string:
        return [str(x.strip(r"[]' ")) for x in string.split(',')]
    else:
        return string
