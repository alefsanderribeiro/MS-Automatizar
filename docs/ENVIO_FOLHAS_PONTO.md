# Sistema de Envio de Folhas de Ponto

**Versao:** v0.9.8
**Atualizado:** 2026-08-01

Sistema automatizado para envio de folhas de ponto em PDF via Email (Zoho Mail) e WhatsApp (grupos e individual), com suporte a multiplos dispositivos WhatsApp por empresa.

---

## Indice

1. [Visao Geral](#-visao-geral)
2. [Arquitetura](#-arquitetura)
3. [Suporte a Multiplos Dispositivos (v0.9.5)](#-suporte-a-multiplos-dispositivos-v095)
4. [Instalacao e Configuracao](#-instalacao-e-configuracao)
5. [Uso](#-uso)
6. [Templates de Mensagem](#-templates-de-mensagem)
7. [Referencia de API](#-referencia-de-api)
8. [Breaking Changes (v0.9.5)](#-breaking-changes-v095)
9. [Migracao de v0.9.4](#-migracao-de-v094)
10. [Troubleshooting](#-troubleshooting)

---

## Visao Geral

O sistema le uma planilha Excel com configuracoes de envio e distribui automaticamente os arquivos PDF das folhas de ponto para os destinatarios configurados atraves de:

- **E-mail**: Via Zoho Mail API com suporte a multiplos anexos
- **WhatsApp Individual**: Envio direto para numeros de telefone
- **WhatsApp Grupo**: Envio para grupos com mapeamento automatico de nome para JID

### Estrategia de Envio (v0.9.3+)

O sistema utiliza uma estrategia otimizada para evitar rate limiting:

1. **Mensagem de texto primeiro**: Envia a mensagem do template antes dos arquivos
2. **Arquivos em sequencia**: Cada arquivo e enviado individualmente com delay
3. **Delays automaticos**:
   - `1.5s` entre cada arquivo
   - `1.0s` apos a mensagem de texto
   - `3.0s` apos erros (retry)

Esta abordagem imita o comportamento de "arrastar multiplos arquivos" no WhatsApp Web.

---

## Arquitetura

```
src/
├── models/
│   ├── envio_folha_ponto_models.py   # Models para registro de envios
│   ├── template_mensagem_models.py   # Models para templates de mensagem
│   ├── grupo_whatsapp_models.py      # Models para cache de grupos
│   └── empresa_models.py             # Model de empresa (com whatsapp_device_id)
├── services/
│   ├── envio_folha_ponto_service.py  # CRUD de registros de envio
│   ├── template_mensagem_service.py  # Gerenciamento de templates
│   ├── grupo_whatsapp_service.py     # Cache e mapeamento de grupos (multidevice)
│   ├── zoho_mail_service.py          # Integracao com Zoho Mail API
│   ├── whatsapp_service.py           # Integracao com WhatsApp API (multidevice)
│   ├── empresa_service.py            # CRUD de empresas (com device_id)
│   └── planilha_contatos_service.py  # Leitura da planilha Excel
├── processadores/
│   └── envio_folha_ponto_orquestrador.py  # Coordenacao do fluxo
├── interface/
│   └── interface_envio_folha_ponto.py     # Menu interativo
├── comandos/
│   └── folha_de_ponto.py               # CLI com argparse (inclui subcomandos envio-*)
└── utils/
    ├── telefone_utils.py             # Normalizacao de telefones
    └── retry_utils.py                # Decorator de retry
```

---

## Suporte a Multiplos Dispositivos (v0.9.5)

### Por que Multiplos Dispositivos?

A versao 0.9.5 introduz suporte a **multiplos dispositivos WhatsApp** por empresa:

- **Cada empresa pode ter seu proprio numero WhatsApp** configurado
- **Isolamento completo** de grupos entre dispositivos
- **Roteamento automatico** de mensagens para o dispositivo correto
- **Cache inteligente** com namespace por dispositivo

### Como Funciona

```
┌─────────────────────────────────────────────────────────────┐
│                     CAMADA DE INTERFACE                     │
│              interface_envio_folha_ponto.py                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ 1. Seleciona empresa
                         │ 2. Extrai whatsapp_device_id
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   CAMADA DE ORQUESTRACAO                    │
│             envio_folha_ponto_orquestrador.py               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ 3. Passa device_id aos servicos
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      CAMADA DE SERVICOS                     │
│  WhatsAppService / GrupoWhatsAppService / EmpresaService   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ 4. Filtra por device_id
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    CAMADA DE PERSISTENCIA                   │
│             MongoDB (empresas / grupos_whatsapp)            │
└─────────────────────────────────────────────────────────────┘
```

### Modelo de Dados

#### EmpresaMongoDB

```python
class EmpresaMongoDB(BaseModel):
    nome: str
    whatsapp_device_id: Optional[str] = Field(
        default=None,
        description="Device ID do WhatsApp (ex: 5569XXXXXXXX@s.whatsapp.net)"
    )
    # ... outros campos

    def obter_device_whatsapp(self) -> Optional[str]:
        """Retorna device_id configurado ou None"""
        return self.whatsapp_device_id
```

#### GrupoWhatsAppMongoDB

```python
class GrupoWhatsAppMongoDB(BaseModel):
    nome: str
    nome_normalizado: str
    jid: str
    whatsapp_device_id: str  # OBRIGATORIO na v0.9.5
    # ... outros campos
```

### Indice Composto MongoDB

```python
# Garante unicidade por (jid, device_id)
db.grupos_whatsapp.create_index([
    ("jid", ASCENDING),
    ("whatsapp_device_id", ASCENDING)
], unique=True, name="idx_jid_device_unico")

# Indice para busca por nome filtrado por device
db.grupos_whatsapp.create_index([
    ("nome_normalizado", ASCENDING),
    ("whatsapp_device_id", ASCENDING)
], name="idx_nome_device")
```

### Pre-processamento e Cache

O sistema usa cache inteligente com chave composta:

```python
# Chave do cache: {device_id}:{nome_normalizado}
cache_key = f"{device_id}:{nome_normalizado}"

# Exemplos:
# "WhatsApp-Alefe:rh_geral"
# "WhatsApp-Empresa:rh_geral"  # Nao conflita!
```

**Otimizacao ~87%**: Ao usar cache, buscas passam de O(n) para O(1).

### Sincronizacao Multi-Device

```python
from src.services.whatsapp_service import WhatsAppService
from src.services.grupo_whatsapp_service import GrupoWhatsAppService

# 1. Obter device_id da empresa
device_id = empresa.obter_device_whatsapp()

# 2. Listar grupos da API filtrado por device
whatsapp = WhatsAppService()
grupos_api = whatsapp.listar_grupos(device_id=device_id)

# 3. Sincronizar com MongoDB
grupo_service = GrupoWhatsAppService()
grupo_service.sincronizar_com_api(grupos_api, device_id=device_id)
```

### Roteamento Automatico por Empresa

Ao enviar mensagens, o sistema automaticamente:

1. Busca a empresa pelo nome
2. Obtem o `whatsapp_device_id` da empresa
3. Passa o `device_id` para o `WhatsAppService`
4. O servico adiciona o header `X-Device-Id` na requisicao

```python
# Exemplo do orquestrador
empresa_nome = contexto.get('empresa', '')
device_id = None

if empresa_nome and empresa_service.disponivel:
    empresa = empresa_service.buscar_por_nome_ou_simplificado(empresa_nome)
    if empresa and empresa.get('whatsapp_device_id'):
        device_id = empresa.get('whatsapp_device_id')
        logger.info(f"Usando device {device_id} para empresa {empresa_nome}")

# Enviar com device_id
resultado = whatsapp_service.enviar_multiplos_arquivos(
    destinatario=telefone,
    arquivos=arquivos,
    mensagem=mensagem,
    device_id=device_id
)
```

---

## Instalacao e Configuracao

### 1. Configurar WhatsApp API (Docker)

```bash
# Iniciar o grupo único (MongoDB + Redis + WhatsApp API)
docker compose -f docker-compose.ms-automatizar.yml up -d

# Verificar logs do WhatsApp
docker logs -f ms-automatizar-whatsapp
```

Acesse http://localhost:3000 e escaneie o QR Code com seu WhatsApp.

### 2. Configurar Zoho Mail API

1. Acesse: https://api-console.zoho.com/
2. Crie um "Self Client" (Server-based Application)
3. Configure no `.env` apenas:
   - `ZOHO_CLIENT_ID`
   - `ZOHO_CLIENT_SECRET`
4. No programa, acesse: **Configuracoes > Zoho Mail (E-mail)**
5. Execute **"Configurar OAuth"** - o navegador abrira automaticamente
6. Autorize o acesso - o programa salvara tudo automaticamente

### 3. Configurar Variaveis de Ambiente

Copie `.env_exemplo` para `.env` e preencha:

```env
# WhatsApp
WHATSAPP_API_URL=http://localhost:3000
WHATSAPP_BASIC_AUTH=usuario:senha    # v8/v9 — envia Authorization: Basic base64(user:pass)

# Zoho Mail
ZOHO_CLIENT_ID=seu_client_id
ZOHO_CLIENT_SECRET=seu_client_secret

# Retry
ENVIO_MAX_TENTATIVAS=3
ENVIO_RETRY_DELAY_SECONDS=5
```

### 4. Preparar Planilha de Contatos

Crie a planilha `src/data/models/Planilha de Contatos - Folha de Ponto.xlsx` com as colunas:

| Coluna | Descricao |
|--------|-----------|
| ID | Identificador unico |
| NOME COMPLETO | Nome do contato |
| EMAIL | E-mail(s) separados por `,` ou `;` |
| TELEFONE | Telefone(s) separados por `,` ou `;` |
| GRUPO WHATSAPP | Nome(s) do(s) grupo(s) |
| ENVIAR EMAIL | S/N |
| ENVIAR WHATSAPP | S/N |
| ENVIAR GRUPO WHATSAPP | S/N |
| EMPRESA | Nome da empresa |
| LOCAL - CONTRATO - POLO | Local de trabalho |
| DIRETORIO GERAL | Caminho base |
| DIRETORIO ESPECIFICO | Subpasta |

### 5. Estrutura dos Diretorios de PDFs

```
{DIRETORIO GERAL}\
└── {ANO}\
    └── {MES:02d}.{ANO}\
        └── {DIRETORIO ESPECIFICO}\
            ├── funcionario1.pdf
            ├── funcionario2.pdf
            └── ...
```

---

## Uso

### Menu Interativo

```bash
uv run python automatizar.py
# Opcao 3 - Operacoes com Folha de Ponto
#   └── Opcao 3 - Envio de Folhas de Ponto
```

### Linha de Comando (CLI)

```bash
# Verificar servicos de envio
uv run python automatizar.py folha_de_ponto envio-verificar

# Validar planilha de contatos
uv run python automatizar.py folha_de_ponto envio-validar

# Sincronizar grupos WhatsApp (v0.9.5: exige selecao de empresa)
uv run python automatizar.py folha_de_ponto envio-sincronizar --listar

# Listar contatos da planilha (envio-listar não usa --mes/--ano)
uv run python automatizar.py folha_de_ponto envio-listar

# Simulacao (dry run)
uv run python automatizar.py folha_de_ponto envio-executar --mes 1 --ano 2026 --dry-run

# Envio apenas por e-mail
uv run python automatizar.py folha_de_ponto envio-executar --mes 1 --ano 2026 --email

# Envio completo (com confirmacao)
uv run python automatizar.py folha_de_ponto envio-executar --mes 1 --ano 2026 --force

# Envio para IDs especificos
uv run python automatizar.py folha_de_ponto envio-executar --mes 1 --ano 2026 --ids "1,5,10"

# Abrir menu interativo de envio
uv run python automatizar.py folha_de_ponto envio
```

---

## Templates de Mensagem

O sistema utiliza templates personalizaveis com placeholders:

| Placeholder | Descricao |
|-------------|-----------|
| `{nome}` | Nome do destinatario |
| `{mes}` | Numero do mes |
| `{ano}` | Ano |
| `{mes_extenso}` | Nome do mes (Janeiro, Fevereiro, etc.) |
| `{local}` | Local/Contrato/Polo |
| `{empresa}` | Nome da empresa |

Templates sao criados automaticamente na primeira execucao.

---

## Referencia de API

### GrupoWhatsAppService

#### obter_jid_por_nome()

Busca o JID de um grupo pelo nome para um dispositivo especifico.

```python
def obter_jid_por_nome(self, nome: str, device_id: str) -> Optional[str]:
    """
    Args:
        nome: Nome do grupo WhatsApp
        device_id: Device ID do WhatsApp (OBRIGATORIO)

    Returns:
        JID do grupo ou None se nao encontrado
    """
```

**Exemplo:**

```python
from src.services.grupo_whatsapp_service import GrupoWhatsAppService

service = GrupoWhatsAppService()

# Busca com device_id OBRIGATORIO
jid = service.obter_jid_por_nome("RH - Geral", device_id="WhatsApp-Alefe")

if jid:
    print(f"JID: {jid}")
else:
    print("Grupo nao encontrado")
```

#### buscar_por_nome()

Busca grupo completo pelo nome e device_id.

```python
def buscar_por_nome(
    self,
    nome: str,
    device_id: str,
    match_parcial: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Args:
        nome: Nome do grupo
        device_id: Device ID do WhatsApp (OBRIGATORIO)
        match_parcial: Se True, faz busca parcial

    Returns:
        Documento do grupo ou None
    """
```

#### sincronizar_com_api()

Sincroniza grupos da API com MongoDB para um dispositivo.

```python
def sincronizar_com_api(
    self,
    grupos_api: List[Dict[str, Any]],
    device_id: str
) -> Dict[str, int]:
    """
    Args:
        grupos_api: Lista de grupos da API
        device_id: Device ID do WhatsApp (OBRIGATORIO)

    Returns:
        Dict com contagem: {"criados": X, "atualizados": Y, "inativos": Z}
    """
```

#### listar_para_exibicao()

Lista grupos formatados filtrados por dispositivo.

```python
def listar_para_exibicao(self, device_id: str) -> List[Dict[str, str]]:
    """
    Args:
        device_id: Device ID do WhatsApp (OBRIGATORIO)

    Returns:
        Lista de dicts com 'nome', 'jid', 'participantes', 'device_id'

    Raises:
        ValueError: Se device_id nao for fornecido
    """
```

#### listar_para_exibicao_sem_filtro()

Lista TODOS os grupos de TODOS os dispositivos (admin/debug).

```python
def listar_para_exibicao_sem_filtro(self) -> List[Dict[str, str]]:
    """
    Returns:
        Lista de TODOS os grupos
    """
```

### WhatsAppService

#### listar_dispositivos()

Lista todos os dispositivos registrados.

```python
def listar_dispositivos(self) -> List[Dict[str, Any]]:
    """
    Returns:
        Lista de dispositivos: [
            {
                "id": "WhatsApp-Alefe",
                "display_name": "Alefsander Ribeiro",
                "state": "logged_in",
                "jid": "556993451333@s.whatsapp.net"
            }
        ]
    """
```

**Exemplo:**

```python
from src.services.whatsapp_service import WhatsAppService

service = WhatsAppService()
dispositivos = service.listar_dispositivos()

for device in dispositivos:
    status = "ATIVO" if device["state"] == "logged_in" else "INATIVO"
    print(f"{device['id']}: {status}")
```

#### verificar_status_dispositivo()

Verifica status de um dispositivo especifico.

```python
def verificar_status_dispositivo(self, device_id: str) -> Dict[str, Any]:
    """
    Args:
        device_id: ID ou JID do dispositivo

    Returns:
        Dict com status: {
            "sucesso": bool,
            "device_id": str,
            "is_logged_in": bool,
            "numero": str,
            "estado": str,
            "nome": str,
            "mensagem": str
        }
    """
```

#### obter_id_dispositivo_por_jid()

Busca ID interno do dispositivo pelo JID.

```python
def obter_id_dispositivo_por_jid(self, jid: str) -> Optional[str]:
    """
    Args:
        jid: JID do dispositivo (ex: 556993451333@s.whatsapp.net)

    Returns:
        ID do dispositivo (ex: WhatsApp-Alefe) ou None
    """
```

### EmpresaMongoDB

#### obter_device_whatsapp()

Retorna device_id configurado para WhatsApp.

```python
def obter_device_whatsapp(self) -> Optional[str]:
    """
    Returns:
        Device ID ou None se nao configurado
    """
```

---

## Breaking Changes (v0.9.5)

### Resumo de Mudancas

| Componente | Mudanca | Impacto |
|------------|---------|---------|
| `GrupoWhatsAppService.obter_jid_por_nome()` | `device_id` agora e OBRIGATORIO | Alto |
| `GrupoWhatsAppService.buscar_por_nome()` | `device_id` agora e OBRIGATORIO | Alto |
| `GrupoWhatsAppService.sincronizar_com_api()` | `device_id` agora e OBRIGATORIO | Alto |
| `GrupoWhatsAppService.listar_para_exibicao()` | `device_id` agora e OBRIGATORIO | Alto |
| CLI `envio-sincronizar --listar` | Exige selecao de empresa primeiro | Medio |
| Cache MongoDB | Chave composta `device_id:nome` | Alto (requer re-sync) |

### Comparacao ANTES/DEPOIS

#### obter_jid_por_nome()

**ANTES (v0.9.4):**
```python
# device_id era opcional
jid = service.obter_jid_por_nome("RH - Geral")
```

**DEPOIS (v0.9.5):**
```python
# device_id e OBRIGATORIO
jid = service.obter_jid_por_nome("RH - Geral", device_id="WhatsApp-Alefe")
```

#### listar_para_exibicao()

**ANTES (v0.9.4):**
```python
# Listava TODOS os grupos
grupos = service.listar_para_exibicao()
```

**DEPOIS (v0.9.5):**
```python
# Requer device_id
grupos = service.listar_para_exibicao(device_id="WhatsApp-Alefe")

# Para listar TODOS, use o novo metodo:
todos = service.listar_para_exibicao_sem_filtro()
```

#### CLI envio-sincronizar

**ANTES (v0.9.4):**
```bash
# Listava grupos diretamente
uv run python automatizar.py envio-sincronizar --listar
```

**DEPOIS (v0.9.5):**
```bash
# Agora exige selecao de empresa
uv run python automatizar.py envio-sincronizar --listar

# Fluxo:
# 1. Sistema lista empresas com device_id
# 2. Usuario seleciona empresa
# 3. Sistema lista grupos APENAS do device_id selecionado
```

---

## Migracao de v0.9.4

### Passo 1: Atualizar Schema MongoDB

Execute o script de migracao (o script abaixo serve de referência — o arquivo físico `scripts/migrate_grupos_0.9.5.py` não faz parte do repositório; use-o como guia para configurar manualmente ou em um script próprio):

```python
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["MS_Automatizar"]

# Adicionar whatsapp_device_id a grupos existentes
result = db.grupos_whatsapp.update_many(
    {"whatsapp_device_id": {"$exists": False}},
    {"$set": {"whatsapp_device_id": ""}}  # Vazio = precisa sincronizar
)

print(f"Grupos atualizados: {result.modified_count}")

# Remover indice antigo se existir
try:
    db.grupos_whatsapp.drop_index("idx_jid_unico")
    print("Indice antigo removido")
except:
    pass

# Criar indices novos
db.grupos_whatsapp.create_index([
    ("jid", 1),
    ("whatsapp_device_id", 1)
], unique=True, name="idx_jid_device_unico")

db.grupos_whatsapp.create_index([
    ("nome_normalizado", 1),
    ("whatsapp_device_id", 1)
], name="idx_nome_device")

print("Indices criados!")
```

### Passo 2: Configurar device_id nas Empresas

```python
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["MS_Automatizar"]

# Listar empresas e seus dispositivos
# (voce precisa saber qual device pertence a qual empresa)
empresas_devices = {
    "Empresa ABC": "556993451333@s.whatsapp.net",
    "Empresa XYZ": "556298765432@s.whatsapp.net",
}

for empresa_nome, device_id in empresas_devices.items():
    result = db.empresas.update_one(
        {"nome": {"$regex": empresa_nome, "$options": "i"}},
        {"$set": {"whatsapp_device_id": device_id}}
    )
    if result.modified_count:
        print(f"Empresa '{empresa_nome}' -> device '{device_id}'")
```

### Passo 3: Re-sincronizar Grupos

```bash
# Para cada empresa, sincronizar grupos
uv run python automatizar.py folha_de_ponto envio-sincronizar

# Selecionar empresa 1, sincronizar
# Selecionar empresa 2, sincronizar
# ...
```

### Passo 4: Atualizar Codigo

Se voce tem scripts customizados, atualize as chamadas:

```python
# ANTES
jid = service.obter_jid_por_nome("Grupo RH")

# DEPOIS
empresa = empresa_service.buscar_por_nome("Empresa ABC")
device_id = empresa.get("whatsapp_device_id")
jid = service.obter_jid_por_nome("Grupo RH", device_id=device_id)
```

### Checklist de Validacao

- [ ] Schema MongoDB atualizado (whatsapp_device_id em empresas e grupos)
- [ ] Indices compostos criados
- [ ] Todas as empresas com device_id configurado
- [ ] Grupos re-sincronizados por device
- [ ] Scripts customizados atualizados

---

## Troubleshooting

### WhatsApp nao conectado

1. Verifique se o container esta rodando: `docker ps`
2. Acesse http://localhost:3000 e reescaneie o QR Code
3. Verifique logs: `docker logs ms-automatizar-whatsapp`

### Erro na autenticacao Zoho

1. Verifique se o refresh_token ainda e valido
2. Gere novos tokens se necessario
3. Confirme os scopes autorizados

### Grupo nao encontrado

1. Execute sincronizacao para a empresa correta
2. Verifique se o nome na planilha corresponde ao nome real do grupo
3. O sistema faz match parcial, mas nomes muito diferentes nao serao encontrados
4. **v0.9.5**: Verifique se o device_id esta correto

### Erro: "device_id e obrigatorio"

**Causa:** Chamada de metodo sem device_id (v0.9.5).

**Solucao:**
```python
# Obter device_id da empresa
empresa = empresa_service.buscar_por_nome("Empresa ABC")
device_id = empresa.get("whatsapp_device_id")

# Passar device_id
jid = service.obter_jid_por_nome("Grupo", device_id=device_id)
```

### Grupos duplicados apos migracao

**Causa:** Cache antigo sem whatsapp_device_id.

**Solucao:**
```python
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["MS_Automatizar"]

# Remover grupos sem device_id
result = db.grupos_whatsapp.delete_many({
    "$or": [
        {"whatsapp_device_id": {"$exists": False}},
        {"whatsapp_device_id": ""}
    ]
})
print(f"Grupos removidos: {result.deleted_count}")

# Re-sincronizar via interface
```

---

## Colecoes MongoDB

| Colecao | Descricao |
|---------|-----------|
| `envios_folhas_de_ponto` | Historico de todos os envios |
| `templates_mensagens` | Templates configurados |
| `grupos_whatsapp` | Cache de grupos (JID + device_id) |
| `empresas` | Empresas (com whatsapp_device_id) |

---

## Formatos de Telefone Aceitos

- `62999999999` (apenas numeros)
- `(62) 99999-9999` (formato brasileiro)
- `+55 62 99999-9999` (internacional)
- `62999999999@s.whatsapp.net` (formato WhatsApp)

---

## Licenca

Este modulo faz parte do projeto MS-Automatizar.
