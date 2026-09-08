from abc import ABC, abstractmethod
from pathlib import Path
import pandas as pd
from datetime import date, timedelta, datetime
import calendar
import locale
from jinja2 import Environment, FileSystemLoader, select_autoescape
try:
    from weasyprint import HTML
except ImportError:
    HTML = None

from typing import List, Dict, Union, Any, Optional
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
import re
import traceback
from src.utils.logger_config_v2 import get_logger

# Logger do módulo
logger = get_logger("folha_ponto")

# Imports para MongoDB e serviços
try:
    from src.services import FuncionarioService, EmpresaService, FolhaDePontoService
    from src.services.mongodb_utils import buscar_nome_funcao
    from src.services.feriado_service import FeriadoService
    from src.services.funcao_service import FuncaoService
    from src.services.horario_service import HorarioService
    from src.services.contrato_service import ContratoService
    from src.services.diretorio_service import DiretorioService
    from src.models.folha_de_ponto_models import (
        FolhaDePontoMongoDB,
        FolhaDePontoData,
        DiaFolhaPonto,
        DiaSemana,
        StatusFolhaPonto
    )
    from src.models.funcionario_models import (
        FuncionarioMongoDB,
        FuncionarioBuilder,
        StatusFuncionario,
        TipoContrato
    )
    from src.models.empresa_models import (
        EmpresaMongoDB,
        EmpresaBuilder,
        StatusEmpresa
    )
    from bson.objectid import ObjectId
    MONGODB_DISPONIVEL = True
except ImportError as e:
    logger.warning(f"Módulos MongoDB não disponíveis: {e}")
    MONGODB_DISPONIVEL = False


# ==================== TIPOS PARA CONTROLE DE PROBLEMAS ====================
class TipoProblema(Enum):
    """Tipos de problemas que podem ocorrer durante o processamento"""
    DUPLICATA_PULADA = "duplicata_pulada"  # Usuário escolheu pular funcionário duplicado
    ERRO_MONGODB = "erro_mongodb"           # Erro ao salvar/buscar em MongoDB
    ERRO_EMPRESA = "erro_empresa"           # Empresa não encontrada
    ERRO_FUNCIONARIO = "erro_funcionario"   # Erro ao processar funcionário
    ERRO_PDF = "erro_pdf"                   # Erro ao gerar PDF


@dataclass
class ProblemaProcessamento:
    """Representa um problema encontrado durante o processamento de folhas de ponto"""
    tipo: TipoProblema
    funcionario_nome: str
    funcionario_id: int
    mensagem: str
    detalhes: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        return f"[{self.tipo.value}] {self.funcionario_nome}: {self.mensagem}"



# Define o locale para português do Brasil (com fallback p/ ambientes sem locale pt_BR, ex.: Linux mínimo/Docker)
try:
    for _locale_candidato in ('pt_BR.UTF-8', 'pt_BR.utf8', 'pt_BR', 'pt_PT.UTF-8', 'pt_PT'):
        try:
            locale.setlocale(locale.LC_TIME, _locale_candidato)
            break
        except locale.Error:
            continue
except locale.Error:
    pass  # mantém o locale padrão — nunca quebra o import

# Interfaces
class IHtmlTemplateProvider(ABC):

    @abstractmethod
    def render(self, contexto: Dict[str, Any]) -> str:
        pass

class IHtmlPdfConverter(ABC):
    @abstractmethod
    def salvar_html_como_pdf(self, html_text: str, caminho_pdf: Path) -> None:
        pass

class IGerenciadorDiretorios(ABC):
    @abstractmethod
    def buscar_diretorio_geral_ponto(self) -> Path:
        pass
    
    @abstractmethod
    def definir_diretorio_processamento(self, caminho: Path = None) -> Path:
        pass

class IProcessadorFolhaPonto(ABC):

    @abstractmethod
    def criar_contexto_html(self, id_empresa: int = None, data: date = None, nome_funcionario: str = None,
                            cargo: str = None, departamento: str = None, contrato: str = None,
                            horario: str = None, dados_empresas: Union[pd.DataFrame, Dict[str, str]] = None,
                            cpf: str = None, folha_id: str = None) -> Dict[str, Any]:
        pass
    

class FolhaPontoHtmlTemplate(IHtmlTemplateProvider):
    """Gerencia o template HTML da folha de ponto."""

    def __init__(self, caminho_template: Path):

        self.logger = get_logger("folha_ponto")
        self.caminho_template = caminho_template
        self.env = Environment(
            loader=FileSystemLoader(caminho_template.parent),
            autoescape=select_autoescape(['html', 'xml'])
        )

        
    def render(self, contexto: Dict[str, Any]) -> str:
        if not self.caminho_template.exists():
            raise FileNotFoundError(f"Template HTML não encontrado: {self.caminho_template}")
        template = self.env.get_template(self.caminho_template.name)
        return template.render(contexto)


class HtmlToPdfConverter(IHtmlPdfConverter):
    """Converte HTML para PDF usando WeasyPrint."""

    @staticmethod
    def salvar_html_como_pdf(html_text: str, caminho_pdf: Path) -> None:
        if not html_text:
            raise ValueError("HTML vazio para conversão")
        if HTML is None:
            raise RuntimeError(
                "WeasyPrint não está disponível ou não foi carregado. "
                "Instale as dependências nativas necessárias para gerar PDF via HTML."
            )
        caminho_pdf.parent.mkdir(parents=True, exist_ok=True)
        HTML(string=html_text).write_pdf(str(caminho_pdf))


class GerenciadorDiretorios(IGerenciadorDiretorios):
    def buscar_diretorio_geral_ponto(self) -> Path:
        # Procurar a pasta de ponto geral
        unidades = [Path(f"{chr(i)}:/") for i in range(65, 91) if Path(f"{chr(i)}:/").exists()]
        
        for unidade in unidades:
            pasta = unidade / "04. PESSOAL" / "FOLHA PONTO"
            if pasta.exists():
                return pasta
        
        # Se não encontrar, usar o local padrão dentro do projeto
        return Path(__file__).resolve().parent / "data" / "output" / "FOLHA PONTO"

    def definir_diretorio_processamento(self, caminho: Optional[Path] = None) -> Path:
        # Diretório padrão relativo ao pacote src/ (robusto em Windows e Linux)
        if caminho is None:
            caminho = Path(__file__).resolve().parent / "data" / "process"
        # Criar o diretório de processamento se não existir
        if not caminho.exists():
            caminho.mkdir(parents=True, exist_ok=True)
        
        return caminho

class ProcessadorFolhaPonto(IProcessadorFolhaPonto):
    def __init__(self):
        
        self.feriados = self._carregar_feriados_mongodb()
    
    
    def _carregar_feriados_mongodb(self) -> pd.DataFrame:
        """
        Carrega feriados do MongoDB e retorna como DataFrame.
        Se não houver feriados, retorna DataFrame vazio.
        """ 
        try:
            servico = FeriadoService()
            if servico.disponivel:
                # Obter DataFrame de feriados
                df = servico.obter_dataframe()
                if not df.empty:
                    logger.debug(f"✓ {len(df)} feriado(s) carregado(s) do MongoDB")
                    return df
                else:
                    logger.debug("⚠ Nenhum feriado cadastrado no MongoDB")
            else:
                logger.debug("⚠ Serviço de feriados não disponível")
        except ImportError:
            logger.debug("⚠ Módulo feriado_service não disponível")
        except Exception as e:
            logger.warning(f"⚠ Erro ao carregar feriados: {e}")
        
        # Retornar DataFrame vazio como fallback
        return pd.DataFrame(columns=["DATA", "DESCRICAO"])
    

    def criar_contexto_html(self, id_empresa: int = None, data: date = None, nome_funcionario: str = None,
                            cargo: str = None, departamento: str = None, contrato: str = None,
                            horario: str = None, dados_empresas: Union[pd.DataFrame, Dict[str, str]] = None,
                            cpf: str = None, folha_id: str = None) -> Dict[str, Any]:
        """Gera o contexto de dados para renderizar o template HTML da folha.
        Gera o contexto de dados para renderizar o template HTML da folha de ponto.
        Este método cria um dicionário contendo todas as informações necessárias para 
        preencher um modelo de folha de ponto em HTML, incluindo dados da empresa, 
        do funcionário e a lista de dias do mês com suas respectivas informações.
        Parâmetros:
        -----------
        id_empresa : int, opcional
            Índice da empresa no DataFrame de dados de empresas.
        data : date, obrigatório
            Data de referência para geração da folha de ponto (mês/ano).
        nome_funcionario : str, opcional
            Nome completo do funcionário.
        cargo : str, opcional
            Cargo ou função do funcionário.
        departamento : str, opcional
            Departamento ou setor do funcionário.
        contrato : str, opcional
            Número ou identificação do contrato de trabalho.
        horario : str, opcional
            Horário de trabalho do funcionário (ex: "08:00 - 18:00").
        dados_empresas : Union[pd.DataFrame, Dict[str, str]], opcional
            Dados da empresa. Pode ser um DataFrame com colunas (EMPRESA, ATIVIDADE, 
            ENDEREÇO, CNPJ) ou um dicionário com as mesmas chaves.
        cpf : str, opcional
            CPF do funcionário.
        folha_id : str, opcional
            Identificador único da folha de ponto.
        Retorna:
        --------
        Dict[str, Any]
            Dicionário contendo o contexto completo para renderização do template HTML, 
            incluindo:
            - FP: Informações de identificação da folha de ponto (id, período)
            - periodo: Data de início e fim do mês
            - data_geracao: Data de geração do documento
            - empresa: Dados da empresa (nome, atividade, endereço, CNPJ)
            - funcionario: Dados do funcionário (nome, cargo, departamento, lotação, 
                contrato, horário, CPF)
            - dias: Lista de dicionários com informações de cada dia do mês
            - total_dias: Total de dias no período
            - feriados: Lista de datas de feriados no formato DD/MM/YYYY
        Levanta:
        --------
        ValueError
            Se o parâmetro 'data' não for fornecido (é obrigatório).
        Notas:
        ------
        - Os dias são gerados para todo o mês da data fornecida.
        - Dias de fim de semana (sábado e domingo) e feriados são marcados com 
            a flag 'eh_descanso' como True.
        - Os nomes dos dias da semana são retornados em português (Segunda, Terça, 
            Quarta, Quinta, Sexta, Sábado, Domingo).
        - Os dias são formatados com zero à esquerda (01, 02, etc.).

        """
        if data is None:
            raise ValueError("Data é obrigatória para gerar contexto HTML")

        data_inicial = data.replace(day=1)
        ultimo_dia = calendar.monthrange(data.year, data.month)[1]
        data_final = date(data.year, data.month, ultimo_dia)

        feriados = set()
        if isinstance(self.feriados, pd.DataFrame) and 'DATA' in self.feriados.columns:
            feriados = {
                dia.date() for dia in self.feriados['DATA'].dropna().tolist()
                if isinstance(dia, datetime) or hasattr(dia, 'date')
            }

        # Mapeamento de dias da semana em português
        nomes_dias_pt = {
            0: 'Segunda',
            1: 'Terça',
            2: 'Quarta',
            3: 'Quinta',
            4: 'Sexta',
            5: 'Sábado',
            6: 'Domingo'
        }

        dias = []
        current_date = data_inicial
        while current_date <= data_final:
            # Verificar se é feriado, sábado ou domingo
            eh_feriado = current_date in feriados
            eh_fim_de_semana = current_date.weekday() >= 5  # 5=sábado, 6=domingo
            eh_descanso = eh_feriado or eh_fim_de_semana
            
            # Determinar observação
            observacao = ''
            
            # Traduzir dia da semana pelo índice numérico, evitando dependência de locale
            dia_semana_pt = nomes_dias_pt[current_date.weekday()]
            
            dias.append({
                'dia_numero': str(current_date.day).zfill(2),  # Zero-padded: 01, 02, etc
                'dia_semana': dia_semana_pt,
                'entrada': '',
                'intervalo_inicio': '',
                'intervalo_fim': '',
                'termino': '',
                'observacoes': observacao,
                'eh_descanso': eh_descanso  # Flag para aplicar cor cinza
            })
            current_date += timedelta(days=1)

        # Preparar dados da empresa (aceita Dict com chaves: EMPRESA, ATIVIDADE, ENDEREÇO, CNPJ ou CNPJ)
        empresa = {}
        if isinstance(dados_empresas, dict):
            empresa = {
                'nome': dados_empresas.get('EMPRESA') or dados_empresas.get('nome', ''),
                'atividade': dados_empresas.get('ATIVIDADE') or dados_empresas.get('atividade', ''),
                'endereco': dados_empresas.get('ENDEREÇO') or dados_empresas.get('endereco', ''),
                'cnpj': dados_empresas.get('CNPJ') or dados_empresas.get('cnpj', '')
            }
        elif isinstance(dados_empresas, pd.DataFrame) and id_empresa is not None:
            try:
                row = dados_empresas.iloc[id_empresa].to_dict()
                empresa = {
                    'nome': row.get('EMPRESA') or row.get('nome', ''),
                    'atividade': row.get('ATIVIDADE') or row.get('atividade', ''),
                    'endereco': row.get('ENDEREÇO') or row.get('endereco', ''),
                    'cnpj': row.get('CNPJ') or row.get('cnpj', '')
                }
            except Exception:
                empresa = {'nome': '', 'atividade': '', 'endereco': '', 'cnpj': ''}

        contexto = {
            'FP': {
                'id': folha_id or '',
                'periodo_inicio': data_inicial.strftime('%d/%m/%Y'),
                'periodo_fim': data_final.strftime('%d/%m/%Y')
            },
            'periodo': {
                'inicio': data_inicial.strftime('%d/%m/%Y'),
                'fim': data_final.strftime('%d/%m/%Y')
            },
            'data_geracao': datetime.now().strftime('%d/%m/%Y'),
            'empresa': empresa,
            'funcionario': {
                'nome': nome_funcionario,
                'cargo': cargo,
                'departamento': departamento,
                'lotacao': departamento,
                'contrato': contrato,
                'horario': horario,
                'cpf': cpf or ''
            },
            'dias': dias,
            'total_dias': len(dias),
            'feriados': [d.strftime('%d/%m/%Y') for d in sorted(feriados)]
        }

        return contexto


class GeradorFolhaPonto:
    def __init__(
        self,
        gerenciador_diretorios: IGerenciadorDiretorios = None,
        processador_folha_ponto: IProcessadorFolhaPonto = None,
        html_template: Optional[IHtmlTemplateProvider] = None,
        html_converter: Optional[IHtmlPdfConverter] = None,
        modo_mongodb_puro: bool = False,
    ):
        """
        Inicializa o gerador de folha de ponto.
        
        Args:
            gerenciador_diretorios: Gerenciador de diretórios
            processador_folha_ponto: Processador de folha de ponto (opcional se modo_mongodb_puro=True)
            html_template: Provedor de template HTML opcional para geração direta de PDF
            html_converter: Conversor de HTML para PDF opcional
            modo_mongodb_puro: Se True, inicializa apenas com serviços MongoDB (sem Excel)
        """
        self.gerenciador_diretorios = gerenciador_diretorios
        self.processador_folha_ponto = processador_folha_ponto
        self.html_template = html_template
        self.html_converter = html_converter
        self.modo_mongodb_puro = modo_mongodb_puro
        
        
        # Inicializar serviços MongoDB
        if not MONGODB_DISPONIVEL:
            logger.error(f"✗ Erro ao inicializar serviços MongoDB: {e}")
            self.servico_funcionario = None
            self.servico_empresa = None
            self.servico_folha_ponto = None
            self.servico_funcao = None
            self.servico_horario = None
            self.servico_contrato = None
            self.servico_diretorio = None
        
        else:
            self.servico_funcionario = FuncionarioService()
            self.servico_empresa = EmpresaService()
            self.servico_folha_ponto = FolhaDePontoService()
            # Services para referências de funcionário (funcao_id, horario_id, contrato_empresa_id)
            self.servico_funcao = FuncaoService()
            self.servico_horario = HorarioService()
            self.servico_contrato = ContratoService()
            self.servico_diretorio = DiretorioService()
            logger.debug("✓ Serviços MongoDB inicializados para GeradorFolhaPonto")
            

    # ==================== MÉTODOS MongoDB - ETAPA 1 ====================
    
    def _normalizar_nome(self, nome: str) -> str:
        """Normaliza nome para busca em MongoDB (remove acentos, minúsculas)"""
        if not nome:
            return ""
        nome_normalizado = unicodedata.normalize('NFKD', nome)
        nome_normalizado = ''.join([c for c in nome_normalizado if not unicodedata.combining(c)])
        return nome_normalizado.lower().strip()

    
    def _obter_nome_diretorio_funcionario(self, funcionario: Dict[str, Any]) -> str:
        """
        Obtém o nome do diretório para um funcionário.
        
        Prioridade:
        1. Usar diretorio_id (novo modelo) → buscar caminho via DiretorioService
        2. Usar diretorio_interno (campo legado) → valor direto
        3. Fallback: retornar '\\'
        
        Args:
            funcionario: Documento do funcionário (MongoDB ou dicionário)
        
        Returns:
            Caminho do diretório ou '\\' como fallback
        """
        # Prioridade 1: diretorio_id (novo modelo)
        diretorio_id = funcionario.get('diretorio_id')
        if diretorio_id and self.servico_diretorio:
            try:
                caminho = self.servico_diretorio.obter_nome_diretorio(str(diretorio_id))
                if caminho and caminho != '\\':
                    logger.debug(f"Diretório obtido via diretorio_id: {caminho}")
                    return caminho
            except Exception as e:
                logger.warning(f"Erro ao buscar diretório por ID: {e}")
        
        # Prioridade 2: diretorio_interno (campo legado)
        diretorio_interno = funcionario.get('diretorio_interno', '')
        if diretorio_interno:
            logger.debug(f"Diretório obtido via campo legado: {diretorio_interno}")
            return diretorio_interno
        
        # Fallback
        logger.debug("Usando fallback para diretório: '\\\\'")
        return '\\'
    
    
    ### ==================== MÉTODO DE CONSTRUÇÃO DE DOCUMENTO MongoDB ===================== ###
    def _construir_documento_mongodb(self, 
                                     funcionario_id: str,
                                     empresa_id: str,
                                     mes_referencia: str,
                                     data: date,
                                     caminho_arquivo_pdf: Optional[Path] = None,
                                     nome_funcionario: Optional[str] = None,
                                     cargo_funcionario: Optional[str] = None,
                                     contrato_funcionario: Optional[str] = None,
                                     horario_funcionario: Optional[str] = None,
                                     lotacao_funcionario: Optional[str] = None,
                                     cpf_funcionario: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Constrói documento FolhaDePontoMongoDB com dados da Planilha ou MongoDB.
        
        IMPORTANTE: Agora usa apenas ObjectId para referenciar funcionário/empresa.
        Não duplica dados - apenas mantém referências.
        Armazena também informações do funcionário na FolhaDePontoData para facilitar
        renderização de relatórios/PDFs sem necessidade de fazer join com coleção de funcionários.
        
        Args:
            funcionario_id: ObjectId string do funcionário
            empresa_id: ObjectId string da empresa
            mes_referencia: Mês em formato YYYY-MM
            data: Data de referência
            caminho_arquivo_pdf: Caminho do arquivo PDF gerado (opcional)
            nome_funcionario: Nome do funcionário (opcional, usado quando origem é MongoDB)
            cargo_funcionario: Cargo/função do funcionário (opcional)
            contrato_funcionario: Nome do contrato/empresa (ex: CENSIPAM, CNJ) (opcional)
            horario_funcionario: Descrição do horário de trabalho (opcional)
            lotacao_funcionario: Lotação/departamento do funcionário (opcional)
            cpf_funcionario: CPF do funcionário (opcional)
        
        Returns:
            Dicionário preparado para salvar ou None se erro
        """
        try:
            from bson import ObjectId
            
            # Converter strings para ObjectId
            funcionario_obj_id = ObjectId(funcionario_id)
            empresa_obj_id = ObjectId(empresa_id)
            
            # Gerar dias vazios (sem horários, apenas datas)
            data_inicial = data.replace(day=1)
            if data.month == 12:
                data_final = data.replace(day=31)
            else:
                primeiro_dia_proximo = data.replace(month=data.month + 1, day=1)
                data_final = primeiro_dia_proximo - timedelta(days=1)
            
            # Mapa de dias da semana para enum DiaSemana
            dias_semana_mapa = {
                0: DiaSemana.SEGUNDA,
                1: DiaSemana.TERCA,
                2: DiaSemana.QUARTA,
                3: DiaSemana.QUINTA,
                4: DiaSemana.SEXTA,
                5: DiaSemana.SABADO,
                6: DiaSemana.DOMINGO
            }
            
            dias = []
            data_loop = data_inicial
            numero_dia = 1
            while data_loop <= data_final:
                dia_semana_enum = dias_semana_mapa.get(data_loop.weekday(), DiaSemana.SEGUNDA)
                dia = DiaFolhaPonto(
                    numero_dia=numero_dia,
                    data=data_loop,
                    dia_semana=dia_semana_enum,
                    hora_entrada=None,
                    hora_intervalo_inicio=None,
                    hora_intervalo_fim=None,
                    hora_saida=None,
                    total_horas_trabalhadas=None,
                    observacoes=None,
                    tipo_dia=None,
                    preenchido_manualmente=False,
                    analise_ia_processada=False
                )
                dias.append(dia)
                data_loop += timedelta(days=1)
                numero_dia += 1
            
            # Criar FolhaDePontoData com informações do funcionário para renderização
            folha_data = FolhaDePontoData(
                mes_referencia=mes_referencia,
                data_inicio=data_inicial,
                data_fim=data_final,
                dias=dias,
                nome_funcionario=nome_funcionario,
                cpf_funcionario=cpf_funcionario,
                cargo_funcionario=cargo_funcionario,
                contrato_funcionario=contrato_funcionario,
                horario_funcionario=horario_funcionario,
                lotacao_funcionario=lotacao_funcionario,
                preenchimento_concluido=False,
                analise_ia_concluida=False
            )
            
            # Criar documento FolhaDePontoMongoDB usando modelo Pydantic
            # AGORA COM ObjectId (não string)
            # Obter caminho absoluto do arquivo PDF gerado (se fornecido)
            caminho_absoluto_gerado = str(caminho_arquivo_pdf.resolve()) if caminho_arquivo_pdf else None
            
            folha = FolhaDePontoMongoDB(
                funcionario_id=funcionario_obj_id,
                empresa_id=empresa_obj_id,
                mes_referencia=mes_referencia,
                folha_data=folha_data,
                caminho_arquivo_gerado=caminho_absoluto_gerado,
                data_criacao=datetime.now(),
                status=StatusFolhaPonto.CRIADA,
                versao=1,
                historico_alteracoes=[]
            )
            
            # Converter para dicionário compatível com MongoDB usando método do modelo
            try:
                documento = folha.dict(by_alias=True)
            except Exception as e_dict:
                logger.error(f"Erro ao converter folha para dict: {e_dict}", exc_info=True)
                logger.debug(f"folha object: {folha}")
                logger.debug(f"folha.folha_data: {folha.folha_data}")
                raise
            
            logger.debug(f"✓ Documento MongoDB construído para {nome_funcionario}")
            return documento
            
        except Exception as e:
            logger.error(f"✗ Erro ao construir documento MongoDB: {e}")
            return None
        
        
    def _processar_folha_unica(
        self, 
        funcionario_id: ObjectId | str, 
        empresa_id: ObjectId | str, 
        data: date,
        diretorio_destino: Optional[Path] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Processa a geração de UMA folha de ponto individual.
        Este é o núcleo compartilhado entre modo individual e lote.
        
        Args:
            funcionario_id: ObjectId do funcionário no MongoDB
            empresa_id: ObjectId da empresa no MongoDB
            data: Data de referência da folha (mês/ano)
            diretorio_destino: Diretório customizado para salvar PDF (opcional)
        
        Returns:
            Dict com status da operação ou None se erro
        """
        try:
            # 1. Buscar funcionário no MongoDB
            funcionario_mongo = self.servico_funcionario.buscar_por_id(funcionario_id)
            if not funcionario_mongo:
                logger.error(f"✗ Funcionário não encontrado: {funcionario_id}")
                return None
            
            nome = funcionario_mongo.get('nome', 'Desconhecido')
            
            # 2. Buscar empresa no MongoDB
            empresa_mongo = self.servico_empresa.buscar_por_id(empresa_id)
            if not empresa_mongo:
                logger.error(f"✗ Empresa não encontrada: {empresa_id}")
                return None
            
            nome_empresa = empresa_mongo.get('nome', 'Desconhecida')
            
            # 3. Buscar dados das referências (função, horário, contrato)
            funcao_id = funcionario_mongo.get("funcao_id")
            cargo = ""
            if funcao_id and self.servico_funcao and self.servico_funcao.disponivel:
                try:
                    funcao_doc = self.servico_funcao.buscar_por_id(str(funcao_id))
                    if funcao_doc:
                        cargo = funcao_doc.get("nome", "")
                except Exception as e:
                    logger.warning(f"  Erro ao buscar função: {e}")
            
            horario_id = funcionario_mongo.get("horario_id")
            horario = ""
            if horario_id and self.servico_horario and self.servico_horario.disponivel:
                try:
                    horario_doc = self.servico_horario.buscar_por_id(str(horario_id))
                    if horario_doc:
                        horario = horario_doc.get("descricao", "")
                except Exception as e:
                    logger.warning(f"  Erro ao buscar horário: {e}")
            
            contrato_empresa_id = funcionario_mongo.get("contrato_empresa_id")
            contrato = ""
            if contrato_empresa_id and self.servico_contrato and self.servico_contrato.disponivel:
                try:
                    contrato_doc = self.servico_contrato.buscar_por_id(str(contrato_empresa_id))
                    if contrato_doc:
                        contrato = contrato_doc.get("nome", "")
                except Exception as e:
                    logger.warning(f"  Erro ao buscar contrato: {e}")
            
            departamento = funcionario_mongo.get("lotacao", "")
            cpf_funcionario = funcionario_mongo.get("cpf", "")
            
            # 4. Preparar dados para geração do PDF
            dados_empresa = {
                "EMPRESA": empresa_mongo.get("nome", ""),
                "ATIVIDADE": empresa_mongo.get("atividade", ""),
                "ENDEREÇO": empresa_mongo.get("endereco", ""),
                "CNPJ": empresa_mongo.get("cnpj", "")
            }
            
            diretorio_geral = self.gerenciador_diretorios.buscar_diretorio_geral_ponto()
            
            if diretorio_destino is None:
                caminho_diretorio = self._obter_nome_diretorio_funcionario(funcionario_mongo)
                diretorio_interno = Path(caminho_diretorio) if caminho_diretorio and caminho_diretorio != '\\' else Path("SEM_LOTACAO")
                diretorio_pdf = (
                    diretorio_geral / 
                    data.strftime('%Y') / 
                    f"{data.strftime('%m')}.{data.strftime('%Y')}" / 
                    diretorio_interno
                )
            else:
                diretorio_pdf = Path(diretorio_destino)
            
            diretorio_pdf.mkdir(parents=True, exist_ok=True)
            
            # 5. Gerar folha de ponto (HTML -> PDF)
            empresas_vinculadas = funcionario_mongo.get('empresas_ids', []) or []
            usar_sigla = len(empresas_vinculadas) > 1

            sigla = empresa_mongo.get('nome_sigla') or empresa_mongo.get('nome_simplificado') or ""
            if not sigla:
                partes_empresa = [p for p in nome_empresa.split() if p]
                if partes_empresa:
                    sigla = ''.join(p[0] for p in partes_empresa[:3]).upper()
                else:
                    sigla = "SEM_SIGLA"

            safe_sigla = re.sub(r'[^A-Za-z0-9_-]', '', sigla) or "SIGLA"
            safe_nome = re.sub(r'[^A-Za-z0-9 _-]', '', nome).strip() or "FUNCIONARIO"
            safe_nome = re.sub(r'\s+', ' ', safe_nome)

            if usar_sigla:
                nome_arquivo_base = f"{safe_nome.title()} - {safe_sigla}"
            else:
                nome_arquivo_base = safe_nome.title()

            caminho_arquivo_pdf = diretorio_pdf / f"{nome_arquivo_base}.pdf"
            
            # 6. Salvar folha no MongoDB
            mes_referencia = data.strftime('%Y-%m')
            
            documento = self._construir_documento_mongodb(
                funcionario_id=funcionario_id,
                empresa_id=empresa_id,
                mes_referencia=mes_referencia,
                data=data,
                caminho_arquivo_pdf=caminho_arquivo_pdf,
                nome_funcionario=nome,
                cargo_funcionario=cargo,
                contrato_funcionario=contrato,
                horario_funcionario=horario,
                lotacao_funcionario=departamento,
                cpf_funcionario=cpf_funcionario
            )
            
            if not documento:
                raise RuntimeError("Falha ao construir documento MongoDB para a folha")
            
            folha_id = self._salvar_folha_mongodb(documento)
            if not folha_id:
                raise RuntimeError("Não foi possível salvar a folha em MongoDB")
            
            # 7. Gerar PDF via HTML
            if not self.html_template or not self.html_converter:
                raise RuntimeError("Template HTML não está disponível para geração de PDF")
            
            folha_id = folha_id or str(funcionario_id)
            
            contexto = self.processador_folha_ponto.criar_contexto_html(
                id_empresa=None,
                data=data,
                nome_funcionario=nome,
                cargo=cargo,
                departamento=departamento,
                contrato=contrato,
                horario=horario,
                dados_empresas=dados_empresa,
                cpf=cpf_funcionario,
                folha_id=folha_id
            )
            
            html_text = self.html_template.render(contexto)
            self.html_converter.salvar_html_como_pdf(html_text, caminho_arquivo_pdf)
            
            return {
                "status": "sucesso",
                "funcionario": nome,
                "empresa": nome_empresa,
                "mes": data.strftime('%m/%Y'),
                "caminho_pdf": str(caminho_arquivo_pdf)
            }
                
        except Exception as e:
            logger.error(f"✗ Erro ao processar folha: {e}")
            logger.debug(traceback.format_exc())
            return None
    
    
    def _salvar_folha_mongodb(
        self, 
        documento: Dict[str, Any],
        forcar_sobrescrita: bool = False,
        perguntar_usuario: bool = True
    ) -> Optional[str]:
        """
        Salva documento em MongoDB com tratamento de duplicidade.
        
        Args:
            documento: Dicionário com dados da folha
            forcar_sobrescrita: Se True, sobrescreve folha existente
            perguntar_usuario: Se True, pergunta ao usuário em caso de duplicidade
        
        Returns:
            ID da folha (ObjectId string) se salvo ou existente, None se erro ou cancelado
        """
        from src.services import ResultadoSalvamento
        
        if not self.servico_folha_ponto or not documento:
            logger.debug("Serviço de folha ou documento inválido")
            return False
        
        try:
            mes = documento.get("mes_referencia", "")
            
            # Buscar dados do funcionário pelo ObjectId
            funcionario_id = documento.get("funcionario_id")
            funcionario = "Desconhecido"
            lotacao = ""
            funcao = ""
            
            if funcionario_id and self.servico_funcionario:
                try:
                    # Usar buscar_por_object_id ao invés de buscar_por_id
                    func_doc = self.servico_funcionario.buscar_por_object_id(funcionario_id)
                    if func_doc:
                        funcionario = func_doc.get("nome", "Desconhecido")
                        lotacao = func_doc.get("lotacao", "")
                        
                        # Buscar nome da função usando a função centralizada
                        funcao_id = func_doc.get("funcao_id")
                        if funcao_id:
                            try:
                                funcao = buscar_nome_funcao(funcao_id) or ""
                            except Exception:
                                pass
                except Exception as e:
                    logger.debug(f"Erro ao buscar dados do funcionário: {e}")
            
            resultado, folha_existente, folha_id = self.servico_folha_ponto.salvar_ou_atualizar(
                documento, 
                forcar_sobrescrita=forcar_sobrescrita
            )
            
            if resultado == ResultadoSalvamento.SUCESSO_INSERIDO:
                logger.info(f"✓ Folha salva em MongoDB: {funcionario} ({mes})")
                return str(folha_id) if folha_id is not None else None
            
            elif resultado == ResultadoSalvamento.SUCESSO_ATUALIZADO:
                logger.info(f"✓ Folha atualizada em MongoDB: {funcionario} ({mes})")
                return str(folha_id) if folha_id is not None else None
            
            elif resultado == ResultadoSalvamento.SUCESSO_INALTERADO:
                logger.info(f"ℹ Folha já existia com mesmos dados: {funcionario} ({mes})")
                return str(folha_id) if folha_id is not None else None
            
            elif resultado == ResultadoSalvamento.DUPLICIDADE:
                if folha_existente is None:
                    # Não conseguiu buscar a folha existente, perguntar mesmo assim
                    logger.warning(f"⚠ Folha duplicada mas não foi possível buscar existente: {funcionario} ({mes})")
                    if perguntar_usuario:
                        return self._tratar_duplicidade_folha_sem_existente(
                            documento, funcionario, mes, lotacao, funcao
                        )
                    else:
                        return None
                elif perguntar_usuario:
                    return self._tratar_duplicidade_folha(
                        documento, folha_existente, funcionario, mes, lotacao, funcao
                    )
                else:
                    logger.warning(f"⚠ Folha duplicada ignorada: {funcionario} ({mes})")
                    return str(folha_id) if folha_id is not None else None
            
            elif resultado == ResultadoSalvamento.INDISPONIVEL:
                logger.warning("MongoDB não disponível para salvar")
                return None
            
            else:
                logger.warning(f"Falha ao salvar folha em MongoDB: {funcionario} ({mes})")
                return None
            
        except Exception as e:
            logger.error(f"✗ Erro ao salvar folha em MongoDB: {e}")
            return None
    
    def _tratar_duplicidade_folha(
        self, 
        documento_novo: Dict[str, Any], 
        folha_existente: Dict[str, Any],
        funcionario: str,
        mes: str,
        lotacao: str = "",
        funcao: str = ""
    ) -> Optional[str]:
        """
        Trata situação de duplicidade perguntando ao usuário.
        
        Args:
            documento_novo: Novo documento a salvar
            folha_existente: Documento existente no MongoDB
            funcionario: Nome do funcionário
            mes: Mês de referência
            lotacao: Lotação do funcionário
            funcao: Função do funcionário
        
        Returns:
            ID da folha existente ou atualizada se sobrescrever, None se cancelar ou erro
        """
        from src.services import ResultadoSalvamento
        
        # Usar lotação e função passadas como parâmetro
        lotacao_exibir = lotacao if lotacao else "N/A"
        funcao_exibir = funcao if funcao else "N/A"
        
        print(f"\n{'='*60}")
        print(f"⚠  FOLHA DE PONTO DUPLICADA DETECTADA")
        print(f"{'='*60}")
        print(f"Funcionário: {funcionario}")
        print(f"Mês: {mes}")
        print(f"Lotação: {lotacao_exibir}")
        print(f"Função: {funcao_exibir}")
        print(f"\nJá existe uma folha de ponto salva no MongoDB para este")
        print(f"funcionário neste mês com a mesma lotação e função.")
        
        # Mostrar diferenças se possível
        data_existente = folha_existente.get('data_criacao', 'Desconhecida')
        if hasattr(data_existente, 'strftime'):
            data_existente = data_existente.strftime('%d/%m/%Y %H:%M')
        print(f"\nFolha existente criada em: {data_existente}")
        
        print(f"\n{'─'*60}")
        print("O que deseja fazer?")
        print("  [S] Sobrescrever a folha existente com a nova")
        print("  [C] Cancelar e manter a folha existente")
        print(f"{'─'*60}")
        
        while True:
            opcao = input("Escolha (S/C): ").strip().upper()
            
            if opcao == 'S':
                # Sobrescrever
                resultado, _, folha_id = self.servico_folha_ponto.salvar_ou_atualizar(
                    documento_novo, 
                    forcar_sobrescrita=True
                )
                
                if resultado in [ResultadoSalvamento.SUCESSO_ATUALIZADO, ResultadoSalvamento.SUCESSO_INALTERADO] and folha_id is not None:
                    print(f"✓ Folha sobrescrita com sucesso!")
                    logger.info(f"✓ Folha sobrescrita por escolha do usuário: {funcionario} ({mes})")
                    return str(folha_id)
                else:
                    print(f"✗ Erro ao sobrescrever folha")
                    logger.error(f"Erro ao sobrescrever folha: {funcionario} ({mes})")
                    return None
            
            elif opcao == 'C':
                print(f"ℹ Salvamento cancelado. Folha existente mantida.")
                logger.info(f"ℹ Salvamento cancelado pelo usuário: {funcionario} ({mes})")
                return None
            
            else:
                print("Opção inválida. Digite S para sobrescrever ou C para cancelar.")
    
    def _tratar_duplicidade_folha_sem_existente(
        self, 
        documento_novo: Dict[str, Any],
        funcionario: str,
        mes: str,
        lotacao: str = "",
        funcao: str = ""
    ) -> Optional[str]:
        """
        Trata situação de duplicidade quando não foi possível recuperar a folha existente.
        
        Args:
            documento_novo: Novo documento a salvar
            funcionario: Nome do funcionário
            mes: Mês de referência
            lotacao: Lotação do funcionário
            funcao: Função do funcionário
        
        Returns:
            ID da folha atualizada se sobrescrever, None se cancelar ou erro
        """
        from src.services import ResultadoSalvamento
        
        # Usar lotação e função passadas como parâmetro
        lotacao_exibir = lotacao if lotacao else "N/A"
        funcao_exibir = funcao if funcao else "N/A"
        
        print(f"\n{'='*60}")
        print(f"⚠  FOLHA DE PONTO DUPLICADA DETECTADA")
        print(f"{'='*60}")
        print(f"Funcionário: {funcionario}")
        print(f"Mês: {mes}")
        print(f"Lotação: {lotacao_exibir}")
        print(f"Função: {funcao_exibir}")
        print(f"\nJá existe uma folha de ponto salva no MongoDB para este")
        print(f"funcionário neste mês com a mesma lotação e função.")
        print(f"\n(Não foi possível recuperar detalhes da folha existente)")
        
        print(f"\n{'─'*60}")
        print("O que deseja fazer?")
        print("  [S] Sobrescrever a folha existente com a nova")
        print("  [C] Cancelar e manter a folha existente")
        print(f"{'─'*60}")
        
        while True:
            opcao = input("Escolha (S/C): ").strip().upper()
            
            if opcao == 'S':
                # Sobrescrever
                resultado, _, folha_id = self.servico_folha_ponto.salvar_ou_atualizar(
                    documento_novo, 
                    forcar_sobrescrita=True
                )
                
                if resultado in [ResultadoSalvamento.SUCESSO_ATUALIZADO, ResultadoSalvamento.SUCESSO_INALTERADO] and folha_id is not None:
                    print(f"✓ Folha sobrescrita com sucesso!")
                    logger.info(f"✓ Folha sobrescrita por escolha do usuário: {funcionario} ({mes})")
                    return str(folha_id)
                else:
                    print(f"✗ Erro ao sobrescrever folha")
                    logger.error(f"Erro ao sobrescrever folha: {funcionario} ({mes})")
                    return None
            
            elif opcao == 'C':
                print(f"ℹ Salvamento cancelado. Folha existente mantida.")
                logger.info(f"ℹ Salvamento cancelado pelo usuário: {funcionario} ({mes})")
                return None
            
            else:
                print("Opção inválida. Digite S para sobrescrever ou C para cancelar.")
    
    def criar_folhas_mongodb(
        self,
        data: date,
        diretorio_destino: Optional[Union[str, Path]] = None,
        # Modo 1: Gerar por IDs específicos
        funcionario_id: Optional[ObjectId | str] = None,
        empresa_id: Optional[ObjectId | str] = None,
        # Modo 2: Gerar em lote por filtros
        filtros: Optional[Dict[str, Any]] = None
    ) -> Union[Dict[str, Any], None]:
        """
        Função unificada para gerar folhas de ponto do MongoDB.
        
        Suporta 2 modos de operação:
        
        MODO 1 - Por IDs individuais:
            Gera folha para UM funcionário+empresa específico
            >>> resultado = gerador.criar_folhas_mongodb(
            ...     data=date(2024, 1, 15),
            ...     funcionario_id="507f1f77bcf86cd799439011",
            ...     empresa_id="507f191e810c19729de860ea"
            ... )
            >>> print(resultado['status'])  # 'sucesso' ou None
        
        MODO 2 - Por filtros (lote):
            Gera folhas para MÚLTIPLOS funcionários
            >>> resultado = gerador.criar_folhas_mongodb(
            ...     data=date(2024, 1, 15),
            ...     filtros={"lotacao": "ADMINISTRATIVO", "status": "ativo"}
            ... )
            >>> print(f"Sucesso: {resultado['sucesso']}/{resultado['total']}")
        
        Args:
            data: Data de referência da folha (mês/ano)
            diretorio_destino: Diretório customizado para salvar PDFs (opcional)
            funcionario_id: [Modo 1] ObjectId do funcionário no MongoDB
            empresa_id: [Modo 1] ObjectId da empresa no MongoDB
            filtros: [Modo 2] Filtros MongoDB (ex: {"lotacao": "ADMINISTRATIVO"})
        
        Returns:
            Modo 1: Dict com status ou None se erro
            Modo 2: Dict com estatísticas da operação
        
        Raises:
            ValueError: Se modo inválido (ambos ou nenhum parâmetro)
        """
        if not all([self.servico_funcionario, self.servico_empresa]):
            logger.error("✗ Serviços MongoDB indisponíveis")
            return None
        
        # Validar modo de operação
        modo_individual = funcionario_id is not None and empresa_id is not None
        modo_lote = filtros is not None
        
        if modo_individual and modo_lote:
            raise ValueError(
                "❌ ERRO: Não pode usar AMBOS os modos!\n"
                "   - Modo individual: forneça funcionario_id + empresa_id\n"
                "   - Modo lote: forneça filtros\n"
                "   Use apenas UM modo por chamada."
            )
        
        if not modo_individual and not modo_lote:
            raise ValueError(
                "❌ ERRO: Nenhum modo especificado!\n"
                "   - Modo individual: forneça funcionario_id + empresa_id\n"
                "   - Modo lote: forneça filtros"
            )
        
        # ==================== MODO 1: INDIVIDUAL ====================
        if modo_individual:
            logger.info(f"\n{'=' * 80}")
            logger.info(f"GERAÇÃO INDIVIDUAL DE FOLHA")
            logger.info(f"{'=' * 80}")
            logger.info(f"Funcionário ID: {funcionario_id}")
            logger.info(f"Empresa ID: {empresa_id}")
            logger.info(f"Data: {data.strftime('%m/%Y')}")
            
            return self._processar_folha_unica(
                funcionario_id=funcionario_id,
                empresa_id=empresa_id,
                data=data,
                diretorio_destino=Path(diretorio_destino) if diretorio_destino else None
            )
        
        # ==================== MODO 2: LOTE ====================
        else:  # modo_lote
            logger.info(f"\n{'=' * 80}")
            logger.info(f"GERAÇÃO EM LOTE DE FOLHAS")
            logger.info(f"{'=' * 80}")
            logger.info(f"Filtros: {filtros}")
            logger.info(f"Data: {data.strftime('%m/%Y')}")
            
            try:
                # Buscar funcionários que atendem aos filtros
                logger.info("\n🔍 Buscando funcionários no MongoDB...")
                funcionarios = self.servico_funcionario.buscar_por_filtros(filtros)
                
                if not funcionarios:
                    logger.warning("⚠ Nenhum funcionário encontrado com os filtros especificados")
                    return {
                        "total": 0,
                        "sucesso": 0,
                        "erros": 0,
                        "taxa_sucesso": 0.0,
                        "detalhes": []
                    }
                
                logger.info(f"✓ {len(funcionarios)} funcionário(s) encontrado(s)")
                
                # Processar cada funcionário
                total = len(funcionarios)
                sucesso = 0
                erros = 0
                detalhes = []
                
                logger.info(f"\n{'=' * 80}")
                logger.info(f"PROCESSANDO {total} FUNCIONÁRIO(S)")
                logger.info(f"{'=' * 80}")
                
                for idx, funcionario in enumerate(funcionarios, 1):
                    funcionario_id = str(funcionario.get("_id"))
                    nome = funcionario.get("nome", "Desconhecido")
                    empresas_ids = funcionario.get("empresas_ids", [])
                    
                    logger.info(f"\n[{idx}/{total}] Processando: {nome}")
                    
                    if not empresas_ids:
                        logger.warning(f"⚠ Sem empresas vinculadas, pulando...")
                        erros += 1
                        detalhes.append({
                            "funcionario": nome,
                            "status": "erro",
                            "motivo": "Sem empresas vinculadas"
                        })
                        continue
                    
                    # Usar primeira empresa
                    empresa_id = str(empresas_ids[0])
                    
                    # Gerar folha
                    resultado = self._processar_folha_unica(
                        funcionario_id=funcionario_id,
                        empresa_id=empresa_id,
                        data=data,
                        diretorio_destino=Path(diretorio_destino) if diretorio_destino else None
                    )
                    
                    if resultado and resultado.get("status") == "sucesso":
                        sucesso += 1
                        detalhes.append({
                            "funcionario": nome,
                            "status": "sucesso",
                            "caminho_pdf": resultado.get("caminho_pdf")
                        })
                    else:
                        erros += 1
                        detalhes.append({
                            "funcionario": nome,
                            "status": "erro",
                            "motivo": "Falha na geração"
                        })
                
                # Resumo final
                taxa_sucesso = round(sucesso/total*100, 1) if total > 0 else 0
                logger.info(f"\n{'=' * 80}")
                logger.info(f"RESUMO DA OPERAÇÃO")
                logger.info(f"{'=' * 80}")
                logger.info(f"Total: {total}")
                logger.info(f"✓ Sucesso: {sucesso}")
                logger.info(f"✗ Erros: {erros}")
                logger.info(f"Taxa de sucesso: {taxa_sucesso}%")
                
                return {
                    "total": total,
                    "sucesso": sucesso,
                    "erros": erros,
                    "taxa_sucesso": taxa_sucesso,
                    "detalhes": detalhes
                }
                
            except Exception as e:
                logger.error(f"✗ Erro na geração em lote: {e}")
                logger.debug(traceback.format_exc())
                return {
                    "erro": str(e),
                    "tipo": type(e).__name__
                }


class Folha_de_Ponto:
    """
    Classe responsável por manipular as folhas de ponto dos funcionários.
    Esta classe segue os princípios SOLID, com responsabilidades bem definidas e separadas.
    
    Modos de operação:
        - modo padrão: Usa apenas MongoDB e gera PDFs via template HTML.
    
    Atributos:
        diretório_geral (Path): Diretório geral onde as folhas de ponto serão salvas.
        diretório_processamento (Path): Diretório onde os arquivos temporários serão processados.
    """
    
    def __init__(self):

        self.gerenciador_diretorios = GerenciadorDiretorios()
        self.diretório_geral = self.gerenciador_diretorios.buscar_diretorio_geral_ponto()
        self.diretório_processamento = self.gerenciador_diretorios.definir_diretorio_processamento()
        
        self._inicializar_gerador_mongodb()
    
    def _inicializar_gerador_mongodb(self):
        """
        Inicializa o gerador de folha de ponto para modo MongoDB puro (sem Excel).
        Permite usar métodos como criar_folhas_mongodb sem carregar planilhas.
        """
        try:
           
            # Buscar feriados do MongoDB
            
            # Carregar template HTML para geração direta de PDF
            html_modelo_path = Path(__file__).parent / "templates" / "Folha_de_Ponto.html"
            if html_modelo_path.exists():
                self.html_template = FolhaPontoHtmlTemplate(html_modelo_path)
                self.html_converter = HtmlToPdfConverter()
                logger.debug(f"✓ Template HTML carregado de: {html_modelo_path}")
            else:
                self.html_template = None
                self.html_converter = None
                logger.error(f"✗ Template HTML não encontrado: {html_modelo_path}")
            
            # Inicializar processador
            self.processador_folha_ponto = ProcessadorFolhaPonto()
            logger.debug("✓ Processador inicializado")
            
            # Inicializar gerador com os componentes necessários
            self.gerador_folha_ponto = GeradorFolhaPonto(
                gerenciador_diretorios=self.gerenciador_diretorios,
                processador_folha_ponto=self.processador_folha_ponto,
                html_template=self.html_template,
                html_converter=self.html_converter,
                modo_mongodb_puro=True
            )
            logger.debug("✓ Gerador de folha de ponto inicializado (modo MongoDB)")
        except Exception as e:
            logger.error(f"✗ Erro ao inicializar gerador MongoDB: {e}")
            self.gerador_folha_ponto = None
    
    
    def _carregar_dados_funcionarios_mongodb(self) -> pd.DataFrame:
        """
        Carrega os funcionários do MongoDB e retorna um DataFrame.
        """
        try:
            from src.services.funcionario_service import FuncionarioService

            servico = FuncionarioService()
            if not servico.disponivel:
                logger.warning("⚠ Serviço de funcionários não disponível")
                return pd.DataFrame()

            funcionarios = []
            skip = 0
            limite = 1000
            total = None

            while True:
                resultado = servico.listar_todos(skip=skip, limit=limite)
                dados = resultado.get("dados", [])
                if not dados:
                    break

                funcionarios.extend(dados)
                if total is None:
                    total = resultado.get("total", len(dados))

                skip += limite
                if total is not None and skip >= total:
                    break

            df = pd.json_normalize(funcionarios)
            if "_id" in df.columns:
                df["_id"] = df["_id"].astype(str)

            self.dados_funcionarios = df
            logger.debug(f"✓ DataFrame de funcionários MongoDB carregado ({len(df)} registros)")
            return df
        except Exception as e:
            logger.warning(f"⚠ Falha ao carregar funcionários do MongoDB: {e}")
            return pd.DataFrame()

    
    def __str__(self):
        return f"""Diretório Geral: {self.diretório_geral}\n\n
                Dados das Empresas:\n {self.dados_empresas}\n\n
                Dados dos Funcionários:\n {self.dados_funcionarios}\n\n
                Dados dos Horários:\n {self.dados_horarios}\n\n
                """
    
    # ==================== MÉTODOS PÚBLICOS (MongoDB) ====================
    
    def criar_dataFrame_funcionários(self):
        """Retorna DataFrame dos funcionários carregados do MongoDB."""
        return self._carregar_dados_funcionarios_mongodb()

    def exportar_dataframe(self, diretorio_destino: Union[str, Path] = None) -> None:
        """Exporta os dados de funcionários para um arquivo em disco."""
        df = self.criar_dataFrame_funcionários()
        if df.empty:
            raise ValueError("Não há dados de funcionários para exportar.")

        if diretorio_destino is None:
            raise ValueError("O caminho de destino é obrigatório.")

        diretorio_destino = Path(diretorio_destino)
        formato = diretorio_destino.suffix.lower().lstrip('.')

        if formato == "xlsx":
            df.to_excel(diretorio_destino, index=False)
        elif formato == "csv":
            df.to_csv(diretorio_destino, index=False)
        elif formato == "json":
            df.to_json(diretorio_destino, orient="records", force_ascii=False)
        elif formato == "html":
            df.to_html(diretorio_destino, index=False)
        else:
            raise ValueError("Formato inválido para exportação.")

        logger.info(f"Arquivo exportado com sucesso para {diretorio_destino}")

    
    
    def criar_mongodb_por_id(self, funcionario_id: ObjectId | str, empresa_id: ObjectId | str, data: date,
                             diretorio_destino: Union[str, Path] = None) -> Optional[Dict[str, Any]]:
        """
        Cria folha de ponto a partir de dados do MongoDB usando IDs específicos.
        
        Args:
            funcionario_id: ObjectId do funcionário no MongoDB
            empresa_id: ObjectId da empresa no MongoDB
            data: Data de referência da folha (mês/ano)
            diretorio_destino: Diretório customizado para salvar PDF (opcional)
        
        Returns:
            Dict com status da operação ou None se erro
        
        Exemplo:
            >>> folha = Folha_de_Ponto()
            >>> resultado = folha.criar_mongodb_por_id(
            ...     funcionario_id="507f1f77bcf86cd799439011",
            ...     empresa_id="507f191e810c19729de860ea",
            ...     data=date(2024, 1, 1)
            ... )
            >>> print(resultado['status'])  # 'sucesso'
        """
        return self.gerador_folha_ponto.criar_folhas_mongodb(
            data=data,
            funcionario_id=funcionario_id,
            empresa_id=empresa_id,
            diretorio_destino=diretorio_destino
        )
    
    def criar_mongodb_por_filtros(self, filtros: Dict[str, Any], data: date,
                                  diretorio_destino: Union[str, Path] = None) -> Dict[str, Any]:
        """
        Cria folhas de ponto para múltiplos funcionários usando filtros do MongoDB.
        
        Args:
            filtros: Filtros MongoDB (ex: {"lotacao": "RH", "status": "ativo"})
            data: Data de referência da folha (mês/ano)
            diretorio_destino: Diretório customizado para salvar PDFs (opcional)
        
        Returns:
            Dict com estatísticas da operação
        
        Exemplo:
            >>> folha = Folha_de_Ponto()
            >>> resultado = folha.criar_mongodb_por_filtros(
            ...     filtros={"lotacao": "RH"},
            ...     data=date(2024, 1, 1)
            ... )
            >>> print(f"Sucesso: {resultado['sucesso']}/{resultado['total']}")
        """
        return self.gerador_folha_ponto.criar_folhas_mongodb(
            data=data,
            filtros=filtros,
            diretorio_destino=diretorio_destino
        )
    
    def gerar_pdf_de_folha_existente(
        self, 
        folha_existente: Dict[str, Any], 
        diretorio_destino: Union[str, Path] = None
    ) -> Optional[str]:
        """
        Gera um PDF a partir de dados de uma folha de ponto existente no MongoDB.
        
        Usa o fluxo 100% MongoDB para gerar o PDF.
        
        Args:
            folha_existente: Documento da folha de ponto do MongoDB
            funcionario: Documento do funcionário do MongoDB
            diretorio_destino: Diretório para salvar o PDF (opcional)
        
        Returns:
            Caminho do PDF gerado ou None se erro
        """
        try:
            funcionario_id = folha_existente.get("funcionario_id")
            empresa_id = folha_existente.get("empresa_id")
            mes_referencia = folha_existente.get("mes_referencia", "")
            
            if not funcionario_id or not empresa_id:
                logger.error("Funcionário ou empresa não encontrados na folha existente")
                return None
                        
            # Converter mes_referencia (YYYY-MM) para data
            try:
                ano, mes = mes_referencia.split('-')
                data_referencia = date(int(ano), int(mes), 1)
            except Exception:
                data_referencia = date.today()
            
            # Usar o fluxo 100% MongoDB para gerar o PDF
            resultado = self.criar_mongodb_por_id(
                funcionario_id=str(funcionario_id),
                empresa_id=str(empresa_id),
                data=data_referencia,
                diretorio_destino=diretorio_destino
            )
            
            if resultado and resultado.get('status') == 'sucesso':
                caminho_pdf = resultado.get('caminho_pdf')
                logger.info(f"✓ PDF gerado: {caminho_pdf}")
                return caminho_pdf
            else:
                logger.warning(f"Falha ao gerar PDF para funcionário {funcionario_id}")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao gerar PDF de folha existente: {e}")
            return None

    def _normalizar_nome(self, nome: str) -> str:
        """Normaliza nome para busca (remove acentos, minúsculas)."""
        if not nome:
            return ""
        nome_normalizado = unicodedata.normalize('NFKD', nome)
        nome_normalizado = ''.join([c for c in nome_normalizado if not unicodedata.combining(c)])
        return nome_normalizado.lower().strip()

    def _montar_contexto_html_editado(
        self,
        folha: Dict[str, Any],
        data_referencia: date,
        funcionario: Optional[Dict[str, Any]] = None,
        empresa: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Monta o contexto HTML de uma folha editada para regenerar o PDF.

        Reutiliza a estrutura de ``criar_contexto_html`` preenchendo os dias
        com os dados editados (horários, observações, tipo de dia).

        Args:
            folha: Documento da folha (do MongoDB)
            data_referencia: Data de referência (mês/ano)
            funcionario: Documento do funcionário (opcional)
            empresa: Documento da empresa (opcional)

        Returns:
            Dict com o contexto pronto para renderizar o template HTML
        """
        folha_data = folha.get("folha_data", {}) or {}
        dias_mongodb = folha_data.get("dias", []) or []

        # Mapa dia_numero -> dados editados
        dias_por_numero = {}
        for dia in dias_mongodb:
            if isinstance(dia, dict):
                numero = dia.get("numero_dia")
            else:
                numero = getattr(dia, "numero_dia", None)
            if numero is not None:
                dias_por_numero[numero] = dia

        # Resolver feriados do período para marcar eh_descanso
        feriados = set()
        try:
            if self.processador_folha_ponto and hasattr(self.processador_folha_ponto, 'feriados'):
                import pandas as pd
                feriados_df = self.processador_folha_ponto.feriados
                if isinstance(feriados_df, pd.DataFrame) and 'DATA' in feriados_df.columns:
                    feriados = {
                        d.date() for d in feriados_df['DATA'].dropna().tolist()
                        if isinstance(d, datetime) or hasattr(d, 'date')
                    }
        except Exception:
            pass

        nomes_dias_pt = {
            0: 'Segunda', 1: 'Terça', 2: 'Quarta', 3: 'Quinta',
            4: 'Sexta', 5: 'Sábado', 6: 'Domingo',
        }

        data_inicial = data_referencia.replace(day=1)
        ultimo_dia = calendar.monthrange(data_referencia.year, data_referencia.month)[1]
        data_final = date(data_referencia.year, data_referencia.month, ultimo_dia)

        dias = []
        current_date = data_inicial
        while current_date <= data_final:
            eh_feriado = current_date in feriados
            eh_fim_de_semana = current_date.weekday() >= 5

            dia_numero = current_date.day
            dia_mongo = dias_por_numero.get(dia_numero, {}) or {}

            def _campo(dia, nome):
                if isinstance(dia, dict):
                    return dia.get(nome)
                return getattr(dia, nome, None)

            entrada = _campo(dia_mongo, "hora_entrada") or ""
            saida = _campo(dia_mongo, "hora_saida") or ""
            intervalo_inicio = _campo(dia_mongo, "hora_intervalo_inicio") or ""
            intervalo_fim = _campo(dia_mongo, "hora_intervalo_fim") or ""
            observacoes = _campo(dia_mongo, "observacoes") or ""
            tipo_dia = _campo(dia_mongo, "tipo_dia") or ""
            if hasattr(tipo_dia, "value"):
                tipo_dia = tipo_dia.value

            # Tipo de dia FALTA/FERIADO vira observação no PDF
            obs_final = observacoes or ""
            if tipo_dia and str(tipo_dia).upper() in ("FALTA", "FERIADO", "ATESTADO", "FOLGA", "LICENÇA", "LICENCA", "FÉRIAS", "FERIAS"):
                obs_final = (f"{tipo_dia}: {obs_final}").strip() if obs_final else str(tipo_dia)

            dias.append({
                'dia_numero': str(dia_numero).zfill(2),
                'dia_semana': nomes_dias_pt[current_date.weekday()],
                'entrada': entrada,
                'intervalo_inicio': intervalo_inicio,
                'intervalo_fim': intervalo_fim,
                'termino': saida,
                'observacoes': obs_final,
                'eh_descanso': eh_feriado or eh_fim_de_semana,
            })
            current_date += timedelta(days=1)

        # Dados da empresa
        dados_empresa = {}
        if empresa:
            dados_empresa = {
                'nome': empresa.get('nome', ''),
                'atividade': empresa.get('atividade', ''),
                'endereco': empresa.get('endereco', ''),
                'cnpj': empresa.get('cnpj', ''),
            }

        funcionario_data = folha_data
        contexto = {
            'FP': {
                'id': str(folha.get('_id', '')) if folha.get('_id') else '',
                'periodo_inicio': data_inicial.strftime('%d/%m/%Y'),
                'periodo_fim': data_final.strftime('%d/%m/%Y'),
            },
            'periodo': {
                'inicio': data_inicial.strftime('%d/%m/%Y'),
                'fim': data_final.strftime('%d/%m/%Y'),
            },
            'data_geracao': datetime.now().strftime('%d/%m/%Y'),
            'empresa': dados_empresa,
            'funcionario': {
                'nome': funcionario_data.get('nome_funcionario') if not funcionario else funcionario.get('nome', funcionario_data.get('nome_funcionario', '')),
                'cargo': funcionario_data.get('cargo_funcionario', ''),
                'departamento': funcionario_data.get('lotacao_funcionario', ''),
                'lotacao': funcionario_data.get('lotacao_funcionario', ''),
                'contrato': funcionario_data.get('contrato_funcionario', ''),
                'horario': funcionario_data.get('horario_funcionario', ''),
                'cpf': funcionario_data.get('cpf_funcionario', '') or '',
            },
            'dias': dias,
            'total_dias': len(dias),
            'feriados': [d.strftime('%d/%m/%Y') for d in sorted(feriados)],
        }

        return contexto

    def regenerar_pdf_folha(
        self,
        folha: Dict[str, Any],
        diretorio_destino: Union[str, Path] = None,
    ) -> Optional[str]:
        """
        Regenera o PDF de uma folha editada a partir dos dados do MongoDB
        (dias já editados/recalculados), mantendo banco e PDF consistentes.

        Args:
            folha: Documento da folha (do MongoDB)
            diretorio_destino: Diretório customizado para salvar o PDF

        Returns:
            Caminho do PDF gerado ou None se erro
        """
        try:
            if not self.html_template or not self.html_converter:
                logger.error("Template HTML ou conversor não disponível para regenerar PDF")
                return None

            funcionario_id = folha.get("funcionario_id")
            empresa_id = folha.get("empresa_id")
            mes_referencia = folha.get("mes_referencia", "")

            if not funcionario_id or not empresa_id:
                logger.error("Funcionário ou empresa não encontrados na folha")
                return None

            try:
                ano, mes = mes_referencia.split('-')
                data_referencia = date(int(ano), int(mes), 1)
            except Exception:
                data_referencia = date.today()

            # Buscar funcionário e empresa para contexto
            funcionario = None
            empresa = None
            try:
                if self.gerador_folha_ponto and self.gerador_folha_ponto.servico_funcionario:
                    funcionario = self.gerador_folha_ponto.servico_funcionario.buscar_por_object_id(funcionario_id)
            except Exception:
                pass
            try:
                if self.gerador_folha_ponto and self.gerador_folha_ponto.servico_empresa:
                    empresa = self.gerador_folha_ponto.servico_empresa.buscar_por_id(str(empresa_id))
            except Exception:
                pass

            contexto = self._montar_contexto_html_editado(
                folha, data_referencia, funcionario=funcionario, empresa=empresa
            )

            html_text = self.html_template.render(contexto)

            # Determinar caminho do PDF
            if diretorio_destino:
                diretorio_pdf = Path(diretorio_destino)
                diretorio_pdf.mkdir(parents=True, exist_ok=True)
                nome_arquivo = f"folha_{mes_referencia}_{str(funcionario_id)[-6:]}.pdf"
                caminho_arquivo_pdf = diretorio_pdf / nome_arquivo
            else:
                caminho_existente = folha.get("caminho_arquivo_gerado")
                if caminho_existente:
                    caminho_arquivo_pdf = Path(caminho_existente)
                    caminho_arquivo_pdf.parent.mkdir(parents=True, exist_ok=True)
                else:
                    # Fallback: usar estrutura de diretórios padrão
                    gerenciador = self.gerenciador_diretorios
                    diretorio_geral = gerenciador.buscar_diretorio_geral_ponto()
                    nome_funcionario = contexto.get('funcionario', {}).get('nome', 'FUNCIONARIO')
                    safe_nome = re.sub(r'[^A-Za-z0-9 _-]', '', nome_funcionario or '').strip() or "FUNCIONARIO"
                    safe_nome = re.sub(r'\s+', ' ', safe_nome)
                    diretorio_pdf = diretorio_geral / str(data_referencia.year) / f"{data_referencia.strftime('%m')}.{data_referencia.strftime('%Y')}"
                    diretorio_pdf.mkdir(parents=True, exist_ok=True)
                    caminho_arquivo_pdf = diretorio_pdf / f"{safe_nome.title()}.pdf"

            self.html_converter.salvar_html_como_pdf(html_text, caminho_arquivo_pdf)
            logger.info(f"✓ PDF regenerado: {caminho_arquivo_pdf}")
            return str(caminho_arquivo_pdf)

        except Exception as e:
            logger.error(f"Erro ao regenerar PDF da folha: {e}")
            logger.debug(traceback.format_exc())
            return None

    def editar_folha(
        self,
        folha_id: str,
        dias_editados: Optional[List[Dict[str, Any]]] = None,
        observacoes_gerais: Optional[str] = None,
        atualizar_pdf: bool = True,
        diretorio_destino: Union[str, Path] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Edita uma folha de ponto já gerada:
        1. Aplica as alterações nos dias (horários, tipo de dia, observações)
        2. RECALCULA os totais (mesmo cálculo da geração)
        3. REGENERA o PDF automaticamente (banco e PDF nunca divergem)
        4. Incrementa ``versao`` e registra em ``historico_alteracoes``

        Args:
            folha_id: ObjectId da folha no MongoDB
            dias_editados: Lista de dicts com os dias corrigidos
            observacoes_gerais: Observação geral da folha (opcional)
            atualizar_pdf: Se True, regenera o PDF automaticamente
            diretorio_destino: Diretório customizado para o PDF

        Returns:
            Dict com resultado ou None se erro
        """
        try:
            from src.processadores.processador_folha_ponto import (
                calcular_total_horas,
                recalcular_totais_folha,
            )
            from src.services.folha_ponto_service import FolhaDePontoService

            servico = None
            if self.gerador_folha_ponto and self.gerador_folha_ponto.servico_folha_ponto:
                servico = self.gerador_folha_ponto.servico_folha_ponto
            else:
                servico = FolhaDePontoService()

            if not servico or not servico.disponivel:
                logger.error("Serviço de folha de ponto não disponível para edição")
                return None

            folha = servico.buscar_por_id(folha_id)
            if not folha:
                logger.error(f"Folha não encontrada para edição: {folha_id}")
                return None

            if folha.get("excluida"):
                logger.warning(f"Folha {folha_id} está excluída (soft delete). Edição bloqueada.")
                return {"status": "bloqueada", "motivo": "Folha excluída"}

            # Aplicar edições nos dias
            folha_data = folha.get("folha_data", {}) or {}
            dias = folha_data.get("dias", []) or []
            dias_por_numero = {}
            for dia in dias:
                if isinstance(dia, dict):
                    dias_por_numero[dia.get("numero_dia")] = dia
                else:
                    dias_por_numero[getattr(dia, "numero_dia", None)] = dia

            campos_dia = [
                "hora_entrada", "hora_saida", "hora_intervalo_inicio",
                "hora_intervalo_fim", "tipo_dia", "observacoes",
                "preenchido_manualmente",
            ]

            campos_alterados = []
            for edicao in dias_editados or []:
                numero = edicao.get("numero_dia")
                if numero is None:
                    continue
                dia_alvo = dias_por_numero.get(numero)
                if dia_alvo is None:
                    continue

                # Guardar estado anterior p/ histórico
                estado_anterior = {}
                for campo in campos_dia:
                    if isinstance(dia_alvo, dict):
                        estado_anterior[campo] = dia_alvo.get(campo)
                    else:
                        estado_anterior[campo] = getattr(dia_alvo, campo, None)

                for campo, valor in edicao.items():
                    if campo == "numero_dia":
                        continue
                    if campo == "limpar_campos":
                        continue
                    if isinstance(dia_alvo, dict):
                        dia_alvo[campo] = valor
                    else:
                        setattr(dia_alvo, campo, valor)

                # Limpar campos marcados (string vazia = intenção de limpar)
                for campo_limpar in edicao.get("limpar_campos", []):
                    if isinstance(dia_alvo, dict):
                        dia_alvo[campo_limpar] = None
                    else:
                        setattr(dia_alvo, campo_limpar, None)

                # Recalcular total_horas_trabalhadas do dia
                entrada = estado_anterior.get("hora_entrada")
                saida = estado_anterior.get("hora_saida")
                intervalo_inicio = estado_anterior.get("hora_intervalo_inicio")
                intervalo_fim = estado_anterior.get("hora_intervalo_fim")
                # Se o campo veio na edição (set), usa o novo valor
                if "hora_entrada" in edicao:
                    entrada = edicao["hora_entrada"]
                if "hora_saida" in edicao:
                    saida = edicao["hora_saida"]
                if "hora_intervalo_inicio" in edicao:
                    intervalo_inicio = edicao["hora_intervalo_inicio"]
                if "hora_intervalo_fim" in edicao:
                    intervalo_fim = edicao["hora_intervalo_fim"]
                # Se campo foi limpo, usar None (não o valor antigo)
                for campo_limpar in edicao.get("limpar_campos", []):
                    if campo_limpar == "hora_entrada":
                        entrada = None
                    elif campo_limpar == "hora_saida":
                        saida = None
                    elif campo_limpar == "hora_intervalo_inicio":
                        intervalo_inicio = None
                    elif campo_limpar == "hora_intervalo_fim":
                        intervalo_fim = None

                total_horas_dia = calcular_total_horas(entrada, saida, intervalo_inicio, intervalo_fim)
                if isinstance(dia_alvo, dict):
                    dia_alvo["total_horas_trabalhadas"] = total_horas_dia
                else:
                    setattr(dia_alvo, "total_horas_trabalhadas", total_horas_dia)

                if edicao.get("hora_entrada") or edicao.get("hora_saida") or edicao.get("tipo_dia") or edicao.get("observacoes"):
                    campos_alterados.append(numero)

            # Recalcular totais do mês (mesmo cálculo da geração)
            totais = recalcular_totais_folha(dias)

            nova_folha_data = dict(folha_data)
            nova_folha_data["dias"] = dias
            nova_folha_data["total_horas_mes"] = totais["total_horas_mes"]
            nova_folha_data["total_faltas"] = totais["total_faltas"]
            nova_folha_data["total_feriados"] = totais["total_feriados"]
            nova_folha_data["total_finais_semana"] = totais["total_finais_semana"]
            nova_folha_data["preenchimento_concluido"] = True
            # Garantir nome_normalizado (cobre folhas antigas sem o campo)
            nome_func = nova_folha_data.get("nome_funcionario")
            if nome_func and not nova_folha_data.get("nome_normalizado"):
                nova_folha_data["nome_normalizado"] = self._normalizar_nome(nome_func)
            if observacoes_gerais:
                nova_folha_data["observacoes_gerais"] = observacoes_gerais

            detalhes_historico = {
                "dias_alterados": campos_alterados,
                "totais": totais,
            }
            if observacoes_gerais:
                detalhes_historico["observacoes_gerais"] = observacoes_gerais

            # Regenerar PDF ANTES de salvar para gravar o caminho atualizado no banco
            caminho_pdf = None
            if atualizar_pdf:
                caminho_pdf = self.regenerar_pdf_folha(
                    {**folha, "folha_data": nova_folha_data},
                    diretorio_destino=diretorio_destino,
                )
                if caminho_pdf:
                    nova_folha_data["caminho_pdf_regenerado"] = caminho_pdf

            # Salvar no banco com versão + histórico
            salvo = servico.atualizar_folha(
                folha_id,
                {"folha_data": nova_folha_data, "caminho_arquivo_gerado": caminho_pdf or folha.get("caminho_arquivo_gerado")},
                acao="Folha editada manualmente",
                detalhes_historico=detalhes_historico,
            )

            if not salvo:
                logger.error(f"Falha ao salvar edição da folha {folha_id}")
                return None

            versao_nova = folha.get("versao", 1) + 1
            logger.info(f"✓ Folha editada: {folha_id} (versão {versao_nova})")
            return {
                "status": "sucesso",
                "folha_id": folha_id,
                "versao": versao_nova,
                "caminho_pdf": caminho_pdf,
                "totais": totais,
                "dias_alterados": campos_alterados,
            }

        except Exception as e:
            logger.error(f"Erro ao editar folha: {e}")
            logger.debug(traceback.format_exc())
            return None

    def análise_folha_de_ponto(
        self,
        arquivo: Union[str, Path],
    ) -> Dict[str, Any]:
        """
        Analisa um arquivo de folha de ponto (PDF) já preenchido.

        Reutiliza o mesmo pipeline de análise usado pela TUI e pelo comando
        ``processar_pdfs`` (verificacao + extracao via IA com Gemini + validacao
        Pydantic). A diferenca e que, aqui, em vez de apenas processar em lote,
        retorna um resumo estruturado da analise para que o CLI ``análise``
        possa exibi-lo de forma legivel.

        Args:
            arquivo: Caminho para o PDF da folha de ponto a analisar.

        Returns:
            Dict com resumo da analise:
                - arquivo: caminho do arquivo analisado
                - verificacoes/passou: se o arquivo passou nas validacoes
                - funcionario: nome/id encontrado (se houver)
                - analise_ia: dados estruturados da analise (se houver)
                - erros/avisos: mensagens da analise
        """
        from src.processadores.processador_folha_ponto import ProcessadorFolhaPonto
        from pathlib import Path
        from pprint import pformat

        caminho = Path(arquivo)

        if not caminho.is_file():
            logger.error(f"Arquivo não encontrado para análise: {caminho}")
            return {
                "arquivo": str(caminho),
                "passou": False,
                "erros": [f"Arquivo não encontrado: {caminho}"],
            }

        if caminho.suffix.lower() != ".pdf":
            logger.warning(f"Arquivo não é PDF, prosseguindo assim mesmo: {caminho}")

        logger.info(f"\n{'=' * 80}")
        logger.info(f"ANÁLISE DA FOLHA DE PONTO: {caminho.name}")
        logger.info(f"{'=' * 80}")

        try:
            processador = ProcessadorFolhaPonto()
            resultado = processador.processar(str(caminho))

            analise = {
                "arquivo": str(caminho),
                "nome_arquivo": caminho.name,
                "passou": resultado.armazenamento_sucesso,
                "funcionario": resultado.funcionario_nome_encontrado,
                "funcionario_id": resultado.funcionario_id,
                "folha_id": resultado.folha_id,
                "tempo_s": resultado.tempo_processamento_total_s,
                "dias_extraidos": resultado.extracao_resultado.dias_com_dados
                if resultado.extracao_resultado
                else 0,
                "avisos": resultado.avisos,
                "erros": resultado.erros,
            }

            if resultado.armazenamento_sucesso:
                logger.info(f"✓ Análise concluída para {caminho.name}")
            else:
                logger.error(f"✗ Falha na análise de {caminho.name}")

            logger.debug(pformat(analise))
            return analise

        except Exception as e:
            logger.error(f"Erro ao analisar folha de ponto: {e}")
            return {
                "arquivo": str(caminho),
                "nome_arquivo": caminho.name,
                "passou": False,
                "erros": [str(e)],
            }

    #TODO: Verificar futuramente sobre essa função para testar se está de acordo o processamento das folhas de ponto e sendo salvos no mongodb.
    def processar_pdfs(
        self,
        caminho_pdfs: Union[str, Path, List[Union[str, Path]]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Processa um ou múltiplos arquivos PDF de folhas de ponto preenchidas
        usando IA (Gemini) e armazena os dados em MongoDB.
        
        Args:
            caminho_pdfs: Caminho para arquivo PDF, diretório contendo PDFs, 
                         ou lista de caminhos de arquivos PDF
            **kwargs: Argumentos adicionais (não utilizados, mantidos para compatibilidade)
        
        Returns:
            Dict com resumo do processamento:
                {
                    'total_arquivos': int,
                    'processados_sucesso': int,
                    'processados_erro': int,
                    'resultados': List[Dict]
                }
        
        Examples:
            >>> fp = Folha_de_Ponto()
            >>> # Processar um arquivo
            >>> fp.processar_pdfs("caminho/folha.pdf")
            >>> 
            >>> # Processar múltiplos arquivos
            >>> fp.processar_pdfs(["folha1.pdf", "folha2.pdf"])
            >>> 
            >>> # Processar todos PDFs de um diretório
            >>> fp.processar_pdfs("caminho/pasta_pdfs/")
        """
        from src.processadores.processador_folha_ponto import ProcessadorFolhaPonto
        from pathlib import Path
        
        logger.info("=" * 80)
        logger.info("INICIANDO PROCESSAMENTO DE FOLHAS DE PONTO (PDF → MongoDB)")
        logger.info("=" * 80)
        
        # Normalizar entrada para lista de arquivos
        arquivos_para_processar = []
        
        if isinstance(caminho_pdfs, (str, Path)):
            caminho = Path(caminho_pdfs)
            
            if caminho.is_dir():
                # Buscar todos os PDFs no diretório
                arquivos_para_processar = list(caminho.glob("*.pdf"))
                logger.info(f"📁 Diretório detectado: {caminho}")
                logger.info(f"   Encontrados {len(arquivos_para_processar)} arquivo(s) PDF")
            elif caminho.is_file():
                # Arquivo único
                arquivos_para_processar = [caminho]
                logger.info(f"📄 Arquivo único: {caminho}")
            else:
                logger.error(f"❌ Caminho não existe: {caminho}")
                return {
                    'total_arquivos': 0,
                    'processados_sucesso': 0,
                    'processados_erro': 0,
                    'resultados': []
                }
        
        elif isinstance(caminho_pdfs, list):
            # Lista de arquivos
            arquivos_para_processar = [Path(p) for p in caminho_pdfs]
            logger.info(f"📋 Lista de {len(arquivos_para_processar)} arquivo(s) fornecida")
        
        else:
            logger.error(f"❌ Tipo de entrada inválido: {type(caminho_pdfs)}")
            return {
                'total_arquivos': 0,
                'processados_sucesso': 0,
                'processados_erro': 0,
                'resultados': []
            }
        
        # Validar arquivos
        arquivos_validos = []
        for arquivo in arquivos_para_processar:
            if not arquivo.exists():
                logger.warning(f"⚠️  Arquivo não existe: {arquivo}")
                continue
            if arquivo.suffix.lower() != '.pdf':
                logger.warning(f"⚠️  Arquivo não é PDF: {arquivo}")
                continue
            arquivos_validos.append(arquivo)
        
        if not arquivos_validos:
            logger.error("❌ Nenhum arquivo PDF válido para processar!")
            return {
                'total_arquivos': 0,
                'processados_sucesso': 0,
                'processados_erro': 0,
                'resultados': []
            }
        
        logger.info(f"\n🎯 Total de arquivos válidos a processar: {len(arquivos_validos)}")
        logger.info("=" * 80)
        
        # Criar processador
        processador = ProcessadorFolhaPonto()
        
        # Processar cada arquivo
        resultados = []
        sucesso = 0
        erro = 0
        
        for idx, arquivo in enumerate(arquivos_validos, 1):
            logger.info(f"\n[{idx}/{len(arquivos_validos)}] Processando: {arquivo.name}")
            logger.info("-" * 80)
            
            try:
                resultado = processador.processar(str(arquivo))
                
                resultados.append({
                    'arquivo': str(arquivo),
                    'nome_arquivo': arquivo.name,
                    'sucesso': resultado.armazenamento_sucesso,
                    'funcionario_id': resultado.funcionario_id,
                    'funcionario_nome': resultado.funcionario_nome_encontrado,
                    'folha_id': resultado.folha_id,
                    'tempo_s': resultado.tempo_processamento_total_s,
                    'dias_extraidos': resultado.extracao_resultado.dias_com_dados if resultado.extracao_resultado else 0,
                    'avisos': resultado.avisos,
                    'erros': resultado.erros
                })
                
                if resultado.armazenamento_sucesso:
                    sucesso += 1
                    logger.info(f"✅ SUCESSO - {arquivo.name}")
                    logger.info(f"   Funcionário: {resultado.funcionario_nome_encontrado} ({resultado.funcionario_id})")
                    logger.info(f"   Folha ID: {resultado.folha_id}")
                    logger.info(f"   Dias extraídos: {resultado.extracao_resultado.dias_com_dados if resultado.extracao_resultado else 0}")
                    logger.info(f"   Tempo: {resultado.tempo_processamento_total_s:.2f}s")
                else:
                    erro += 1
                    logger.error(f"❌ ERRO - {arquivo.name}")
                    if resultado.erros:
                        for err in resultado.erros:
                            logger.error(f"   • {err}")
            
            except Exception as e:
                erro += 1
                logger.error(f"❌ EXCEÇÃO - {arquivo.name}: {str(e)}")
                resultados.append({
                    'arquivo': str(arquivo),
                    'nome_arquivo': arquivo.name,
                    'sucesso': False,
                    'erro': str(e)
                })
        
        # Resumo final
        logger.info("\n" + "=" * 80)
        logger.info("RESUMO DO PROCESSAMENTO")
        logger.info("=" * 80)
        logger.info(f"Total de arquivos: {len(arquivos_validos)}")
        logger.info(f"✅ Processados com sucesso: {sucesso}")
        logger.info(f"❌ Erros: {erro}")
        logger.info(f"Taxa de sucesso: {(sucesso/len(arquivos_validos)*100):.1f}%")
        logger.info("=" * 80)
        
        return {
            'total_arquivos': len(arquivos_validos),
            'processados_sucesso': sucesso,
            'processados_erro': erro,
            'resultados': resultados
        }


