"""
Service para leitura e processamento da Planilha de Contatos
Responsabilidades:
- Carregar planilha Excel
- Parsear linhas com configurações de envio
- Montar diretórios completos
- Validar dados
"""

import os
from typing import Dict, Any, Optional, List, Generator
from datetime import datetime
from pathlib import Path
import dotenv

from src.utils.dotenv_path import caminho_dotenv
from src.utils.logger_config import logger
from src.utils.telefone_utils import parsear_multiplos_telefones

# Tentativa de importação do pandas
try:
    import pandas as pd
    PANDAS_DISPONIVEL = True
except ImportError:
    PANDAS_DISPONIVEL = False
    logger.warning("Pandas não instalado - PlanilhaContatosService não funcionará")


class PlanilhaContatosService:
    r"""
    Lê e processa a Planilha de Contatos para envio de folhas de ponto
    
    Colunas esperadas na planilha:
    - ID: Identificador único
    - NOME COMPLETO: Nome do contato
    - EMAIL: E-mail(s) separados por , ou ;
    - TELEFONE: Telefone(s) separados por , ou ;
    - GRUPO WHATSAPP: Nome(s) do(s) grupo(s) separados por , ou ;
    - ENVIAR EMAIL: S/N
    - ENVIAR WHATSAPP: S/N
    - ENVIAR GRUPO WHATSAPP: S/N
    - ENVIAR IMPRESSO: S/N (para referência, não usado no envio digital)
    - EMPRESA: Nome da empresa
    - LOCAL - CONTRATO - POLO: Local de trabalho
    - DIRETÓRIO GERAL: Caminho base (ex: Z:\04. PESSOAL\FOLHA PONTO)
    - DIRETÓRIO ESPECÍFICO: Subpasta específica (ex: 01. MS SERVIÇOS\ADMINISTRATIVO)
    """
    
    # Colunas obrigatórias
    COLUNAS_OBRIGATORIAS = [
        "ID",
        "NOME COMPLETO",
        "EMAIL",
        "TELEFONE",
        "GRUPO WHATSAPP",
        "ENVIAR EMAIL",
        "ENVIAR WHATSAPP",
        "ENVIAR GRUPO WHATSAPP",
        "EMPRESA",
        "LOCAL - CONTRATO - POLO",
        "DIRETÓRIO GERAL",
        "DIRETÓRIO ESPECÍFICO"
    ]
    
    # Valores que significam "Sim"
    VALORES_SIM = ["S", "SIM", "YES", "Y", "1", "TRUE", "X"]
    
    def __init__(self, planilha_path: str = None):
        """
        Inicializa o service
        
        Args:
            planilha_path: Caminho da planilha. Se None, usa caminho padrão do .env
        """
        self._planilha_path = planilha_path or self._obter_caminho_padrao()
        self._df: Optional[pd.DataFrame] = None
        self._disponivel = PANDAS_DISPONIVEL
    
    def _obter_caminho_padrao(self) -> str:
        """Obtém caminho padrão da planilha"""
        import os
        env_path = caminho_dotenv()
        dotenv.load_dotenv(env_path, override=True)
        
        # Tentar do .env
        caminho = os.getenv("PLANILHA_CONTATOS_PATH")
        
        if not caminho:
            # Caminho padrão dentro do projeto
            base_dir = Path(__file__).parent.parent
            caminho = str(base_dir / "data" / "models" / "planilha_contatos.xlsx")
        
        return caminho
    
    @property
    def disponivel(self) -> bool:
        return self._disponivel
    
    @property
    def planilha_path(self) -> str:
        return self._planilha_path
    
    def carregar(self, sheet_name: str = 0) -> bool:
        """
        Carrega a planilha em memória
        
        Args:
            sheet_name: Nome ou índice da aba (default: primeira aba)
        
        Returns:
            True se carregou com sucesso
        """
        if not self._disponivel:
            logger.error("Pandas não disponível")
            return False
        
        if not os.path.exists(self._planilha_path):
            logger.error(f"Planilha não encontrada: {self._planilha_path}")
            return False
        
        try:
            self._df = pd.read_excel(
                self._planilha_path,
                sheet_name=sheet_name,
                dtype=str  # Ler tudo como string para evitar problemas
            )
            
            # Normalizar nomes das colunas (remover espaços extras, uppercase)
            self._df.columns = self._df.columns.str.strip().str.upper()
            
            # Verificar colunas obrigatórias
            colunas_faltando = [
                col for col in self.COLUNAS_OBRIGATORIAS 
                if col not in self._df.columns
            ]
            
            if colunas_faltando:
                logger.error(f"Colunas faltando na planilha: {', '.join(colunas_faltando)}")
                return False
            
            # Limpar valores NaN
            self._df = self._df.fillna("")
            
            logger.info(f"✓ Planilha carregada: {len(self._df)} linhas de '{self._planilha_path}'")
            return True
        
        except Exception as e:
            logger.error(f"Erro ao carregar planilha: {e}")
            return False
    
    def _valor_booleano(self, valor: Any) -> bool:
        """Converte valor para booleano"""
        if pd.isna(valor) or valor is None:
            return False
        
        return str(valor).strip().upper() in self.VALORES_SIM
    
    def _parsear_lista(self, valor: Any) -> List[str]:
        """
        Parseia valor separado por , ou ; em lista
        
        Args:
            valor: Valor da célula
        
        Returns:
            Lista de valores limpos (sem vazios)
        """
        if pd.isna(valor) or not valor:
            return []
        
        texto = str(valor).strip()
        
        # Tentar separar por ; primeiro, depois por ,
        if ";" in texto:
            itens = texto.split(";")
        else:
            itens = texto.split(",")
        
        # Limpar e filtrar vazios
        return [item.strip() for item in itens if item.strip()]
    
    def montar_diretorio_completo(self, 
                                   diretorio_geral: str, 
                                   diretorio_especifico: str,
                                   mes: int, 
                                   ano: int) -> str:
        r"""
        Monta o caminho completo do diretório das folhas de ponto
        
        Padrão: {DIRETÓRIO GERAL}\{ANO}\{MÊS:02d}.{ANO}\{DIRETÓRIO ESPECÍFICO}
        Exemplo: Z:\04. PESSOAL\FOLHA PONTO\2026\01.2026\01. MS SERVIÇOS\ADMINISTRATIVO
        
        Args:
            diretorio_geral: Caminho base
            diretorio_especifico: Subpasta específica
            mes: Mês de referência
            ano: Ano de referência
        
        Returns:
            Caminho completo montado
        """
        
        # Montar caminho
        caminho = Path(diretorio_geral.strip()) / str(ano) / f"{mes:02d}.{ano}" / diretorio_especifico.strip()
        
        return str(caminho)

    
    def listar_arquivos_pdf(self, diretorio: str) -> List[str]:
        """
        Lista arquivos PDF em um diretório e subdiretórios (busca recursiva)
        
        Args:
            diretorio: Caminho do diretório raiz
        
        Returns:
            Lista de caminhos completos dos PDFs ordenados alfabeticamente
        """
        
        if not Path(diretorio).exists():
            logger.warning(f"Diretório não encontrado: {diretorio}")
            return []
        
        try:
                        
            # Busca recursiva em todos os subdiretórios
            arquivos = [
                str(f) for f in Path(diretorio).rglob("*.pdf")
                if f.is_file()
            ]
            
            # Ordenar alfabeticamente pelo nome do arquivo
            arquivos.sort(key=lambda x: os.path.basename(x).lower())
            
            if arquivos:
                logger.debug(f"Encontrados {len(arquivos)} PDFs em {diretorio} (recursivo)")
            
            return arquivos
        except Exception as e:
            logger.error(f"Erro ao listar arquivos: {e}")
            return []
    
    def iterar_contatos(self, mes: int, ano: int) -> Generator[Dict[str, Any], None, None]:
        """
        Itera sobre os contatos da planilha
        
        Args:
            mes: Mês de referência
            ano: Ano de referência
        
        Yields:
            Dict com dados processados de cada linha
        """
        if self._df is None:
            if not self.carregar():
                return
        
        for idx, row in self._df.iterrows():
            try:
                # Verificar se há algum canal de envio ativo
                enviar_email = self._valor_booleano(row.get("ENVIAR EMAIL"))
                enviar_whatsapp = self._valor_booleano(row.get("ENVIAR WHATSAPP"))
                enviar_grupo = self._valor_booleano(row.get("ENVIAR GRUPO WHATSAPP"))
                
                if not any([enviar_email, enviar_whatsapp, enviar_grupo]):
                    continue  # Pular linha sem envio ativo
                
                # Montar diretório
                diretorio = self.montar_diretorio_completo(
                    row.get("DIRETÓRIO GERAL", ""),
                    row.get("DIRETÓRIO ESPECÍFICO", ""),
                    mes,
                    ano
                )
                
                # Listar PDFs
                arquivos = self.listar_arquivos_pdf(diretorio)
                
                # Parsear listas
                emails = self._parsear_lista(row.get("EMAIL"))
                telefones = parsear_multiplos_telefones(row.get("TELEFONE", ""))
                grupos = self._parsear_lista(row.get("GRUPO WHATSAPP"))
                
                yield {
                    "id": row.get("ID", str(idx)),
                    "nome": row.get("NOME COMPLETO", "").strip(),
                    "empresa": row.get("EMPRESA", "").strip(),
                    "local_contrato_polo": row.get("LOCAL - CONTRATO - POLO", "").strip(),
                    "diretorio_geral": row.get("DIRETÓRIO GERAL", "").strip(),
                    "diretorio_especifico": row.get("DIRETÓRIO ESPECÍFICO", "").strip(),
                    "diretorio_completo": diretorio,
                    "arquivos_pdf": arquivos,
                    
                    # Dados de envio
                    "emails": emails,
                    "telefones": telefones,
                    "grupos_whatsapp": grupos,
                    
                    # Flags de envio
                    "enviar_email": enviar_email,
                    "enviar_whatsapp": enviar_whatsapp,
                    "enviar_grupo_whatsapp": enviar_grupo,
                    "enviar_impresso": self._valor_booleano(row.get("ENVIAR IMPRESSO")),
                    
                    # Metadados
                    "mes_referencia": mes,
                    "ano_referencia": ano,
                    "linha_planilha": idx + 2  # +2 por causa do header e índice base 0
                }
            
            except Exception as e:
                logger.error(f"Erro ao processar linha {idx + 2}: {e}")
                continue
    
    def obter_contato_por_id(self, contato_id: str, mes: int, ano: int) -> Optional[Dict[str, Any]]:
        """
        Obtém dados de um contato específico
        
        Args:
            contato_id: ID do contato
            mes: Mês de referência
            ano: Ano de referência
        
        Returns:
            Dict com dados do contato ou None
        """
        for contato in self.iterar_contatos(mes, ano):
            if str(contato.get("id")) == str(contato_id):
                return contato
        return None
    
    def listar_resumo(self) -> List[Dict[str, Any]]:
        """
        Lista resumo dos contatos para exibição
        
        Returns:
            Lista de dicts com resumo de cada contato
        """
        if self._df is None:
            if not self.carregar():
                return []
        
        resumo = []
        
        for idx, row in self._df.iterrows():
            resumo.append({
                "id": row.get("ID", str(idx)),
                "nome": row.get("NOME COMPLETO", "").strip(),
                "empresa": row.get("EMPRESA", "").strip(),
                "local": row.get("LOCAL - CONTRATO - POLO", "").strip(),
                "enviar_email": "✓" if self._valor_booleano(row.get("ENVIAR EMAIL")) else "",
                "enviar_whatsapp": "✓" if self._valor_booleano(row.get("ENVIAR WHATSAPP")) else "",
                "enviar_grupo": "✓" if self._valor_booleano(row.get("ENVIAR GRUPO WHATSAPP")) else ""
            })
        
        return resumo
    
    def validar_planilha(self) -> Dict[str, Any]:
        """
        Valida a planilha e retorna relatório de problemas
        
        Returns:
            Dict com resultado da validação
        """
        if self._df is None:
            if not self.carregar():
                return {"valida": False, "erro": "Não foi possível carregar a planilha"}
        
        problemas = []
        avisos = []
        
        for idx, row in self._df.iterrows():
            linha = idx + 2  # +2 por header e índice base 0
            
            # Verificar campos obrigatórios preenchidos para linhas com envio ativo
            enviar_email = self._valor_booleano(row.get("ENVIAR EMAIL"))
            enviar_whatsapp = self._valor_booleano(row.get("ENVIAR WHATSAPP"))
            enviar_grupo = self._valor_booleano(row.get("ENVIAR GRUPO WHATSAPP"))
            
            if enviar_email and not row.get("EMAIL", "").strip():
                problemas.append(f"Linha {linha}: ENVIAR EMAIL = S mas sem EMAIL preenchido")
            
            if enviar_whatsapp and not row.get("TELEFONE", "").strip():
                problemas.append(f"Linha {linha}: ENVIAR WHATSAPP = S mas sem TELEFONE preenchido")
            
            if enviar_grupo and not row.get("GRUPO WHATSAPP", "").strip():
                problemas.append(f"Linha {linha}: ENVIAR GRUPO WHATSAPP = S mas sem GRUPO WHATSAPP preenchido")
            
            # Verificar diretórios
            if any([enviar_email, enviar_whatsapp, enviar_grupo]):
                if not row.get("DIRETÓRIO GERAL", "").strip():
                    problemas.append(f"Linha {linha}: Sem DIRETÓRIO GERAL preenchido")
                if not row.get("DIRETÓRIO ESPECÍFICO", "").strip():
                    avisos.append(f"Linha {linha}: Sem DIRETÓRIO ESPECÍFICO preenchido")
        
        return {
            "valida": len(problemas) == 0,
            "total_linhas": len(self._df),
            "problemas": problemas,
            "avisos": avisos
        }
    
    def contar_envios_pendentes(self) -> Dict[str, int]:
        """
        Conta quantos envios estão pendentes por tipo
        
        Returns:
            Dict com contagem por tipo
        """
        if self._df is None:
            if not self.carregar():
                return {}
        
        return {
            "email": sum(1 for _, row in self._df.iterrows() if self._valor_booleano(row.get("ENVIAR EMAIL"))),
            "whatsapp": sum(1 for _, row in self._df.iterrows() if self._valor_booleano(row.get("ENVIAR WHATSAPP"))),
            "grupo_whatsapp": sum(1 for _, row in self._df.iterrows() if self._valor_booleano(row.get("ENVIAR GRUPO WHATSAPP")))
        }


# Instância singleton
planilha_contatos_service = PlanilhaContatosService()
