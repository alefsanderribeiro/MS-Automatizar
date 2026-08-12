"""
Utilitários para manipulação e validação de telefones brasileiros
Normaliza diferentes formatos para o padrão do WhatsApp
"""

import re
import unicodedata
from typing import Optional, Tuple
from src.utils.logger_config import logger


# DDDs válidos do Brasil (por região)
DDDS_VALIDOS = {
    # Região Sudeste
    '11', '12', '13', '14', '15', '16', '17', '18', '19',  # São Paulo
    '21', '22', '24',  # Rio de Janeiro
    '27', '28',  # Espírito Santo
    '31', '32', '33', '34', '35', '37', '38',  # Minas Gerais
    # Região Sul
    '41', '42', '43', '44', '45', '46',  # Paraná
    '47', '48', '49',  # Santa Catarina
    '51', '53', '54', '55',  # Rio Grande do Sul
    # Região Centro-Oeste
    '61',  # Distrito Federal
    '62', '64',  # Goiás
    '63',  # Tocantins
    '65', '66',  # Mato Grosso
    '67',  # Mato Grosso do Sul
    # Região Nordeste
    '71', '73', '74', '75', '77',  # Bahia
    '79',  # Sergipe
    '81', '87',  # Pernambuco
    '82',  # Alagoas
    '83',  # Paraíba
    '84',  # Rio Grande do Norte
    '85', '88',  # Ceará
    '86', '89',  # Piauí
    # Região Norte
    '91', '93', '94',  # Pará
    '92', '97',  # Amazonas
    '95',  # Roraima
    '96',  # Amapá
    '68',  # Acre
    '69',  # Rondônia
    '98', '99',  # Maranhão
}


def limpar_telefone(telefone: str) -> str:
    """
    Remove todos os caracteres não numéricos do telefone
    
    Args:
        telefone: Telefone em qualquer formato
    
    Returns:
        Apenas os dígitos do telefone
    """
    if not telefone:
        return ""
    return re.sub(r'\D', '', telefone)


def normalizar_telefone(telefone: str) -> Optional[str]:
    """
    Normaliza telefone para o formato do WhatsApp: 5511999999999@s.whatsapp.net
    
    Aceita variações:
    - 55 81 9187-4184
    - +5581918741184
    - 81918741184
    - 81 91874-1184
    - (81) 91874-1184
    - 9187-4184 (adiciona DDD padrão se configurado)
    
    Args:
        telefone: Telefone em qualquer formato
    
    Returns:
        Telefone normalizado no formato WhatsApp ou None se inválido
    """
    if not telefone:
        logger.warning("Telefone vazio fornecido")
        return None
    
    # Limpar telefone
    digitos = limpar_telefone(telefone)
    
    if not digitos:
        logger.warning(f"Telefone inválido (sem dígitos): {telefone}")
        return None
    
    # Remover código de país se presente (55)
    if digitos.startswith('55') and len(digitos) >= 12:
        digitos = digitos[2:]
    
    # Validar tamanho (DDD + número)
    # Celular: 11 dígitos (DDD + 9 + 8 dígitos)
    # Fixo: 10 dígitos (DDD + 8 dígitos)
    if len(digitos) < 10 or len(digitos) > 11:
        logger.warning(f"Telefone com tamanho inválido ({len(digitos)} dígitos): {telefone}")
        return None
    
    # Extrair DDD
    ddd = digitos[:2]
    
    # Validar DDD
    if ddd not in DDDS_VALIDOS:
        logger.warning(f"DDD inválido ({ddd}): {telefone}")
        return None
    
    # Montar número completo com código do país
    numero_completo = f"55{digitos}"
    
    # Formato WhatsApp
    telefone_whatsapp = f"{numero_completo}@s.whatsapp.net"
    
    logger.debug(f"Telefone normalizado: {telefone} -> {telefone_whatsapp}")
    return telefone_whatsapp


def extrair_numero_sem_sufixo(telefone_whatsapp: str) -> str:
    """
    Extrai apenas o número do formato WhatsApp
    
    Args:
        telefone_whatsapp: Telefone no formato 5511999999999@s.whatsapp.net
    
    Returns:
        Apenas os dígitos (5511999999999)
    """
    if not telefone_whatsapp:
        return ""
    return telefone_whatsapp.replace('@s.whatsapp.net', '')


def validar_telefone(telefone: str) -> Tuple[bool, str]:
    """
    Valida se o telefone é válido
    
    Args:
        telefone: Telefone em qualquer formato
    
    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    if not telefone:
        return False, "Telefone vazio"
    
    digitos = limpar_telefone(telefone)
    
    if not digitos:
        return False, "Telefone não contém dígitos"
    
    # Remover código de país se presente
    if digitos.startswith('55') and len(digitos) >= 12:
        digitos = digitos[2:]
    
    # Validar tamanho
    if len(digitos) < 10:
        return False, f"Telefone muito curto ({len(digitos)} dígitos)"
    
    if len(digitos) > 11:
        return False, f"Telefone muito longo ({len(digitos)} dígitos)"
    
    # Validar DDD
    ddd = digitos[:2]
    if ddd not in DDDS_VALIDOS:
        return False, f"DDD inválido ({ddd})"
    
    # Validar se celular tem 9 na frente (obrigatório desde 2016)
    if len(digitos) == 11:
        primeiro_digito_numero = digitos[2]
        if primeiro_digito_numero != '9':
            return False, "Celular deve começar com 9 após o DDD"
    
    return True, "Válido"


def formatar_para_exibicao(telefone: str) -> str:
    """
    Formata telefone para exibição amigável
    
    Args:
        telefone: Telefone em qualquer formato
    
    Returns:
        Telefone formatado: +55 (81) 91874-1184
    """
    if not telefone:
        return ""
    
    # Se já está no formato WhatsApp, extrair número
    if '@s.whatsapp.net' in telefone:
        telefone = extrair_numero_sem_sufixo(telefone)
    
    digitos = limpar_telefone(telefone)
    
    if not digitos:
        return telefone  # Retorna original se não conseguir processar
    
    # Remover código de país se presente
    tem_codigo_pais = False
    if digitos.startswith('55') and len(digitos) >= 12:
        tem_codigo_pais = True
        digitos = digitos[2:]
    
    # Formatar baseado no tamanho
    if len(digitos) == 11:  # Celular
        ddd = digitos[:2]
        parte1 = digitos[2:7]
        parte2 = digitos[7:]
        if tem_codigo_pais:
            return f"+55 ({ddd}) {parte1}-{parte2}"
        return f"({ddd}) {parte1}-{parte2}"
    
    elif len(digitos) == 10:  # Fixo
        ddd = digitos[:2]
        parte1 = digitos[2:6]
        parte2 = digitos[6:]
        if tem_codigo_pais:
            return f"+55 ({ddd}) {parte1}-{parte2}"
        return f"({ddd}) {parte1}-{parte2}"
    
    return telefone  # Retorna original se formato não reconhecido


def parsear_multiplos_telefones(texto: str, separadores: str = ",;") -> list[str]:
    """
    Parseia múltiplos telefones de uma string
    
    Args:
        texto: String com telefones separados
        separadores: Caracteres separadores (default: vírgula e ponto-vírgula)
    
    Returns:
        Lista de telefones normalizados (formato WhatsApp)
    """
    if not texto:
        return []
    
    # Criar regex para split
    pattern = f"[{re.escape(separadores)}]"
    telefones_raw = re.split(pattern, texto)
    
    telefones_normalizados = []
    for tel in telefones_raw:
        tel = tel.strip()
        if tel:
            normalizado = normalizar_telefone(tel)
            if normalizado:
                telefones_normalizados.append(normalizado)
            else:
                logger.warning(f"Telefone ignorado (inválido): {tel}")
    
    return telefones_normalizados
