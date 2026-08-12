"""
Orquestrador de Envio de Holerites
Responsabilidades:
- Coordenar todo o fluxo de envio de holerites
- Suportar dois modos: via planilha ou via MongoDB
- Enviar por Email, WhatsApp individual e grupo
- Registrar todos os envios no MongoDB
- Gerar relatórios
"""

import os
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from src.utils.logger_config import logger
from src.utils.retry_utils import obter_config_retry

from src.models.holerite_models import StatusHoleriteEnum
from src.models.template_mensagem_models import TipoTemplateEnum
from src.services.planilha_holerites_service import (
    planilha_holerites_service, 
    TipoEnvioHolerite
)
from src.services.holerite_service import holerite_service
from src.services.contato_funcionario_service import contato_funcionario_service
from src.services.empresa_service import empresa_service
from src.services.funcionario_service import FuncionarioService
from src.services.template_mensagem_service import template_mensagem_service
from src.services.grupo_whatsapp_service import grupo_whatsapp_service

# Serviços de envio
try:
    from src.services.zoho_mail_service import zoho_mail_service
    ZOHO_DISPONIVEL = True
except ImportError:
    ZOHO_DISPONIVEL = False
    zoho_mail_service = None

try:
    from src.services.whatsapp_service import whatsapp_service
    WHATSAPP_DISPONIVEL = True
except ImportError:
    WHATSAPP_DISPONIVEL = False
    whatsapp_service = None

try:
    from bson import ObjectId
except ImportError:
    ObjectId = str


# Nomes dos meses em português
MESES_EXTENSO = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}


class TipoEnvioEnum:
    """Tipos de envio disponíveis"""
    EMAIL = "email"
    WHATSAPP_INDIVIDUAL = "whatsapp_individual"
    WHATSAPP_GRUPO = "whatsapp_grupo"


@dataclass
class ResultadoEnvioHolerite:
    """Resultado de um envio individual de holerite"""
    tipo: str
    sucesso: bool
    destinatario: str
    holerite_id: Optional[str] = None
    funcionario_id: Optional[str] = None
    arquivo: str = ""
    mensagem: str = ""
    detalhes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RelatorioEnvioHolerite:
    """Relatório consolidado de envios de holerites"""
    competencia: str
    modo_envio: str  # "planilha" ou "mongodb"
    total_holerites: int = 0
    total_envios: int = 0
    enviados_sucesso: int = 0
    enviados_erro: int = 0
    por_tipo: Dict[str, Dict[str, int]] = field(default_factory=dict)
    erros: List[Dict[str, Any]] = field(default_factory=list)
    inicio: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    fim: Optional[datetime] = None
    
    def duracao_segundos(self) -> float:
        if self.fim:
            return (self.fim - self.inicio).total_seconds()
        return 0


class EnvioHoleriteOrquestrador:
    """
    Coordena o processo completo de envio de holerites.
    
    Dois modos de operação:
    
    1. MODO PLANILHA (TipoEnvioHolerite.PLANILHA):
       - Lê planilha de contatos de holerites
       - Envia para grupos ou contatos genéricos
       - Similar ao fluxo de folhas de ponto
    
    2. MODO MONGODB (TipoEnvioHolerite.MONGODB):
       - Busca holerites pendentes no MongoDB
       - Envia diretamente para o funcionário
       - Usa contatos cadastrados no MongoDB
    """
    
    def __init__(self):
        """Inicializa o orquestrador"""
        self._config_retry_max_tentativas, self._config_retry_delay = obter_config_retry()
        self._callback_progresso: Optional[Callable[[str, int, int], None]] = None
        self._funcionario_service = FuncionarioService()
    
    def definir_callback_progresso(self, callback: Callable[[str, int, int], None]) -> None:
        """
        Define callback para atualização de progresso
        
        Args:
            callback: Função(mensagem, atual, total)
        """
        self._callback_progresso = callback
    
    def _reportar_progresso(self, mensagem: str, atual: int = 0, total: int = 0) -> None:
        """Reporta progresso via callback"""
        if self._callback_progresso:
            self._callback_progresso(mensagem, atual, total)
        logger.info(mensagem)
    
    def verificar_servicos(self) -> Dict[str, bool]:
        """
        Verifica disponibilidade dos serviços necessários
        
        Returns:
            Dict com status de cada serviço
        """
        self._reportar_progresso("Verificando serviços...")
        
        status = {
            "planilha_holerites": planilha_holerites_service.disponivel,
            "holerite_service": holerite_service.disponivel,
            "contato_service": contato_funcionario_service.disponivel,
            "templates": template_mensagem_service.disponivel,
            "whatsapp": WHATSAPP_DISPONIVEL and whatsapp_service is not None,
            "zoho_mail": ZOHO_DISPONIVEL and zoho_mail_service is not None
        }
        
        # Verificar conexão WhatsApp
        if status["whatsapp"] and whatsapp_service:
            try:
                ws_status = whatsapp_service.verificar_status()
                status["whatsapp_conectado"] = ws_status.get("conectado", False)
            except:
                status["whatsapp_conectado"] = False
        else:
            status["whatsapp_conectado"] = False
        
        # Verificar Zoho
        if status["zoho_mail"] and zoho_mail_service:
            try:
                zoho_status = zoho_mail_service.verificar_conexao()
                status["zoho_mail_conectado"] = zoho_status.get("token_valido", False)
            except:
                status["zoho_mail_conectado"] = False
        else:
            status["zoho_mail_conectado"] = False
        
        # Log
        for servico, disponivel in status.items():
            emoji = "✓" if disponivel else "✗"
            logger.info(f"  {emoji} {servico}: {'OK' if disponivel else 'Indisponível'}")
        
        return status
    
    # ==================== CONTEXTO DE TEMPLATE ====================
    
    def _montar_contexto_template(
        self,
        funcionario_nome: str,
        competencia: str,
        empresa_nome: str = "",
        dados_extras: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Monta contexto para renderização de templates
        
        Args:
            funcionario_nome: Nome do funcionário
            competencia: Competência no formato MM/AAAA
            empresa_nome: Nome da empresa
            dados_extras: Dados adicionais
        
        Returns:
            Dicionário de contexto para template
        """
        # Extrair mês e ano da competência
        try:
            mes, ano = competencia.split("/")
            mes = int(mes)
            ano = int(ano)
            mes_extenso = MESES_EXTENSO.get(mes, competencia)
        except:
            mes_extenso = competencia
            mes = 0
            ano = 0
        
        contexto = {
            "funcionario_nome": funcionario_nome,
            "nome": funcionario_nome,  # Alias
            "competencia": competencia,
            "mes": mes,  # Para templates
            "ano": ano,  # Para templates
            "mes_referencia": mes,
            "ano_referencia": ano,
            "mes_extenso": mes_extenso,
            "empresa": empresa_nome,
            "local": "",  # Será preenchido via dados_extras se disponível
            "tipo_documento": "Recibo de Pagamento",
            "data_envio": datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        
        if dados_extras:
            contexto.update(dados_extras)
        
        return contexto
    
    # ==================== ENVIO POR CANAL ====================
    
    def _enviar_email(
        self,
        destinatarios: List[str],
        arquivos: List[str],
        contexto: Dict[str, Any]
    ) -> ResultadoEnvioHolerite:
        """Envia holerite por e-mail"""
        
        if not ZOHO_DISPONIVEL or not zoho_mail_service:
            return ResultadoEnvioHolerite(
                tipo=TipoEnvioEnum.EMAIL,
                sucesso=False,
                destinatario=", ".join(destinatarios),
                mensagem="Serviço de e-mail não disponível"
            )
        
        if not destinatarios:
            return ResultadoEnvioHolerite(
                tipo=TipoEnvioEnum.EMAIL,
                sucesso=False,
                destinatario="",
                mensagem="Nenhum e-mail configurado"
            )
        
        if not arquivos:
            return ResultadoEnvioHolerite(
                tipo=TipoEnvioEnum.EMAIL,
                sucesso=False,
                destinatario=", ".join(destinatarios),
                mensagem="Nenhum arquivo para enviar"
            )
        
        # Renderizar template - usar EMAIL_HOLERITE
        template_renderizado = template_mensagem_service.renderizar_por_tipo(
            TipoTemplateEnum.EMAIL_HOLERITE,
            contexto
        )
        
        if not template_renderizado:
            # Usar mensagem padrão com assunto correto
            local = contexto.get('local', '')
            mes = contexto.get('mes_referencia', contexto.get('mes', ''))
            ano = contexto.get('ano_referencia', contexto.get('ano', ''))
            
            # Formatar mês com zero à esquerda
            if mes:
                mes = f"{int(mes):02d}"
            
            assunto = f"Recibo de Pagamento - {mes}/{ano}"
            if local:
                assunto += f" - {local}"
            
            template_renderizado = {
                "assunto": assunto,
                "mensagem": f"""Bom dia,

Segue anexo do(s) recibo(s) de pagamento referente ao mês de {contexto.get('mes_extenso', '')}/{ano}.

Atenciosamente,
Moraes e Santos"""
            }
        
        # Enviar
        resultado = zoho_mail_service.enviar_email(
            destinatarios=destinatarios,
            assunto=template_renderizado.get("assunto", "Holerite"),
            corpo=template_renderizado.get("mensagem", ""),
            anexos=arquivos
        )
        
        return ResultadoEnvioHolerite(
            tipo=TipoEnvioEnum.EMAIL,
            sucesso=resultado.get("sucesso", False),
            destinatario=", ".join(destinatarios),
            arquivo=os.path.basename(arquivos[0]) if arquivos else "",
            mensagem=resultado.get("mensagem", ""),
            detalhes=resultado.get("detalhes", {})
        )
    
    def _enviar_whatsapp(
        self,
        telefone: str,
        arquivos: List[str],
        contexto: Dict[str, Any]
    ) -> ResultadoEnvioHolerite:
        """Envia holerite por WhatsApp individual"""
        
        if not WHATSAPP_DISPONIVEL or not whatsapp_service:
            return ResultadoEnvioHolerite(
                tipo=TipoEnvioEnum.WHATSAPP_INDIVIDUAL,
                sucesso=False,
                destinatario=telefone,
                mensagem="Serviço WhatsApp não disponível"
            )
        
        if not telefone:
            return ResultadoEnvioHolerite(
                tipo=TipoEnvioEnum.WHATSAPP_INDIVIDUAL,
                sucesso=False,
                destinatario="",
                mensagem="Nenhum telefone configurado"
            )
        
        if not arquivos:
            return ResultadoEnvioHolerite(
                tipo=TipoEnvioEnum.WHATSAPP_INDIVIDUAL,
                sucesso=False,
                destinatario=telefone,
                mensagem="Nenhum arquivo para enviar"
            )
        
        # Renderizar template - usar WHATSAPP_INDIVIDUAL_HOLERITE
        template_renderizado = template_mensagem_service.renderizar_por_tipo(
            TipoTemplateEnum.WHATSAPP_INDIVIDUAL_HOLERITE,
            contexto
        )
        
        if not template_renderizado:
            nome = contexto.get('funcionario_nome', contexto.get('nome', ''))
            mes_extenso = contexto.get('mes_extenso', '')
            ano = contexto.get('ano_referencia', contexto.get('ano', ''))
            mensagem = f"Olá {nome}! Segue seu recibo de pagamento de {mes_extenso}/{ano}."
        else:
            mensagem = template_renderizado.get("mensagem", "")

        # Obter device_id da empresa se existir
        empresa_nome = contexto.get('empresa', '')
        device_id = None

        if empresa_nome:
            try:
                if empresa_service.disponivel:
                    # Busca por nome_simplificado primeiro, depois nome completo
                    empresa = empresa_service.buscar_por_nome_ou_simplificado(empresa_nome)
                    if empresa and empresa.get('whatsapp_device_id'):
                        device_id = empresa.get('whatsapp_device_id')
                        logger.info(f"📱 Usando device {device_id} para empresa {empresa_nome}")
                    else:
                        logger.info(f"📱 Empresa {empresa_nome} sem device configurado, usando padrão")
            except Exception as e:
                logger.warning(f"⚠ Erro ao buscar empresa {empresa_nome}: {e}")

        # Enviar: primeiro mensagem de texto, depois os arquivos
        resultado = whatsapp_service.enviar_multiplos_arquivos(
            destinatario=telefone,
            arquivos=arquivos,
            mensagem=mensagem,
            is_grupo=False,
            device_id=device_id
        )
        
        sucesso_total = resultado.get("sucesso", False)
        
        return ResultadoEnvioHolerite(
            tipo=TipoEnvioEnum.WHATSAPP_INDIVIDUAL,
            sucesso=sucesso_total,
            destinatario=telefone,
            arquivo=os.path.basename(arquivos[0]) if arquivos else "",
            mensagem="Enviado com sucesso" if sucesso_total else "Falha no envio"
        )
    
    def _enviar_whatsapp_grupo(
        self,
        grupo_nome: str,
        arquivos: List[str],
        contexto: Dict[str, Any]
    ) -> ResultadoEnvioHolerite:
        """Envia holerite para grupo WhatsApp"""
        
        if not WHATSAPP_DISPONIVEL or not whatsapp_service:
            return ResultadoEnvioHolerite(
                tipo=TipoEnvioEnum.WHATSAPP_GRUPO,
                sucesso=False,
                destinatario=grupo_nome,
                mensagem="Serviço WhatsApp não disponível"
            )
        
        # Buscar grupo no cache
        grupo = grupo_whatsapp_service.buscar_por_nome(grupo_nome)
        if not grupo:
            return ResultadoEnvioHolerite(
                tipo=TipoEnvioEnum.WHATSAPP_GRUPO,
                sucesso=False,
                destinatario=grupo_nome,
                mensagem=f"Grupo '{grupo_nome}' não encontrado"
            )
        
        # O campo é 'jid', não 'group_id'
        grupo_jid = grupo.get("jid")
        if not grupo_jid:
            return ResultadoEnvioHolerite(
                tipo=TipoEnvioEnum.WHATSAPP_GRUPO,
                sucesso=False,
                destinatario=grupo_nome,
                mensagem="JID do grupo não encontrado"
            )
        
        # Renderizar template - usar WHATSAPP_GRUPO_HOLERITE
        template_renderizado = template_mensagem_service.renderizar_por_tipo(
            TipoTemplateEnum.WHATSAPP_GRUPO_HOLERITE,
            contexto
        )
        
        if not template_renderizado:
            mes_extenso = contexto.get('mes_extenso', '')
            ano = contexto.get('ano_referencia', contexto.get('ano', ''))
            mensagem = f"Bom dia! Seguem os recibos de pagamento referente ao mês de {mes_extenso}/{ano}."
        else:
            mensagem = template_renderizado.get("mensagem", "")

        # Obter device_id da empresa se existir
        empresa_nome = contexto.get('empresa', '')
        device_id = None

        if empresa_nome:
            try:
                if empresa_service.disponivel:
                    # Busca por nome_simplificado primeiro, depois nome completo
                    empresa = empresa_service.buscar_por_nome_ou_simplificado(empresa_nome)
                    if empresa and empresa.get('whatsapp_device_id'):
                        device_id = empresa.get('whatsapp_device_id')
                        logger.info(f"📱 Usando device {device_id} para empresa {empresa_nome}")
                    else:
                        logger.info(f"📱 Empresa {empresa_nome} sem device configurado, usando padrão")
            except Exception as e:
                logger.warning(f"⚠ Erro ao buscar empresa {empresa_nome}: {e}")

        # Enviar: primeiro mensagem de texto, depois os arquivos
        resultado = whatsapp_service.enviar_multiplos_arquivos(
            destinatario=grupo_jid,
            arquivos=arquivos,
            mensagem=mensagem,
            is_grupo=True,
            device_id=device_id
        )
        
        sucesso_total = resultado.get("sucesso", False)
        
        return ResultadoEnvioHolerite(
            tipo=TipoEnvioEnum.WHATSAPP_GRUPO,
            sucesso=sucesso_total,
            destinatario=grupo_nome,
            arquivo=os.path.basename(arquivos[0]) if arquivos else "",
            mensagem="Enviado com sucesso" if sucesso_total else "Falha no envio"
        )
    
    # ==================== MODO PLANILHA ====================
    
    def enviar_via_planilha(
        self,
        mes: int | None = None,
        ano: int | None = None,
        apenas_simular: bool = False
    ) -> RelatorioEnvioHolerite:
        """
        Envia holerites usando a planilha de contatos.
        
        Similar ao envio de folhas de ponto: lê planilha,
        busca PDFs no diretório, envia para grupos/contatos.
        
        Args:
            mes: Mês de referência
            ano: Ano de referência
            apenas_simular: Se True, não envia de fato
        
        Returns:
            Relatório de envio
        """
        competencia = f"{mes:02d}/{ano}" if mes and ano else "N/A"
        relatorio = RelatorioEnvioHolerite(
            competencia=competencia,
            modo_envio="planilha"
        )
        
        self._reportar_progresso(f"Iniciando envio de holerites via planilha ({competencia})...")
        
        # Carregar planilha
        if not planilha_holerites_service.carregar():
            logger.error("Falha ao carregar planilha de holerites")
            relatorio.erros.append({"erro": "Falha ao carregar planilha"})
            relatorio.fim = datetime.now(timezone.utc)
            return relatorio
        
        # Iterar contatos
        contatos = list(planilha_holerites_service.iterar_contatos(mes, ano))
        relatorio.total_holerites = len(contatos)
        
        for i, contato in enumerate(contatos, 1):
            nome = contato.get("nome", "")
            self._reportar_progresso(f"Processando {nome}...", i, len(contatos))
            
            arquivos = contato.get("arquivos_pdf", [])
            if not arquivos:
                logger.warning(f"  Sem PDFs para: {nome}")
                continue
            
            # Montar contexto com todas as informações necessárias
            contexto = self._montar_contexto_template(
                funcionario_nome=nome,
                competencia=competencia,
                empresa_nome=contato.get("empresa", ""),
                dados_extras={
                    "local": contato.get("local", ""),
                    "mes_referencia": contato.get("mes_referencia", mes),
                    "ano_referencia": contato.get("ano_referencia", ano)
                }
            )
            
            resultados_contato: List[ResultadoEnvioHolerite] = []
            
            # Email
            if contato.get("enviar_email"):
                if apenas_simular:
                    logger.info(f"  [SIMULAÇÃO] Enviaria e-mail para: {contato.get('emails', [])}")
                else:
                    resultado = self._enviar_email(
                        destinatarios=contato.get("emails", []),
                        arquivos=arquivos,
                        contexto=contexto
                    )
                    resultados_contato.append(resultado)
                    relatorio.total_envios += 1
                    if resultado.sucesso:
                        relatorio.enviados_sucesso += 1
                    else:
                        relatorio.enviados_erro += 1
                        relatorio.erros.append({
                            "contato": nome,
                            "tipo": "email",
                            "erro": resultado.mensagem
                        })
            
            # WhatsApp Individual
            if contato.get("enviar_whatsapp"):
                for telefone in contato.get("telefones", []):
                    if apenas_simular:
                        logger.info(f"  [SIMULAÇÃO] Enviaria WhatsApp para: {telefone}")
                    else:
                        resultado = self._enviar_whatsapp(
                            telefone=telefone,
                            arquivos=arquivos,
                            contexto=contexto
                        )
                        resultados_contato.append(resultado)
                        relatorio.total_envios += 1
                        if resultado.sucesso:
                            relatorio.enviados_sucesso += 1
                        else:
                            relatorio.enviados_erro += 1
                            relatorio.erros.append({
                                "contato": nome,
                                "tipo": "whatsapp",
                                "erro": resultado.mensagem
                            })
            
            # WhatsApp Grupo
            if contato.get("enviar_grupo_whatsapp"):
                for grupo in contato.get("grupos_whatsapp", []):
                    if apenas_simular:
                        logger.info(f"  [SIMULAÇÃO] Enviaria para grupo: {grupo}")
                    else:
                        resultado = self._enviar_whatsapp_grupo(
                            grupo_nome=grupo,
                            arquivos=arquivos,
                            contexto=contexto
                        )
                        resultados_contato.append(resultado)
                        relatorio.total_envios += 1
                        if resultado.sucesso:
                            relatorio.enviados_sucesso += 1
                        else:
                            relatorio.enviados_erro += 1
                            relatorio.erros.append({
                                "contato": nome,
                                "tipo": "whatsapp_grupo",
                                "erro": resultado.mensagem
                            })
        
        relatorio.fim = datetime.now(timezone.utc)
        
        # Log resumo
        logger.info(f"\n=== RESUMO ENVIO VIA PLANILHA ===")
        logger.info(f"Total contatos: {relatorio.total_holerites}")
        logger.info(f"Total envios: {relatorio.total_envios}")
        logger.info(f"Sucesso: {relatorio.enviados_sucesso}")
        logger.info(f"Erros: {relatorio.enviados_erro}")
        logger.info(f"Duração: {relatorio.duracao_segundos():.1f}s")
        
        return relatorio
    
    # ==================== MODO MONGODB ====================
    
    def enviar_via_mongodb(
        self,
        competencia: str,
        empresa_id: str | None = None,
        canais: List[str] | None = None,
        apenas_simular: bool = False
    ) -> RelatorioEnvioHolerite:
        """
        Envia holerites diretamente para funcionários usando dados do MongoDB.
        
        Busca holerites pendentes e envia para os contatos
        cadastrados de cada funcionário.
        
        Args:
            competencia: Competência no formato MM/AAAA
            empresa_id: Filtrar por empresa (opcional)
            canais: Lista de canais a usar ["email", "whatsapp"] (default: ambos)
            apenas_simular: Se True, não envia de fato
        
        Returns:
            Relatório de envio
        """
        relatorio = RelatorioEnvioHolerite(
            competencia=competencia,
            modo_envio="mongodb"
        )
        
        if canais is None:
            canais = ["email", "whatsapp"]
        
        self._reportar_progresso(f"Iniciando envio de holerites via MongoDB ({competencia})...")
        
        # Buscar holerites pendentes
        holerites = holerite_service.listar_pendentes_envio(
            empresa_id=empresa_id,
            competencia=competencia
        )
        
        relatorio.total_holerites = len(holerites)
        
        if not holerites:
            logger.info(f"Nenhum holerite pendente para {competencia}")
            relatorio.fim = datetime.now(timezone.utc)
            return relatorio
        
        logger.info(f"Encontrados {len(holerites)} holerites pendentes")
        
        # OTIMIZAÇÃO: Obter todos os contatos em BATCH (1 query ao invés de N)
        funcionario_ids = [str(h.get("funcionario_id")) for h in holerites if h.get("funcionario_id")]
        contatos_map = {}
        
        if funcionario_ids and contato_funcionario_service:
            try:
                self._reportar_progresso(f"Carregando contatos de {len(funcionario_ids)} funcionários...")
                contatos_map = contato_funcionario_service.obter_contatos_batch(funcionario_ids)
                logger.info(f"✅ Contatos carregados em batch para {len(contatos_map)} funcionários")
            except Exception as e:
                logger.error(f"Erro ao carregar contatos em batch: {e}")
        
        for i, holerite in enumerate(holerites, 1):
            funcionario_id = holerite.get("funcionario_id")
            funcionario_nome = holerite.get("funcionario_nome", "Desconhecido")
            holerite_id = str(holerite.get("_id", ""))
            
            self._reportar_progresso(
                f"Enviando para {funcionario_nome}...", 
                i, 
                len(holerites)
            )
            
            # Obter caminho do arquivo
            arquivo_info = holerite.get("arquivo", {})
            caminho_arquivo = arquivo_info.get("caminho", "")
            
            if not caminho_arquivo or not Path(caminho_arquivo).exists():
                logger.warning(f"  Arquivo não encontrado: {caminho_arquivo}")
                relatorio.erros.append({
                    "holerite_id": holerite_id,
                    "funcionario": funcionario_nome,
                    "erro": "Arquivo não encontrado"
                })
                continue
            
            arquivos = [caminho_arquivo]
            
            # Obter contatos do funcionário
            if not funcionario_id:
                logger.warning(f"  Holerite sem funcionário vinculado")
                continue
            
            funcionario_id_str = str(funcionario_id)
            
            # Obter local/contrato/polo do holerite (se disponível)
            contrato_nome = holerite.get("contrato_nome", "")
            local = contrato_nome if contrato_nome else holerite.get("empresa_nome", "")
            
            # Contexto para template - para envio individual via MongoDB
            contexto = self._montar_contexto_template(
                funcionario_nome=funcionario_nome,
                competencia=competencia,
                empresa_nome=holerite.get("empresa_nome", ""),
                dados_extras={
                    "local": local
                }
            )
            
            # Enviar por Email
            if "email" in canais:
                # OTIMIZADO: Buscar do dicionário pré-carregado
                email = contatos_map.get(funcionario_id_str, {}).get("email")
                
                if email:
                    if apenas_simular:
                        logger.info(f"  [SIMULAÇÃO] Enviaria e-mail para: {email}")
                    else:
                        resultado = self._enviar_email(
                            destinatarios=[email],
                            arquivos=arquivos,
                            contexto=contexto
                        )
                        resultado.holerite_id = holerite_id
                        resultado.funcionario_id = funcionario_id_str
                        
                        relatorio.total_envios += 1
                        if resultado.sucesso:
                            relatorio.enviados_sucesso += 1
                            # Registrar envio
                            holerite_service.registrar_envio(
                                holerite_id=holerite_id,
                                funcionario_id=funcionario_id_str,
                                canal="email",
                                destino=email,
                                sucesso=True
                            )
                        else:
                            relatorio.enviados_erro += 1
                            relatorio.erros.append({
                                "holerite_id": holerite_id,
                                "funcionario": funcionario_nome,
                                "tipo": "email",
                                "erro": resultado.mensagem
                            })
                            holerite_service.registrar_envio(
                                holerite_id=holerite_id,
                                funcionario_id=funcionario_id_str,
                                canal="email",
                                destino=email,
                                sucesso=False,
                                mensagem_erro=resultado.mensagem
                            )
                else:
                    logger.debug(f"  Sem e-mail cadastrado para: {funcionario_nome}")
            
            # Enviar por WhatsApp
            if "whatsapp" in canais:
                # OTIMIZADO: Buscar do dicionário pré-carregado
                whatsapp = contatos_map.get(funcionario_id_str, {}).get("whatsapp")
                
                if whatsapp:
                    if apenas_simular:
                        logger.info(f"  [SIMULAÇÃO] Enviaria WhatsApp para: {whatsapp}")
                    else:
                        resultado = self._enviar_whatsapp(
                            telefone=whatsapp,
                            arquivos=arquivos,
                            contexto=contexto
                        )
                        resultado.holerite_id = holerite_id
                        resultado.funcionario_id = funcionario_id_str
                        
                        relatorio.total_envios += 1
                        if resultado.sucesso:
                            relatorio.enviados_sucesso += 1
                            holerite_service.registrar_envio(
                                holerite_id=holerite_id,
                                funcionario_id=funcionario_id_str,
                                canal="whatsapp",
                                destino=whatsapp,
                                sucesso=True
                            )
                        else:
                            relatorio.enviados_erro += 1
                            relatorio.erros.append({
                                "holerite_id": holerite_id,
                                "funcionario": funcionario_nome,
                                "tipo": "whatsapp",
                                "erro": resultado.mensagem
                            })
                            holerite_service.registrar_envio(
                                holerite_id=holerite_id,
                                funcionario_id=funcionario_id_str,
                                canal="whatsapp",
                                destino=whatsapp,
                                sucesso=False,
                                mensagem_erro=resultado.mensagem
                            )
                else:
                    logger.debug(f"  Sem WhatsApp cadastrado para: {funcionario_nome}")
        
        relatorio.fim = datetime.now(timezone.utc)
        
        # Log resumo
        logger.info(f"\n=== RESUMO ENVIO VIA MONGODB ===")
        logger.info(f"Total holerites: {relatorio.total_holerites}")
        logger.info(f"Total envios: {relatorio.total_envios}")
        logger.info(f"Sucesso: {relatorio.enviados_sucesso}")
        logger.info(f"Erros: {relatorio.enviados_erro}")
        logger.info(f"Duração: {relatorio.duracao_segundos():.1f}s")
        
        return relatorio
    
    def obter_estatisticas_competencia(self, competencia: str) -> Dict[str, Any]:
        """
        Obtém estatísticas de envio para uma competência.
        
        Args:
            competencia: Competência (MM/AAAA)
        
        Returns:
            Dicionário com estatísticas
        """
        contagem = holerite_service.contar_por_status(competencia)
        
        return {
            "competencia": competencia,
            "total": sum(contagem.values()),
            "por_status": contagem,
            "pendentes": contagem.get(StatusHoleriteEnum.PENDENTE.value, 0) + 
                         contagem.get(StatusHoleriteEnum.PROCESSADO.value, 0),
            "enviados": contagem.get(StatusHoleriteEnum.ENVIADO.value, 0),
            "erros": contagem.get(StatusHoleriteEnum.ERRO.value, 0)
        }


# Instância singleton
envio_holerite_orquestrador = EnvioHoleriteOrquestrador()
