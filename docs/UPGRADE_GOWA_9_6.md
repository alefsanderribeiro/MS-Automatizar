# Upgrade GOWA v9.0.0 → v9.6.0 + subdomínio gowa.alefsander.dev

**Data:** 2026-10-07
**Status:** ✅ Arquivos ajustados (aplicação no servidor feita pelo Alef)

Upgrade do **go-whatsapp-web-multidevice (GOWA)** da **v9.0.0** (deploy atual) para a **v9.6.0**, e exposição da API no subdomínio **https://gowa.alefsander.dev** — acessível **somente pela rede Tailscale**.

Repositório: https://github.com/aldinokemal/go-whatsapp-web-multidevice

---

## 1. Mudanças v9.0.0 → v9.6.0

### 🔴 Breaking changes: NENHUMA para consumidores HTTP

O único breaking da série v9 ficou na **v9.0/v9.1** (já tratado no [UPGRADE_GOWA_9.md](UPGRADE_GOWA_9.md)):

- **v9.1** — o MCP passou a rodar dentro do `rest` (comando `mcp` removido); MCP em `http://<host>:<port>/mcp`, protegido pelo mesmo Basic Auth. Não usamos MCP.
- **v9.0** — dashboard embutido removido (gowa-ui baixado em runtime). Já usamos `APP_UI_ENABLED=false` + `APP_UI_AUTO_UPDATE=false`.

Da **v9.1 → v9.6** não há breaking changes para quem consome a API HTTP.

### ✅ Endpoints usados pelo `whatsapp_service.py` — todos preservados

Confirmado contra a OpenAPI da **v9.6.0** (`docs/openapi.yaml`):

| Endpoint | v9.6.0 | Uso |
|----------|--------|-----|
| `POST /send/file` | ✅ | envio de folhas/holerites (PDF) |
| `POST /send/message` | ✅ | envio de texto |
| `GET /user/my/groups` | ✅ | listar grupos |
| `GET /devices` | ✅ | listar dispositivos (multidevice) |
| `GET /app/status` | ✅ | status (exige `X-Device-Id`/`device_id`) |
| `GET /app/info` | ✅ | metadados (versão, limites) |
| `GET /app/login` | ✅ | QR (v9) |
| `GET /health` | ✅ | healthcheck público (sem auth) |

Header `X-Device-Id` e Basic Auth (`APP_BASIC_AUTH`) seguem iguais. Envelope de resposta `results` inalterado.

### ✨ Novidades relevantes (opcionais — nada quebra)

| Versão | Recurso |
|--------|---------|
| **v9.2** | HD em foto/vídeo (`hd=true`); OAuth 2.1 embutido no MCP (`MCP_OAUTH_ENABLED=false` por padrão) |
| **v9.3** | download de mídia de newsletter; votos de enquete em webhooks; recibo de áudio tocado |
| **v9.4** | histórico de chat sob demanda; webhook por device pode somar aos globais; ignorar mídia de status |
| **v9.5** | **agendamento/repetição de envios** (`scheduled_at`, `timezone`, `recurrence`); menções em legendas de imagem/arquivo/vídeo |
| **v9.6** | contexto de resposta no histórico; status reshareable; link rico em edição; **fix do QR expirado**; fix WhatsApp Business; fix contatos iPhone |

### ⚠️ Atenção no upgrade

- A v9.5 adiciona a tabela `scheduled_sends` e a série v9 inclui **migrations SQLite internas**. O banco vive no volume `ms-automatizar-whatsapp-data` (`/app/storages`), onde também ficam as **sessões pareadas dos 2 devices**.
- **Antes de subir:** fazer backup do volume (ver comandos de deploy). O upgrade é in-place; sem backup, uma migration mal-sucedida pode exigir re-pareamento dos números.

---

## 2. Subdomínio `gowa.alefsander.dev` (SOMENTE via Tailscale)

Padrão idêntico ao de `vault/health/metrics/pdf/atelie/finance.alefsander.dev`: DNS-only apontando para o IP Tailscale + Caddy compartilhado.

```
Cliente na tailnet
   │  DNS: gowa.alefsander.dev → A (DNS-only, nuvem cinza) = 100.82.203.59
   ▼
Caddy (container caddy-proxy-tailscale, do ~/vaultwarden)
   │  reverse_proxy ms-automatizar-whatsapp:3000   (rede vaultwarden_tailscale-net)
   ▼
ms-automatizar-whatsapp (GOWA v9.6.0) :3000
```

### Componentes alterados

1. **Cloudflare (DNS)** — criar A record `gowa` → `100.82.203.59`, **DNS-only** (nuvem cinza). Não usar proxy: o IP Tailscale não é alcançável pela internet.
2. **Caddyfile** (`~/vaultwarden/Caddyfile`) — novo bloco:
   ```caddy
   gowa.alefsander.dev {
       reverse_proxy ms-automatizar-whatsapp:3000
       tls {
           dns cloudflare {env.CF_API_TOKEN}
       }
   }
   ```
3. **Compose** (`~/ms_automatizar/docker-compose.ms-automatizar.yml`) — o serviço `whatsapp-api` entra também na rede externa `vaultwarden_tailscale-net`:
   ```yaml
   networks:
     - ms-automatizar-network
     - vaultwarden_tailscale-net
   ...
   networks:
     vaultwarden_tailscale-net:
       external: true
   ```

### Por que funciona

- O Caddy só enxerga containers na sua rede (`vaultwarden_tailscale-net`). Por isso o `whatsapp-api` foi conectado a ela (além da rede própria `ms-automatizar-network`).
- O nome `ms-automatizar-whatsapp` é o `container_name`, que o DNS embutido do Docker resolve dentro da rede.
- O DNS-only faz `gowa.alefsander.dev` resolver para `100.82.203.59` — que **só existe na tailnet**. Fora dela, o nome resolve mas o IP é inalcançável.

---

## 3. Segurança

- A exposição é **dupla**: só quem está na tailnet alcança o IP, e o GOWA continua exigindo **Basic Auth** (`APP_BASIC_AUTH`).
- **Nunca** usar Cloudflare proxied (nuvem laranja) para este subdomínio.
- O QR de pareamento pode ser obtido via `https://gowa.alefsander.dev/app/login` (Basic Auth) — mesmo mecanismo de antes, agora com TLS válido.

---

## 4. Validação pós-deploy

```bash
# 1) API responde na porta Tailscale
curl -s -u "USUARIO:SENHA" http://100.82.203.59:3001/app/info

# 2) Resolve dentro da tailnet
getent hosts gowa.alefsander.dev      # deve retornar 100.82.203.59

# 3) HTTPS via Caddy (de qualquer PC da tailnet)
curl -s -u "USUARIO:SENHA" https://gowa.alefsander.dev/app/info

# 4) Devices pareados preservados
curl -s -u "USUARIO:SENHA" https://gowa.alefsander.dev/devices
```

Esperado: `version` = `v9.6.0`, os 2 devices (`WhatsApp-MS`, `WhatsApp-MD`) ainda `logged_in`.

---

## 5. Rollback

Se algo falhar, voltar a imagem para `:v9.0.0` no compose e recriar o container (o volume com as sessões permanece). Em último caso, restaurar o backup do volume feito antes do upgrade.

---

## Referências

- Releases/changelog: https://github.com/aldinokemal/go-whatsapp-web-multidevice/releases
- Análise v8 → v9: [UPGRADE_GOWA_9.md](UPGRADE_GOWA_9.md)
- Infra de deploy: [INFRAESTRUTURA.md](INFRAESTRUTURA.md)
