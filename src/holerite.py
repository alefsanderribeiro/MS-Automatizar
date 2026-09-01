from pathlib import Path
from typing import List, Union, Tuple, Optional
import datetime
from concurrent.futures import ThreadPoolExecutor
import locale
from abc import ABC, abstractmethod
import PyPDF2
import shutil
from src.utils.pdf_conversor import converter_pdf_para_imagens
import tempfile
import re

# Imports dos serviços que permanecem separados
from src.services.analise_ai_service import GeminiService, MistralService
from src.services.cache_ocr_service import cache_ocr
from src.utils.logger_config import logger

# Define o locale para português do Brasil, de forma segura (nunca quebra o
# import em sistemas que não têm o locale instalado — ex.: muitos servidores
# Linux). Se nenhuma variante for encontrada, mantém o locale padrão e segue.
for _locale_candidato in ('pt_BR.UTF-8', 'pt_BR.utf8', 'pt_BR', 'pt_PT.UTF-8', 'pt_PT'):
    try:
        locale.setlocale(locale.LC_TIME, _locale_candidato)
        break
    except locale.Error:
        continue


# ==================== INTERFACES ====================

class IArquivoProcessor(ABC):
    """Interface para processamento de arquivos"""
    
    @abstractmethod
    def processar_arquivo(self, arquivo: Path, diretorio: Path) -> bool:
        pass


class IExtractorNome(ABC):
    """Interface para extração de nomes"""
    
    @abstractmethod
    def extrair_nome(self, arquivo: Path) -> str:
        pass


class IAnaliseHolerite(ABC):
    """Interface para análise de holerites"""
    
    @abstractmethod
    def analisar(self, arquivo: Path) -> str:
        pass


class IDirectoryFilter(ABC):
    """Interface para filtros de diretório"""
    
    @abstractmethod
    def filtrar(self, diretorios: List[Path], criterio: str) -> List[Path]:
        pass


class IPdfProcessor(ABC):
    """Interface para processamento de PDF"""
    
    @abstractmethod
    def extrair_cabecalho(self, arquivo: Path) -> Path:
        pass


# ==================== SERVIÇOS CONSOLIDADOS ====================

class PdfProcessorService(IPdfProcessor):
    """Serviço para processamento de arquivos PDF"""
    
    def __init__(self, diretorio_processamento: Path):
        self.diretorio_processamento = diretorio_processamento
        self.coordenadas_cabecalho = ((120, 785), (363, 795))
    
    def extrair_cabecalho(self, arquivo: Path) -> Path:
        self.diretorio_processamento.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(dir=self.diretorio_processamento) as temp_dir:
            arquivo_recortado = Path(temp_dir) / f"{arquivo.stem}_cropped.pdf"
            self._recortar_cabecalho(arquivo, arquivo_recortado)

            arquivo_imagem = self._converter_para_imagem(arquivo_recortado, arquivo.stem)
            return arquivo_imagem
        
    
    def _criar_copia_temporaria(self, arquivo: Path) -> Path:
        """Cria uma cópia temporária do arquivo"""
        arquivo_copia = self.diretorio_processamento / f"{arquivo.stem}_temp.pdf"
        shutil.copy(arquivo, arquivo_copia)
        return arquivo_copia
    
    def _recortar_cabecalho(self, arquivo: Path, arquivo_recortado: Path) -> None:
        with open(arquivo, 'rb') as pdf_file:
            reader = PyPDF2.PdfReader(pdf_file)
            writer = PyPDF2.PdfWriter()

            first_page = reader.pages[0]
            lower_left, upper_right = self.coordenadas_cabecalho
            first_page.cropbox.lower_left = lower_left
            first_page.cropbox.upper_right = upper_right
            writer.add_page(first_page)

            with open(arquivo_recortado, 'wb') as output_pdf:
                writer.write(output_pdf)
                
    
    def _converter_para_imagem(self, arquivo_pdf: Path, nome_base: str) -> Path:
        """Converte PDF para imagem PNG (sem programa externo)."""
        if not arquivo_pdf.exists():
            raise FileNotFoundError(f"Arquivo PDF não encontrado: {arquivo_pdf}")

        arquivo_imagem = self.diretorio_processamento / f"{nome_base}.png"

        # Usa pypdfium2 embutido (cross-platform) em vez de pdf2image+poppler.
        # O uso de use_cropbox era preservado pela renderização com cropbox;
        # para equivalência, renderizamos a área visível da página. O pypdfium2
        # já renderiza o conteúdo visível por padrão. Mantém o mesmo DPI (200).
        imagens = converter_pdf_para_imagens(arquivo_pdf, dpi=200)

        imagens[0].save(arquivo_imagem, "PNG")

        return arquivo_imagem


class DirectoryProcessor:
    """Processador de diretórios"""
    
    @staticmethod
    def processar_entrada(diretorio: Union[Path, str, List, None]) -> List[Path]:
        """Processa entrada de diretório e retorna lista de Path"""
        if isinstance(diretorio, str):
            return [Path(diretorio)]
        elif isinstance(diretorio, Path):
            return [diretorio]
        elif isinstance(diretorio, list):
            return [Path(dir) if isinstance(dir, str) else dir for dir in diretorio]
        elif diretorio is None:
            return [Path(__file__).resolve().parent / "data" / "input"]
        else:
            raise ValueError(f"Tipo de diretório não suportado: {type(diretorio)}")


class DirectoryFilter(IDirectoryFilter):
    """Filtro de diretórios com glob otimizado."""
    
    def filtrar(self, diretorios: List[Path], criterio: str) -> List[Path]:
        """
        Filtra diretórios baseado em critério usando glob otimizado.
        
        Args:
            diretorios: Lista de diretórios base
            criterio: Critério de filtro (substring do nome)
        
        Returns:
            Lista de diretórios que contêm o critério no nome
        """
        diretorios_filtrados = []
        
        for diretorio_base in diretorios:
            if not diretorio_base.exists():
                logger.warning(f"Diretório {diretorio_base} não existe.")
                continue
            
            # ✨ GLOB OTIMIZADO: busca diretórios com critério no nome
            try:
                # Padrão com wildcard inteligente
                padroes = [
                    f"**/*{criterio}*",  # Qualquer profundidade
                    f"*{criterio}*"       # Nível raiz
                ]
                
                diretorios_encontrados = []
                for padrao in padroes:
                    try:
                        encontrados = [
                            item for item in diretorio_base.glob(padrao)
                            if item.is_dir() and criterio in item.name
                        ]
                        diretorios_encontrados.extend(encontrados)
                    except Exception as e:
                        logger.debug(f"Padrão '{padrao}' falhou: {e}")
                
                # Remover duplicatas
                diretorios_unicos = list(set(diretorios_encontrados))
                diretorios_filtrados.extend(diretorios_unicos)
                
                logger.debug(f"✓ {len(diretorios_unicos)} diretório(s) encontrado(s) em {diretorio_base}")
                
            except Exception as e:
                logger.error(f"Erro ao filtrar {diretorio_base}: {e}")
        
        if not diretorios_filtrados:
            logger.warning(f"Nenhum diretório encontrado com critério: {criterio}")
        
        return diretorios_filtrados


class NomeExtractorOCR(IExtractorNome):
    """Extrator de nomes usando OCR com cache"""
    
    def __init__(self):
        self.ocr = MistralService()
    
    def extrair_nome(self, arquivo: Path) -> str:
        """
        Extrai nome usando OCR Mistral, com cache automático baseado em hash da imagem
        
        Args:
            arquivo: Path da imagem do cabeçalho
        
        Returns:
            Nome do funcionário
        """
        try:
            # ✨ TENTAR CACHE PRIMEIRO
            if cache_ocr and cache_ocr.disponivel:
                nome_cache = cache_ocr.obter_ocr(arquivo)
                if nome_cache:
                    logger.info(f"✓ Cache HIT para {arquivo.name}: {nome_cache}")
                    return nome_cache
            
            # Não estava em cache, fazer chamada ao OCR Mistral
            logger.debug(f"Cache miss para {arquivo.name}, chamando Mistral OCR...")
            nome_funcionario = self.ocr.imagem(arquivo)
            nome_funcionario = ''.join(filter(lambda x: x.isalnum() or x.isspace(), nome_funcionario))
            logger.debug(f"Nome extraído por OCR: {nome_funcionario.strip()}")
            
            # Remover números extras no final do nome, se houver
            nome_funcionario = re.sub(r'\d+$', '', nome_funcionario).strip()

            logger.debug(f"Nome corrigido para: {nome_funcionario.strip()}")

            
            # 💾 SALVAR NO CACHE para próximas vezes
            if cache_ocr and cache_ocr.disponivel:
                cache_ocr.salvar_ocr(arquivo, nome_funcionario.strip())
                logger.info(f"✓ Nome armazenado em cache: {nome_funcionario.strip()}")
            
            return nome_funcionario.strip()
        
        except Exception as e:
            logger.error(f"Erro na extração por OCR: {e}")
            raise


class NomeExtractorIA(IExtractorNome):
    """Extrator de nomes usando IA com cache"""
    
    def __init__(self):
        self.servico_gemini = GeminiService(model="gemini-2.5-flash-lite")
    
    def extrair_nome(self, arquivo: Path) -> str:
        """
        Extrai nome usando IA, com cache automático baseado em hash da imagem
        
        Args:
            arquivo: Path da imagem do cabeçalho
        
        Returns:
            Nome do funcionário
        """
        try:
            # ✨ TENTAR CACHE PRIMEIRO
            if cache_ocr and cache_ocr.disponivel:
                nome_cache = cache_ocr.obter_ocr(arquivo)
                if nome_cache:
                    logger.info(f"✓ Cache HIT para {arquivo.name}: {nome_cache}")
                    return nome_cache
            
            # Não estava em cache, fazer chamada à IA
            logger.debug(f"Cache miss para {arquivo.name}, chamando Gemini API...")
            prompt = "Me informa o nome completo do funcionário em uma única string, devendo conter só isso e mais nada além disso."
            nome_funcionario = self.servico_gemini.imagem(arquivo, prompt)
            logger.debug(f"Nome extraído por IA: {nome_funcionario}")
            
            # 💾 SALVAR NO CACHE para próximas vezes
            if cache_ocr and cache_ocr.disponivel:
                cache_ocr.salvar_ocr(arquivo, nome_funcionario)
                logger.info(f"✓ Nome armazenado em cache: {nome_funcionario}")
            
            return nome_funcionario
        
        except Exception as e:
            logger.error(f"Erro na extração por IA: {e}")
            raise


class NomeExtractorComposite(IExtractorNome):
    """Extrator que combina OCR e IA com fallback"""
    
    def __init__(self):
        self.ocr_extractor = NomeExtractorOCR()
        self.ia_extractor = NomeExtractorIA()
    
    def extrair_nome(self, arquivo: Path) -> str:
        try:
            return self.ocr_extractor.extrair_nome(arquivo)
        except Exception as e:
            logger.warning(f"OCR falhou, tentando IA: {e}")
            return self.ia_extractor.extrair_nome(arquivo)


class ArquivoProcessor(IArquivoProcessor):
    """Processador de arquivos de holerite"""
    
    def __init__(self, nome_extractor: IExtractorNome, pdf_processor: IPdfProcessor):
        self.nome_extractor = nome_extractor
        self.pdf_processor = pdf_processor
    
    def processar_arquivo(self, arquivo: Path, diretorio: Path) -> bool:
        """Processa um arquivo renomeando-o com o nome do funcionário"""
        try:
            # Extrair cabeçalho do PDF
            img_cabecalho = self.pdf_processor.extrair_cabecalho(arquivo)
            
            # Extrair nome do funcionário
            nome_funcionario = self.nome_extractor.extrair_nome(img_cabecalho)
            
            if not nome_funcionario:
                logger.error("Nome do funcionário não encontrado no cabeçalho do holerite.")
                return False
            
            # Renomear arquivo
            arquivo_renomeado = diretorio / f"Recibo de Pagamento - {nome_funcionario.title()}.pdf"
            arquivo.rename(arquivo_renomeado)
            
            # Limpar arquivo temporário
            img_cabecalho.unlink(missing_ok=True)
            
            logger.info(f"Arquivo do funcionário {nome_funcionario} foi renomeado com sucesso!")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao processar arquivo {arquivo}: {e}")
            return False


def processar_arquivo_standalone(arquivo_path: str, diretorio_path: str, diretorio_processamento_path: str) -> bool:
    """
    Função standalone para processamento de arquivo que pode ser serializada.
    Esta função é necessária para o multiprocessing funcionar corretamente.
    """
    try:
        arquivo = Path(arquivo_path)
        diretorio = Path(diretorio_path)
        diretorio_processamento = Path(diretorio_processamento_path)
        
        # Criar instâncias locais dos serviços
        pdf_processor = PdfProcessorService(diretorio_processamento)
        nome_extractor = NomeExtractorComposite()
        arquivo_processor = ArquivoProcessor(nome_extractor, pdf_processor)
        
        return arquivo_processor.processar_arquivo(arquivo, diretorio)
    except Exception as e:
        logger.error(f"Erro no processamento standalone: {e}")
        return False


class Holerite:
    """
    Classe principal para manipular e processar arquivos de recibos de pagamento (holerites).
    
    Refatorada seguindo os princípios SOLID para maior manutenibilidade e extensibilidade.
    
    Atributos:
        diretorio (List[Path]): Lista de diretórios onde os arquivos estão localizados.
        diretorio_processamento (Path): Diretório onde os arquivos processados serão salvos temporariamente.
    
    Exemplo de uso:
        >>> from src.holerite import Holerite
        >>> holerite = Holerite(diretório='caminho/para/diretorio')
        >>> processados, erros = holerite.renomear_arquivos()
    """
    
    def __init__(self, diretório: Union[Path, str, List, None] = None):
        """Inicializa a classe Holerite com dependências injetadas"""
        self.diretorio = DirectoryProcessor.processar_entrada(diretório)
        # Caminho relativo ao pacote src/ (robusto em Windows e Linux)
        self.diretorio_processamento = Path(__file__).resolve().parent / "data" / "process"
        
        # Injeção de dependências
        self._pdf_processor = PdfProcessorService(self.diretorio_processamento)
        self._nome_extractor = NomeExtractorComposite()
        self._arquivo_processor = ArquivoProcessor(self._nome_extractor, self._pdf_processor)
        self._directory_filter = DirectoryFilter()
    
    def __str__(self) -> str:
        return f"Diretórios: {[str(d) for d in self.diretorio]}"
    
    def renomear_arquivos(
        self, 
        max_workers: int = 5, 
        mês_ano: Optional[Union[datetime.date, str]] = None,
        usar_multiprocessing: bool = True  # Nova opção
    ) -> Tuple[int, int]:
        """
        Renomeia arquivos usando processamento paralelo.
        
        Args:
            max_workers: Número máximo de processos/threads paralelos
            mês_ano: Filtro de mês/ano para buscar diretórios específicos
            usar_multiprocessing: Se True, usa ProcessPoolExecutor, senão ThreadPoolExecutor
        
        Returns:
            Tuple com (arquivos_processados, arquivos_com_erro)
        """
        diretorios_trabalho = self._preparar_diretorios(mês_ano)
        arquivos_para_processar = self._coletar_arquivos(diretorios_trabalho)
        
        if usar_multiprocessing:
            return self._processar_arquivos_multiprocessing(arquivos_para_processar, max_workers)
        else:
            return self._processar_arquivos_threading(arquivos_para_processar, max_workers)
    
    def _preparar_diretorios(self, mês_ano: Optional[Union[datetime.date, str]]) -> List[Path]:
        """Prepara lista de diretórios baseado no filtro de mês/ano"""
        if mês_ano is None:
            return self.diretorio
        
        mês_ano_str = self._processar_mes_ano(mês_ano)
        diretorios_filtrados = self._directory_filter.filtrar(self.diretorio, mês_ano_str)
        
        if not diretorios_filtrados:
            logger.warning(f"Nenhum diretório encontrado para {mês_ano_str}")
            return []
        
        return diretorios_filtrados
    
    def _processar_mes_ano(self, mês_ano: Union[datetime.date, str]) -> str:
        """Processa e valida o parâmetro mês_ano"""
        if isinstance(mês_ano, str):
            try:
                mês_ano = datetime.datetime.strptime(mês_ano, "%m.%Y")
            except ValueError:
                raise ValueError("Formato de data inválido. Use 'MM.YYYY'")
        
        if isinstance(mês_ano, datetime.date):
            return mês_ano.strftime("%m.%Y")
        
        raise ValueError("O parâmetro 'mês_ano' deve ser uma string no formato 'MM.YYYY' ou um objeto datetime.date.")
    
    def _coletar_arquivos(self, diretorios: List[Path]) -> List[Tuple[Path, Path]]:
        """Coleta todos os arquivos de holerite dos diretórios, filtrando por nome e usando paralelismo para acelerar a coleta"""
        arquivos_para_processar = []
        
        def coletar_de_diretorio(caminho: Path) -> List[Tuple[Path, Path]]:
            return [(arquivo, caminho) for arquivo in caminho.glob('*') 
                    if arquivo.name.endswith("Recibo de Pagamento.pdf")]
        
        with ThreadPoolExecutor(max_workers=min(len(diretorios), 10)) as executor:
            resultados = executor.map(coletar_de_diretorio, diretorios)
        
        for resultado in resultados:
            arquivos_para_processar.extend(resultado)
            
        return arquivos_para_processar
    
    def _processar_arquivos_threading(
        self, 
        arquivos_para_processar: List[Tuple[Path, Path]], 
        max_workers: int
    ) -> Tuple[int, int]:
        """Processa arquivos usando threads (mais compatível)"""
        processados = 0
        erros = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self._arquivo_processor.processar_arquivo, arquivo, diretorio)
                for arquivo, diretorio in arquivos_para_processar
            ]
            
            for future in futures:
                try:
                    if future.result():
                        processados += 1
                    else:
                        erros += 1
                except Exception as e:
                    logger.error(f"Erro no processamento: {e}")
                    erros += 1
        
        self._log_resultados(processados, erros)
        return (processados, erros)
    
    def _processar_arquivos_multiprocessing(
        self, 
        arquivos_para_processar: List[Tuple[Path, Path]], 
        max_workers: int
    ) -> Tuple[int, int]:
        """Processa arquivos usando multiprocessing (para casos que exigem mais isolamento)"""
        from concurrent.futures import ProcessPoolExecutor
        
        processados = 0
        erros = 0
        
        # Preparar argumentos para a função standalone
        args_lista = [
            (str(arquivo), str(diretorio), str(self.diretorio_processamento))
            for arquivo, diretorio in arquivos_para_processar
        ]
        
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(processar_arquivo_standalone, *args)
                for args in args_lista
            ]
            
            for future in futures:
                try:
                    if future.result():
                        processados += 1
                    else:
                        erros += 1
                except Exception as e:
                    logger.error(f"Erro no processamento: {e}")
                    erros += 1
        
        self._log_resultados(processados, erros)
        return (processados, erros)
    
    def _processar_arquivos_paralelo(
        self, 
        arquivos_para_processar: List[Tuple[Path, Path]], 
        max_workers: int
    ) -> Tuple[int, int]:
        """Método mantido para compatibilidade - usa threading por padrão"""
        return self._processar_arquivos_threading(arquivos_para_processar, max_workers)
    
    def _log_resultados(self, processados: int, erros: int) -> None:
        """Log dos resultados do processamento"""
        logger.debug(f"Arquivos processados: {processados}, Erros: {erros}")
        if erros > 0:
            logger.error("Alguns arquivos não foram processados corretamente. Verifique os logs.")
        
        # Mostrar estatísticas do cache ao final do processamento
        self._mostrar_stats_cache()
    
    def _mostrar_stats_cache(self) -> None:
        """Exibe estatísticas do cache OCR MongoDB"""
        if not cache_ocr or not cache_ocr.disponivel:
            logger.warning("Cache OCR não disponível")
            return
        
        try:
            stats = cache_ocr.obter_estatisticas()
            logger.info(f"""
    ═══════════════════════════════════════════════════════
            📊 ESTATÍSTICAS DO CACHE OCR MONGODB          
    ═══════════════════════════════════════════════════════
     ✓ Status: {stats.get('status', 'Desconhecido'):.<38} 
     ✓ Total de documentos: {stats.get('total_documentos', 0):<28} 
     ✓ Tamanho total: {stats.get('tamanho_total_mb', 0):.2f} MB{' ':<24} 
     ✓ Banco de dados: {stats.get('banco_dados', 'N/A'):<30} 
     ✓ Coleção: {stats.get('colecao', 'N/A'):<35} 
     ✓ Arquivos únicos: {stats.get('arquivos_unicos', 0):<27} 
    ═══════════════════════════════════════════════════════
            """)
        except Exception as e:
            logger.warning(f"Erro ao exibir estatísticas do cache: {e}")