from pathlib import Path
import PIL.Image
import requests
import io
import httpx
import base64
from abc import ABC
from src.utils.dotenv_path import caminho_dotenv
import dotenv
from google import genai
from google.genai import types
from mistralai import Mistral
from src.utils.logger_config_v2 import get_logger

logger = get_logger("ia")




class ServiceBaseGemini(ABC):
    """Classe base abstrata para serviços de IA do Gemini"""
    
    def __init__(self, **kwargs):

        self.logger = get_logger("ia")
        self._api_key = dotenv.get_key(caminho_dotenv(), "KEY_API_GEMINI")
        self._sdk_disponivel = False
        self._client = None
        self._model = None
        self._default_config_kwargs = kwargs  # Armazena os kwargs padrão
        self._configurado = self._configurar_sdk()
    
    def _configurar_sdk(self) -> bool:
        if not self.api_key:
            logger.warning(f"IA: API Key não configurada para {self.__class__.__name__}")
            return False
        try:
            self._client = genai.Client(api_key=self.api_key)
            self._sdk_disponivel = True
            return True
        except ImportError:
            logger.warning(f"IA: SDK não encontrado para {self.__class__.__name__}")
            return False
        except Exception as e:
            logger.error(f"IA: Erro config SDK {self.__class__.__name__}: {e}")
            return False
    
    def _create_config(self, **kwargs) -> types.GenerateContentConfig:
        """Cria uma nova configuração mesclando os kwargs padrão com os fornecidos"""
        merged_kwargs = {**self._default_config_kwargs, **kwargs}
        return types.GenerateContentConfig(**merged_kwargs)
    
    @property
    def api_key(self) -> str: 
        return self._api_key
    @property
    def sdk_disponivel(self) -> bool: 
        return self._sdk_disponivel
    @property
    def client(self) -> genai.Client: 
        return self._client
    @property
    def model(self): 
        return self._model
    @property
    def configurado(self) -> bool: 
        return self._configurado



class ServiceBaseMistral(ABC):
    """Classe base abstrata para serviços de IA do Mistral"""
    
    def __init__(self, **kwargs):
        self._api_key = dotenv.get_key(caminho_dotenv(), "KEY_API_MISTRAL")
        self._sdk_disponivel = False
        self._client = None
        self._model = None
        self._configurado = self._configurar_sdk()
    
    def _configurar_sdk(self) -> bool:
        if not self.api_key:
            logger.warning(f"IA: API Key não configurada para {self.__class__.__name__}")
            return False
        try:
            self._client = Mistral(api_key=self.api_key)
            self._sdk_disponivel = True
            return True
        except ImportError:
            logger.warning(f"IA: SDK não encontrado para {self.__class__.__name__}")
            return False
        except Exception as e:
            logger.error(f"IA: Erro config SDK {self.__class__.__name__}: {e}")
            return False
    
    @property
    def api_key(self) -> str: 
        return self._api_key
    @property
    def sdk_disponivel(self) -> bool: 
        return self._sdk_disponivel
    @property
    def client(self) -> Mistral: 
        return self._client
    @property
    def model(self): 
        return self._model
    @property
    def configurado(self) -> bool: 
        return self._configurado



class GeminiService(ServiceBaseGemini):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Caso não seja especificado com o "model" nos kwargs, usar o padrão que é o "gemini-2.5-pro"
        # Trocar para "gemini-2.5-flash-lite" se quiser uma versão mais leve
        # Usar o "gemini-2.5-pro" para análises mais robustas e profundas

        self._model = kwargs.get("model", "gemini-2.5-pro")

    def __str__(self):
        return "Serviço Gemini para realizar análises de texto, imagem e documentos."

    def _get_mime_type(self, extensao: str) -> str:
        tipos_arquivo = {
            ".pdf": "application/pdf",
            ".html": "text/html",
            ".txt": "text/plain",
            ".xml": "text/xml",
            ".csv": "text/csv",
            ".py": "application/x-python"
        }
        mime_type = tipos_arquivo.get(extensao)
        if not mime_type:
            raise ValueError(f"Extensão não suportada: {extensao}")
        return mime_type
    
    def _tentar_gerar_conteudo(self, config, contents):
        try:
            logger.info(f"Gerando conteúdo com modelo {self._model}...")
            response = self._client.models.generate_content(
                model=self._model,
                config=config,
                contents=contents
            )
            
            if response is None:
                logger.error("Resposta é None do Gemini")
                return None
            
            if not hasattr(response, 'text') or response.text is None:
                logger.error(f"Resposta sem texto. Response: {response}")
                return None
            
            logger.info(f"Resposta recebida ({len(response.text)} caracteres)")
            return response
        except Exception as e:
            logger.error(f"Erro na geração de conteúdo: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _build_complete_schema(self, schema_json: dict) -> dict:
        """
        Constrói um schema completo com todas as definições inlined.
        Remove 'default', 'title' e outros campos não suportados pelo Gemini.
        """
        defs = schema_json.get("$defs", {})
        
        def clean_schema(obj):
            """Remove campos não suportados e resolve referências"""
            if isinstance(obj, dict):
                # Se tem uma referência, substituir pela definição
                if "$ref" in obj:
                    ref_key = obj["$ref"].split("/")[-1]
                    if ref_key in defs:
                        return clean_schema(dict(defs[ref_key]))
                    else:
                        logger.warning(f"Referência não encontrada: {ref_key}")
                        return obj
                
                # Copiar mantendo a estrutura mas removendo campos não suportados
                cleaned = {}
                
                # Campos que devem ser sempre mantidos se presentes
                if "type" in obj:
                    cleaned["type"] = obj["type"]
                
                if "required" in obj:
                    cleaned["required"] = obj["required"]
                
                if "enum" in obj:
                    cleaned["enum"] = obj["enum"]
                
                if "description" in obj:
                    cleaned["description"] = obj["description"]
                
                # Manter constraints numéricos
                for key in ["minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems", "pattern"]:
                    if key in obj:
                        cleaned[key] = obj[key]
                
                # Processar items e properties recursivamente
                if "items" in obj:
                    cleaned["items"] = clean_schema(obj["items"])
                
                if "properties" in obj and isinstance(obj["properties"], dict):
                    cleaned["properties"] = {}
                    for key, value in obj["properties"].items():
                        cleaned["properties"][key] = clean_schema(value)
                
                # Processar allOf, anyOf, oneOf
                for key in ["allOf", "anyOf", "oneOf"]:
                    if key in obj:
                        cleaned[key] = [clean_schema(item) for item in obj[key]]
                
                return cleaned
            elif isinstance(obj, list):
                return [clean_schema(item) for item in obj]
            else:
                return obj
        
        # Construir schema limpo
        props = schema_json.get("properties", {})
        cleaned_props = {}
        for key, value in props.items():
            cleaned_props[key] = clean_schema(dict(value))
        
        complete_schema = {
            "type": "object",
            "properties": cleaned_props,
            "required": schema_json.get("required", [])
        }
        
        return complete_schema
            
    def imagem(self, imagem, prompt: str, **kwargs):
        
        """Processa uma imagem e retorna o texto de acordo com o prompt."""
        if isinstance(imagem, PIL.Image.Image):
            img = imagem
        elif isinstance(imagem, str) and Path(imagem).is_file() or isinstance(imagem, Path) and imagem.exists():
            img = PIL.Image.open(imagem)
        else:
            response = requests.get(imagem)
            img = PIL.Image.open(io.BytesIO(response.content))
        
        response = self._tentar_gerar_conteudo(self._create_config(**kwargs), [img, prompt])
        return response.text
        

    def texto(self, prompt: str, **kwargs):
        contents = [prompt]
        response = self._tentar_gerar_conteudo(self._create_config(**kwargs), contents)
        return response.text

    def documento(self, documento: Path, prompt: str, **kwargs):
        """Processa um documento e retorna o texto de acordo com o prompt."""
        
        if not isinstance(documento, Path):
            raise TypeError("O parâmetro 'documento' deve ser do tipo Path.")
        if not documento.exists():
            raise FileNotFoundError(f"O arquivo '{documento}' não foi encontrado.")
        if not documento.is_file():
            raise ValueError(f"O caminho '{documento}' não é um arquivo válido.")

        contents = [types.Part.from_bytes(data=documento.read_bytes(), mime_type=self._get_mime_type(documento.suffix.lower())), prompt]
        response = self._tentar_gerar_conteudo(self._create_config(**kwargs), contents)
        return response.text

    def documento_na_internet(self, url_documento: str, prompt: str, **kwargs):
        
        try:
            response = httpx.get(url_documento)
            response.raise_for_status()
        except httpx.RequestError as e:
            raise ValueError(f"Erro ao acessar a URL: {e}")

        if not response.content:
            raise ValueError("O conteúdo da URL está vazio ou não foi encontrado.")

        mime_type = self._get_mime_type(Path(url_documento).suffix)
        contents = [types.Part.from_bytes(data=response.content, mime_type=mime_type), prompt]
        response = self._tentar_gerar_conteudo(self._create_config(**kwargs), contents)
        return response.text

    def documento_estruturado(self, documento: Path, prompt: str, schema_pydantic, **kwargs):
        """
        Processa um documento com Structured Output usando Pydantic schema.
        
        Retorna JSON conforme o schema fornecido.
        Seleciona automaticamente entre inline (<20MB) e File API (>20MB).
        
        Args:
            documento: Caminho para o documento (PDF, HTML, etc)
            prompt: Prompt descrevendo o que extrair
            schema_pydantic: Modelo Pydantic V2 com model_json_schema()
            **kwargs: Configurações adicionais para GenerateContentConfig
            
        Returns:
            str: JSON conforme schema_pydantic
            
        Raises:
            TypeError: Se documento não for Path
            FileNotFoundError: Se arquivo não existir
            ValueError: Se arquivo não for válido
        """
        if not isinstance(documento, Path):
            raise TypeError("O parâmetro 'documento' deve ser do tipo Path.")
        if not documento.exists():
            raise FileNotFoundError(f"O arquivo '{documento}' não foi encontrado.")
        if not documento.is_file():
            raise ValueError(f"O caminho '{documento}' não é um arquivo válido.")
        
        # Verificar tamanho do arquivo
        tamanho_bytes = documento.stat().st_size
        limite_20mb = 20 * 1024 * 1024  # 20MB em bytes
        
        if tamanho_bytes < limite_20mb:
            return self._documento_estruturado_inline(documento, prompt, schema_pydantic, **kwargs)
        else:
            return self._documento_estruturado_file_api(documento, prompt, schema_pydantic, **kwargs)

    def imagem_estruturada(self, imagem, prompt: str, schema_pydantic, **kwargs):
        """
        Processa uma imagem com Structured Output usando Pydantic schema.
        
        Retorna JSON conforme o schema fornecido.
        
        Args:
            imagem: PIL.Image, caminho para arquivo, ou URL
            prompt: Prompt descrevendo o que extrair
            schema_pydantic: Modelo Pydantic V2 com model_json_schema()
            **kwargs: Configurações adicionais para GenerateContentConfig
            
        Returns:
            str: JSON conforme schema_pydantic
        """
        if isinstance(imagem, PIL.Image.Image):
            img = imagem
        elif isinstance(imagem, str) and Path(imagem).is_file() or isinstance(imagem, Path) and imagem.exists():
            img = PIL.Image.open(imagem)
        else:
            response = requests.get(imagem)
            img = PIL.Image.open(io.BytesIO(response.content))
        
        # Converter schema Pydantic para format esperado pelo Gemini
        schema_json = schema_pydantic.model_json_schema()
        
        # Construir schema completo com $defs inlined
        response_schema = self._build_complete_schema(schema_json)
        
        # Criar config com Structured Output
        config = self._create_config(
            response_mime_type="application/json",
            response_schema=response_schema,
            **kwargs
        )
        
        response = self._tentar_gerar_conteudo(config, [img, prompt])
        if response is None:
            raise ValueError("Falha ao gerar conteúdo estruturado (resposta None)")
        return response.text

    def _documento_estruturado_inline(self, documento: Path, prompt: str, schema_pydantic, **kwargs):
        """
        Processa documento <20MB inline com base64 encoding.
        
        Args:
            documento: Caminho do arquivo
            prompt: Prompt de extração
            schema_pydantic: Modelo Pydantic V2
            **kwargs: Configurações adicionais
            
        Returns:
            str: JSON conforme schema
        """
        mime_type = self._get_mime_type(documento.suffix.lower())
        
        # Converter schema Pydantic para format esperado pelo Gemini
        schema_json = schema_pydantic.model_json_schema()
        
        # Construir schema completo com $defs inlined
        response_schema = self._build_complete_schema(schema_json)
        
        # Criar config com Structured Output
        config = self._create_config(
            response_mime_type="application/json",
            response_schema=response_schema,
            **kwargs
        )
        
        # Criar contents com documento e prompt
        contents = [
            types.Part.from_bytes(
                data=documento.read_bytes(),
                mime_type=mime_type
            ),
            prompt
        ]
        
        response = self._tentar_gerar_conteudo(config, contents)
        if response is None:
            raise ValueError("Falha ao gerar conteúdo estruturado (resposta None)")
        return response.text

    def _documento_estruturado_file_api(self, documento: Path, prompt: str, schema_pydantic, **kwargs):
        """
        Processa documento >20MB usando File API com upload temporário.
        
        O Gemini File API gerencia limpeza automática após 48h.
        
        Args:
            documento: Caminho do arquivo
            prompt: Prompt de extração
            schema_pydantic: Modelo Pydantic V2
            **kwargs: Configurações adicionais
            
        Returns:
            str: JSON conforme schema
            
        Raises:
            ValueError: Se upload falhar
            Exception: Se processamento falhar
        """
        try:
            # Upload do arquivo via File API
            logger.info(f"Uploading {documento.name} via Gemini File API (>20MB)...")
            
            with open(documento, "rb") as f:
                response = self._client.files.upload(file=f)
            
            file_id = response.name  # format: "files/..."
            logger.info(f"File uploaded: {file_id}")
            
            # Converter schema Pydantic para format esperado pelo Gemini
            schema_json = schema_pydantic.model_json_schema()
            
            # Construir schema completo com $defs inlined
            response_schema = self._build_complete_schema(schema_json)
            
            # Criar config com Structured Output
            config = self._create_config(
                response_mime_type="application/json",
                response_schema=response_schema,
                **kwargs
            )
            
            # Criar contents com file reference
            mime_type = self._get_mime_type(documento.suffix.lower())
            contents = [
                types.Part.from_uri(
                    uri=file_id,
                    mime_type=mime_type
                ),
                prompt
            ]
            
            # Processar com File API
            response = self._tentar_gerar_conteudo(config, contents)
            
            # Limpar arquivo uploadado
            try:
                self._client.files.delete(name=file_id)
                logger.info(f"File deleted: {file_id}")
            except Exception as e:
                logger.warning(f"Erro ao deletar arquivo {file_id}: {e}")
            
            if response is None:
                raise ValueError("Falha ao gerar conteúdo estruturado (resposta None)")
            return response.text
            
        except Exception as e:
            logger.error(f"Erro ao processar documento via File API: {e}")
            raise


class MistralService(ServiceBaseMistral):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._model_ocr = "mistral-ocr-2512"
        self._model_ai = "mistral-small-2506"
    
    def __str__(self):
        return "Serviço Mistral para realizar análises de texto, imagem e documentos."

    def _encode_image(self, image_path) -> str:
        """Codifica a imagem para base64."""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except FileNotFoundError:
            logger.error(f"Arquivo {image_path} não foi encontrado.")
            return None
        except Exception as e:
            logger.error(f"Erro ao codificar imagem: {e}")
            return None

    def _tentar_ocr(self, document_config):
        """Tenta executar OCR com o Mistral."""
        try:
            return self._client.ocr.process(
                model=self._model_ocr,
                document=document_config,
                include_image_base64=True
            )
        except Exception as e:
            logger.error(f"Erro OCR Mistral: {e}")
            return None

    def _tentar_chat(self, messages):
        """Tenta executar chat com o Mistral."""
        try:
            return self._client.chat.complete(
                model=self._model_ai,
                messages=messages
            )
        except Exception as e:
            logger.error(f"Erro Chat Mistral: {e}")
            return None

    def imagem(self, imagem, prompt: str=None, **kwargs):
        """Processa uma imagem e retorna o texto de acordo com o prompt."""
        
        # Determinar o caminho da imagem
        if isinstance(imagem, str) and Path(imagem).is_file():
            image_path = imagem
        elif isinstance(imagem, Path) and imagem.exists():
            image_path = str(imagem)
        else:
            # Se for URL, baixar a imagem
            try:
                response = requests.get(imagem)
                response.raise_for_status()
                # Salvar temporariamente para codificar
                temp_path = Path("temp_image.jpg")
                with open(temp_path, "wb") as f:
                    f.write(response.content)
                image_path = str(temp_path)
            except Exception as e:
                logger.error(f"Erro ao baixar imagem: {e}")
                return None

        # Codificar imagem
        base64_image = self._encode_image(image_path)
        if not base64_image:
            return None

        # Executar OCR
        ocr_response = self._tentar_ocr({
            "type": "image_url",
            "image_url": f"data:image/jpeg;base64,{base64_image}"
        })

        if not ocr_response or not ocr_response.pages:
            return None

        # Se há prompt específico, usar IA para analisar o texto extraído
        if prompt:
            extracted_text = ocr_response.pages[0].markdown
            messages = [
                {"role": "user", "content": f"Texto extraído: {extracted_text}\n\nPrompt: {prompt}"}
            ]
            chat_response = self._tentar_chat(messages)
            return chat_response.choices[0].message.content if chat_response else extracted_text
        
        return ocr_response.pages[0].markdown

    def texto(self, prompt: str, **kwargs):
        """Processa texto usando o modelo de chat do Mistral."""
        messages = [{"role": "user", "content": prompt}]
        response = self._tentar_chat(messages)
        return response.choices[0].message.content if response else None

    def documento(self, documento: Path, prompt: str=None, **kwargs):
        """Processa um documento e retorna o texto de acordo com o prompt."""
        
        if not isinstance(documento, Path):
            raise TypeError("O parâmetro 'documento' deve ser do tipo Path.")
        if not documento.exists():
            raise FileNotFoundError(f"O arquivo '{documento}' não foi encontrado.")
        if not documento.is_file():
            raise ValueError(f"O caminho '{documento}' não é um arquivo válido.")

        try:
            # Upload do arquivo
            uploaded_file = self._client.files.upload(
                file={
                    "file_name": str(documento),
                    "content": open(documento, "rb"),
                },
                purpose="ocr"
            )

            # Verificar se o arquivo foi carregado
            self._client.files.retrieve(file_id=uploaded_file.id)

            # Obter URL assinada
            signed_url = self._client.files.get_signed_url(file_id=uploaded_file.id)

            # Executar OCR
            ocr_response = self._tentar_ocr({
                "type": "document_url",
                "document_url": signed_url.url,
            })

            if not ocr_response or not ocr_response.pages:
                return None

            # Se há prompt específico, usar IA para analisar o texto extraído
            if prompt:
                extracted_text = ocr_response.pages[0].markdown
                messages = [
                    {"role": "user", "content": f"Texto extraído: {extracted_text}\n\nPrompt: {prompt}"}
                ]
                chat_response = self._tentar_chat(messages)
                return chat_response.choices[0].message.content if chat_response else extracted_text
            
            return ocr_response.pages[0].markdown

        except Exception as e:
            logger.error(f"Erro ao processar documento: {e}")
            return None

    def documento_na_internet(self, url_documento: str, prompt: str, **kwargs):
        """Processa um documento da internet e retorna o texto de acordo com o prompt."""
        
        try:
            # Executar OCR diretamente na URL
            ocr_response = self._tentar_ocr({
                "type": "document_url",
                "document_url": url_documento,
            })

            if not ocr_response or not ocr_response.pages:
                return None

            # Se há prompt específico, usar IA para analisar o texto extraído
            if prompt:
                extracted_text = ocr_response.pages[0].markdown
                messages = [
                    {"role": "user", "content": f"Texto extraído: {extracted_text}\n\nPrompt: {prompt}"}
                ]
                chat_response = self._tentar_chat(messages)
                return chat_response.choices[0].message.content if chat_response else extracted_text
            
            return ocr_response.pages[0].markdown

        except Exception as e:
            logger.error(f"Erro ao processar documento da internet: {e}")
            return None
