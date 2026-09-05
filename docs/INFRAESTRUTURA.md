# Infraestrutura MS-Automatizar

**Atualizado:** 2026-08-01
**Versão do projeto:** v0.9.8

Documentação da infraestrutura de deploy do MS-Automatizar no servidor (`servidor-ubuntu-home`).

---

## Arquitetura de Deploy

O MS-Automatizar roda como um stack Docker Compose com 3 serviços, todos na mesma rede interna `ms-automatizar-network`:

```
┌────────────────────────────────────────────────────────────┐
│                    HOST (servidor-ubuntu-home)              │
│                                                            │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────────┐ │
│  │   MongoDB    │   │    Redis     │   │  WhatsApp API    │ │
│  │   mongo:8.0  │   │ redis:7.2    │   │     (GOWA)      │ │
│  │   :27017     │   │  :6379       │   │   :3000         │ │
│  └──────┬───────┘   └──────┬───────┘   └────────┬────────┘ │
│         │                  │                    │          │
│         └────── ms-automatizar-network ─────────┘          │
│                                                            │
│  Portas publicadas (bind Tailscale 100.82.203.59):         │
│   • MongoDB      → 100.82.203.59:27018                     │
│   • Redis        → 100.82.203.59:6380                      │
│   • WhatsApp API → 100.82.203.59:3001                      │
└────────────────────────────────────────────────────────────┘
```

---

## Serviços

| Serviço | Imagem | Porta interna | Porta host | Container |
|---------|--------|---------------|------------|-----------|
| **mongodb** | `mongo:8.0` | 27017 | `100.82.203.59:27018` | `ms-automatizar-mongodb` |
| **redis** | `redis:7.2-alpine` | 6379 | `100.82.203.59:6380` | `ms-automatizar-redis` |
| **whatsapp-api** | `aldinokemal2104/go-whatsapp-web-multidevice:v9.0.0` | 3000 | `100.82.203.59:3001` | `ms-automatizar-whatsapp` |

### Rede e Volumes

- **Rede:** `ms-automatizar-network` (driver bridge) — os serviços conversam pelos nomes internos (`mongodb`, `redis`, `whatsapp-api`)
- **Volumes persistentes:**
  - `mongodb_data` → `/data/db`
  - `mongodb_log` → `/var/log/mongodb`
  - `redis_data` → `/data`
  - `whatsapp_data` → `/app/storages`

---

## Acesso (Tailscale)

O bind das portas é feito no **IP Tailscale do servidor** (`100.82.203.59` via `BIND_IP` no `.env`). Isso garante que os serviços **só respondem dentro da rede Tailscale** — computadores de fora da tailnet não conseguem conectar.

**Conexão de qualquer PC da tailnet** (via MagicDNS `servidor-ubuntu-home.tail2f0857.ts.net`):

```bash
# MongoDB
mongosh "mongodb://alefsander:***@servidor-ubuntu-home.tail2f0857.ts.net:27018/?authSource=admin"

# Redis
redis-cli -h servidor-ubuntu-home.tail2f0857.ts.net -p 6380 -a 'SUA_SENHA'

# WhatsApp API (basic auth)
curl -u "alefsander:SUA_SENHA" http://servidor-ubuntu-home.tail2f0857.ts.net:3001/app/status
```

---

## Configuração (.env do servidor)

Criar `~/ms_automatizar/.env` (NÃO versionar):

```env
BIND_IP=100.82.203.59

# MongoDB
MONGO_ROOT_USERNAME=alefsander
MONGO_ROOT_PASSWORD=SUA_SENHA
MONGO_PORT=27018

# Redis
REDIS_PASSWORD=SUA_SENHA
REDIS_PORT=6380

# WhatsApp API
WHATSAPP_BASIC_AUTH=alefsander:SUA_SENHA
WHATSAPP_PORT=3001
```

---

## Configuração do Projeto (.env local, quem consome)

```env
MONGO_URI="mongodb://alefsander:***@servidor-ubuntu-home.tail2f0857.ts.net:27018/?authSource=admin"
MONGO_DATABASE_NAME="MS_Automatizar"
MODO_OPERACAO="mongodb"

REDIS_HOST="servidor-ubuntu-home.tail2f0857.ts.net"
REDIS_PORT="6380"
REDIS_PASSWORD="SUA_SENHA"
REDIS_ENABLED="true"

WHATSAPP_API_URL="http://servidor-ubuntu-home.tail2f0857.ts.net:3001"
WHATSAPP_API_KEY=""
```

---

## Subir / Gerenciar

> ⚠️ **Workaround do kernel (importante):** o serviço `mongodb` do compose inclui a env var `GLIBC_TUNABLES=glibc.pthread.rseq=1`, **obrigatória** para o MongoDB 8.x subir em kernels Linux 6.19–7.0.13 (incompatibilidade TCMalloc × RSEQ — JIRA SERVER-121912). NÃO remova essa linha do compose, senão o mongo falha ao iniciar.

```bash
cd ~/ms_automatizar
sudo docker compose up -d          # subir tudo
sudo docker compose ps             # status
sudo docker compose logs -f        # logs em tempo real
sudo docker compose logs mongodb   # log de um serviço
sudo docker compose down           # parar (mantém volumes)
```

---

## Banco de Dados

### Restauração de Backup

O dump (formato `mongodump`) fica em `backup_mongo/MS_Automatizar/` no repositório.

```bash
mongorestore --uri="mongodb://alefsander:***@100.82.203.59:27018/?authSource=admin" \
  --db=MS_Automatizar \
  --drop \
  backup_mongo/MS_Automatizar
```

### Coleções

| Coleção | Docs | Descrição |
|---------|------|-----------|
| funcionarios | 580 | Funcionários |
| folha_de_ponto | 4.691 | Folhas de ponto |
| grupos_whatsapp | 226 | Cache de grupos |
| envios_folhas_de_ponto | 208 | Registro de envios |
| cache_ocr | 552 | Cache OCR |
| diretorios | 57 | Diretórios |
| contratos | 39 | Contratos |
| funcoes | 34 | Funções/cargos |
| holerites | 27 | Holerites |
| horarios | 26 | Horários |
| feriados | 17 | Feriados |
| templates_mensagens | 6 | Templates |
| empresas | 3 | Empresas |
| contatos_funcionarios | 0 | Contatos |
| envios_holerites | 0 | Envios holerites |

⚠️ Contém **dados pessoais** (CPFs, PIS). Repositório deve ser privado.

---

## WhatsApp API — go-whatsapp-web-multidevice (GOWA)

**Versão atual no deploy:** v9.0.0 (imagem `aldinokemal2104/go-whatsapp-web-multidevice:v9.0.0`).

A atualização v8 → v9 já foi aplicada — ver [UPGRADE_GOWA_9.md](UPGRADE_GOWA_9.md) com a análise completa das mudanças v8 → v9 e os ajustes feitos no código. Na v9 o dashboard embutido foi removido (gowa-ui baixado em runtime); no deploy puro de API usamos `APP_UI_ENABLED=false` e `APP_UI_AUTO_UPDATE=false`.

O pareamento do WhatsApp é feito pelo dashboard em `http://100.82.203.59:3001` (login com `WHATSAPP_BASIC_AUTH`) ou via API.

### Estado esperado no primeiro boot

```
[DEVICE_MANAGER] discovered 0 device records
auto-connect skipped: no devices available   ← NORMAL: nenhum número pareado ainda
```

Depois de parear um número, o device aparece e os envios passam a funcionar.
