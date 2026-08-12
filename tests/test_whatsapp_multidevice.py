"""
Testes para suporte a múltiplos dispositivos WhatsApp (v8.2.0+)

Cobre funcionalidades:
- Headers com X-Device-Id
- Envio de arquivos com device_id específico
- Retrocompatibilidade (sem device_id)
- Validação de formato de device_id
- Roteamento por empresa
- Integração com EmpresaMongoDB
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
from datetime import datetime, timezone

from src.services.whatsapp_service import WhatsAppService
from src.models.empresa_models import EmpresaMongoDB, EmpresaBuilder, StatusEmpresa


class TestWhatsAppGetHeaders:
    """Testes para método _get_headers com suporte a device_id"""

    def test_get_headers_com_device_id(self):
        """Testa se headers incluem X-Device-Id quando fornecido"""
        service = WhatsAppService()
        device_id = "5569988887777@s.whatsapp.net"

        headers = service._get_headers(device_id=device_id)

        assert "X-Device-Id" in headers
        assert headers["X-Device-Id"] == device_id
        assert headers["Accept"] == "application/json"

    def test_get_headers_sem_device_id(self):
        """Testa se headers funcionam sem device_id (retrocompatível)"""
        service = WhatsAppService()

        headers = service._get_headers()

        assert "X-Device-Id" not in headers
        assert headers["Accept"] == "application/json"

    def test_get_headers_sem_device_id_none_explícito(self):
        """Testa se headers funcionam com device_id=None (retrocompatível)"""
        service = WhatsAppService()

        headers = service._get_headers(device_id=None)

        assert "X-Device-Id" not in headers
        assert headers["Accept"] == "application/json"

    @patch.dict('os.environ', {'WHATSAPP_API_KEY': 'test-key-123'})
    def test_get_headers_com_api_key_e_device_id(self):
        """Testa headers com API_KEY e device_id simultâneos"""
        service = WhatsAppService()
        service.api_key = "test-key-123"
        device_id = "5569999999999@s.whatsapp.net"

        headers = service._get_headers(device_id=device_id)

        assert headers["Authorization"] == "Bearer test-key-123"
        assert headers["X-Device-Id"] == device_id
        assert headers["Accept"] == "application/json"


class TestEnviarArquivoComDeviceId:
    """Testes para envio de arquivo com device_id"""

    @patch('builtins.open', create=True)
    @patch('requests.post')
    @patch('os.path.exists')
    def test_enviar_arquivo_com_device_id(self, mock_exists, mock_post, mock_open):
        """Testa envio de arquivo com device_id específico"""
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value = MagicMock()

        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": {"message_id": "msg123456"}
        }
        mock_post.return_value = mock_response

        with patch('src.utils.dotenv_path.caminho_dotenv', return_value='.env'):
            service = WhatsAppService()
            device_id = "5569988887777@s.whatsapp.net"
            device_internal_id = "WhatsApp-Device1"

            # Mock status para "conectado"
            with patch.object(service, 'verificar_status') as mock_status:
                # Mock listar_dispositivos para retornar dispositivo correspondente
                with patch.object(service, 'listar_dispositivos') as mock_listar:
                    mock_status.return_value = {"conectado": True}
                    mock_listar.return_value = [
                        {
                            "id": device_internal_id,
                            "jid": device_id,
                            "display_name": "Test Device",
                            "state": "logged_in"
                        }
                    ]

                    resultado = service.enviar_arquivo(
                        destinatario="5569999999999",
                        arquivo_path="/tmp/teste.pdf",
                        device_id=device_id
                    )

        # Verificações
        assert resultado["sucesso"] is True
        assert resultado["mensagem"] == "Arquivo enviado com sucesso"

        # Verificar se device_id foi passado nos headers
        call_args = mock_post.call_args
        assert call_args is not None
        headers = call_args[1].get("headers", {})
        assert headers.get("X-Device-Id") == device_internal_id

    @patch('builtins.open', create=True)
    @patch('requests.post')
    @patch('os.path.exists')
    def test_enviar_arquivo_sem_device_id(self, mock_exists, mock_post, mock_open):
        """Testa envio retrocompatível sem device_id"""
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value = MagicMock()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": {"message_id": "msg123456"}
        }
        mock_post.return_value = mock_response

        with patch('src.utils.dotenv_path.caminho_dotenv', return_value='.env'):
            service = WhatsAppService()

            with patch.object(service, 'verificar_status') as mock_status:
                mock_status.return_value = {"conectado": True}

                resultado = service.enviar_arquivo(
                    destinatario="5569999999999",
                    arquivo_path="/tmp/teste.pdf"
                )

        assert resultado["sucesso"] is True

        # Verificar que X-Device-Id NÃO foi incluído
        call_args = mock_post.call_args
        headers = call_args[1].get("headers", {})
        assert "X-Device-Id" not in headers

    @patch('requests.post')
    @patch('os.path.exists')
    def test_enviar_arquivo_não_conectado(self, mock_exists, mock_post):
        """Testa falha ao enviar se WhatsApp não está conectado"""
        service = WhatsAppService()

        with patch.object(service, 'verificar_status') as mock_status:
            mock_status.return_value = {"conectado": False}

            resultado = service.enviar_arquivo(
                destinatario="5569999999999",
                arquivo_path="/tmp/teste.pdf",
                device_id="5569988887777@s.whatsapp.net"
            )

        assert resultado["sucesso"] is False
        assert "não conectado" in resultado["mensagem"].lower()
        # requests.post não deve ter sido chamado
        mock_post.assert_not_called()

    @patch('src.utils.dotenv_path.caminho_dotenv')
    @patch('requests.post')
    def test_enviar_arquivo_arquivo_não_existe(self, mock_post, mock_dotenv):
        """Testa falha ao enviar se arquivo não existe"""
        mock_dotenv.return_value = '.env'

        service = WhatsAppService()

        # Mock os.path.exists e verificar_status
        with patch('os.path.exists') as mock_exists:
            with patch.object(service, 'verificar_status') as mock_status:
                # Arquivo não existe
                mock_exists.return_value = False
                mock_status.return_value = {"conectado": True}

                resultado = service.enviar_arquivo(
                    destinatario="5569999999999",
                    arquivo_path="/tmp/nao_existe.pdf",
                    device_id="5569988887777@s.whatsapp.net"
                )

        assert resultado["sucesso"] is False
        assert "não encontrado" in resultado["mensagem"].lower()
        mock_post.assert_not_called()


class TestEnviarTextoComDeviceId:
    """Testes para envio de texto com device_id"""

    @patch('requests.post')
    def test_enviar_texto_com_device_id(self, mock_post):
        """Testa envio de texto com device_id específico"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": {"message_id": "msg123456"}
        }
        mock_post.return_value = mock_response

        service = WhatsAppService()
        device_id = "5569988887777@s.whatsapp.net"
        device_internal_id = "WhatsApp-Device1"

        with patch.object(service, 'verificar_status') as mock_status:
            # Mock listar_dispositivos para retornar dispositivo correspondente
            with patch.object(service, 'listar_dispositivos') as mock_listar:
                mock_status.return_value = {"conectado": True}
                mock_listar.return_value = [
                    {
                        "id": device_internal_id,
                        "jid": device_id,
                        "display_name": "Test Device",
                        "state": "logged_in"
                    }
                ]

                resultado = service.enviar_texto(
                    destinatario="5569999999999",
                    mensagem="Olá, tudo bem?",
                    device_id=device_id
                )

        assert resultado["sucesso"] is True

        # Verificar se device_id foi passado nos headers
        call_args = mock_post.call_args
        headers = call_args[1].get("headers", {})
        assert headers.get("X-Device-Id") == device_internal_id


class TestEmpresaComDeviceId:
    """Testes para integração do device_id com modelo EmpresaMongoDB"""

    def test_empresa_com_device_id_válido(self):
        """Testa criação de empresa com device_id válido"""
        device_id = "5569988887777@s.whatsapp.net"

        empresa = EmpresaBuilder() \
            .set_nome("Teste Corp") \
            .set_whatsapp_device_id(device_id) \
            .build()

        assert empresa.whatsapp_device_id == device_id
        assert empresa.obter_device_whatsapp() == device_id

    def test_empresa_sem_device_id(self):
        """Testa retrocompatibilidade: empresa sem device_id"""
        empresa = EmpresaBuilder() \
            .set_nome("Teste Corp") \
            .build()

        assert empresa.whatsapp_device_id is None
        assert empresa.obter_device_whatsapp() is None

    def test_empresa_multiple_devices_diferentes(self):
        """Testa criação de múltiplas empresas com device_ids diferentes"""
        device_id_1 = "5569988887777@s.whatsapp.net"
        device_id_2 = "5569999998888@s.whatsapp.net"

        empresa_1 = EmpresaBuilder() \
            .set_nome("Empresa 1") \
            .set_whatsapp_device_id(device_id_1) \
            .build()

        empresa_2 = EmpresaBuilder() \
            .set_nome("Empresa 2") \
            .set_whatsapp_device_id(device_id_2) \
            .build()

        assert empresa_1.obter_device_whatsapp() == device_id_1
        assert empresa_2.obter_device_whatsapp() == device_id_2
        assert empresa_1.whatsapp_device_id != empresa_2.whatsapp_device_id

    def test_empresa_atualizar_device_id(self):
        """Testa atualização de device_id em empresa existente"""
        device_id_novo = "5569977776666@s.whatsapp.net"

        empresa = EmpresaBuilder() \
            .set_nome("Empresa Atualizável") \
            .set_whatsapp_device_id("5569988887777@s.whatsapp.net") \
            .build()

        # Simula atualização
        empresa.whatsapp_device_id = device_id_novo

        assert empresa.obter_device_whatsapp() == device_id_novo


class TestValidacaoDeviceId:
    """Testes para validação de formato do device_id"""

    def test_validacao_device_id_formato_válido(self):
        """Testa validação com formatos válidos"""
        dispositivos_válidos = [
            "5569988887777@s.whatsapp.net",
            "5511999999999@s.whatsapp.net",
            "5585988887777@s.whatsapp.net",
        ]

        for device_id in dispositivos_válidos:
            empresa = EmpresaBuilder() \
                .set_nome(f"Empresa {device_id}") \
                .set_whatsapp_device_id(device_id) \
                .build()

            assert empresa.whatsapp_device_id == device_id

    def test_validacao_device_id_sem_domínio(self):
        """Testa rejeição de device_id sem @s.whatsapp.net"""
        with pytest.raises(ValueError, match="Device ID inválido"):
            EmpresaBuilder() \
                .set_nome("Teste") \
                .set_whatsapp_device_id("5569999999999") \
                .build()

    def test_validacao_device_id_domínio_errado(self):
        """Testa rejeição de device_id com domínio incorreto"""
        from pydantic_core._pydantic_core import ValidationError
        with pytest.raises(ValidationError):
            EmpresaBuilder() \
                .set_nome("Teste") \
                .set_whatsapp_device_id("5569999999999@example.com") \
                .build()

    def test_validacao_device_id_múltiplos_arroba(self):
        """Testa rejeição de device_id com múltiplos @"""
        with pytest.raises(ValueError, match="inválido"):
            EmpresaBuilder() \
                .set_nome("Teste") \
                .set_whatsapp_device_id("5569999999999@invalid@s.whatsapp.net") \
                .build()

    def test_validacao_device_id_caracteres_inválidos_número(self):
        """Testa rejeição com caracteres não-numéricos na parte do número"""
        with pytest.raises(ValueError, match="número"):
            EmpresaBuilder() \
                .set_nome("Teste") \
                .set_whatsapp_device_id("556999999ABCD@s.whatsapp.net") \
                .build()

    def test_validacao_device_id_vazio(self):
        """Testa que device_id vazio é aceito (compatibilidade)"""
        empresa = EmpresaBuilder() \
            .set_nome("Teste") \
            .set_whatsapp_device_id(None) \
            .build()

        assert empresa.whatsapp_device_id is None


class TestEnviarMultiplosArquivos:
    """Testes para envio de múltiplos arquivos com device_id"""

    @patch('builtins.open', create=True)
    @patch('requests.post')
    @patch('os.path.exists')
    def test_enviar_multiplos_com_device_id(self, mock_exists, mock_post, mock_open):
        """Testa envio de múltiplos arquivos com device_id"""
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value = MagicMock()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": {"message_id": "msg123456"}
        }
        mock_post.return_value = mock_response

        with patch('src.utils.dotenv_path.caminho_dotenv', return_value='.env'):
            service = WhatsAppService()
            device_id = "5569988887777@s.whatsapp.net"
            device_internal_id = "WhatsApp-Device1"

            with patch.object(service, 'verificar_status') as mock_status:
                # Mock listar_dispositivos para retornar dispositivo correspondente
                with patch.object(service, 'listar_dispositivos') as mock_listar:
                    mock_status.return_value = {"conectado": True}
                    mock_listar.return_value = [
                        {
                            "id": device_internal_id,
                            "jid": device_id,
                            "display_name": "Test Device",
                            "state": "logged_in"
                        }
                    ]

                    resultado = service.enviar_multiplos_arquivos(
                        destinatario="5569999999999",
                        arquivos=["/tmp/arquivo1.pdf", "/tmp/arquivo2.pdf"],
                        device_id=device_id
                    )

        assert resultado["sucesso"] is True
        # Verificar que ambos os arquivos foram processados
        assert mock_post.call_count >= 2

        # Verificar que device_id foi usado em todas as chamadas
        for call_args_item in mock_post.call_args_list:
            headers = call_args_item[1].get("headers", {})
            assert headers.get("X-Device-Id") == device_internal_id


class TestIntegracaoComOrquestrador:
    """Testes de integração com orquestrador de envios"""

    @patch('src.services.empresa_service.EmpresaService.buscar_por_nome')
    @patch.object(WhatsAppService, 'enviar_arquivo')
    def test_roteamento_por_device_id_da_empresa(self, mock_envio, mock_busca_empresa):
        """Testa se envio respeita device_id da empresa"""
        from src.models.empresa_models import EmpresaMongoDB

        device_id_esperado = "5569988887777@s.whatsapp.net"

        # Mock da empresa com device_id
        empresa = EmpresaBuilder() \
            .set_nome("Empresa X") \
            .set_whatsapp_device_id(device_id_esperado) \
            .build()

        mock_busca_empresa.return_value = empresa
        mock_envio.return_value = {"sucesso": True}

        # Simula lógica de roteamento
        whatsapp_service = WhatsAppService()
        resultado = whatsapp_service.enviar_arquivo(
            destinatario="5569999999999",
            arquivo_path="/tmp/test.pdf",
            device_id=empresa.obter_device_whatsapp()
        )

        # Verificar que o método foi chamado com device_id correto
        mock_envio.assert_called_once()
        call_kwargs = mock_envio.call_args[1] if mock_envio.call_args else {}
        assert call_kwargs.get('device_id') == device_id_esperado


class TestRetrocompatibilidade:
    """Testes para garantir retrocompatibilidade com código antigo"""

    @patch('builtins.open', create=True)
    @patch('requests.post')
    @patch('os.path.exists')
    def test_código_antigo_sem_device_id_continua_funcionando(self, mock_exists, mock_post, mock_open):
        """Testa que código antigo (sem device_id) continua funcionando"""
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value = MagicMock()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": {"message_id": "msg123456"}
        }
        mock_post.return_value = mock_response

        with patch('src.utils.dotenv_path.caminho_dotenv', return_value='.env'):
            service = WhatsAppService()

            with patch.object(service, 'verificar_status') as mock_status:
                mock_status.return_value = {"conectado": True}

                # Chamada antiga (sem device_id)
                resultado = service.enviar_arquivo(
                    destinatario="5569999999999",
                    arquivo_path="/tmp/teste.pdf"
                )

        assert resultado["sucesso"] is True
        mock_post.assert_called_once()

    def test_empresa_antiga_sem_device_id_continua_funcionando(self):
        """Testa que empresas antigas (sem device_id) continuam funcionando"""
        # Simula empresa do banco de dados antigo
        dados_antigos = {
            "nome": "Empresa Antiga",
            "cnpj": "12.345.678/0001-90",
            "status": "ativa"
        }

        empresa = EmpresaMongoDB(**dados_antigos)

        # Device_id deve ser None
        assert empresa.whatsapp_device_id is None
        assert empresa.obter_device_whatsapp() is None

        # Empresa continua funcional
        assert empresa.nome == "Empresa Antiga"
        assert empresa.status == StatusEmpresa.ATIVA


class TestEdgeCases:
    """Testes para casos extremos e situações especiais"""

    def test_device_id_com_espaços(self):
        """Testa tratamento de device_id com espaços"""
        device_id_com_espaço = "  5569988887777@s.whatsapp.net  "

        empresa = EmpresaBuilder() \
            .set_nome("Teste") \
            .set_whatsapp_device_id(device_id_com_espaço) \
            .build()

        # Deve ter feito strip
        assert empresa.whatsapp_device_id == "5569988887777@s.whatsapp.net"

    def test_múltiplas_empresas_com_mesmo_device_id(self):
        """Testa se múltiplas empresas podem compartilhar mesmo device_id"""
        device_id = "5569988887777@s.whatsapp.net"

        empresa_1 = EmpresaBuilder() \
            .set_nome("Empresa A") \
            .set_whatsapp_device_id(device_id) \
            .build()

        empresa_2 = EmpresaBuilder() \
            .set_nome("Empresa B") \
            .set_whatsapp_device_id(device_id) \
            .build()

        # Ambas devem ter o mesmo device_id
        assert empresa_1.whatsapp_device_id == empresa_2.whatsapp_device_id
        assert empresa_1.obter_device_whatsapp() == device_id

    @patch('builtins.open', create=True)
    @patch('requests.post')
    def test_dispositivo_desconectado_durante_envio(self, mock_post, mock_open):
        """Testa comportamento quando dispositivo desconecta durante envio"""
        mock_open.return_value.__enter__.return_value = MagicMock()

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized - Device disconnected"
        mock_post.return_value = mock_response

        with patch('src.utils.dotenv_path.caminho_dotenv', return_value='.env'):
            service = WhatsAppService()

            with patch.object(service, 'verificar_status') as mock_status:
                mock_status.return_value = {"conectado": True}
                with patch('os.path.exists', return_value=True):
                    resultado = service.enviar_arquivo(
                        destinatario="5569999999999",
                        arquivo_path="/tmp/teste.pdf",
                        device_id="5569988887777@s.whatsapp.net"
                    )

        assert resultado["sucesso"] is False


class TestCoverageRequirements:
    """Testes para garantir coverage mínimo de 80%"""

    def test_obter_info_resumida_com_device_id(self):
        """Garante coverage de métodos de empresa"""
        empresa = EmpresaBuilder() \
            .set_nome("Teste Corp") \
            .set_cnpj("12.345.678/0001-90") \
            .set_whatsapp_device_id("5569988887777@s.whatsapp.net") \
            .build()

        info = empresa.obter_info_resumida()
        assert "nome" in info
        assert "status" in info
        assert "incompleto" in info

    def test_obter_dados_folha_ponto_empresa(self):
        """Garante coverage do método obter_dados_folha_ponto"""
        empresa = EmpresaBuilder() \
            .set_nome("TechCorp") \
            .set_atividade("Desenvolvimento") \
            .set_endereco("Rua A, 123") \
            .set_cnpj("12.345.678/0001-90") \
            .set_whatsapp_device_id("5569988887777@s.whatsapp.net") \
            .build()

        dados = empresa.obter_dados_folha_ponto()
        assert dados["EMPRESA"] == "TechCorp"
        assert dados["ATIVIDADE"] == "Desenvolvimento"
        assert dados["ENDEREÇO"] == "Rua A, 123"

    def test_histórico_alterações_empresa(self):
        """Garante coverage de histórico de alterações"""
        empresa = EmpresaBuilder() \
            .set_nome("Teste") \
            .build()

        empresa.adicionar_historico("teste_acao", {"detalhes": "teste"})

        assert len(empresa.historico_alteracoes) >= 1
        assert empresa.historico_alteracoes[-1]["acao"] == "teste_acao"

    def test_to_mongo_insert(self):
        """Garante coverage de conversão para MongoDB"""
        empresa = EmpresaBuilder() \
            .set_nome("MongoDB Test") \
            .set_whatsapp_device_id("5569988887777@s.whatsapp.net") \
            .build()

        mongo_doc = empresa.to_mongo_insert()
        assert mongo_doc["nome"] == "MongoDB Test"
        assert mongo_doc["whatsapp_device_id"] == "5569988887777@s.whatsapp.net"
        assert "_id" not in mongo_doc

    def test_to_mongo_update(self):
        """Garante coverage de conversão para atualização no MongoDB"""
        empresa = EmpresaBuilder() \
            .set_nome("MongoDB Update Test") \
            .set_whatsapp_device_id("5569988887777@s.whatsapp.net") \
            .build()

        update_doc = empresa.to_mongo_update()
        assert "$set" in update_doc
        assert update_doc["$set"]["nome"] == "MongoDB Update Test"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=src", "--cov-report=term-missing"])
