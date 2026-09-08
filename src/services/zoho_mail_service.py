"""
Service para envio de e-mails via Zoho Mail API com OAuth2 automatizado
Responsabilidades:
- Fluxo completo OAuth2 (autorização, tokens, refresh)
- Salvar tokens automaticamente no .env
- Obter Account ID automaticamente
- Envio de e-mails com anexos
- Renovação automática de tokens
"""

import os
import webbrowser
import urllib.parse
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import dotenv
import re

from src.utils.dotenv_path import caminho_dotenv
from src.utils.retry_utils import retry_com_log
from src.utils.logger_config_v2 import get_logger

logger = get_logger("email")


# Tentativa de importação de requests
try:
    import requests
    REQUESTS_DISPONIVEL = True
except ImportError:
    REQUESTS_DISPONIVEL = False
    logger.warning("Requests não instalado - ZohoMailService não funcionará")


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handler para receber callback OAuth"""
    
    authorization_code = None
    location = None
    
    def do_GET(self):
        """Processa GET request do callback OAuth"""
        # Parsear query string
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        if "code" in params:
            OAuthCallbackHandler.authorization_code = params["code"][0]
            OAuthCallbackHandler.location = params.get("location", ["com"])[0]
            
            # Responder sucesso
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            
            html = """
            <!DOCTYPE html>
            <html>
            <head><title>Autorização Concluída</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: #28a745;">✓ Autorização Concluída!</h1>
                <p>Você pode fechar esta janela e voltar ao programa.</p>
                <p>O código de autorização foi recebido com sucesso.</p>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
        else:
            # Erro
            error = params.get("error", ["unknown"])[0]
            self.send_response(400)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            
            html = f"""
            <!DOCTYPE html>
            <html>
            <head><title>Erro na Autorização</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: #dc3545;">✗ Erro na Autorização</h1>
                <p>Erro: {error}</p>
                <p>Por favor, tente novamente.</p>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
    
    def log_message(self, format, *args):
        """Suprime logs do servidor HTTP"""
        pass


class ZohoMailService:
    """
    Gerencia envio de e-mails via Zoho Mail API com OAuth2 automatizado
    
    Fluxo OAuth2:
    1. Gerar URL de autorização
    2. Usuário autoriza no navegador
    3. Receber código via callback local (http://localhost:8080)
    4. Trocar código por access_token e refresh_token
    5. Obter Account ID automaticamente
    6. Salvar tudo no .env
    7. Renovar tokens quando necessário
    
    Requer no .env (mínimo):
    - ZOHO_CLIENT_ID
    - ZOHO_CLIENT_SECRET
    
    O serviço obtém/atualiza automaticamente:
    - ZOHO_REFRESH_TOKEN
    - ZOHO_ACCESS_TOKEN
    - ZOHO_ACCOUNT_ID
    - ZOHO_EMAIL_FROM
    - ZOHO_API_DOMAIN
    - ZOHO_TOKEN_EXPIRY
    """
    
    # URLs base por datacenter
    ACCOUNTS_URLS = {
        "com": "https://accounts.zoho.com",
        "eu": "https://accounts.zoho.eu",
        "in": "https://accounts.zoho.in",
        "com.cn": "https://accounts.zoho.com.cn",
        "com.au": "https://accounts.zoho.com.au",
        "jp": "https://accounts.zoho.jp",
    }
    
    MAIL_URLS = {
        "com": "https://mail.zoho.com",
        "eu": "https://mail.zoho.eu",
        "in": "https://mail.zoho.in",
        "com.cn": "https://mail.zoho.com.cn",
        "com.au": "https://mail.zoho.com.au",
        "jp": "https://mail.zoho.jp",
    }
    
    # Scopes necessários
    SCOPES = [
        "ZohoMail.messages.ALL",
        "ZohoMail.attachments.ALL",
        "ZohoMail.accounts.READ"
    ]
    
    # Porta para callback OAuth
    CALLBACK_PORT = 8080
    REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/callback"
    
    def __init__(self):

        self.logger = get_logger("email")
        """Inicializa configurações do Zoho Mail"""
        self.env_path = caminho_dotenv()
        # Inicializar atributos ANTES de carregar configurações
        self._access_token: Optional[str] = None
        self._token_expira_em: Optional[datetime] = None
        self._carregar_configuracoes()
    
    def _obter_env(self, chave: str, padrao: str = None) -> Optional[str]:
        """Obtém valor do .env sem avisos"""
        import os
        # Recarregar .env silenciosamente
        dotenv.load_dotenv(self.env_path, override=True)
        return os.getenv(chave, padrao)
    
    def _carregar_configuracoes(self) -> None:
        """Carrega configurações do .env"""
        # Carregar .env uma vez
        dotenv.load_dotenv(self.env_path, override=True)
        
        import os
        self.client_id = os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = os.getenv("ZOHO_CLIENT_SECRET")
        self.refresh_token = os.getenv("ZOHO_REFRESH_TOKEN")
        self.account_id = os.getenv("ZOHO_ACCOUNT_ID")
        self.email_from = os.getenv("ZOHO_EMAIL_FROM")
        self.api_domain = os.getenv("ZOHO_API_DOMAIN") or "com"
        
        # Carregar access token e expiração se existirem
        saved_token = os.getenv("ZOHO_ACCESS_TOKEN")
        saved_expiry = os.getenv("ZOHO_TOKEN_EXPIRY")
        
        if saved_token and saved_expiry:
            try:
                self._access_token = saved_token
                self._token_expira_em = datetime.fromisoformat(saved_expiry)
            except:
                pass
        
        # Validar configurações
        self._tem_credenciais = bool(self.client_id and self.client_secret)
        self._tem_tokens = bool(self.refresh_token and self.account_id)
        
        # Disponível se tem requests E (credenciais OU tokens válidos)
        if not REQUESTS_DISPONIVEL:
            self._disponivel = False
            logger.warning("Zoho Mail: requests não instalado")
        elif self._tem_tokens:
            # Temos tokens - podemos operar (mas sem credenciais, não poderemos reautorizar se tokens expirarem)
            self._disponivel = True
            if not self._tem_credenciais:
                logger.debug("Zoho Mail: Operando com tokens salvos (adicione CLIENT_ID/SECRET para reautorização)")
            else:
                logger.debug("✓ Configurações do Zoho Mail carregadas completamente")
        elif self._tem_credenciais:
            # Temos credenciais mas não tokens - pode configurar
            self._disponivel = True
            logger.debug("Zoho Mail: Credenciais carregadas - necessário configurar OAuth")
        else:
            # Sem credenciais e sem tokens - não funcional
            self._disponivel = False
            logger.warning("Zoho Mail: Adicione ZOHO_CLIENT_ID e ZOHO_CLIENT_SECRET no .env")
    
    @property
    def disponivel(self) -> bool:
        """Verifica se o serviço pode operar (tem credenciais OU tokens)"""
        return self._disponivel
    
    @property
    def configurado(self) -> bool:
        """Verifica se OAuth está completamente configurado (tem tokens válidos)"""
        return bool(self.refresh_token and self.account_id and self.email_from)
    
    @property
    def pode_reautorizar(self) -> bool:
        """Verifica se pode fazer reautorização OAuth (precisa de CLIENT_ID e SECRET)"""
        return self._tem_credenciais
    
    @property
    def status_config(self) -> str:
        """Retorna status detalhado da configuração"""
        if not REQUESTS_DISPONIVEL:
            return "❌ Requests não instalado"
        
        if self.configurado:
            if self._tem_credenciais:
                return "✅ Totalmente configurado"
            else:
                return "⚠️ Configurado (adicione CLIENT_ID/SECRET para reautorização)"
        elif self._tem_credenciais:
            return "🔧 Credenciais OK - Execute configuração OAuth"
        else:
            return "❌ Não configurado - Adicione ZOHO_CLIENT_ID e ZOHO_CLIENT_SECRET"
    
    def _salvar_no_env(self, chave: str, valor: str) -> None:
        """Salva valor no arquivo .env"""
        try:
            dotenv.set_key(self.env_path, chave, valor)
            logger.debug(f"✓ Salvo no .env: {chave}")
        except Exception as e:
            logger.error(f"Erro ao salvar {chave} no .env: {e}")
    
    def _get_accounts_url(self) -> str:
        """Retorna URL do servidor de contas baseado no datacenter"""
        return self.ACCOUNTS_URLS.get(self.api_domain, self.ACCOUNTS_URLS["com"])
    
    def _get_mail_url(self) -> str:
        """Retorna URL da API de mail baseado no datacenter"""
        return self.MAIL_URLS.get(self.api_domain, self.MAIL_URLS["com"])
    
    # ==================== FLUXO OAUTH2 ====================
    
    def gerar_url_autorizacao(self) -> str:
        """
        Gera URL para autorização OAuth2
        
        Returns:
            URL para abrir no navegador
        """
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.REDIRECT_URI,
            "scope": ",".join(self.SCOPES),
            "access_type": "offline",  # Para receber refresh_token
            "prompt": "consent"  # Sempre pedir consentimento
        }
        
        base_url = f"{self._get_accounts_url()}/oauth/v2/auth"
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        
        return url
    
    def iniciar_servidor_callback(self, timeout: int = 120) -> Optional[Dict[str, str]]:
        """
        Inicia servidor local para receber callback OAuth
        
        Args:
            timeout: Tempo máximo de espera em segundos
        
        Returns:
            Dict com 'code' e 'location' ou None se timeout/erro
        """
        OAuthCallbackHandler.authorization_code = None
        OAuthCallbackHandler.location = None
        
        server = HTTPServer(("localhost", self.CALLBACK_PORT), OAuthCallbackHandler)
        server.timeout = timeout
        
        logger.info(f"Aguardando callback OAuth em http://localhost:{self.CALLBACK_PORT}...")
        
        # Aguardar uma requisição
        start_time = datetime.now()
        while OAuthCallbackHandler.authorization_code is None:
            server.handle_request()
            
            if (datetime.now() - start_time).total_seconds() > timeout:
                logger.warning("Timeout aguardando callback OAuth")
                server.server_close()
                return None
        
        server.server_close()
        
        return {
            "code": OAuthCallbackHandler.authorization_code,
            "location": OAuthCallbackHandler.location or "com"
        }
    
    def trocar_codigo_por_tokens(self, code: str, location: str = "com") -> Optional[Dict[str, Any]]:
        """
        Troca código de autorização por tokens
        
        Args:
            code: Código de autorização
            location: Datacenter do usuário
        
        Returns:
            Dict com tokens ou None se erro
        """
        if not REQUESTS_DISPONIVEL:
            return None
        
        # Atualizar domínio baseado na localização
        self.api_domain = location
        self._salvar_no_env("ZOHO_API_DOMAIN", location)
        
        url = f"{self._get_accounts_url()}/oauth/v2/token"
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.REDIRECT_URI
        }
        
        try:
            response = requests.post(url, data=data, timeout=30)
            
            if response.status_code == 200:
                tokens = response.json()
                
                # Salvar access_token
                access_token = tokens.get("access_token")
                if access_token:
                    self._access_token = access_token
                    self._salvar_no_env("ZOHO_ACCESS_TOKEN", access_token)
                    
                    # Calcular e salvar expiração
                    expires_in = tokens.get("expires_in", 3600)
                    self._token_expira_em = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 300)
                    self._salvar_no_env("ZOHO_TOKEN_EXPIRY", self._token_expira_em.isoformat())
                
                # Salvar refresh_token
                refresh_token = tokens.get("refresh_token")
                if refresh_token:
                    self.refresh_token = refresh_token
                    self._salvar_no_env("ZOHO_REFRESH_TOKEN", refresh_token)
                
                logger.info("✓ Tokens OAuth obtidos com sucesso")
                return tokens
            else:
                logger.error(f"Erro ao obter tokens: {response.status_code} - {response.text}")
                return None
        
        except Exception as e:
            logger.error(f"Erro ao trocar código por tokens: {e}")
            return None
    
    def renovar_access_token(self) -> Optional[str]:
        """
        Renova access_token usando refresh_token
        
        Returns:
            Novo access_token ou None se erro
        """
        if not self.refresh_token:
            logger.error("Refresh token não disponível")
            return None
        
        if not self._tem_credenciais:
            logger.error("ZOHO_CLIENT_ID e ZOHO_CLIENT_SECRET necessários para renovar token")
            return None
        
        if not REQUESTS_DISPONIVEL:
            return None
        
        url = f"{self._get_accounts_url()}/oauth/v2/token"
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        
        try:
            response = requests.post(url, data=data, timeout=30)
            
            if response.status_code == 200:
                dados = response.json()
                
                access_token = dados.get("access_token")
                if access_token:
                    self._access_token = access_token
                    self._salvar_no_env("ZOHO_ACCESS_TOKEN", access_token)
                    
                    # Calcular e salvar expiração
                    expires_in = dados.get("expires_in", 3600)
                    self._token_expira_em = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 300)
                    self._salvar_no_env("ZOHO_TOKEN_EXPIRY", self._token_expira_em.isoformat())
                    
                    logger.debug("✓ Access token renovado com sucesso")
                    return access_token
            else:
                erro = response.json() if response.text else {}
                erro_code = erro.get("error", "unknown")
                
                if erro_code == "invalid_code":
                    logger.error("Refresh token inválido ou expirado - necessário reautorizar")
                    # Limpar tokens inválidos
                    self._salvar_no_env("ZOHO_REFRESH_TOKEN", "")
                    self.refresh_token = None
                else:
                    logger.error(f"Erro ao renovar token: {response.status_code} - {response.text}")
                
                return None
        
        except Exception as e:
            logger.error(f"Erro ao renovar access token: {e}")
            return None
    
    def _obter_access_token(self) -> Optional[str]:
        """
        Obtém access token válido (renovando se necessário)
        
        Returns:
            Access token ou None se erro
        """
        # Verificar se token atual ainda é válido
        if self._access_token and self._token_expira_em:
            agora = datetime.now(timezone.utc)
            # Se expiração não tem timezone, assumir UTC
            expira = self._token_expira_em
            if expira.tzinfo is None:
                expira = expira.replace(tzinfo=timezone.utc)
            
            if agora < expira:
                return self._access_token
        
        # Token expirado ou inexistente - tentar renovar
        if self.refresh_token:
            return self.renovar_access_token()
        
        logger.error("Nenhum token disponível - necessário configurar OAuth")
        return None
    
    def obter_account_id(self) -> Optional[str]:
        """
        Obtém Account ID da API do Zoho Mail
        
        Returns:
            Account ID ou None se erro
        """
        token = self._obter_access_token()
        if not token:
            return None
        
        try:
            url = f"{self._get_mail_url()}/api/accounts"
            headers = {
                "Authorization": f"Zoho-oauthtoken {token}"
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                dados = response.json()
                contas = dados.get("data", [])
                
                if contas:
                    # Pegar primeira conta
                    conta = contas[0]
                    account_id = str(conta.get("accountId", ""))
                    email = conta.get("primaryEmailAddress", "")
                    
                    if account_id:
                        self.account_id = account_id
                        self._salvar_no_env("ZOHO_ACCOUNT_ID", account_id)
                        
                        if email:
                            self.email_from = email
                            self._salvar_no_env("ZOHO_EMAIL_FROM", email)
                        
                        logger.info(f"✓ Account ID obtido: {account_id} ({email})")
                        return account_id
            else:
                logger.error(f"Erro ao obter Account ID: {response.status_code} - {response.text}")
                return None
        
        except Exception as e:
            logger.error(f"Erro ao obter Account ID: {e}")
            return None
    
    # ==================== CONFIGURAÇÃO INTERATIVA ====================
    
    def configurar_oauth_interativo(self) -> bool:
        """
        Executa fluxo completo de configuração OAuth interativamente
        
        Returns:
            True se configurado com sucesso
        """
        print("\n" + "=" * 60)
        print("  CONFIGURAÇÃO OAUTH2 DO ZOHO MAIL")
        print("=" * 60)
        
        if not self.client_id or not self.client_secret:
            print("\n✗ ZOHO_CLIENT_ID e ZOHO_CLIENT_SECRET são obrigatórios!")
            print("Configure-os no arquivo .env antes de continuar.")
            return False
        
        print("\nO processo irá:")
        print("1. Abrir seu navegador para autorização")
        print("2. Aguardar você fazer login no Zoho")
        print("3. Receber o código de autorização automaticamente")
        print("4. Obter e salvar os tokens no .env")
        print("5. Obter Account ID e e-mail automaticamente")
        
        input("\nPressione ENTER para continuar...")
        
        # Gerar URL
        url = self.gerar_url_autorizacao()
        print(f"\nAbrindo navegador para autorização...")
        print(f"URL: {url}\n")
        
        # Abrir navegador
        webbrowser.open(url)
        
        # Iniciar servidor e aguardar callback
        print("Aguardando autorização (timeout: 2 minutos)...")
        resultado = self.iniciar_servidor_callback(timeout=120)
        
        if not resultado:
            print("\n✗ Timeout ou erro ao aguardar autorização")
            return False
        
        print(f"\n✓ Código recebido!")
        print(f"Datacenter: {resultado['location']}")
        
        # Trocar código por tokens
        print("\nObtendo tokens...")
        tokens = self.trocar_codigo_por_tokens(resultado["code"], resultado["location"])
        
        if not tokens:
            print("\n✗ Erro ao obter tokens")
            return False
        
        print("✓ Tokens obtidos e salvos no .env")
        
        # Obter Account ID
        print("\nObtendo Account ID...")
        account_id = self.obter_account_id()
        
        if not account_id:
            print("\n✗ Erro ao obter Account ID")
            return False
        
        print(f"✓ Account ID: {account_id}")
        print(f"✓ E-mail: {self.email_from}")
        
        print("\n" + "=" * 60)
        print("  ✓ CONFIGURAÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 60)
        print("\nAs seguintes variáveis foram salvas no .env:")
        print(f"  - ZOHO_REFRESH_TOKEN")
        print(f"  - ZOHO_ACCESS_TOKEN")
        print(f"  - ZOHO_TOKEN_EXPIRY")
        print(f"  - ZOHO_ACCOUNT_ID: {account_id}")
        print(f"  - ZOHO_EMAIL_FROM: {self.email_from}")
        print(f"  - ZOHO_API_DOMAIN: {self.api_domain}")
        
        return True
    
    def revogar_e_reautorizar(self) -> bool:
        """
        Revoga tokens atuais e inicia nova autorização
        
        Returns:
            True se reautorizado com sucesso
        """
        print("\n⚠ Revogando tokens atuais...")
        
        # Limpar tokens salvos
        self._salvar_no_env("ZOHO_REFRESH_TOKEN", "")
        self._salvar_no_env("ZOHO_ACCESS_TOKEN", "")
        self._salvar_no_env("ZOHO_TOKEN_EXPIRY", "")
        
        self.refresh_token = None
        self._access_token = None
        self._token_expira_em = None
        
        print("✓ Tokens revogados")
        
        # Reautorizar
        return self.configurar_oauth_interativo()
    
    # ==================== UPLOAD E ENVIO ====================
    
    def _upload_anexo(self, arquivo_path: str) -> Optional[Dict[str, str]]:
        """
        Faz upload de anexo e retorna informações para envio
        
        Args:
            arquivo_path: Caminho absoluto do arquivo
        
        Returns:
            Dict com storeName, attachmentName, attachmentPath ou None
        """
        token = self._obter_access_token()
        if not token:
            return None
        
        if not os.path.exists(arquivo_path):
            logger.error(f"Arquivo não encontrado: {arquivo_path}")
            return None
        
        try:
            nome_arquivo = os.path.basename(arquivo_path)
            
            # URL com parâmetro uploadType=multipart (obrigatório para MULTIPART_FORM_DATA)
            url = f"{self._get_mail_url()}/api/accounts/{self.account_id}/messages/attachments?uploadType=multipart"
            
            headers = {
                "Authorization": f"Zoho-oauthtoken {token}"
            }
            
            with open(arquivo_path, "rb") as f:
                files = {
                    "attach": (nome_arquivo, f, "application/pdf")
                }
                
                response = requests.post(
                    url,
                    headers=headers,
                    files=files,
                    timeout=120
                )
            
            if response.status_code == 200:
                dados = response.json()
                logger.debug(f"Resposta upload anexo: {dados}")
                
                # A resposta pode vir como lista (multipart) ou dict (raw)
                attach_data = dados.get("data", {})
                
                # Se for lista, pegar o primeiro item
                if isinstance(attach_data, list):
                    if len(attach_data) > 0:
                        attach_data = attach_data[0]
                    else:
                        logger.error("Resposta de upload sem dados de anexo")
                        return None
                
                result = {
                    "storeName": attach_data.get("storeName", ""),
                    "attachmentName": attach_data.get("attachmentName", nome_arquivo),
                    "attachmentPath": attach_data.get("attachmentPath", "")
                }
                
                logger.debug(f"✓ Anexo enviado: {nome_arquivo}")
                return result
            else:
                logger.error(f"Erro no upload do anexo: {response.status_code} - {response.text}")
                return None
        
        except Exception as e:
            logger.error(f"Erro ao fazer upload do anexo: {e}")
            return None
    
    @retry_com_log()
    def enviar_email(self, 
                     destinatarios: List[str],
                     assunto: str,
                     corpo: str,
                     anexos: List[str] = None,
                     cc: List[str] = None,
                     cco: List[str] = None) -> Dict[str, Any]:
        """
        Envia e-mail com anexos via Zoho Mail API
        
        Args:
            destinatarios: Lista de e-mails destinatários
            assunto: Assunto do e-mail
            corpo: Corpo do e-mail (texto ou HTML)
            anexos: Lista de caminhos de arquivos para anexar
            cc: Lista de e-mails em cópia
            cco: Lista de e-mails em cópia oculta
        
        Returns:
            Dict com resultado: {"sucesso": bool, "mensagem": str, "detalhes": ...}
        """
        if not self._disponivel:
            return {
                "sucesso": False,
                "mensagem": "Zoho Mail não configurado ou requests não disponível",
                "detalhes": None
            }
        
        if not self.configurado:
            return {
                "sucesso": False,
                "mensagem": "OAuth não configurado - execute configurar_oauth_interativo()",
                "detalhes": None
            }
        
        token = self._obter_access_token()
        if not token:
            return {
                "sucesso": False,
                "mensagem": "Não foi possível obter access token - token pode estar expirado",
                "detalhes": {"sugestao": "Execute revogar_e_reautorizar()"}
            }
        
        try:
            # Fazer upload dos anexos
            attachments_list = []
            if anexos:
                for anexo_path in anexos:
                    attach_info = self._upload_anexo(anexo_path)
                    if attach_info:
                        attachments_list.append(attach_info)
                    else:
                        logger.warning(f"Falha no upload do anexo: {anexo_path}")
            
            # Preparar payload do e-mail
            url = f"{self._get_mail_url()}/api/accounts/{self.account_id}/messages"
            
            headers = {
                "Authorization": f"Zoho-oauthtoken {token}",
                "Content-Type": "application/json"
            }
            
            # Formatar destinatários (JSON array)
            to_address = ",".join(destinatarios)
            
            
            # Detectar se o corpo contém HTML simples
            is_html = bool(re.search(r"<[^>]+>", corpo or ""))

            corpo_html = (corpo.replace("\r\n", "\n").replace("\n", "<br/>") if corpo and not is_html else corpo)
            
            payload = {
                "fromAddress": self.email_from,
                "toAddress": to_address,
                "subject": assunto,
                "content": corpo_html,
                "mailFormat": "html"
            }
            
            
            # Adicionar CC se houver
            if cc:
                payload["ccAddress"] = ",".join(cc)
            
            # Adicionar CCO se houver
            if cco:
                payload["bccAddress"] = ",".join(cco)
            
            # Adicionar anexos se houver
            if attachments_list:
                payload["attachments"] = attachments_list
            
            # Enviar e-mail
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                dados = response.json()
                
                logger.info(
                    f"✓ E-mail enviado para {', '.join(destinatarios)} "
                    f"com {len(attachments_list)} anexo(s)"
                )
                
                return {
                    "sucesso": True,
                    "mensagem": "E-mail enviado com sucesso",
                    "detalhes": {
                        "destinatarios": destinatarios,
                        "anexos_count": len(attachments_list),
                        "response": dados
                    }
                }
            else:
                erro_msg = f"Erro ao enviar e-mail: {response.status_code} - {response.text}"
                logger.error(erro_msg)
                return {
                    "sucesso": False,
                    "mensagem": erro_msg,
                    "detalhes": response.json() if response.text else None
                }
        
        except Exception as e:
            erro_msg = f"Erro ao enviar e-mail: {e}"
            logger.error(erro_msg)
            return {
                "sucesso": False,
                "mensagem": erro_msg,
                "detalhes": None
            }
    
    # ==================== VERIFICAÇÕES ====================
    
    def verificar_conexao(self) -> Dict[str, Any]:
        """
        Verifica se a conexão com Zoho Mail está funcionando
        
        Returns:
            Dict com status detalhado
        """
        status = {
            "disponivel": self._disponivel,
            "configurado": self.configurado,
            "token_valido": False,
            "account_id": self.account_id,
            "email_from": self.email_from,
            "pode_reautorizar": self._tem_credenciais,
            "mensagem": ""
        }
        
        if not self._disponivel:
            status["mensagem"] = "Serviço não disponível"
            return status
        
        if not self.configurado:
            if self._tem_credenciais:
                status["mensagem"] = "OAuth não configurado - execute configurar_oauth_interativo()"
            else:
                status["mensagem"] = "Adicione ZOHO_CLIENT_ID e ZOHO_CLIENT_SECRET no .env"
            return status
        
        # Tentar obter token (primeiro usar token salvo, depois tentar refresh)
        token = self._obter_access_token()
        if not token:
            if self._tem_credenciais:
                status["mensagem"] = "Token expirado - execute revogar_e_reautorizar()"
            else:
                status["mensagem"] = "Token expirado - adicione CLIENT_ID/SECRET para renovar"
            return status
        
        # Tentar uma requisição simples
        try:
            url = f"{self._get_mail_url()}/api/accounts/{self.account_id}"
            headers = {"Authorization": f"Zoho-oauthtoken {token}"}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                status["token_valido"] = True
                status["mensagem"] = "Conexão OK"
                logger.info("✓ Conexão com Zoho Mail verificada")
            else:
                status["mensagem"] = f"Erro na verificação: {response.status_code}"
        
        except Exception as e:
            status["mensagem"] = f"Erro de conexão: {e}"
        
        return status
    
    def obter_status_tokens(self) -> Dict[str, Any]:
        """
        Retorna status dos tokens OAuth
        
        Returns:
            Dict com informações dos tokens
        """
        agora = datetime.now(timezone.utc)
        
        status = {
            "refresh_token_presente": bool(self.refresh_token),
            "access_token_presente": bool(self._access_token),
            "token_expira_em": None,
            "token_expirado": True,
            "tempo_restante": None
        }
        
        if self._token_expira_em:
            expira = self._token_expira_em
            if expira.tzinfo is None:
                expira = expira.replace(tzinfo=timezone.utc)
            
            status["token_expira_em"] = expira.isoformat()
            status["token_expirado"] = agora >= expira
            
            if not status["token_expirado"]:
                delta = expira - agora
                status["tempo_restante"] = f"{int(delta.total_seconds() / 60)} minutos"
        
        return status


# Instância singleton
zoho_mail_service = ZohoMailService()
