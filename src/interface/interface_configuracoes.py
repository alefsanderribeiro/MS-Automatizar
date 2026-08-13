"""
Interface de Configuracoes

Este modulo fornece uma interface interativa para gerenciar
as configuracoes do sistema atraves do menu principal.
"""

from typing import Optional
from src.utils.logger_config import logger
from src.services.config_service import (
    ConfigService,
    TipoConfiguracao,
    ModoOperacao,
    obter_config_service
)
from src.interface.core.components import (
    MenuBuilder,
    exibir_cabecalho,
    exibir_sucesso,
    exibir_erro,
    exibir_aviso,
    exibir_info,
    exibir_painel,
    pausar,
    pedir_confirmacao,
    pedir_texto,
    pedir_selecao,
    pedir_inteiro,
)
from src.interface.core.theme import console, ICONES


def Interface_Configuracoes():
    """Interface principal de Configuracoes"""

    (
        MenuBuilder("CONFIGURACOES", ICONES["config"])
        .adicionar("Configuracoes do MongoDB", _config_mongodb, ICONES["banco_dados"])
        .adicionar("Configuracoes de APIs (IA)", _config_apis, ICONES["api"])
        .adicionar("Configuracoes do Sistema", _config_sistema, ICONES["config"])
        .adicionar("Configuracoes do Zoho Mail (E-mail)", _config_zoho_mail, ICONES["email"])
        .separador()
        .adicionar("Ver todas as configuracoes", _ver_todas_configs, ICONES["listar"])
        .adicionar("Validar configuracoes", _validar_configs, ICONES["check"])
        .adicionar("Restaurar configuracoes padrao", _restaurar_padrao, ICONES["atualizar"])
        .com_voltar("Voltar ao Menu Principal")
        .executar()
    )


def _config_mongodb():
    """Configuracoes do MongoDB"""
    config_service = obter_config_service()

    def _exibir_valores_atuais():
        """Exibe os valores atuais do MongoDB"""
        mongo_uri = config_service.obter("MONGO_URI") or "(nao configurado)"
        mongo_db = config_service.obter("MONGO_DATABASE_NAME") or "(nao configurado)"
        max_pool = config_service.obter("MONGO_MAX_POOL_SIZE") or "100"
        min_pool = config_service.obter("MONGO_MIN_POOL_SIZE") or "10"

        # Ocultar URI para exibicao
        if mongo_uri != "(nao configurado)" and len(mongo_uri) > 30:
            uri_display = mongo_uri[:25] + "..."
        else:
            uri_display = mongo_uri

        conteudo = f"""[cyan]Valores atuais:[/cyan]

[bold]URI:[/bold] {uri_display}
[bold]Database:[/bold] {mongo_db}
[bold]Pool maximo:[/bold] {max_pool}
[bold]Pool minimo:[/bold] {min_pool}"""

        exibir_painel(conteudo, "Configuracoes Atuais do MongoDB", "cyan")
        pausar()

    def _alterar_uri():
        """Altera a URI de conexao do MongoDB"""
        mongo_uri = config_service.obter("MONGO_URI") or "(nao configurado)"
        uri_display = mongo_uri[:25] + "..." if len(mongo_uri) > 30 else mongo_uri

        exibir_info(f"URI atual: {uri_display}")
        console.print("[dim]Exemplo: mongodb://localhost:27017[/dim]")

        novo_valor = pedir_texto("Nova URI", obrigatorio=False)
        if novo_valor:
            config_service.definir("MONGO_URI", novo_valor)
            exibir_sucesso("URI atualizada!")
        pausar()

    def _alterar_database():
        """Altera o nome do banco de dados"""
        mongo_db = config_service.obter("MONGO_DATABASE_NAME") or "(nao configurado)"

        exibir_info(f"Database atual: {mongo_db}")

        novo_valor = pedir_texto("Novo nome do banco", obrigatorio=False)
        if novo_valor:
            config_service.definir("MONGO_DATABASE_NAME", novo_valor)
            exibir_sucesso("Nome do banco atualizado!")
        pausar()

    def _alterar_pool_max():
        """Altera o tamanho maximo do pool"""
        max_pool = config_service.obter("MONGO_MAX_POOL_SIZE") or "100"

        exibir_info(f"Pool maximo atual: {max_pool}")

        novo_valor = pedir_inteiro("Novo valor", obrigatorio=False, minimo=1)
        if novo_valor is not None:
            config_service.definir("MONGO_MAX_POOL_SIZE", str(novo_valor))
            exibir_sucesso("Pool maximo atualizado!")
        pausar()

    def _alterar_pool_min():
        """Altera o tamanho minimo do pool"""
        min_pool = config_service.obter("MONGO_MIN_POOL_SIZE") or "10"

        exibir_info(f"Pool minimo atual: {min_pool}")

        novo_valor = pedir_inteiro("Novo valor", obrigatorio=False, minimo=1)
        if novo_valor is not None:
            config_service.definir("MONGO_MIN_POOL_SIZE", str(novo_valor))
            exibir_sucesso("Pool minimo atualizado!")
        pausar()

    def _testar_conexao():
        """Testa a conexao com MongoDB"""
        exibir_info("Testando conexao com MongoDB...")

        try:
            from src.services.mongodb_connection import verificar_conexao_mongodb, mongodb_pool

            if verificar_conexao_mongodb():
                health = mongodb_pool.health_check()

                conteudo = f"""[green]Conexao bem-sucedida![/green]

[bold]Latencia:[/bold] {health.get('latencia_ms', 'N/A')}ms
[bold]Conexoes ativas:[/bold] {health.get('conexoes_ativas', 'N/A')}
[bold]Database:[/bold] {health.get('database', 'N/A')}"""

                exibir_painel(conteudo, "Teste de Conexao MongoDB", "green")
            else:
                exibir_erro("Falha na conexao com MongoDB")
                exibir_aviso("Verifique se o MongoDB esta rodando e a URI esta correta")
        except Exception as e:
            exibir_erro(f"Erro ao testar conexao: {e}")

        pausar()

    (
        MenuBuilder("CONFIGURACOES DO MONGODB", ICONES["banco_dados"])
        .adicionar("Ver valores atuais", _exibir_valores_atuais, ICONES["info"])
        .separador()
        .adicionar("Alterar URI de conexao", _alterar_uri, ICONES["editar"])
        .adicionar("Alterar nome do banco de dados", _alterar_database, ICONES["editar"])
        .adicionar("Alterar tamanho do pool (maximo)", _alterar_pool_max, ICONES["editar"])
        .adicionar("Alterar tamanho do pool (minimo)", _alterar_pool_min, ICONES["editar"])
        .separador()
        .adicionar("Testar conexao", _testar_conexao, ICONES["check"])
        .com_voltar("Voltar")
        .executar()
    )


def _ocultar_chave(valor: Optional[str]) -> str:
    """Oculta uma chave API para exibicao"""
    if not valor:
        return "(nao configurado)"
    if len(valor) > 8:
        return f"{valor[:4]}...{valor[-4:]}"
    return "****"


def _config_apis():
    """Configuracoes de APIs de IA"""
    config_service = obter_config_service()

    def _exibir_valores_atuais():
        """Exibe os valores atuais das APIs"""
        gemini = config_service.obter("KEY_API_GEMINI")
        mistral = config_service.obter("KEY_API_MISTRAL")

        gemini_display = _ocultar_chave(gemini)
        mistral_display = _ocultar_chave(mistral)

        conteudo = f"""[cyan]Valores atuais:[/cyan]

[bold]Google Gemini:[/bold] {gemini_display}
[bold]Mistral AI:[/bold] {mistral_display}

[dim]As APIs sao usadas para processar PDFs preenchidos com IA.[/dim]"""

        exibir_painel(conteudo, "Configuracoes Atuais de APIs", "cyan")
        pausar()

    def _config_gemini():
        """Configura a API do Google Gemini"""
        console.print("\n[bold cyan]Configurar API do Google Gemini[/bold cyan]")
        console.print("[dim]Obtenha sua chave em: https://makersuite.google.com/app/apikey[/dim]\n")

        nova_chave = pedir_texto("Nova chave", obrigatorio=False)
        if nova_chave:
            config_service.definir("KEY_API_GEMINI", nova_chave)
            exibir_sucesso("Chave do Gemini atualizada!")
        pausar()

    def _config_mistral():
        """Configura a API do Mistral AI"""
        console.print("\n[bold cyan]Configurar API do Mistral AI[/bold cyan]")
        console.print("[dim]Obtenha sua chave em: https://console.mistral.ai/[/dim]\n")

        nova_chave = pedir_texto("Nova chave", obrigatorio=False)
        if nova_chave:
            config_service.definir("KEY_API_MISTRAL", nova_chave)
            exibir_sucesso("Chave do Mistral atualizada!")
        pausar()

    def _testar_apis():
        """Testa as APIs configuradas"""
        exibir_info("Testando APIs configuradas...")
        console.print()

        # Testar Gemini
        gemini_key = config_service.obter("KEY_API_GEMINI")
        if gemini_key:
            try:
                import google.genai as genai
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel('gemini-2.5-flash')
                response = model.generate_content("Responda apenas: OK")
                exibir_sucesso("Google Gemini: Funcionando")
            except Exception as e:
                exibir_erro(f"Google Gemini: {e}")
        else:
            exibir_aviso("Google Gemini: Nao configurado")

        # Testar Mistral
        mistral_key = config_service.obter("KEY_API_MISTRAL")
        if mistral_key:
            exibir_aviso("Mistral AI: Configurado (teste nao implementado)")
        else:
            exibir_aviso("Mistral AI: Nao configurado")

        pausar()

    (
        MenuBuilder("CONFIGURACOES DE APIs (IA)", ICONES["api"])
        .adicionar("Ver valores atuais", _exibir_valores_atuais, ICONES["info"])
        .separador()
        .adicionar("Configurar API do Google Gemini", _config_gemini, ICONES["editar"])
        .adicionar("Configurar API do Mistral AI", _config_mistral, ICONES["editar"])
        .separador()
        .adicionar("Testar APIs configuradas", _testar_apis, ICONES["check"])
        .com_voltar("Voltar")
        .executar()
    )


def _config_sistema():
    """Configuracoes gerais do sistema"""
    config_service = obter_config_service()

    def _exibir_valores_atuais():
        """Exibe os valores atuais do sistema"""
        modo = config_service.obter("MODO_OPERACAO") or "mongodb"
        log_level = config_service.obter("LOG_LEVEL") or "INFO"
        dir_saida = config_service.obter("DIRETORIO_SAIDA") or "(padrao do sistema)"

        conteudo = f"""[cyan]Valores atuais:[/cyan]

[bold]Modo de operacao:[/bold] {modo}
[bold]Nivel de log:[/bold] {log_level}
[bold]Diretorio de saida:[/bold] {dir_saida}"""

        exibir_painel(conteudo, "Configuracoes Atuais do Sistema", "cyan")
        pausar()

    def _alterar_modo():
        """Altera o modo de operacao"""
        modo_atual = config_service.obter("MODO_OPERACAO") or "mongodb"

        exibir_info(f"Modo atual: {modo_atual}")

        opcoes = [
            "mongodb - Usar apenas MongoDB (recomendado)",
            "excel - Usar apenas planilhas Excel (legado)",
            "ambos - Usar MongoDB e Excel simultaneamente"
        ]

        escolha = pedir_selecao("Escolha o modo de operacao", opcoes)
        if escolha:
            # Extrair apenas o prefixo
            modo_escolhido = escolha.split(" - ")[0]
            config_service.definir("MODO_OPERACAO", modo_escolhido)
            exibir_sucesso(f"Modo alterado para: {modo_escolhido}")
        pausar()

    def _alterar_log():
        """Altera o nivel de log"""
        log_atual = config_service.obter("LOG_LEVEL") or "INFO"

        exibir_info(f"Nivel atual: {log_atual}")

        opcoes = [
            "DEBUG - Todos os logs (muito detalhado)",
            "INFO - Logs informativos (recomendado)",
            "WARNING - Apenas avisos e erros",
            "ERROR - Apenas erros"
        ]

        escolha = pedir_selecao("Escolha o nivel de log", opcoes)
        if escolha:
            # Extrair apenas o prefixo
            nivel_escolhido = escolha.split(" - ")[0]
            config_service.definir("LOG_LEVEL", nivel_escolhido)
            exibir_sucesso(f"Nivel de log alterado para: {nivel_escolhido}")
        pausar()

    def _alterar_diretorio():
        """Altera o diretorio de saida"""
        dir_atual = config_service.obter("DIRETORIO_SAIDA") or "(padrao do sistema)"

        exibir_info(f"Diretorio atual: {dir_atual}")
        console.print("[dim]Exemplo: C:\\Users\\Usuario\\Documentos\\MS-Automatizar\\output[/dim]\n")

        novo_dir = pedir_texto("Novo diretorio", obrigatorio=False)
        if novo_dir:
            import os
            if os.path.isdir(novo_dir):
                config_service.definir("DIRETORIO_SAIDA", novo_dir)
                exibir_sucesso("Diretorio de saida atualizado!")
            else:
                criar = pedir_confirmacao(f"Diretorio nao existe. Criar?", padrao=False)
                if criar:
                    try:
                        os.makedirs(novo_dir, exist_ok=True)
                        config_service.definir("DIRETORIO_SAIDA", novo_dir)
                        exibir_sucesso("Diretorio criado e configurado!")
                    except Exception as e:
                        exibir_erro(f"Erro ao criar diretorio: {e}")
        pausar()

    (
        MenuBuilder("CONFIGURACOES DO SISTEMA", ICONES["config"])
        .adicionar("Ver valores atuais", _exibir_valores_atuais, ICONES["info"])
        .separador()
        .adicionar("Alterar modo de operacao", _alterar_modo, ICONES["editar"])
        .adicionar("Alterar nivel de log", _alterar_log, ICONES["editar"])
        .adicionar("Alterar diretorio de saida", _alterar_diretorio, ICONES["editar"])
        .com_voltar("Voltar")
        .executar()
    )


def _config_zoho_mail():
    """Configuracoes do Zoho Mail com OAuth2 automatizado"""
    from src.services.zoho_mail_service import zoho_mail_service

    def _exibir_status():
        """Exibe o status atual do Zoho Mail"""
        status = zoho_mail_service.verificar_conexao()
        tokens_status = zoho_mail_service.obter_status_tokens()

        # Formatar exibicao - garantir que valores nao sejam None
        client_id = zoho_mail_service.client_id
        client_id_display = _ocultar_chave(client_id) if client_id else "(nao configurado)"

        account_id = str(zoho_mail_service.account_id or "(nao configurado)")
        email_from = str(zoho_mail_service.email_from or "(nao configurado)")

        oauth_status = "Configurado" if status.get("configurado") else "Nao configurado"
        token_status = "Valido" if status.get("token_valido") else "Invalido/Expirado"
        tempo_restante = str(tokens_status.get("tempo_restante") or "N/A")

        conteudo = f"""[cyan]Status atual:[/cyan]

[bold]Client ID:[/bold] {client_id_display}
[bold]OAuth:[/bold] {oauth_status}
[bold]Token:[/bold] {token_status}
[bold]Tempo restante:[/bold] {tempo_restante}
[bold]Account ID:[/bold] {account_id}
[bold]E-mail:[/bold] {email_from}

[dim]Certifique-se de ter ZOHO_CLIENT_ID e ZOHO_CLIENT_SECRET no .env[/dim]"""

        exibir_painel(conteudo, "Status do Zoho Mail", "cyan")
        pausar()

    def _configurar_oauth():
        """Configura o OAuth2 do Zoho Mail"""
        console.print("\n[bold cyan]CONFIGURAR OAUTH2 DO ZOHO MAIL[/bold cyan]\n")

        if not zoho_mail_service.client_id or not zoho_mail_service.client_secret:
            exibir_erro("ZOHO_CLIENT_ID e ZOHO_CLIENT_SECRET sao obrigatorios!")
            console.print("\n[yellow]Configure-os no arquivo .env antes de continuar.[/yellow]")
            console.print("\n[dim]Exemplo no .env:[/dim]")
            console.print('[dim]ZOHO_CLIENT_ID="seu_client_id_aqui"[/dim]')
            console.print('[dim]ZOHO_CLIENT_SECRET="seu_client_secret_aqui"[/dim]')
        else:
            confirma = pedir_confirmacao("Iniciar fluxo OAuth?", padrao=False)
            if confirma:
                zoho_mail_service.configurar_oauth_interativo()
        pausar()

    def _renovar_token():
        """Renova o token de acesso"""
        exibir_info("Renovando token de acesso...")
        token = zoho_mail_service.renovar_access_token()
        if token:
            exibir_sucesso("Token renovado com sucesso!")
        else:
            exibir_erro("Erro ao renovar token - pode ser necessario reautorizar")
        pausar()

    def _revogar_reautorizar():
        """Revoga tokens e reautoriza"""
        exibir_aviso("Esta opcao ira revogar todos os tokens e iniciar nova autorizacao.")
        confirma = pedir_confirmacao("Continuar?", padrao=False)
        if confirma:
            zoho_mail_service.revogar_e_reautorizar()
        pausar()

    def _testar_conexao():
        """Testa a conexao com Zoho Mail"""
        exibir_info("Testando conexao com Zoho Mail...")
        resultado = zoho_mail_service.verificar_conexao()

        disponivel = "Sim" if resultado.get('disponivel') else "Nao"
        configurado = "Sim" if resultado.get('configurado') else "Nao"
        token_valido = "Sim" if resultado.get('token_valido') else "Nao"

        conteudo = f"""[cyan]Status da Conexao:[/cyan]

[bold]Disponivel:[/bold] {disponivel}
[bold]Configurado:[/bold] {configurado}
[bold]Token valido:[/bold] {token_valido}
[bold]Account ID:[/bold] {resultado.get('account_id', 'N/A')}
[bold]E-mail:[/bold] {resultado.get('email_from', 'N/A')}
[bold]Mensagem:[/bold] {resultado.get('mensagem', '')}"""

        exibir_painel(conteudo, "Teste de Conexao Zoho Mail", "cyan")
        pausar()

    def _ver_status_tokens():
        """Exibe status detalhado dos tokens"""
        tokens_status = zoho_mail_service.obter_status_tokens()

        refresh_token = "Presente" if tokens_status.get('refresh_token_presente') else "Ausente"
        access_token = "Presente" if tokens_status.get('access_token_presente') else "Ausente"
        expirado = "Sim" if tokens_status.get('token_expirado') else "Nao"

        conteudo = f"""[cyan]Status dos Tokens OAuth:[/cyan]

[bold]Refresh Token:[/bold] {refresh_token}
[bold]Access Token:[/bold] {access_token}
[bold]Expira em:[/bold] {tokens_status.get('token_expira_em', 'N/A')}
[bold]Expirado:[/bold] {expirado}
[bold]Tempo restante:[/bold] {tokens_status.get('tempo_restante', 'N/A')}"""

        exibir_painel(conteudo, "Status dos Tokens", "cyan")
        pausar()

    (
        MenuBuilder("CONFIGURACOES DO ZOHO MAIL (E-MAIL)", ICONES["email"])
        .adicionar("Ver status atual", _exibir_status, ICONES["info"])
        .separador()
        .adicionar("Configurar OAuth (autorizacao completa)", _configurar_oauth, ICONES["chave"])
        .adicionar("Renovar token de acesso", _renovar_token, ICONES["atualizar"])
        .adicionar("Revogar e reautorizar", _revogar_reautorizar, ICONES["excluir"])
        .separador()
        .adicionar("Testar conexao", _testar_conexao, ICONES["check"])
        .adicionar("Ver status detalhado dos tokens", _ver_status_tokens, ICONES["info"])
        .com_voltar("Voltar")
        .executar()
    )


def _ver_todas_configs():
    """Exibe todas as configuracoes"""
    config_service = obter_config_service()
    configs = config_service.listar_todas()

    exibir_cabecalho("TODAS AS CONFIGURACOES", ICONES["config"])

    # Agrupar por tipo
    por_tipo = {}
    for chave, config in configs.items():
        tipo = config.tipo.value.upper()
        if tipo not in por_tipo:
            por_tipo[tipo] = []
        por_tipo[tipo].append(config)

    for tipo, items in sorted(por_tipo.items()):
        console.print(f"\n{ICONES['diretorio']} [bold cyan]{tipo}[/bold cyan]")
        console.print("[dim]" + "-" * 60 + "[/dim]")
        for config in items:
            valor_display = config_service.exibir_valor(config)
            obrig = "* " if config.obrigatorio else "  "
            console.print(f"{obrig}[bold]{config.chave}:[/bold] {valor_display}")
            console.print(f"     [dim]└─ {config.descricao}[/dim]")

    console.print("\n[dim]" + "=" * 70 + "[/dim]")
    console.print("[yellow]* = Obrigatorio[/yellow]")
    console.print("[dim]" + "=" * 70 + "[/dim]")

    pausar()


def _validar_configs():
    """Valida todas as configuracoes"""
    config_service = obter_config_service()
    resultado = config_service.validar()

    exibir_cabecalho("VALIDACAO DE CONFIGURACOES", ICONES["check"])

    if resultado["erros"]:
        console.print(f"\n{ICONES['erro']} [bold red]ERROS:[/bold red]")
        for erro in resultado["erros"]:
            console.print(f"   {erro}")

    if resultado["avisos"]:
        console.print(f"\n{ICONES['aviso']} [bold yellow]AVISOS:[/bold yellow]")
        for aviso in resultado["avisos"]:
            console.print(f"   {aviso}")

    if resultado["valido"]:
        exibir_sucesso("Todas as configuracoes obrigatorias estao OK!")
    else:
        exibir_erro("Ha configuracoes obrigatorias faltando!")

    console.print("\n[dim]" + "=" * 60 + "[/dim]")

    pausar()


def _restaurar_padrao():
    """Restaura configuracoes para valores padrao"""
    conteudo = """[red bold]ATENCAO:[/red bold] Esta acao ira:

• Restaurar TODAS as configuracoes para valores padrao
• Apagar chaves de API configuradas
• Resetar configuracoes do MongoDB

[yellow]Esta acao NAO PODE ser desfeita![/yellow]"""

    exibir_painel(conteudo, "Restaurar Configuracoes Padrao", "red")

    confirmacao = pedir_texto("\nDigite 'CONFIRMAR' para prosseguir", obrigatorio=False)

    if confirmacao != "CONFIRMAR":
        exibir_erro("Operacao cancelada.")
        pausar()
        return

    config_service = obter_config_service()

    try:
        # Definir valores padrao
        config_service.definir("MONGO_URI", "mongodb://localhost:27017")
        config_service.definir("MONGO_DATABASE_NAME", "MS_Automatizar")
        config_service.definir("MONGO_MAX_POOL_SIZE", "100")
        config_service.definir("MONGO_MIN_POOL_SIZE", "10")
        config_service.definir("MODO_OPERACAO", "mongodb")
        config_service.definir("LOG_LEVEL", "INFO")

        # Limpar configuracoes opcionais
        config_service.remover("KEY_API_GEMINI")
        config_service.remover("KEY_API_MISTRAL")
        config_service.remover("DIRETORIO_SAIDA")
        config_service.remover("ONEDRIVE_URL_DADOS")
        config_service.remover("ONEDRIVE_URL_MODELOS")

        exibir_sucesso("Configuracoes restauradas para valores padrao!")
        exibir_aviso("Voce precisara reconfigurar as chaves de API.")

    except Exception as e:
        exibir_erro(f"Erro ao restaurar configuracoes: {e}")

    pausar()


if __name__ == "__main__":
    # Permite testar interface diretamente
    Interface_Configuracoes()
