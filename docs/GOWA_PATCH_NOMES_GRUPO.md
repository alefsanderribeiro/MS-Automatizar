# GOWA — patch de nomes de grupo (imagem local)

## Problema

O GOWA v9.6.0 grava **todo grupo novo** com o nome placeholder `Group <id>` e nunca
corrige depois, mesmo conhecendo o subject real. Isso quebra busca e identificação na
UI e nas integrações que leem `chats.name`.

- Issue upstream: [#879](https://github.com/aldinokemal/go-whatsapp-web-multidevice/issues/879)
- Fix upstream: PR [#872](https://github.com/aldinokemal/go-whatsapp-web-multidevice/pull/872) — **aberto, não mesclado** (situação em 2026-10-22)

## Solução

Imagem local `gowa-patched:9.6.0-groupnames` = `v9.6.0` + esse patch.

O patch vive em [`gowa-patch/`](../gowa-patch/):

| Arquivo | Função |
|---|---|
| `0001-group-chat-names.patch` | `git diff` sobre a tag `v9.6.0` |
| `rebuild.sh` | reconstrói a imagem do zero (API do Docker, sem CLI) |
| `fetch-group-names.py` | puxa nomes reais da API → `group-names.json` |
| `backfill-names.py` | corrige nomes já gravados (dry-run por padrão) |
| `cleanup.py` | remove linhas de device órfão / mídia antiga |
| `maintenance.py` | stop → cleanup → start → healthcheck |
| `healthcheck.py` | versão, UI, devices, contagem de placeholders |

### O que o patch faz

Em `src/infrastructure/chatstorage/sqlite_repository.go`: quando o nome calculado é
exatamente o placeholder (`Group <user>` / `Newsletter <user>`), consulta
`GetGroupInfo` / `GetNewsletterInfo` e grava `Group <subject>`. Só roda nesse caso,
com timeout de 5s; falha de lookup mantém o placeholder e tenta de novo na próxima
mensagem. Sem migração e sem request extra no caminho normal.

### Rebuild

```bash
cd gowa-patch && ./rebuild.sh
```

### Quando o upstream lançar o fix

1. Confirmar que a release contém o merge do #872.
2. Trocar `image:` no `docker-compose.yml` de volta para
   `aldinokemal2104/go-whatsapp-web-multidevice:vX.Y.Z`.
3. `docker compose up -d whatsapp-api`.
4. Aposentar `gowa-patch/`.

## Notas operacionais

- **Mapeamento de colunas**: `devices.device_id` guarda o nome lógico
  (`WhatsApp-MS`), enquanto `chats.device_id` / `messages.device_id` guardam o **JID**
  (`556992518455@s.whatsapp.net`). Comparar com a coluna errada faz devices ativos
  parecerem órfãos — sempre use `devices.jid`.
- **Mídia**: os arquivos `<epoch>-<uuid>.<ext>` na raiz de `storages/` **não** são
  registrados no `chatstorage.db` (a coluna `filename` guarda o nome original
  enviado). Não há como saber pelo banco quais ainda são usados, então remoção é por
  idade e só com `--prune-media-days`.
- **Backup**: `cleanup.py --apply` faz `VACUUM INTO` antes de escrever e roda
  `PRAGMA integrity_check` no fim.
