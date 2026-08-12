# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [0.9.8] - 2026-08-01

### Adicionado

#### 🐳 Infraestrutura Docker unificada
- **docker-compose unificado** (`docker-compose.ms-automatizar.yml`): MongoDB 8.0 + Redis 7.2 + WhatsApp API em um único compose.
- **Backup/restauração MongoDB documentada** (`backup_mongo/`): procedimento de backup completo do banco `MS_Automatizar` e restore validado **6.466 documentos**.
- **Docs novas**: `INFRAESTRUTURA.md` (visão geral de deploy/containers) e `UPGRADE_GOWA_9.md` (guia de migração do WhatsApp API v8→v9).

#### 🔄 WhatsApp API — upgrade para GOWA v9.0.0
- **Imagem** `aldinokemal2104/go-whatsapp-web-multidevice` pinada em `:v9.0.0` no `docker-compose.ms-automatizar.yml`.
- **Basic Auth (`WHATSAPP_BASIC_AUTH`)**: o `whatsapp_service.py` agora envia `Authorization: Basic base64(user:pass)` (v8/v9). Fallback: `WHATSAPP_API_KEY` com `:` vira Basic Auth; token simples vira `Bearer` (legado v7).
- **QR code**: `/app/qr` foi REMOVIDO na v9 — `obter_qr_code()` usa `/app/login` (`results.qr_link`, URL) com fallback p/ `/app/qr` (v8 legacy).
- **Deploy API puro**: `APP_UI_ENABLED=false` e `APP_UI_AUTO_UPDATE=false` (não baixa gowa-ui em rede restrita).
- **Healthcheck do WhatsApp**: trocado de `/app/status` (401 com auth) para `/health` (público).

#### 🛠️ MongoDB em kernel Linux 6.19–7.0.13 (workaround)
- Adicionada env `GLIBC_TUNABLES=glibc.pthread.rseq=1` no serviço `mongodb` (JIRA SERVER-121912) para o MongoDB 8.x iniciar nesses kernels.

### Alterado

- **`whatsapp_service.py` alinhado à v9**: autenticação corrigida para Basic Auth (antes usava Bearer) e fluxo de QR via `/app/login`.
- **Documentação 100% alinhada ao código**: auditoria completa em `AGENTS.md`, `README.md`, `specs/` e `docs/` cobrindo GOWA v9, `pypdfium2`, `--data YYYY-MM-DD`, `WHATSAPP_BASIC_AUTH` e infraestrutura unificada.

### Melhorado

- **Consistência da documentação**: todas as referências de versão e dependências sincronizadas com o estado real do código.

---

## [0.9.7] - 2026-05-01
 
### Adicionado
 
#### 🌐 HTML como Formato Principal de Folha de Ponto
- **Template HTML institucional** (`src/templates/Folha_de_Ponto.html`): Layout completo e fiel ao modelo da empresa
  - Cabeçalho com campos: ID da Folha, Período, Empresa, Atividade, CNPJ, Endereço, Funcionário, CPF, Lotação, Cargo, Horário
  - Tabela de frequência com colunas: Dias, Início, Intervalo (entrada/saída), Término e Assinatura/Observações
  - Suporte a 31 linhas de lançamento (todos os dias do mês)
  - Estilo CSS inline compatível com impressão direta e renderização via WeasyPrint
  - Charset UTF-8 com suporte completo ao português
- **WeasyPrint**: Integrado como conversor HTML → PDF
  - Conversão de alta fidelidade, preservando layout e estilos CSS
  - Elimina dependência do Microsoft Excel e do `win32com` para geração de PDFs
  - Funciona em Windows, Linux e macOS
  - Instalação: `uv add weasyprint`

#### 🔄 WhatsApp API — upgrade para GOWA v9.0.0
- **Imagem** `aldinokemal2104/go-whatsapp-web-multidevice` pinada em `:v9.0.0` no `docker-compose.ms-automatizar.yml`.
- **Basic Auth (`WHATSAPP_BASIC_AUTH`)**: o `whatsapp_service.py` agora envia `Authorization: Basic base64(user:pass)` (v8/v9). Fallback: `WHATSAPP_API_KEY` com `:` vira Basic Auth; token simples vira `Bearer` (legado v7).
- **QR code**: `/app/qr` foi REMOVIDO na v9 — `obter_qr_code()` usa `/app/login` (`results.qr_link`, URL) com fallback p/ `/app/qr` (v8 legacy).
- **Deploy API puro**: `APP_UI_ENABLED=false` e `APP_UI_AUTO_UPDATE=false` (não baixa gowa-ui em rede restrita).
- **Healthcheck do WhatsApp**: trocado de `/app/status` (401 com auth) para `/health` (público).
- Env documentado no `.env_exemplo`.

#### 🛠️ MongoDB em kernel Linux 6.19–7.0.13 (workaround)
- Adicionada env `GLIBC_TUNABLES=glibc.pthread.rseq=1` no serviço `mongodb` (JIRA SERVER-121912) para o MongoDB 8.x iniciar nesses kernels.

#### 🧪 Dependências de desenvolvimento
- `pyproject.toml`/`uv.lock`: grupo `[dependency-groups].dev` (faker, freezegun, pytest, pytest-asyncio, pytest-cov, pytest-mock).

### Alterado
 
- **Pipeline de geração de folhas**: Antes era Excel → win32com → PDF; agora é MongoDB → HTML (template) → WeasyPrint → PDF.
- **PDF → imagem**: `pdf2image` + Poppler substituídos por **`pypdfium2`** (embutido, cross-platform).
### Removido
 
- **Geração via Excel como modelo**: Toda a lógica de preenchimento de planilhas `.xlsx` como template de folha de ponto foi removida
  - Removidas dependências: `openpyxl` (para preenchimento de modelos), `win32com.client` (para conversão Excel → PDF)
- **Dependência do Microsoft Excel para geração de PDFs**: Substituído pelo WeasyPrint — multiplataforma, sem necessidade de Windows ou Office instalado
- **Arquivos `.xlsx` de template de folha de ponto**: O único template de folha agora é o arquivo HTML
### Melhorado
 
- **Velocidade de geração**: O pipeline HTML → WeasyPrint é significativamente mais rápido que a automação Excel via COM
- **Portabilidade**: A geração de folhas e PDFs funciona em qualquer sistema operacional
- **Manutenibilidade do template**: O layout é editado em HTML/CSS puro, sem necessidade de abrir o Excel

---

## [0.9.6] - 2026-02-03

### Adicionado

#### 🖥️ Sistema de Interface Moderna (questionary + rich)
- **Modulo `src/interface/core/`**: Nova infraestrutura de interface
  - `components.py`: Componentes reutilizaveis (`MenuBuilder`, `exibir_tabela`, `exibir_resultado`, `exibir_painel`, `exibir_com_spinner`, `pedir_texto`, `pedir_selecao`, `pedir_confirmacao`, `pedir_inteiro`, `pedir_data`, `pedir_cpf`, `pedir_mes_ano`, `pedir_caminho`, `pedir_selecao_multipla`)
  - `theme.py`: Tema centralizado com cores, estilos e icones padronizados (suporte Unicode e ASCII fallback)
  - `validators.py`: Validadores de input (data, CPF, mes/ano)
  - `MenuBuilder`: Classe builder fluente para criacao de menus com `questionary.select` (navegacao por setas)

- **Icones centralizados**: Dicionario `ICONES` com 45+ icones categorizados (navegacao, status, CRUD, entidades, comunicacao, configuracao, dados, processamento)
  - Deteccao automatica de suporte Unicode no terminal
  - Fallback para ASCII em terminais Windows sem suporte

#### 📧 Melhorias no Envio de E-mails
- **Deteccao automatica de HTML**: `ZohoMailService` agora detecta se o corpo ja contem HTML
- **Conversao de quebras de linha**: `\n` convertido para `<br/>` automaticamente quando o corpo nao e HTML

### Alterado

#### 🔄 Interfaces Refatoradas (9 modulos)
Todos os 9 modulos de interface foram migrados do padrao antigo (`print()` + `input()` + bordas ASCII) para o novo sistema moderno:

- **`menu.py`**: Menu principal com `MenuBuilder`, logo em Rich markup, painel de status do sistema com `exibir_painel`, submenu "Gerenciar Dados"
- **`interface_funcionarios.py`**: Listagem com `rich.Table`, formularios com `pedir_texto`/`pedir_selecao`, filtros interativos, exportacao e estatisticas
- **`interface_empresas.py`**: CRUD completo com componentes modernos, status com cores, formularios validados
- **`interface_folha_de_ponto.py`**: Menus de processamento e listagem com navegacao por setas
- **`interface_holerite.py`**: Processamento de PDFs e envio com interface modernizada
- **`interface_envio_folha_ponto.py`**: Envio por email/WhatsApp com selecao interativa e spinners
- **`interface_envio_holerite.py`**: Envio de holerites com interface padronizada
- **`interface_referencias.py`**: Submenus de contratos, horarios, funcoes, diretorios e feriados com tabelas Rich
- **`interface_configuracoes.py`**: Configuracoes de MongoDB, APIs, sistema e Zoho Mail

#### 📝 Templates de Mensagem
- **Removida assinatura fixa** "Moraes e Santos" dos templates padrao de email (folha de ponto e holerite)
- Corpo do template agora termina em "Atenciosamente," sem nome fixo da empresa

#### 🏗️ Estrutura do Menu
- **Removido menu duplicado** de "Diretorios" do menu "Gerenciar Dados" (acesso apenas via Referencias)
- **Submenu "Gerenciar Dados"**: Reorganizado com Funcionarios, Empresas e Referencias

### Melhorado

- **Navegacao**: Menus com setas (↑↓) via `questionary` substituem digitacao de numeros
- **Validacao de inputs**: Todos os campos agora tem validacao em tempo real (CPF, datas, numeros, caminhos)
- **Feedback visual**: Mensagens de sucesso, erro, aviso e info com icones e cores padronizadas
- **Tabelas de dados**: Todas as listagens usam `rich.Table` com colunas estilizadas
- **Paineis informativos**: Status do sistema, cabecalhos e resultados em paineis `rich.Panel`
- **Performance**: Pre-fetch de contratos na listagem de diretorios (elimina N+1 queries)
- **Compatibilidade**: Fallback automatico de Unicode para ASCII em terminais sem suporte

### Removido

- **71 instancias de `input("Pressione ENTER")`** substituidas por `pausar()`
- **20+ bordas ASCII hardcoded** (`╔═══╗`, `║...║`, `╚═══╝`) substituidas por `rich.Panel`
- **Emojis hardcoded** em strings substituidos pelo dicionario centralizado `ICONES`

---

## [0.9.5] - 2026-01-30

### Adicionado

#### 📱 Múltiplos Dispositivos WhatsApp (Feature Completa)
- **Campo `whatsapp_device_id`** em `EmpresaMongoDB`: Vinculação segura de empresa a dispositivo WhatsApp
  - Formato validado: `XXXXXXXXXX@s.whatsapp.net`
  - Método helper `obter_device_whatsapp()` para obter device_id configurado
  - Validation robusta no modelo com mensagens claras de erro

- **Índices Compostos de Segurança** em `GrupoWhatsAppMongoDB`:
  - Índice único: `(jid, whatsapp_device_id)` previne JID duplicado em devices diferentes
  - Índice de busca: `(nome_normalizado, whatsapp_device_id)` otimiza queries por device

- **Sincronização por Dispositivo** em `GrupoWhatsAppService`:
  - `sincronizar_com_api(grupos_api, device_id)` - Agora obrigatório passar device_id
  - Cada grupo armazenado com vinculação clara ao seu dispositivo
  - Método `_criar_ou_atualizar_com_device()` para upsert por jid+device_id

- **Busca Contextualizada de Grupos**:
  - `obter_jid_por_nome(nome, device_id)` - device_id obrigatório
  - `buscar_por_nome(nome, device_id)` - Filtra por device_id
  - `listar_para_exibicao(device_id)` - device_id obrigatório, sem default
  - Novo método `listar_para_exibicao_sem_filtro()` para admin view
  - Busca parcial em cache antes de fallback ao banco

#### 🎯 Contexto Obrigatório por Empresa/Device
- **Função helper `_selecionar_empresa_para_grupos()`**:
  - Em `interface_envio_folha_ponto.py` e `interface_envio_holerite.py`
  - Lista empresas ativas com device configurado
  - Valida se empresa tem device antes de listar grupos
  - Seleção numérica (1-N) com mensagens de erro específicas

- **Menu de Sincronização Atualizado**:
  - Sincroniza automaticamente
  - Pergunta: "Deseja visualizar os grupos?" (S/N)
  - Se Sim: Exige seleção de empresa antes de listar
  - Mostra apenas grupos da empresa/device selecionado

- **Comandos CLI com Seleção de Empresa**:
  - `envio-sincronizar --listar` agora exige seleção de empresa
  - Mostra mensagem clara se nenhuma empresa tem device
  - Suporte em `folha_de_ponto.py` handler de subcommand

#### ⚡ Pré-Processamento Otimizado de Grupos (Opção C)
- **Método `_preprocessar_grupos_por_empresa()`** em `EnvioFolhaPontoOrquestrador`:
  - Executa UMA VEZ antes do loop de contatos
  - Extrai empresas únicas dos contatos
  - Para cada empresa: busca grupos 1 vez, cria mapa {grupo_normalizado: jid}
  - Armazena em `self._cache_grupos_por_empresa`

- **Performance Comprovada**:
  - Redução de 87% em queries ao banco (150 → 20)
  - Complexidade O(E + G) em vez de O(N*G)
  - 5x mais rápido em envios com múltiplos grupos
  - Fallback automático se cache vazio (segurança)

- **Reutilização em Método de Envio**:
  - `_enviar_whatsapp_grupo()` usa cache em memória
  - Busca parcial em cache antes de fallback
  - Logging detalhado para debug

#### 🔄 Sincronização de Múltiplos Dispositivos
- **`sincronizar_grupos_whatsapp()` reescrito**:
  - Busca todos dispositivos conectados via `whatsapp_service.listar_dispositivos()`
  - Para cada dispositivo: sincroniza grupos separadamente
  - Consolidda resultados (criados, atualizados, inativos)
  - Logging: "Sincronizando X dispositivos"

- **Cada Dispositivo Tratado Independently**:
  - Extrai device_id interno (`disp.get("id")`)
  - Chama `listar_grupos(device_id)` por dispositivo
  - Chama `sincronizar_com_api(grupos_api, device_id)` com device específico

#### 🔐 Roteamento Seguro de Envio
- **Validação Device_id em `_enviar_whatsapp_grupo()`**:
  - Obtém device_jid da empresa (via `empresa_service`)
  - Converte para device_id_interno via `obter_id_dispositivo_por_jid()`
  - Busca grupos APENAS daquele device: `obter_jid_por_nome(nome_grupo, device_id_interno)`
  - Retorna erro específico se empresa sem device ou grupo não encontrado naquele device

- **Mensagens de Erro Específicas**:
  - "Empresa sem dispositivo WhatsApp configurado ou dispositivo não encontrado"
  - "Grupo não encontrado: {nome} (device: {device_id})"
  - Logging: "✓ Grupo 'X' encontrado no dispositivo correto"

#### 📊 Testes Abrangentes
- **31 testes passando** em `test_whatsapp_multidevice.py`:
  - Headers com X-Device-Id: 4 testes
  - Envio arquivo/texto/múltiplos com device_id: 10 testes
  - Empresa com device_id: 4 testes
  - Validação device_id: 6 testes
  - Integração com orquestrador: 1 teste
  - Retrocompatibilidade: 2 testes
  - Edge cases: 3 testes
  - Coverage requirements: 5 testes

- **Mock de `listar_dispositivos()`** nos testes para simular múltiplos devices
- **Validação de headers** para garantir X-Device-Id incluído corretamente
- **Fallback testing** para comportamento sem device_id

### Alterado

#### Modelos de Dados
- **EmpresaMongoDB**: Adicionado campo `whatsapp_device_id` com validação
- **GrupoWhatsAppMongoDB**: Adicionado campo `whatsapp_device_id` com validação
- **GrupoWhatsAppBuilder**: Novo método `device_id()` para construção

#### Serviços
- **GrupoWhatsAppService**:
  - `_criar_indices()`: Índices compostos por device_id
  - `_carregar_cache()`: Chave composta `{device_id}:{nome_normalizado}`
  - `obter_jid_por_nome()`: device_id obrigatório
  - `buscar_por_nome()`: device_id obrigatório
  - `sincronizar_com_api()`: device_id obrigatório
  - `listar_todos()`: Aceita filtro opcional por device_id
  - `listar_para_exibicao()`: device_id obrigatório

#### Orquestrador
- **EnvioFolhaPontoOrquestrador**:
  - Novo método `_preprocessar_grupos_por_empresa()`
  - Atributo `self._cache_grupos_por_empresa` para cache pré-processado
  - `executar()`: Chama pré-processamento antes do loop
  - `_enviar_whatsapp_grupo()`: Usa cache, roteamento por device_id

#### Interface e Comandos
- **interface_envio_folha_ponto.py**:
  - Nova função `_selecionar_empresa_para_grupos()`
  - `menu_sincronizar_grupos()`: Exige seleção de empresa
  - Validação clara de empresa sem device

- **interface_envio_holerite.py**:
  - Nova função `_selecionar_empresa_para_grupos()`
  - `menu_sincronizar_grupos()`: Mesmo padrão da folha de ponto

- **comandos/folha_de_ponto.py**:
  - Handler `envio-sincronizar`: Exige seleção de empresa com `--listar`

### Corrigido

- **Sincronização de Grupos**: Agora sincroniza TODOS os dispositivos, não apenas o primeiro
- **Busca de Grupos**: Impossível buscar grupo de dispositivo errado mesmo com mesmo nome
- **Performance**: Redução massiva de queries desnecessárias (87% redução)
- **Segurança**: Validação rigorosa de device_id em cada etapa

### Testado

- ✅ 31 testes na suite de multidevice
- ✅ Headers com X-Device-Id incluídos corretamente
- ✅ Grupos vinculados ao dispositivo correto
- ✅ Sincronização por dispositivo separado
- ✅ Pré-processamento reduzindo queries
- ✅ Retrocompatibilidade com código antigo
- ✅ Edge cases (múltiplas empresas, dispositivos desconectados, etc)

---

## [0.9.4] - 2026-01-14

### Adicionado

#### 📄 Sistema de Holerites (Novo!)
- **Processamento com Gemini AI**: Extração estruturada de dados de PDFs de holerites
  - `HoleriteExtracaoSchema`: Schema Pydantic para structured output do Gemini
  - Extração de proventos, descontos, bases de cálculo, dados do funcionário
  - Suporte a diferentes tipos de folha: normal, férias, rescisão, 13º salário

- **HoleriteMongoDB**: Modelo completo para armazenamento de holerites
  - Vinculação com funcionário via ObjectId e CPF (para auditoria)
  - Armazenamento de caminho + hash SHA256 do arquivo (não o binário)
  - Status: pendente, processado, enviado, erro
  - Factory method `from_extracao()` para converter saída do Gemini

- **EnvioHoleriteMongoDB**: Registro de envios de holerites
  - Rastreamento por canal (email, whatsapp, whatsapp_grupo)
  - Histórico de sucesso/falha por destinatário

#### 👤 Contatos de Funcionários
- **ContatoFuncionarioMongoDB**: Modelo para múltiplos contatos por funcionário
  - Tipos: telefone, celular, whatsapp, email_pessoal, email_corporativo
  - Status de validação, preferências de envio
  - Métodos `is_whatsapp_disponivel()`, `is_email_disponivel()`
  
- **ContatoFuncionarioBuilder**: Builder pattern para criação intuitiva
  - `set_telefone()`, `set_whatsapp()`, `set_email()`
  - Detecção automática de tipo (celular vs fixo)

- **ContatoFuncionarioService**: CRUD para contatos (`src/services/contato_funcionario_service.py`)
  - `obter_whatsapp_funcionario()`: Busca contato WhatsApp preferencial
  - `obter_email_funcionario()`: Busca email preferencial
  - `marcar_preferencial()`: Define contato preferencial por tipo

#### 🔧 Funcionários - Cadastro Incompleto
- **StatusCadastro enum**: Novo status para cadastros (completo, incompleto, pendente_revisao)
- **Campos opcionais**: `lotacao`, `contrato`, `contrato_empresa_id`, `horario_id`, `funcao_id`
  - Permite criar funcionários com apenas nome + CPF (via processamento de holerites)
- **Métodos de verificação**:
  - `is_cadastro_completo()`: Verifica se todos os campos obrigatórios estão preenchidos
  - `completar_cadastro()`: Preenche campos e atualiza status para COMPLETO
  - `marcar_pendente_revisao()`: Marca para revisão manual
- **FuncionarioBuilder atualizado**:
  - `set_status_cadastro()`: Define status do cadastro
  - `build_incompleto()`: Cria funcionário com dados mínimos
- **FuncionarioService atualizado**:
  - Índice parcial MongoDB (`partialFilterExpression`) para unicidade
  - Índice único por documento (CPF) com `sparse=True`
  - `buscar_por_documento()`: Busca por CPF
  - `listar_incompletos()`: Lista funcionários pendentes de completar
  - `criar_ou_buscar_por_documento()`: Cria funcionário incompleto se não existir

#### 📊 Serviços de Holerites
- **HoleriteService** (`src/services/holerite_service.py`):
  - CRUD completo para holerites
  - Índices otimizados (funcionário+competência, hash de arquivo)
  - `registrar_envio()`: Registra tentativas de envio
  - `listar_pendentes_envio()`: Lista holerites aguardando envio
  - `contar_por_status()`: Estatísticas por status

- **PlanilhaHoleritesService** (`src/services/planilha_holerites_service.py`):
  - Leitura de planilha Excel de holerites
  - Similar ao PlanilhaContatosService (folhas de ponto)
  - Suporte a mês/ano de referência por coluna ou parâmetro

#### ⚙️ Processadores
- **HoleriteProcessador** (`src/processadores/holerite_processador.py`):
  - Extrai dados de PDFs usando Gemini AI
  - Vincula ou cria funcionário automaticamente
  - Cria/atualiza contatos do funcionário
  - Evita duplicatas via hash SHA256
  - `processar_arquivo()`: Processa um PDF
  - `processar_diretorio()`: Processa todos os PDFs de um diretório

- **EnvioHoleriteOrquestrador** (`src/processadores/envio_holerite_orquestrador.py`):
  - **Modo Planilha**: Envia para grupos/contatos da planilha Excel
  - **Modo MongoDB**: Envia diretamente para funcionários via contatos cadastrados
  - Suporte a Email (Zoho) e WhatsApp
  - Registro de envios no MongoDB
  - Relatórios consolidados

#### 🖥️ Interface de Menus
- **Interface_Holerite atualizada** (`src/interface/interface_holerite.py`):
  - Nova opção: "Processar PDFs com IA (Extração Gemini)"
  - Nova opção: "Enviar Holerites" (abre submenu)
  - Nova opção: "Listar Holerites no MongoDB"
  - Menu expandido de 4 para 7 opções

- **Interface_Envio_Holerite** (`src/interface/interface_envio_holerite.py`):
  - Submenu completo para envio de holerites
  - Modo Planilha: validação, simulação (dry-run), envio real
  - Modo MongoDB: estatísticas, simulação, envio real
  - Verificação de serviços, sincronização de grupos, templates

#### 🎯 Comandos CLI
- **holerite processar_pdfs**: Processa PDFs com Gemini AI
  - `--caminho`: Diretório ou arquivo PDF
  - `--empresa_id`: ObjectId da empresa (opcional)
  - `--temperatura`: Temperatura do Gemini (0.0-1.0)

- **holerite enviar**: Envia holerites por e-mail/WhatsApp
  - `--competencia`: Formato MM/AAAA
  - `--modo`: "mongodb" ou "planilha"
  - `--canais`: "email,whatsapp"
  - `--dry_run`: Modo simulação

- **holerite listar**: Lista holerites no MongoDB
  - `--competencia`: Filtrar por competência
  - `--funcionario`: Filtrar por nome
  - `--status`: Filtrar por status
  - `--limite`: Máximo de resultados

- **holerite stats**: Estatísticas de holerites
  - `--competencia`: Competência específica

### Melhorado

- **Arquitetura**: Separação clara entre schema de extração (Gemini) e modelo de armazenamento (MongoDB)
- **Auditoria**: Campo `funcionario_documento` mantido no holerite para rastreabilidade
- **Performance**: Armazena apenas caminho + hash do arquivo (não o binário do PDF)

### Otimizado

#### ⚡ Cache Híbrido com Redis
- **CacheService** (`src/services/cache_service.py`): Nova camada de cache com Redis + fallback em memória
  - Singleton thread-safe com detecção automática de disponibilidade
  - TTL configurável via `CACHE_TTL` (padrão: 300s)
  - Métodos batch: `get_many()`, `set_many()` para operações em lote
  - Invalidação por padrão: `invalidate("empresas:*")` com suporte a wildcards
  - Fallback transparente para memória se Redis indisponível

- **Redis 7.2-alpine**: Container Docker com persistência e health checks
  - `docker-compose.redis.yml`: Configuração pronta para desenvolvimento
  - Variáveis de ambiente: `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_ENABLED`

#### 🚀 Aggregation Pipelines (MongoDB)
Novos métodos otimizados no **FuncionarioService** eliminando N+1 queries:

1. **`buscar_aniversariantes(mes)`**: Filtro por mês usando `$expr + $month`
   - **ANTES**: 1000 registros + loop Python filtrando
   - **DEPOIS**: 1 aggregation retornando apenas aniversariantes

2. **`buscar_com_relacionamentos(id)`**: Lookup de funcionário com 5 joins
   - **ANTES**: 7 queries (1 funcionário + 6 relacionamentos)
   - **DEPOIS**: 1 aggregation com $lookup paralelos

3. **`exportar_com_relacionamentos()`**: Exportação completa com relacionamentos
   - **ANTES**: 1 query + 600 queries (6 por funcionário × 100)
   - **DEPOIS**: 1 aggregation + 1 batch de contatos

4. **`listar_por_empresa_com_contagem()`**: Lista com contagem usando `$facet`
   - Dados + total em query única

5. **`obter_estatisticas()`**: 3 agregações paralelas com `$facet`
   - Por status, por contrato, top 10 lotações
   - **ANTES**: 1 query + 3 loops Python
   - **DEPOIS**: 1 aggregation com 3 facets

6. **`validar_referencias_batch()`**: Validação de múltiplas referências
   - **ANTES**: 4 queries sequenciais (find_one cada)
   - **DEPOIS**: 4 queries paralelas com `count_documents + $in`

#### 📊 Batch Queries
- **ContatoFuncionarioService.obter_contatos_batch()**: Busca contatos de múltiplos funcionários
  - Elimina problema N+1 em loops de envio
  - **ANTES**: 2000 funcionários = 4000 queries (email + whatsapp cada)
  - **DEPOIS**: 2000 funcionários = 1 aggregation
  - **Ganho**: 99.975% redução de queries

- **EnvioHoleriteOrquestrador**: Pré-carregamento batch antes de loop
  - Contatos carregados uma vez, reutilizados em loop

#### 🔍 Índices Compostos
5 novos índices otimizados no **FuncionarioService**:

1. `idx_contrato_status`: Busca por empresa + filtro de status
2. `idx_data_nascimento`: Suporte a filtro de aniversariantes com `$expr`
3. `idx_contrato_lotacao`: Relatórios e estatísticas
4. `idx_funcao_horario`: Filtros de folha de ponto
5. `idx_diretorio_status`: Geração de folhas e validações

#### 💾 Cache Pré-load de Empresas
- **EmpresaService**:
  - `_carregar_cache_completo()`: Pré-carga de todas empresas (~50-200 registros)
  - Cache híbrido (memória local + Redis) para lookup O(1)
  - `_invalidar_cache()`: Invalidação automática em CREATE/UPDATE/DELETE
  - Recarregamento automático após invalidação

#### 📈 Otimizações de Interface
- **interface_funcionarios.py**:
  - `exportar_funcionarios_json()`: 200 linhas → 50 linhas (usa aggregation)
  - Filtro aniversariantes: Usa `buscar_aniversariantes()` ao invés de loop
  - `exibir_estatisticas()`: Usa `obter_estatisticas()` com `$facet`
  - `_exibir_detalhes_funcionario()`: Usa `buscar_com_relacionamentos()`

#### 🎯 Performance Global
- **Redução de 95%+ em queries MongoDB** em operações críticas:
  - Exportação de funcionários: 2500 queries → 2 queries
  - Envio de 1000 holerites: 2000 queries → 1 query
  - Detalhes de funcionário: 7 queries → 1 query
  - Estatísticas: 1000 registros processados em Python → 1 aggregation

---

## [0.9.3] - 2026-01-14

### Adicionado

#### 📧 Sistema de Envio de Folhas de Ponto (Versão Final)
- **Estratégia de Envio Otimizada**: Envio de mensagem de texto primeiro, seguido dos arquivos em sequência
- **Delays Anti-Rate Limiting**: 
  - 1.5s entre arquivos
  - 1.0s após mensagem de texto
  - 3.0s após erros
- **Suporte a API v8+**: Compatibilidade total com `go-whatsapp-web-multidevice` versão 8+

#### 🔧 WhatsApp Service
- **Novo endpoint**: `/send/message` para envio de texto (substituiu `/send/text`)
- **Parsing de resposta v8+**: Tratamento de `{"code": "SUCCESS", "results": {...}}`
- **Delays integrados**: `DELAY_ENTRE_ARQUIVOS`, `DELAY_APOS_MENSAGEM`, `DELAY_APOS_ERRO`
- **`enviar_multiplos_arquivos()`**: Refatorado para enviar texto primeiro, depois arquivos sequencialmente

#### 📬 Zoho Mail Service  
- **Upload de anexos corrigido**: Parâmetro `uploadType=multipart` obrigatório na URL
- **Parsing de resposta lista**: Tratamento correto quando API retorna lista em `data`

### Corrigido

#### 🐛 Correções Críticas
- **WhatsApp API v8+**: Corrigido parsing de `verificar_status()` para formato `results` vs `data`
- **Grupos WhatsApp**: Corrigido `listar_grupos()` para parsear `results.data`
- **Sincronização de Grupos**: Corrigido conflito MongoDB em `criar_ou_atualizar()` (campo `criado_em`)
- **Registro de Envios**: Corrigido uso de `obter_config_retry()` que retorna tupla
- **Upload de Anexos**: Corrigido erro "fileName is null" adicionando `uploadType=multipart`
- **Resposta de Anexos**: Tratamento de lista vs dict no response do Zoho Mail

#### 📊 Orquestrador de Envios
- **`_registrar_envio()`**: Corrigido para usar `_config_retry_max_tentativas` ao invés de dict
- **Detecção de Status Parcial**: Melhorada lógica de detecção em resultados aninhados

### Melhorado

- **Logs detalhados**: Mensagens de progresso para cada arquivo enviado
- **Tratamento de erros**: Mensagens mais claras para debugging
- **Performance**: Remoção de delays redundantes do orquestrador (agora no service)

---

## [0.9.2] - 2025-12-05

### Adicionado

#### 🏗️ Novos Modelos Pydantic
- **FuncaoMongoDB**: Modelo completo para Funções/Cargos (`src/models/funcao_models.py`)
  - Validadores customizados, histórico de alterações e soft delete
  - Normalização para busca fuzzy com `nome_normalizado`
  - Suporte a descrição e ativo/inativo

- **HorarioMongoDB**: Modelo para Horários de Trabalho (`src/models/horario_models.py`)
  - Jornadas complexas (entrada1/saída1, entrada2/saída2)
  - Validação de formato de horário
  - StatusHorario com soft delete

- **DiretorioMongoDB**: Modelo para Diretórios (`src/models/diretorio_models.py`)
  - Relacionamento 1:1 com Contrato via ObjectId
  - Organização de pastas de folhas de ponto
  - Validação de caminhos

- **FeriadoMongoDB**: Modelo para Feriados (`src/models/feriado_models.py`)
  - Tipos: nacional, estadual, municipal, ponto_facultativo
  - Suporte a feriados recorrentes
  - Campos opcionais para UF e cidade

#### 📦 Novos Serviços
- **HorarioService**: Service completo para gerenciar Horários (`src/services/horario_service.py`)
  - CRUD, cache em memória, soft delete e busca fuzzy
  - Auto-cadastro de horários padrão

- **FuncaoService**: Service para Funções (`src/services/funcao_service.py`)
  - CRUD completo com cache permanente
  - Integração MongoDB e busca por nome

- **DiretorioService**: Service para Diretórios (`src/services/diretorio_service.py`)
  - Integração com HistoricoMixin
  - Cache por contrato_id e auto-cadastro

- **FeriadoService**: Service para Feriados (`src/services/feriado_service.py`)
  - Importação de feriados nacionais padrão
  - Busca por período/tipo e geração de DataFrame

#### 🔄 Sistema de Histórico Automático
- **historico_decorators.py**: Decorador `@registrar_historico` para tracking automático
  - `HistoricoMixin` fornece métodos auxiliares para histórico
  - Rastreamento de valores anteriores e novos
  - Registro de origem, timestamp e detalhes da alteração

#### 🖥️ Interface de Referências
- **interface_referencias.py**: Interface interativa completa para gerenciar Referências
  - Submenus para Contratos, Horários, Funções, Diretórios e Feriados
  - Listagem, adição e inativação de registros
  - Integração com todos os serviços de referências

#### 🎯 Novos Comandos CLI
- **referencias.py**: Comandos CLI para Contratos, Horários e Funções
  - `python automatizar.py referencias contratos listar`
  - `python automatizar.py referencias horarios adicionar`
  - `python automatizar.py referencias funcoes inativar`

- **diretorios.py**: Comandos CLI para Diretórios
  - `python automatizar.py diretorios listar`
  - `python automatizar.py diretorios criar_para_contratos`
  - Estatísticas e vinculação automática

#### 🔧 Scripts de Migração
- **migrar_diretorio_interno.py**: Converte `diretorio_interno` (string) para referência ObjectId `diretorio_id`
- **vincular_diretorios_contratos.py**: Vincula diretórios aos contratos baseado no nome do contrato no caminho
- **migrar_feriados.py**: Importa feriados do Excel para MongoDB
- **migrar_timestamps_historico.py**: Converte timestamps de string ISO para DateTime nativo
- **reverter_e_recriar_diretorios.py**: Script para reverter migração e recriar diretórios

### Melhorado

- **Modelo Funcionário**:
  - Novos campos de relacionamento: `funcao_id`, `horario_id`, `contrato_id`, `diretorio_id` como ObjectId
  - Campo legado `diretorio_interno` mantido para retrocompatibilidade
  - Método `obter_lotacao()` com fallback para lotação normalizada

- **Interface Folha de Ponto**:
  - Uso de `mongodb_utils` centralizado para buscar dados relacionados
  - Exibição formatada com dados enriquecidos (função, horário, contrato)
  - Interface 100% MongoDB para geração de folhas de ponto

- **Comandos Folha de Ponto**:
  - Novo subcomando `criar_mongodb_id` para criar folha usando ObjectIds
  - Novo subcomando `criar_mongodb_filtro` para criar folhas em lote com filtros
  - Filtros por lotação, função, contrato e status ativo

- **Menu Principal**:
  - Verificação de ambiente e conexões no startup
  - Exibição de status visual do sistema (Ambiente ✅/⚠️, MongoDB ✅/❌)
  - Integração com ValidadorAmbiente e health_check

- **MongoDB Utils**:
  - Cache de serviços `_service_cache` para evitar reinicialização
  - Lazy loading de serviços (inicializados apenas quando necessários)
  - Novas funções utilitárias: `buscar_diretorio_por_id()`, `buscar_feriado_por_id()`

- **Services `__init__.py`**:
  - Exportação de novos serviços: HorarioService, FuncaoService, DiretorioService, FeriadoService
  - Exportação de decoradores: registrar_historico, HistoricoMixin

### Alterado

- **Arquitetura de Relacionamentos**:
  - Antes: `diretorio_interno` como string direta no funcionário
  - Agora: `diretorio_id` como ObjectId referenciando coleção `diretorios`
  - Novos relacionamentos: `funcao_id` → `funcoes`, `horario_id` → `horarios`

- **Novas Coleções MongoDB**:
  - `funcoes`: Cargos/funções dos funcionários
  - `horarios`: Jornadas de trabalho
  - `diretorios`: Pastas para organização de folhas (1:1 com contratos)
  - `feriados`: Calendário de feriados

## [0.9.1] - 2025-11-26

### Adicionado

#### 🔌 MongoDB Connection Pool
- **Pool de Conexões Centralizado**: Gerenciamento eficiente de conexões MongoDB
  - Padrão Singleton para instância única global
  - Thread-safe com Lock para ambientes multi-thread
  - Configuração flexível de pool (2-10 conexões)
  - Arquivo: `src/services/mongodb_connection.py`

- **Classe MongoDBConnectionPool**:
  - `health_check()` - Retorna status completo (latência, versão servidor, pool size)
  - `ping()` - Verificação rápida de conexão
  - `get_database()` - Obtém instância do banco de dados
  - `get_collection()` - Obtém coleção específica
  - `fechar()` - Encerra conexão limpa

- **Instância Global**: `mongodb_pool` exportada para uso direto
- **Função auxiliar**: `verificar_conexao_mongodb()` para verificação simples

#### 💓 Health Check e Monitoramento
- **Verificação no Startup**: Health check automático ao iniciar o menu
- **Métricas de Latência**: Medição em milissegundos do tempo de resposta
- **Informações do Servidor**: Versão MongoDB e tamanho do pool
- **Indicadores Visuais**: ✅ OK ou ❌ Erro no status do sistema

#### ✅ Validação de Ambiente
- **ValidadorAmbiente**: Classe para validação de variáveis de ambiente
  - Arquivo: `src/utils/env_validator.py`
  - Validação de variáveis obrigatórias e opcionais
  - Relatório detalhado de configurações

- **Variáveis Validadas**:
  - `MONGO_URI` - Obrigatória (padrão: localhost)
  - `KEY_API_GEMINI` - Obrigatória
  - `KEY_API_MISTRAL` - Obrigatória
  - `MONGO_DATABASE_NAME` - Obrigatória (padrão: MS_Automatizar)

- **Métodos Disponíveis**:
  - `validar()` - Retorna se ambiente está válido
  - `obter_resumo()` - Estatísticas de variáveis (total, configuradas, faltando)
  - `validar_ou_avisar()` - Exibe avisos no console

#### 📄 Paginação nas Listagens
- **FuncionarioService**:
  - `listar_todos(skip=0, limit=100)` - Listagem paginada de funcionários

- **EmpresaService**:
  - `listar_todos(skip=0, limit=100)` - Listagem paginada de empresas
  - `listar_incompletas(skip=0, limit=100)` - Empresas incompletas paginadas
  - `contar_total()` - Contagem total de empresas

- **FolhaDePontoService**:
  - `listar_todos(skip=0, limit=100)` - Listagem paginada de folhas
  - `contar_total()` - Contagem total de folhas

#### 🖥️ Status no Menu Principal
- **Dashboard de Status**: Exibição do status do sistema ao iniciar
- **MongoDB Status**: Indicador de conexão com latência
- **Ambiente Status**: Indicador de variáveis configuradas
- **Formato Visual**: Ícones coloridos para fácil identificação

### Melhorado

- **Gerenciamento de Conexões**:
  - Pool reutilizável evita reconexões desnecessárias
  - Conexões mantidas entre operações
  - Timeout configurável para operações

- **Startup do Menu**:
  - Verificações de saúde antes de exibir opções
  - Alertas claros sobre problemas de configuração
  - Experiência do usuário melhorada

- **Performance de Listagens**:
  - Paginação evita carregar todos os registros na memória
  - Contagem separada para estatísticas
  - Queries otimizadas com skip/limit

### Alterado

- **menu.py**: Adicionado health check e validação de ambiente no startup
- **services/__init__.py**: Exporta novos módulos (mongodb_pool, verificar_conexao_mongodb)

## [0.9.0] - 2025-11-26

### Adicionado

#### 🏗️ Arquitetura de Serviços Refatorada
- **Serviços Individuais**: Cada serviço agora tem seu próprio arquivo dedicado
  - `funcionario_service.py` - CRUD completo de funcionários
  - `empresa_service.py` - Gerenciamento de empresas
  - `folha_ponto_service.py` - Operações com folhas de ponto
  - `funcao_service.py` - Gerenciamento de funções
  - `horario_service.py` - Gerenciamento de horários
  - `contrato_service.py` - Gerenciamento de contratos
  
- **mongodb_utils.py**: Funções utilitárias centralizadas para operações MongoDB
  - `buscar_funcao_por_id()` - Busca função por ObjectId
  - `buscar_horario_por_id()` - Busca horário por ObjectId
  - `buscar_contrato_por_id()` - Busca contrato por ObjectId
  - `buscar_funcionario_por_id()` - Busca funcionário por ObjectId
  - `buscar_empresa_por_id()` - Busca empresa por ObjectId
  - `buscar_folha_ponto_por_id()` - Busca folha de ponto por ObjectId
  - `enriquecer_funcionario_com_referencias()` - Adiciona dados de referências
  - `enriquecer_folha_com_referencias()` - Adiciona dados de referências
  - `listar_todas_funcoes()` - Lista todas as funções disponíveis
  - `listar_todos_horarios()` - Lista todos os horários disponíveis
  - `listar_todos_contratos()` - Lista todos os contratos disponíveis

- **Cache de Serviços**: Instâncias globais cacheadas para melhor performance
  - `funcionario_service` - Instância global do FuncionarioService
  - `empresa_service` - Instância global do EmpresaService
  - `folha_de_ponto_service` - Instância global do FolhaDePontoService

#### 🎯 Menu Unificado de Folha de Ponto
- **Opção 1 consolidada**: Processar PDFs e salvar no MongoDB
- **Opção 2 com submenu**: Listar funcionários, empresas ou folhas de ponto
- Interface simplificada com menos opções redundantes
- Fluxo mais intuitivo para o usuário

### Melhorado

- **Arquitetura**:
  - Menor acoplamento entre componentes
  - Serviços independentes e testáveis
  - Código mais organizado seguindo princípios SOLID
  - Lazy loading de serviços (inicializados sob demanda)

- **Performance**:
  - Cache de instâncias de serviços evita reinicialização
  - Imports otimizados com lazy loading
  - Redução de conexões redundantes ao MongoDB

- **Retrocompatibilidade**:
  - `cache_service.py` re-exporta todos os serviços para compatibilidade
  - Imports existentes continuam funcionando sem alterações
  - Migração gradual possível

- **Documentação**:
  - README atualizado com nova estrutura de serviços
  - Exemplos de código para novos imports
  - Changelog detalhado com todas as mudanças

### Alterado

- **Estrutura de arquivos**:
  - `cache_service.py` agora contém apenas `CacheOCRMongoDB`
  - Serviços movidos para arquivos individuais
  - `__init__.py` do services atualizado com novos exports

- **Imports recomendados**:
  ```python
  # Forma recomendada (v0.9.2+)
  from src.services import FuncionarioService, funcionario_service
  
  # Ou importação direta do módulo
  from src.services.funcionario_service import FuncionarioService, funcionario_service
  ```

## [0.8.0] - 2025-11-24

### Adicionado

#### 🤖 Processamento Inteligente de Folhas de Ponto
- **ProcessadorFolhaPonto**: Pipeline completo para análise de PDFs manuscritos
  - Validação de arquivos
  - Extração com Gemini 2.5 Pro
  - Lookup inteligente de funcionários
  - Armazenamento automático em MongoDB
- **Structured Output**: Extração de dados validados com schemas Pydantic
- **Retry inteligente**: Até 3 tentativas com temperatura ajustável
- **Métricas detalhadas**: Tempo por etapa, tokens utilizados, taxa de sucesso
- Método `processar_pdfs()` em `Folha_de_Ponto` para processar múltiplos PDFs
- Suporte a processamento em lote de diretórios completos

#### 💾 Persistência MongoDB Avançada
- **Modelos Pydantic V2**:
  - `FuncionarioMongoDB`: Modelo completo com validações e builders
  - `EmpresaMongoDB`: Modelo de empresa com CNPJ e relacionamentos
  - `FolhaDePontoMongoDB`: Estrutura completa com dias e análise IA
  - `DiaFolhaPonto`: Modelo de dia individual com horários e totalizações
  - `AnaliseIAResultado`: Resultado detalhado da análise Gemini
  
- **Serviços MongoDB Especializados**:
  - `FuncionarioService`: CRUD completo para funcionários
  - `EmpresaService`: Gerenciamento de empresas
  - `FolhaDePontoService`: Gestão de folhas de ponto
  - Busca fuzzy com normalização Unicode
  - Autocadastro inteligente de registros incompletos
  
- **Relacionamentos N:N**: ObjectId references entre coleções
- **Índices otimizados**: Unique constraints e performance queries
- **Histórico de alterações**: Tracking completo de mudanças

#### 🧹 Sanitização e Validação
- `SanitizadorFuncionario`: Limpeza inteligente de dados de PDFs
- `ConstrutorFuncionarioIncompleto`: Criação automática de registros parciais
- Validadores customizados em todos os modelos Pydantic
- Normalização de nomes com Unicode

#### 🔧 Melhorias nos Serviços de IA
- **GeminiService**:
  - Upgrade para Gemini 2.5 Pro em análises complexas
  - Structured Output com `documento_estruturado()` e `imagem_estruturada()`
  - File API para documentos >20MB
  - Schemas Pydantic inlined (resolve $defs automaticamente)
  - Configuração dinâmica de temperatura e parâmetros
  
- **Totalização Automática**:
  - Cálculo de horas trabalhadas por dia
  - Total de horas no mês
  - Contagem de faltas, feriados e finais de semana

### Melhorado

- **Folha de Ponto**:
  - Autocadastro de funcionários durante geração de folhas
  - Relacionamento empresa-funcionário atualizado automaticamente
  - Conversão automática de date para datetime para MongoDB
  - Validação de unicidade por funcionário/empresa/período
  
- **Performance**:
  - Índices compostos para buscas rápidas
  - Cache de OCR com hash SHA256
  - Queries otimizadas com projeções
  
- **Documentação**:
  - README expandido com todos os novos recursos
  - Exemplos de código para processamento de PDFs
  - Documentação de modelos Pydantic
  - Changelog detalhado

### Corrigido

- Tratamento de erros E11000 (duplicatas) em MongoDB com retry automático
- Conversão correta de `date` para `datetime` em documentos MongoDB
- Validação de schemas Pydantic com `$defs` inlined
- Melhor tratamento de campos opcionais em extração de PDFs
- Normalização consistente de nomes em buscas fuzzy
- Atualização correta de CNPJ em empresas existentes

### Alterado

- MongoDB agora é **recomendado** (antes era opcional)
  - Funcionalidades completas requerem MongoDB
  - Cache OCR funciona em memória sem MongoDB (limitado)
  - Processamento de PDFs **requer** MongoDB
  
- Modelo Gemini padrão alterado para `gemini-2.5-pro` (análises complexas)
- Estrutura de dados de folhas não duplica mais informações de funcionário/empresa
- Relacionamentos agora usam ObjectId em vez de dados duplicados

## [0.7.1] - 2025-11-13

### Melhorado

- Otimização do cache OCR com MongoDB
- Melhorias na interface do usuário
- Refatoração de código seguindo princípios SOLID

### Corrigido

- Correções de bugs menores
- Melhor tratamento de exceções

## [0.7.0] - 2025-11-01

### Adicionado

- Sistema de cache OCR com MongoDB
- Integração com Mistral AI para OCR
- Suporte a arquivos online do OneDrive
- Conversão inteligente de URLs do OneDrive

### Melhorado

- Performance do processamento de holerites
- Interface de linha de comando mais robusta

## [0.6.0] - 2025-10-15

### Adicionado

- Geração automática de folhas de ponto
- Integração com Google Gemini
- Sistema de logs estruturado
- Comandos CLI para folhas de ponto

### Melhorado

- Estrutura modular do projeto
- Separação de responsabilidades (SOLID)

## [0.5.0] - 2025-09-20

### Adicionado

- Processamento de holerites com OCR
- Renomeação automática de arquivos
- Interface interativa

### Corrigido

- Problemas com encoding de caracteres
- Erros na conversão de PDFs

---

## Categorias de Mudanças

- `Adicionado` para novas funcionalidades
- `Melhorado` para mudanças em funcionalidades existentes
- `Descontinuado` para funcionalidades que serão removidas
- `Removido` para funcionalidades removidas
- `Corrigido` para correção de bugs
- `Segurança` para vulnerabilidades

---

**Legenda de Emojis:**
- 🤖 IA e Machine Learning
- 💾 Banco de Dados
- 🔧 Ferramentas e Utilitários
- 📊 Relatórios e Análises
- 🧹 Limpeza e Manutenção
- ⚡ Performance
- 📝 Documentação
- 🐛 Correção de Bugs
- 🔒 Segurança
