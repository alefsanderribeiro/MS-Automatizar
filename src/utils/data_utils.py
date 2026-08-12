"""
Utilitários centrais de conversão e formatação de datas.

O projeto MS-Automatizar armazena datas em formato canônico (datetime nativo
do MongoDB / ISO interno) para preservar ordenação, comparação e filtros.
A conversão para o formato brasileiro acontece **nas bordas**: na ENTRADA
(CLI/interfaces, que aceitam DD/MM/YYYY) e na EXIBIÇÃO (DD/MM/YYYY).

Convenções:
- ENTRADA flexível: aceita `DD/MM/YYYY` e `YYYY-MM-DD` (ISO), além de
  variantes com hora (`YYYY-MM-DDTHH:MM:SS`). Se o texto contém `/` →
  interpretado como DD/MM/YYYY (padrão brasileiro). Se contém `-` com
  4 dígitos no início → ISO/YYYY-MM-DD. Ambíguo como `01/02/2026` é sempre
  dia/mês/ano (1 de fevereiro).
- EXIBIÇÃO: sempre `DD/MM/YYYY` (`formatar_data_br`).
"""

from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import Optional, Union


# ---------------------------------------------------------------------------
# ENTRADA — parsing flexível
# ---------------------------------------------------------------------------

def parse_data_flexivel(
    texto: Optional[str],
    *,
    retornar_date: bool = False,
) -> Optional[Union[date, datetime]]:
    """
    Converte um texto de data em objeto `date` ou `datetime`.

    Aceita os formatos:
      - `DD/MM/YYYY` (padrão brasileiro) — ex: `15/08/2026`
      - `DD/MM/YY` (2 dígitos no ano, p.ex. `15/08/26` → 2026)
      - `DD/MM/YYYY HH:MM[:SS]` — ex: `15/08/2026 09:30`
      - `YYYY-MM-DD` (ISO) — ex: `2026-08-15` (também com 1 dígito: `2026-8-5`)
      - `YYYY-MM-DDTHH:MM[:SS]` (ISO com hora) — ex: `2026-08-15T09:30:00`

    **Recusado** (retorna `None`): datas impossíveis/inválidas como `32/13/2026`,
    `2026-13-45`, textos sem formato de data (`abc`), e datas em formato `YYYY/DD/MM`
    (barras invertidas no estilo americano, p.ex. `2026/08/15`).

    Heurística de desambiguação (ex: `01/02/2026`):
      - contém `/`        -> DD/MM/YYYY (dia/mês/ano).
      - contém `-` e o 1º campo tem 4 dígitos -> ISO (YYYY-MM-DD).

    Args:
        texto: String a converter. `None`/vazio retorna `None`.
        retornar_date: Se `True`, retorna `date.day`; caso contrário retorna
            `datetime`. Datas sem hora viram datetime à meia-noite.

    Returns:
        Objeto `date` (se `retornar_date=True`) ou `datetime`, ou `None`
        caso a string seja vazia ou inválida.
    """
    if not texto:
        return None

    texto = texto.strip()
    if not texto:
        return None

    parcela_data = texto
    # Separa a data da hora (aceita espaço ou 'T' como separador).
    m = re.match(r"^(.+?)[ T](\d{1,2}:\d{2}(?::\d{2})?)$", texto)
    hora_str = None
    if m:
        parcela_data, hora_str = m.group(1), m.group(2)

    dt: Optional[datetime] = None

    # Formato brasileiro: contém '/'
    if "/" in parcela_data:
        # Tenta DD/MM/YYYY primeiro (padrão brasileiro).
        dt = _tentar(parcela_data, "%d/%m/%Y")
        if dt is None:
            # Fallback genérico (cobre, p.ex., um único dígito em dia/mês).
            dt = _tentar(parcela_data, "%d/%m/%Y", lenient=True)
        if dt is None:
            # Ano com 2 dígitos: 15/08/26 -> 15/08/2026.
            dt = _tentar(parcela_data, "%d/%m/%y")

    # Formato ISO: 'YYYY-MM-DD' (4 dígitos no início) — ou já veio com '-'
    elif re.match(r"^\d{4}-\d{1,2}-\d{1,2}", parcela_data):
        dt = _tentar(parcela_data, "%Y-%m-%d")
        if dt is None and "T" in texto:
            dt = _tentar(texto, "%Y-%m-%dT%H:%M:%S")
        if dt is None and "T" in texto:
            dt = _tentar(texto, "%Y-%m-%dT%H:%M")
        if dt is None:
            # ISO com 1 dígito em dia/mês (ex: 2026-8-5). `date.fromisoformat`
            # aceita 1 dígito; aqui parseamos só a parcela da data.
            try:
                dt = datetime.combine(date.fromisoformat(parcela_data), time.min)
            except ValueError:
                dt = None
    else:
        # Sem separador óbvio: tenta DD/MM/YYYY por último (nenhum "/" mas
        # poderia ser "15082026"? improvável) e também DD-MM-YYYY.
        dt = _tentar(parcela_data, "%d-%m-%Y")

    if dt is None:
        return None

    # Aplica a hora, se fornecida junto.
    if hora_str:
        hh, mm = hora_str.split(":")[0], hora_str.split(":")[1]
        ss = hora_str.split(":")[2] if len(hora_str.split(":")) > 2 else "00"
        try:
            dt = dt.replace(hour=int(hh), minute=int(mm), second=int(ss))
        except ValueError:
            dt = None

    if dt is None:
        return None

    if retornar_date:
        return dt.date()
    return dt


def _tentar(valor: str, formato: str, *, lenient: bool = False) -> Optional[datetime]:
    """Tenta parsear com `formato`. Se `lenient`, permite 1 dígito em dia/mês."""
    if lenient:
        # Converte '1/2/2026' para '01/02/2026' e reusa o formato estrito.
        partes = valor.split("/")
        if len(partes) == 3 and len(partes[2]) == 4:
            try:
                valor = f"{int(partes[0]):02d}/{int(partes[1]):02d}/{int(partes[2]):04d}"
            except ValueError:
                return None
            formato = "%d/%m/%Y"
    try:
        return datetime.strptime(valor, formato)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# EXIBIÇÃO — formatação brasileira
# ---------------------------------------------------------------------------

def formatar_data_br(data_obj: Optional[Union[date, datetime, str]]) -> str:
    """
    Formata uma data como `DD/MM/YYYY` para exibição.

    Aceita `date`, `datetime` ou string. Strings já em `DD/MM/YYYY` são
    devolvidas como estão; `YYYY-MM-DD`/ISO são convertidas.

    Args:
        data_obj: Objeto date/datetime ou string.

    Returns:
        String `DD/MM/YYYY`, ou `""` se vazio, ou o valor original se não
        for possível interpretar.
    """
    if data_obj is None:
        return ""
    if hasattr(data_obj, "strftime"):
        return data_obj.strftime("%d/%m/%Y")

    # Strings
    texto = str(data_obj).strip()
    if not texto:
        return ""
    # Já está em DD/MM/YYYY?
    if re.match(r"^\d{2}/\d{2}/\d{4}$", texto):
        return texto
    # Tenta converter de outro formato.
    dt = parse_data_flexivel(texto)
    if dt is not None:
        return dt.strftime("%d/%m/%Y")
    return texto


def formatar_data_hora_br(data_obj: Optional[Union[date, datetime, str]]) -> str:
    """Formata date/datetime como `DD/MM/YYYY HH:MM` (ou `DD/MM/YYYY` se só date)."""
    if data_obj is None:
        return ""
    if hasattr(data_obj, "strftime"):
        if isinstance(data_obj, datetime) and (data_obj.hour or data_obj.minute or data_obj.second):
            return data_obj.strftime("%d/%m/%Y %H:%M")
        return data_obj.strftime("%d/%m/%Y")
    dt = parse_data_flexivel(str(data_obj))
    if dt is not None:
        return formatar_data_hora_br(dt)
    return str(data_obj)


def date_para_datetime_inicio(data_obj: date) -> datetime:
    """Converte date em datetime à meia-noite (início do dia) — útil p/ queries $gte."""
    return datetime.combine(data_obj, time.min)


def date_para_datetime_fim(data_obj: date) -> datetime:
    """Converte date em datetime ao fim do dia (23:59:59.999999) — útil p/ queries $lte."""
    return datetime.combine(data_obj, time.max)
