"""
Interface CLI para gerenciamento de Contatos de Envio de Folhas de Ponto
"""

import os
import questionary
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm

from src.services.contatos_folha_ponto_service import contatos_folha_ponto_service
from src.utils.logger_config_v2 import get_logger

logger = get_logger("interface_contatos")

console = Console()


class InterfaceContatosFolhaPonto:
    """
    Interface interativa para gerenciamento de contatos de envio de folhas de ponto.
    """
    
    def __init__(self):
        self.service = contatos_folha_ponto_service
        self.pagina_atual = 0
        self.itens_por_pagina = 20
        
        if not self.service.disponivel:
            console.print("[red]Erro: MongoDB não está disponível[/red]")
            return
        
        self.executar()
    
    def executar(self):
        """Loop principal da interface"""
        while True:
            self.exibir_menu()
            opcao = self.obter_opcao()
            
            if opcao is None or opcao == "Voltar":
                break
            
            self.processar_opcao(opcao)
    
    def exibir_menu(self):
        """Exibe o menu principal"""
        console.clear()
        console.print(Panel(
            "[bold cyan]GERENCIAR CONTATOS DE ENVIO DE FOLHA DE PONTO[/bold cyan]",
            style="cyan"
        ))
        
        # Estatísticas rápidas
        stats = self.service.estatisticas()
        if stats:
            console.print(f"[dim]Total de contatos: {stats.get('total', 0)}[/dim]")
        
        console.print()
    
    def obter_opcao(self) -> str:
        """Obtém opção do usuário"""
        opcoes = [
            "Listar contatos",
            "Buscar contato",
            "Adicionar novo contato",
            "Editar contato existente",
            "Excluir contato",
            "Estatísticas",
            "---",
            "Voltar"
        ]
        
        return questionary.select(
            "Selecione uma opção:",
            choices=opcoes
        ).ask()
    
    def processar_opcao(self, opcao: str):
        """Processa a opção selecionada"""
        if opcao == "Listar contatos":
            self.listar_contatos()
        elif opcao == "Buscar contato":
            self.buscar_contato()
        elif opcao == "Adicionar novo contato":
            self.adicionar_contato()
        elif opcao == "Editar contato existente":
            self.editar_contato()
        elif opcao == "Excluir contato":
            self.excluir_contato()
        elif opcao == "Estatísticas":
            self.exibir_estatisticas()
    
    def listar_contatos(self):
        """Lista contatos com filtros"""
        console.clear()
        console.print(Panel("[bold cyan]LISTAR CONTATOS[/bold cyan]", style="cyan"))
        
        # Opções de filtro
        filtro_opcoes = [
            "Todos",
            "Filtrar por empresa",
            "Filtrar por local",
            "Filtrar por tipo de envio"
        ]
        
        filtro = questionary.select(
            "Tipo de filtro:",
            choices=filtro_opcoes
        ).ask()
        
        if filtro is None:
            return
        
        # Resetar paginação
        self.pagina_atual = 0
        
        # Aplicar filtro
        if filtro == "Todos":
            contatos = self.service.listar_todos(
                skip=self.pagina_atual * self.itens_por_pagina,
                limit=self.itens_por_pagina
            )
        elif filtro == "Filtrar por empresa":
            empresa = questionary.text("Nome da empresa:").ask()
            if not empresa:
                return
            contatos = self.service.listar_por_empresa(
                empresa,
                skip=self.pagina_atual * self.itens_por_pagina,
                limit=self.itens_por_pagina
            )
        elif filtro == "Filtrar por local":
            local = questionary.text("Local/contrato/polo:").ask()
            if not local:
                return
            contatos = self.service.listar_por_local(
                local,
                skip=self.pagina_atual * self.itens_por_pagina,
                limit=self.itens_por_pagina
            )
        elif filtro == "Filtrar por tipo de envio":
            tipo_envio = questionary.select(
                "Tipo de envio:",
                choices=["email", "whatsapp", "grupo_whatsapp", "impresso"]
            ).ask()
            if not tipo_envio:
                return
            contatos = self.service.listar_por_envio(
                tipo_envio,
                skip=self.pagina_atual * self.itens_por_pagina,
                limit=self.itens_por_pagina
            )
        
        self.exibir_tabela_contatos(contatos)
    
    def exibir_tabela_contatos(self, contatos, titulo: str = "Contatos"):
        """Exibe tabela de contatos"""
        if not contatos:
            console.print("[yellow]Nenhum contato encontrado[/yellow]")
            questionary.press_any_key_to_continue().ask()
            return
        
        table = Table(title=titulo, show_header=True, header_style="bold cyan")
        
        table.add_column("ID", style="dim", width=10)
        table.add_column("Nome", style="bold")
        table.add_column("Empresa", style="green")
        table.add_column("Email", style="blue")
        table.add_column("Telefone", style="magenta")
        table.add_column("Envios", style="yellow")
        
        for contato in contatos:
            # Montar flags de envio
            envios = []
            if contato.get("enviar_email"):
                envios.append("📧")
            if contato.get("enviar_whatsapp"):
                envios.append("💬")
            if contato.get("enviar_grupo_whatsapp"):
                envios.append("👥")
            if contato.get("enviar_impresso"):
                envios.append("📄")
            
            table.add_row(
                str(contato.get("_id", ""))[:8],
                contato.get("nome", ""),
                contato.get("empresa", ""),
                contato.get("email", ""),
                contato.get("telefone", ""),
                " ".join(envios) if envios else "-"
            )
        
        console.print(table)
        
        # Navegação de páginas
        console.print(f"\n[dim]Página {self.pagina_atual + 1}[/dim]")
        
        if len(contatos) == self.itens_por_pagina:
            proximo = questionary.confirm("Próxima página?", default=False).ask()
            if proximo:
                self.pagina_atual += 1
                # Recarregar lista (simplificado - ideal seria manter filtro)
                self.listar_contatos()
        
        questionary.press_any_key_to_continue().ask()
    
    def buscar_contato(self):
        """Busca contato por nome, email ou telefone"""
        console.clear()
        console.print(Panel("[bold cyan]BUSCAR CONTATO[/bold cyan]", style="cyan"))
        
        tipo_busca = questionary.select(
            "Buscar por:",
            choices=["Nome", "Email", "Telefone"]
        ).ask()
        
        if tipo_busca is None:
            return
        
        termo = questionary.text(f"Digite o {tipo_busca.lower()}:").ask()
        if not termo:
            return
        
        if tipo_busca == "Nome":
            contatos = self.service.buscar_por_nome(termo)
        elif tipo_busca == "Email":
            contatos = self.service.buscar_por_email(termo)
        elif tipo_busca == "Telefone":
            contatos = self.service.buscar_por_telefone(termo)
        else:
            contatos = []
        
        self.exibir_tabela_contatos(contatos, f"Resultados da busca por {tipo_busca}")
    
    def adicionar_contato(self):
        """Adiciona um novo contato"""
        console.clear()
        console.print(Panel("[bold cyan]ADICIONAR NOVO CONTATO[/bold cyan]", style="cyan"))
        
        # Coletar dados
        dados = {}
        
        dados["funcionario_id"] = questionary.text("ID do funcionário (da planilha):").ask()
        if not dados["funcionario_id"]:
            console.print("[red]ID do funcionário é obrigatório[/red]")
            questionary.press_any_key_to_continue().ask()
            return
        
        dados["nome"] = questionary.text("Nome completo:").ask()
        if not dados["nome"]:
            console.print("[red]Nome é obrigatório[/red]")
            questionary.press_any_key_to_continue().ask()
            return
        
        dados["email"] = questionary.text("Email(s) separados por vírgula (opcional):").ask() or ""
        dados["telefone"] = questionary.text("Telefone(s) separados por vírgula (opcional):").ask() or ""
        dados["grupo_whatsapp"] = questionary.text("Grupo(s) WhatsApp separados por vírgula (opcional):").ask() or ""
        
        dados["empresa"] = questionary.text("Nome da empresa:").ask() or ""
        dados["local_contrato_polo"] = questionary.text("Local/Contrato/Polo:").ask() or ""
        
        dados["diretorio_geral"] = questionary.text("Diretório geral (ex: Z:\\\\04. PESSOAL\\\\FOLHA PONTO):").ask() or ""
        dados["diretorio_especifico"] = questionary.text("Diretório específico (ex: 01. MS SERVICOS\\\\ADMINISTRATIVO):").ask() or ""
        
        # Flags de envio
        console.print("\n[bold]Configurar canais de envio:[/bold]")
        dados["enviar_email"] = questionary.confirm("Enviar por email?", default=False).ask()
        dados["enviar_whatsapp"] = questionary.confirm("Enviar por WhatsApp?", default=True).ask()
        dados["enviar_grupo_whatsapp"] = questionary.confirm("Enviar para grupo WhatsApp?", default=False).ask()
        dados["enviar_impresso"] = questionary.confirm("Enviar impresso?", default=False).ask()
        
        # Confirmar
        console.print("\n[bold]Dados do contato:[/bold]")
        for key, value in dados.items():
            console.print(f"  {key}: {value}")
        
        if questionary.confirm("Confirmar criação?", default=True).ask():
            resultado = self.service.criar(dados)
            
            if resultado:
                console.print(f"[green]✓ Contato criado com sucesso! ID: {resultado}[/green]")
            else:
                console.print("[red]✗ Erro ao criar contato[/red]")
        else:
            console.print("[yellow]Criação cancelada[/yellow]")
        
        questionary.press_any_key_to_continue().ask()
    
    def editar_contato(self):
        """Edita um contato existente"""
        console.clear()
        console.print(Panel("[bold cyan]EDITAR CONTATO[/bold cyan]", style="cyan"))
        
        # Buscar contato para editar
        contato_id = questionary.text("ID do contato (ObjectId):").ask()
        if not contato_id:
            return
        
        contato = self.service.buscar_por_id(contato_id)
        if not contato:
            console.print("[red]Contato não encontrado[/red]")
            questionary.press_any_key_to_continue().ask()
            return
        
        console.print("\n[bold]Dados atuais:[/bold]")
        for key, value in contato.items():
            if key not in ["_id", "criado_em", "atualizado_em"]:
                console.print(f"  {key}: {value}")
        
        # Campos para editar
        campos_editaveis = [
            "funcionario_id", "nome", "email", "telefone", "grupo_whatsapp",
            "empresa", "local_contrato_polo", "diretorio_geral", "diretorio_especifico",
            "enviar_email", "enviar_whatsapp", "enviar_grupo_whatsapp", "enviar_impresso"
        ]
        
        campos_para_editar = questionary.checkbox(
            "Selecione os campos para editar:",
            choices=campos_editaveis
        ).ask()
        
        if not campos_para_editar:
            console.print("[yellow]Nenhum campo selecionado[/yellow]")
            questionary.press_any_key_to_continue().ask()
            return
        
        dados_atualizacao = {}
        
        for campo in campos_para_editar:
            valor_atual = contato.get(campo, "")
            
            if isinstance(valor_atual, bool):
                novo_valor = questionary.confirm(
                    f"Valor atual de {campo}: {valor_atual}. Novo valor:",
                    default=valor_atual
                ).ask()
            else:
                novo_valor = questionary.text(
                    f"Valor atual de {campo}: {valor_atual}. Novo valor:",
                    default=str(valor_atual)
                ).ask()
            
            if novo_valor is not None:
                if isinstance(valor_atual, bool):
                    dados_atualizacao[campo] = novo_valor
                else:
                    dados_atualizacao[campo] = novo_valor
        
        if dados_atualizacao:
            if questionary.confirm("Confirmar atualização?", default=True).ask():
                resultado = self.service.atualizar(contato_id, dados_atualizacao)
                
                if resultado:
                    console.print("[green]✓ Contato atualizado com sucesso![/green]")
                else:
                    console.print("[red]✗ Erro ao atualizar contato[/red]")
            else:
                console.print("[yellow]Atualização cancelada[/yellow]")
        else:
            console.print("[yellow]Nenhum campo alterado[/yellow]")
        
        questionary.press_any_key_to_continue().ask()
    
    def excluir_contato(self):
        """Exclui um contato"""
        console.clear()
        console.print(Panel("[bold cyan]EXCLUIR CONTATO[/bold cyan]", style="cyan"))
        
        contato_id = questionary.text("ID do contato (ObjectId):").ask()
        if not contato_id:
            return
        
        contato = self.service.buscar_por_id(contato_id)
        if not contato:
            console.print("[red]Contato não encontrado[/red]")
            questionary.press_any_key_to_continue().ask()
            return
        
        console.print("\n[bold]Contato a ser excluído:[/bold]")
        console.print(f"  Nome: {contato.get('nome', '')}")
        console.print(f"  Empresa: {contato.get('empresa', '')}")
        console.print(f"  Email: {contato.get('email', '')}")
        
        if Confirm.ask("[red]Tem certeza que deseja excluir este contato?[/red]", default=False):
            resultado = self.service.excluir(contato_id)
            
            if resultado:
                console.print("[green]✓ Contato excluído com sucesso![/green]")
            else:
                console.print("[red]✗ Erro ao excluir contato[/red]")
        else:
            console.print("[yellow]Exclusão cancelada[/yellow]")
        
        questionary.press_any_key_to_continue().ask()
    
    def exibir_estatisticas(self):
        """Exibe estatísticas dos contatos"""
        console.clear()
        console.print(Panel("[bold cyan]ESTATÍSTICAS DOS CONTATOS[/bold cyan]", style="cyan"))
        
        stats = self.service.estatisticas()
        
        if not stats:
            console.print("[yellow]Não foi possível carregar estatísticas[/yellow]")
            questionary.press_any_key_to_continue().ask()
            return
        
        # Total geral
        console.print(f"\n[bold]Total de contatos:[/bold] {stats.get('total', 0)}")
        
        # Por empresa
        empresas = stats.get("por_empresa", [])
        if empresas:
            console.print("\n[bold]Por Empresa:[/bold]")
            table_empresas = Table(show_header=True, header_style="bold cyan")
            table_empresas.add_column("Empresa")
            table_empresas.add_column("Quantidade", justify="right")
            
            for empresa in empresas[:10]:  # Top 10
                table_empresas.add_row(
                    empresa.get("empresa", "N/A"),
                    str(empresa.get("count", 0))
                )
            
            console.print(table_empresas)
        
        # Por local
        locais = stats.get("por_local", [])
        if locais:
            console.print("\n[bold]Por Local:[/bold]")
            table_locais = Table(show_header=True, header_style="bold cyan")
            table_locais.add_column("Local")
            table_locais.add_column("Quantidade", justify="right")
            
            for local in locais[:10]:  # Top 10
                table_locais.add_row(
                    local.get("local", "N/A"),
                    str(local.get("count", 0))
                )
            
            console.print(table_locais)
        
        # Por tipo de envio
        envios = stats.get("por_envio", {})
        if envios:
            console.print("\n[bold]Por Tipo de Envio:[/bold]")
            console.print(f"  📧 Email: {envios.get('email', 0)}")
            console.print(f"  💬 WhatsApp: {envios.get('whatsapp', 0)}")
            console.print(f"  👥 Grupo WhatsApp: {envios.get('grupo_whatsapp', 0)}")
            console.print(f"  📄 Impresso: {envios.get('impresso', 0)}")
        
        questionary.press_any_key_to_continue().ask()
