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
