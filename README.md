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
