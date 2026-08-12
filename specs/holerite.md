# SPEC: Holerite (Payslip)

## 1. Visao Geral

O dominio Holerite automatiza o processamento e envio de recibos de pagamento (holerites) em PDF para funcionarios da empresa Solucoes Dinamicas.

Duas grandes responsabilidades:

1. **Processamento de PDFs**: Renomeacao automatica de arquivos PDF por nome do funcionario (via OCR Mistral ou IA Gemini), extracao completa de dados estruturados com Gemini 2.5 Pro (vencimentos, descontos, bases de calculo) e armazenamento em MongoDB com vinculacao a funcionarios e empresas.

2. **Envio automatizado**: Distribuicao dos holerites processados via Email (Zoho Mail OAuth2) e WhatsApp (individual e grupos, com suporte a multiplos dispositivos). Dois modos: via planilha Excel de contatos ou via dados diretamente do MongoDB.

O dominio tambem inclui um sistema de cache OCR baseado em hash SHA256 no MongoDB para evitar reprocessamento de imagens iguais, com suporte a estatisticas e limpeza de dados antigos.

---

## 2. Arquitetura

```
┌──────────────────────────────────────────────────────────────────┐
│                     CAMADA DE APRESENTACAO                       │
│                                                                  │
│  CLI (argparse)              TUI (questionary + rich)           │
│  src/comandos/holerite.py    src/interface/interface_holerite.py│
│                              src/interface/interface_envio_holerite.py│
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                   CAMADA DE ORQUESTRACAO                         │
│                                                                  │
│  HoleriteProcessador (extracao)   EnvioHoleriteOrquestrador     │
│  src/processadores/               src/processadores/             │
│  holerite_processador.py          envio_holerite_orquestrador.py│
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                    CAMADA DE SERVICOS                            │
│                                                                  │
│  HoleriteService    CacheOCRMongoDB   FuncionarioService         │
│  EmpresaService     ContatoFuncionarioService                    │
│  GeminiService      MistralService    WhatsAppService            │
│  ZohoMailService    PlanilhaHoleritesService                     │
│  TemplateMensagemService  GrupoWhatsAppService                   │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                    CAMADA DE DADOS                               │
│                                                                  │
│  MongoDB: holerites, contatos_funcionarios, cache_ocr,           │
│           empresas, funcionarios, envios_holerites,              │
│           templates_mensagens, grupos_whatsapp                    │
└──────────────────────────────────────────────────────────────────┘
```

### Fluxo de Renomeacao de Arquivos (src/holerite.py)

```
PDF Original ──► PdfProcessorService.extrair_cabecalho()
                    │
                    ▼
              CacheOCRMongoDB.obter_ocr() ←── hash SHA256
                    │
              ┌─────┴─────┐
              │ Cache HIT │ Cache MISS
              └─────┬─────┘
                    │         │
                    │         ▼
                    │    NomeExtractorOCR.imagem() (Mistral)
                    │         │
                    │    ┌────┴─────┐
                    │    │  Falha   │ OK
                    │    └────┬─────┘
                    │         │    │
                    │         ▼    ▼
                    │    NomeExtractorIA.imagem() (Gemini Flash Lite)
                    │         │
                    │         ▼
                    │    CacheOCRMongoDB.salvar_ocr()
                    │
                    ▼
              ArquivoProcessor.processar_arquivo()
                    │
                    ▼
              PDF renomeado: "Recibo de Pagamento - {Nome}.pdf"
```

### Fluxo de Extracao IA (HoleriteProcessador)

```
PDF "Recibo de Pagamento..." ──► calcular_hash_arquivo()
                                    │
                                    ▼
                              HoleriteService.buscar_por_hash()
                                    │
                              ┌─────┴─────┐
                              │ Existe?   │ Sim → retorna existente (dedup)
                              └─────┬─────┘
                                    │ Nao
                                    ▼
                              GeminiService.documento_estruturado()
                              (HoleriteExtracaoSchema, ate 2 tentativas)
                                    │
                                    ▼
                              HoleriteExtracaoSchema.model_validate_json()
                                    │
                                    ├──► FuncionarioService.criar_ou_buscar_por_documento()
                                    │       (busca por CPF/nome, autocadastro se necessario)
                                    │
                                    ├──► EmpresaService.buscar_por_nome_ou_simplificado()
                                    │       (vincula empresa pela razao social)
                                    │
                                    ├──► HoleriteMongoDB.from_extracao()
                                    │       (converte schema extraido para modelo MongoDB)
                                    │
                                    ├──► HoleriteService.criar_holerite()
                                    │       (insere no MongoDB)
                                    │
                                    └──► ContatoFuncionarioService.criar_ou_atualizar()
                                            (cria/atualiza contatos do funcionario)
```

### Fluxo de Envio (EnvioHoleriteOrquestrador)

```
MODO PLANILHA:
  Planilha Excel ──► PlanilhaHoleritesService.carregar()
                        ├──► iterar_contatos(mes, ano)
                        │       ├── Email → ZohoMailService
                        │       ├── WhatsApp Individual → WhatsAppService
                        │       └── WhatsApp Grupo → GrupoWhatsAppService
                        └──► RelatorioEnvioHolerite

MODO MONGODB:
  HoleriteService.listar_pendentes_envio(competencia)
    ├──► ContatoFuncionarioService.obter_contatos_batch() (1 query otimizada)
    ├──► Para cada holerite:
    │       ├── Email → ZohoMailService
    │       └── WhatsApp → WhatsAppService
    ├──► HoleriteService.registrar_envio() (em cada envio)
    └──► RelatorioEnvioHolerite
```

---

## 3. Modelos de Dados

### 3.1 HoleriteExtracaoSchema (schema para Gemini)

```python
class HoleriteExtracaoSchema(BaseModel):
    # EMPRESA (dados brutos do documento)
    empresa_razao_social: str              # "SOLUCOES DINAMICAS SERVICOS LTDA"
    empresa_cnpj: str                      # "00.000.000/0000-00"
    empresa_codigo_cc: Optional[str]       # Centro de Custo
    
    # FUNCIONARIO (dados brutos do documento)
    funcionario_codigo: Optional[int]
    funcionario_nome: str                  # Nome completo
    funcionario_cpf: Optional[str]
    funcionario_cbo: Optional[str]         # Codigo CBO
    funcionario_departamento: Optional[int]
    funcionario_filial: Optional[int]
    funcionario_funcao: Optional[str]
    funcionario_data_admissao: Optional[str]  # DD/MM/AAAA
    
    # REFERENCIA DO PERIODO
    tipo_folha: str                        # "Folha Mensal", "Horista", etc.
    mes_referencia_texto: str              # "Dezembro de 2025"
    mes_referencia: int                    # 1-14 (13=13o 1a, 14=13o 2a)
    ano_referencia: int                    # >= 2000
    
    # VENCIMENTOS E DESCONTOS
    vencimentos: List[ItemHoleriteExtracao]  # Lista de proventos
    total_vencimentos: float
    descontos: List[ItemHoleriteExtracao]    # Lista de descontos
    total_descontos: float
    valor_liquido: float
    
    # BASES DE CALCULO
    salario_base: Optional[float]
    sal_contr_inss: Optional[float]
    base_calc_fgts: Optional[float]
    fgts_do_mes: Optional[float]
    base_calc_irrf: Optional[float]
    faixa_irrf: Optional[float]

    Config:
        extra = "forbid"  # Nao permite campos extras do Gemini
```

### 3.2 ItemHoleriteExtracao

```python
class ItemHoleriteExtracao(BaseModel):
    codigo: Optional[int]         # Codigo do evento (ex: 998, 210)
    descricao: str                # "I.N.S.S.", "PLANO DE SAUDE"
    referencia: Optional[str]     # "227:20", "100,36"
    valor: Optional[float]
```

### 3.3 HoleriteMongoDB (modelo de persistencia)

```python
class HoleriteMongoDB(BaseModel):
    # REFERENCIAS (ObjectId)
    empresa_id: ObjectId                     # Obrigatorio
    funcionario_id: Optional[ObjectId]       # Opcional (None se nao vinculado)
    
    # DADOS DO FUNCIONARIO NO DOCUMENTO (auditoria)
    funcionario_documento: Dict[str, Any]    # Dados brutos do PDF
    
    # PERIODO
    tipo_folha: str
    mes_referencia: int                      # 1-14
    ano_referencia: int                      # >= 2000
    
    # VALORES
    vencimentos: List[ItemHolerite]
    total_vencimentos: float
    descontos: List[ItemHolerite]
    total_descontos: float
    valor_liquido: float
    bases_calculo: Optional[BasesCalculo]
    
    # ARQUIVO
    arquivo: ArquivoHolerite
    
    # PROCESSAMENTO
    processamento: ProcessamentoHolerite
    
    # STATUS
    status: StatusHoleriteEnum               # processado, pendente, etc.
    
    # TIMESTAMPS
    criado_em: datetime
    atualizado_em: datetime
    versao: int
    historico_alteracoes: List[Dict[str, Any]]
```

### 3.4 EnvioHoleriteMongoDB

```python
class EnvioHoleriteMongoDB(BaseModel):
    holerite_id: ObjectId
    funcionario_id: Optional[ObjectId]
    tipo_envio: str                    # "email", "whatsapp_individual", "whatsapp_grupo"
    destinatarios: List[str]
    sucesso: bool
    mensagem: Optional[str]
    enviado_em: datetime
```

### 3.5 Modelos Auxiliares

| Modelo | Campos principais |
|--------|------------------|
| `ItemHolerite` | codigo, descricao, referencia, valor |
| `BasesCalculo` | salario_base, sal_contr_inss, base_calc_fgts, fgts_do_mes, base_calc_irrf, faixa_irrf |
| `ArquivoHolerite` | caminho_completo, nome_arquivo, hash_sha256, tamanho_bytes, verificado_em |
| `ProcessamentoHolerite` | processado_em, modelo_ia, tempo_processamento_ms, confianca |

### 3.6 Enums

| Enum | Valores |
|------|---------|
| `TipoFolhaEnum` | MENSAL, HORISTA, MENSALISTA, DECIMO_TERCEIRO_1, DECIMO_TERCEIRO_2, FERIAS, RESCISAO, ADIANTAMENTO |
| `StatusHoleriteEnum` | PROCESSADO, PENDENTE, PENDENTE_REVISAO, ENVIADO, ERRO |
| `TipoContato` | TELEFONE, CELULAR, WHATSAPP, EMAIL_PESSOAL, EMAIL_CORPORATIVO |
| `OrigemContato` | PLANILHA_EXCEL, HOLERITE, CADASTRO_MANUAL, API |

### 3.7 Modelos de Contato (usados na criacao via holerite)

```python
def criar_contato_de_holerite(
    funcionario_id: ObjectId,
    funcionario_documento: str,
    funcionario_nome: str,
    telefone: str = None,
    email: str = None
) -> List[ContatoFuncionarioMongoDB]:
    # Cria ate 2 contatos (telefone com whatsapp=True, email pessoal)
    # Origem: OrigemContato.HOLERITE
    # Preferencial: True
```

### 3.8 Relacionamentos entre Entidades

```
HoleriteMongoDB
  ├── empresa_id: ObjectId ──► EmpresaMongoDB (N:1)
  ├── funcionario_id: ObjectId ──► FuncionarioMongoDB (N:1, opcional)
  └── arquivo.hash_sha256 ──► (indice unico para dedup)

EnvioHoleriteMongoDB
  ├── holerite_id: ObjectId ──► HoleriteMongoDB (1:N)
  └── funcionario_id: ObjectId ──► FuncionarioMongoDB (1:1, opcional)

ContatoFuncionarioMongoDB
  └── funcionario_id: ObjectId ──► FuncionarioMongoDB (1:N)

FuncionarioMongoDB
  ├── empresas_ids: List[ObjectId] ──► EmpresaMongoDB (N:N)
  └── contrato_empresa_id: ObjectId ──► ContratoMongoDB (1:1)
```

---

## 4. Servicos

### 4.1 HoleriteService (686 linhas)

Gerencia holerites em MongoDB via pool centralizado (MongoDBConnectionPool).

**Metodos:**

| Metodo | Descricao |
|--------|-----------|
| `criar_holerite(holerite)` | Insere holerite, detecta duplicatas por hash SHA256 |
| `buscar_por_id(holerite_id)` | Busca por ObjectId |
| `buscar_por_hash(hash_sha256)` | Busca por hash SHA256 (dedup) |
| `buscar_por_funcionario(funcionario_id, competencia)` | Holerites de um funcionario |
| `buscar_por_documento(documento, competencia)` | Busca por CPF do funcionario |
| `listar_todos(limite, skip, **filtros)` | Lista com filtros (competencia, nome, status, empresa_id) |
| `contar_total(**filtros)` | Contagem com filtros |
| `buscar_por_competencia(competencia, empresa_id, status)` | Busca por mes/ano |
| `atualizar_status(holerite_id, novo_status)` | Atualiza status do holerite |
| `registrar_envio(holerite_id, funcionario_id, canal, destino, sucesso)` | Registra tentativa de envio |
| `listar_envios_holerite(holerite_id)` | Lista envios de um holerite |
| `listar_pendentes_envio(empresa_id, competencia, limite)` | Holerites pendentes (status IN pendente, processado) |
| `contar_por_status(competencia)` | Agregacao por status |
| `existe_holerite(funcionario_id, competencia, tipo_folha)` | Verifica existencia |
| `calcular_hash_arquivo(caminho_arquivo)` | Calcula SHA256 do arquivo |

**Indices MongoDB:**
- `idx_holerite_unico`: (funcionario_id, competencia, tipo_folha) unique
- `idx_arquivo_hash`: (arquivo.hash_sha256) unique, sparse
- `idx_funcionario_doc`, `idx_empresa`, `idx_competencia`, `idx_status`, `idx_criado_em`
- `idx_holerite` (envios), `idx_funcionario` (envios), `idx_enviado_em` (envios)

**Singleton global:** `holerite_service`

### 4.2 CacheOCRMongoDB (414 linhas)

Cache de OCR com hash SHA256, armazenado em MongoDB (colecao `cache_ocr`).

**Metodos:**

| Metodo | Descricao |
|--------|-----------|
| `obter_ocr(imagem_path)` | Busca OCR no cache por hash; retorna texto ou None |
| `salvar_ocr(imagem_path, resultado_ocr)` | Salva OCR com upsert por hash |
| `obter_info_cache(imagem_path)` | Informacoes completas do documento em cache |
| `listar_cache(limite)` | Ultimos documentos adicionados |
| `limpar_cache_antigo(dias)` | Remove documentos mais antigos que N dias |
| `limpar_tudo()` | Remove todos os documentos |
| `obter_estatisticas()` | Total documentos, tamanho, arquivos unicos |
| `desconectar()` | No-op (pool centralizado gerencia) |

**Re-exports (compatibilidade legada):**
- `FolhaDePontoService`, `ResultadoSalvamento`, `folha_de_ponto_service`
- `FuncionarioService`, `funcionario_service`
- `EmpresaService`, `empresa_service`

**Singleton global:** `cache_ocr`

### 4.3 GeminiService (647+ linhas em analise_ai_service.py)

Classe `GeminiService(ServiceBaseGemini)` com modelo padrao `gemini-2.5-pro`.

**Metodos usados pelo dominio Holerite:**

| Metodo | Uso no Holerite |
|--------|-----------------|
| `documento_estruturado(documento, prompt, schema_pydantic)` | Extracao de holerites com `HoleriteExtracaoSchema` (ate 20MB inline, >20MB File API) |
| `imagem(imagem, prompt)` | Extracao de nome do cabecalho (usado em NomeExtractorIA) |

**Caracteristicas:**
- Structured Output com Pydantic V2 (`extra = "forbid"`)
- Schema cleaning: resolve `$defs`, remove campos nao suportados pelo Gemini
- File API automatica para documentos >20MB (upload temporario, cleanup apos 48h)

### 4.4 MistralService (647+ linhas em analise_ai_service.py)

**Metodos usados pelo dominio Holerite:**

| Metodo | Uso no Holerite |
|--------|-----------------|
| `imagem(imagem, prompt)` | OCR de cabecalho (usado em NomeExtractorOCR) |

Modelo OCR: `mistral-ocr-2512`, modelo chat: `mistral-small-2506`.

### 4.5 ContatoFuncionarioService (799 linhas)

Gerencia contatos de funcionarios. Usado para criar/atualizar contatos apos extracao de holerite.

**Metodos relevantes:**

| Metodo | Descricao |
|--------|-----------|
| `criar_contato(contato)` | Insere novo contato |
| `criar_ou_atualizar(contato)` | Upsert por (funcionario_id, tipo, valor_normalizado) |
| `obter_contatos_batch(funcionario_ids)` | **Otimizacao**: 1 aggregation query para N funcionarios; retorna Dict[funcionario_id, {email, whatsapp}] |

**Indices MongoDB:** indices unicos e compostos para busca rapida.

### 4.6 PlanilhaHoleritesService (491 linhas)

Le planilha Excel de contatos de holerites.

**Colunas esperadas:** ID, NOME COMPLETO, EMAIL, TELEFONE, GRUPO WHATSAPP, ENVIAR EMAIL, ENVIAR WHATSAPP, ENVIAR GRUPO WHATSAPP, EMPRESA, MES REFERENCIA, ANO REFERENCIA, DIRETORIO GERAL, DIRETORIO ESPECIFICO, LOCAL - CONTRATO - POLO.

**Metodos:**

| Metodo | Descricao |
|--------|-----------|
| `carregar(sheet_name)` | Carrega Excel em DataFrame pandas |
| `iterar_contatos(mes, ano)` | Generator que processa cada linha, monta diretorios, lista PDFs |
| `montar_diretorio_completo(geral, especifico, mes, ano)` | Monta caminho padrao `{geral}/{ano}/{mes.ano}/{especifico}` |
| `listar_arquivos_pdf(diretorio, prefixo)` | Lista PDFs recursivamente filtrando por prefixo "Recibo de Pagamento" |
| `validar_planilha()` | Valida colunas obrigatorias |
| `contar_envios_pendentes()` | Contagem por canal |
| `listar_resumo()` | Resumo para exibicao |

**Enum interno:** `TipoEnvioHolerite` (PLANILHA, MONGODB)

**Singleton global:** `planilha_holerites_service`

### 4.7 Demais Servicos

| Servico | Uso no Holerite |
|---------|-----------------|
| `WhatsAppService` | Envio de holerites para individuos e grupos (multidevice) |
| `ZohoMailService` | Envio de holerites por email com OAuth2 |
| `FuncionarioService` | Busca fuzzy e autocadastro de funcionarios na extracao |
| `EmpresaService` | Busca empresa por nome/simplificado para vinculacao |
| `TemplateMensagemService` | Renderizacao de templates EMAIL_HOLERITE, WHATSAPP_INDIVIDUAL_HOLERITE, WHATSAPP_GRUPO_HOLERITE |
| `GrupoWhatsAppService` | Cache e mapeamento de grupos por device_id |

---

## 5. Processadores / Orquestradores

### 5.1 HoleriteProcessador (530 linhas, src/processadores/holerite_processador.py)

Processa PDFs de holerites com pipeline de extracao IA.

**Estrutura interna:**

```python
@dataclass
class ResultadoProcessamentoHolerite:
    arquivo: str
    sucesso: bool = False
    erro: Optional[str] = None
    extracao: Optional[HoleriteExtracaoSchema] = None
    extracao_json: Optional[str] = None
    holerite_id: Optional[str] = None
    funcionario_id: Optional[str] = None
    empresa_id: Optional[str] = None
    funcionario_criado: bool = False
    tempo_extracao_s: float = 0.0
    tempo_total_s: float = 0.0
    mensagens: List[str] = field(default_factory=list)
```

**Metodos principais:**

| Metodo | Descricao |
|--------|-----------|
| `processar_arquivo(arquivo, empresa_id, temperatura, max_tentativas)` | Processa um PDF: validacao, extracao Gemini, vinculacao funcionario/empresa, salvamento, contatos |
| `processar_diretorio(diretorio, empresa_id, recursivo, temperatura)` | Processa todos PDFs "Recibo de Pagamento" de um diretorio |
| `calcular_hash_arquivo(caminho)` | SHA256 do arquivo |
| `obter_estatisticas()` | Contadores de processamento |

**Pipeline de `processar_arquivo()`:**

1. **Validacao inicial**: processador disponivel, arquivo existe, e PDF
2. **Dedup por hash**: `calcular_hash_arquivo()` + `holerite_service.buscar_por_hash()` → se existe, retorna imediatamente
3. **Extracao Gemini**: `gemini.documento_estruturado(arquivo, PROMPT_EXTRACAO, HoleriteExtracaoSchema)` com ate 2 tentativas e temperatura 0.1
4. **Vinculacao funcionario**: `funcionario_service.criar_ou_buscar_por_documento(cpf, nome)` → autocadastro se `status_cadastro == 'incompleto'`
5. **Vinculacao empresa**: Se `empresa_id` fornecido usa direto; senao `empresa_service.buscar_por_nome_ou_simplificado(extracao.empresa_razao_social)`
6. **Criacao HoleriteMongoDB**: `HoleriteMongoDB.from_extracao()` + `holerite_service.criar_holerite()`
7. **Criacao contatos**: `criar_contato_de_holerite()` + `contato_service.criar_ou_atualizar()`

**Prompt de extracao** (`PROMPT_EXTRACAO`):
- Extrai nome completo, CPF sem formatacao, competencia MM/AAAA
- Lista todos proventos e descontos
- Extrai bases de calculo de INSS, IRRF e FGTS
- Valores monetarios como numeros (ex: 1234.56)
- Datas no formato DD/MM/AAAA

**Singleton global:** `holerite_processador`

### 5.2 EnvioHoleriteOrquestrador (865 linhas, src/processadores/envio_holerite_orquestrador.py)

Coordena o envio de holerites por email e WhatsApp.

**Data classes:**

```python
@dataclass
class ResultadoEnvioHolerite:
    tipo: str                        # email, whatsapp_individual, whatsapp_grupo
    sucesso: bool
    destinatario: str
    holerite_id: Optional[str] = None
    funcionario_id: Optional[str] = None
    arquivo: str = ""
    mensagem: str = ""
    detalhes: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RelatorioEnvioHolerite:
    competencia: str
    modo_envio: str                  # planilha ou mongodb
    total_holerites: int = 0
    total_envios: int = 0
    enviados_sucesso: int = 0
    enviados_erro: int = 0
    por_tipo: Dict[str, Dict[str, int]] = field(default_factory=dict)
    erros: List[Dict[str, Any]] = field(default_factory=list)
    inicio: datetime = ...
    fim: Optional[datetime] = None
```

**Metodos principais:**

| Metodo | Descricao |
|--------|-----------|
| `verificar_servicos()` | Verifica disponibilidade de todos os servicos (planilha, holerite, contato, templates, whatsapp, zoho) |
| `enviar_via_planilha(mes, ano, apenas_simular)` | Le planilha de holerites, itera contatos, envia email + whatsapp individual + grupo |
| `enviar_via_mongodb(competencia, empresa_id, canais, apenas_simular)` | Busca holerites pendentes, carrega contatos em batch (1 query), envia |
| `obter_estatisticas_competencia(competencia)` | Agregacao por status para uma competencia |
| `definir_callback_progresso(callback)` | Callback para TUI (mensagem, atual, total) |

**Modo MongoDB - Otimizacao batch:**
- Carrega contatos de todos funcionarios em UMA unica query via `contato_funcionario_service.obter_contatos_batch()`
- Acesso O(1) por funcionario: `contatos_map.get(funcionario_id, {}).get("email")`

**Canais de envio:**
- `TipoEnvioEnum.EMAIL` → ZohoMailService com template `EMAIL_HOLERITE`
- `TipoEnvioEnum.WHATSAPP_INDIVIDUAL` → WhatsAppService com template `WHATSAPP_INDIVIDUAL_HOLERITE`
- `TipoEnvioEnum.WHATSAPP_GRUPO` → GrupoWhatsAppService com template `WHATSAPP_GRUPO_HOLERITE`

**Templates padrao (fallback):**
- Email: assunto "Recibo de Pagamento - {mes}/{ano}", corpo com saudacao padrao
- WhatsApp individual: "Ola {nome}! Segue seu recibo de pagamento de {mes_extenso}/{ano}."
- WhatsApp grupo: "Bom dia! Seguem os recibos de pagamento referente ao mes de {mes_extenso}/{ano}."

**Singleton global:** `envio_holerite_orquestrador`

### 5.3 Classes Core (src/holerite.py, 558 linhas)

| Classe | Responsabilidade |
|--------|-----------------|
| `Holerite` | Classe principal para renomeacao de arquivos em lote |
| `PdfProcessorService` | Extrai cabecalho do PDF (recorte + conversao para imagem) |
| `DirectoryProcessor` | Processa entrada de diretorio (string, Path, lista, None) |
| `DirectoryFilter` | Filtra diretorios por substring no nome com glob otimizado |
| `NomeExtractorOCR` | Extrai nome via Mistral OCR com cache |
| `NomeExtractorIA` | Extrai nome via Gemini Flash Lite com cache |
| `NomeExtractorComposite` | Tenta OCR primeiro, fallback para IA |
| `ArquivoProcessor` | Orquestra extracao de cabecalho + nome + renomeacao |

**Interfaces (ABC):** `IArquivoProcessor`, `IExtractorNome`, `IAnaliseHolerite`, `IDirectoryFilter`, `IPdfProcessor`

**Metodo principal `Holerite.renomear_arquivos()`:**
- Parametros: `max_workers=5`, `mes_ano`, `usar_multiprocessing=True`
- Fluxo: `_preparar_diretorios()` → `_coletar_arquivos()` → `_processar_arquivos_multiprocessing()` ou `_processar_arquivos_threading()`
- Filtra arquivos por nome exato `"Recibo de Pagamento.pdf"`
- Exibe estatisticas do cache OCR ao final

**Funcao standalone:** `processar_arquivo_standalone()` (necessaria para multiprocessing serializavel)

---

## 6. CLI (Command Line Interface)

**Arquivo:** `src/comandos/holerite.py` (300 linhas)

### 6.1 Subcomandos

| Comando | Descricao | Argumentos |
|---------|-----------|------------|
|| `renomear_arquivos` | Renomeia PDFs por nome do funcionario | `--diretorio`, `--mês_ano` (MM.AAAA) |
| `processar_pdfs` | Extrai dados com Gemini e salva no MongoDB | `--caminho` (obrigatorio), `--empresa_id`, `--temperatura` |
| `enviar` | Envia holerites por email e WhatsApp | `--competencia` (obrigatorio), `--modo` (mongodb/planilha), `--canais`, `--dry_run`, `--empresa_id` |
| `listar` | Lista holerites no MongoDB | `--competencia`, `--funcionario`, `--status`, `--limite` |
| `stats` | Exibe estatisticas | `--competencia` |

### 6.2 Exemplos de Uso

```bash
# Renomear todos os holerites de um diretorio
uv run python automatizar.py holerite renomear_arquivos --diretorio "C:\Holerites"

# Renomear de um mes especifico
uv run python automatizar.py holerite renomear_arquivos --diretorio "C:\Holerites" --mês_ano "01.2026"

# Processar PDFs com IA
uv run python automatizar.py holerite processar_pdfs --caminho "diretorio_com_pdfs"

# Enviar via MongoDB
uv run python automatizar.py holerite enviar --competencia "01/2026" --modo mongodb

# Enviar via planilha (simulacao)
uv run python automatizar.py holerite enviar --competencia "01/2026" --modo planilha --dry_run

# Listar holerites
uv run python automatizar.py holerite listar --competencia "01/2026" --limite 50

# Estatisticas
uv run python automatizar.py holerite stats --competencia "01/2026"
```

### 6.3 Validacoes

- `renomear_arquivos`: valida formato `MM.AAAA`, mes entre 1 e 12, ano entre 1900 e 2100
- `processar_pdfs`: verifica existencia do caminho, se e arquivo ou diretorio, valida prefixo "Recibo de Pagamento"
- `enviar`: valida formato `MM/AAAA`, componentes numericos, modo (mongodb/planilha)

---

## 7. Interface Interativa (TUI)

### 7.1 Interface_Holerite (src/interface/interface_holerite.py, 371 linhas)

Menu principal de operacoes com holerites:

```
OPERACOES COM HOLERITE
├── 1. Renomear arquivo(s)                     → _processar_renomear_holerite()
├── 2. Processar PDFs com IA (Gemini)          → _processar_pdfs_gemini()
├── 3. Enviar Holerites                        → _abrir_menu_envio()
├── 4. Listar Holerites no MongoDB             → _listar_holerites()
├── ─────────────────────────────────
├── 5. Estatisticas do Cache OCR               → _exibir_stats_cache()
├── 6. Limpar Cache OCR (antigos)              → _limpar_cache_antigo()
├── 7. Limpar todo o Cache OCR                 → _limpar_todo_cache()
└── 0. Voltar ao Menu Principal
```

### 7.2 Menu de Envio (src/interface/interface_envio_holerite.py, 795 linhas)

```
SISTEMA DE ENVIO DE HOLERITES
├── Via Planilha (modo planilha)
│   ├── Validar Planilha de Contatos
│   ├── Simulacao de Envio (Dry Run)
│   └── Executar Envio Real
├── Via MongoDB (modo mongodb)
│   ├── Ver Estatisticas
│   ├── Simulacao de Envio (Dry Run)
│   └── Executar Envio Real
├── ─────────────────────────────────
├── Verificar Servicos
├── Sincronizar Grupos WhatsApp
├── Gerenciar Dispositivos WhatsApp
│   ├── Listar dispositivos conectados
│   ├── Verificar status dos dispositivos
│   └── Mostrar dispositivo de uma empresa
└── Gerenciar Templates
```

---

## 8. Integracoes Externas

| Integracao | Tecnologia | Uso no Holerite |
|------------|-----------|-----------------|
| Google Gemini AI | `gemini-2.5-pro` | Extracao estruturada de holerites (HoleriteExtracaoSchema) |
| Gemini Flash Lite | `gemini-2.5-flash-lite` | Extracao de nome do cabecalho (fallback) |
| Mistral AI OCR | `mistral-ocr-2512` | OCR primario de cabecalhos de holerites |
| WhatsApp API | `go-whatsapp-web-multidevice` (Docker, porta 3000) | Envio de holerites para individuos e grupos |
| Zoho Mail API | OAuth2 (Self Client) | Envio de holerites por email |
| MongoDB | Atlas / local (pymongo) | Persistencia: holerites, contatos, cache OCR, empresas, funcionarios |
| Redis | 7.2+ (opcional) | Cache de servicos de referencia (nao usado diretamente pelo holerite) |

---

## 9. Pipeline de Extracao IA

### 9.1 Etapas Detalhadas

1. **Filtragem de arquivos**: apenas PDFs com prefixo "Recibo de Pagamento"
2. **Calculo de hash**: SHA256 do arquivo completo (lido em chunks de 8KB)
3. **Dedup**: consulta `holerite_service.buscar_por_hash()` → se existe, retorna sem reprocessar
4. **Extracao Gemini**: `gemini.documento_estruturado()` com `HoleriteExtracaoSchema`
   - Prompt: `PROMPT_EXTRACAO` com instrucoes detalhadas
   - Temperatura: 0.1 (configuravel)
   - Max tentativas: 2
   - Retry em resposta curta (<50 caracteres)
5. **Validacao**: `HoleriteExtracaoSchema.model_validate_json()` (Pydantic, `extra = "forbid"`)
6. **Lookup funcionario**: `funcionario_service.criar_ou_buscar_por_documento(cpf, nome)`
   - Se funcionario tem `status_cadastro == 'incompleto'`, marca como `funcionario_criado = True`
7. **Lookup empresa**: Se `empresa_id` nao fornecido, busca por `extracao.empresa_razao_social`
8. **Conversao para MongoDB**: `HoleriteMongoDB.from_extracao()`
9. **Insercao**: `holerite_service.criar_holerite()` (lida com `DuplicateKeyError`)
10. **Criacao de contatos**: `criar_contato_de_holerite()` + `contato_service.criar_ou_atualizar()`

### 9.2 HoleriteExtracaoSchema - Restricoes

- `extra = "forbid"`: Gemini nao pode inventar campos
- Validadores: `empresa_cnpj` e `funcionario_nome` nao podem ser vazios
- `mes_referencia`: 1-12 (meses normais), 13 (13o 1a parcela), 14 (13o 2a parcela)
- `ano_referencia`: >= 2000
- `ItemHoleriteExtracao`: `extra = "forbid"` tambem

### 9.3 Historico de Bugs Corrigidos

Os seguintes bugs foram identificados e corrigidos no codigo. Os testes que estavam marcados como `@pytest.mark.skip` foram reativados:

1. **Acesso a `extracao.competencia`** (atributo inexistente em `HoleriteExtracaoSchema`): Corrigido para formatar a partir de `mes_referencia`/`ano_referencia`.
2. **Acesso a `extracao.funcionario_documento`** (atributo inexistente): Corrigido para usar `extracao.funcionario_cpf`.
3. **Acesso a `funcionario_telefone` e `funcionario_email`** (inexistentes no modelo): Corrigido. Agora `criar_contato_de_holerite()` e chamado com `telefone=None, email=None`, nunca criando contatos com dados do PDF.
4. **Uso de `extracao.empresa_nome`**: Corrigido para usar `extracao.empresa_razao_social`.
5. **`HoleriteMongoDB.from_extracao()` recebendo strings**: Corrigido para passar objetos `ArquivoHolerite` e `ProcessamentoHolerite`.

10 testes permanecem marcados como `@pytest.mark.skip` por outras razoes (dependencias de infraestrutura MongoDB, etc).
---

## 10. Pipeline de Envio

### 10.1 Modo Planilha

1. **Carregar**: `planilha_holerites_service.carregar()` (Excel para DataFrame)
2. **Iterar contatos**: `planilha_holerites_service.iterar_contatos(mes, ano)`
   - Para cada linha com envio ativo (email, whatsapp ou grupo):
   - Monta diretorio: `{DIRETORIO GERAL}/{ANO}/{MES.ANO}/{DIRETORIO ESPECIFICO}`
   - Lista PDFs com prefixo "Recibo de Pagamento"
3. **Para cada contato**:
   - Monta contexto do template (nome, competencia, empresa, local)
   - Se `enviar_email` → `_enviar_email()` com template `EMAIL_HOLERITE`
   - Se `enviar_whatsapp` → `_enviar_whatsapp()` com template `WHATSAPP_INDIVIDUAL_HOLERITE`
   - Se `enviar_grupo_whatsapp` → `_enviar_whatsapp_grupo()` com template `WHATSAPP_GRUPO_HOLERITE`

### 10.2 Modo MongoDB

1. **Buscar pendentes**: `holerite_service.listar_pendentes_envio(competencia, empresa_id)`
   - Filtro: status IN (pendente, processado)
2. **Carregar contatos batch**: `contato_funcionario_service.obter_contatos_batch(funcionario_ids)`
   - OTIMIZACAO: 1 aggregation query em vez de N queries
3. **Para cada holerite**:
   - Verifica se arquivo existe no disco
   - Monta contexto do template
   - Se `"email" in canais` e email disponivel → `_enviar_email()` + `registrar_envio()`
   - Se `"whatsapp" in canais` e whatsapp disponivel → `_enviar_whatsapp()` + `registrar_envio()`
4. **Registro de envio**: `holerite_service.registrar_envio()` com dados do canal, destino, sucesso
   - Atualiza status do holerite para ENVIADO se sucesso

### 10.3 Canais de Envio

**Email (ZohoMailService):**
- Template: `EMAIL_HOLERITE`
- Fallback: assunto "Recibo de Pagamento - {mes}/{ano}"
- Anexos: lista de PDFs do holerite

**WhatsApp Individual:**
- Template: `WHATSAPP_INDIVIDUAL_HOLERITE`
- Fallback: "Ola {nome}! Segue seu recibo de pagamento de {mes_extenso}/{ano}."
- Device ID: obtido da empresa vinculada (`empresa.whatsapp_device_id`)
- Envia: mensagem de texto + arquivos em sequencia (com delay de 1.5s entre arquivos)

**WhatsApp Grupo:**
- Template: `WHATSAPP_GRUPO_HOLERITE`
- Fallback: "Bom dia! Seguem os recibos de pagamento referente ao mes de {mes_extenso}/{ano}."
- Busca grupo por nome via `grupo_whatsapp_service.buscar_por_nome()`
- Requer `device_id` da empresa

### 10.4 Templates - Placeholders

| Placeholder | Descricao |
|-------------|-----------|
| `{funcionario_nome}` ou `{nome}` | Nome do funcionario |
| `{competencia}` | Competencia (MM/AAAA) |
| `{mes}` | Numero do mes |
| `{ano}` | Ano |
| `{mes_extenso}` | Nome do mes por extenso |
| `{empresa}` | Nome da empresa |
| `{local}` | Local/Contrato/Polo |
| `{tipo_documento}` | "Recibo de Pagamento" |
| `{data_envio}` | Data/hora do envio |

---

## 11. Cache OCR

### 11.1 Estrutura

**Colecao MongoDB:** `cache_ocr`

```json
{
    "hash_imagem": "sha256:abc123...",
    "nome_arquivo": "cabecalho_001.png",
    "caminho_arquivo": "/path/to/file.png",
    "resultado_ocr": "JOAO DA SILVA",
    "data_criacao": ISODate("2026-01-14T10:30:00Z"),
    "tamanho_arquivo": 123456
}
```

**Indice:** `hash_imagem` (ASCENDING, unique)

### 11.2 Metodos de Estatistica

```python
cache_ocr.obter_estatisticas() -> {
    'status': 'OK',
    'total_documentos': 1250,
    'tamanho_total_mb': 15.30,
    'banco_dados': 'MS_Automatizar',
    'colecao': 'cache_ocr',
    'arquivos_unicos': 1180,
    'mongo_uri': 'mongodb://...'
}
```

### 11.3 Fluxo de Cache

```
NomeExtractorOCR.extrair_nome(imagem)
  ├── cache_ocr.obter_ocr(imagem) → calcula hash → busca no MongoDB
  │   ├── HIT → retorna texto do cache (evita chamada OCR)
  │   └── MISS → chama Mistral OCR, depois cache_ocr.salvar_ocr()
  └── Retorna nome do funcionario

NomeExtractorIA.extrair_nome(imagem)
  └── Mesmo fluxo, mas com Gemini Flash Lite e prompt customizado
```

---

## 12. Testes

### 12.1 test_holerite_service.py (653 linhas)

14 classes de teste, cobrindo:

| Classe de Teste | Descricao |
|-----------------|-----------|
| `TestHoleriteServiceInit` | Inicializacao com/sem MongoDB, property disponivel |
| `TestCalcularHashArquivo` | Calculo SHA256 para arquivos existentes/inexistentes |
| `TestCriarHolerite` | Criacao com sucesso e com MongoDB indisponivel |
| `TestBuscarPorId` | Busca por ObjectId (encontrado/nao encontrado) |
| `TestBuscarPorHash` | Busca por hash SHA256 |
| `TestBuscarPorFuncionario` | Busca por funcionario (com/sem resultados, MongoDB indisponivel) |
| `TestBuscarPorDocumento` | Busca por CPF (testa normalizacao) |
| `TestListarTodos` | Listagem com/sem filtros |
| `TestContarTotal` | Contagem |
| `TestBuscarPorCompetencia` | Busca por competencia |
| `TestAtualizarStatus` | Atualizacao de status (sucesso/nao encontrado) |
| `TestRegistrarEnvio` | Registro de envio |
| `TestListarEnviosHolerite` | Listagem de envios |
| `TestListarPendentesEnvio` | Listagem de pendentes |
| `TestContarPorStatus` | Agregacao por status |
| `TestExisteHolerite` | Verificacao de existencia |

### 12.2 test_holerite_processador.py (1112 linhas)

16 classes/grupos de teste:

| Classe de Teste | Cobertura |
|-----------------|-----------|
| `TestHoleriteProcessadorInit` | Injecao de dependencias, criacao de servicos, estatisticas zeradas |
| `TestDisponivel` | Property disponivel (gemini, holerite_service, funcionario_service) |
| `TestCalcularHashArquivo` | Hash valido, reprodutivel, inexistente, diferentes conteudos |
| `TestProcessarArquivoValidacoes` | Arquivo nao disponivel, nao existe, nao e PDF, path como string |
| `TestProcessarArquivoExtracao` | Extracao sucesso, retry logic, max tentativas, resposta curta, temperatura customizada |
| `TestProcessarArquivoLookup` | Busca funcionario por CPF, autocadastro (3 testes SKIP por bug) |
| `TestProcessarArquivoArmazenamento` | Salvamento, falha, criacao contatos, estatisticas (6 testes SKIP) |
| `TestProcessarArquivoHashDuplicado` | Deteccao de duplicata, continuacao sem hash |
| `TestProcessarDiretorio` | Diretorio nao existe, sem PDFs, recursivo, nao recursivo, empresa_id, path string |
| `TestObterEstatisticas` | Estatisticas inicial, apos processamento, calculo taxa sucesso |
| `TestResultadoProcessamentoHolerite` | Dataclass: inicial, extracao, mensagens, metricas |

**10 testes SKIP** devido a dependencias de infraestrutura (MongoDB, Redis) em ambiente de teste.

### 12.3 Testes Relacionados (outros dominios)

- `test_cache_ocr_service.py` - Cache OCR (MongoDB)
- `test_cache_service.py` - CacheService (Redis + memoria)
- `test_funcionario_service.py` - FuncionarioService (usado na extracao)
- `test_empresa_service.py` - EmpresaService (usado na extracao)
- `test_funcionario_sanitizador.py` - SanitizadorFuncionario
- `test_env_validator.py` - ValidadorAmbiente
- `test_whatsapp_multidevice.py` - WhatsAppService (630 linhas, 9 classes)

### 12.4 Fixtures usadas

- `mock_env_vars` - Variaveis de ambiente mockadas
- `temp_pdf_file` - Arquivo PDF temporario (`%PDF-1.4\n%%EOF`)
- `tmp_path` - Diretorio temporario (pytest)
- `mock_collection`, `mock_database`, `mock_mongo_client` - Mocks MongoDB

### 12.5 Gaps de Teste

| Componente | Sem Testes |
|------------|-----------|
| `EnvioHoleriteOrquestrador` | Nenhum teste |
| `PlanilhaHoleritesService` | Nenhum teste |
| `ContatoFuncionarioService` | Nenhum teste (parcial) |
| `Interface Holerite` | Nenhum teste |
| `Interface Envio Holerite` | Nenhum teste |
| `CLI comandos` | Nenhum teste |
| `src/holerite.py` (classes core) | Nenhum teste |

---

## 13. Configuracao

### 13.1 Variaveis de Ambiente

```env
# MongoDB
MONGO_URI=mongodb+srv://...
MONGO_DATABASE_NAME=MS_Automatizar

# IA
KEY_API_GEMINI=...
KEY_API_MISTRAL=...

# WhatsApp
WHATSAPP_API_URL=http://localhost:3000

# Zoho Mail
ZOHO_CLIENT_ID=...
ZOHO_CLIENT_SECRET=...
ZOHO_REFRESH_TOKEN=...
ZOHO_ACCESS_TOKEN=...
ZOHO_ACCOUNT_ID=...
ZOHO_EMAIL_FROM=...

# Planilha de Holerites (opcional)
PLANILHA_HOLERITES_PATH=/caminho/para/planilha.xlsx

# Configuracao de Envio
ENVIO_MAX_TENTATIVAS=3
ENVIO_RETRY_DELAY_SECONDS=5
```

### 13.2 Dependencias do Dominio

| Pacote | Uso |
|--------|-----|
| `pymongo` | MongoDB driver |
| `pydantic>=2.0` | Validacao de dados |
| `google-genai` | Gemini API |
| `mistralai` | Mistral AI OCR |
| `PyPDF2` | Manipulacao de PDFs |
| `pypdfium2` | Conversao PDF para imagem (embutido, cross-platform — nao usa Poppler) |
| `PIL/Pillow` | Manipulacao de imagens |
| `requests` | Chamadas HTTP (WhatsApp, Zoho) |
| `httpx` | Download de documentos da internet |
| `pandas` | Leitura de planilhas |
| `openpyxl` | Engine Excel para pandas |
| `python-dotenv` | Leitura de .env |

### 13.3 Docker

```bash
# WhatsApp API
docker compose -f docker-compose.whatsapp.yml up -d

# Redis (opcional)
docker compose -f docker-compose.redis.yml up -d
```

---

## 14. Glossario

| Termo | Significado |
|-------|-------------|
| **Holerite** | Recibo de pagamento / contracheque |
| **Competencia** | Mes/ano de referencia do pagamento (formato MM/AAAA) |
| **Vencimentos** | Proventos, creditos, acrescimos ao salario |
| **Descontos** | Valores deduzidos do salario (INSS, IRRF, VT, etc.) |
| **Bases de Calculo** | Valores usados para calcular INSS, IRRF, FGTS |
| **Salario Liquido** | Total vencimentos - total descontos |
| **TipoFolhaEnum** | Classificacao: Mensal, Horista, 13o, Ferias, Rescisao, Adiantamento |
| **StatusHoleriteEnum** | Ciclo de vida: processado, pendente, enviado, erro |
| **Hash SHA256** | Identificador unico do arquivo para deduplicacao |
| **Cache OCR** | Cache de resultados de OCR no MongoDB |
| **Device ID** | Identificador do dispositivo WhatsApp (JID: `numero@s.whatsapp.net`) |
| **Dry Run** | Modo de simulacao que nao envia mensagens de fato |
| **Structured Output** | Recurso do Gemini que retorna JSON validado por schema Pydantic |
| **Autocadastro** | Criacao automatica de registro incompleto quando dados sao insuficientes |
