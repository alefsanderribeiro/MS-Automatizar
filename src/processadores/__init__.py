"""
Processadores para automação de Folha de Ponto
Orquestração completa do pipeline: arquivo → Gemini → Pydantic → Lookup → MongoDB
"""

from .processador_folha_ponto import ProcessadorFolhaPonto, ProcessarResultado

__all__ = [
    "ProcessadorFolhaPonto",
    "ProcessarResultado",
]
