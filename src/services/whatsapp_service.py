"""
Service para integração com WhatsApp via go-whatsapp-web-multidevice
Responsabilidades:
- Envio de arquivos para contatos e grupos
- Sincronização de grupos
- Verificação de status da conexão
- Tratamento de erros e retry

API Reference: https://github.com/aldinokemal/go-whatsapp-web-multidevice
"""

import os
import time
import base64
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import dotenv

from src.utils.dotenv_path import caminho_dotenv
from src.utils.retry_utils import retry_com_log
from src.utils.telefone_utils import normalizar_telefone, validar_telefone
from src.utils.logger_config_v2 import get_logger


# Tentativa de importação de requests
try:
    import requests
    REQUESTS_DISPONIVEL = True
except ImportError:
    REQUESTS_DISPONIVEL = False
    logger.warning("Requests não instalado - WhatsAppService não funcionará")


class WhatsAppService:
    """
    Integração com WhatsApp via go-whatsapp-web-multidevice (Docker)
    
    Requer as seguintes variáveis no .env:
    - WHATSAPP_API_URL: URL base da API (ex: http://localhost:3000)
    - WHATSAPP_API_KEY: Chave de API (se configurada)
    
    O container Docker deve estar rodando e conectado ao WhatsApp Web.
    """
    
    # Endpoints da API
    ENDPOINT_STATUS = "/app/status"
    ENDPOINT_GROUPS = "/user/my/groups"
    ENDPOINT_SEND_FILE = "/send/file"
    ENDPOINT_SEND_MESSAGE = "/send/message"
    # v8: /app/qr retornava base64 em data.qr_code
    # v9: /app/qr foi REMOVIDO — o QR agora vem de /app/login (results.qr_link, URL da imagem)
    ENDPOINT_QR_CODE_LEGACY = "/app/qr"
    ENDPOINT_LOGIN = "/app/login"
    
    # Delays para evitar rate limiting (em segundos)
    DELAY_ENTRE_ARQUIVOS = 1.5  # Delay entre cada arquivo
    DELAY_APOS_MENSAGEM = 1.0   # Delay após enviar mensagem antes dos arquivos
    DELAY_APOS_ERRO = 3.0       # Delay adicional após erro
    
    def __init__(self):

        self.logger = get_logger("whatsapp")
        """Inicializa configurações do WhatsApp"""
        self._carregar_configuracoes()
    
    def _carregar_configuracoes(self) -> None:
        """Carrega configurações do .env"""
        import os
        env_path = caminho_dotenv()
        dotenv.load_dotenv(env_path, override=True)
        
        self.api_url = os.getenv("WHATSAPP_API_URL") or "http://localhost:3000"
        self.api_key = os.getenv("WHATSAPP_API_KEY")
        # Basic Auth (formato usuario:senha) — usado pelo go-whatsapp-web-multidevice
        # desde a v8 e OBRIGATÓRIO na v9 (APP_BASIC_AUTH). O service envia o header
        # Authorization: Basic base64(user:pass) quando configurado.
        self.basic_auth = os.getenv("WHATSAPP_BASIC_AUTH") or ""

        # Remover trailing slash se houver
        self.api_url = self.api_url.rstrip("/")
        
        self._disponivel = REQUESTS_DISPONIVEL
        
        if self._disponivel:
            auth_desc = "Basic Auth" if self.basic_auth else ("Bearer" if self.api_key else "sem autenticação")
            logger.debug(f"✓ WhatsApp API configurada: {self.api_url} (auth: {auth_desc})")
    
    @property
    def disponivel(self) -> bool:
        return self._disponivel
    
    def _get_headers(self, device_id: Optional[str] = None) -> Dict[str, str]:
        """
        Retorna headers para requisições

        Args:
            device_id: Device ID opcional (formato: 5569XXXXXXXX@s.whatsapp.net)
                      Se fornecido, adiciona header X-Device-Id

        Returns:
            Dict com headers HTTP
        """
        headers = {
            "Accept": "application/json"
        }

        # Prioridade de autenticação (v9 e v8):
        # 1. WHATSAPP_BASIC_AUTH (user:secret) -> Authorization: Basic base64(user:pass)
        #    - Go-whatsapp-web-multidevice v8+ e v9 usam HTTP Basic Auth (APP_BASIC_AUTH),
        #      que o Fiber valida no header Authorization com esquema 'Basic'.
        # 2. WHATSAPP_API_KEY no formato 'user:secret' -> tratado como Basic Auth (fallback)
        # 3. WHATSAPP_API_KEY como token simples  -> Bearer (comportamento legado v7)
        basic_creds = self.basic_auth
        if not basic_creds and self.api_key and ":" in self.api_key:
            basic_creds = self.api_key

        if basic_creds:
            token = base64.b64encode(basic_creds.encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        elif self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        if device_id:
            headers["X-Device-Id"] = device_id
            logger.debug(f"Header X-Device-Id adicionado: {device_id}")

        return headers
    
    # ==================== STATUS E CONEXÃO ====================
    
    def verificar_status(self) -> Dict[str, Any]:
        """
        Verifica status da conexão com WhatsApp.

        Com múltiplos dispositivos, verifica se há pelo menos um dispositivo conectado.
        Retorna o status do primeiro dispositivo conectado.

        Returns:
            Dict com status: {"conectado": bool, "numero": str, "mensagem": str}
        """
        if not self._disponivel:
            return {
                "conectado": False,
                "numero": None,
                "mensagem": "Requests nao disponivel"
            }

        try:
            # Obter lista de dispositivos para verificar se há algum conectado
            dispositivos = self.listar_dispositivos()

            if not dispositivos:
                return {
                    "conectado": False,
                    "numero": None,
                    "mensagem": "Nenhum dispositivo encontrado"
                }

            # Procurar o primeiro dispositivo conectado
            for dispositivo in dispositivos:
                state = dispositivo.get("state", "unknown")

                if state == "logged_in":
                    jid = dispositivo.get("jid", "")
                    numero = jid.split("@")[0] if "@" in jid else jid
                    nome = dispositivo.get("display_name", "Desconhecido")

                    logger.info(f"WhatsApp conectado: {numero} ({nome})")

                    return {
                        "conectado": True,
                        "numero": numero,
                        "mensagem": f"Conectado ({nome})"
                    }

            # Se chegou aqui, nenhum dispositivo está conectado
            return {
                "conectado": False,
                "numero": None,
                "mensagem": "Nenhum dispositivo conectado - escanear QR Code"
            }

        except requests.exceptions.ConnectionError:
            return {
                "conectado": False,
                "numero": None,
                "mensagem": f"Nao foi possivel conectar a API em {self.api_url}. Container Docker rodando?"
            }
        except Exception as e:
            logger.error(f"Erro ao verificar status WhatsApp: {e}")
            return {
                "conectado": False,
                "numero": None,
                "mensagem": f"Erro: {str(e)}"
            }
    
    def obter_qr_code(self) -> Optional[str]:
        """
        Obtém QR Code para conexão.

        Compatível com v8 e v9:
        - v9: /app/qr foi REMOVIDO. Usa /app/login que retorna results.qr_link (URL para a
          imagem PNG do QR). A URL é retornada para o chamador abrir/exibir.
        - v8: /app/qr retornava data.qr_code (base64). Tenta em segundo lugar como fallback.

        Returns:
            Para v9: URL do QR (str) ou None se erro.
            Para v8: base64 do QR (str) ou None se erro.
        """
        if not self._disponivel:
            return None

        # Tentativa 1: v9 — /app/login (results.qr_link)
        try:
            response = requests.get(
                f"{self.api_url}{self.ENDPOINT_LOGIN}",
                headers=self._get_headers(),
                timeout=30
            )
            if response.status_code == 200:
                dados = response.json()
                results = dados.get("results") or {}
                qr_link = results.get("qr_link")
                if qr_link:
                    logger.debug("QR obtido via /app/login (v9)")
                    return qr_link
                # Pode haver qr_code base64 em alguns formatos
                if results.get("qr_code"):
                    return results.get("qr_code")
        except Exception as e:
            logger.debug(f"Falha ao obter QR via /app/login: {e}")

        # Tentativa 2: v8 — /app/qr (data.qr_code base64)
        try:
            response = requests.get(
                f"{self.api_url}{self.ENDPOINT_QR_CODE_LEGACY}",
                headers=self._get_headers(),
                timeout=30
            )
            if response.status_code == 200:
                dados = response.json()
                qr = dados.get("data", {}).get("qr_code") or (dados.get("results") or {}).get("qr_code")
                if qr:
                    logger.debug("QR obtido via /app/qr (v8 legacy)")
                    return qr
        except Exception as e:
            logger.debug(f"Falha ao obter QR via /app/qr: {e}")

        return None
    
    # ==================== GRUPOS ====================
    
    def listar_grupos(self, device_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lista todos os grupos do WhatsApp conectado

        Args:
            device_id: Device ID opcional (ex: WhatsApp-Alefe). Se não fornecido, usa o primeiro conectado

        Returns:
            Lista de grupos com JID, nome, etc.
        """
        if not self._disponivel:
            return []

        try:
            # Se device_id não fornecido, usar o primeiro dispositivo conectado
            device_id_header = device_id
            if not device_id_header:
                dispositivos = self.listar_dispositivos()
                for disp in dispositivos:
                    if disp.get("state") == "logged_in":
                        device_id_header = disp.get("id")
                        logger.debug(f"Usando dispositivo padrão para listar grupos: {device_id_header}")
                        break

            if not device_id_header:
                logger.warning("Nenhum dispositivo conectado para listar grupos")
                return []

            response = requests.get(
                f"{self.api_url}{self.ENDPOINT_GROUPS}",
                headers=self._get_headers(device_id_header),
                timeout=30
            )

            if response.status_code == 200:
                dados = response.json()

                # API v8+ retorna {"results": {"data": [...]}}
                # API antiga retorna {"data": [...]}
                results = dados.get("results") or dados
                grupos = results.get("data", []) if isinstance(results, dict) else []

                logger.info(f"✓ {len(grupos)} grupos obtidos da API")
                return grupos
            else:
                logger.error(f"Erro ao listar grupos: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            logger.error(f"Erro ao listar grupos: {e}")
            return []
    
    # ==================== ENVIO ====================
    
    @retry_com_log()
    def enviar_arquivo(self,
                       destinatario: str,
                       arquivo_path: str,
                       mensagem: str = "",
                       is_grupo: bool = False,
                       device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Envia arquivo para contato ou grupo

        Args:
            destinatario: Número de telefone ou JID do grupo
            arquivo_path: Caminho absoluto do arquivo
            mensagem: Legenda/mensagem junto com o arquivo
            is_grupo: Se True, destinatario é tratado como JID de grupo
            device_id: Device ID opcional (ex: 5569XXXXXXXX@s.whatsapp.net)

        Returns:
            Dict com resultado: {"sucesso": bool, "mensagem": str, "detalhes": ...}
        """
        with self.logger.system_logger.correlation("enviar_whatsapp_arquivo") as corr_id:
            self.logger.info("Iniciando envio de arquivo WhatsApp", correlation_id=corr_id)
            if not self._disponivel:
                return {
                    "sucesso": False,
                    "mensagem": "WhatsApp API não disponível",
                    "detalhes": None
                }
        
            # Verificar conexão
            status = self.verificar_status()
            if not status.get("conectado"):
                return {
                    "sucesso": False,
                    "mensagem": "WhatsApp não conectado",
                    "detalhes": status
                }
        
            # Validar arquivo
            if not os.path.exists(arquivo_path):
                return {
                    "sucesso": False,
                    "mensagem": f"Arquivo não encontrado: {arquivo_path}",
                    "detalhes": None
                }
        
            try:
                # Preparar destinatário
                if is_grupo:
                    # Já deve ser um JID de grupo (ex: 123456@g.us)
                    to = destinatario if "@g.us" in destinatario else f"{destinatario}@g.us"
                else:
                    # Normalizar telefone
                    to = normalizar_telefone(destinatario)
                    if not to:
                        return {
                            "sucesso": False,
                            "mensagem": f"Telefone invalido: {destinatario}",
                            "detalhes": None
                        }

                # Preparar multipart form data
                nome_arquivo = os.path.basename(arquivo_path)

                # Se device_id foi fornecido, obter seu ID interno (não o JID)
                device_id_header = None
                device_id_param = None

                if device_id:
                    device_id_header = self.obter_id_dispositivo_por_jid(device_id)
                    if device_id_header:
                        logger.info(f"Usando device header: {device_id_header} ({device_id})")
                    else:
                        # Se não encontrou o ID, usar o JID como fallback
                        device_id_param = device_id
                        logger.info(f"Usando device como query param: {device_id}")

                with open(arquivo_path, "rb") as f:
                    files = {
                        "file": (nome_arquivo, f, "application/pdf")
                    }

                    data = {
                        "phone": to,
                        "caption": mensagem or ""
                    }

                    # Montar URL com query parameters se necessário
                    url = f"{self.api_url}{self.ENDPOINT_SEND_FILE}"
                    if device_id_param:
                        url = f"{url}?device_id={device_id_param}"

                    response = requests.post(
                        url,
                        headers=self._get_headers(device_id_header),
                        data=data,
                        files=files,
                        timeout=120
                    )
            
                if response.status_code == 200:
                    dados = response.json()
                
                    logger.info(f"✓ Arquivo enviado para {to}: {nome_arquivo}")
                
                    # API v8+ usa "results", API antiga usa "data"
                    results = dados.get("results") or dados.get("data", {})
                
                    return {
                        "sucesso": True,
                        "mensagem": "Arquivo enviado com sucesso",
                        "detalhes": {
                            "destinatario": to,
                            "arquivo": nome_arquivo,
                            "message_id": results.get("message_id") if isinstance(results, dict) else None
                        }
                    }
                else:
                    erro_msg = f"Erro ao enviar arquivo: {response.status_code} - {response.text}"
                    logger.error(erro_msg)
                    return {
                        "sucesso": False,
                        "mensagem": erro_msg,
                        "detalhes": response.json() if response.text else None
                    }
        
            except Exception as e:
                erro_msg = f"Erro ao enviar arquivo: {e}"
                logger.error(erro_msg)
                return {
                    "sucesso": False,
                    "mensagem": erro_msg,
                    "detalhes": None
                }

            self.logger.info("Envio de arquivo WhatsApp concluído", correlation_id=corr_id)
    
    @retry_com_log()
    def enviar_texto(self,
                     destinatario: str,
                     mensagem: str,
                     is_grupo: bool = False,
                     device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Envia mensagem de texto para contato ou grupo

        Args:
            destinatario: Número de telefone ou JID do grupo
            mensagem: Texto da mensagem
            is_grupo: Se True, destinatario é tratado como JID de grupo
            device_id: Device ID opcional (ex: 5569XXXXXXXX@s.whatsapp.net)

        Returns:
            Dict com resultado: {"sucesso": bool, "mensagem": str, "detalhes": ...}
        """
        with self.logger.system_logger.correlation("enviar_whatsapp_texto") as corr_id:
            self.logger.info("Iniciando envio de texto WhatsApp", correlation_id=corr_id)
            if not self._disponivel:
                return {
                    "sucesso": False,
                    "mensagem": "WhatsApp API não disponível",
                    "detalhes": None
                }
        
            # Verificar conexão
            status = self.verificar_status()
            if not status.get("conectado"):
                return {
                    "sucesso": False,
                    "mensagem": "WhatsApp não conectado",
                    "detalhes": status
                }
        
            try:
                # Preparar destinatário
                if is_grupo:
                    to = destinatario if "@g.us" in destinatario else f"{destinatario}@g.us"
                else:
                    to = normalizar_telefone(destinatario)
                    if not to:
                        return {
                            "sucesso": False,
                            "mensagem": f"Telefone invalido: {destinatario}",
                            "detalhes": None
                        }

                # Se device_id foi fornecido, obter seu ID interno (não o JID)
                device_id_header = None
                device_id_param = None

                if device_id:
                    device_id_header = self.obter_id_dispositivo_por_jid(device_id)
                    if device_id_header:
                        logger.info(f"Usando device header: {device_id_header} ({device_id})")
                    else:
                        # Se não encontrou o ID, usar o JID como fallback
                        device_id_param = device_id
                        logger.info(f"Usando device como query param: {device_id}")

                # Montar URL com query parameters se necessário
                url = f"{self.api_url}{self.ENDPOINT_SEND_MESSAGE}"
                if device_id_param:
                    url = f"{url}?device_id={device_id_param}"

                response = requests.post(
                    url,
                    headers=self._get_headers(device_id_header),
                    json={
                        "phone": to,
                        "message": mensagem
                    },
                    timeout=30
                )
            
                if response.status_code == 200:
                    dados = response.json()
                
                    logger.info(f"✓ Texto enviado para {to}")
                
                    return {
                        "sucesso": True,
                        "mensagem": "Texto enviado com sucesso",
                        "detalhes": {
                            "destinatario": to,
                            "message_id": dados.get("results", {}).get("message_id") or dados.get("data", {}).get("message_id")
                        }
                    }
                else:
                    erro_msg = f"Erro ao enviar texto: {response.status_code} - {response.text}"
                    logger.error(erro_msg)
                    return {
                        "sucesso": False,
                        "mensagem": erro_msg,
                        "detalhes": None
                    }
        
            except Exception as e:
                erro_msg = f"Erro ao enviar texto: {e}"
                logger.error(erro_msg)
                return {
                    "sucesso": False,
                    "mensagem": erro_msg,
                    "detalhes": None
                }

            self.logger.info("Envio de texto WhatsApp concluído", correlation_id=corr_id)
    
    def enviar_multiplos_arquivos(self,
                                   destinatario: str,
                                   arquivos: List[str],
                                   mensagem: str = "",
                                   is_grupo: bool = False,
                                   device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Envia múltiplos arquivos para o mesmo destinatário.

        Estratégia otimizada para evitar rate limiting:
        1. Primeiro envia a mensagem de texto (template)
        2. Aguarda um breve delay
        3. Envia os arquivos em sequência com delays menores entre eles

        Isso funciona melhor porque:
        - Mensagens de texto são muito mais leves que mídia
        - O rate limiting do WhatsApp é mais rigoroso para mídia
        - O destinatário recebe a mensagem primeiro, entendendo o contexto

        Args:
            destinatario: Número de telefone ou JID do grupo
            arquivos: Lista de caminhos de arquivos
            mensagem: Mensagem/template a ser enviada antes dos arquivos
            is_grupo: Se True, destinatario é tratado como JID de grupo
            device_id: Device ID opcional (ex: 5569XXXXXXXX@s.whatsapp.net)

        Returns:
            Dict com resultado consolidado
        """
        with self.logger.system_logger.correlation("enviar_whatsapp_multiplos") as corr_id:
            self.logger.info("Iniciando envio múltiplos WhatsApp", correlation_id=corr_id)
            if not arquivos:
                return {
                    "sucesso": False,
                    "mensagem": "Nenhum arquivo para enviar",
                    "detalhes": None
                }
        
            resultados = {
                "mensagem_enviada": False,
                "arquivos_enviados": [],
                "erros": []
            }
        
            # 1. PRIMEIRO: Enviar a mensagem de texto (se houver)
            if mensagem and mensagem.strip():
                logger.info(f"📤 Enviando mensagem de texto para {destinatario}...")
                resultado_msg = self.enviar_texto(destinatario, mensagem, is_grupo, device_id)
            
                if resultado_msg.get("sucesso"):
                    resultados["mensagem_enviada"] = True
                    logger.info(f"✓ Mensagem de texto enviada")
                    # Pequeno delay após enviar mensagem
                    time.sleep(self.DELAY_APOS_MENSAGEM)
                else:
                    resultados["erros"].append({
                        "tipo": "mensagem",
                        "erro": resultado_msg.get("mensagem")
                    })
                    logger.warning(f"⚠ Falha ao enviar mensagem: {resultado_msg.get('mensagem')}")
                    # Delay maior após erro
                    time.sleep(self.DELAY_APOS_ERRO)
        
            # 2. DEPOIS: Enviar os arquivos em sequência (SEM caption, já que a mensagem foi enviada)
            total_arquivos = len(arquivos)
            for idx, arquivo in enumerate(arquivos, 1):
                nome_arquivo = os.path.basename(arquivo)
                logger.info(f"📤 Enviando arquivo {idx}/{total_arquivos}: {nome_arquivo}")
            
                # Envia arquivo SEM caption (a mensagem já foi enviada separadamente)
                resultado = self.enviar_arquivo(destinatario, arquivo, "", is_grupo, device_id)
            
                if resultado.get("sucesso"):
                    resultados["arquivos_enviados"].append(nome_arquivo)
                    logger.info(f"✓ Arquivo enviado: {nome_arquivo}")
                
                    # Delay entre arquivos (não precisa após o último)
                    if idx < total_arquivos:
                        time.sleep(self.DELAY_ENTRE_ARQUIVOS)
                else:
                    resultados["erros"].append({
                        "tipo": "arquivo",
                        "arquivo": nome_arquivo,
                        "erro": resultado.get("mensagem")
                    })
                    logger.warning(f"⚠ Falha ao enviar {nome_arquivo}: {resultado.get('mensagem')}")
                    # Delay maior após erro
                    time.sleep(self.DELAY_APOS_ERRO)
        
            # Consolidar resultado
            total = len(arquivos)
            enviados = len(resultados["arquivos_enviados"])
            msg_ok = resultados["mensagem_enviada"]
        
            if enviados == total and (not mensagem or msg_ok):
                return {
                    "sucesso": True,
                    "mensagem": f"Mensagem + {total} arquivo(s) enviados com sucesso" if mensagem else f"{total} arquivo(s) enviados",
                    "detalhes": resultados
                }
            elif enviados > 0 or msg_ok:
                return {
                    "sucesso": True,
                    "parcial": True,
                    "mensagem": f"Parcial: msg={'✓' if msg_ok else '✗'}, arquivos={enviados}/{total}",
                    "detalhes": resultados
                }
            else:
                return {
                    "sucesso": False,
                    "mensagem": f"Falha ao enviar (msg={'✗' if mensagem else 'N/A'}, arquivos=0/{total})",
                    "detalhes": resultados
                }

        # ==================== DISPOSITIVOS (MULTIDEVICE) ====================

            self.logger.info("Envio múltiplos WhatsApp concluído", correlation_id=corr_id)

    def obter_id_dispositivo_por_jid(self, jid: str) -> Optional[str]:
        """
        Obtém o ID interno do dispositivo baseado em seu JID.

        Args:
            jid: JID do dispositivo (ex: 556993451333@s.whatsapp.net)

        Returns:
            ID do dispositivo (ex: WhatsApp-Alefe) ou None se não encontrado
        """
        if not jid:
            return None

        # Se for apenas o número, transformar em JID
        if "@" not in jid:
            if len(jid) >= 10:
                # Assumir que é um número de telefone
                jid = f"{jid}@s.whatsapp.net"
            else:
                return None

        dispositivos = self.listar_dispositivos()

        if not dispositivos:
            logger.warning(f"Nenhum dispositivo encontrado para buscar ID de {jid}")
            return None

        # Extrair número do JID
        numero = jid.split("@")[0] if "@" in jid else jid

        # Tentar encontrar exatamente pelo JID
        for dispositivo in dispositivos:
            disp_jid = dispositivo.get("jid", "")
            if disp_jid == jid:
                device_id = dispositivo.get("id")
                logger.debug(f"Dispositivo encontrado por JID exato: {jid} -> {device_id}")
                return device_id

        # Tentar encontrar pelo número (mais flexível)
        for dispositivo in dispositivos:
            disp_jid = dispositivo.get("jid", "")
            disp_numero = disp_jid.split("@")[0] if "@" in disp_jid else disp_jid

            # Comparar números - remover caracteres especiais
            numero_limpo = numero.replace("-", "").replace(" ", "")
            disp_numero_limpo = disp_numero.replace("-", "").replace(" ", "")

            if numero_limpo == disp_numero_limpo or disp_jid.startswith(numero + "@"):
                device_id = dispositivo.get("id")
                logger.debug(f"Dispositivo encontrado por numero: {numero} ({jid}) -> {device_id}")
                return device_id

        logger.warning(f"Dispositivo não encontrado para: {jid} (numero: {numero})")
        logger.debug(f"Dispositivos disponiveis: {[d.get('jid') for d in dispositivos]}")

        return None

    def listar_dispositivos(self) -> List[Dict[str, Any]]:
        """
        Lista todos os dispositivos conectados na API WhatsApp Multidevice v8.2.0+

        Returns:
            Lista de dispositivos com informações (id, display_name, state, jid, created_at)
            Exemplo: [
                {
                    "id": "WhatsApp-Alefe",
                    "display_name": "Alefsander Ribeiro",
                    "state": "logged_in",
                    "jid": "556993451333@s.whatsapp.net",
                    "created_at": "2026-01-29T19:50:40.864764866Z"
                }
            ]
        """
        if not self._disponivel:
            logger.warning("WhatsApp API não disponível")
            return []

        try:
            # Endpoint para listar dispositivos
            endpoint = "/devices"
            response = requests.get(
                f"{self.api_url}{endpoint}",
                headers=self._get_headers(None),
                timeout=30
            )

            if response.status_code == 200:
                dados = response.json()

                # API retorna {"code": "SUCCESS", "message": "...", "results": [...]}
                # results é um array direto de dispositivos
                dispositivos = dados.get("results", [])

                if not isinstance(dispositivos, list):
                    logger.error(f"Formato inesperado em results: {type(dispositivos)}")
                    return []

                logger.info(f"✓ {len(dispositivos)} dispositivo(s) obtido(s) da API")
                return dispositivos
            else:
                logger.error(f"Erro ao listar dispositivos: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            logger.error(f"Erro ao listar dispositivos: {e}")
            return []

    def verificar_status_dispositivo(self, device_id: str) -> Dict[str, Any]:
        """
        Verifica o status de um dispositivo específico buscando na lista de dispositivos

        Este método procura o dispositivo na lista retornada por listar_dispositivos()
        e retorna seu status atual.

        Args:
            device_id: ID do dispositivo (ex: 5569XXXXXXXX@s.whatsapp.net ou 556993451333)

        Returns:
            Dict com status do dispositivo:
            {
                "sucesso": bool,
                "device_id": str,
                "is_logged_in": bool,
                "numero": str,
                "estado": str,  # logged_in, connection_lost, etc
                "nome": str,    # Nome do dispositivo
                "mensagem": str
            }
        """
        if not self._disponivel:
            return {
                "sucesso": False,
                "device_id": device_id,
                "mensagem": "WhatsApp API nao disponivel"
            }

        if not device_id or ("@" not in device_id and len(device_id) < 10):
            return {
                "sucesso": False,
                "device_id": device_id,
                "mensagem": f"Device ID invalido: {device_id}. Formato esperado: 5569XXXXXXXX@s.whatsapp.net"
            }

        try:
            # Obter lista de dispositivos
            dispositivos = self.listar_dispositivos()

            if not dispositivos:
                return {
                    "sucesso": False,
                    "device_id": device_id,
                    "mensagem": "Nenhum dispositivo conectado"
                }

            # Normalizar device_id para busca (remover @ se for apenas número)
            device_id_busca = device_id if "@" in device_id else f"{device_id}@s.whatsapp.net"
            numero_busca = device_id.split("@")[0] if "@" in device_id else device_id

            # Procurar o dispositivo na lista
            for dispositivo in dispositivos:
                jid = dispositivo.get("jid", "")

                # Comparar por JID completo ou pelo número
                if jid == device_id_busca or jid.startswith(numero_busca + "@"):
                    estado = dispositivo.get("state", "unknown")
                    nome = dispositivo.get("display_name", "Desconhecido")
                    is_logged_in = estado == "logged_in"
                    numero = jid.split("@")[0] if "@" in jid else jid

                    logger.info(f"Status do dispositivo {numero}: {estado}")

                    return {
                        "sucesso": True,
                        "device_id": jid,
                        "is_logged_in": is_logged_in,
                        "numero": numero,
                        "estado": estado,
                        "nome": nome,
                        "mensagem": "Conectado" if is_logged_in else "Nao conectado - escanear QR Code"
                    }

            # Dispositivo nao encontrado na lista
            return {
                "sucesso": False,
                "device_id": device_id,
                "mensagem": f"Dispositivo {device_id} nao encontrado na lista de dispositivos conectados"
            }

        except Exception as e:
            erro_msg = f"Erro ao verificar status do dispositivo: {e}"
            logger.error(erro_msg)
            return {
                "sucesso": False,
                "device_id": device_id,
                "mensagem": erro_msg
            }


# Instância singleton
whatsapp_service = WhatsAppService()
