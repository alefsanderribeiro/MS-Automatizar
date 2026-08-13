"""
Comandos CLI para gerenciar coleções de referência (Contratos, Horários, Funções)
"""

from typing import Optional
from bson import ObjectId

from src.services.contrato_service import ContratoService
from src.services.horario_service import HorarioService
from src.services.funcao_service import FuncaoService
from src.models.contrato_models import ContratoBuilder, StatusContrato
from src.models.horario_models import HorarioBuilder, StatusHorario
from src.models.funcao_models import FuncaoBuilder, StatusFuncao
from src.utils.logger_config import logger


# ============================================================================
# COMANDOS DE CONTRATOS
# ============================================================================

def listar_contratos(apenas_ativos: bool = False, formato: str = "tabela") -> None:
    """
    Lista contratos cadastrados
    
    Args:
        apenas_ativos: Se True, lista apenas contratos ativos
        formato: "tabela" ou "json"
    """
    service = ContratoService()
    
    if not service.disponivel:
        logger.error("MongoDB não disponível")
        return
    
    contratos = service.listar_ativos() if apenas_ativos else service.listar_todos()
    
    if not contratos:
        logger.info("Nenhum contrato encontrado")
        return
    
    if formato == "json":
        import json
        print(json.dumps(contratos, indent=2, default=str))
    else:
        # Formato tabela
        logger.info(f"\n{'=' * 100}")
        logger.info(f"CONTRATOS CADASTRADOS ({len(contratos)})")
        logger.info(f"{'=' * 100}")
        
        for contrato in contratos:
            status_val = contrato.get('status')
            if isinstance(status_val, str):
                status_val = status_val.lower()

            is_ativo = status_val == StatusContrato.ATIVO.value
            status = "ATIVO" if is_ativo else "INATIVO"
            auto = " [AUTO]" if contrato.get('auto_criado') else ""
            
            logger.info(f"\n{contrato.get('nome')}{auto}")
            logger.info(f"  Status:     {status}")
            logger.info(f"  ID:         {contrato.get('_id')}")
            
            if contrato.get('numero_contrato'):
                logger.info(f"  Nº:         {contrato.get('numero_contrato')}")
            if contrato.get('orgao'):
                logger.info(f"  Órgão:      {contrato.get('orgao')}")
            if contrato.get('localidade'):
                logger.info(f"  Local:      {contrato.get('localidade')}")
            if contrato.get('inicio_vigencia'):
                from src.utils.data_utils import formatar_data_br
                logger.info(f"  Vigência:   {formatar_data_br(contrato.get('inicio_vigencia'))} até {formatar_data_br(contrato.get('fim_vigencia'))}")


def adicionar_contrato_interativo() -> None:
    """
    Adiciona contrato via input interativo
    """
    service = ContratoService()
    
    if not service.disponivel:
        logger.error("MongoDB não disponível")
        return
    
    logger.info("\n" + "=" * 80)
    logger.info("ADICIONAR NOVO CONTRATO")
    logger.info("=" * 80)
    
    try:
        # Input obrigatório
        nome = input("\nNome do contrato (*): ").strip()
        if not nome:
            logger.error("Nome é obrigatório")
            return
        
        # Verificar duplicata
        existente = service.buscar_por_nome(nome)
        if existente:
            logger.warning(f"Contrato '{nome}' já existe (ID: {existente.get('_id')})")
            sobrescrever = input("Deseja continuar mesmo assim? (s/N): ").lower()
            if sobrescrever != 's':
                logger.info("Operação cancelada")
                return
        
        # Inputs opcionais
        numero_contrato = input("Número do contrato: ").strip() or None
        numero_processo = input("Número do processo: ").strip() or None
        orgao = input("Órgão: ").strip() or None
        localidade = input("Localidade: ").strip() or None
        
        # Datas (aceitar vazio)
        inicio_vigencia_str = input("Início vigência (DD/MM/YYYY): ").strip()
        inicio_vigencia = None
        if inicio_vigencia_str:
            from datetime import datetime
            try:
                inicio_vigencia = datetime.strptime(inicio_vigencia_str, "%d/%m/%Y")
            except ValueError:
                logger.warning("Data início inválida, será ignorada")
        
        fim_vigencia_str = input("Fim vigência (DD/MM/YYYY): ").strip()
        fim_vigencia = None
        if fim_vigencia_str:
            from datetime import datetime
            try:
                fim_vigencia = datetime.strptime(fim_vigencia_str, "%d/%m/%Y")
            except ValueError:
                logger.warning("Data fim inválida, será ignorada")
        
        ordem_str = input("Ordem de exibição (número): ").strip()
        ordem = int(ordem_str) if ordem_str.isdigit() else 999
        
        # Criar com Builder
        builder = (ContratoBuilder()
                   .set_nome(nome)
                   .set_ordem(ordem))
        
        if numero_contrato:
            builder.set_numero_contrato(numero_contrato)
        if numero_processo:
            builder.set_numero_processo(numero_processo)
        if orgao:
            builder.set_orgao(orgao)
        if localidade:
            builder.set_localidade(localidade)
        # Aplicar vigência de uma só vez (evita depender de métodos inexistentes)
        builder.set_vigencia(inicio=inicio_vigencia, fim=fim_vigencia)
        
        contrato = builder.build()
        
        # Salvar
        contrato_id = service.criar(contrato)
        
        if contrato_id:
            logger.info(f"\n✓ Contrato criado com sucesso!")
            logger.info(f"  ID: {contrato_id}")
        else:
            logger.error("✗ Erro ao criar contrato")
    
    except KeyboardInterrupt:
        logger.info("\nOperação cancelada pelo usuário")
    except Exception as e:
        logger.error(f"Erro ao adicionar contrato: {e}")


def inativar_contrato(contrato_id: str) -> None:
    """
    Inativa contrato por ID
    
    Args:
        contrato_id: ID do contrato (string ObjectId)
    """
    service = ContratoService()
    
    if not service.disponivel:
        logger.error("MongoDB não disponível")
        return
    
    try:
        obj_id = ObjectId(contrato_id)
        
        # Buscar contrato
        contrato = service.buscar_por_id(obj_id)
        if not contrato:
            logger.error(f"Contrato {contrato_id} não encontrado")
            return
        
        logger.info(f"\nInativando: {contrato.get('nome')}")
        
        # Tentar inativar
        sucesso = service.marcar_inativo(obj_id)
        
        if sucesso:
            logger.info("✓ Contrato inativado com sucesso")
        else:
            logger.error("✗ Não foi possível inativar o contrato")
            logger.error("  Provavelmente existem funcionários vinculados")
            logger.error("  Use: db.funcionarios.count_documents({'contrato_empresa_id': ObjectId('...')})")
    
    except Exception as e:
        logger.error(f"Erro ao inativar contrato: {e}")


# ============================================================================
# COMANDOS DE HORÁRIOS
# ============================================================================

def listar_horarios(apenas_ativos: bool = False, formato: str = "tabela") -> None:
    """
    Lista horários cadastrados
    
    Args:
        apenas_ativos: Se True, lista apenas horários ativos
        formato: "tabela" ou "json"
    """
    service = HorarioService()
    
    if not service.disponivel:
        logger.error("MongoDB não disponível")
        return
    
    horarios = service.listar_ativos() if apenas_ativos else service.listar_todos()
    
    if not horarios:
        logger.info("Nenhum horário encontrado")
        return
    
    if formato == "json":
        import json
        print(json.dumps(horarios, indent=2, default=str))
    else:
        logger.info(f"\n{'=' * 100}")
        logger.info(f"HORÁRIOS CADASTRADOS ({len(horarios)})")
        logger.info(f"{'=' * 100}")
        
        for horario in horarios:
            # Se status for None, considerar como ATIVO (retrocompatibilidade)
            status_valor = horario.get('status', StatusHorario.ATIVO.value)
            status = "✓ ATIVO" if status_valor == StatusHorario.ATIVO.value else "✗ INATIVO"
            auto = " [AUTO]" if horario.get('auto_criado') else ""
            
            logger.info(f"\n{horario.get('descricao')}{auto}")
            logger.info(f"  Status:          {status}")
            logger.info(f"  ID:              {horario.get('_id')}")
            logger.info(f"  Dias/mês:        {horario.get('dias_trabalho_mes', 'N/A')}")
            
            if horario.get('entrada1'):
                logger.info(f"  Entrada 1:       {horario.get('entrada1')}")
                logger.info(f"  Saída 1:         {horario.get('saida1')}")
            if horario.get('entrada2'):
                logger.info(f"  Entrada 2:       {horario.get('entrada2')}")
                logger.info(f"  Saída 2:         {horario.get('saida2')}")
            if horario.get('total_horas'):
                logger.info(f"  Total horas:     {horario.get('total_horas')}")


def adicionar_horario_interativo() -> None:
    """
    Adiciona horário via input interativo
    """
    service = HorarioService()
    
    if not service.disponivel:
        logger.error("MongoDB não disponível")
        return
    
    logger.info("\n" + "=" * 80)
    logger.info("ADICIONAR NOVO HORÁRIO")
    logger.info("=" * 80)
    
    try:
        # Input obrigatório
        descricao = input("\nDescrição do horário (*): ").strip()
        if not descricao:
            logger.error("Descrição é obrigatória")
            return
        
        # Verificar duplicata
        existente = service.buscar_por_descricao(descricao)
        if existente:
            logger.warning(f"Horário '{descricao}' já existe (ID: {existente.get('_id')})")
            sobrescrever = input("Deseja continuar mesmo assim? (s/N): ").lower()
            if sobrescrever != 's':
                logger.info("Operação cancelada")
                return
        
        # Inputs numéricos
        dias_str = input("Dias de trabalho por mês: ").strip()
        dias_trabalho_mes = int(dias_str) if dias_str.isdigit() else None
        
        # Horários (formato HH:MM)
        entrada1 = input("Entrada 1 (HH:MM): ").strip() or None
        saida1 = input("Saída 1 (HH:MM): ").strip() or None
        entrada2 = input("Entrada 2 (HH:MM, deixe vazio se não houver): ").strip() or None
        saida2 = input("Saída 2 (HH:MM, deixe vazio se não houver): ").strip() or None
        total_horas = input("Total de horas: ").strip() or None
        
        ordem_str = input("Ordem de exibição (número): ").strip()
        ordem = int(ordem_str) if ordem_str.isdigit() else 999
        
        # Converter strings de horário para time
        from datetime import time
        entrada1_time = None
        saida1_time = None
        entrada2_time = None
        saida2_time = None
        total_horas_time = None

        if entrada1:
            try:
                h, m = entrada1.split(':')
                entrada1_time = time(int(h), int(m))
            except:
                logger.warning(f"Formato de entrada1 inválido: {entrada1}")

        if saida1:
            try:
                h, m = saida1.split(':')
                saida1_time = time(int(h), int(m))
            except:
                logger.warning(f"Formato de saida1 inválido: {saida1}")

        if entrada2:
            try:
                h, m = entrada2.split(':')
                entrada2_time = time(int(h), int(m))
            except:
                logger.warning(f"Formato de entrada2 inválido: {entrada2}")

        if saida2:
            try:
                h, m = saida2.split(':')
                saida2_time = time(int(h), int(m))
            except:
                logger.warning(f"Formato de saida2 inválido: {saida2}")

        if total_horas:
            try:
                h, m = total_horas.split(':')
                total_horas_time = time(int(h), int(m))
            except:
                logger.warning(f"Formato de total_horas inválido: {total_horas}")

        # Criar com Builder
        builder = (HorarioBuilder()
                   .set_descricao(descricao)
                   .set_ordem(ordem))

        if dias_trabalho_mes:
            builder.set_dias_trabalho_mes(dias_trabalho_mes)

        # Usar set_jornada para horários
        builder.set_jornada(
            entrada1=entrada1_time,
            saida1=saida1_time,
            entrada2=entrada2_time,
            saida2=saida2_time
        )

        if total_horas_time:
            builder.set_total_horas(total_horas_time)

        horario = builder.build()
        
        # Salvar
        horario_id = service.criar(horario)
        
        if horario_id:
            logger.info(f"\n✓ Horário criado com sucesso!")
            logger.info(f"  ID: {horario_id}")
        else:
            logger.error("✗ Erro ao criar horário")
    
    except KeyboardInterrupt:
        logger.info("\nOperação cancelada pelo usuário")
    except Exception as e:
        logger.error(f"Erro ao adicionar horário: {e}")


def inativar_horario(horario_id: str) -> None:
    """
    Inativa horário por ID
    
    Args:
        horario_id: ID do horário (string ObjectId)
    """
    service = HorarioService()
    
    if not service.disponivel:
        logger.error("MongoDB não disponível")
        return
    
    try:
        obj_id = ObjectId(horario_id)
        
        # Buscar horário
        horario = service.buscar_por_id(obj_id)
        if not horario:
            logger.error(f"Horário {horario_id} não encontrado")
            return
        
        logger.info(f"\nInativando: {horario.get('descricao')}")
        
        # Tentar inativar
        sucesso = service.marcar_inativo(obj_id)
        
        if sucesso:
            logger.info("✓ Horário inativado com sucesso")
        else:
            logger.error("✗ Não foi possível inativar o horário")
            logger.error("  Provavelmente existem funcionários vinculados")
    
    except Exception as e:
        logger.error(f"Erro ao inativar horário: {e}")


# ============================================================================
# COMANDOS DE FUNÇÕES
# ============================================================================

def listar_funcoes(apenas_ativos: bool = False, formato: str = "tabela", categoria: Optional[str] = None) -> None:
    """
    Lista funções cadastradas
    
    Args:
        apenas_ativos: Se True, lista apenas funções ativas
        formato: "tabela" ou "json"
        categoria: Filtrar por função geral (categoria)
    """
    service = FuncaoService()
    
    if not service.disponivel:
        logger.error("MongoDB não disponível")
        return
    
    if categoria:
        funcoes = service.listar_por_categoria(categoria)
    elif apenas_ativos:
        funcoes = service.listar_ativos()
    else:
        funcoes = service.listar_todos()
    
    if not funcoes:
        logger.info("Nenhuma função encontrada")
        return
    
    if formato == "json":
        import json
        print(json.dumps(funcoes, indent=2, default=str))
    else:
        logger.info(f"\n{'=' * 100}")
        logger.info(f"FUNÇÕES CADASTRADAS ({len(funcoes)})")
        logger.info(f"{'=' * 100}")
        
        # Agrupar por categoria
        por_categoria = {}
        for funcao in funcoes:
            cat = funcao.get('funcao_geral', 'SEM CATEGORIA')
            if cat not in por_categoria:
                por_categoria[cat] = []
            por_categoria[cat].append(funcao)
        
        for cat, funcs in sorted(por_categoria.items()):
            logger.info(f"\n[{cat}]")
            for funcao in funcs:
                # Se status for None, considerar como ATIVO (retrocompatibilidade)
                status_valor = funcao.get('status', StatusFuncao.ATIVO.value)
                status = "✓" if status_valor == StatusFuncao.ATIVO.value else "✗"
                auto = " [AUTO]" if funcao.get('auto_criado') else ""
                logger.info(f"  {status} {funcao.get('nome')}{auto} (ID: {funcao.get('_id')})")


def adicionar_funcao_interativo() -> None:
    """
    Adiciona função via input interativo
    """
    service = FuncaoService()
    
    if not service.disponivel:
        logger.error("MongoDB não disponível")
        return
    
    logger.info("\n" + "=" * 80)
    logger.info("ADICIONAR NOVA FUNÇÃO")
    logger.info("=" * 80)
    
    try:
        # Input obrigatório
        nome = input("\nNome da função (*): ").strip()
        if not nome:
            logger.error("Nome é obrigatório")
            return
        
        # Verificar duplicata
        existente = service.buscar_por_nome(nome)
        if existente:
            logger.warning(f"Função '{nome}' já existe (ID: {existente.get('_id')})")
            sobrescrever = input("Deseja continuar mesmo assim? (s/N): ").lower()
            if sobrescrever != 's':
                logger.info("Operação cancelada")
                return
        
        # Categoria (texto livre)
        funcao_geral = input("Categoria/Função Geral: ").strip() or None
        
        ordem_str = input("Ordem de exibição (número): ").strip()
        ordem = int(ordem_str) if ordem_str.isdigit() else 999
        
        # Criar com Builder
        builder = (FuncaoBuilder()
                   .set_nome(nome)
                   .set_ordem(ordem))
        
        if funcao_geral:
            builder.set_funcao_geral(funcao_geral)
        
        funcao = builder.build()
        
        # Salvar
        funcao_id = service.criar(funcao)
        
        if funcao_id:
            logger.info(f"\n✓ Função criada com sucesso!")
            logger.info(f"  ID: {funcao_id}")
        else:
            logger.error("✗ Erro ao criar função")
    
    except KeyboardInterrupt:
        logger.info("\nOperação cancelada pelo usuário")
    except Exception as e:
        logger.error(f"Erro ao adicionar função: {e}")


def inativar_funcao(funcao_id: str) -> None:
    """
    Inativa função por ID
    
    Args:
        funcao_id: ID da função (string ObjectId)
    """
    service = FuncaoService()
    
    if not service.disponivel:
        logger.error("MongoDB não disponível")
        return
    
    try:
        obj_id = ObjectId(funcao_id)
        
        # Buscar função
        funcao = service.buscar_por_id(obj_id)
        if not funcao:
            logger.error(f"Função {funcao_id} não encontrada")
            return
        
        logger.info(f"\nInativando: {funcao.get('nome')}")
        
        # Tentar inativar
        sucesso = service.marcar_inativo(obj_id)
        
        if sucesso:
            logger.info("✓ Função inativada com sucesso")
        else:
            logger.error("✗ Não foi possível inativar a função")
            logger.error("  Provavelmente existem funcionários vinculados")
    
    except Exception as e:
        logger.error(f"Erro ao inativar função: {e}")


# ============================================================================
# COMANDOS GERAIS
# ============================================================================

def exibir_estatisticas() -> None:
    """
    Exibe estatísticas das 3 coleções
    """
    contrato_service = ContratoService()
    horario_service = HorarioService()
    funcao_service = FuncaoService()
    
    if not contrato_service.disponivel:
        logger.error("MongoDB não disponível")
        return
    
    logger.info("\n" + "=" * 80)
    logger.info("ESTATÍSTICAS DAS COLEÇÕES")
    logger.info("=" * 80)
    
    # Contratos
    total_contratos = contrato_service.colecao.count_documents({})
    ativos_contratos = contrato_service.colecao.count_documents({"status": StatusContrato.ATIVO.value})
    auto_contratos = contrato_service.colecao.count_documents({"auto_criado": True})
    
    logger.info(f"\nCONTRATOS:")
    logger.info(f"  Total:        {total_contratos}")
    logger.info(f"  Ativos:       {ativos_contratos}")
    logger.info(f"  Inativos:     {total_contratos - ativos_contratos}")
    logger.info(f"  Auto-criados: {auto_contratos}")
    
    # Horários
    total_horarios = horario_service.colecao.count_documents({})
    ativos_horarios = horario_service.colecao.count_documents({"status": StatusHorario.ATIVO.value})
    auto_horarios = horario_service.colecao.count_documents({"auto_criado": True})
    
    logger.info(f"\nHORÁRIOS:")
    logger.info(f"  Total:        {total_horarios}")
    logger.info(f"  Ativos:       {ativos_horarios}")
    logger.info(f"  Inativos:     {total_horarios - ativos_horarios}")
    logger.info(f"  Auto-criados: {auto_horarios}")
    
    # Funções
    total_funcoes = funcao_service.colecao.count_documents({})
    ativos_funcoes = funcao_service.colecao.count_documents({"status": StatusFuncao.ATIVO.value})
    auto_funcoes = funcao_service.colecao.count_documents({"auto_criado": True})
    
    logger.info(f"\nFUNÇÕES:")
    logger.info(f"  Total:        {total_funcoes}")
    logger.info(f"  Ativos:       {ativos_funcoes}")
    logger.info(f"  Inativos:     {total_funcoes - ativos_funcoes}")
    logger.info(f"  Auto-criados: {auto_funcoes}")
    
    logger.info("\n" + "=" * 80)
