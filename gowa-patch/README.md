# GOWA — patch de nomes de grupo (imagem local)

## Por que existe

O GOWA v9.6.0 grava **todo grupo novo** com o nome placeholder `Group <id>` e nunca
corrige depois, mesmo conhecendo o subject real. Isso quebra busca e identificação na
UI. O fix está no PR upstream
[aldinokemal/go-whatsapp-web-multidevice#872](https://github.com/aldinokemal/go-whatsapp-web-multidevice/pull/872),
**aberto e não mesclado** (situação em 2026-10-22). A issue é a
[#879](https://github.com/aldinokemal/go-whatsapp-web-multidevice/issues/879).

Enquanto o PR não entra num release, o servidor roda uma **imagem local**:
`gowa-patched:9.6.0-groupnames` = `v9.6.0` + esse patch.

## O que o patch faz

Em `src/infrastructure/chatstorage/sqlite_repository.go`, quando o nome calculado é
exatamente o placeholder (`Group <user>` / `Newsletter <user>`), ele consulta
`GetGroupInfo` / `GetNewsletterInfo` e grava `Group <subject>`. Só roda nesse caso,
com timeout de 5s, e falha de lookup mantém o placeholder (tenta de novo na próxima
mensagem). Sem migração, sem request extra no caminho normal.

## Arquivos

| Caminho | O quê |
|---|---|
| `gowa-patch/0001-group-chat-names.patch` | patch (245 linhas, `git diff` sobre a tag `v9.6.0`) |
| `gowa-patch/rebuild.sh` | reconstrói a imagem do zero |
| `gowa-patch/backfill-names.py` | corrige nomes já gravados (dry-run por padrão) |
| `gowa-work/group-names.json` | mapa `device -> {jid: nome}` puxado da API |
| `gowa-work/fetch-group-names.py` | regenera o mapa a partir do GOWA rodando |

## Rebuild da imagem

```bash
cd ~/ms_automatizar
./gowa-patch/rebuild.sh
```

O script clona a tag `v9.6.0`, aplica o patch, monta o contexto e builda via API do
Docker. Não precisa de CLI do docker instalado.

## Corrigir nomes já no banco (backfill)

Rodar **com o container parado** (o script monta o volume em modo leitura no dry-run,
escrita no `--apply`):

```bash
python3 ~/ms_automatizar/gowa-patch/fetch-group-names.py   # atualiza o mapa
python3 ~/ms_automatizar/gowa-patch/backfill-names.py      # dry-run
python3 ~/ms_automatizar/gowa-patch/backfill-names.py --apply
```

Só toca em linhas cujo `name` ainda é o placeholder exato — nomes reais ficam intactos.

## Quando o upstream lançar o fix

1. Confirmar que a release contém o merge do #872.
2. Trocar a imagem no compose de volta para
   `aldinokemal2104/go-whatsapp-web-multidevice:vX.Y.Z`.
3. `docker compose up -d whatsapp-api` (no servidor: `-f docker-compose.ms-automatizar.yml`).
4. Aposentar esta pasta `gowa-patch/`.

## Notas

- O volume `ms-automatizar-whatsapp-data` guarda `chatstorage.db` (histórico de chats),
  `whatsapp.db` (sessão/dispositivos) e a mídia solta. Backup feito em
  `~/gowa-backups/`.
- A UI (`gowa-ui`) é baixada do GitHub no boot e servida em `/`; ver `APP_UI_*` no
  compose.
