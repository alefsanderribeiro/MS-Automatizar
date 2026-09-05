"""
Orquestrador de Envio de Folhas de Ponto
Responsabilidades:
- Coordenar todo o fluxo de envio
- Ler planilha de contatos
- Enviar por Email, WhatsApp individual e grupo
- Registrar todos os envios no MongoDB
- Retry automático
- Gerar relatórios
"""

import os
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timezone
from dataclasses import dataclass, field
from src.utils.retry_utils import obter_config_retry
from src.models.envio_folha_ponto_models import TipoEnvioEnum, StatusEnvioEnum
from src.models.template_mensagem_models import TipoTemplateEnum
from src.services.planilha_contatos_service import planilha_contatos_service
from src.services.envio_folha_ponto_service import envio_folha_ponto_service
from src.services.template_mensagem_service import template_mensagem_service
from src.services.grupo_whatsapp_service import grupo_whatsapp_service
from src.utils.logger_config_v2 import get_logger

# Logger do módulo
logger = get_logger("folha_ponto")

from src.services.zoho_mail_service import zoho_mail_service
from src.services.whatsapp_service import whatsapp_service
from src.services.empresa_service import empresa_service
from src.models.grupo_whatsapp_models import GrupoWhatsAppMongoDB

# Nomes dos meses em português
MESES_EXTENSO = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}


@dataclass
class ResultadoEnvio:
    """Resultado de um envio individual"""
    tipo: TipoEnvioEnum
    sucesso: bool
    destinatario: str
    arquivos: List[str] = field(default_factory=list)
    mensagem: str = ""
    detalhes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RelatorioEnvio:
    """Relatório consolidado de envios"""
    mes: int
    ano: int
    total_contatos: int = 0
    total_envios: int = 0
    enviados_sucesso: int = 0
    enviados_erro: int = 0
    enviados_parcial: int = 0
    por_tipo: Dict[str, Dict[str, int]] = field(default_factory=dict)
    erros: List[Dict[str, Any]] = field(default_factory=list)
    inicio: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    fim: Optional[datetime] = None
    
    def duracao_segundos(self) -> float:
        if self.fim:
            return (self.fim - self.inicio).total_seconds()
        return 0


class EnvioFolhaPontoOrquestrador:
    """
    Coordena o processo completo de envio de folhas de ponto
    
    Fluxo:
    1. Carregar planilha de contatos
    2. Para cada contato com envio ativo:
       a. Verificar existência de PDFs no diretório
       b. Renderizar template apropriado
       c. Enviar por cada canal ativo (email, whatsapp individual, grupo)
       d. Registrar envio no MongoDB
    3. Gerar relatório final
    """
    
    def __init__(self):
        """Inicializa o orquestrador"""
        self._config_retry_max_tentativas, self._config_retry_delay = obter_config_retry()
        self._callback_progresso: Optional[Callable[[str, int, int], None]] = None
        # Cache pre-processado: {empresa_nome: {grupo_normalizado: jid}}
        self._cache_grupos_por_empresa: Dict[str, Dict[str, str]] = {}
    
    def definir_callback_progresso(self, callback: Callable[[str, int, int], None]) -> None:
        """
        Define callback para atualização de progresso
        
        Args:
            callback: Função(mensagem, atual, total)
        """
        self._callback_progresso = callback
    
    def _reportar_progresso(self, mensagem: str, atual: int = 0, total: int = 0) -> None:
        """Reporta progresso se callback definido"""
        if self._callback_progresso:
            self._callback_progresso(mensagem, atual, total)
        logger.info(f"[{atual}/{total}] {mensagem}" if total > 0 else mensagem)
    
    def _montar_contexto_template(self, contato: Dict[str, Any]) -> Dict[str, Any]:
        """Monta contexto para renderização de template"""
        mes = contato.get("mes_referencia", 1)
        ano = contato.get("ano_referencia", datetime.now().year)
        
        return {
            "nome": contato.get("nome", ""),
            "mes": mes,
            "ano": ano,
            "mes_extenso": MESES_EXTENSO.get(mes, str(mes)),
            "local": contato.get("local_contrato_polo", ""),
            "empresa": contato.get("empresa", "")
        }
    
    # ==================== VERIFICAÇÕES ====================
    
    def verificar_servicos(self) -> Dict[str, bool]:
        """
        Verifica disponibilidade de todos os serviços
        
        Returns:
            Dict com status de cada serviço
        """
        self._reportar_progresso("Verificando serviços...")
        
        status = {
            "planilha": planilha_contatos_service.disponivel,
            "mongodb_envios": envio_folha_ponto_service.disponivel,
            "mongodb_templates": template_mensagem_service.disponivel,
            "mongodb_grupos": grupo_whatsapp_service.disponivel,
            "zoho_mail": zoho_mail_service.disponivel,
            "whatsapp": whatsapp_service.disponivel
        }
        
        # Verificar conexão real do WhatsApp
        if status["whatsapp"]:
            wa_status = whatsapp_service.verificar_status()
            status["whatsapp_conectado"] = wa_status.get("conectado", False)
        else:
            status["whatsapp_conectado"] = False
        
        # Verificar conexão real do Zoho
        if status["zoho_mail"]:
            zoho_status = zoho_mail_service.verificar_conexao()
            status["zoho_mail_conectado"] = zoho_status.get("token_valido", False)
            status["zoho_mail_configurado"] = zoho_status.get("configurado", False)
        else:
            status["zoho_mail_conectado"] = False
            status["zoho_mail_configurado"] = False
        
        # Log
        for servico, disponivel in status.items():
            emoji = "✓" if disponivel else "✗"
            logger.info(f"  {emoji} {servico}: {'OK' if disponivel else 'Indisponível'}")
        
        return status
    
    def sincronizar_grupos_whatsapp(self) -> Dict[str, int]:
        """
        Sincroniza grupos do WhatsApp com o cache local para TODOS os dispositivos conectados.

        Itera sobre cada dispositivo conectado (state == "logged_in") e sincroniza
        seus grupos individualmente. Isso permite que grupos com o mesmo nome em
        dispositivos diferentes sejam armazenados separadamente.

        Returns:
            Dict com contagem consolidada de grupos sincronizados
        """
        self._reportar_progresso("Sincronizando grupos WhatsApp...")

        if not whatsapp_service.disponivel:
            logger.warning("WhatsApp Service nao disponivel")
            return {"criados": 0, "atualizados": 0, "inativos": 0}

        status = whatsapp_service.verificar_status()
        if not status.get("conectado"):
            logger.warning("WhatsApp nao conectado - nao e possivel sincronizar grupos")
            return {"criados": 0, "atualizados": 0, "inativos": 0}

        # Obter lista de dispositivos conectados
        dispositivos = whatsapp_service.listar_dispositivos()

        if not dispositivos:
            logger.warning("Nenhum dispositivo encontrado para sincronizar grupos")
            return {"criados": 0, "atualizados": 0, "inativos": 0}

        # Filtrar apenas dispositivos conectados
        dispositivos_conectados = [d for d in dispositivos if d.get("state") == "logged_in"]

        if not dispositivos_conectados:
            logger.warning("Nenhum dispositivo conectado (logged_in) para sincronizar grupos")
            return {"criados": 0, "atualizados": 0, "inativos": 0}

        logger.info(f"Sincronizando grupos de {len(dispositivos_conectados)} dispositivo(s)...")

        # Resultado consolidado
        resultado_total = {"criados": 0, "atualizados": 0, "inativos": 0}

        for disp in dispositivos_conectados:
            # O "id" do dispositivo e o identificador interno (ex: "WhatsApp-Alefe")
            device_id = disp.get("id")
            device_nome = disp.get("display_name", device_id)

            if not device_id:
                logger.warning(f"Dispositivo sem ID: {disp}")
                continue

            logger.info(f"Sincronizando grupos do dispositivo: {device_nome} ({device_id})")

            # Listar grupos deste dispositivo
            grupos_api = whatsapp_service.listar_grupos(device_id)

            if grupos_api:
                # Sincronizar com o service de grupos, passando o device_id
                resultado = grupo_whatsapp_service.sincronizar_com_api(grupos_api, device_id)

                # Consolidar resultados
                resultado_total["criados"] += resultado.get("criados", 0)
                resultado_total["atualizados"] += resultado.get("atualizados", 0)
                resultado_total["inativos"] += resultado.get("inativos", 0)
            else:
                logger.info(f"Nenhum grupo encontrado no dispositivo: {device_nome}")

        logger.info(
            f"Sincronizacao total concluida: "
            f"{resultado_total['criados']} criados, "
            f"{resultado_total['atualizados']} atualizados, "
            f"{resultado_total['inativos']} inativos"
        )

        return resultado_total

    def _preprocessar_grupos_por_empresa(self, contatos: List[Dict]) -> Dict[str, Dict[str, str]]:
        """
        Pre-processa todos os grupos das empresas antes do envio.

        Reduz queries: em vez de buscar 1 grupo por contato,
        busca todos os grupos de cada empresa UMA VEZ.

        Args:
            contatos: Lista de contatos para processar

        Returns:
            Dict[empresa_name] = {grupo_normalizado: jid}
            Exemplo:
            {
                "MS Servicos": {
                    "administrativo": "123@g.us",
                    "financeiro": "456@g.us"
                },
                "Madeira Servicos": {
                    "administrativo": "789@g.us"
                }
            }
        """
        grupos_por_empresa: Dict[str, Dict[str, str]] = {}

        try:
            # 1. Extrair empresas unicas de todos os contatos
            empresas_unicas = set()
            for contato in contatos:
                empresa_nome = contato.get("empresa", "")
                if empresa_nome:
                    empresas_unicas.add(empresa_nome)

            if not empresas_unicas:
                logger.warning("Nenhuma empresa encontrada nos contatos")
                return grupos_por_empresa

            logger.info(f"Pre-processando grupos de {len(empresas_unicas)} empresa(s)")

            # 2. Para CADA empresa, buscar device e seus grupos UMA VEZ
            for empresa_nome in empresas_unicas:
                try:
                    # Buscar empresa
                    empresa = empresa_service.buscar_por_nome_ou_simplificado(empresa_nome, exato=False)

                    if not empresa or not empresa.get("whatsapp_device_id"):
                        logger.debug(f"Empresa '{empresa_nome}' sem device configurado")
                        grupos_por_empresa[empresa_nome] = {}
                        continue

                    device_jid = empresa.get("whatsapp_device_id")
                    # Obter ID interno do dispositivo pelo JID
                    device_id_interno = whatsapp_service.obter_id_dispositivo_por_jid(device_jid)

                    if not device_id_interno:
                        logger.debug(f"Nao foi possivel obter ID interno para device {device_jid}")
                        grupos_por_empresa[empresa_nome] = {}
                        continue

                    # Listar TODOS os grupos dessa empresa UMA VEZ
                    todos_grupos = grupo_whatsapp_service.listar_para_exibicao(device_id_interno)

                    # Criar mapa: grupo_normalizado -> jid (para busca rapida em memoria)
                    mapa_grupos: Dict[str, str] = {}
                    for grupo in todos_grupos:
                        nome_grupo = grupo.get("nome", "")
                        jid = grupo.get("jid", "")

                        if nome_grupo and jid:
                            # Normalizar nome para comparacao (mesmo padrao do service)
                            nome_normalizado = GrupoWhatsAppMongoDB.normalizar_texto(nome_grupo)
                            mapa_grupos[nome_normalizado] = jid

                    grupos_por_empresa[empresa_nome] = mapa_grupos
                    logger.debug(f"Pre-processados {len(mapa_grupos)} grupos para '{empresa_nome}'")

                except Exception as e:
                    logger.warning(f"Erro ao pre-processar grupos de '{empresa_nome}': {e}")
                    grupos_por_empresa[empresa_nome] = {}

            logger.info(f"Pre-processamento concluido: {len(grupos_por_empresa)} empresa(s)")
            return grupos_por_empresa

        except Exception as e:
            logger.error(f"Erro no pre-processamento de grupos: {e}")
            return {}

    # ==================== ENVIO POR CANAL ====================
    
    def _enviar_email(self, contato: Dict[str, Any]) -> ResultadoEnvio:
        """Envia folhas por e-mail"""
        emails = contato.get("emails", [])
        arquivos = contato.get("arquivos_pdf", [])
        
        if not emails:
            return ResultadoEnvio(
                tipo=TipoEnvioEnum.EMAIL,
                sucesso=False,
                destinatario="",
                mensagem="Nenhum e-mail configurado"
            )
        
        if not arquivos:
            return ResultadoEnvio(
                tipo=TipoEnvioEnum.EMAIL,
                sucesso=False,
                destinatario=", ".join(emails),
                mensagem="Nenhum arquivo PDF encontrado no diretório"
            )
        
        # Renderizar template
        contexto = self._montar_contexto_template(contato)
        template_renderizado = template_mensagem_service.renderizar_por_tipo(
            TipoTemplateEnum.EMAIL,
            contexto
        )
        
        if not template_renderizado:
            return ResultadoEnvio(
                tipo=TipoEnvioEnum.EMAIL,
                sucesso=False,
                destinatario=", ".join(emails),
                mensagem="Erro ao renderizar template de e-mail"
            )
        
        # Enviar
        resultado = zoho_mail_service.enviar_email(
            destinatarios=emails,
            assunto=template_renderizado.get("assunto", "Folha de Ponto"),
            corpo=template_renderizado.get("mensagem", ""),
            anexos=arquivos
        )
        
        return ResultadoEnvio(
            tipo=TipoEnvioEnum.EMAIL,
            sucesso=resultado.get("sucesso", False),
            destinatario=", ".join(emails),
            arquivos=[os.path.basename(f) for f in arquivos],
            mensagem=resultado.get("mensagem", ""),
            detalhes=resultado.get("detalhes", {})
        )
    
    def _enviar_whatsapp_individual(self, contato: Dict[str, Any]) -> ResultadoEnvio:
        """Envia folhas por WhatsApp individual"""
        telefones = contato.get("telefones", [])
        arquivos = contato.get("arquivos_pdf", [])
        
        if not telefones:
            return ResultadoEnvio(
                tipo=TipoEnvioEnum.WHATSAPP_INDIVIDUAL,
                sucesso=False,
                destinatario="",
                mensagem="Nenhum telefone configurado"
            )
        
        if not arquivos:
            return ResultadoEnvio(
                tipo=TipoEnvioEnum.WHATSAPP_INDIVIDUAL,
                sucesso=False,
                destinatario=", ".join(telefones),
                mensagem="Nenhum arquivo PDF encontrado no diretório"
            )
        
        # Renderizar template
        contexto = self._montar_contexto_template(contato)
        template_renderizado = template_mensagem_service.renderizar_por_tipo(
            TipoTemplateEnum.WHATSAPP_INDIVIDUAL,
            contexto
        )
        
        mensagem = template_renderizado.get("mensagem", "") if template_renderizado else ""
        
        # Enviar para cada telefone
        resultados_por_telefone = []

        # Obter empresa do contato para roteamento
        empresa_nome = contato.get("empresa", "")
        device_id = None

        if empresa_nome and empresa_service and empresa_service.disponivel:
            try:
                # Buscar empresa no MongoDB (tenta nome_simplificado primeiro, depois nome completo)
                empresa = empresa_service.buscar_por_nome_ou_simplificado(empresa_nome, exato=False)

                if empresa and empresa.get("whatsapp_device_id"):
                    device_id = empresa.get("whatsapp_device_id")
                    logger.info(f"📱 Usando device {device_id} para empresa {empresa_nome}")
                else:
                    logger.info(f"📱 Empresa {empresa_nome} sem device configurado, usando padrão")
            except Exception as e:
                logger.warning(f"Erro ao buscar empresa {empresa_nome}: {e}")
                logger.info(f"📱 Empresa {empresa_nome} sem device configurado, usando padrão")
        elif empresa_nome:
            logger.info(f"📱 Empresa {empresa_nome} sem device configurado, usando padrão")

        for telefone in telefones:
            resultado = whatsapp_service.enviar_multiplos_arquivos(
                destinatario=telefone,
                arquivos=arquivos,
                mensagem=mensagem,
                is_grupo=False,
                device_id=device_id
            )
            resultados_por_telefone.append({
                "telefone": telefone,
                "sucesso": resultado.get("sucesso", False),
                "parcial": resultado.get("parcial", False),
                "mensagem": resultado.get("mensagem", "")
            })
        
        # Consolidar resultado
        total = len(telefones)
        sucesso = sum(1 for r in resultados_por_telefone if r["sucesso"])
        
        return ResultadoEnvio(
            tipo=TipoEnvioEnum.WHATSAPP_INDIVIDUAL,
            sucesso=sucesso == total,
            destinatario=", ".join(telefones),
            arquivos=[os.path.basename(f) for f in arquivos],
            mensagem=f"{sucesso}/{total} destinatários receberam",
            detalhes={"resultados": resultados_por_telefone}
        )
    
    def _enviar_whatsapp_grupo(self, contato: Dict[str, Any]) -> ResultadoEnvio:
        """Envia folhas por WhatsApp para grupos (usando cache pre-processado)"""
        grupos = contato.get("grupos_whatsapp", [])
        arquivos = contato.get("arquivos_pdf", [])
        empresa_nome = contato.get("empresa", "")

        if not grupos:
            return ResultadoEnvio(
                tipo=TipoEnvioEnum.WHATSAPP_GRUPO,
                sucesso=False,
                destinatario="",
                mensagem="Nenhum grupo configurado"
            )

        if not arquivos:
            return ResultadoEnvio(
                tipo=TipoEnvioEnum.WHATSAPP_GRUPO,
                sucesso=False,
                destinatario=", ".join(grupos),
                mensagem="Nenhum arquivo PDF encontrado no diretório"
            )

        # Renderizar template
        contexto = self._montar_contexto_template(contato)
        template_renderizado = template_mensagem_service.renderizar_por_tipo(
            TipoTemplateEnum.WHATSAPP_GRUPO,
            contexto
        )

        mensagem = template_renderizado.get("mensagem", "") if template_renderizado else ""

        # Buscar device da empresa (necessario para envio)
        device_jid = None  # JID do dispositivo (ex: 5569XXXXXXXX@s.whatsapp.net)
        device_id_interno = None  # ID interno do dispositivo (ex: WhatsApp-Alefe)

        if empresa_nome and empresa_service and empresa_service.disponivel:
            try:
                empresa = empresa_service.buscar_por_nome_ou_simplificado(empresa_nome, exato=False)

                if empresa and empresa.get("whatsapp_device_id"):
                    device_jid = empresa.get("whatsapp_device_id")
                    # Obter o ID interno do dispositivo pelo JID
                    device_id_interno = whatsapp_service.obter_id_dispositivo_por_jid(device_jid)

                    if device_id_interno:
                        logger.debug(f"Usando device {device_id_interno} (JID: {device_jid}) para empresa {empresa_nome}")
                    else:
                        logger.warning(f"Nao foi possivel obter ID interno do dispositivo {device_jid}")
                else:
                    logger.debug(f"Empresa {empresa_nome} sem device configurado")
            except Exception as e:
                logger.warning(f"Erro ao buscar empresa {empresa_nome}: {e}")

        # Se nao temos device_id_interno, nao podemos enviar para grupos
        if not device_id_interno:
            return ResultadoEnvio(
                tipo=TipoEnvioEnum.WHATSAPP_GRUPO,
                sucesso=False,
                destinatario=", ".join(grupos),
                mensagem="Empresa sem dispositivo WhatsApp configurado ou dispositivo nao encontrado"
            )

        # OTIMIZACAO: Usar cache pre-processado em vez de buscar cada grupo individualmente
        mapa_grupos = self._cache_grupos_por_empresa.get(empresa_nome, {})

        # Enviar para cada grupo
        resultados_por_grupo = []

        for nome_grupo in grupos:
            # Busca em memoria (MUITO rapido!) em vez de query ao banco
            nome_normalizado = GrupoWhatsAppMongoDB.normalizar_texto(nome_grupo)
            jid = mapa_grupos.get(nome_normalizado)

            # Busca parcial no cache se busca exata nao encontrou
            if not jid:
                for nome_cache, jid_cache in mapa_grupos.items():
                    if nome_normalizado in nome_cache or nome_cache in nome_normalizado:
                        jid = jid_cache
                        logger.debug(f"Match parcial (cache): '{nome_grupo}' -> JID encontrado")
                        break

            # Fallback: buscar individualmente se nao encontrou no cache
            if not jid:
                logger.debug(f"Grupo '{nome_grupo}' nao encontrado no cache, buscando no banco...")
                jid = grupo_whatsapp_service.obter_jid_por_nome(nome_grupo, device_id_interno)

            if not jid:
                resultados_por_grupo.append({
                    "grupo": nome_grupo,
                    "sucesso": False,
                    "mensagem": f"Grupo nao encontrado: {nome_grupo} (device: {device_id_interno})"
                })
                continue

            resultado = whatsapp_service.enviar_multiplos_arquivos(
                destinatario=jid,
                arquivos=arquivos,
                mensagem=mensagem,
                is_grupo=True,
                device_id=device_jid  # Usar o JID do dispositivo para envio
            )

            resultados_por_grupo.append({
                "grupo": nome_grupo,
                "jid": jid,
                "sucesso": resultado.get("sucesso", False),
                "parcial": resultado.get("parcial", False),
                "mensagem": resultado.get("mensagem", "")
            })
        
        # Consolidar resultado
        total = len(grupos)
        sucesso = sum(1 for r in resultados_por_grupo if r["sucesso"])
        
        return ResultadoEnvio(
            tipo=TipoEnvioEnum.WHATSAPP_GRUPO,
            sucesso=sucesso == total,
            destinatario=", ".join(grupos),
            arquivos=[os.path.basename(f) for f in arquivos],
            mensagem=f"{sucesso}/{total} grupos receberam",
            detalhes={"resultados": resultados_por_grupo}
        )
    
    # ==================== REGISTRO ====================
    
    def _registrar_envio(self, contato: Dict[str, Any], resultado: ResultadoEnvio) -> Optional[str]:
        """Registra envio no MongoDB"""
        try:
            # Determinar status
            if resultado.sucesso:
                # Verificar se é parcial (dentro dos detalhes dos resultados)
                detalhes = resultado.detalhes or {}
                resultados = detalhes.get("resultados", [])
                
                # É parcial se algum resultado individual tem "parcial": True
                eh_parcial = False
                if isinstance(resultados, list):
                    eh_parcial = any(r.get("parcial", False) for r in resultados if isinstance(r, dict))
                elif isinstance(detalhes, dict):
                    eh_parcial = detalhes.get("parcial", False)
                
                status = StatusEnvioEnum.PARCIAL if eh_parcial else StatusEnvioEnum.ENVIADO
            else:
                status = StatusEnvioEnum.ERRO
            
            dados = {
                "tipo_envio": resultado.tipo.value,
                "status": status.value,
                "destinatarios": [resultado.destinatario] if resultado.destinatario else [],
                "local_contrato_polo": contato.get("local_contrato_polo", ""),
                "diretorio_completo": contato.get("diretorio_completo", ""),
                "arquivos_enviados": resultado.arquivos if resultado.sucesso else [],
                "arquivos_com_erro": [] if resultado.sucesso else resultado.arquivos,
                "mes_referencia": contato.get("mes_referencia"),
                "ano_referencia": contato.get("ano_referencia"),
                "tentativas": 1,
                "max_tentativas": self._config_retry_max_tentativas,
                "erro_detalhes": None if resultado.sucesso else resultado.mensagem,
                "data_envio_sucesso": datetime.now(timezone.utc) if resultado.sucesso else None
            }
            
            return envio_folha_ponto_service.registrar_envio(dados)
        
        except Exception as e:
            logger.error(f"Erro ao registrar envio: {e}")
            return None
    
    # ==================== EXECUÇÃO PRINCIPAL ====================
    
    def executar(self, 
                 mes: int, 
                 ano: int,
                 tipos_envio: List[TipoEnvioEnum] = None,
                 contatos_ids: List[str] = None,
                 dry_run: bool = False) -> RelatorioEnvio:
        """
        Executa o processo completo de envio
        
        Args:
            mes: Mês de referência
            ano: Ano de referência
            tipos_envio: Tipos de envio a realizar (None = todos)
            contatos_ids: IDs de contatos específicos (None = todos)
            dry_run: Se True, apenas simula sem enviar
        
        Returns:
            Relatório com resultado dos envios
        """
        relatorio = RelatorioEnvio(mes=mes, ano=ano)
        
        # Correlation ID para rastreamento do fluxo de envio
        with logger.correlation("envio_folha_ponto") as corr_id:
            logger.info(f"Iniciando envio de folhas de ponto {mes:02d}/{ano}", correlation_id=corr_id)
        
        # Tipos de envio
        tipos = tipos_envio or [
            TipoEnvioEnum.EMAIL,
            TipoEnvioEnum.WHATSAPP_INDIVIDUAL,
            TipoEnvioEnum.WHATSAPP_GRUPO
        ]
        
        relatorio.por_tipo = {tipo.value: {"sucesso": 0, "erro": 0, "parcial": 0} for tipo in tipos}
        
        self._reportar_progresso(f"Iniciando envio de folhas de ponto {mes:02d}/{ano}")
        
        if dry_run:
            self._reportar_progresso("⚠ Modo DRY RUN - nenhum envio será realizado")
        
        # Verificar serviços
        status_servicos = self.verificar_servicos()
        
        # Carregar planilha
        if not planilha_contatos_service.carregar():
            logger.error("Não foi possível carregar a planilha de contatos")
            relatorio.erros.append({"erro": "Falha ao carregar planilha"})
            relatorio.fim = datetime.now(timezone.utc)
            return relatorio

        # Iterar contatos (carregar ANTES do pre-processamento)
        contatos = list(planilha_contatos_service.iterar_contatos(mes, ano))

        # Filtrar por IDs se especificado
        if contatos_ids:
            contatos = [c for c in contatos if str(c.get("id")) in contatos_ids]

        # Sincronizar e PRE-PROCESSAR grupos se WhatsApp grupo esta nos tipos
        if TipoEnvioEnum.WHATSAPP_GRUPO in tipos and status_servicos.get("whatsapp_conectado"):
            self.sincronizar_grupos_whatsapp()
            # PRE-PROCESSAR grupos (UMA VEZ antes do loop)
            self._cache_grupos_por_empresa = self._preprocessar_grupos_por_empresa(contatos)
        
        relatorio.total_contatos = len(contatos)
        
        for idx, contato in enumerate(contatos, 1):
            nome = contato.get("nome", "Desconhecido")
            local = contato.get("local_contrato_polo", "")
            
            self._reportar_progresso(f"Processando: {nome} - {local}", idx, len(contatos))
            
            # Verificar se há arquivos
            if not contato.get("arquivos_pdf"):
                logger.warning(f"  ⚠ Sem arquivos PDF em: {contato.get('diretorio_completo')}")
                continue
            
            # Enviar por cada canal ativo
            
            # Email
            if TipoEnvioEnum.EMAIL in tipos and contato.get("enviar_email"):
                relatorio.total_envios += 1
                
                if dry_run:
                    logger.info(f"  [DRY RUN] Enviaria e-mail para: {contato.get('emails')}")
                    relatorio.por_tipo[TipoEnvioEnum.EMAIL.value]["sucesso"] += 1
                else:
                    if status_servicos.get("zoho_mail_conectado"):
                        resultado = self._enviar_email(contato)
                        self._registrar_envio(contato, resultado)
                        
                        if resultado.sucesso:
                            relatorio.enviados_sucesso += 1
                            relatorio.por_tipo[TipoEnvioEnum.EMAIL.value]["sucesso"] += 1
                        else:
                            relatorio.enviados_erro += 1
                            relatorio.por_tipo[TipoEnvioEnum.EMAIL.value]["erro"] += 1
                            relatorio.erros.append({
                                "contato": nome,
                                "tipo": "email",
                                "erro": resultado.mensagem
                            })
                    else:
                        logger.warning("  ⚠ Zoho Mail não conectado - pulando e-mail")
            
            # WhatsApp Individual
            if TipoEnvioEnum.WHATSAPP_INDIVIDUAL in tipos and contato.get("enviar_whatsapp"):
                relatorio.total_envios += 1
                
                if dry_run:
                    logger.info(f"  [DRY RUN] Enviaria WhatsApp para: {contato.get('telefones')}")
                    relatorio.por_tipo[TipoEnvioEnum.WHATSAPP_INDIVIDUAL.value]["sucesso"] += 1
                else:
                    if status_servicos.get("whatsapp_conectado"):
                        resultado = self._enviar_whatsapp_individual(contato)
                        self._registrar_envio(contato, resultado)
                        
                        if resultado.sucesso:
                            relatorio.enviados_sucesso += 1
                            relatorio.por_tipo[TipoEnvioEnum.WHATSAPP_INDIVIDUAL.value]["sucesso"] += 1
                            # Delays já implementados dentro de whatsapp_service.enviar_multiplos_arquivos
                        else:
                            relatorio.enviados_erro += 1
                            relatorio.por_tipo[TipoEnvioEnum.WHATSAPP_INDIVIDUAL.value]["erro"] += 1
                            relatorio.erros.append({
                                "contato": nome,
                                "tipo": "whatsapp_individual",
                                "erro": resultado.mensagem
                            })
                    else:
                        logger.warning("  ⚠ WhatsApp não conectado - pulando individual")
            
            # WhatsApp Grupo
            if TipoEnvioEnum.WHATSAPP_GRUPO in tipos and contato.get("enviar_grupo_whatsapp"):
                relatorio.total_envios += 1
                
                if dry_run:
                    logger.info(f"  [DRY RUN] Enviaria para grupos: {contato.get('grupos_whatsapp')}")
                    relatorio.por_tipo[TipoEnvioEnum.WHATSAPP_GRUPO.value]["sucesso"] += 1
                else:
                    if status_servicos.get("whatsapp_conectado"):
                        resultado = self._enviar_whatsapp_grupo(contato)
                        self._registrar_envio(contato, resultado)
                        
                        if resultado.sucesso:
                            relatorio.enviados_sucesso += 1
                            relatorio.por_tipo[TipoEnvioEnum.WHATSAPP_GRUPO.value]["sucesso"] += 1
                            # Delays já implementados dentro de whatsapp_service.enviar_multiplos_arquivos
                        else:
                            relatorio.enviados_erro += 1
                            relatorio.por_tipo[TipoEnvioEnum.WHATSAPP_GRUPO.value]["erro"] += 1
                            relatorio.erros.append({
                                "contato": nome,
                                "tipo": "whatsapp_grupo",
                                "erro": resultado.mensagem
                            })
                    else:
                        logger.warning("  ⚠ WhatsApp não conectado - pulando grupo")
        
        relatorio.fim = datetime.now(timezone.utc)
        
        # Log final
        self._reportar_progresso(
            f"✓ Envio concluído em {relatorio.duracao_segundos():.1f}s: "
            f"{relatorio.enviados_sucesso} sucesso, "
            f"{relatorio.enviados_erro} erro"
        )
        
        return relatorio
    
    def executar_retry(self, max_tentativas: int | None = None) -> RelatorioEnvio:
        """
        Reexecuta envios com erro
        
        Args:
            max_tentativas: Máximo de tentativas (usa config se None)
        
        Returns:
            Relatório dos retries
        """
        max_tent = max_tentativas or self._config_retry_max_tentativas
        
        self._reportar_progresso("Buscando envios pendentes de retry...")
        
        pendentes = envio_folha_ponto_service.buscar_pendentes_retry(max_tent)
        
        if not pendentes:
            logger.info("Nenhum envio pendente de retry")
            return RelatorioEnvio(mes=0, ano=0)
        
        self._reportar_progresso(f"Encontrados {len(pendentes)} envios para retry")
        
        # TODO: Implementar lógica de retry baseada nos registros do MongoDB
        # Por enquanto, apenas log
        for envio in pendentes:
            logger.info(
                f"  Pendente: {envio.get('tipo_envio')} - {envio.get('local_contrato_polo')} "
                f"(tentativa {envio.get('tentativas')}/{max_tent})"
            )
        
        return RelatorioEnvio(mes=0, ano=0, total_envios=len(pendentes))


# Instância singleton
envio_folha_ponto_orquestrador = EnvioFolhaPontoOrquestrador()
