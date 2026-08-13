"""
Processador de Holerites
Extrai dados de PDFs de holerites usando Gemini AI
e salva no MongoDB com vinculação a funcionários e empresas
"""

import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

from src.utils.logger_config import logger
from src.models.holerite_models import (
    HoleriteExtracaoSchema,
    HoleriteMongoDB,
    StatusHoleriteEnum,
    TipoFolhaEnum
)
from src.models.contato_funcionario_models import criar_contato_de_holerite
from src.services.holerite_service import HoleriteService
from src.services.funcionario_service import FuncionarioService
from src.services.contato_funcionario_service import ContatoFuncionarioService
from src.services.empresa_service import EmpresaService

# Tentar importar GeminiService
try:
    from src.services.analise_ai_service import GeminiService
    GEMINI_DISPONIVEL = True
except ImportError:
    GEMINI_DISPONIVEL = False
    logger.warning("GeminiService não disponível")

try:
    from bson import ObjectId
    BSON_DISPONIVEL = True
except ImportError:
    BSON_DISPONIVEL = False


@dataclass
class ResultadoProcessamentoHolerite:
    """Resultado do processamento de um holerite"""
    
    arquivo: str = ""
    sucesso: bool = False
    erro: Optional[str] = None
    
    # Dados extraídos
    extracao: Optional[HoleriteExtracaoSchema] = None
    extracao_json: Optional[str] = None
    
    # IDs criados/vinculados
    holerite_id: Optional[str] = None
    funcionario_id: Optional[str] = None
    empresa_id: Optional[str] = None
    funcionario_criado: bool = False  # Se foi criado novo funcionário
    
    # Métricas
    tempo_extracao_s: float = 0.0
    tempo_total_s: float = 0.0
    
    # Mensagens de log
    mensagens: List[str] = field(default_factory=list)


class HoleriteProcessador:
    """
    Processa PDFs de holerites:
    1. Extrai dados com Gemini AI usando schema estruturado
    2. Vincula ou cria funcionário no MongoDB
    3. Vincula empresa (se identificada)
    4. Salva holerite no MongoDB
    5. Cria/atualiza contatos do funcionário
    """

    # Padrão de nome esperado para arquivos de holerite
    PREFIXO_HOLERITE = "Recibo de Pagamento"

    # Prompt para extração de holerites
    PROMPT_EXTRACAO = """
    Analise este holerite/contracheque e extraia TODOS os dados solicitados no schema.
    
    INSTRUÇÕES IMPORTANTES:
    1. Extraia o nome COMPLETO do funcionário exatamente como aparece
    2. O CPF deve ser extraído sem formatação (apenas números)
    3. A competência é o mês/ano de referência do pagamento (formato MM/AAAA)
    4. Identifique TODOS os proventos (salário, horas extras, adicionais, etc.)
    5. Identifique TODOS os descontos (INSS, IRRF, VT, VR, faltas, etc.)
    6. Extraia as bases de cálculo de INSS, IRRF e FGTS se disponíveis
    7. O tipo_folha pode ser: normal, ferias, rescisao, 13_salario, adiantamento
    
    ATENÇÃO:
    - Se um campo não estiver visível ou legível, use null
    - Valores monetários devem ser numéricos (ex: 1234.56, não "R$ 1.234,56")
    - Datas no formato DD/MM/AAAA
    - Telefone/celular sem formatação (apenas números com DDD)
    
    Seja preciso e extraia o máximo de informações possível.
    """
    
    def __init__(
        self,
        gemini_service: "GeminiService" = None,
        holerite_service: HoleriteService = None,
        funcionario_service: FuncionarioService = None,
        contato_service: ContatoFuncionarioService = None,
        empresa_service: EmpresaService = None
    ):
        """
        Inicializa o processador.
        
        Args:
            gemini_service: Instância do GeminiService (cria nova se None)
            holerite_service: Instância do HoleriteService
            funcionario_service: Instância do FuncionarioService
            contato_service: Instância do ContatoFuncionarioService
            empresa_service: Instância do EmpresaService
        """
        # Inicializar serviços
        if gemini_service:
            self.gemini = gemini_service
        elif GEMINI_DISPONIVEL:
            self.gemini = GeminiService()
        else:
            self.gemini = None
            logger.warning("GeminiService não inicializado")
        
        self.holerite_service = holerite_service or HoleriteService()
        self.funcionario_service = funcionario_service or FuncionarioService()
        self.contato_service = contato_service or ContatoFuncionarioService()
        self.empresa_service = empresa_service or EmpresaService()
        
        # Estatísticas
        self.total_processados = 0
        self.total_sucesso = 0
        self.total_falhas = 0
    
    @property
    def disponivel(self) -> bool:
        """Verifica se o processador está pronto"""
        return (
            self.gemini is not None and
            self.holerite_service.disponivel and
            self.funcionario_service.disponivel
        )
    
    def _arquivo_eh_holerite_valido(self, arquivo: Path) -> bool:
        """
        Verifica se o arquivo é um holerite válido.

        Um arquivo é considerado válido se:
        - É um arquivo PDF
        - Começa com "Recibo de Pagamento"

        Args:
            arquivo: Caminho do arquivo

        Returns:
            True se é um holerite válido, False caso contrário
        """
        if arquivo.suffix.lower() != ".pdf":
            return False

        if not arquivo.name.startswith(self.PREFIXO_HOLERITE):
            return False

        return True

    def calcular_hash_arquivo(self, caminho: Path) -> Optional[str]:
        """Calcula SHA256 do arquivo"""
        try:
            sha256 = hashlib.sha256()
            with open(caminho, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"Erro ao calcular hash: {e}")
            return None
    
    def processar_arquivo(
        self,
        arquivo: Path,
        empresa_id: str = None,
        temperatura: float = 0.1,
        max_tentativas: int = 2
    ) -> ResultadoProcessamentoHolerite:
        """
        Processa um único arquivo PDF de holerite.
        
        Args:
            arquivo: Caminho do arquivo PDF
            empresa_id: ObjectId da empresa (opcional, tenta identificar pelo conteúdo)
            temperatura: Temperatura para o Gemini (default: 0.1 - mais preciso)
            max_tentativas: Tentativas em caso de erro
        
        Returns:
            ResultadoProcessamentoHolerite com dados do processamento
        """
        resultado = ResultadoProcessamentoHolerite(arquivo=str(arquivo))
        tempo_inicio = time.time()
        
        # Validações iniciais
        if not self.disponivel:
            resultado.erro = "Processador não disponível (Gemini ou MongoDB indisponível)"
            return resultado
        
        if not isinstance(arquivo, Path):
            arquivo = Path(arquivo)
        
        if not arquivo.exists():
            resultado.erro = f"Arquivo não encontrado: {arquivo}"
            return resultado
        
        if arquivo.suffix.lower() != ".pdf":
            resultado.erro = f"Arquivo não é PDF: {arquivo.suffix}"
            return resultado
        
        # Calcular hash para evitar duplicatas
        hash_arquivo = self.calcular_hash_arquivo(arquivo)
        
        if hash_arquivo:
            # Verificar se já foi processado
            existente = self.holerite_service.buscar_por_hash(hash_arquivo)
            if existente:
                resultado.sucesso = True
                resultado.holerite_id = str(existente['_id'])
                resultado.funcionario_id = str(existente.get('funcionario_id', ''))
                resultado.mensagens.append(f"Holerite já processado anteriormente (ID: {resultado.holerite_id})")
                resultado.tempo_total_s = time.time() - tempo_inicio
                return resultado
        
        logger.info(f"Processando holerite: {arquivo.name}")
        
        # ==================== EXTRAÇÃO COM GEMINI ====================
        extracao = None
        tempo_extracao_inicio = time.time()
        
        for tentativa in range(1, max_tentativas + 1):
            try:
                resultado_json = self.gemini.documento_estruturado(
                    documento=arquivo,
                    prompt=self.PROMPT_EXTRACAO,
                    schema_pydantic=HoleriteExtracaoSchema,
                    temperature=temperatura
                )
                
                resultado.extracao_json = resultado_json
                
                # Validar resposta
                if not resultado_json or len(resultado_json) < 50:
                    if tentativa < max_tentativas:
                        logger.warning(f"Resposta curta, tentando novamente ({tentativa}/{max_tentativas})")
                        continue
                    else:
                        raise ValueError("Resposta do Gemini muito curta")
                
                # Parsear para modelo Pydantic
                extracao = HoleriteExtracaoSchema.model_validate_json(resultado_json)
                resultado.extracao = extracao

                # Formar competência no formato MM/AAAA
                competencia = f"{extracao.mes_referencia:02d}/{extracao.ano_referencia}"
                logger.info(f"  ✓ Extração OK: {extracao.funcionario_nome}, {competencia}")
                break
                
            except Exception as e:
                logger.warning(f"  Erro na tentativa {tentativa}: {e}")
                if tentativa >= max_tentativas:
                    resultado.erro = f"Falha na extração após {max_tentativas} tentativas: {e}"
                    resultado.tempo_total_s = time.time() - tempo_inicio
                    return resultado
        
        resultado.tempo_extracao_s = time.time() - tempo_extracao_inicio
        
        if not extracao:
            resultado.erro = "Falha na extração: objeto vazio"
            resultado.tempo_total_s = time.time() - tempo_inicio
            return resultado
        
        # ==================== VINCULAR/CRIAR FUNCIONÁRIO ====================
        funcionario = None
        funcionario_criado = False

        logger.info(f"[PROCESSADOR] Iniciando vinculação de funcionário - CPF: {extracao.funcionario_cpf}, Nome: {extracao.funcionario_nome}")

        # SEMPRE tentar buscar/criar funcionário se temos nome
        # Mesmo sem CPF, podemos buscar pelo nome normalizado
        if extracao.funcionario_nome:
            logger.info(f"[PROCESSADOR] Chamando criar_ou_buscar_por_documento...")

            # Passar CPF se disponível, senão passar uma string vazia
            cpf_para_buscar = extracao.funcionario_cpf or ""

            funcionario = self.funcionario_service.criar_ou_buscar_por_documento(
                documento=cpf_para_buscar,
                nome=extracao.funcionario_nome,
                dados_extras={}
            )

            if funcionario:
                logger.info(f"[PROCESSADOR] ✓ Funcionário encontrado/criado - Tipo: {type(funcionario)}, ID: {funcionario.get('_id')}")
                resultado.funcionario_id = str(funcionario['_id'])
                logger.info(f"[PROCESSADOR] funcionario_id setado para: {resultado.funcionario_id}")

                # Verificar se foi criado agora (tem status_cadastro = incompleto)
                if funcionario.get('status_cadastro') == 'incompleto':
                    funcionario_criado = True
                    resultado.funcionario_criado = True
                    resultado.mensagens.append(f"Novo funcionário criado: {extracao.funcionario_nome}")
                else:
                    resultado.mensagens.append(f"Funcionário vinculado: {extracao.funcionario_nome}")
            else:
                logger.error(f"[PROCESSADOR] ✗ FALHA: criar_ou_buscar_por_documento retornou None!")
                resultado.mensagens.append(f"ERRO: Não foi possível vincular/criar funcionário {extracao.funcionario_nome}")
        else:
            logger.warning(f"[PROCESSADOR] Holerite sem nome de funcionário - não vinculado a funcionário")
            resultado.mensagens.append("AVISO: Holerite sem nome de funcionário - não vinculado a funcionário")

        # ==================== VINCULAR EMPRESA ====================
        logger.info(f"[PROCESSADOR] Iniciando vinculação de empresa - Razão Social: {extracao.empresa_razao_social}")

        if empresa_id:
            logger.info(f"[PROCESSADOR] empresa_id recebido como parâmetro: {empresa_id} (tipo: {type(empresa_id)})")
            resultado.empresa_id = empresa_id
        elif extracao.empresa_razao_social:
            # Tentar buscar empresa pelo nome (tenta nome_simplificado primeiro)
            logger.info(f"[PROCESSADOR] Buscando empresa por nome: {extracao.empresa_razao_social}")
            empresa = self.empresa_service.buscar_por_nome_ou_simplificado(extracao.empresa_razao_social, exato=False)
            if empresa and empresa.get('_id'):
                logger.info(f"[PROCESSADOR] ✓ Empresa encontrada - ID: {empresa.get('_id')} (tipo: {type(empresa.get('_id'))})")
                resultado.empresa_id = str(empresa['_id'])
                logger.info(f"[PROCESSADOR] empresa_id setado para: {resultado.empresa_id} (tipo: {type(resultado.empresa_id)})")
                resultado.mensagens.append(f"Empresa vinculada: {extracao.empresa_razao_social}")
            else:
                logger.warning(f"[PROCESSADOR] Empresa NÃO encontrada para: {extracao.empresa_razao_social}")
        else:
            logger.warning(f"[PROCESSADOR] Sem empresa_id e sem razão social no holerite")
        
        # ==================== CRIAR HOLERITE NO MONGODB ====================
        try:
            # Preparar informações do arquivo
            from src.models.holerite_models import ArquivoHolerite, ProcessamentoHolerite

            arquivo_info = ArquivoHolerite(
                caminho_completo=str(arquivo),
                nome_arquivo=arquivo.name,
                hash_sha256=hash_arquivo,
                tamanho_bytes=arquivo.stat().st_size if arquivo.exists() else 0,
                verificado_em=datetime.now(timezone.utc)
            )

            processamento_info = ProcessamentoHolerite(
                processado_em=datetime.now(timezone.utc),
                modelo_ia="gemini-2.5-pro",
                tempo_processamento_ms=int(resultado.tempo_extracao_s * 1000),
                confianca=None
            )

            # Converter extração para modelo MongoDB
            logger.info(f"[PROCESSADOR] Preparando conversão para HoleriteMongoDB:")
            logger.info(f"  - funcionario_id (resultado): {resultado.funcionario_id} (tipo: {type(resultado.funcionario_id)})")
            logger.info(f"  - empresa_id (resultado): {resultado.empresa_id} (tipo: {type(resultado.empresa_id)})")

            funcionario_id_obj = None
            empresa_id_obj = None

            if resultado.funcionario_id:
                try:
                    funcionario_id_obj = ObjectId(resultado.funcionario_id)
                    logger.info(f"[PROCESSADOR] ✓ funcionario_id convertido para ObjectId: {funcionario_id_obj}")
                except Exception as e:
                    logger.error(f"[PROCESSADOR] ✗ ERRO ao converter funcionario_id para ObjectId: {e}")

            if resultado.empresa_id:
                try:
                    empresa_id_obj = ObjectId(resultado.empresa_id)
                    logger.info(f"[PROCESSADOR] ✓ empresa_id convertido para ObjectId: {empresa_id_obj}")
                except Exception as e:
                    logger.error(f"[PROCESSADOR] ✗ ERRO ao converter empresa_id para ObjectId: {e}")

            holerite_mongo = HoleriteMongoDB.from_extracao(
                extracao=extracao,
                funcionario_id=funcionario_id_obj,
                empresa_id=empresa_id_obj,
                arquivo=arquivo_info,
                processamento=processamento_info
            )
            logger.info(f"[PROCESSADOR] ✓ HoleriteMongoDB criado - funcionario_id: {holerite_mongo.funcionario_id}, empresa_id: {holerite_mongo.empresa_id}")
            
            # Inserir no MongoDB
            holerite_id = self.holerite_service.criar_holerite(holerite_mongo)
            
            if holerite_id:
                resultado.holerite_id = str(holerite_id)
                resultado.sucesso = True
                resultado.mensagens.append(f"Holerite salvo: {resultado.holerite_id}")
                
                # Atualizar estatísticas
                self.total_processados += 1
                self.total_sucesso += 1
            else:
                resultado.erro = "Falha ao salvar holerite no MongoDB"
                self.total_falhas += 1
                
        except Exception as e:
            resultado.erro = f"Erro ao salvar holerite: {e}"
            logger.error(resultado.erro)
            self.total_falhas += 1
        
        # ==================== CRIAR/ATUALIZAR CONTATOS ====================
        if resultado.sucesso and resultado.funcionario_id:
            try:
                contatos = criar_contato_de_holerite(
                    funcionario_id=ObjectId(resultado.funcionario_id),
                    funcionario_documento=extracao.funcionario_cpf or "",
                    funcionario_nome=extracao.funcionario_nome,
                    telefone=None,
                    email=None
                )
                
                for contato in contatos:
                    self.contato_service.criar_ou_atualizar(contato)
                
                if contatos:
                    resultado.mensagens.append(f"{len(contatos)} contato(s) criado(s)/atualizado(s)")
                    
            except Exception as e:
                logger.warning(f"Erro ao criar contatos: {e}")
        
        resultado.tempo_total_s = time.time() - tempo_inicio
        return resultado
    
    def processar_diretorio(
        self,
        diretorio: Path,
        empresa_id: str = None,
        recursivo: bool = True,
        temperatura: float = 0.1
    ) -> List[ResultadoProcessamentoHolerite]:
        """
        Processa todos os PDFs de um diretório que começam com "Recibo de Pagamento".

        Args:
            diretorio: Caminho do diretório
            empresa_id: ObjectId da empresa (aplicado a todos)
            recursivo: Se True, busca em subdiretórios
            temperatura: Temperatura para o Gemini

        Returns:
            Lista de resultados de processamento
        """
        if not isinstance(diretorio, Path):
            diretorio = Path(diretorio)

        if not diretorio.exists():
            logger.error(f"Diretório não encontrado: {diretorio}")
            return []

        # Listar PDFs
        if recursivo:
            todos_pdfs = list(diretorio.rglob("*.pdf"))
        else:
            todos_pdfs = list(diretorio.glob("*.pdf"))

        if not todos_pdfs:
            logger.warning(f"Nenhum PDF encontrado em: {diretorio}")
            return []

        # Filtrar apenas holerites válidos (que começam com "Recibo de Pagamento")
        arquivos = [pdf for pdf in todos_pdfs if self._arquivo_eh_holerite_valido(pdf)]

        # Log dos PDFs ignorados
        ignorados = [pdf for pdf in todos_pdfs if not self._arquivo_eh_holerite_valido(pdf)]
        if ignorados:
            logger.warning(f"Ignorando {len(ignorados)} arquivo(s) PDF (não começam com '{self.PREFIXO_HOLERITE}'):")
            for pdf_ignorado in ignorados:
                logger.warning(f"  - {pdf_ignorado.name}")

        if not arquivos:
            logger.warning(f"Nenhum holerite válido encontrado em: {diretorio}")
            logger.info(f"Todos os {len(todos_pdfs)} PDF(s) foram ignorados por não começarem com '{self.PREFIXO_HOLERITE}'")
            return []

        logger.info(f"Processando {len(arquivos)} holerite(s) de {diretorio}")

        resultados = []
        for i, arquivo in enumerate(arquivos, 1):
            logger.info(f"[{i}/{len(arquivos)}] {arquivo.name}")

            resultado = self.processar_arquivo(
                arquivo=arquivo,
                empresa_id=empresa_id,
                temperatura=temperatura
            )
            resultados.append(resultado)

            if resultado.sucesso:
                logger.info(f"  ✓ OK: {resultado.holerite_id}")
            else:
                logger.error(f"  ✗ ERRO: {resultado.erro}")

        # Resumo
        sucesso = sum(1 for r in resultados if r.sucesso)
        logger.info(f"\n=== RESUMO ===")
        logger.info(f"Total processado: {len(resultados)}")
        logger.info(f"Sucesso: {sucesso}")
        logger.info(f"Falhas: {len(resultados) - sucesso}")
        if ignorados:
            logger.info(f"Ignorados: {len(ignorados)} (não começam com '{self.PREFIXO_HOLERITE}')")

        return resultados
    
    def obter_estatisticas(self) -> Dict[str, Any]:
        """Retorna estatísticas do processador"""
        return {
            "total_processados": self.total_processados,
            "total_sucesso": self.total_sucesso,
            "total_falhas": self.total_falhas,
            "taxa_sucesso": (
                self.total_sucesso / self.total_processados * 100 
                if self.total_processados > 0 else 0
            )
        }


# Instância singleton
holerite_processador = HoleriteProcessador()
