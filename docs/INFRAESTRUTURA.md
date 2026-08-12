# Infraestrutura MS-Automatizar

**Atualizado:** 2026-08-12
**Versão do projeto:** v0.9.8

Documentação da infraestrutura de deploy do MS-Automatizar no servidor de produção.

---

## Arquitetura de Deploy

O MS-Automatizar roda como um stack Docker Compose (arquivo `docker-compose.yml`) com 3 serviços, todos na mesma rede interna `ms-automatizar-network`:

```
┌────────────────────────────────────────────────────────────┐
│                     HOST (servidor de produção)             │
│                                                            │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────────┐ │
│  │   MongoDB    │   │    Redis     │   │  WhatsApp API    │ │
│  │   mongo:8.0  │   │ redis:7.2    │   │     (GOWA)      │ │
│  │   :27017     │   │  :6379       │   │   :3000         │ │
│  └──────┬───────┘   └──────┬───────┘   └────────┬────────┘ │
│         │                  │                    │          │
│         └────── ms-automatizar-network ─────────┘          │
│                                                            │
│  Portas publicadas (bind do IP da rede privada):           │
│   • MongoDB      → ${BIND_IP}:${MONGO_PORT:-27017}          │
│   • Redis        → ${BIND_IP}:${REDIS_PORT:-6379}           │
│   • WhatsApp API → ${BIND_IP}:${WHATSAPP_PORT:-3001}        │
└────────────────────────────────────────────────────────────┘
```

> **Nota:** os valores de porta mostrados acima são os padrões do `.env.example`. No servidor de produção, o `.env` local define as portas publicadas e o `BIND_IP` da rede privada.

---

## Serviços

| Serviço | Imagem | Porta interna | Porta host | Container |
|---------|--------|---------------|------------|-----------|
| **mongodb** | `mongo:8.0` | 27017 | `${BIND_IP}:${MONGO_PORT:-27017}` | `ms-automatizar-mongodb` |
| **redis** | `redis:7.2-alpine` | 6379 | `${BIND_IP}:${REDIS_PORT:-6379}` | `ms-automatizar-redis` |
| **whatsapp-api** | `aldinokemal2104/go-whatsapp-web-multidevice:v9.0.0` | 3000 | `${BIND_IP}:${WHATSAPP_PORT:-3001}` | `ms-automatizar-whatsapp` |

### Rede e Volumes

- **Rede:** `ms-automatizar-network` (driver bridge) — os serviços conversam pelos nomes internos (`mongodb`, `redis`, `whatsapp-api`)
- **Volumes persistentes:**
  - `mongodb_data` → `/data/db`
  - `mongodb_log` → `/var/log/mongodb`
  - `redis_data` → `/data`
  - `whatsapp_data` → `/app/storages`

---

## Acesso (rede privada)

O bind das portas é feito no **IP da rede privada** do servidor (definido via `BIND_IP` no `.env`). Por padrão o bind é `127.0.0.1` (só localhost). Para que outros computadores da rede privada/VPN acessem, defina `BIND_IP` com o IP da interface de rede privada do servidor. Isso garante que os serviços **só respondem dentro da rede privada** — computadores de fora da rede não conseguem conectar.

**Conexão de qualquer máquina da rede privada** (substitua `IP_DA_REDE_PRIVADA` pelo IP do servidor e `SEU_SERVIDOR` pelo nome de host na sua rede privada):

```bash
# MongoDB
mongosh "mongodb://usuario:SUA_SENHA@IP_DA_REDE_PRIVADA:27018/?authSource=admin"

# Redis
redis-cli -h IP_DA_REDE_PRIVADA -p 6380 -a 'SUA_SENHA'

# WhatsApp API (basic auth)
curl -u "usuario:SUA_SENHA" http://IP_DA_REDE_PRIVADA:3001/app/status
```

---

## Configuração (.env do servidor)

Criar um `.env` no diretório onde está o `docker-compose.yml` (NÃO versionar). O modelo com todas as variáveis está em `.env.example`:

```env
# IP de bind das portas — IP da rede privada do servidor (deixe vazio p/ localhost)
BIND_IP=IP_DA_REDE_PRIVADA

# MongoDB
MONGO_ROOT_USERNAME=usuario
MONGO_ROOT_PASSWORD=SUA_SENHA
MONGO_PORT=27018

# Redis
REDIS_PASSWORD=SUA_SENHA
REDIS_PORT=6380

# WhatsApp API
WHATSAPP_BASIC_AUTH=usuario:SUA_SENHA
WHATSAPP_PORT=3001
```

---

## Configuração do Projeto (.env local, quem consome)

Quem consome a API (por exemplo, a aplicação rodando em outra máquina da rede privada) usa:

```env
MONGO_URI="mongodb://usuario:SUA_SENHA@IP_DA_REDE_PRIVADA:27018/?authSource=admin"
MONGO_DATABASE_NAME="MS_Automatizar"
MODO_OPERACAO="mongodb"

REDIS_HOST="IP_DA_REDE_PRIVADA"
REDIS_PORT="6380"
REDIS_PASSWORD="SUA_SENHA"
REDIS_ENABLED="true"

WHATSAPP_API_URL="http://IP_DA_REDE_PRIVADA:3001"
WHATSAPP_API_KEY=""
```

---

## Subir / Gerenciar

> ⚠️ **Workaround do kernel (importante):** o serviço `mongodb` do compose inclui a env var `GLIBC_TUNABLES=glibc.pthread.rseq=1`, **obrigatória** para o MongoDB 8.x subir em kernels Linux 6.19–7.0.13 (incompatibilidade TCMalloc × RSEQ — JIRA SERVER-121912). NÃO remova essa linha do compose, senão o mongo falha ao iniciar.

```bash
cd ~/ms_automatizar
docker compose up -d          # subir tudo
docker compose ps             # status
docker compose logs -f        # logs em tempo real
docker compose logs mongodb   # log de um serviço
docker compose down           # parar (mantém volumes)
```

---

## Banco de Dados

### Restauração de Backup

O dump (formato `mongodump`) fica em `backup_mongo/MS_Automatizar/` no repositório.

```bash
mongorestore --uri="mongodb://usuario:SUA_SENHA@IP_DA_REDE_PRIVADA:27018/?authSource=admin" \
  --db=MS_Automatizar \
  --drop \
  backup_mongo/MS_Automatizar
```

> ⚠️ O dump de produção contém **dados pessoais** (CPFs, PIS). Não publique backups reais — mantenha-os fora do repositório ou em versão anonimizada/descartável.

### Coleções

| Coleção | Descrição |
|---------|-----------|
| funcionarios | Funcionários |
| folha_de_ponto | Folhas de ponto |
| grupos_whatsapp | Cache de grupos |
| envios_folhas_de_ponto | Registro de envios |
| cache_ocr | Cache OCR |
| diretorios | Diretórios |
| contratos | Contratos |
| funcoes | Funções/cargos |
| holerites | Holerites |
| horarios | Horários |
| feriados | Feriados |
| templates_mensagens | Templates |
| empresas | Empresas |
| contatos_funcionarios | Contatos |
| envios_holerites | Envios holerites |

---

## WhatsApp API — go-whatsapp-web-multidevice (GOWA)

**Versão atual no deploy:** v9.0.0 (imagem `aldinokemal2104/go-whatsapp-web-multidevice:v9.0.0`).

A atualização v8 → v9 já foi aplicada — ver [UPGRADE_GOWA_9.md](UPGRADE_GOWA_9.md) com a análise completa das mudanças v8 → v9 e os ajustes feitos no código. Na v9 o dashboard embutido foi removido (gowa-ui baixado em runtime); no deploy puro de API usamos `APP_UI_ENABLED=false` e `APP_UI_AUTO_UPDATE=false`.

O pareamento do WhatsApp é feito pelo dashboard em `http://IP_DA_REDE_PRIVADA:3001` (login com `WHATSAPP_BASIC_AUTH`) ou via API.

### Estado esperado no primeiro boot

```
[DEVICE_MANAGER] discovered 0 device records
auto-connect skipped: no devices available   ← NORMAL: nenhum número pareado ainda
```

Depois de parear um número, o device aparece e os envios passam a funcionar.
