"""
Comandos CLI para gerenciar coleção de diretórios
"""

from typing import Optional
from bson import ObjectId

from src.services.diretorio_service import DiretorioService
from src.services.contrato_service import ContratoService
from src.models.diretorio_models import DiretorioBuilder, StatusDiretorio
from src.utils.logger_config import logger


# ============================================================================
# COMANDOS DE DIRETÓRIOS
# ============================================================================

def listar_diretorios(apenas_ativos: bool = False, formato: str = "tabela") -> None:
    """
    Lista diretórios cadastrados
    
    Args:
        apenas_ativos: Se True, lista apenas diretórios ativos
        formato: "tabela" ou "json"
    """
    service = DiretorioService()
    
    if not service.disponivel:
        logger.error("MongoDB não disponível")
        return
    
    # listar_ativos() retorna lista, listar_todos() retorna dict com 'dados'
    if apenas_ativos:
        diretorios = service.listar_ativos()
    else:
        resultado = service.listar_todos()
        diretorios = resultado.get('dados', [])
    
    if not diretorios:
        logger.info("Nenhum diretório encontrado")
        return
    
    if formato == "json":
        import json
        print(json.dumps(diretorios, indent=2, default=str))
    else:
        # Formato tabela
        logger.info(f"\n{'=' * 100}")
        logger.info(f"DIRETÓRIOS CADASTRADOS ({len(diretorios)})")
        logger.info(f"{'=' * 100}")
        
        # Buscar nomes dos contratos para exibição
        contrato_service = ContratoService()
        
        for diretorio in diretorios:
            # Se status for None, considerar como ATIVO (retrocompatibilidade)
            status_valor = diretorio.get('status', StatusDiretorio.ATIVO.value)
            status = "✓ ATIVO" if status_valor == StatusDiretorio.ATIVO.value else "✗ INATIVO"
            auto = " [AUTO]" if diretorio.get('auto_criado') else ""
            
            logger.info(f"\n{diretorio.get('nome')}{auto}")
            logger.info(f"  Status:     {status}")
            logger.info(f"  ID:         {diretorio.get('_id')}")
            
            if diretorio.get('id_diretorio'):
                logger.info(f"  ID Diret:   {diretorio.get('id_diretorio')}")
            
            # Buscar nome do contrato associado
            contrato_id = diretorio.get('contrato_id')
            if contrato_id:
                contrato = contrato_service.buscar_por_id(str(contrato_id))
                contrato_nome = contrato.get('nome', str(contrato_id)) if contrato else str(contrato_id)
                logger.info(f"  Contrato:   {contrato_nome}")
            
            if diretorio.get('caminho_relativo'):
                logger.info(f"  Caminho:    {diretorio.get('caminho_relativo')}")
            if diretorio.get('descricao'):
                logger.info(f"  Descrição:  {diretorio.get('descricao')}")


def adicionar_diretorio_interativo() -> None:
    """
    Adiciona diretório via input interativo
    """
    service = DiretorioService()
    contrato_service = ContratoService()
    
    if not service.disponivel:
        logger.error("MongoDB não disponível")
        return
    
    logger.info("\n" + "=" * 80)
    logger.info("ADICIONAR NOVO DIRETÓRIO")
    logger.info("=" * 80)
    
    try:
        # Input obrigatório
        nome = input("\nNome do diretório (*): ").strip()
        if not nome:
            logger.error("Nome é obrigatório")
            return
        
        # Verificar duplicata
        existente = service.buscar_por_nome(nome)
        if existente:
            logger.warning(f"Diretório '{nome}' já existe (ID: {existente.get('_id')})")
            sobrescrever = input("Deseja continuar mesmo assim? (s/N): ").lower()
            if sobrescrever != 's':
                logger.info("Operação cancelada")
                return
        
        # Inputs opcionais
        descricao = input("Descrição: ").strip() or None
        caminho_relativo = input("Caminho relativo: ").strip() or None
        
        # Associar contrato (opcional)
        associar_contrato = input("Associar a um contrato? (s/N): ").lower()
        contrato_id = None
        
        if associar_contrato == 's':
            # Listar contratos para seleção
            contratos = contrato_service.listar_ativos()
            if contratos:
                logger.info("\nContratos disponíveis:")
                for i, contrato in enumerate(contratos, 1):
                    logger.info(f"  {i}. {contrato.get('nome')} ({contrato.get('_id')})")
                
                escolha = input("\nEscolha o número do contrato (ou ENTER para pular): ").strip()
                if escolha.isdigit():
                    idx = int(escolha) - 1
                    if 0 <= idx < len(contratos):
                        contrato_id = contratos[idx].get('_id')
                        logger.info(f"Contrato selecionado: {contratos[idx].get('nome')}")
                    else:
                        logger.warning("Número inválido, contrato não associado")
            else:
                logger.warning("Nenhum contrato disponível")
        
        ordem_str = input("Ordem de exibição (número): ").strip()
        ordem = int(ordem_str) if ordem_str.isdigit() else 999
        
        # Criar com Builder
        builder = (DiretorioBuilder()
                   .set_nome(nome)
                   .set_ordem(ordem))
        
        if descricao:
            builder.set_descricao(descricao)
        if caminho_relativo:
            builder.set_caminho_relativo(caminho_relativo)
        if contrato_id:
            builder.set_contrato_id(contrato_id)
        
        diretorio = builder.build()

        # Salvar
        resultado = service.criar_diretorio(diretorio)
        
        if resultado:
            logger.info(f"\n✅ Diretório '{nome}' criado com sucesso!")
            logger.info(f"   ID: {resultado}")
        else:
            logger.error(f"❌ Erro ao criar diretório '{nome}'")
    
    except KeyboardInterrupt:
        logger.info("\nOperação cancelada")
    except Exception as e:
        logger.error(f"Erro ao adicionar diretório: {e}")


def criar_diretorio_para_contrato() -> None:
    """
    Cria automaticamente um diretório para um contrato existente
    """
    service = DiretorioService()
    contrato_service = ContratoService()
    
    if not service.disponivel:
        logger.error("MongoDB não disponível")
        return
    
    logger.info("\n" + "=" * 80)
    logger.info("CRIAR DIRETÓRIO PARA CONTRATO")
    logger.info("=" * 80)
    
    # Listar contratos
    contratos = contrato_service.listar_ativos()
    if not contratos:
        logger.warning("Nenhum contrato ativo encontrado")
        return
    
    logger.info("\nContratos disponíveis:")
    for i, contrato in enumerate(contratos, 1):
        # Verificar se já tem diretório
        diretorio_existente = service.buscar_por_contrato_id(contrato.get('_id'))
        status = " [JÁ TEM DIRETÓRIO]" if diretorio_existente else ""
        logger.info(f"  {i}. {contrato.get('nome')}{status}")
    
    escolha = input("\nEscolha o número do contrato: ").strip()
    if not escolha.isdigit():
        logger.warning("Número inválido")
        return
    
    idx = int(escolha) - 1
    if idx < 0 or idx >= len(contratos):
        logger.warning("Número fora do intervalo")
        return
    
    contrato = contratos[idx]
    contrato_id = contrato.get('_id')
    
    # Verificar se já existe
    existente = service.buscar_por_contrato_id(contrato_id)
    if existente:
        logger.warning(f"Diretório já existe para este contrato: {existente.get('nome')}")
        return
    
    # Criar
    diretorio_id = service.criar_diretorio_para_contrato(contrato_id)
    
    if diretorio_id:
        logger.info(f"\n✅ Diretório criado automaticamente!")
        logger.info(f"   Contrato: {contrato.get('nome')}")
        logger.info(f"   Diretório ID: {diretorio_id}")
    else:
        logger.error(f"❌ Erro ao criar diretório para contrato")


def inativar_diretorio(diretorio_id: str) -> None:
    """
    Marca um diretório como inativo
    
    Args:
        diretorio_id: ObjectId do diretório em formato string
    """
    service = DiretorioService()
    
    if not service.disponivel:
        logger.error("MongoDB não disponível")
        return
    
    # Validar ObjectId
    try:
        ObjectId(diretorio_id)
    except Exception:
        logger.error(f"ID inválido: {diretorio_id}")
        return
    
    # Buscar para confirmar
    diretorio = service.buscar_por_id(diretorio_id)
    if not diretorio:
        logger.error(f"Diretório não encontrado: {diretorio_id}")
        return
    
    nome = diretorio.get('nome', 'Sem nome')
    
    # Confirmar
    confirma = input(f"Confirma inativação do diretório '{nome}'? (s/N): ").lower()
    if confirma != 's':
        logger.info("Operação cancelada")
        return
    
    # Inativar
    sucesso = service.marcar_inativo(diretorio_id)
    
    if sucesso:
        logger.info(f"✅ Diretório '{nome}' inativado com sucesso!")
    else:
        logger.error(f"❌ Erro ao inativar diretório '{nome}'")


def atualizar_diretorio_interativo() -> None:
    """
    Atualiza diretório via input interativo
    """
    service = DiretorioService()
    
    if not service.disponivel:
        logger.error("MongoDB não disponível")
        return
    
    logger.info("\n" + "=" * 80)
    logger.info("ATUALIZAR DIRETÓRIO")
    logger.info("=" * 80)
    
    # Listar para seleção - listar_todos() retorna dict com 'dados'
    resultado = service.listar_todos()
    diretorios = resultado.get('dados', [])
    if not diretorios:
        logger.warning("Nenhum diretório encontrado")
        return
    
    logger.info("\nDiretórios disponíveis:")
    for i, diretorio in enumerate(diretorios, 1):
        # Se status for None, considerar como ATIVO (retrocompatibilidade)
        status_valor = diretorio.get('status', StatusDiretorio.ATIVO.value)
        status = "✓" if status_valor == StatusDiretorio.ATIVO.value else "✗"
        logger.info(f"  {i}. [{status}] {diretorio.get('nome')}")
    
    escolha = input("\nEscolha o número do diretório: ").strip()
    if not escolha.isdigit():
        logger.warning("Número inválido")
        return
    
    idx = int(escolha) - 1
    if idx < 0 or idx >= len(diretorios):
        logger.warning("Número fora do intervalo")
        return
    
    diretorio = diretorios[idx]
    diretorio_id = str(diretorio.get('_id'))
    
    logger.info(f"\nEditando: {diretorio.get('nome')}")
    logger.info("(Pressione ENTER para manter valor atual)\n")
    
    # Coletar alterações
    alteracoes = {}
    
    novo_nome = input(f"Nome [{diretorio.get('nome')}]: ").strip()
    if novo_nome and novo_nome != diretorio.get('nome'):
        alteracoes['nome'] = novo_nome
    
    nova_descricao = input(f"Descrição [{diretorio.get('descricao', '')}]: ").strip()
    if nova_descricao and nova_descricao != diretorio.get('descricao'):
        alteracoes['descricao'] = nova_descricao
    
    novo_caminho = input(f"Caminho relativo [{diretorio.get('caminho_relativo', '')}]: ").strip()
    if novo_caminho and novo_caminho != diretorio.get('caminho_relativo'):
        alteracoes['caminho_relativo'] = novo_caminho
    
    nova_ordem_str = input(f"Ordem [{diretorio.get('ordem', 0)}]: ").strip()
    if nova_ordem_str.isdigit():
        nova_ordem = int(nova_ordem_str)
        if nova_ordem != diretorio.get('ordem'):
            alteracoes['ordem'] = nova_ordem
    
    # Aplicar
    if alteracoes:
        sucesso = service.atualizar(diretorio_id, alteracoes)
        if sucesso:
            logger.info(f"\n✅ Diretório atualizado com sucesso!")
            logger.info(f"   Campos alterados: {list(alteracoes.keys())}")
        else:
            logger.error(f"❌ Erro ao atualizar diretório")
    else:
        logger.info("Nenhuma alteração realizada")


def exibir_estatisticas_diretorios() -> None:
    """
    Exibe estatísticas sobre diretórios
    """
    service = DiretorioService()
    
    if not service.disponivel:
        logger.error("MongoDB não disponível")
        return
    
    # listar_todos() retorna dict com 'dados'
    resultado = service.listar_todos()
    todos = resultado.get('dados', [])
    ativos = service.listar_ativos()
    
    # Contar auto-criados
    auto_criados = sum(1 for d in todos if d.get('auto_criado'))
    com_contrato = sum(1 for d in todos if d.get('contrato_id'))
    
    logger.info("\n" + "=" * 50)
    logger.info("ESTATÍSTICAS DE DIRETÓRIOS")
    logger.info("=" * 50)
    logger.info(f"  Total:          {len(todos)}")
    logger.info(f"  Ativos:         {len(ativos)}")
    logger.info(f"  Inativos:       {len(todos) - len(ativos)}")
    logger.info(f"  Auto-criados:   {auto_criados}")
    logger.info(f"  Com contrato:   {com_contrato}")


# ============================================================================
# COMANDOS DE SINCRONIZAÇÃO
# ============================================================================

def criar_diretorios_todos_contratos() -> None:
    """
    Cria diretórios automaticamente para TODOS os contratos que não têm
    """
    service = DiretorioService()
    contrato_service = ContratoService()
    
    if not service.disponivel:
        logger.error("MongoDB não disponível")
        return
    
    logger.info("\n" + "=" * 80)
    logger.info("CRIAR DIRETÓRIOS PARA TODOS OS CONTRATOS")
    logger.info("=" * 80)
    
    contratos = contrato_service.listar_ativos()
    if not contratos:
        logger.warning("Nenhum contrato ativo encontrado")
        return
    
    criados = 0
    existentes = 0
    erros = 0
    
    for contrato in contratos:
        contrato_id = contrato.get('_id')
        nome = contrato.get('nome', 'Sem nome')
        
        # Verificar se já existe
        existente = service.buscar_por_contrato_id(contrato_id)
        if existente:
            existentes += 1
            logger.debug(f"Diretório já existe para: {nome}")
            continue
        
        # Criar
        diretorio_id = service.criar_diretorio_para_contrato(contrato_id)
        
        if diretorio_id:
            criados += 1
            logger.info(f"✅ Criado diretório para: {nome}")
        else:
            erros += 1
            logger.warning(f"⚠️ Erro ao criar diretório para: {nome}")
    
    logger.info("\n" + "-" * 50)
    logger.info("RESUMO")
    logger.info("-" * 50)
    logger.info(f"  Contratos processados: {len(contratos)}")
    logger.info(f"  Diretórios criados:    {criados}")
    logger.info(f"  Já existentes:         {existentes}")
    if erros > 0:
        logger.info(f"  ⚠️ Erros:              {erros}")


if __name__ == "__main__":
    # Permite testar comandos diretamente
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python diretorios.py <comando>")
        print("Comandos: listar, adicionar, inativar, estatisticas, criar-todos")
        sys.exit(1)
    
    comando = sys.argv[1]
    
    if comando == "listar":
        listar_diretorios()
    elif comando == "adicionar":
        adicionar_diretorio_interativo()
    elif comando == "inativar" and len(sys.argv) > 2:
        inativar_diretorio(sys.argv[2])
    elif comando == "estatisticas":
        exibir_estatisticas_diretorios()
    elif comando == "criar-todos":
        criar_diretorios_todos_contratos()
    else:
        print(f"Comando desconhecido: {comando}")
        sys.exit(1)
