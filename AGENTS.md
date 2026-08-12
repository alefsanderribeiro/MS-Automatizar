# MS-Automatizar — Conhecimento Completo do Projeto

> **Versão**: 0.9.8 | **Última Atualização**: Agosto/2026
> **Autor**: Alefsander Ribeiro Nascimento
> **Repositório**: `https://github.com/alefsanderribeiro/MS-Automatizar`

---

## Índice

1. [Identidade do Projeto](#1-identidade-do-projeto)
2. [Estrutura de Diretórios](#2-estrutura-de-diretórios)
3. [Entry Point & Fluxo de Execução](#3-entry-point--fluxo-de-execução)
4. [Camada de Dados (Models)](#4-camada-de-dados-models)
5. [Camada de Serviços (Services)](#5-camada-de-serviços-services)
6. [Orquestradores (Processadores)](#6-orquestradores-processadores)
7. [CLI e Interface](#7-cli-e-interface)
8. [Integrações Externas](#8-integrações-externas)
9. [Utilitários](#9-utilitários)
10. [Testes](#10-testes)
11. [Infraestrutura](#11-infraestrutura)
12. [Configuração de Ambiente](#12-configuração-de-ambiente)
13. [Gaps e Observações](#13-gaps-e-observações)

---

## 1. Identidade do Projeto

**MS-Automatizar** é um sistema de automação administrativa para **a empresa cliente**. Ele automatiza dois domínios principais:

### Domínio 1: Folha de Ponto (Timesheet)
- Geração de folhas de ponto mensais em PDF (via HTML → WeasyPrint)
- Dados provenientes do MongoDB (funcionários, empresas, cargos, horários, contratos)
- Análise de PDFs manuscritos com IA (Gemini 2.5 Pro + Structured Output Pydantic)
- Envio por E-mail (Zoho Mail) e WhatsApp (individual + grupos)

### Domínio 2: Holerite (Payslip)
- Renomeação de PDFs de holerite por extração de nome via OCR (Mistral) ou IA (Gemini)
- Extração completa de dados: PDF → Gemini → schema validado → MongoDB
- Cache de OCR por hash SHA256 para evitar reprocessamento
- Envio automatizado por E-mail e WhatsApp

### Stack Técnica
| Categoria | Tecnologia |
|-----------|-----------|
| Linguagem | Python 3.12+ |
| Validação | Pydantic V2 |
| Banco | MongoDB (via PyMongo, pool thread-safe) |
| Cache | Redis 7.2 + fallback em memória |
| IA/OCR | Google Gemini 2.5 Pro, Mistral AI |
| Email | Zoho Mail API (OAuth2) |
| WhatsApp | go-whatsapp-web-multidevice (Docker) |
| PDF | WeasyPrint, pypdfium2, PyPDF2 |
| Excel | openpyxl, pandas |
| CLI/UI | argparse, questionary, rich |
| Gerenciador | uv (Astral) |

---

## 2. Estrutura de Diretórios

```
MS-Automatizar/
├── automatizar.py                    # ▲ ENTRY POINT — chama start_command()
├── pyproject.toml                    # Metadados, dependências, entry point CLI
├── pytest.ini                        # Config de testes (coverage ≥50%)
├── AGENTS.md                         # ← ESTE ARQUIVO — conhecimento do projeto
│
├── src/
│   ├── __init__.py                   # Re-exporta os principais submódulos (PyInstaller)
│   │
│   ├── folha_de_ponto.py             # ★ CORE: Folha_de_Ponto (~1700 linhas, geração de timesheets)
│   │   └── Classes: FolhaPontoHtmlTemplate, HtmlToPdfConverter, GeradorFolhaPonto,
│   │               ProcessadorFolhaPonto, GerenciadorDiretorios
│   │
│   ├── holerite.py                   # ★ CORE: Holerite (renomeação/processamento)
│   │   └── Classes: NomeExtractorOCR, NomeExtractorIA, NomeExtractorComposite,
│   │               PdfProcessorService, ArquivoProcessor, Holerite
│   │
│   ├── comandos/                     # Handlers CLI (argparse)
│   │   ├── main.py                   # start_command() — dispatch central
│   │   ├── folha_de_ponto.py         # 14 subcomandos de folha de ponto
│   │   ├── holerite.py               # 5 subcomandos de holerite
│   │   ├── referencias.py            # CRUD de contratos/horários/funções
│   │   └── diretorios.py             # CRUD + sync de diretórios
│   │
│   ├── config/
│   │   └── urls.py                   # URLs de dados (ex.: OneDrive) + timeouts
│   │
│   ├── interface/                    # TUI interativa (questionary + rich)
│   │   ├── menu.py                   # init_interface() — menu principal
│   │   ├── core/
│   │   │   ├── components.py         # MenuBuilder, display/input functions
│   │   │   ├── theme.py              # Tema Rich, cores, ícones
│   │   │   └── validators.py         # Validadores de email, CPF, CNPJ, etc.
│   │   ├── interface_folha_de_ponto.py
│   │   ├── interface_holerite.py
│   │   ├── interface_envio_folha_ponto.py
│   │   ├── interface_envio_holerite.py
│   │   ├── interface_funcionarios.py
│   │   ├── interface_empresas.py
│   │   ├── interface_referencias.py
│   │   └── interface_configuracoes.py
│   │
│   ├── models/                       # Modelos Pydantic V2
│   │   ├── __init__.py               # Exporta os principais modelos públicos
│   │   ├── funcionario_models.py     # FuncionarioMongoDB + FuncionarioBuilder (~1750 linhas)
│   │   ├── empresa_models.py         # EmpresaMongoDB + EmpresaBuilder (~470 linhas)
│   │   ├── folha_de_ponto_models.py  # FolhaDePontoMongoDB + FolhaDePontoData
│   │   ├── holerite_models.py        # HoleriteMongoDB + HoleriteExtracaoSchema
│   │   ├── contato_funcionario_models.py
│   │   ├── contrato_models.py
│   │   ├── diretorio_models.py
│   │   ├── feriado_models.py
│   │   ├── funcao_models.py
│   │   ├── horario_models.py
│   │   ├── grupo_whatsapp_models.py
│   │   ├── template_mensagem_models.py
│   │   └── envio_folha_ponto_models.py
│   │
│   ├── services/                     # ★ Lógica de negócio (26 arquivos)
│   │   ├── __init__.py               # Hub central de re-exports
│   │   ├── mongodb_connection.py      # MongoDBConnectionPool (singleton thread-safe)
│   │   ├── mongodb_utils.py          # Funções auxiliares de lookup/formatação de data
│   │   ├── analise_ai_service.py     # GeminiService + MistralService
│   │   ├── cache_service.py          # CacheService (Redis + memória, singleton)
│   │   ├── cache_keys.py             # ★ Formadores centralizados de chaves de cache (padronização p/ evitar stale)
│   │   ├── cache_ocr_service.py      # CacheOCRMongoDB (hash SHA256)
│   │   ├── config_service.py         # ConfigService (leitura/escrita .env)
│   │   ├── funcionario_service.py    # ★ o maior arquivo do projeto (~1750 linhas)
│   │   ├── empresa_service.py        # ~1000 linhas
│   │   ├── folha_ponto_service.py
│   │   ├── holerite_service.py
│   │   ├── contato_funcionario_service.py
│   │   ├── contrato_service.py
│   │   ├── diretorio_service.py
│   │   ├── funcao_service.py
│   │   ├── horario_service.py
│   │   ├── whatsapp_service.py       # ★ API multidevice (v9)
│   │   ├── grupo_whatsapp_service.py
│   │   ├── zoho_mail_service.py      # ★ OAuth2 completo
│   │   ├── planilha_contatos_service.py
│   │   ├── planilha_holerites_service.py
│   │   ├── envio_folha_ponto_service.py
│   │   ├── template_mensagem_service.py
│   │   ├── feriado_service.py
│   │   └── historico_decorators.py   # @registrar_historico + HistoricoMixin
│   │
│   ├── processadores/                # Orquestradores de pipeline
│   │   ├── __init__.py
│   │   ├── processador_folha_ponto.py      # Pipeline IA: PDF→Gemini→MongoDB
│   │   ├── holerite_processador.py         # Extração IA de holerites
│   │   ├── envio_folha_ponto_orquestrador.py  # Envio folha de ponto
│   │   └── envio_holerite_orquestrador.py  # Envio holerites
│   ├── templates/                   # Templates HTML
│   │   └── Folha_de_Ponto.html      # Template HTML para geração de PDF
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logger_config.py          # Logger + remoção de emojis (PowerShell)
│       ├── dotenv_path.py            # Localização do .env
│       ├── env_validator.py          # Validador de variáveis de ambiente
│       ├── exceção.py                # MinhaExcecao customizada
│       ├── telefone_utils.py         # Normalização/validação de telefone
│       ├── retry_utils.py            # Decoradores de retry
│       ├── data_utils.py             # ★ Parsing flexível de data (DD/MM/YYYY + ISO) e formatação BR
│       ├── funcionario_sanitizador.py # Limpeza de nomes + construção incompleta
│       └── type.py                   # Conversores argparse (bool, date, list)
│
├── tests/                            # Suíte de testes pytest
│   ├── conftest.py                   # Fixtures globais
│   ├── __init__.py
│   ├── fixtures/
│   │   ├── mongodb_fixtures.py       # service mocks + document factories
│   │   ├── redis_fixtures.py         # Redis mock + cache test helpers
│   │   ├── model_fixtures.py         # fixtures Pydantic
│   │   ├── gemini_fixtures.py        # Mock de IA (success/retry/fail)
│   │   └── file_fixtures.py          # PDF/Excel/JSON temporários
│   ├── unit/
│   │   ├── services/                 # cache_keys, cache_service, cache_ocr, empresa,
│   │   │                             # folha_ponto, funcionario, holerite, whatsapp_service
│   │   ├── processadores/            # holerite + folha ponto
│   │   └── utils/                    # env, sanitizador, data_utils
│   ├── test_fixtures_validation.py   # Validação de fixtures
│   ├── test_whatsapp_multidevice.py  # Suíte multidevice WhatsApp
│   ├── FIXTURES_SUMMARY.md
│   ├── FIXTURE_USAGE_EXAMPLES.md
│   └── README.md
│
├── docs/                             # Documentação de funcionalidades
│   ├── FOLHA_DE_PONTO.md
│   ├── HOLERITE.md
│   ├── ENVIO_FOLHAS_PONTO.md
│   ├── ENVIO_HOLERITE.md
│   └── GUIA_MULTIDEVICE_COMANDOS.md  # Guia prático do envio multidevice WhatsApp
│
├── specs/                            # Especificações de domínio
│   ├── folha-de-ponto.md
│   └── holerite.md
│
├── docker-compose.yml                 # ⭐ GRUPO ÚNICO: MongoDB 8.0 + Redis 7.2 + WhatsApp API
│
└── (scripts de manutenção/migração ficam fora do público — não incluídos)
```

---

## 3. Entry Point & Fluxo de Execução

### Dispatcher Central

```
automatizar.py::main()
  └─ src.comandos.main::start_command()
       │
       ├─ argparse COM args
       │    ├─ "folha_de_ponto" → handle_folha_de_ponto()
       │    ├─ "holerite" → handle_holerite()
       │    ├─ "referencias" → handle_referencias()
       │    └─ "diretorios" → handle_diretorios()
       │
       └─ argparse SEM args → src.interface.menu::init_interface()
            ├─ Logo + verificação de ambiente
            └─ MenuBuilder → menu hierárquico
```

### Fluxo Folha de Ponto

```
CLI: python automatizar.py folha_de_ponto criar --data 2026-05-01 --id_funcionario 123
  # (o arg --data aceita o formato YYYY-MM-DD — src/utils/type.py::date_type)
  → handle_folha_de_ponto() → Folha_de_Ponto()
       → Busca dados (FuncionarioService → EmpresaService → FuncaoService → etc.)
       → Gera HTML (Jinja2 template)
       → Converte para PDF (WeasyPrint)
       → Salva no diretório de destino

OU via processamento de PDF preenchido:
  → Folha_de_Ponto().processar_pdfs() → ProcessadorFolhaPonto
       → Valida arquivo
       → Extrai com Gemini (3 tentativas com temperature variável)
       → Faz lookup do funcionário (nome_normalizado + fuzzy match)
       → Armazena no MongoDB

OU via envio:
  → EnvioFolhaPontoOrquestrador.executar(mes, ano, tipos_envio)
       → Carrega planilha de contatos
       → Pré-processa grupos WhatsApp
       → Para cada contato: email (Zoho) + WhatsApp individual + WhatsApp grupo
       → Registra status do envio no MongoDB
```

### Fluxo Holerite

```
CLI: python automatizar.py holerite processar_pdfs --caminho /path
  → HoleriteProcessador.processar_diretorio()
       → Para cada PDF com prefixo "Recibo de Pagamento":
            → Verifica hash SHA256 (cache)
            → Extrai com Gemini (HoleriteExtracaoSchema)
            → Busca/vincula funcionário por CPF/nome
            → Busca/vincula empresa
            → Cria HoleriteMongoDB + contatos

CLI: python automatizar.py holerite enviar --competencia 01/2025 --modo mongodb
  → EnvioHoleriteOrquestrador.enviar_via_mongodb()
       → Lista holerites pendentes
       → Carrega contatos em lote (1 query otimizada)
       → Para cada holerite: email + WhatsApp
       → Registra envio
```

---

## 4. Camada de Dados (Models)

### Arquitetura

Modelos Pydantic V2 distribuídos em 14 arquivos. Todos seguem:
- `BaseModel` do Pydantic V2 (sem classe base compartilhada)
- Relacionamentos via `bson.ObjectId` (NÃO DBRef ou documentos embutidos)
- Campos comuns: `criado_em`, `atualizado_em`, `versao`, `historico_alteracoes`
- Métodos: `to_mongo_insert()`, `to_mongo_update()`, `adicionar_historico()`
- Builders fluent (vários modelos têm builders)

### Mapa de Entidades

```
FuncionarioMongoDB (central)
  ├── empresas_ids: List[ObjectId] ──→ EmpresaMongoDB (N:N)
  ├── contrato_empresa_id: ObjectId ──→ ContratoMongoDB (1:1)
  ├── horario_id: ObjectId ──→ HorarioMongoDB (1:1)
  ├── funcao_id: ObjectId ──→ FuncaoMongoDB (1:1)
  └── diretorio_id: ObjectId ──→ DiretorioMongoDB (1:1)

FolhaDePontoMongoDB
  ├── funcionario_id: ObjectId ──→ FuncionarioMongoDB (N:1)
  └── empresa_id: ObjectId ──→ EmpresaMongoDB (N:1)

HoleriteMongoDB
  ├── empresa_id: ObjectId ──→ EmpresaMongoDB (N:1)
  └── funcionario_id: ObjectId ──→ FuncionarioMongoDB (N:1, opcional)

ContatoFuncionarioMongoDB
  └── funcionario_id: ObjectId ──→ FuncionarioMongoDB (N:1)

DiretorioMongoDB
  └── contrato_id: ObjectId ──→ ContratoMongoDB (1:1)
```

### Enums principais

| Arquivo | Enums |
|---------|-------|
| `funcionario_models.py` | TipoContrato, StatusFuncionario, StatusCadastro |
| `empresa_models.py` | StatusEmpresa |
| `folha_de_ponto_models.py` | DiaSemana, TipoDia, StatusFolhaPonto |
| `holerite_models.py` | TipoFolhaEnum, StatusHoleriteEnum |
| `contato_funcionario_models.py` | TipoContato, StatusContato, OrigemContato |
| `contrato_models.py` | StatusContrato |
| `diretorio_models.py` | StatusDiretorio |
| `feriado_models.py` | TipoFeriado, StatusFeriado |
| `funcao_models.py` | StatusFuncao |
| `horario_models.py` | StatusHorario |
| `grupo_whatsapp_models.py` | StatusGrupo |
| `template_mensagem_models.py` | TipoTemplateEnum, StatusTemplate |
| `envio_folha_ponto_models.py` | TipoEnvioEnum, StatusEnvioEnum |

---

## 5. Camada de Serviços (Services)

### Padrão Arquitetural

- **26 arquivos** de serviço
- **Singleton**: a maioria dos serviços tem uma instância global criada no módulo
- **Pool de conexão compartilhado**: `MongoDBConnectionPool` (thread-safe, double-checked locking)
- **Observação**: todos os services usam o `MongoDBConnectionPool` centralizado — não há mais serviços criando `MongoClient` próprio.

### Cache

O `CacheService` (Redis com TTL 300s + fallback em memória) é usado de forma híbrida por vários serviços de dados de referência (Contrato, Diretorio, Funcao, Horario, Empresa). As chaves seguem o esquema centralizado em `cache_keys.py` (detalhe na seção 9) para garantir consistência entre leitura e invalidação.

`CacheOCRMongoDB` é separado — usa MongoDB com hash SHA256 para cache de OCR.

### HistoricoMixin + @registrar_historico

Decorator e Mixin para auditoria automática:
- Captura: valores anteriores, novos valores, timestamp, origem, versão
- Origens suportadas: "interface_cli", "excel", "api", "sistema", "importacao", "migracao"
- Usado por: ContratoService, DiretorioService, EmpresaService, FuncaoService, HorarioService, FeriadoService, FuncionarioService, TemplateMensagemService

### Arquivos Mais Pesados (candidatos a refatoração)

| Arquivo | Linhas | Observação |
|---------|--------|------------|
| `funcionario_service.py` | ~1750 | Extremamente grande — fuzzy search, CRUD, autocadastro, $lookup |
| `empresa_service.py` | ~1000 | CRUD + autocadastro + cache híbrido |
| `zoho_mail_service.py` | ~915 | OAuth2 completo + envio |
| `folha_de_ponto.py` | ~1700 | Geração de timesheet — várias classes |
| `whatsapp_service.py` | ~856 | API multidevice |
| `envio_holerite_orquestrador.py` | ~865 | Orquestração de envio |
| `processador_folha_ponto.py` | ~850 | Pipeline IA |
| `envio_folha_ponto_orquestrador.py` | ~828 | Orquestração de envio |
| `contato_funcionario_service.py` | ~799 | CRUD + batch optimization |
| `comandos/folha_de_ponto.py` | ~734 | Handler CLI — grande para handler |

---

## 6. Orquestradores (Processadores)

### ProcessadorFolhaPonto
Pipeline de 4 estágios:
1. **Validar** → existência, tipo PDF, tamanho < 50MB
2. **Extrair** → Gemini 2.5 Pro com Structured Output (até 3 retries, temperature 0.2→0.4→0.6)
3. **Lookup** → busca por nome_normalizado → fuzzy match (0.75 threshold) → autocadastro
4. **Armazenar** → cria/atualiza FolhaDePontoMongoDB, vincula empresas_ids

Schema de extração: `ExtratorFolhaPonto`

### HoleriteProcessador
- Filtra PDFs por prefixo "Recibo de Pagamento"
- Deduplica por hash SHA256
- Extrai com `HoleriteExtracaoSchema` (Pydantic, `extra = "forbid"`)
- Converte `HoleriteExtracaoSchema → HoleriteMongoDB` via `from_extracao()`
- Cria/atualiza contatos do funcionário

### EnvioFolhaPontoOrquestrador
- `executar(mes, ano, tipos_envio, contatos_ids, dry_run)` → fluxo principal
- Otimização: pré-processa grupos por empresa (evita N+1 queries)
- Canais: email (Zoho), WhatsApp individual, WhatsApp grupo
- Roteamento multidevice: cada empresa pode ter um `whatsapp_device_id`; o orquestrador envia pelo device correto (`X-Device-Id`)
- Templates renderizados com placeholders: `{nome}`, `{mes}`, `{ano}`, `{empresa}`
- Retorna `RelatorioEnvio` com duração, sucessos, falhas

### EnvioHoleriteOrquestrador
Dois modos:
1. **`enviar_via_planilha()`** → lê planilha de contatos, envia por contato
2. **`enviar_via_mongodb()`** → busca holerites pendentes, carrega contatos em batch (1 query), envia

---

## 7. CLI e Interface

### Comandos CLI

| Comando | Subcomandos |
|---------|-------------|
| `folha_de_ponto` | criar, análise, gerar_dataframe, mongodb, processar_pdf, criar_mongodb_id, criar_mongodb_filtro, envio, envio-verificar, envio-validar, envio-sincronizar, envio-dispositivos, envio-listar, envio-executar |
| `holerite` | renomear_arquivos, processar_pdfs, enviar, listar, stats |
| `referencias` | stats, contratos, contrato-add, contrato-inativar, horarios, horario-add, horario-inativar, funcoes, funcao-add, funcao-inativar |
| `diretorios` | listar, estatisticas, adicionar, atualizar, criar-para-contrato, criar-todos, inativar |

### Interface Interativa (TUI)

Framework: `MenuBuilder` (fluent builder sobre `questionary.select` + `rich`)

```
Menu Principal
├── Folha de Ponto
│   ├── Gerar Folha de Ponto (PDF + MongoDB)
│   ├── Processar PDFs Preenchidos com IA
│   └── Enviar Folhas → submenu completo (verificar, validar, sincronizar, dry-run, real, histórico)
│
├── Holerite
│   ├── Renomear arquivos
│   ├── Processar PDFs com IA
│   ├── Enviar Holerites → submenu (via planilha ou MongoDB)
│   ├── Listar Holerites
│   └── Estatísticas Cache OCR
│
├── Gerenciar Dados
│   ├── Funcionários (CRUD completo + exportação)
│   ├── Empresas (CRUD completo + migração)
│   └── Referências (Contratos, Horários, Funções, Diretórios, Feriados)
│
└── Configurações
    ├── MongoDB (URI, database, pool, testar)
    ├── APIs (Gemini, Mistral, testar)
    ├── Sistema (modo operação, log level, output dir)
    └── Zoho Mail (OAuth2 completo)
```

---

## 8. Integrações Externas

### GeminiService (analise_ai_service.py)
- Modelo: `gemini-2.5-pro` (default)
- Métodos: `imagem()`, `texto()`, `documento()`, `documento_na_internet()`, `documento_estruturado()`, `imagem_estruturada()`
- Structured Output com Pydantic V2 (auto-detects inline vs File API para >20MB)
- `extra = "forbid"` nos schemas de extração para evitar alucinação

### MistralService (analise_ai_service.py)
- Modelos: `mistral-ocr-2512` (OCR) + `mistral-small-2506` (chat)
- Métodos: `imagem()`, `documento()`, `documento_na_internet()`, `texto()`

### WhatsAppService (whatsapp_service.py)
- API REST `go-whatsapp-web-multidevice` **v9** (Docker, porta 3000)
- **Autenticação (v8+/v9):** `Authorization: Basic base64(user:pass)` via `WHATSAPP_BASIC_AUTH`; se `WHATSAPP_API_KEY` contiver `:` é tratada como `user:pass` (Basic); token simples vira `Bearer` (legado v7)
- **QR code (v9):** `/app/qr` foi REMOVIDO na v9 — `obter_qr_code()` usa `/app/login` (`results.qr_link`) com fallback p/ `/app/qr` (v8 legacy)
- **Multidevice:** `listar_dispositivos()`, `obter_id_dispositivo_por_jid()`, `verificar_status_dispositivo()`
- Envio: `enviar_arquivo()`, `enviar_texto()`, `enviar_multiplos_arquivos()` (sequenciado para evitar rate limit)
- Roteamento por dispositivo via header `X-Device-Id` (quando a empresa tem `whatsapp_device_id`)
- Grupos: `listar_grupos()`, `verificar_status()`, `obter_qr_code()`
- Singleton global: `whatsapp_service`

### ZohoMailService (zoho_mail_service.py)
- OAuth2 completo: autorização → callback HTTP local → tokens → refresh automático
- Datacenters: com, eu, in, com.cn, com.au, jp
- Envio: `enviar_email()` com anexos, HTML, CC/BCC
- Singleton global: `zoho_mail_service`

### CacheService (cache_service.py)
- Redis + fallback em memória
- TTL configurável, operações em lote, invalidação por padrão (wildcard)
- Singleton global: `cache_service`

### CacheOCRMongoDB (cache_ocr_service.py)
- Hash SHA256 de imagem → MongoDB `cache_ocr`
- Singleton global: `cache_ocr`

### MongoDBConnectionPool (mongodb_connection.py)
- Singleton thread-safe com double-checked locking
- Pool size configurável via .env
- `@retry_mongodb()` decorator com exponential backoff
- Singleton global: `mongodb_pool`

---

## 9. Utilitários

| Utilitário | Função Principal |
|------------|------------------|
| `logger_config.py` | Logger com arquivo + console, filtro de emojis (PowerShell) |
| `dotenv_path.py` | `caminho_dotenv()` — localiza .env |
| `env_validator.py` | `ValidadorAmbiente` — validação tipada de env vars |
| `exceção.py` | `MinhaExcecao` — exceção base customizada |
| `telefone_utils.py` | `normalizar_telefone()` → `5511999999999@s.whatsapp.net`, validação com DDD |
| `retry_utils.py` | `@retry_com_log()`, `retry_simples()`, `RetryContextManager` |
| `data_utils.py` | `parse_data_flexivel()` (aceita DD/MM/YYYY e ISO), `formatar_data_br()`, `formatar_data_hora_br()`, `date_para_datetime_inicio/fim()` |
| `funcionario_sanitizador.py` | `SanitizadorFuncionario` (limpeza) + `ConstrutorFuncionarioIncompleto` |
| `type.py` | `bool_type()`, `date_type()` (ISO), `list_type()` — conversores argparse |

### cache_keys.py — Esquema central de chaves de cache

`src/services/cache_keys.py` centraliza os formadores de chave (`{entidade}:{id}`, `{entidade}:all`, por nome, por ano/mês) e helpers de padrão de invalidação (`{entidade}:*`). Regra de ouro: toda leitura de `{prefixo}:...` deve ser invalidável escaneando `{prefixo}:*`. Também fornece `normalizar_nome()` e `ttl_padrao()` (via `CACHE_TTL`, default 300s).

---

## 10. Testes

### Estrutura
- **Framework**: pytest 8+ com pytest-mock, pytest-cov, pytest-asyncio, freezegun, faker
- **Cobertura mínima**: 50% (falha abaixo disso — `--cov-fail-under=50`)
- **Markers**: `unit`, `integration`, `slow`
- **Fixtures**: em `tests/fixtures/` (mongodb, redis, models, gemini, file)

### Cobertura Atual (arquivos de teste)

| Categoria | Arquivos |
|-----------|----------|
| Services | `test_cache_service`, `test_cache_ocr_service`, `test_cache_keys`, `test_empresa_service`, `test_folha_ponto_service`, `test_funcionario_service`, `test_holerite_service`, `test_whatsapp_service` |
| Processadores | `test_holerite_processador`, `test_processador_folha_ponto` |
| Utils | `test_env_validator`, `test_funcionario_sanitizador`, `test_data_utils` |
| WhatsApp Multidevice | `test_whatsapp_multidevice` (9 classes) |
| Fixtures Validation | `test_fixtures_validation` |

### Padrão de Mock
- MongoDB: `MagicMock`/`AsyncMock` com respostas canônicas
- Redis: Mock com dicionário em memória
- Gemini: níveis success/retry/fail
- Serviços: injeção via substituição de `_get_database()` / mocks de coleção

---

## 11. Infraestrutura

### Docker (um grupo único)

O repo traz `docker-compose.yml` — MongoDB + Redis + WhatsApp API sobem juntos:

| Container | Imagem | Porta host | Porta interna | Uso |
|-----------|--------|-----------|----------------|-----|
| ms-automatizar-mongodb | mongo:8.0 | ${MONGO_PORT:-27017} | 27017 | Banco de dados |
| ms-automatizar-redis | redis:7.2-alpine | ${REDIS_PORT:-6379} | 6379 | Cache |
| ms-automatizar-whatsapp | aldinokemal2104/go-whatsapp-web-multidevice:v9.0.0 | ${WHATSAPP_PORT:-3001} | 3000 | API REST do WhatsApp |

- Por padrão o bind é `127.0.0.1` (`BIND_IP`); use `BIND_IP=0.0.0.0` (somente em rede privada) se precisar expor na rede local/VPN.
- Autenticação obrigatória: `MONGO_ROOT_PASSWORD`, `REDIS_PASSWORD`, `WHATSAPP_BASIC_AUTH` (definidos no `.env`).
- Dentro da rede do compose, os serviços conversam pelos nomes internos (`mongodb:27017`, `redis:6379`, `whatsapp-api:3000`).

**Subir:**
```bash
cp .env.example .env   # preencha as senhas
docker compose up -d   # sobe MongoDB + Redis + WhatsApp
docker compose ps
```

**MongoDB**: pode rodar local via Docker (banco `MS_Automatizar`). Sem dados de produção no repo — use dados fictícios/exemplos localmente.

### CI/CD
❌ **Nenhum pipeline configurado** — sem `.github/workflows/` no repo público. Testes são executados manualmente (`uv run pytest`).

---

## 12. Configuração de Ambiente

### Variáveis de Ambiente (`.env`) — modelo em `.env.example`

```env
# --- MongoDB (Docker) ---
MONGO_ROOT_USERNAME=seu_usuario
MONGO_ROOT_PASSWORD=sua_senha_forte
MONGO_PORT=27017

# --- Redis (Docker) ---
REDIS_PASSWORD=sua_senha_forte
REDIS_PORT=6379

# --- WhatsApp ---
WHATSAPP_BASIC_AUTH=seu_usuario:sua_senha_forte   # Basic Auth v8/v9 (obrigatório)
WHATSAPP_PORT=3001

# --- IA ---
KEY_API_GEMINI=...
KEY_API_MISTRAL=...

# --- MongoDB (conexão da aplicação) ---
MONGO_URI=...
MONGO_DATABASE_NAME=MS_Automatizar

# --- Zoho Mail ---
ZOHO_CLIENT_ID=...
ZOHO_CLIENT_SECRET=...
ZOHO_REFRESH_TOKEN=...
ZOHO_ACCESS_TOKEN=...
ZOHO_ACCOUNT_ID=...
ZOHO_EMAIL_FROM=...

# --- Config ---
MODO_OPERACAO=mongodb
LOG_LEVEL=INFO
ENVIO_MAX_TENTATIVAS=3
ENVIO_RETRY_DELAY_SECONDS=5
CACHE_TTL=300
```

### Comandos Úteis

```bash
# Executar o sistema
uv run python automatizar.py

# Executar comando específico
uv run python automatizar.py folha_de_ponto --help
uv run python automatizar.py holerite --help

# Testes
uv run pytest                                          # Todos os testes
uv run pytest -m unit                                  # Só unitários
uv run pytest tests/unit/services/                     # Só services
uv run pytest --cov=src --cov-report=html --cov-report=term-missing   # Com cobertura

# Infraestrutura
docker compose up -d    # grupo único: MongoDB + Redis + WhatsApp API
```

---

## 13. Gaps e Observações

### Gaps Identificados

1. **Gerenciamento de conexão** (resolvido): todos os serviços usam o pool compartilhado `MongoDBConnectionPool`. Não há mais `MongoClient` próprio.

2. **Instâncias singleton faltando**: `ContratoService`, `FuncaoService`, `HorarioService`, `FeriadoService` não têm instâncias globais no módulo (diferente dos demais).

3. **Cache TTL**: algumas leituras usam `int(os.getenv("CACHE_TTL", "300"))` localmente; `cache_keys.ttl_padrao()` centraliza esse valor.

4. **`ismaster` obsoleto**: alguns serviços usam `ismaster` para verificar conexão (depreciado no MongoDB 5+). Deveria ser `hello`.

5. **Cobertura de testes incompleta**: interface/TUI, comandos CLI diretos, ZohoMail, AnaliseAI, GrupoWhatsApp e Planilhas ainda sem testes dedicados.

6. **Sem CI/CD**: sem pipelines GitHub Actions no público. Testes manuais.

7. **Arquivos muito grandes**: `funcionario_service.py` (~1750 linhas), `empresa_service.py` (~1000 linhas), `folha_de_ponto.py` (~1700 linhas) — candidatos a refatoração.

8. **`cache_keys.py` / `data_utils.py`**: módulos utilitários presentes, mas ainda não integralmente adotados em todos os caminhos de leitura dos serviços. Migração progressiva.

### Padrões de Código

- **Idioma**: Português do Brasil (código, comentários, commits)
- **Docstrings**: Google style
- **Tipagem**: Type hints obrigatórios em todas as funções
- **SOLID**: Seguido na arquitetura de serviços
- **Commits**: `<tipo>: <descrição em português, imperativo, minúsculo, sem ponto final>`
- **Pydantic V2**: Validação antes de qualquer escrita no MongoDB
- **UV-only**: sem pip, sem `python` direto — sempre `uv run python ...`
