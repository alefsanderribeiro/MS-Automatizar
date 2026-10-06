"""Utilitários para extração robusta de JSON de respostas de IA.

Modelos de chat (OpenAI-compatible, Mistral, etc.) às vezes embrulham o JSON em
texto explicativo ou em blocos de código ```json ...```. Esta função tenta
recuperar o primeiro objeto JSON válido da resposta.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional


def extrair_json(texto: Optional[str]) -> Optional[Any]:
    """Extrai o primeiro objeto/array JSON válido de um texto.

    Estratégias, em ordem:
    1. ``json.loads`` direto no texto completo;
    2. conteúdo de um bloco de código ```json ... ``` ou ``` ... ```;
    3. primeiro ``{ ... }`` balanceado encontrado no texto.

    Args:
        texto: Texto retornado pelo modelo.

    Returns:
        Objeto Python desserializado ou ``None`` se nada válido for encontrado.
    """
    if not texto or not isinstance(texto, str):
        return None

    texto = texto.strip()

    # 1. JSON puro
    try:
        return json.loads(texto)
    except Exception:
        pass

    # 2. Bloco de código
    match = re.search(r"```(?:json)?\s*(.+?)\s*```", texto, re.DOTALL | re.IGNORECASE)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    # 3. Primeiro objeto balanceado
    inicio = texto.find("{")
    if inicio != -1:
        profundidade = 0
        for i in range(inicio, len(texto)):
            if texto[i] == "{":
                profundidade += 1
            elif texto[i] == "}":
                profundidade -= 1
                if profundidade == 0:
                    try:
                        return json.loads(texto[inicio : i + 1])
                    except Exception:
                        break

    return None
