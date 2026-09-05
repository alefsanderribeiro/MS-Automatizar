# Upgrade GOWA para v9.0.0 — Análise e Plano de Ajuste

**Data:** 2026-08-01
**Status:** ✅ Concluído — código ajustado e análise validada (ver seção de confirmação ao final)

Análise das mudanças do **go-whatsapp-web-multidevice (GOWA)** da v8.x para a **v9.0.0**, focada no impacto para o envio de **folhas de ponto** e **holerites** pelo WhatsApp.

Repositório: https://github.com/aldinokemal/go-whatsapp-web-multidevice

---

## Mudanças importantes na v9.0.0 (resumo do changelog v8.11.0 → v9.0.0)

### 🔴 Breaking Changes

| Mudança | Impacto no nosso código |
|---------|------------------------|
| **Dashboard embutido removido** — passa a ser download em runtime de `gowa-ui` | Visual, mas **não afeta a API**. Endpoints HTTP permanecem. Ajuste de deploy (ver abaixo). |
| **Upgrade Fiber v2 → v3** | Apenas para quem embute GOWA como biblioteca Go. **Consumidores HTTP não são afetados** (nossa integração é via HTTP REST). |
| `src/views/` removido, template engine removido | Deploy — o dashboard vem de outro repositório |

### ✅ O que NÃO muda (importante)

> *"HTTP API consumers are unaffected: routes, payloads, device scoping, and WebSocket behavior are preserved"*

**Nossos endpoints críticos continuam iguais:**
- `POST /send/file` — envio de arquivo (folhas/holerites PDF)
- `POST /send/message` — envio de texto
- `GET /user/my/groups` — listar grupos
- `GET /app/status` — status
- `GET /app/qr` — QR code
- Header `X-Device-Id` → preservado
- Basic auth `APP_BASIC_AUTH=user:secret` → preservado

### ✨ Novidades relevantes

| Recurso | Detalhe |
|---------|---------|
| `GET /app/info` | Novo endpoint de metadados (versão, limites de arquivo, os) |
| WebSocket com auth cross-origin | `/ws?authorization=<base64(user:pass)>` — só relevante se usarmos WS (não usamos) |
| CORS ampliado | Permite `Authorization` e `X-Device-Id` |
| `GET /chat/{chat_jid}/*` | Corrigido para aceitar JID percent-encoded |
| Envio de mensagens sob contenção | Correção de perda de mensagem (não afeta nossa API) |

### Configurações novas (env do container)

| Variável | Padrão | Uso |
|----------|--------|-----|
| `APP_UI_ENABLED` | true | Se `false`, `/` vira banner JSON (só API) |
| `APP_UI_AUTO_UPDATE` | true | Baixa a UI do gowa-ui automaticamente |
| `APP_UI_REPO` | aldinokemal/gowa-ui | Repositório da UI |
| `APP_UI_UPDATE_INTERVAL` | 3h | Frequência de checagem de update da UI |
| `APP_UI_ASSET_SHA256` | — | Pin de supply-chain (segurança) |

---

## Impacto no envio de Folhas de Ponto / Holerites

Nosso código de envio está em **`src/services/whatsapp_service.py`** e usa exatamente os endpoints preservados. A análise do código atual:

### Endpoints usados pelo `whatsapp_service.py`

| Constante | Valor | Status na v9 |
|-----------|-------|--------------|
| `ENDPOINT_STATUS` | `/app/status` | ✅ Preservado |
| `ENDPOINT_GROUPS` | `/user/my/groups` | ✅ Preservado |
| `ENDPOINT_SEND_FILE` | `/send/file` | ✅ Preservado |
| `ENDPOINT_SEND_MESSAGE` | `/send/message` | ✅ Preservado |
| `ENDPOINT_QR_CODE_LEGACY` | `/app/qr` | ⚠️ REMOVIDO na v9 — mantido como fallback v8 |
| `ENDPOINT_LOGIN` | `/app/login` | ✅ Novo na v9 — retorna `results.qr_link` (URL do QR) |

### Formato de resposta

O código já lida com **v8+** (usa `dados.get("results")` com fallback para `dados.get("data")`):
```python
# API v8+ retorna {"results": {"data": [...]}}
results = dados.get("results") or dados
grupos = results.get("data", []) if isinstance(results, dict) else []
```
A v9 **mantém o envelope `results`** — ✅ compatível.

### Header `X-Device-Id`

A v9 **preserva** o header `X-Device-Id` para device scoping. ✅ Nossa implementação está correta.

### Conclusão preliminar

**Nossa biblioteca de envio (`whatsapp_service.py`) é compatível com a v9** nos endpoints e formatos que usa. As mudanças da v9 são majoritariamente internas (dashboard, Fiber v3) e não quebram a API HTTP.

---

## O que PRECISA ser ajustado

### 1. Deploy (docker-compose)
- A imagem passa a baixar a UI em runtime — garantir **acesso ao GitHub** ou pre-seed com `APP_UI_AUTO_UPDATE=false` + `storages/ui/`
- Opcional: `APP_UI_ENABLED` para deploy puro de API
- **Recomendado:** pinar a imagem na tag `latest` é arriscado — considerar pinar em `v9.0.0-*` explícita

### 2. Verificação do código (a confirmar pelo Dev)
- ✅ Endpoints e formato `results` — compatíveis
- ⚠️ **Confirmar** se há qualquer uso de endpoint removido/renomeado que não pegamos na varredura (ex: outros services que falam direto com a API, não só `whatsapp_service.py`)
- ⚠️ **Confirmar** se o `ENDPOINT_SEND_MESSAGE` e `/send/file` não mudaram os **campos obrigatórios** do payload na v9 (a v8.11→v9 não lista mudança, mas o Dev deve validar contra a OpenAPI/Swagger da v9)

### 3. Validação funcional
- Parear um WhatsApp e testar envio real de folha/holerite contra a v9
- Testar com `X-Device-Id` e sem
- Testar listagem de grupos

---

## Plano de Ação

1. **[Dev]** Analisar `src/services/whatsapp_service.py` + `grupo_whatsapp_service.py` + orquestradores de envio contra a OpenAPI da v9
2. **[Dev]** Confirmar payloads de `/send/file` e `/send/message` na v9 (campos `phone`, `caption`, `file`)
3. **[Dev]** Ajustar o que for necessário (se houver) para compatibilidade total com v9
4. **[Dev]** Atualizar docker-compose para a v9 com configurações de UI corretas
5. **[Aura+Alef]** Validar com envio real após pareamento

---

## ✅ Confirmação Dev contra OpenAPI + Código-Fonte da v9.0.0 (2026-08-01)

Analisei a **OpenAPI oficial** (`docs/openapi.yaml`), o **código-fonte** (`src/cmd/rest.go`, `src/ui/rest/{app,user,device}.go`, `src/domains/send/{base,file,text}.go`) e o **changelog** v8.11.0→v9.0.0. Resultado ponto a ponto:

### Endpoints / Payloads — CONFIRMADO COMPATÍVEL (não mudaram)

| Endpoint | v9 (OpenAPI/código) | Nosso código | Verdicto |
|----------|--------------------|--------------|----------|
| `POST /send/file` | multipart: `file`, `phone`, `caption` (+ opcionais `reply_message_id`, `is_forwarded`, `duration`) | envia multipart `{file, phone, caption}` | ✅ OK |
| `POST /send/message` | JSON: `phone`, `message` (+ opcionais) | envia JSON `{phone, message}` | ✅ OK |
| `GET /user/my/groups` | resposta `results.data[]` (itens com `JID`, `Name`, `OwnerJID`, `Topic`, `Participants`) | `results = dados.get("results") or dados; dados["data"]` | ✅ OK |
| `GET /devices` | `results` = **lista** de dispositivos (`id`, `display_name`, `jid`, `state`, `created_at`) | `dados.get("results", [])` esperando lista | ✅ OK |
| `GET /app/status` | `results.{is_connected, is_logged_in, device_id, jid}` (inalterado) | usado indiretamente (ver_status usa `/devices`) | ✅ OK |
| Header `X-Device-Id` | preservado; também aceita `?device_id=` como query | envia header `X-Device-Id` + fallback query | ✅ OK |

### 🔴 BREAKING — AJUSTADO pelo Dev

**1. Autenticação → Basic Auth (CRÍTICO)**
- A v8+ e a v9 aplicam **HTTP Basic Auth** em TODOS os endpoints (OpenAPI `securitySchemes.basicAuth`, `type: http, scheme: basic`; global `security: [basicAuth]`; Fiber `basicauth`).
- Exceções públicas: `/health` e `/chatwoot/webhook` (sem auth). `/app/info` e `/devices` também ficam atrás do auth.
- **Nosso código ANTES enviava `Authorization: Bearer {WHATSAPP_API_KEY}` (ou nada) → teria levado 401 na v9.**
- **AJUSTE:** `whatsapp_service._get_headers()` agora envia `Authorization: Basic base64(user:secret)` quando:
  1. `WHATSAPP_BASIC_AUTH` está definido (novo, explícito), ou
  2. `WHATSAPP_API_KEY` contém `:` (interpretado como `user:secret` — o `.env` atual já usa `alefsander:.Alefe...` neste campo), ou
  3. cai para `Bearer` só como compat. legado v7 quando api_key é token simples.
- **`.env` do cliente não muda** (o valor `alefsander:senha` no `WHATSAPP_API_KEY` passa a ser tratado como Basic Auth automaticamente). Recomendado migrar para `WHATSAPP_BASIC_AUTH` explícito.

**2. `/app/qr` REMOVIDO na v9**
- `GET /app/qr` **não existe mais** na OpenAPI v9. O QR agora vem de `GET /app/login` → `results.qr_link` (URL para `statics/.../qrcode/*.png`), e por-device em `GET /devices/:device_id/login`.
- **AJUSTE:** `obter_qr_code()` tenta `/app/login` (v9) primeiro e cai para `/app/qr` (v8 legacy). Sem callers hoje — é helper de diagnostico.

### Ajustes de Deploy (docker-compose) — FEITO
- Imagem pinada em `aldinokemal2104/go-whatsapp-web-multidevice:v9.0.0` (tag existe no Docker Hub).
- `APP_UI_ENABLED=false` + `APP_UI_AUTO_UPDATE=false` → deploy **puro de API**, sem depender de download do GitHub no boot (ideal para servidor via Tailscale/air-gapped).
- **Healthcheck corrigido:** passava a usar `http://localhost:3000/app/status` (que com auth retorna 401). Agora usa `http://localhost:3000/health` (endpoint público, sem auth).
- Mongodb/Redis: preservados (o compose também ganhou o workaround `GLIBC_TUNABLES=glibc.pthread.rseq=1` no MongoDB para kernels 6.19–7.0.13 — JIRA SERVER-121912).

### Ainda pendente de teste REAL (com device pareado)
- Enviar folha/holerite via `/send/file` e `/send/message` contra a v9 rodando.
- Listar grupos / dispositivos autenticados.
- Confirmar que o `Authorization: Basic` bate com o `APP_BASIC_AUTH` do container.

### Arquivos alterados
- `src/services/whatsapp_service.py` — Basic Auth + `obter_qr_code` v9/v8.
- `docker-compose.ms-automatizar.yml` — imagem v9.0.0, env de UI, healthcheck `/health`.
- `.env_exemplo` — adicionado `WHATSAPP_BASIC_AUTH` (docs).
- `docs/UPGRADE_GOWA_9.md` — esta seção.

---

## Referências

- Changelog oficial: https://github.com/aldinokemal/go-whatsapp-web-multidevice/releases (v8.11.0...v9.0.0)
- gowa-ui (novo dashboard): https://github.com/aldinokemal/gowa-ui
- Código de integração: `src/services/whatsapp_service.py`
