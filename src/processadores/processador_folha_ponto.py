"""
ProcessadorFolhaPonto - Orquestração completa do pipeline de análise

Pipeline:
1. Validar arquivo PDF
2. Enviar para Gemini com Structured Output
3. Validar resposta conforme Pydantic schema
4. Lookup de funcionário via FuncionarioService
5. Armazenar em MongoDB
6. Retornar resultado com métricas
"""

from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, date, timezone
from enum import Enum
import time
import json
from bson import ObjectId
from src.services.analise_ai_service import GeminiService
from src.services import FuncionarioService, FolhaDePontoService, EmpresaService
from src.models.folha_de_ponto_models import (
    FolhaDePontoMongoDB,
    FolhaDePontoData,
    AnaliseIAResultado,
    DiaFolhaPonto,
    TipoDia,
    StatusFolhaPonto,
)
from src.utils.logger_config import logger
from src.utils.funcionario_sanitizador import (
    SanitizadorFuncionario,
    ConstrutorFuncionarioIncompleto,
)


# ==================== ENUMS ====================

class StatusProcessamento(str, Enum):
    """Status do processamento de folha de ponto"""
    PENDENTE = "pendente"
    SUCESSO = "sucesso"
    ERRO = "erro"
    EXTRAIDO = "extraido"


def converter_string_para_tipo_dia(valor: Optional[str]) -> Optional[TipoDia]:
    """
    Converte string para TipoDia ENUM de forma segura e compatível.
    
    Args:
        valor: String com tipo de dia (ex: "FERIADO", "falta", "Normal")
    
    Returns:
        TipoDia correspondente ou None se não reconhecido
    """
    if not valor:
        return None
    
    valor_upper = valor.upper().strip()
    
    # Mapeamento de strings para ENUM
    mapeamento = {
        'NORMAL': TipoDia.NORMAL,
        'FERIADO': TipoDia.FERIADO,
        'SABADO': TipoDia.SABADO,
        'SÁBADO': TipoDia.SABADO,
        'DOMINGO': TipoDia.DOMINGO,
        'FALTA': TipoDia.FALTA,
        'ATESTADO': TipoDia.ATESTADO,
        'FOLGA': TipoDia.FOLGA,
        'LICENCA': TipoDia.LICENCA,
        'LICENÇA': TipoDia.LICENCA,
        'FERIAS': TipoDia.FERIAS,
        'FÉRIAS': TipoDia.FERIAS,
    }
    
    # Busca direta
    if valor_upper in mapeamento:
        return mapeamento[valor_upper]
    
    # Busca parcial (para casos como "FERIADO NACIONAL")
    for chave, enum_valor in mapeamento.items():
        if chave in valor_upper:
            return enum_valor
    
    # Se não encontrou, retorna NORMAL como padrão
    logger.debug(f"Tipo de dia não reconhecido: '{valor}', usando NORMAL")
    return TipoDia.NORMAL


# ==================== FUNÇÕES UTILITÁRIAS ====================

def calcular_total_horas(entrada: Optional[str], saida: Optional[str], 
                         intervalo_inicio: Optional[str], intervalo_fim: Optional[str]) -> Optional[str]:
    """Calcula total de horas trabalhadas no formato HH:MM"""
    if not entrada or not saida:
        return None
    
    try:
        # Converter strings para minutos (aceita "HH:MM" ou "HHMM")
        def hora_para_minutos(hora_str: str) -> int:
            texto = str(hora_str).strip()
            if not texto:
                raise ValueError("hora vazia")
            if ':' in texto:
                partes = texto.split(':')
                if len(partes) != 2:
                    raise ValueError(f"hora inválida: {hora_str!r}")
                horas, minutos = int(partes[0]), int(partes[1])
            else:
                # Formato compacto "HHMM" ou "HMM"
                if len(texto) == 4:
                    horas, minutos = int(texto[:2]), int(texto[2:])
                elif len(texto) == 3:
                    horas, minutos = int(texto[:1]), int(texto[1:])
                else:
                    raise ValueError(f"hora inválida: {hora_str!r}")
            if not (0 <= horas <= 23 and 0 <= minutos <= 59):
                raise ValueError(f"hora fora do intervalo: {hora_str!r}")
            return horas * 60 + minutos
        
        minutos_entrada = hora_para_minutos(entrada)
        minutos_saida = hora_para_minutos(saida)
        
        # Se saída for menor que entrada, passou da meia-noite
        if minutos_saida < minutos_entrada:
            minutos_saida += 24 * 60
        
        minutos_trabalhados = minutos_saida - minutos_entrada
        
        # Descontar intervalo se houver
        if intervalo_inicio and intervalo_fim:
            minutos_intervalo_inicio = hora_para_minutos(intervalo_inicio)
            minutos_intervalo_fim = hora_para_minutos(intervalo_fim)
            
            if minutos_intervalo_fim < minutos_intervalo_inicio:
                minutos_intervalo_fim += 24 * 60
            
            minutos_intervalo = minutos_intervalo_fim - minutos_intervalo_inicio
            minutos_trabalhados -= minutos_intervalo
            
            # Um intervalo não pode ser maior que o total trabalhado (dado inválido)
            if minutos_intervalo > minutos_saida - minutos_entrada:
                return None
        
        # Se o resultado ficou negativo (dados inválidos), não retornar horário absurdo
        if minutos_trabalhados < 0:
            return None
        
        # Converter de volta para HH:MM
        horas = minutos_trabalhados // 60
        minutos = minutos_trabalhados % 60
        return f"{horas:02d}:{minutos:02d}"
    
    except Exception:
        return None


def _extrair_valor_dia(dia, campo: str):
    """Extrai um campo de um dia que pode ser dict ou objeto Pydantic/BaseModel."""
    if isinstance(dia, dict):
        return dia.get(campo)
    return getattr(dia, campo, None)


def recalcular_totais_folha(dias) -> Dict[str, Any]:
    """
    Recalcula as totalizações de uma folha de ponto a partir da lista de dias.

    É o MESMO cálculo usado na geração/armazenamento da IA (total_horas_mes,
    total_faltas, total_feriados, total_finais_semana), extraído para ser
    reutilizado na edição de folha sem duplicar a lógica.

    Aceita dias como listas de dicts (formato MongoDB) ou de ``DiaFolhaPonto``.

    Args:
        dias: Lista de dias da folha

    Returns:
        Dict com: total_horas_mes (HH:MM), total_faltas, total_feriados,
        total_finais_semana
    """
    total_horas_mes_minutos = 0
    total_faltas = 0
    total_feriados = 0
    total_finais_semana = 0

    for dia in dias or []:
        tipo_dia = _extrair_valor_dia(dia, "tipo_dia")
        # Normalizar para comparação (pode ser str do enum ou valor)
        if hasattr(tipo_dia, "value"):
            tipo_dia = tipo_dia.value
        tipo_dia_str = str(tipo_dia or "").upper()

        # Feriado
        if tipo_dia_str == "FERIADO":
            total_feriados += 1

        # Finais de semana
        dia_semana = _extrair_valor_dia(dia, "dia_semana")
        if hasattr(dia_semana, "value"):
            dia_semana = dia_semana.value
        if tipo_dia_str in ("SÁBADO", "SABADO", "DOMINGO"):
            total_finais_semana += 1
        elif dia_semana and str(dia_semana).upper() in ["SÁBADO", "SABADO", "DOMINGO"]:
            total_finais_semana += 1

        # Faltas
        if tipo_dia_str == "FALTA":
            total_faltas += 1

        # Horas trabalhadas
        total_horas = _extrair_valor_dia(dia, "total_horas_trabalhadas")
        if total_horas:
            try:
                partes = str(total_horas).split(':')
                if len(partes) == 2:
                    total_horas_mes_minutos += (int(partes[0]) * 60 + int(partes[1]))
            except Exception:
                pass

    total_horas_mes = f"{total_horas_mes_minutos // 60:02d}:{total_horas_mes_minutos % 60:02d}"

    return {
        "total_horas_mes": total_horas_mes,
        "total_faltas": total_faltas,
        "total_feriados": total_feriados,
        "total_finais_semana": total_finais_semana,
    }


# ==================== MODELO EXTRATOR (Structured Output) ====================

class DiaExtraido(BaseModel):
    """
    Dia extraído do PDF pelo Gemini
    IMPORTANTE: Estrutura IDÊNTICA a DiaFolhaPonto para compatibilidade total
    """
    numero_dia: int = Field(..., description="Número do dia (1-31)")
    data: Optional[str] = Field(default=None, description="Data do dia (YYYY-MM-DD)")
    dia_semana: Optional[str] = Field(default=None, description="Dia da semana")
    
    # Horários
    hora_entrada: Optional[str] = Field(default=None, description="Hora entrada HH:MM")
    hora_intervalo_inicio: Optional[str] = Field(default=None, description="Início intervalo HH:MM")
    hora_intervalo_fim: Optional[str] = Field(default=None, description="Fim intervalo HH:MM")
    hora_saida: Optional[str] = Field(default=None, description="Hora saída HH:MM")
    
    # Totalizações
    total_horas_trabalhadas: Optional[str] = Field(default=None, description="Total de horas trabalhadas")
    
    # Observações e tipo
    observacoes: Optional[str] = Field(default=None, description="Observações/anotações")
    tipo_dia: Optional[str] = Field(default=None, description="NORMAL, FERIADO, FALTA, ATESTADO, etc")
    
    # Controle (sempre False para dados extraídos da IA)
    preenchido_manualmente: bool = Field(default=False, description="Se foi preenchido manualmente")
    analise_ia_processada: bool = Field(default=True, description="Marca que veio da IA")


class ExtratorFolhaPonto(BaseModel):
    """Resultado do Gemini Structured Output para Folha de Ponto"""
    
    # Informações extraídas do cabeçalho
    empresa_nome: Optional[str] = Field(default=None, description="Nome da empresa")
    empresa_cnpj: Optional[str] = Field(default=None, description="CNPJ da empresa")
    funcionario_nome: Optional[str] = Field(default=None, description="Nome do funcionário")
    funcionario_pis: Optional[str] = Field(default=None, description="PIS do funcionário")
    funcionario_cpf: Optional[str] = Field(default=None, description="CPF do funcionário")
    periodo_inicio: Optional[str] = Field(default=None, description="Data início período (YYYY-MM-DD)")
    periodo_fim: Optional[str] = Field(default=None, description="Data fim período (YYYY-MM-DD)")
    mes_ano: Optional[str] = Field(default=None, description="Mês/Ano da folha (ex: 2025-11)")
    
    # Dias extraídos
    dias: List[DiaExtraido] = Field(default_factory=list, description="Dias encontrados no PDF")
    
    # Qualidade da extração
    dias_com_dados: int = Field(default=0, description="Quantidade de dias com dados")
    dias_em_branco: int = Field(default=0, description="Quantidade de dias sem dados")
    confianca_geral: int = Field(default=0, description="Confiança geral 0-100")
    
    # Avisos e erros
    avisos: Optional[List[str]] = Field(default=None, description="Avisos durante extração")
    erros: Optional[List[str]] = Field(default=None, description="Erros encontrados")


# ==================== MODELO DE RESULTADO ====================

class ProcessarResultado(BaseModel):
    """Resultado completo do processamento de uma Folha de Ponto"""
    
    # Arquivo processado
    arquivo_origem: str = Field(..., description="Caminho do arquivo original")
    arquivo_hash: Optional[str] = Field(default=None, description="Hash SHA256 do arquivo")
    
    # Resultado do Gemini
    extracao_sucesso: bool = Field(default=False, description="Se extração foi bem-sucedida")
    extracao_resultado: Optional[ExtratorFolhaPonto] = Field(default=None, description="Resultado Gemini")
    prompt_gemini: Optional[str] = Field(default=None, description="Prompt enviado ao Gemini")
    resposta_bruta_gemini: Optional[str] = Field(default=None, description="Resposta bruta do Gemini")
    tokens_utilizados: Optional[int] = Field(default=None, description="Tokens utilizados pela API")
    
    # Lookup do funcionário
    lookup_sucesso: bool = Field(default=False, description="Se lookup foi bem-sucedido")
    funcionario_id: Optional[str] = Field(default=None, description="ID do funcionário encontrado")
    funcionario_nome_encontrado: Optional[str] = Field(default=None, description="Nome do funcionário found")
    funcionario_score_similaridade: Optional[float] = Field(default=None, description="Score da busca (0-100)")
    
    # Armazenamento
    armazenamento_sucesso: bool = Field(default=False, description="Se foi armazenado em MongoDB")
    folha_id: Optional[str] = Field(default=None, description="ID do documento em MongoDB")
    
    # Métricas
    tempo_processamento_total_s: float = Field(default=0, description="Tempo total em segundos")
    tempo_gemini_s: Optional[float] = Field(default=None, description="Tempo Gemini em segundos")
    tempo_lookup_s: Optional[float] = Field(default=None, description="Tempo lookup em segundos")
    tempo_mongodb_s: Optional[float] = Field(default=None, description="Tempo MongoDB em segundos")
    
    # Status e mensagens
    status: StatusProcessamento = Field(default=StatusProcessamento.PENDENTE, description="Status do processamento (usar enum StatusProcessamento)")
    mensagens: List[str] = Field(default_factory=list, description="Mensagens de log")
    avisos: List[str] = Field(default_factory=list, description="Avisos (não impedem processamento)")
    erros: List[str] = Field(default_factory=list, description="Erros encontrados")


# ==================== PROCESSADOR PRINCIPAL ====================

class ProcessadorFolhaPonto:
    """
    Orquestrador do pipeline completo de Folha de Ponto.
    
    Pipeline:
    1. Validar arquivo
    2. Extrair dados via Gemini (Structured Output)
    3. Fazer lookup de funcionário
    4. Armazenar em MongoDB
    5. Retornar resultado detalhado
    """
    
    def __init__(
        self,
        servico_gemini: Optional[GeminiService] = None,
        servico_funcionario: Optional[FuncionarioService] = None,
        servico_folha: Optional[FolhaDePontoService] = None,
        servico_empresa: Optional[EmpresaService] = None,
    ):
        """
        Inicializa o processador.
        
        Args:
            servico_gemini: Instância de GeminiService (cria novo se None)
            servico_funcionario: Instância de FuncionarioService (cria novo se None)
            servico_folha: Instância de FolhaDePontoService (cria novo se None)
            servico_empresa: Instância de EmpresaService (cria novo se None)
        """
        self.gemini = servico_gemini or GeminiService(model="gemini-2.5-pro")
        self.funcionario_service = servico_funcionario or FuncionarioService()
        self.folha_service = servico_folha or FolhaDePontoService()
        self.empresa_service = servico_empresa or EmpresaService()
        
        logger.info("ProcessadorFolhaPonto inicializado")
    
    def processar(self, arquivo_pdf: Path) -> ProcessarResultado:
        """
        Processa um arquivo de Folha de Ponto completo.
        
        Args:
            arquivo_pdf: Caminho para o arquivo PDF (Path ou str)
            
        Returns:
            ProcessarResultado com todos os detalhes do processamento
        """
        # Garantir que é Path
        if isinstance(arquivo_pdf, str):
            arquivo_pdf = Path(arquivo_pdf)
        
        resultado = ProcessarResultado(arquivo_origem=str(arquivo_pdf))
        tempo_inicio = time.time()
        
        try:
            # ==================== ETAPA 1: Validação ====================
            logger.info(f"Iniciando processamento: {arquivo_pdf.name}")
            resultado.mensagens.append(f"Arquivo: {arquivo_pdf.name}")
            
            if not self._validar_arquivo(arquivo_pdf, resultado):
                resultado.status = StatusProcessamento.ERRO
                return resultado
            
            # ==================== ETAPA 2: Extração Gemini ====================
            if not self._extrair_gemini(arquivo_pdf, resultado):
                resultado.status = StatusProcessamento.ERRO
                return resultado
            
            # ==================== ETAPA 3: Lookup Funcionário ====================
            if not self._lookup_funcionario(resultado, str(arquivo_pdf)):
                resultado.status = StatusProcessamento.ERRO
                return resultado
            
            # ==================== ETAPA 4: Armazenamento MongoDB ====================
            if not self._armazenar_mongodb(resultado):
                resultado.status = StatusProcessamento.ERRO
                return resultado
            
            # ==================== Sucesso ====================
            resultado.status = StatusProcessamento.SUCESSO
            resultado.armazenamento_sucesso = True
            resultado.mensagens.append(f" Processamento concluído com sucesso")
            
        except Exception as e:
            logger.error(f"Erro crítico: {e}")
            resultado.status = StatusProcessamento.ERRO
            resultado.erros.append(f"Erro crítico: {str(e)}")
        
        finally:
            resultado.tempo_processamento_total_s = time.time() - tempo_inicio
            logger.info(f"Processamento finalizado em {resultado.tempo_processamento_total_s:.2f}s")
        
        return resultado
    
    def _validar_arquivo(self, arquivo: Path, resultado: ProcessarResultado) -> bool:
        """Valida arquivo antes de processar"""
        
        if not arquivo.exists():
            msg = f"Arquivo não encontrado: {arquivo}"
            logger.error(msg)
            resultado.erros.append(msg)
            return False
        
        if not arquivo.is_file():
            msg = f"Caminho não é arquivo: {arquivo}"
            logger.error(msg)
            resultado.erros.append(msg)
            return False
        
        if arquivo.suffix.lower() != ".pdf":
            msg = f"Arquivo não é PDF: {arquivo.suffix}"
            logger.error(msg)
            resultado.erros.append(msg)
            return False
        
        tamanho_kb = arquivo.stat().st_size / 1024
        if tamanho_kb > 50 * 1024:  # 50MB limite
            msg = f"Arquivo muito grande: {tamanho_kb:.0f} KB (máx 50MB)"
            logger.error(msg)
            resultado.erros.append(msg)
            return False
        
        resultado.mensagens.append(f" Validação OK ({tamanho_kb:.1f} KB)")
        return True
    
    def _extrair_gemini(self, arquivo: Path, resultado: ProcessarResultado) -> bool:
        """Extrai dados via Gemini Structured Output com retry automático"""
        
        tempo_inicio = time.time()
        max_tentativas = 3
        tentativa = 0
        ultima_erro = None
        
        while tentativa < max_tentativas:
            tentativa += 1
            try:
                logger.info(f"Iniciando extração Gemini (tentativa {tentativa}/{max_tentativas})...")
                resultado.mensagens.append(f"Enviando para Gemini (tentativa {tentativa})...")
                
                # Variar temperatura conforme tentativa
                temperature = 0.2 if tentativa == 1 else (0.4 if tentativa == 2 else 0.6)
                
                # Prompt descritivo
                prompt = """
                Analise esta Folha de Ponto manuscrita e extraia os dados conforme o JSON schema.
                
                Informações a extrair:
                1. **Cabeçalho**: Empresa (nome/CNPJ), Funcionário (nome/PIS/CPF), Período
                2. **Tabela de Dias**: IMPORTANTE - Incluir TODOS os dias do mês (1-31):
                   - Para dias com dados: Extrair hora entrada/saída, intervalo, total de horas, observações
                   - Para dias NÃO preenchidos/em branco: Incluir entrada com numero_dia, dia_semana (se houver), 
                     e todos os horários/observações como NULL (mas o dia deve estar na lista)
                   - Incluir também dias que podem estar marcados como feriado, folga, atestado (observar observações)
                
                Estrutura esperada para CADA dia (mesmo não preenchido):
                {
                  "numero_dia": 25,
                  "dia_semana": "Sábado",
                  "hora_entrada": null,
                  "hora_intervalo_inicio": null,
                  "hora_intervalo_fim": null,
                  "hora_saida": null,
                  "total_horas_trabalhadas": null,
                  "observacoes": null
                }
                
                Inclua:
                - Contagem de dias com dados vs em branco
                - Confiança geral (0-100) da leitura
                - Avisos sobre dificuldades de leitura
                
                Mesmo com manuscrito ilegível, tente extrair o máximo possível.
                Seja conservador: coloque NULL onde não conseguir ler com segurança.
                """
                
                # Salvar prompt no resultado
                if tentativa == 1:
                    resultado.prompt_gemini = prompt
                
                # Chamar Gemini com Structured Output
                resultado_json = self.gemini.documento_estruturado(
                    documento=arquivo,
                    prompt=prompt,
                    schema_pydantic=ExtratorFolhaPonto,
                    temperature=temperature,
                )
                
                # Salvar resposta bruta
                resultado.resposta_bruta_gemini = resultado_json
                
                # Validar se resposta está completa
                if not resultado_json or len(resultado_json) < 100:
                    ultima_erro = f"Resposta truncada: apenas {len(resultado_json)} caracteres"
                    logger.warning(f"  {ultima_erro} (tentativa {tentativa})")
                    if tentativa < max_tentativas:
                        continue
                    else:
                        raise ValueError(ultima_erro)
                
                # Validar se tem "dias" na resposta
                if '"dias"' not in resultado_json or '"dias":[]' in resultado_json:
                    ultima_erro = "Resposta sem dias extraídos"
                    logger.warning(f"  {ultima_erro} (tentativa {tentativa})")
                    if tentativa < max_tentativas:
                        continue
                    else:
                        # Se ainda não tiver dias, tentar parser de qualquer jeito
                        pass
                
                # Validar e parsear
                extracao = ExtratorFolhaPonto.model_validate_json(resultado_json)
                resultado.extracao_resultado = extracao
                resultado.extracao_sucesso = True
                
                tempo_gemini = time.time() - tempo_inicio
                resultado.tempo_gemini_s = tempo_gemini
                
                logger.info(f" Extração Gemini OK ({extracao.dias_com_dados} dias, confiança {extracao.confianca_geral}%)")
                resultado.mensagens.append(
                    f" Extração OK: {extracao.dias_com_dados} dias com dados, "
                    f"confiança {extracao.confianca_geral}%"
                )
                
                return True
                
            except Exception as e:
                ultima_erro = str(e)
                logger.warning(f"  Erro na tentativa {tentativa}: {e}")
                
                if tentativa < max_tentativas:
                    logger.info(f"Retentando...")
                    continue
                else:
                    break
        
        # Se chegou aqui, todas as tentativas falharam
        logger.error(f"Erro na extração após {max_tentativas} tentativas: {ultima_erro}")
        resultado.erros.append(f"Erro Gemini (após {max_tentativas} tentativas): {ultima_erro}")
        resultado.tempo_gemini_s = time.time() - tempo_inicio
        return False
    
    def _lookup_funcionario(self, resultado: ProcessarResultado, arquivo_pdf: str) -> bool:
        """
        Faz lookup do funcionário via FuncionarioService
        Se não encontrar, cria registro incompleto para completar depois
        """
        
        if not resultado.extracao_sucesso or not resultado.extracao_resultado:
            resultado.erros.append("Extração Gemini falhou, impossível fazer lookup")
            return False
        
        tempo_inicio = time.time()
        
        try:
            nome_extraido = resultado.extracao_resultado.funcionario_nome
            
            if not nome_extraido or nome_extraido.strip() == "":
                resultado.erros.append("Nome do funcionário não extraído do PDF")
                return False
            
            logger.info(f"Fazendo lookup de: {nome_extraido}")
            resultado.mensagens.append(f"Procurando funcionário: {nome_extraido}")
            
            # PASSO 1: Tentar busca APENAS por nome (ignorando lotação)
            # Isso evita duplicatas quando lotação difere entre geração e AI
            funcionario = None
            
            # Normalizar nome para busca
            import unicodedata
            nfkd = unicodedata.normalize('NFKD', nome_extraido)
            nome_normalizado = ''.join([c for c in nfkd if not unicodedata.combining(c)]).lower()
            
            candidatos = list(self.funcionario_service.colecao.find({
                "nome_normalizado": nome_normalizado
            }))
            
            if len(candidatos) == 1:
                # Único candidato encontrado - usar este
                funcionario = candidatos[0]
                logger.info(f"✓ Funcionário encontrado por nome único: {funcionario['nome']}")
            elif len(candidatos) > 1:
                # Múltiplos candidatos - tentar refinar por lotação/contrato
                logger.warning(f"Múltiplos funcionários ({len(candidatos)}) com nome '{nome_extraido}'")
                # Por ora, usar o primeiro (no futuro, pode implementar seleção inteligente)
                funcionario = candidatos[0]
                logger.info(f"Usando primeiro candidato: {funcionario['nome']} (lotação: {funcionario.get('lotacao', 'N/A')})")
            
            # PASSO 2: Se não encontrado por nome exato, tentar busca similar
            if not funcionario:
                logger.debug("Busca por nome falhou, tentando busca similar...")
                funcionario = self.funcionario_service.buscar_similar(
                    nome=nome_extraido,
                    lotacao="",
                    contrato="CLT",
                    limiar_similaridade=0.75
                )
            
            # PASSO 3: Se ainda não encontrado, AUTO-CADASTRAR
            if not funcionario:
                logger.warning(f"Funcionário não encontrado para: {nome_extraido}")
                logger.info("Iniciando auto-cadastro de funcionário incompleto...")
                
                # Sanitizar e criar estrutura
                func_doc, erros_sanitizacao = ConstrutorFuncionarioIncompleto.criar_do_pdf(
                    nome_pdf=Path(arquivo_pdf).name,
                    empresa_extraida=resultado.extracao_resultado.empresa_nome or "Desconhecida",
                    funcionario_nome_extraido=nome_extraido,
                    funcionario_funcao=None,  # Não extraído do PDF
                    mes_ano=resultado.extracao_resultado.mes_ano,
                    modo_rígido=False
                )
                
                # Registrar erros de sanitização
                if erros_sanitizacao:
                    for erro in erros_sanitizacao:
                        logger.warning(f"    {erro}")
                        resultado.avisos.append(f"Sanitização: {erro}")
                
                # Inserir funcionário incompleto
                try:
                    id_novo = self.funcionario_service.criar_funcionario(func_doc)
                    
                    if id_novo:
                        logger.info(f" Auto-cadastro OK: {func_doc['nome']} (ID: {id_novo})")
                        resultado.funcionario_id = str(id_novo)
                        resultado.funcionario_nome_encontrado = func_doc['nome']
                        resultado.funcionario_score_similaridade = 0  # Auto-cadastro
                        resultado.lookup_sucesso = True
                        resultado.avisos.append(
                            f"Funcionário auto-cadastrado como incompleto: {func_doc['nome']}"
                        )
                        resultado.mensagens.append(
                            f" Funcionário criado (incompleto): {func_doc['nome']}"
                        )
                        
                        tempo_lookup = time.time() - tempo_inicio
                        resultado.tempo_lookup_s = tempo_lookup
                        return True
                    else:
                        msg = "Erro ao criar funcionário incompleto"
                        logger.error(msg)
                        resultado.erros.append(msg)
                        resultado.tempo_lookup_s = time.time() - tempo_inicio
                        return False
                
                except Exception as e:
                    msg = f"Erro ao auto-cadastrar funcionário: {str(e)}"
                    logger.error(msg)
                    resultado.erros.append(msg)
                    resultado.tempo_lookup_s = time.time() - tempo_inicio
                    return False
            
            # PASSO 4: Se encontrado (exato ou similar)
            resultado.lookup_sucesso = True
            # Obter _id do funcionário (sempre presente)
            id_obj = funcionario.get("_id")
            resultado.funcionario_id = str(id_obj) if isinstance(id_obj, ObjectId) else id_obj
            resultado.funcionario_nome_encontrado = funcionario.get("nome")
            resultado.funcionario_score_similaridade = 100  # Encontrado
            
            tempo_lookup = time.time() - tempo_inicio
            resultado.tempo_lookup_s = tempo_lookup
            
            logger.info(f" Lookup OK: {funcionario.get('nome')} ({resultado.funcionario_id})")
            resultado.mensagens.append(f" Funcionário encontrado: {funcionario.get('nome')}")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro no lookup: {e}")
            resultado.erros.append(f"Erro lookup: {str(e)}")
            resultado.tempo_lookup_s = time.time() - tempo_inicio
            return False
    
    def _armazenar_mongodb(self, resultado: ProcessarResultado) -> bool:
        """Armazena dados extraídos em MongoDB na coleção folha_de_ponto"""
        
        if not resultado.lookup_sucesso or not resultado.extracao_sucesso:
            resultado.erros.append("Extração ou lookup falhou, impossível armazenar")
            return False
        
        tempo_inicio = time.time()
        
        try:
            logger.info("Armazenando em MongoDB...")
            
            extracao = resultado.extracao_resultado
            
            # Obter caminho absoluto do arquivo analisado
            caminho_absoluto_analisado = str(Path(resultado.arquivo_origem).resolve()) if resultado.arquivo_origem else None
            
            # ==================== AUTOCADASTRO DE EMPRESA ====================
            # Verificar se empresa existe, se não criar incompleta
            empresa_nome = extracao.empresa_nome or "Desconhecida"
            empresa_doc = self.empresa_service.obter_ou_criar_incompleta(empresa_nome)
            
            # Extrair empresa_id do documento
            # Sempre usar _id como identificador único (nunca id_empresa que é redundante)
            try:
                if '_id' in empresa_doc:
                    empresa_oid = empresa_doc['_id']
                    if isinstance(empresa_oid, str):
                        empresa_oid = ObjectId(empresa_oid)
                    empresa_id = str(empresa_oid)
                else:
                    raise ValueError("Empresa documento sem _id!")
            except Exception as e:
                logger.error(f"Erro ao extrair empresa_oid: {e}")
                # Fallback: criar novo ObjectId (não deve acontecer)
                empresa_oid = ObjectId()
                empresa_id = str(empresa_oid)
            
            logger.debug(f"Empresa para folha: {empresa_nome} (ID: {empresa_id})")
            
            # Converter dias extraídos para DiaFolhaPonto
            dias_processados = []
            if extracao and extracao.dias:
                # Reconstruir data a partir de mes_referencia
                mes_ano = extracao.mes_ano or datetime.now().strftime("%Y-%m")
                ano, mes = mes_ano.split('-')
                
                for dia_extr in extracao.dias:
                    # Reconstruir data completa (MELHORIA 2)
                    try:
                        data_dia = datetime(int(ano), int(mes), dia_extr.numero_dia)
                    except ValueError:
                        data_dia = None  # Dia inválido (ex: 31 de fevereiro)
                    
                    # Calcular total de horas se não foi extraído (MELHORIA 3)
                    total_horas = dia_extr.total_horas_trabalhadas
                    if not total_horas:
                        total_horas = calcular_total_horas(
                            dia_extr.hora_entrada,
                            dia_extr.hora_saida,
                            dia_extr.hora_intervalo_inicio,
                            dia_extr.hora_intervalo_fim
                        )
                    
                    dia = DiaFolhaPonto(
                        numero_dia=dia_extr.numero_dia,
                        data=data_dia,  # MELHORIA 2: data reconstruída
                        dia_semana=dia_extr.dia_semana,
                        hora_entrada=dia_extr.hora_entrada,
                        hora_intervalo_inicio=dia_extr.hora_intervalo_inicio,
                        hora_intervalo_fim=dia_extr.hora_intervalo_fim,
                        hora_saida=dia_extr.hora_saida,
                        total_horas_trabalhadas=total_horas,  # MELHORIA 3: calculado
                        observacoes=dia_extr.observacoes,
                        tipo_dia=converter_string_para_tipo_dia(dia_extr.tipo_dia),  # Converte string -> TipoDia ENUM
                        preenchido_manualmente=False,
                        analise_ia_processada=True,  # MELHORIA 1: marca que veio da IA
                    )
                    dias_processados.append(dia)
            
            # Criar AnaliseIAResultado com informações completas do Gemini
            analise_ia = AnaliseIAResultado(
                data_analise=datetime.now(timezone.utc),
                modelo_ia="gemini-2.5-pro",
                prompt_utilizado=resultado.prompt_gemini,
                resposta_bruta=resultado.resposta_bruta_gemini,
                dias_analisados=len(dias_processados),
                taxa_preenchimento=(extracao.dias_com_dados / len(dias_processados) * 100) if dias_processados else 0,
                avisos=extracao.avisos if extracao else [],
                erros=extracao.erros if extracao else [],
                tempo_processamento_segundos=resultado.tempo_gemini_s,
                tokens_utilizados=resultado.tokens_utilizados,
            )
            
            # Calcular data_inicio e data_fim do mês
            mes_ano = extracao.mes_ano or datetime.now().strftime("%Y-%m")
            ano, mes = map(int, mes_ano.split('-'))
            data_inicio = date(ano, mes, 1)
            
            # Último dia do mês
            if mes == 12:
                data_fim = date(ano, 12, 31)
            else:
                data_fim = date(ano if mes < 12 else ano + 1, mes + 1 if mes < 12 else 1, 1) - timedelta(days=1)
            
            # Calcular totalizações
            total_horas_mes_minutos = 0
            total_faltas = 0
            total_feriados = 0
            total_finais_semana = 0
            
            for dia in dias_processados:
                # Contar feriados (compatível com ENUM)
                if dia.tipo_dia == TipoDia.FERIADO:
                    total_feriados += 1
                
                # Contar finais de semana (compatível com ENUM)
                if dia.tipo_dia in (TipoDia.SABADO, TipoDia.DOMINGO):
                    total_finais_semana += 1
                elif dia.dia_semana and dia.dia_semana.upper() in ['SÁBADO', 'SABADO', 'DOMINGO']:
                    total_finais_semana += 1
                
                # Contar faltas (compatível com ENUM)
                if dia.tipo_dia == TipoDia.FALTA:
                    total_faltas += 1
                
                # Somar horas trabalhadas
                if dia.total_horas_trabalhadas:
                    try:
                        partes = dia.total_horas_trabalhadas.split(':')
                        if len(partes) == 2:
                            horas = int(partes[0])
                            minutos = int(partes[1])
                            total_horas_mes_minutos += (horas * 60 + minutos)
                    except:
                        pass
            
            # Converter total de minutos para HH:MM
            total_horas_mes = f"{total_horas_mes_minutos // 60:02d}:{total_horas_mes_minutos % 60:02d}"
            
            # Criar documento FolhaDePontoData com campos completos
            folha_data = FolhaDePontoData(
                mes_referencia=mes_ano,
                data_inicio=data_inicio,
                data_fim=data_fim,
                dias=dias_processados,
                total_horas_mes=total_horas_mes,
                total_faltas=total_faltas,
                total_feriados=total_feriados,
                total_finais_semana=total_finais_semana,
                analise_ia=analise_ia,
                preenchimento_concluido=False,
                analise_ia_concluida=True
            )
            
            # Construir documento para MongoDB com campos de controle
            # Converter funcionario_id para ObjectId
            try:
                funcionario_oid = ObjectId(resultado.funcionario_id)
            except:
                funcionario_oid = ObjectId()
            
            # Criar FolhaDePontoMongoDB e usar to_mongo_insert() para garantir conversão de dates
            folha_completa = FolhaDePontoMongoDB(
                folha_data=folha_data,
                funcionario_id=funcionario_oid,
                empresa_id=empresa_oid,
                mes_referencia=extracao.mes_ano or datetime.now().strftime("%Y-%m"),
                caminho_arquivo_analisado=caminho_absoluto_analisado,
                data_criacao=datetime.now(timezone.utc),
                data_atualizacao=datetime.now(timezone.utc),
                status=StatusFolhaPonto.ANALISE_CONCLUIDA,
                versao=1
            )
            
            # Usar to_mongo_insert() que converte date→datetime automaticamente
            doc_mongodb = folha_completa.to_mongo_insert()
            
            # Inserir em MongoDB com upsert se houver duplicata
            try:
                id_documento = self.folha_service.colecao.insert_one(doc_mongodb).inserted_id
                logger.info(f" Nova folha inserida: ID {id_documento}")
            except Exception as insert_error:
                # Se erro de chave duplicada, fazer upsert
                if "E11000" in str(insert_error) or "duplicate key" in str(insert_error):
                    logger.debug(f"Folha já existe para este período, atualizando...")
                    
                    # Filtro pela chave composta
                    filtro = {
                        "funcionario_id": funcionario_oid,
                        "empresa_id": empresa_oid,
                        "mes_referencia": extracao.mes_ano or datetime.now().strftime("%Y-%m"),
                    }
                    
                    # Remover _id para não tentar atualizar campo imutável
                    doc_update = doc_mongodb.copy()
                    doc_update.pop("_id", None)
                    
                    # Fazer upsert
                    resultado_upsert = self.folha_service.colecao.update_one(
                        filtro,
                        {"$set": doc_update},
                        upsert=True
                    )
                    
                    # Buscar documento atualizado
                    doc_existente = self.folha_service.colecao.find_one(filtro)
                    id_documento = doc_existente.get("_id") if doc_existente else resultado_upsert.upserted_id
                    
                    tempo_mongodb = time.time() - tempo_inicio
                    logger.info(f" Folha atualizada via upsert (ID: {id_documento}, {tempo_mongodb:.2f}s)")
                else:
                    raise insert_error
            
            # ==================== ATUALIZAR RELACIONAMENTOS ====================
            # Adicionar empresa ao funcionário (em empresas_ids como ObjectId)
            try:
                funcionario_doc = self.funcionario_service.colecao.find_one({
                    "_id": funcionario_oid
                })
                if funcionario_doc:
                    # Adicionar empresa_oid à lista de empresas do funcionário
                    self.funcionario_service.colecao.update_one(
                        {"_id": funcionario_oid},
                        {"$addToSet": {"empresas_ids": empresa_oid}}
                    )
                    logger.debug(f"Empresa adicionada ao funcionário")
            except Exception as e:
                logger.debug(f"Erro ao adicionar empresa ao funcionário: {e}")
            
            resultado.armazenamento_sucesso = True
            resultado.folha_id = str(id_documento)
            
            tempo_mongodb = time.time() - tempo_inicio
            resultado.tempo_mongodb_s = tempo_mongodb
            
            logger.info(f" MongoDB armazenado (ID: {id_documento}, {tempo_mongodb:.2f}s)")
            resultado.mensagens.append(f" Armazenado em MongoDB: {id_documento}")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro no armazenamento: {e}")
            resultado.erros.append(f"Erro MongoDB: {str(e)}")
            resultado.tempo_mongodb_s = time.time() - tempo_inicio
            return False
