# SPEC: Folha de Ponto (Timesheet)

## 1. Visao Geral

O dominio Folha de Ponto (Timesheet) e o modulo central do MS-Automatizar responsavel por automatizar o ciclo completo de gestao de ponto dos funcionarios da empresa Moraes & Santos.

### Ciclo completo

```
Geracao (MongoDB + PDF) → Processamento IA → Envio (Email + WhatsApp)
```

O sistema abrange tres grandes fluxos:

1. **Geracao de Folhas**: Cria folhas de ponto em PDF a partir de dados do MongoDB, com template HTML fiel ao modelo institucional, calculo de dias uteis/feriados e estrutura de diretorios por ano/mes/contrato.

2. **Processamento de PDFs Manuscritos com IA**: Leitura de folhas preenchidas a mao usando Gemini 2.5 Pro (Structured Output, ate 3 retries com temperature escalonada), extracao de dados validados via Pydantic, lookup fuzzy de funcionarios com autocadastro de registros incompletos, e armazenamento em MongoDB.

3. **Envio Automatizado**: Distribuicao das folhas em PDF por Email (Zoho Mail OAuth2), WhatsApp individual e WhatsApp em grupos, com templates de mensagem personalizaveis, suporte a multiplos dispositivos WhatsApp por empresa, e registro completo de todos os envios no MongoDB.

---

## 2. Arquitetura

### Diagrama de Camadas

```
┌──────────────────────────────────────────────────────────┐
│                   ENTRY POINT                             │
│          automatizar.py → start_command()                 │
└──────────────────┬───────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
┌─────────────────┐  ┌──────────────────┐
│   CLI (argparse) │  │  TUI (questionary│
│  comandos/       │  │  + rich)         │
│  folha_de_ponto. │  │  interface/      │
│  py              │  │  interface_folha │
│                  │  │  _de_ponto.py    │
│                  │  │  interface_envio │
│                  │  │  _folha_ponto.py │
└────────┬────────┘  └────────┬─────────┘
         │                    │
         └────────┬───────────┘
                  ▼
┌─────────────────────────────────────────────┐
│           ORQUESTRADORES                     │
│  processadores/processador_folha_ponto.py    │
│  (pipeline IA: validar→extrair→lookup→salvar)│
│                                              │
│  processadores/envio_folha_ponto_            │
│  orquestrador.py                             │
│  (envio email+whatsapp com relatorio)        │
└─────────────────────┬───────────────────────┘
                      ▼
┌─────────────────────────────────────────────┐
│              SERVICOS                        │
│  folha_ponto_service.py    (CRUD folhas)     │
│  envio_folha_ponto_service (CRUD envios)     │
│  funcionario_service.py    (CRUD func.)      │
│  empresa_service.py        (CRUD empresas)   │
│  feriado_service.py        (feriados)        │
│  funcao_service.py         (funcoes)         │
│  horario_service.py        (horarios)        │
│  contrato_service.py       (contratos)       │
│  diretorio_service.py      (diretorios)      │
│  template_mensagem_serv.   (templates msg)   │
│  grupo_whatsapp_service.py (grupos WA)       │
│  whatsapp_service.py       (API WA)          │
│  zoho_mail_service.py      (API Zoho)        │
│  planilha_contatos_service (planilha Excel)  │
│  analise_ai_service.py     (Gemini/Mistral)   │
│  cache_service.py          (Redis+memoria)    │
│  mongodb_connection.py     (pool central)    │
│  mongodb_utils.py          (helpers)         │
└─────────────────────┬───────────────────────┘
                      ▼
┌─────────────────────────────────────────────┐
│              MODELOS (Pydantic V2)           │
│  folha_de_ponto_models.py                   │
│  envio_folha_ponto_models.py                │
│  funcionario_models.py                      │
│  empresa_models.py                          │
│  contrato_models.py                         │
│  horario_models.py                          │
│  funcao_models.py                           │
│  diretorio_models.py                        │
│  feriado_models.py                          │
│  template_mensagem_models.py                │
│  grupo_whatsapp_models.py                   │
└─────────────────────┬───────────────────────┘
                      ▼
┌─────────────────────────────────────────────┐
│           INFRAESTRUTURA                     │
│  MongoDB (Atlas)        │ Redis 7.2          │
│  go-whatsapp-web-       │ WeasyPrint         │
│  multidevice (Docker)   │ (HTML→PDF)         │
│  Google Gemini 2.5 Pro   │ Zoho Mail API     │
└─────────────────────────────────────────────┘
```

### Fluxo Principal de Geracao

```
CLI/TUI
  │
  ▼
Folha_de_Ponto.criar_mongodb_por_id()
  ou .criar_mongodb_por_filtros()
  │
  ├─▶ FuncionarioService.buscar_por_id()
  ├─▶ EmpresaService.buscar_por_id()
  ├─▶ FuncaoService.buscar_por_id()
  ├─▶ HorarioService.buscar_por_id()
  ├─▶ ContratoService.buscar_por_id()
  ├─▶ DiretorioService.obter_nome_diretorio()
  │
  ▼
GeradorFolhaPonto._construir_documento_mongodb()
  → FolhaDePontoMongoDB() com FolhaDePontoData
  │
  ▼
GeradorFolhaPonto._salvar_folha_mongodb()
  → FolhaDePontoService.salvar_ou_atualizar()
  │
  ▼
ProcessadorFolhaPonto.criar_contexto_html()
  → contexto com dias, feriados, empresa, funcionario
  │
  ▼
FolhaPontoHtmlTemplate.render(contexto)
  → HTML (Jinja2)
  │
  ▼
HtmlToPdfConverter.salvar_html_como_pdf()
  → PDF (WeasyPrint)
```

### Fluxo de Processamento IA

```
PDF preenchido (manuscrito)
  │
  ▼
ProcessadorFolhaPonto.processar()
  │
  ├─ ETAPA 1: _validar_arquivo()
  │   → existência, tipo PDF, tamanho < 50MB
  │
  ├─ ETAPA 2: _extrair_gemini()
  │   → Gemini 2.5 Pro + Structured Output
  │   → Até 3 tentativas (temp 0.2→0.4→0.6)
  │   → Schema: ExtratorFolhaPonto (Pydantic)
  │
  ├─ ETAPA 3: _lookup_funcionario()
  │   → Busca por nome_normalizado
  │   → Fuzzy match (similaridade ≥ 0.75)
  │   → Autocadastro via ConstrutorFuncionarioIncompleto
  │   → Autocadastro empresa via EmpresaService
  │
  └─ ETAPA 4: _armazenar_mongodb()
      → Converte Extraido→DiaFolhaPonto
      → Cria FolhaDePontoMongoDB
      → Insere/Upsert no MongoDB
      → Atualiza relacionamentos (empresas_ids)
```

### Fluxo de Envio

```
CLI/TUI: executar(mes, ano, tipos_envio)
  │
  ├─ verificar_servicos() → Zoho, WhatsApp
  ├─ sincronizar_grupos_whatsapp() → multidevice
  ├─ _preprocessar_grupos_por_empresa()
  │   → cache dos grupos na memoria
  │
  ▼
Loop de contatos (planilha Excel):
  │
  ├─ Email:
  │   → Renderizar template (TipoTemplateEnum.EMAIL)
  │   → zoho_mail_service.enviar_email()
  │   → Registrar envio no MongoDB
  │
  ├─ WhatsApp Individual:
  │   → Renderizar template (WHATSAPP_INDIVIDUAL)
  │   → whatsapp_service.enviar_multiplos_arquivos()
  │   → Delay 1.5s entre arquivos, 1s apos texto
  │
  └─ WhatsApp Grupo (com cache pre-processado):
      → Usar _cache_grupos_por_empresa (evita N+1 queries)
      → whatsapp_service.enviar_multiplos_arquivos()
      → Fallback: busca individual no banco
      → Registrar envio no MongoDB
  │
  ▼
RelatorioEnvio: sucessos, erros, duracao
```

---

## 3. Modelos de Dados

### 3.1 FolhaDePontoMongoDB (`folha_de_ponto_models.py`)

Modelo principal que representa uma folha de ponto no MongoDB.

**Relacionamentos:**
- `funcionario_id: ObjectId` → FuncionarioMongoDB (N:1)
- `empresa_id: ObjectId` → EmpresaMongoDB (N:1)

**Campos de controle:**
- `folha_data: FolhaDePontoData` — dados completos da folha
- `caminho_arquivo_gerado: str` — path absoluto do PDF gerado
- `caminho_arquivo_analisado: str` — path do PDF preenchido analisado pela IA
- `data_criacao, data_atualizacao: datetime`
- `status: StatusFolhaPonto` — enum: criada, preenchida, analise_pendente, analise_concluida, exportada, erro
- `versao: int` — controle de versao
- `historico_alteracoes: List[Dict]`

**Metodos auxiliares:**
- `adicionar_historico(acao, detalhes)` — registra alteracao
- `marcar_como_preenchida()` — altera status para PREENCHIDA
- `marcar_analise_concluida()` — altera status para ANALISE_CONCLUIDA
- `obter_chave_unica()` → (funcionario_id, empresa_id, mes_referencia)
- `to_mongo_insert()` → dict com dates convertidas para datetime
- `to_mongo_update()` → dict com operador $set

### 3.2 FolhaDePontoData (`folha_de_ponto_models.py`)

Contem os dados temporais da folha de ponto de um mes.

**Campos:**
- `mes_referencia: str` (YYYY-MM)
- `data_inicio, data_fim: date`
- `dias: List[DiaFolhaPonto]` — lista completa de dias (28-31)
- `nome_funcionario, cpf_funcionario, cargo_funcionario: Optional[str]` — dados copiados do funcionario para facilitar renderizacao sem join
- `lotacao_funcionario, contrato_funcionario, horario_funcionario: Optional[str]`
- `total_horas_mes: Optional[str]` — calculado pela IA
- `total_faltas, total_feriados, total_finais_semana: Optional[int]`
- `analise_ia: Optional[AnaliseIAResultado]`
- `preenchimento_concluido, analise_ia_concluida: bool`

### 3.3 DiaFolhaPonto (`folha_de_ponto_models.py`)

Representa um dia individual na folha de ponto.

**Campos:**
- `numero_dia: int` (1-31)
- `data: Optional[datetime]`
- `dia_semana: Optional[DiaSemana]` — Segunda a Domingo
- `hora_entrada, hora_intervalo_inicio, hora_intervalo_fim, hora_saida: Optional[str]` (HH:MM)
- `total_horas_trabalhadas: Optional[str]`
- `observacoes: Optional[str]`
- `tipo_dia: Optional[TipoDia]` — NORMAL, FERIADO, FALTA, ATESTADO, FOLGA, SABADO, DOMINGO, LICENCA, FERIAS, COMPENSACAO
- `preenchido_manualmente, analise_ia_processada: bool`

### 3.4 AnaliseIAResultado (`folha_de_ponto_models.py`)

Metadados da analise de IA para a folha.

**Campos:**
- `data_analise: datetime`
- `modelo_ia: str` (gemini-2.5-pro — a descricao do campo Pydantic diz "gemini-2.5-flash-lite", mas na pratica e setado para "gemini-2.5-pro" pelo processador)
- `prompt_utilizado, resposta_bruta: Optional[str]`
- `dias_analisados: int`
- `taxa_preenchimento: float` (0-100)
- `avisos, erros: Optional[List[str]]`
- `tempo_processamento_segundos: float`
- `tokens_utilizados: int`

### 3.5 Enums do Dominio

| Enum | Valores | Arquivo |
|------|---------|---------|
| `DiaSemana` | SEGUNDA, TERCA, QUARTA, QUINTA, SEXTA, SABADO, DOMINGO | folha_de_ponto_models |
| `TipoDia` | NORMAL, FERIADO, FALTA, ATESTADO, FOLGA, SABADO, DOMINGO, LICENCA, FERIAS, COMPENSACAO | folha_de_ponto_models |
| `StatusFolhaPonto` | CRIADA, PREENCHIDA, ANALISE_PENDENTE, ANALISE_CONCLUIDA, EXPORTADA, ERRO | folha_de_ponto_models |
| `TipoEnvioEnum` | EMAIL, WHATSAPP_GRUPO, WHATSAPP_INDIVIDUAL | envio_folha_ponto_models |
| `StatusEnvioEnum` | PENDENTE, ENVIADO, ERRO, PARCIAL | envio_folha_ponto_models |
| `TipoTemplateEnum` | EMAIL, WHATSAPP_GRUPO, WHATSAPP_INDIVIDUAL, EMAIL_HOLERITE, WHATSAPP_GRUPO_HOLERITE, WHATSAPP_INDIVIDUAL_HOLERITE | template_mensagem_models |
| `StatusProcessamento` | PENDENTE, SUCESSO, ERRO, EXTRAIDO | processador_folha_ponto |

### 3.6 Modelos de Dominios Conectados

**FuncionarioMongoDB** (`funcionario_models.py`):
- `nome, pis, cpf` — identificacao
- `lotacao, contrato (TipoContrato)` — contratuais
- `empresas_ids: List[ObjectId]` — relacao N:N com empresas
- `contrato_empresa_id, horario_id, funcao_id, diretorio_id: ObjectId` — referencias 1:1
- `status: StatusFuncionario` (ATIVO, INATIVO, AFASTADO, DEMITIDO, TRANSFERIDO)
- `status_cadastro: StatusCadastro` (COMPLETO, INCOMPLETO, PENDENTE_REVISAO)

**EmpresaMongoDB** (`empresa_models.py`):
- `nome, cnpj, atividade, endereco, telefone, email`
- `whatsapp_device_id: str` — JID do dispositivo WhatsApp (multidevice v0.9.5)
- `status: StatusEmpresa` (ATIVA, INATIVA, SUSPENSA, EM_CONSTRUCAO)
- `nome_sigla, nome_simplificado` — para exibicao e busca

**ContratoMongoDB** (`contrato_models.py`):
- `nome` (ex: ADMINISTRATIVO, CENSIPAM, DSEI ALTO RIO NEGRO)
- `numero_contrato, numero_processo, orgao, localidade`
- `inicio_vigencia, fim_vigencia: date`

**HorarioMongoDB** (`horario_models.py`):
- `descricao` (ex: "Segunda a Sexta-feira: 07:00 as 17:00")
- `entrada1, saida1, entrada2, saida2, total_horas: time`
- `dias_trabalho_mes: int`

**FuncaoMongoDB** (`funcao_models.py`):
- `nome` (ex: ASSISTENTE ADMINISTRATIVO)
- `funcao_geral` (categoria: ADMINISTRATIVO, MOTORISTA, etc.)

**DiretorioMongoDB** (`diretorio_models.py`):
- `nome` (igual ao nome do contrato vinculado)
- `contrato_id: ObjectId` — relacao 1:1 com contrato
- `caminho_relativo: str` — subpasta customizada opcional

**FeriadoMongoDB** (`feriado_models.py`):
- `data: date`, `descricao: str`
- `tipo: TipoFeriado` (NACIONAL, ESTADUAL, MUNICIPAL, PONTO_FACULTATIVO)
- `recorrente: bool` — se repete todo ano
- `FERIADOS_NACIONAIS_FIXOS` — 8 feriados fixos pre-definidos

### 3.7 Modelos de Envio

**EnvioFolhaPontoMongoDB** (`envio_folha_ponto_models.py`):
- `tipo_envio: TipoEnvioEnum`
- `destinatarios: List[str]` — emails, JIDs, ou telefones
- `mes_referencia, ano_referencia: int`
- `local_contrato_polo: str`
- `diretorio_completo: str` — caminho dos PDFs
- `arquivos_enviados, arquivos_com_erro: List[str]`
- `template_usado, assunto_email, mensagem_enviada: Optional[str]`
- `status: StatusEnvioEnum`
- `tentativas, max_tentativas: int`
- `erro_detalhes: Optional[str]`
- `data_ultima_tentativa, data_envio_sucesso: Optional[datetime]`

**TemplateMensagemMongoDB** (`template_mensagem_models.py`):
- `nome, tipo: TipoTemplateEnum, descricao`
- `assunto: Optional[str]` — para email
- `corpo_mensagem: str` — com placeholders
- Placeholders suportados: `{nome}`, `{mes}`, `{ano}`, `{mes_extenso}`, `{local}`, `{empresa}`
- Metodo `renderizar(contexto)` → substitui placeholders

### 3.8 Modelos do Processador IA

**ExtratorFolhaPonto** (Pydantic, `processador_folha_ponto.py`):
- Schema usado como Structured Output do Gemini
- Campos: `empresa_nome, empresa_cnpj, funcionario_nome, funcionario_pis, funcionario_cpf`
- `periodo_inicio, periodo_fim, mes_ano`
- `dias: List[DiaExtraido]`
- `dias_com_dados, dias_em_branco, confianca_geral`
- `avisos, erros: Optional[List[str]]`

**ProcessarResultado** (Pydantic, `processador_folha_ponto.py`):
- Resultado completo de cada PDF processado
- `arquivo_origem, arquivo_hash, extracao_sucesso, extracao_resultado`
- `prompt_gemini, resposta_bruta_gemini, tokens_utilizados`
- `lookup_sucesso, funcionario_id, funcionario_nome_encontrado, funcionario_score_similaridade`
- `armazenamento_sucesso, folha_id`
- Metricas de tempo: `tempo_processamento_total_s, tempo_gemini_s, tempo_lookup_s, tempo_mongodb_s`
- `status: StatusProcessamento`
- `mensagens, avisos, erros: List[str]`

### 3.9 Classe de Problemas (`folha_de_ponto.py`)

**TipoProblema** (Enum): DUPLICATA_PULADA, ERRO_MONGODB, ERRO_EMPRESA, ERRO_FUNCIONARIO, ERRO_PDF

**ProblemaProcessamento** (dataclass): tipo, funcionario_nome, funcionario_id, mensagem, detalhes

---

## 4. Servicos

### 4.1 FolhaDePontoService (`folha_ponto_service.py`)

CRUD de folhas de ponto no MongoDB usando pool centralizado.

**Colecao:** `folha_de_ponto`

**Indices:** composto (funcionario_id, empresa_id, mes_referencia, lotacao, funcao) — NAO unico; validacao por codigo. Indices simples em mes_referencia, funcionario_id, empresa_id, data_criacao, status.

**Metodos:**
- `salvar_ou_atualizar(folha_mongodb, forcar_sobrescrita)` — upsert com deteccao de duplicidade analisando (funcionario_id + empresa_id + mes + lotacao + funcao). Retorna `Tuple[ResultadoSalvamento, Optional[Dict], Optional[Any]]`.
- `buscar_folha_existente(funcionario_id, empresa_id, mes_referencia)` — busca por chave composta
- `listar_por_funcionario(funcionario_id)` — folhas de um funcionario (ordenado por mes DESC)
- `buscar_por_periodo(data_inicio, data_fim)` — entre datas
- `buscar_por_empresa(empresa)` — por nome de empresa
- `buscar_por_status(status)` — por status
- `obter_estatisticas()` — contagem total, por status, por empresa
- `deletar_folha(funcionario_id, mes_referencia, lotacao, funcao)` — deleta especifica
- `listar_todos(skip, limit)` — paginacao

**ResultadoSalvamento (Enum):** SUCESSO_INSERIDO, SUCESSO_ATUALIZADO, SUCESSO_INALTERADO, DUPLICIDADE, ERRO, INDISPONIVEL

### 4.2 EnvioFolhaPontoService (`envio_folha_ponto_service.py`)

CRUD de registros de envio de folhas de ponto.

**Colecao:** `envios_folhas_de_ponto`

**Indices:** composto (ano_referencia, mes_referencia), simples (tipo_envio, status, tentativas, local_contrato_polo, criado_em, data_envio_sucesso), composto (status, tentativas) para retry.

**Metodos:**
- `registrar_envio(dados)` — valida com EnvioFolhaPontoMongoDB, insere
- `buscar_por_id`, `buscar_por_periodo`, `buscar_por_tipo`, `buscar_por_status`
- `buscar_pendentes_retry(max_tentativas)` — envios com erro e tentativas < max
- `incrementar_tentativa`, `marcar_enviado`, `marcar_erro`, `marcar_parcial`
- `contar_por_status`, `contar_por_tipo`, `obter_resumo_periodo`
- `listar_historico(limit, skip)` — paginacao

### 4.3 FuncionarioService (`funcionario_service.py` — 1765 linhas)

O maior arquivo do projeto. CRUD completo de funcionarios com:
- Busca por nome (exata e fuzzy), ObjectId, filtros
- Autocadastro de funcionarios incompletos (via processamento de PDF)
- Busca similar com limiar de similaridade (0.75)
- Cache hibrido (dicionario local + Redis + MongoDB)

### 4.4 EmpresaService (`empresa_service.py` — 1001 linhas)

CRUD de empresas, com suporte a autocadastro de empresas incompletas.
- `obter_ou_criar_incompleta(nome)` — usado pelo processador de PDF
- `buscar_por_nome_ou_simplificado(nome)` — busca flexivel

### 4.5 Servicos de Referencia

- **FeriadoService**: CRUD de feriados, importacao de `FERIADOS_NACIONAIS_FIXOS`, `obter_dataframe()` para processador de folha
- **FuncaoService**: CRUD de funcoes/cargos
- **HorarioService**: CRUD de horarios de trabalho
- **ContratoService**: CRUD de contratos
- **DiretorioService**: CRUD de diretorios, `obter_nome_diretorio(diretorio_id)`

### 4.6 Servicos de Envio

- **WhatsAppService** (`whatsapp_service.py` — 806 linhas): API REST para go-whatsapp-web-multidevice. `listar_dispositivos()`, `obter_id_dispositivo_por_jid()`, `enviar_arquivo()`, `enviar_texto()`, `enviar_multiplos_arquivos()` (com delay sequencial), `listar_grupos(device_id)`
- **GrupoWhatsAppService**: Cache de grupos WhatsApp no MongoDB. Busca por nome+device_id, sincronizacao com API
- **ZohoMailService** (`zoho_mail_service.py` — 915 linhas): OAuth2 completo, `enviar_email()` com anexos, HTML, CC/BCC
- **TemplateMensagemService**: CRUD de templates, `renderizar_por_tipo(tipo, contexto)`
- **PlanilhaContatosService**: Leitura de planilha Excel com colunas padrao, iteracao de contatos, validacao

### 4.7 Servicos de Infra

- **MongoDBConnectionPool** (`mongodb_connection.py` — 463 linhas): Singleton thread-safe com double-checked locking
- **CacheService** (`cache_service.py` — 429 linhas): Redis + fallback em memoria, TTL configuravel
- **GeminiService** (`analise_ai_service.py` — 647 linhas): Google Gemini 2.5 Pro, Structured Output, File API para >20MB
- **MistralService** (`analise_ai_service.py`): Mistral OCR (mistral-ocr-2505) + chat (mistral-small-2506)

> **Nota (Gap Arquitetural):** `EnvioFolhaPontoService` e `FeriadoService` criam suas proprias instancias de `MongoClient` em vez de usar o pool compartilhado `MongoDBConnectionPool`. Isso e uma inconsistencia com os demais servicos e pode causar vazamento de conexao. Os demais servicos (ContratoService, DiretorioService, FuncaoService, HorarioService) tambem tem esse problema.

---

## 5. Processadores / Orquestradores

### 5.1 ProcessadorFolhaPonto (`processadores/processador_folha_ponto.py` — 849 linhas)

Orquestrador do pipeline de analise IA de folhas de ponto.

**Pipeline de 4 estagios:**

```
ETAPA 1: Validacao
  _validar_arquivo(arquivo, resultado)
  → arquivo existe, e PDF, tamanho < 50MB

ETAPA 2: Extracao Gemini
  _extrair_gemini(arquivo, resultado)
  → Gemini 2.5 Pro + Structured Output (ExtratorFolhaPonto)
  → Até 3 tentativas com temperature escalonada: 0.2 → 0.4 → 0.6
  → Valida resposta: minimo 100 chars, contem "dias"
  → Salva prompt e resposta bruta no resultado

ETAPA 3: Lookup Funcionario
  _lookup_funcionario(resultado, arquivo_pdf)
  → Busca por nome_normalizado (unicodedata NFKD)
  → Se multiplos candidatos: usa o primeiro
  → Se nao encontrado: busca similar (buscar_similar, 0.75 threshold)
  → Se ainda nao: autocadastro via ConstrutorFuncionarioIncompleto
  → Registra avisos de sanitizacao

ETAPA 4: Armazenamento MongoDB
  _armazenar_mongodb(resultado)
  → Autocadastro de empresa via EmpresaService.obter_ou_criar_incompleta()
  → Converte DiaExtraido → DiaFolhaPonto (com calculo de horas)
  → Cria AnaliseIAResultado com metadados
  → Cria FolhaDePontoMongoDB com status ANALISE_CONCLUIDA
  → Insere com fallback para upsert em caso de duplicata
  → Atualiza empresas_ids do funcionario ($addToSet)
```

**Metricas coletadas por PDF:** tempo_gemini_s, tempo_lookup_s, tempo_mongodb_s, tempo_processamento_total_s, tokens_utilizados

### 5.2 EnvioFolhaPontoOrquestrador (`processadores/envio_folha_ponto_orquestrador.py` — 828 linhas)

Orquestrador do envio de folhas de ponto por multiplos canais.

**Estruturas de dados:**

`ResultadoEnvio` (dataclass): tipo, sucesso, destinatario, arquivos, mensagem, detalhes

`RelatorioEnvio` (dataclass): mes, ano, total_contatos, total_envios, enviados_sucesso, enviados_erro, enviados_parcial, por_tipo, erros, inicio, fim, duracao_segundos()

**Fluxo `executar(mes, ano, tipos_envio, contatos_ids, dry_run)`:**

```
1. Verificar servicos (Zoho, WhatsApp, MongoDB)
2. Carregar planilha de contatos
3. Filtrar por contatos_ids se especificado
4. Sincronizar grupos WhatsApp (multidevice)
5. PRE-processar grupos por empresa (cache em memoria)
   → _cache_grupos_por_empresa: {empresa_nome: {grupo_normalizado: jid}}
   → Reduz de N+1 queries para O(1) em memoria
6. Para cada contato:
   a. Email (se ativo): template → enviar → registrar
   b. WhatsApp Individual (se ativo): template → enviar_multiplos_arquivos → registrar
   c. WhatsApp Grupo (se ativo): buscar jid no cache → enviar → registrar
7. Gerar RelatorioEnvio
```

**Otimizacao de grupos:** O `_preprocessar_grupos_por_empresa()` extrai empresas unicas de todos os contatos, para cada uma busca o device_id da empresa, lista todos os grupos daquele dispositivo UMA VEZ, e monta um mapa `{nome_normalizado: jid}` em memoria. O envio usa esse cache em vez de fazer queries individuais.

---

## 6. CLI (Command Line Interface)

### 6.1 Subcomandos de `folha_de_ponto`

Todos os subcomandos sao registrados em `comandos/folha_de_ponto.py` e roteados por `handle_folha_de_ponto()`.

| Subcomando | Descricao | Argumentos |
|------------|-----------|------------|
| `criar` | Cria folhas de ponto (MongoDB → PDF) | `--data`, `--id_funcionario`, `--nome_funcionario`, `--lotacao`, `--contrato`, `--diretorio_destino` |
| `analise` | Analisa folha existente | `--arquivo` |
| `gerar_dataframe` | Exibe/exporta DataFrame | `--memoria`, `--diretorio_destino` |
| `mongodb` | Processa e salva em MongoDB | `--data`, `--id_funcionario`, `--nome_funcionario`, `--lotacao`, `--contrato`, `--diretorio_destino` |
| `processar_pdf` | Processa PDF(s) com IA | `--arquivo`, `--arquivos`, `--diretorio` |
| `criar_mongodb_id` | Cria por IDs do MongoDB | `--funcionario_id`, `--empresa_id`, `--data`, `--diretorio_destino` |
| `criar_mongodb_filtro` | Cria por filtros MongoDB | `--lotacao`, `--funcao`, `--contrato`, `--ativo`, `--data`, `--diretorio_destino` |
| `envio` | Abre menu interativo de envio | — |
| `envio-verificar` | Verifica servicos de envio | — |
| `envio-validar` | Valida planilha de contatos | — |
| `envio-sincronizar` | Sincroniza grupos WhatsApp | `--listar` |
| `envio-dispositivos` | Gerencia dispositivos WhatsApp | `--listar`, `--empresa`, `--status` |
| `envio-listar` | Lista contatos da planilha | — |
| `envio-executar` | Executa envio de folhas | `--mes/-m`, `--ano/-a`, `--dry-run/-d`, `--email/-e`, `--whatsapp/-w`, `--grupo/-g`, `--ids`, `--force/-f`, `--verbose/-v` |

### 6.2 Exemplos de Uso

```bash
# Gerar folha para funcionario especifico
uv run python automatizar.py folha_de_ponto criar_mongodb_id \
    --funcionario_id 65abc123def456789 \
    --empresa_id 65xyz789abc123456 \
    --data 2026-05-01

# Processar PDFs com IA
uv run python automatizar.py folha_de_ponto processar_pdf \
    --diretorio "/caminho/dos/pdfs"

# Enviar com dry-run
uv run python automatizar.py folha_de_ponto envio-executar \
    --mes 5 --ano 2026 --dry-run

# Envio completo forcar
uv run python automatizar.py folha_de_ponto envio-executar \
    --mes 5 --ano 2026 --force
```

---

## 7. Interface Interativa (TUI)

### 7.1 Menu Principal (`interface/interface_folha_de_ponto.py`)

```
OPERACOES COM FOLHA DE PONTO
├── Gerar Folha de Ponto (PDF + MongoDB)
│   └── Fluxo: selecionar filtro → data → processar funcionarios
│       → verifica folha existente → gera PDF ou sobrescreve
│
├── Processar PDFs Preenchidos com IA
│   └── Selecionar: arquivo unico / multiplos / diretorio
│       → processa → exibe resumo detalhado
│
└── Enviar Folhas de Ponto (E-mail/WhatsApp)
    └── Abre menu de envio (interface_envio_folha_ponto.py)
```

### 7.2 Menu de Envio (`interface/interface_envio_folha_ponto.py`)

```
SISTEMA DE ENVIO DE FOLHAS DE PONTO
├── Verificar Servicos
├── Validar Planilha de Contatos
├── Sincronizar Grupos WhatsApp
├── Gerenciar Dispositivos WhatsApp
│   ├── Listar dispositivos conectados
│   ├── Verificar status dos dispositivos
│   └── Mostrar dispositivo de uma empresa
├── Gerenciar Templates
├── Simulacao de Envio (Dry Run)
├── Executar Envio
│   └── Selecionar mes/ano → tipos de envio → confirmar
└── Historico de Envios
```

---

## 8. Integracoes Externas

### 8.1 Google Gemini 2.5 Pro
- **Uso:** Extracao de dados de folhas de ponto manuscritas
- **Modelo:** `gemini-2.5-pro` (premium, visao computacional)
- **Metodo:** `documento_estruturado()` com Structured Output (Pydantic schema)
- **Retry:** 3 tentativas com temperature 0.2 → 0.4 → 0.6
- **File API:** Para arquivos > 20MB
- **Chave:** `.env` → `GEMINI_API_KEY`

### 8.2 WhatsApp (go-whatsapp-web-multidevice)
- **API REST:** Docker na porta 3000
- **Autenticação (v8+/v9):** Basic Auth — `Authorization: Basic base64(user:pass)` via `WHATSAPP_BASIC_AUTH` (fallback: `WHATSAPP_API_KEY` com `:` vira Basic; token simples vira Bearer).
- **Multidevice:** Suporte a multiplos dispositivos (v0.9.5)
- **Roteamento:** Cada empresa tem seu `whatsapp_device_id` (JID)
- **Envio:** `enviar_multiplos_arquivos()` com delay de 1.5s entre arquivos
- **Grupos:** Cache em MongoDB com chave composta `(jid, device_id)`
- **Chave:** `.env` → `WHATSAPP_API_URL`

### 8.3 Zoho Mail (OAuth2)
- **Autenticacao:** Self Client OAuth2 com refresh token
- **Envio:** SMTP via API, suporte a anexos e HTML
- **Callback:** Servidor HTTP local para receber codigo de autorizacao
- **Chaves:** `.env` → `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`, etc.

### 8.4 MongoDB (Atlas)
- **Pool:** `MongoDBConnectionPool` — singleton thread-safe
- **Colecoes do dominio:** `folha_de_ponto`, `envios_folhas_de_ponto`, `funcionarios`, `empresas`, `contratos`, `horarios`, `funcoes`, `diretorios`, `feriados`, `templates_mensagens`, `grupos_whatsapp`
- **Chave:** `.env` → `MONGO_URI`, `MONGO_DATABASE_NAME`

### 8.5 Redis 7.2
- **Uso:** Cache hibrido (segundo nivel, apos cache local)
- **Fallback:** Memoria local quando Redis indisponivel
- **TTL:** 300s padrao
- **Chave:** `.env` → `REDIS_HOST`, `REDIS_PORT`, `REDIS_ENABLED`

---

## 9. Pipeline de IA

### 9.1 Structured Output com Pydantic

O Gemini e chamado com `documento_estruturado(documento, prompt, schema_pydantic=ExtratorFolhaPonto)`.

O schema `ExtratorFolhaPonto` define explicitamente:
- Informacoes do cabecalho (empresa, funcionario, periodo)
- Lista de `DiaExtraido` com horarios, observacoes, tipo de dia
- Contagem de qualidade (dias com dados, confianca)

### 9.2 Estrategia de Retry

```
Tentativa 1: temperature = 0.2 (baixa, precisa)
Tentativa 2: temperature = 0.4 (media, mais criativa)
Tentativa 3: temperature = 0.6 (alta, ultimo recurso)
```

Apos 3 falhas, o processamento e abortado com erro.

### 9.3 Conversao de Dados

`converter_string_para_tipo_dia(valor)` → mapeia strings do Gemini para o enum `TipoDia`. Suporta match parcial (ex: "FERIADO NACIONAL" → FERIADO). Retorna NORMAL como padrao para valores desconhecidos.

`calcular_total_horas(entrada, saida, inicio_intervalo, fim_intervalo)` → calcula HH:MM a partir de strings. Suporta jornada que cruza meia-noite.

### 9.4 Lookup de Funcionario

**Algoritmo de 4 passos:**

1. Busca por `nome_normalizado` exato no MongoDB
2. Se multiplos candidatos: usa o primeiro (log de aviso)
3. Se zero candidatos: `funcionario_service.buscar_similar(nome, lotacao, contrato, limiar=0.75)`
4. Se zero: autocadastro via `ConstrutorFuncionarioIncompleto.criar_do_pdf()`

O autocadastro cria registro com `status_cadastro = INCOMPLETO`, campos `lotacao`, `pis`, `cpf`, `horario_trabalho`, `data_admissao` como null, para revisao manual posterior.

---

## 10. Pipeline de Envio

### 10.1 Canais de Envio

**Email (Zoho Mail):**
- Template renderizado com placeholders
- Anexos: PDFs das folhas de ponto
- Multiplos destinatarios separados por `,` ou `;`
- Registro de envio no MongoDB (status, data, arquivos)

**WhatsApp Individual:**
- Envio para cada telefone do contato
- Template renderizado
- Roteamento por device_id da empresa
- Envio com delay para evitar rate limiting
- Consolidacao: todos os telefones precisam receber para status = sucesso

**WhatsApp Grupo:**
- Busca JID do grupo via cache em memoria (`_cache_grupos_por_empresa`)
- Fallback: busca individual no MongoDB se nao encontrado no cache
- Roteamento por device_id da empresa
- Envio com delay

### 10.2 Templates de Mensagem

Placeholders disponiveis:
- `{nome}` — nome do destinatario
- `{mes}` — numero do mes (01-12)
- `{ano}` — ano (ex: 2026)
- `{mes_extenso}` — nome do mes por extenso (Janeiro, Fevereiro...)
- `{local}` — Local/Contrato/Polo
- `{empresa}` — nome da empresa

Templates padrao criados automaticamente na primeira execucao (em `criar_templates_padrao()`):
- Email Formal Folha de Ponto
- WhatsApp Grupo Padrao
- WhatsApp Individual Personalizado

### 10.3 Estrutura de Diretorio de Saida

```
{DIRETORIO GERAL}/
└── {ANO}/
    └── {MES:02d}.{ANO}/
        └── {NOME_DIRETORIO}/
            ├── {Nome_Funcionario} - {SIGLA_EMPRESA}.pdf
            └── ...
```

O nome do arquivo PDF usa sigla da empresa se funcionario tiver multiplas empresas vinculadas. A extensao `.html` tambem e suportada (alternativa ao PDF).

---

## 11. Testes

### 11.1 Testes Existentes

| Arquivo | Classe/Assunto | Quantidade Testes | Cobertura |
|---------|---------------|-------------------|-----------|
| `tests/unit/processadores/test_processador_folha_ponto.py` | TestProcessadorInit | 5 | ~50% target |
| | TestValidacaoArquivo | 5 | |
| | TestExtracaoGemini | 6 | |
| | TestLookupFuncionario | 7 | |
| | TestLookupEmpresa | 3 | |
| | TestArmazenamentoMongoDB | 7 | |
| | TestPipelineCompleto | 6 | |
| | TestConversoesModelos | 12 | |
| | TestCalcularTotalHoras | 7 | |
| | TestExtratorFolhaPonto | 3 | |
| | TestProcessarResultado | 4 | |
| **Total** | | **~65 testes** | |
| `tests/unit/services/test_folha_ponto_service.py` | TestFolhaDePontoServiceInit | 2 | ~50% target |
| | TestBuscarFolhaExistente | 3 | |
| | TestSalvarOuAtualizar | 6 | |
| | TestListarPorFuncionario | 3 | |
| | TestBuscarPorPeriodo | 3 | |
| | TestBuscarPorEmpresa | 3 | |
| | TestBuscarPorStatus | 3 | |
| | TestObterEstatisticas | 3 | |
| | TestDeletarFolha | 3 | |
| | TestListarTodos | 4 | |
| | TestMongoDBIndisponivel | 2 | |
| **Total** | | **~35 testes** | |

### 11.2 Gaps de Teste

- **Interface TUI** (`interface_folha_de_ponto.py`, `interface_envio_folha_ponto.py`): 0 testes
- **CLI/Comandos** (`comandos/folha_de_ponto.py`): 0 testes
- **EnvioFolhaPontoService**: 0 testes
- **EnvioFolhaPontoOrquestrador**: 0 testes
- **PlanilhaContatosService**: 0 testes
- **TemplateMensagemService**: 0 testes
- **WhatsAppService**: apenas `test_whatsapp_multidevice.py` integrado
- **ZohoMailService**: 0 testes

### 11.3 Fixtures Compartilhadas

Em `tests/conftest.py` e `tests/fixtures/`:

- `temp_pdf_file` — PDF minimo temporario
- `folha_ponto_dict` — documento completo de folha
- `funcionario_dict`, `empresa_dict` — documentos base
- `sample_object_id` — ObjectId fixo para testes
- `mock_collection` — colecao MongoDB mockada
- `mock_mongo_client` — cliente MongoDB mockado

---

## 12. Configuracao

### 12.1 Variaveis de Ambiente (`.env`)

```env
# MongoDB
MONGO_URI=mongodb+srv://...
MONGO_DATABASE_NAME=MS_Automatizar

# IA
GEMINI_API_KEY=...
KEY_API_MISTRAL=...

# WhatsApp
WHATSAPP_API_URL=http://localhost:3000

# Redis (opcional)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_ENABLED=true

# Zoho Mail
ZOHO_CLIENT_ID=...
ZOHO_CLIENT_SECRET=...
ZOHO_REFRESH_TOKEN=...
ZOHO_ACCESS_TOKEN=...
ZOHO_ACCOUNT_ID=...
ZOHO_EMAIL_FROM=...

# Config
MODO_OPERACAO=mongodb
LOG_LEVEL=INFO
ENVIO_MAX_TENTATIVAS=3
ENVIO_RETRY_DELAY_SECONDS=5
```

### 12.2 Dependencias do Dominio

| Dependencia | Uso | Obrigatoria? |
|------------|-----|-------------|
| MongoDB | Persistencia de dados | Sim (para funcionalidades completas) |
| WeasyPrint | HTML → PDF | Sim (para geracao de PDF) |
| Jinja2 | Template HTML | Sim |
| Google Gemini API | Extracao IA de PDFs manuais | Sim (para pipeline IA) |
| Docker (go-whatsapp-web-multidevice) | Envio WhatsApp | Sim (para envio) |
| Zoho Mail API | Envio Email | Opcional |
| Redis | Cache | Opcional (fallback em memoria) |
| Mistral AI | OCR | Opcional |
| Pandas | Planilha de contatos | Sim (para envio) |

### 12.3 Docker

```bash
# WhatsApp API
docker compose -f docker-compose.whatsapp.yml up -d

# Redis
docker compose -f docker-compose.redis.yml up -d
```

---

## 13. Glossario

| Termo | Significado |
|-------|------------|
| Folha de Ponto | Documento mensal que registra a frequencia do funcionario (entradas, saidas, intervalos, faltas, feriados) |
| Holerite | Recibo de pagamento (contra-cheque) — dominio separado |
| Processador IA | Pipeline que le PDF manuscrito com Gemini e extrai dados estruturados |
| Structured Output | Recurso do Gemini que retorna JSON validado contra um schema Pydantic |
| Lookup | Busca de funcionario no MongoDB por nome (exata + fuzzy + autocadastro) |
| Autocadastro | Criacao automatica de registro incompleto quando funcionario nao encontrado |
| Device ID | JID do dispositivo WhatsApp (ex: 5569XXXX@s.whatsapp.net) |
| Dry Run | Modo de simulacao que nao enga mensagens de verdade |
| Upsert | Operacao MongoDB que insere ou atualiza (insert + update) |
| Cache Pre-processado | Mapa de grupos WhatsApp carregado em memoria antes do loop de envio |
| Multidevice | Suporte a multiplos dispositivos WhatsApp, um por empresa |
| Template | Mensagem personalizavel com placeholders para cada tipo de envio |
| MESES_EXTENSO | Mapa de numero do mes para nome em portugues (1 → "Janeiro", etc.) |
| Feriados Nacionais Fixos | 8 feriados brasileiros fixos: Confraternizacao Universal (1/1), Tiradentes (21/4), Dia do Trabalho (1/5), Independencia (7/9), Aparecida (12/10), Finados (2/11), Proclamacao (15/11), Natal (25/12) |
