"""
Utilitários para sanitização e auto-cadastro de funcionários
Trata caracteres especiais e cria registros incompletos que serão completados depois
"""

import re
import logging
import unicodedata
from typing import Optional, Tuple
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


class SanitizadorFuncionario:
    """
    Sanitiza nomes de funcionários extraídos do PDF
    Remove/substitui caracteres que causam problemas no MongoDB
    """
    
    # Caracteres que causam problemas no MongoDB
    CARACTERES_PERIGOSOS = {
        '†': 't',
        '‡': 't',
        '§': 's',
        '¶': 'p',
        '†': 't',
        '°': 'o',
        '·': '.',
        '¹': '1',
        '²': '2',
        '³': '3',
        '¼': '1/4',
        '½': '1/2',
        '¾': '3/4',
        '¿': '?',
        '¡': '!',
        'ª': 'a',
        'º': 'o',
    }
    
    # Padrões regex para validação
    REGEX_NOME_VALIDO = re.compile(
        r"^[a-záéíóúàâêôãõü\s\-'\.]+$",
        re.IGNORECASE | re.UNICODE
    )
    
    @staticmethod
    def remover_acentos(texto: str) -> str:
        """Remove acentos do texto mantendo caracteres válidos"""
        if not texto:
            return ""
        
        nfkd = unicodedata.normalize('NFKD', texto)
        return ''.join([c for c in nfkd if not unicodedata.combining(c)])
    
    @staticmethod
    def remover_caracteres_especiais(texto: str, permitir_acentos: bool = True) -> str:
        """
        Remove caracteres especiais perigosos
        
        Args:
            texto: Texto a limpar
            permitir_acentos: Se False, remove acentos também
        
        Returns:
            Texto limpo
        """
        if not texto:
            return ""
        
        # Substituir caracteres perigosos conhecidos
        for char_perigoso, substituto in SanitizadorFuncionario.CARACTERES_PERIGOSOS.items():
            texto = texto.replace(char_perigoso, substituto)
        
        # Se não permitir acentos, remover
        if not permitir_acentos:
            texto = SanitizadorFuncionario.remover_acentos(texto)
        
        # Remover outros caracteres especiais (mantém espaços, hífens, pontos)
        # Padrão: aceita letras, acentos, números, espaços, hífens, pontos e apóstrofos
        texto = re.sub(
            r"[^a-záéíóúàâêôãõü0-9\s\-'\.]+",
            "",
            texto,
            flags=re.IGNORECASE | re.UNICODE
        )
        
        # Remover espaços múltiplos
        texto = re.sub(r"\s+", " ", texto)
        
        # Remover espaços nas extremidades
        texto = texto.strip()
        
        return texto
    
    @staticmethod
    def limpar_nome(nome: str, modo_rígido: bool = False) -> str:
        """
        Limpa e valida nome do funcionário
        
        Args:
            nome: Nome bruto do PDF
            modo_rígido: Se True, remove acentos também
        
        Returns:
            Nome limpo e válido
        
        Raises:
            ValueError: Se nome não for válido após limpeza
        """
        if not nome or not nome.strip():
            raise ValueError("Nome não pode ser vazio")
        
        # Limpar caracteres especiais
        nome_limpo = SanitizadorFuncionario.remover_caracteres_especiais(
            nome,
            permitir_acentos=not modo_rígido
        )
        
        # Validar
        if not nome_limpo or len(nome_limpo) < 3:
            raise ValueError(f"Nome muito curto após limpeza: {nome} -> {nome_limpo}")
        
        # Capitalizar corretamente (primeira letra de cada palavra)
        nome_limpo = ' '.join(
            palavra.capitalize()
            for palavra in nome_limpo.split()
        )
        
        # Validação final
        if not SanitizadorFuncionario.REGEX_NOME_VALIDO.match(nome_limpo):
            raise ValueError(f"Nome contém caracteres inválidos: {nome_limpo}")
        
        return nome_limpo
    
    @staticmethod
    def limpar_funcao(funcao: str) -> str:
        """Limpa campo função (similar a nome)"""
        if not funcao or not funcao.strip():
            return "Não Especificado"
        
        funcao_limpa = SanitizadorFuncionario.remover_caracteres_especiais(
            funcao,
            permitir_acentos=True
        )
        
        # Capitalizar
        funcao_limpa = ' '.join(
            palavra.capitalize()
            for palavra in funcao_limpa.split()
        )
        
        return funcao_limpa if funcao_limpa else "Não Especificado"
    
    @staticmethod
    def limpar_lotacao(lotacao: str) -> str:
        """Limpa campo lotação"""
        if not lotacao or not lotacao.strip():
            return "Sem Lotação"
        
        lotacao_limpa = SanitizadorFuncionario.remover_caracteres_especiais(
            lotacao,
            permitir_acentos=True
        )
        
        lotacao_limpa = ' '.join(
            palavra.capitalize()
            for palavra in lotacao_limpa.split()
        )
        
        return lotacao_limpa if lotacao_limpa else "Sem Lotação"
    
    @staticmethod
    def limpar_empresa(empresa: str) -> str:
        """Limpa campo empresa"""
        if not empresa or not empresa.strip():
            return "Empresa Desconhecida"
        
        # Permitir também números e pontos (para CNPJ)
        empresa_limpa = re.sub(
            r"[^a-záéíóúàâêôãõü0-9\s\-'\.\/]+",
            "",
            empresa,
            flags=re.IGNORECASE | re.UNICODE
        )
        
        empresa_limpa = re.sub(r"\s+", " ", empresa_limpa).strip()
        
        return empresa_limpa if empresa_limpa else "Empresa Desconhecida"


class ConstrutorFuncionarioIncompleto:
    """
    Constrói funcionário incompleto a partir de dados do PDF
    Marca como "incompleto" para revisão manual posterior
    """
    
    @staticmethod
    def criar_do_pdf(
        nome_pdf: str,
        empresa_extraida: str,
        funcionario_nome_extraido: str,
        funcionario_funcao: Optional[str] = None,
        mes_ano: Optional[str] = None,
        modo_rígido: bool = False
    ) -> Tuple[dict, list]:
        """
        Cria estrutura de funcionário incompleto a partir de extração PDF
        
        Args:
            nome_pdf: Nome do arquivo PDF (para rastreamento)
            empresa_extraida: Empresa extraída do PDF
            funcionario_nome_extraido: Nome extraído do PDF
            funcionario_funcao: Função extraída (opcional)
            mes_ano: Mês/ano da folha (para referência)
            modo_rígido: Se True, remove acentos
        
        Returns:
            Tupla (dicionário_funcionario, lista_erros)
            - dicionário_funcionario: Estrutura pronta para inserção
            - lista_erros: Lista de problemas encontrados durante sanitização
        """
        erros = []
        
        try:
            # Sanitizar nome
            try:
                nome_limpo = SanitizadorFuncionario.limpar_nome(
                    funcionario_nome_extraido,
                    modo_rígido=modo_rígido
                )
            except ValueError as e:
                erros.append(f"Erro ao limpar nome: {str(e)}")
                # Usar nome original se falhar
                nome_limpo = funcionario_nome_extraido.strip()[:100] if funcionario_nome_extraido else "Sem Nome"
            
            # Sanitizar empresa
            try:
                empresa_limpa = SanitizadorFuncionario.limpar_empresa(empresa_extraida)
            except Exception as e:
                erros.append(f"Erro ao limpar empresa: {str(e)}")
                empresa_limpa = empresa_extraida.strip()[:100] if empresa_extraida else "Empresa Desconhecida"
            
            # Sanitizar função
            try:
                funcao_limpa = SanitizadorFuncionario.limpar_funcao(funcionario_funcao or "")
            except Exception as e:
                erros.append(f"Erro ao limpar função: {str(e)}")
                funcao_limpa = funcionario_funcao.strip()[:100] if funcionario_funcao else "Não Especificado"
            
            # Normalizar nome para índice
            nfkd = unicodedata.normalize('NFKD', nome_limpo)
            nome_normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)]).lower()
            
            # Construir documento
            funcionario_doc = {
                "nome": nome_limpo,
                "nome_normalizado": nome_normalizado,
                "funcao": funcao_limpa,
                "lotacao": "Pendente Definição",  # Será preenchido depois
                "contrato": "CLT",  # Padrão
                "empresa": empresa_limpa,
                "pis": None,  # Não extraído do PDF
                "cpf": None,  # Não extraído do PDF
                "horario_trabalho": None,  # Não extraído do PDF
                "data_admissao": None,  # Não extraído do PDF
                "status": "ativo",
                
                # Metadados de origem
                "origem_pdf": nome_pdf,
                "origem_mes": mes_ano,
                "incompleto": True,  # FLAG importante
                "incompleto_motivo": "Auto-cadastrado do PDF - aguardando completação",
                "incompleto_campos": [
                    "lotacao",
                    "pis",
                    "cpf",
                    "horario_trabalho",
                    "data_admissao"
                ],
                "erros_sanitizacao": erros,
            }
            
            return funcionario_doc, erros
        
        except Exception as e:
            logger.error(f"Erro ao criar funcionário incompleto: {e}")
            erros.append(f"Erro geral: {str(e)}")
            
            # Retornar estrutura mínima mesmo com erro
            return {
                "nome": funcionario_nome_extraido.strip()[:100],
                "nome_normalizado": funcionario_nome_extraido.lower().strip()[:100],
                "funcao": "Erro na Sanitização",
                "lotacao": "Pendente Definição",
                "contrato": "CLT",
                "empresa": empresa_extraida.strip()[:100],
                "incompleto": True,
                "incompleto_motivo": f"Erro ao processar: {str(e)}",
                "incompleto_campos": ["nome", "funcao", "lotacao", "pis", "cpf"],
                "erros_sanitizacao": erros,
                "origem_pdf": nome_pdf,
            }, erros


def exemplo_uso():
    """Exemplos de uso dos utilitários"""
    
    print("="*80)
    print("EXEMPLOS: Sanitizador de Funcionário")
    print("="*80)
    
    # Exemplo 1: Limpar nome com caracteres especiais
    print("\n1. Limpar nome com caracteres especiais:")
    nomes_teste = [
        "JOÃO†SILVA",
        "MARIA·SANTOS",
        "JOSÉ‡OLIVEIRA",
        "FRANCISCA§DA§SILVA",
    ]
    for nome in nomes_teste:
        try:
            limpo = SanitizadorFuncionario.limpar_nome(nome)
            print(f"  {nome:30s} -> {limpo}")
        except ValueError as e:
            print(f"  {nome:30s} -> ERRO: {e}")
    
    # Exemplo 2: Criar funcionário incompleto
    print("\n2. Criar funcionário incompleto do PDF:")
    
    func_doc, erros = ConstrutorFuncionarioIncompleto.criar_do_pdf(
        nome_pdf="Folha de Ponto - JOÃO SILVA.pdf",
        empresa_extraida="SOLUCOES DINAMICAS†SERVIÇOS",
        funcionario_nome_extraido="JOÃO†DA·SILVA",
        funcionario_funcao="ANALISTA†DE†SISTEMAS",
        mes_ano="2025-11"
    )
    
    print(f"  Documento criado:")
    for chave, valor in func_doc.items():
        print(f"    {chave:25s}: {valor}")
    
    if erros:
        print(f"  Erros encontrados:")
        for erro in erros:
            print(f"    - {erro}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    exemplo_uso()
