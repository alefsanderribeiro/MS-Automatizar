"""Conversão de PDF → imagem 100% cross-platform (Windows + Linux).

Substitui o uso de ``pdf2image`` + ``poppler`` (programa externo com path Windows
hardcoded) por uma biblioteca embutida no Python: **pypdfium2** (bindings do
PDFium/Chromium). Os wheels do pypdfium2 já trazem o PDFium embutido, então
funciona nos dois SO com apenas ``pip install pypdfium2`` — sem instalar
poppler e sem path hardcoded.

A API exposta é compatível com o que o sistema esperava de pdf2image:
retorna uma lista de imagens **PIL em memória** (uma por página).

Modo de uso:
    from src.utils.pdf_conversor import converter_pdf_para_imagens
    imagens = converter_pdf_para_imagens(arquivo_pdf, dpi=200)
    imagens[0].save("pagina.png", "PNG")
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Union

from src.utils.logger_config import logger

try:
    import pypdfium2 as _pdfium
    PYPDFIUM_DISPONIVEL = True
except ImportError:  # pragma: no cover - depende do ambiente
    _pdfium = None
    PYPDFIUM_DISPONIVEL = False
    logger.warning(
        "pypdfium2 não instalado. Instale com: pip install pypdfium2 "
        "(necessário para converter PDF → imagem sem programa externo)"
    )


def converter_pdf_para_imagens(
    arquivo_pdf: Union[str, Path],
    dpi: float = 200.0,
) -> List[object]:
    """Converte um PDF para uma lista de imagens PIL em memória.

    Args:
        arquivo_pdf: Caminho do arquivo PDF.
        dpi: Resolução alvo (o sistema usava 200 para leitura de manuscrito).

    Returns:
        Lista de objetos PIL.Image (um por página), em memória, prontos para
        ``.save()`` ou uso direto por OCR/IA.

    Raises:
        FileNotFoundError: Se o arquivo não existir.
        RuntimeError: Se a conversão falhar (incluindo pypdfium2 não instalado).
    """
    caminho = Path(arquivo_pdf)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {caminho}")

    if not PYPDFIUM_DISPONIVEL:
        raise RuntimeError(
            "pypdfium2 não está instalado. Execute: pip install pypdfium2 "
            "para habilitar a conversão de PDF para imagem."
        )

    try:
        doc = _pdfium.PdfDocument(str(caminho))
    except Exception as e:  # pragma: no cover - depende do PDF
        raise RuntimeError(f"Falha ao abrir PDF {caminho}: {e}")

    imagens: List[object] = []
    try:
        # 72 pontos de base por polegada no PDFium; dpi define a escala
        scale = float(dpi) / 72.0
        total = len(doc)
        for i in range(total):
            pagina = doc[i]
            try:
                bitmap = pagina.render(scale=scale)
                try:
                    pil = bitmap.to_pil()
                finally:
                    bitmap.close()
                imagens.append(pil)
            finally:
                pagina.close()
        logger.debug(f"✓ {total} página(s) convertida(s) em {dpi} DPI: {caminho.name}")
        return imagens
    except Exception as e:  # pragma: no cover - depende do PDF
        raise RuntimeError(f"Erro ao renderizar PDF {caminho}: {e}")
    finally:
        doc.close()
