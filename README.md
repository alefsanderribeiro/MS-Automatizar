# MS-Automatizar

Automação administrativa com inteligência artificial: geração e análise de **folhas de ponto** e **holerites**, **OCR** de documentos manuscritos, **renomeação automática de arquivos**, integração com **MongoDB**, **e-mail (Zoho)** e **WhatsApp (multidevice)**.

> ⚙️ Projeto em desenvolvimento (v0.9.8). Foco em ambiente Windows, com suporte parcial a Linux.

---

## ✨ Funcionalidades

- **Geração de Folhas de Ponto** — a partir de dados em MongoDB, com renderização HTML → PDF.
- **Processamento de Holerites** — leitura/renomeação de PDFs de holerites de forma automatizada.
- **OCR + IA** — análise de documentos manuscritos (PDFs/imagens) usando Google Gemini / Mistral.
- **Cache OCR** — cache de resultados no MongoDB para evitar reprocessamento.
- **Envio automático** — distribuição de folhas e holerites por **e-mail (Zoho Mail)** e **WhatsApp** (individuais e grupos).
- **Persistência MongoDB** — modelos Pydantic + serviços modulares.
- **Interface interativa** (CLI/TUI) para gerenciar empresas, funcionários, folhas e holerites.

---

## 🛠️ Stack

| Camada      | Tecnologia |
|-------------|------------|
| Linguagem    | Python 3.12+ (Type Hints) |
| Modelagem    | Pydantic v2 |
| Banco        | MongoDB (PyMongo) |
| Cache        | Redis (opcional) / memória |
| OCR / IA     | Google Gemini, Mistral AI, pypdfium2 |
| PDF          | WeasyPrint, PyPDF2 |
| Planilhas    | pandas, openpyxl |
| UI           | rich, questionary |
| Gerenciador  | `uv` |

---

## 🚀 Como rodar

### Pré-requisitos

- Python 3.12 ou superior
- [uv](https://docs.astral.sh/uv/) (recomendado)
- MongoDB (local ou remoto) — veja a seção Infraestrutura
- (Opcional) Redis
- (Opcional) WhatsApp API via Docker (`aldinokemal/go-whatsapp-web-multidevice`)

### Instalação

```bash
# 1. Clonar o repositório
git clone https://github.com/alefsanderribeiro/MS-Automatizar.git
cd MS-Automatizar

# 2. Instalar dependências com uv
uv sync

# 3. Configurar variáveis de ambiente
cp .env_exemplo .env   # crie o seu com base nas váriaveis abaixo
```

> O repositório público **não** inclui arquivos de exemplo de segredos — as variáveis necessárias estão documentadas em `src/utils/env_validator.py` e no `docs/`.

### Variáveis de Ambiente (`.env`)

```ini
# IA
KEY_API_GEMINI=               # opcional (Google Gemini)
KEY_API_MISTRAL=              # opcional (Mistral AI)

# MongoDB
MONGO_URI=mongodb://localhost:27017
MONGO_DATABASE_NAME=MS_Automatizar

# Redis (opcional)
REDIS_ENABLED=true
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# Zoho Mail (envio de e-mail)
ZOHO_CLIENT_ID=
ZOHO_CLIENT_SECRET=
ZOHO_REFRESH_TOKEN=

# WhatsApp API (Docker go-whatsapp-web-multidevice)
WHATSAPP_API_URL=http://localhost:3000
WHATSAPP_API_KEY=
WHATSAPP_BASIC_AUTH=
```

### Uso

```bash
# Interface interativa (CLI/TUI)
python -m automatizar

# Geração de folhas de ponto (MongoDB → PDF)
python -m automatizar folha ...
```

---

## 🚀 Rodando com Docker

Suba **MongoDB 8.0**, **Redis 7.2** e a **WhatsApp API v9** (go-whatsapp-web-multidevice) de uma vez, com volumes persistentes, usando o `docker-compose.yml` na raiz do repositório.

### Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/) (incluso no Docker Desktop)

### Passo a passo

```bash
# 1. Clonar o repositório (se ainda não fez)
git clone https://github.com/alefsanderribeiro/MS-Automatizar.git
cd MS-Automatizar

# 2. Criar o .env a partir do exemplo e editar as SENHAS
cp .env.example .env
nano .env   # defina MONGO_ROOT_PASSWORD, REDIS_PASSWORD e WHATSAPP_BASIC_AUTH

# 3. Subir a infraestrutura (MongoDB + Redis + WhatsApp API)
docker compose up -d

# 4. Conferir os serviços
docker compose ps
```

> ⚠️ As variáveis obrigatórias (`MONGO_ROOT_PASSWORD`, `REDIS_PASSWORD`, `WHATSAPP_BASIC_AUTH`) são **exigidas** pelo compose — os serviços não sobem sem elas.

### O que sobe

| Serviço         | Imagem                                        | Porta interna | Uso                                    |
|-----------------|-----------------------------------------------|---------------|----------------------------------------|
| `mongodb`       | `mongo:8.0`                                   | `27017`       | Banco de dados principal               |
| `redis`         | `redis:7.2-alpine`                            | `6379`        | Cache                                  |
| `whatsapp-api`  | `aldinokemal2104/go-whatsapp-web-multidevice:v9.0.0` | `3000` | API de WhatsApp (multidevice)          |

### Volumes persistentes

Os dados persistem entre restarts (named volumes com `driver: local`):

- `mongodb_data` — dados do MongoDB (`/data/db`)
- `mongodb_log` — logs do MongoDB (`/var/log/mongodb`)
- `redis_data` — dados do Redis (`/data`)
- `whatsapp_data` — storages da WhatsApp API (`/app/storages`)

### Healthchecks e logs

- **Verificar saúde:** `docker compose ps` mostra o estado de cada container.
- **Logs em tempo real:** `docker compose logs -f` (ou `docker compose logs -f whatsapp-api`).
- **Parar sem apagar dados:** `docker compose down` mantém os volumes; use `docker compose down -v` apenas se quiser apagar tudo.

### Endpoints da WhatsApp API

- `GET /health` — endpoint **público** (usado pelo healthcheck, sem autenticação).
- Demais endpoints exigem **Basic Auth** (o `WHATSAPP_BASIC_AUTH` em formato `usuario:senha`).

### Como o app usa essas infras

O app Python conecta aos serviços via variáveis do `.env` do projeto:

```ini
MONGO_URI=mongodb://usuario:senha@localhost:27017/MS_Automatizar?authSource=admin
REDIS_HOST=localhost
WHATSAPP_API_URL=http://localhost:3001
```

Se os containers rodarem na mesma máquina, use `localhost` + a porta host definida no `.env` da infra (`MONGO_PORT`, `REDIS_PORT`, `WHATSAPP_PORT`).

### Referência

- Documentação do [go-whatsapp-web-multidevice](https://github.com/aldinokemal2104/go-whatsapp-web-multidevice)



---

## 🚀 Funcionalidades em Detalhe

### 1. Geração de Folhas de Ponto
- Criação automatizada de folhas de ponto para funcionários
- Preenchimento inteligente de dados (nome, departamento, cargo, horário)
- Cálculo automático de dias úteis e feriados
- Filtros avançados: por ID, nome, lotação ou contrato
- Interface CLI e modo interativo
- Processamento de PDFs manuscritos com IA (Gemini 2.5 Pro)
- Extração estruturada de dados com validação Pydantic
- Armazenamento completo em MongoDB com relacionamentos

**Comandos disponíveis:**
```bash
# Criar folhas de ponto (MongoDB → PDF)
uv run python automatizar.py folha_de_ponto criar --data YYYY-MM-DD --nome_funcionario "Nome" --diretorio_destino "Diretório do Destino"

# Filtrar por ID
uv run python automatizar.py folha_de_ponto criar --id_funcionario 1,2,3

# Filtrar por lotação
uv run python automatizar.py folha_de_ponto criar --lotacao "Departamento A"

# Gerar DataFrame com dados
uv run python automatizar.py folha_de_ponto gerar_dataframe --diretorio_destino "caminho"

# Analisar folha existente
uv run python automatizar.py folha_de_ponto análise --arquivo "caminho/arquivo.xlsx"

# Processar e salvar em MongoDB (todos os ativos)
uv run python automatizar.py folha_de_ponto mongodb --data YYYY-MM-DD

# Criar folha a partir do MongoDB usando IDs específicos
uv run python automatizar.py folha_de_ponto criar_mongodb_id --funcionario_id <ObjectId> --empresa_id <ObjectId> --data YYYY-MM-DD

# Criar folhas a partir do MongoDB usando filtros
uv run python automatizar.py folha_de_ponto criar_mongodb_filtro --lotacao "Departamento A" --data YYYY-MM-DD

# Processar PDFs manuscritos com IA (diretório ou arquivo único)
uv run python automatizar.py folha_de_ponto processar_pdf --diretorio "diretorio_com_pdfs"
uv run python automatizar.py folha_de_ponto processar_pdf --arquivo "folha.pdf"
uv run python automatizar.py folha_de_ponto processar_pdf --arquivos "folha1.pdf,folha2.pdf"
```

### 2. Geração de Folhas de Ponto em HTML *(Novo em v0.9.8)*

O sistema suporta geração de folhas de ponto no formato HTML.

**Características do formato HTML:**
- Layout fiel ao modelo institucional da empresa
- Cabeçalho completo: ID da Folha, Período, Empresa, Atividade, CNPJ, Endereço, Funcionário, CPF, Lotação, Cargo e Horário
- Tabela de frequência com colunas de Início, Intervalo, Término e Assinatura/Observações
- Suporte a até 31 linhas de lançamento
- Estilo compatível com impressão direta pelo navegador (sem necessidade de Excel ou conversores externos)
- Charset UTF-8 com suporte completo ao português

```python
from src.folha_de_ponto import Folha_de_Ponto

fp = Folha_de_Ponto()

# Gerar folha em HTML
resultado = fp.criar_mongodb_por_id(
    funcionario_id="<ObjectId>",
    empresa_id="<ObjectId>",
    data=date(2026, 5, 1),
    diretorio_destino=Path("saida/"),
)
```

### 3. Processamento de Holerites
- Renomeação automática de holerites para o nome do funcionário
- Extração inteligente de informações via OCR/AI
- Extração completa de dados com Gemini AI (nome, CPF, salário, proventos, descontos)
- Envio automatizado por E-mail e WhatsApp
- Dois modos de envio: via planilha ou via MongoDB
- Autocadastro de funcionários durante processamento
- Cache OCR com MongoDB para otimização
- Filtro por período (mês e ano)
- Processamento em lote com threads para maior performance
- Estatísticas de cache e limpeza de dados antigos

**Comandos disponíveis:**
```bash
# Renomear holerites de um diretório
uv run python automatizar.py holerite renomear_arquivos --diretório "caminho"

# Filtrar por mês/ano
uv run python automatizar.py holerite renomear_arquivos --diretório "caminho" --mês_ano "01.2025"

# Processar PDFs com Gemini AI
uv run python automatizar.py holerite processar_pdfs --caminho "diretorio_ou_arquivo.pdf"

# Enviar holerites via MongoDB
uv run python automatizar.py holerite enviar --competencia "01/2025" --modo mongodb

# Enviar via planilha (com simulação)
uv run python automatizar.py holerite enviar --competencia "01/2025" --modo planilha --dry_run

# Listar holerites no MongoDB
uv run python automatizar.py holerite listar --competencia "01/2025" --limite 50

# Ver estatísticas
uv run python automatizar.py holerite stats --competencia "01/2025"
```

### 4. Serviços de IA e OCR

#### GeminiService (Google Generative AI)
- Modelo padrão: `gemini-2.5-pro` (configurável via `model=` no construtor)
- **Structured Output**: Extração de dados validados com schemas Pydantic
- Processamento de imagens com visão computacional
- Análise de documentos (PDF, HTML, XML, CSV)
- Processamento de documentos na internet
- File API para arquivos >20MB
- Configuração flexível de parâmetros com temperature ajustável

```python
from src.services.analise_ai_service import GeminiService
from pydantic import BaseModel
from typing import List

gemini = GeminiService()

# Extrair texto de imagem
nome = gemini.imagem("foto.jpg", "Extrai o nome completo da pessoa")

# Analisar documento
resultado = gemini.documento(Path("documento.pdf"), "Sumarize o conteúdo")

# Structured Output com validação Pydantic
class Pessoa(BaseModel):
    nome: str
    idade: int
    cidades: List[str]

resultado_json = gemini.documento_estruturado(
    Path("curriculo.pdf"),
    "Extraia dados da pessoa",
    schema_pydantic=Pessoa
)
```

#### MistralService (Mistral AI OCR)
- Modelos: `mistral-ocr-2512` (OCR) e `mistral-small-2506` (IA)
- OCR de alta precisão com IA integrada
- Upload e processamento de documentos
- Análise inteligente de imagens
- Suporte a múltiplos formatos

```python
from src.services.analise_ai_service import MistralService

mistral = MistralService()

# OCR com análise
texto = mistral.imagem("documento.jpg", "Qual é o valor total?")

# Processar documentos
mistral.documento(Path("holerite.pdf"), "Extrai o valor bruto de salário")
```

### 5. Sistema de Cache OCR com MongoDB
- Armazenamento de resultados OCR para evitar reprocessamento
- Hash SHA256 para identificação de imagens duplicadas
- Rastreamento de data/hora e metadados
- Estatísticas e gerenciamento de cache
- Limpeza automática de dados antigos

### 6. Persistência MongoDB com Modelos Pydantic
- **Modelos estruturados**: Funcionário, Empresa, Folha de Ponto
- **Validação automática**: Pydantic V2 com validadores customizados
- **Relacionamentos**: ObjectId references entre coleções (N:N)
- **Autocadastro inteligente**: Criação automática de registros incompletos
- **Serviços especializados**: FuncionarioService, EmpresaService, FolhaDePontoService
- **Busca fuzzy**: Matching inteligente de nomes com normalização Unicode
- **Índices otimizados**: Unique constraints e performance queries
- **Histórico de alterações**: Tracking completo de mudanças

### 7. Processador de Folhas de Ponto com IA
- **Pipeline completo**: Validação → Extração IA → Lookup → Armazenamento
- **Análise manuscrita**: Leitura de folhas preenchidas à mão com Gemini 2.5 Pro
- **Retry inteligente**: Até 3 tentativas com temperatura ajustável
- **Autocadastro**: Funcionários e empresas criados automaticamente se não existirem
- **Totalizações automáticas**: Cálculo de horas trabalhadas, faltas, feriados
- **Métricas detalhadas**: Tempo de processamento por etapa, tokens utilizados
- **Sanitização de dados**: Limpeza e normalização de entradas do PDF

---

## 🖥️ Uso (Interface e CLI)

### Interface Interativa

```bash
uv run python automatizar.py
```

**Menu Principal:**
```
? Selecione uma opção: (Use setas ↑↓)
❯ Operações com Folha de Ponto
  Operações com Holerite
  ─────────────────
  Gerenciar Dados
    ❯ Funcionários
      Empresas
      Referências (Funções, Horários, etc.)
  Configurações
  Sair
```

### Linha de Comando (CLI)

```bash
# Folhas de Ponto
uv run python automatizar.py folha_de_ponto --help

# Holerites
uv run python automatizar.py holerite --help

# Referências (contratos, horários, funções)
uv run python automatizar.py referencias --help

# Diretórios
uv run python automatizar.py diretorios --help
```

---

## 🗄️ Serviços e Modelos (exemplos)

### Funcionários

```python
from src.services import funcionario_service
from src.models.funcionario_models import FuncionarioBuilder

# Buscar por nome (retorna lista de todos com o mesmo nome normalizado)
funcionarios = funcionario_service.buscar_todos_por_nome("João Silva")

# Criar funcionário completo
funcionario = (
    FuncionarioBuilder()
    .set_identificacao(nome="João Silva", cpf="123.456.789-00")
    .set_contratacao(lotacao="TI")
    .build()
)
funcionario_service.criar_funcionario(funcionario.model_dump())
```

### Empresas

```python
from src.services import empresa_service
from src.models.empresa_models import EmpresaBuilder

empresa = (
    EmpresaBuilder()
    .set_nome("Empresa ABC")
    .set_cnpj("12.345.678/0001-90")
    .build()
)
empresa_service.criar_empresa(empresa.model_dump())
```

### Folhas de Ponto

```python
from src.folha_de_ponto import Folha_de_Ponto
from datetime import date
from pathlib import Path

fp = Folha_de_Ponto()

# Gerar folha em PDF/HTML (via template HTML → WeasyPrint)
resultado = fp.criar_mongodb_por_id(
    funcionario_id="<ObjectId>",
    empresa_id="<ObjectId>",
    data=date(2026, 5, 1),
    diretorio_destino=Path("saida/")
)
```

### Utilitários MongoDB

```python
from src.services.mongodb_utils import (
    buscar_nome_funcao,
    buscar_nome_horario,
    buscar_nome_contrato,
    buscar_funcionario,
    buscar_empresa,
    buscar_folha_existente,
    listar_funcionarios_por_filtro,
)

# Buscar dados relacionados por ObjectId
funcao_nome = buscar_nome_funcao("507f1f77bcf86cd799439011")
funcionario = buscar_funcionario("507f1f77bcf86cd799439011")
folha = buscar_folha_existente(
    funcionario_id="...",
    empresa_id="...",
    mes_referencia="2026-05"
)
```

---

## 🗄️ Cache Híbrido (Redis + Memória)

```python
from src.services.cache_service import cache_service

cache_service.set("empresa:123", dados_empresa, ttl=300)
cache_service.get("empresa:123")
cache_service.invalidate("empresas:*")
cache_service.set_many({"key1": val1, "key2": val2})
resultados = cache_service.get_many(["key1", "key2"])
```

---

## 📋 Observações Importantes

1. **PDF → imagem**: Usa `pypdfium2` (embutido, cross-platform) — Poppler **não** é necessário
2. **APIs Requerem Internet**: Google Gemini e Mistral AI precisam de conexão
3. **Credenciais Seguras**: Nunca commitar arquivo `.env` com chaves de API
4. **MongoDB Recomendado**: Funcionalidades completas requerem MongoDB configurado
5. **Geração de PDF independente**: HTML → PDF usa WeasyPrint — não requer Excel ou Poppler
6. **Pydantic V2**: Projeto usa Pydantic V2 — não compatível com V1
7. **Gemini 2.5 Pro**: Modelo premium com melhor capacidade de leitura manuscrita

---

## 🧰 Troubleshooting

- **"Chave de API inválida"** → Verifique se as chaves estão corretas no [Google AI Studio](https://aistudio.google.com) ou [Mistral Console](https://console.mistral.ai).
- **"MongoDB não conecta"** → Verifique se o MongoDB está rodando e a URI em `.env`.
- **"Pydantic validation error"** → Certifique-se de usar Pydantic V2 (`pip show pydantic`).
- **Erro ao processar PDFs manuscritos** → Verifique a qualidade do PDF (DPI mínimo 150) e os logs em `logs/`.
- **Lentidão no processamento** → Aumente os workers, use o cache OCR (MongoDB) e verifique limites de API.

---

## 🤝 Contribuindo

1. **Fork** o projeto
2. **Crie uma branch** para sua feature
3. **Commit** suas mudanças
4. **Push** para a branch
5. **Abra um Pull Request**

### Diretrizes
- Manter compatibilidade com Python 3.12+
- Adicionar testes para novas funcionalidades
- Atualizar documentação
- Seguir PEP 8 para estilo de código
- Atualizar CHANGELOG


---

## 📁 Estrutura do Projeto

```
src/
├── comandos/        # interface de linha de comando (CLI)
├── config/          # configurações (URLs, etc.)
├── interface/       # interface interativa (rich/questionary)
├── models/          # modelos Pydantic (funcionários, empresas, folhas, holerites...)
├── processadores/   # orquestradores e processadores de envio
├── services/        # serviços (MongoDB, WhatsApp, Zoho, folha, holerite, IA...)
├── templates/       # templates HTML (folha de ponto)
└── utils/           # utilitários (logger, validação, PDF, retry, telefone...)
tests/               # testes unitários (pytest + fixtures)
specs/               # especificações técnicas (folha de ponto, holerite)
docs/                # documentação de uso
```

---

## 🧪 Testes

```bash
uv run pytest
```

---

## 📄 Licença

Distribuído sob a licença MIT. Veja [LICENSE](./LICENSE) para mais detalhes.
