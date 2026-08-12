# Sistema de Envio de Holerites

**Versao:** v0.9.8
**Atualizado:** 2026-08-01

Sistema automatizado para envio de recibos de pagamento (holerites) em PDF via Email (Zoho Mail) e WhatsApp (grupos e individual), com suporte a multiplos dispositivos WhatsApp por empresa.

---

## Indice

1. [Visao Geral](#-visao-geral)
2. [Arquitetura](#-arquitetura)
3. [Suporte a Multiplos Dispositivos (v0.9.5)](#-suporte-a-multiplos-dispositivos-v095)
4. [Modos de Operacao](#-modos-de-operacao)
5. [Instalacao e Configuracao](#-instalacao-e-configuracao)
6. [Uso](#-uso)
7. [Templates de Mensagem](#-templates-de-mensagem)
8. [Referencia de API](#-referencia-de-api)
9. [Breaking Changes (v0.9.5)](#-breaking-changes-v095)
10. [Migracao de v0.9.4](#-migracao-de-v094)
11. [Troubleshooting](#-troubleshooting)

---

## Visao Geral

O sistema de envio de holerites suporta dois modos de operacao:

1. **Modo Planilha**: Similar ao envio de folhas de ponto, le configuracoes de uma planilha Excel
2. **Modo MongoDB**: Busca holerites processados no MongoDB e envia diretamente para funcionarios

Os envios podem ser feitos via:

- **E-mail**: Via Zoho Mail API com suporte a multiplos anexos
- **WhatsApp Individual**: Envio direto para numeros de telefone
- **WhatsApp Grupo**: Envio para grupos com mapeamento automatico de nome para JID

### Estrategia de Envio

O sistema utiliza uma estrategia otimizada para evitar rate limiting:

1. **Mensagem de texto primeiro**: Envia a mensagem do template antes dos arquivos
2. **Arquivos em sequencia**: Cada arquivo e enviado individualmente com delay
3. **Delays automaticos**:
   - `1.5s` entre cada arquivo
   - `1.0s` apos a mensagem de texto
   - `3.0s` apos erros (retry)

---

## Arquitetura

```
src/
├── models/
│   ├── holerite_models.py            # Models para holerites processados
│   ├── template_mensagem_models.py   # Models para templates de mensagem
│   ├── grupo_whatsapp_models.py      # Models para cache de grupos
│   └── empresa_models.py             # Model de empresa (com whatsapp_device_id)
├── services/
│   ├── holerite_service.py           # CRUD de holerites no MongoDB
│   ├── contato_funcionario_service.py # Busca contatos de funcionarios
│   ├── template_mensagem_service.py  # Gerenciamento de templates
│   ├── grupo_whatsapp_service.py     # Cache e mapeamento de grupos (multidevice)
│   ├── zoho_mail_service.py          # Integracao com Zoho Mail API
│   ├── whatsapp_service.py           # Integracao com WhatsApp API (multidevice)
│   ├── empresa_service.py            # CRUD de empresas (com device_id)
│   └── planilha_holerites_service.py # Leitura da planilha de contatos
├── processadores/
│   └── envio_holerite_orquestrador.py # Coordenacao do fluxo
├── interface/
│   └── interface_envio_holerite.py    # Menu interativo
└── utils/
    ├── telefone_utils.py              # Normalizacao de telefones
    └── retry_utils.py                 # Decorator de retry
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
│               interface_envio_holerite.py                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ 1. Identifica empresa do holerite
                         │ 2. Extrai whatsapp_device_id
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   CAMADA DE ORQUESTRACAO                    │
│              envio_holerite_orquestrador.py                 │
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

### Roteamento Automatico por Empresa

O orquestrador de envio automaticamente:

1. Busca a empresa pelo nome (usando `buscar_por_nome_ou_simplificado`)
2. Obtem o `whatsapp_device_id` da empresa
3. Passa o `device_id` para o `WhatsAppService`

```python
# Codigo do envio_holerite_orquestrador.py
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

### Cache Multi-Device

O sistema usa cache inteligente com chave composta:

```python
# Chave do cache: {device_id}:{nome_normalizado}
cache_key = f"{device_id}:{nome_normalizado}"

# Exemplos:
# "WhatsApp-Alefe:rh_geral"
# "WhatsApp-Empresa:rh_geral"  # Nao conflita!
```

---

## Modos de Operacao

### Modo Planilha (TipoEnvioHolerite.PLANILHA)

Similar ao envio de folhas de ponto:

- Le planilha de contatos de holerites
- Envia para grupos ou contatos genericos
- Util para envios em lote por departamento/setor

```python
from src.processadores.envio_holerite_orquestrador import envio_holerite_orquestrador

relatorio = envio_holerite_orquestrador.enviar_via_planilha(
    mes=1,
    ano=2026,
    apenas_simular=False
)
```

### Modo MongoDB (TipoEnvioHolerite.MONGODB)

Envio direto baseado em dados do MongoDB:

- Busca holerites pendentes no MongoDB
- Envia diretamente para o funcionario
- Usa contatos cadastrados no MongoDB (email/whatsapp)

```python
relatorio = envio_holerite_orquestrador.enviar_via_mongodb(
    competencia="01/2026",
    empresa_id=None,  # Todas as empresas
    canais=["email", "whatsapp"],
    apenas_simular=False
)
```

### Otimizacao em Batch (MongoDB)

O modo MongoDB usa busca em batch para contatos:

```python
# Uma unica query ao inves de N queries
contatos_map = contato_funcionario_service.obter_contatos_batch(funcionario_ids)

# Acesso O(1) por funcionario
email = contatos_map.get(funcionario_id, {}).get("email")
whatsapp = contatos_map.get(funcionario_id, {}).get("whatsapp")
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
3. Configure no `.env`:
   - `ZOHO_CLIENT_ID`
   - `ZOHO_CLIENT_SECRET`
4. No programa, execute **"Configurar OAuth"**

### 3. Configurar Variaveis de Ambiente

```env
# MongoDB
MONGO_URI=mongodb://localhost:27017
MONGO_DATABASE_NAME=MS_Automatizar

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

### 4. Estrutura de Holerites no MongoDB

```json
{
    "_id": ObjectId("..."),
    "funcionario_id": ObjectId("..."),
    "funcionario_nome": "Joao da Silva",
    "empresa_id": ObjectId("..."),
    "empresa_nome": "Empresa ABC",
    "competencia": "01/2026",
    "arquivo": {
        "caminho": "C:\\Holerites\\01.2026\\Recibo - Joao da Silva.pdf",
        "nome": "Recibo - Joao da Silva.pdf"
    },
    "status": "pendente",
    "envios": []
}
```

---

## Uso

### Menu Interativo

```bash
uv run python automatizar.py
# Opcao 4 - Operacoes com Holerite
#   └── Opcao X - Envio de Holerites
```

### Uso Programatico

#### Verificar Servicos

```python
from src.processadores.envio_holerite_orquestrador import envio_holerite_orquestrador

status = envio_holerite_orquestrador.verificar_servicos()

print(f"WhatsApp: {'OK' if status['whatsapp_conectado'] else 'ERRO'}")
print(f"Zoho Mail: {'OK' if status['zoho_mail_conectado'] else 'ERRO'}")
```

#### Enviar via Planilha

```python
relatorio = envio_holerite_orquestrador.enviar_via_planilha(
    mes=1,
    ano=2026,
    apenas_simular=True  # Dry run
)

print(f"Total: {relatorio.total_holerites}")
print(f"Enviados: {relatorio.enviados_sucesso}")
print(f"Erros: {relatorio.enviados_erro}")
```

#### Enviar via MongoDB

```python
relatorio = envio_holerite_orquestrador.enviar_via_mongodb(
    competencia="01/2026",
    empresa_id="65abc123...",  # Opcional: filtrar por empresa
    canais=["email", "whatsapp"],
    apenas_simular=False
)

print(f"Duracao: {relatorio.duracao_segundos():.1f}s")
```

#### Obter Estatisticas

```python
stats = envio_holerite_orquestrador.obter_estatisticas_competencia("01/2026")

print(f"Total: {stats['total']}")
print(f"Pendentes: {stats['pendentes']}")
print(f"Enviados: {stats['enviados']}")
print(f"Erros: {stats['erros']}")
```

---

## Templates de Mensagem

O sistema usa templates especificos para holerites:

| Tipo | Uso |
|------|-----|
| `EMAIL_HOLERITE` | Template de email para holerites |
| `WHATSAPP_INDIVIDUAL_HOLERITE` | Template WhatsApp individual |
| `WHATSAPP_GRUPO_HOLERITE` | Template WhatsApp grupo |

### Placeholders Disponiveis

| Placeholder | Descricao |
|-------------|-----------|
| `{funcionario_nome}` ou `{nome}` | Nome do funcionario |
| `{competencia}` | Competencia (MM/AAAA) |
| `{mes}` | Numero do mes |
| `{ano}` | Ano |
| `{mes_extenso}` | Nome do mes (Janeiro, etc.) |
| `{empresa}` | Nome da empresa |
| `{local}` | Local/Contrato/Polo |
| `{tipo_documento}` | "Recibo de Pagamento" |
| `{data_envio}` | Data/hora do envio |

### Exemplo de Template

```
Ola {nome}!

Segue seu recibo de pagamento de {mes_extenso}/{ano}.

Atenciosamente,
{empresa}
```

---

## Referencia de API

### EnvioHoleriteOrquestrador

#### verificar_servicos()

```python
def verificar_servicos(self) -> Dict[str, bool]:
    """
    Verifica disponibilidade dos servicos.

    Returns:
        Dict com status de cada servico:
        {
            "planilha_holerites": bool,
            "holerite_service": bool,
            "contato_service": bool,
            "templates": bool,
            "whatsapp": bool,
            "whatsapp_conectado": bool,
            "zoho_mail": bool,
            "zoho_mail_conectado": bool
        }
    """
```

#### enviar_via_planilha()

```python
def enviar_via_planilha(
    self,
    mes: int = None,
    ano: int = None,
    apenas_simular: bool = False
) -> RelatorioEnvioHolerite:
    """
    Envia holerites usando a planilha de contatos.

    Args:
        mes: Mes de referencia
        ano: Ano de referencia
        apenas_simular: Se True, nao envia de fato

    Returns:
        RelatorioEnvioHolerite com resultado
    """
```

#### enviar_via_mongodb()

```python
def enviar_via_mongodb(
    self,
    competencia: str,
    empresa_id: str = None,
    canais: List[str] = None,
    apenas_simular: bool = False
) -> RelatorioEnvioHolerite:
    """
    Envia holerites diretamente do MongoDB.

    Args:
        competencia: Competencia (MM/AAAA)
        empresa_id: Filtrar por empresa (opcional)
        canais: ["email", "whatsapp"] (default: ambos)
        apenas_simular: Se True, nao envia de fato

    Returns:
        RelatorioEnvioHolerite com resultado
    """
```

### GrupoWhatsAppService

Ver [ENVIO_FOLHAS_PONTO.md](ENVIO_FOLHAS_PONTO.md#referencia-de-api) para referencia completa.

**Resumo - Metodos principais (v0.9.5):**

```python
# Todos os metodos agora exigem device_id
jid = service.obter_jid_por_nome(nome, device_id=device_id)
grupo = service.buscar_por_nome(nome, device_id=device_id)
service.sincronizar_com_api(grupos_api, device_id=device_id)
grupos = service.listar_para_exibicao(device_id=device_id)
```

### WhatsAppService

Ver [ENVIO_FOLHAS_PONTO.md](ENVIO_FOLHAS_PONTO.md#referencia-de-api) para referencia completa.

**Resumo - Metodos principais:**

```python
dispositivos = service.listar_dispositivos()
status = service.verificar_status_dispositivo(device_id)
device_id = service.obter_id_dispositivo_por_jid(jid)
```

---

## Breaking Changes (v0.9.5)

### Resumo de Mudancas

| Componente | Mudanca | Impacto |
|------------|---------|---------|
| `GrupoWhatsAppService.obter_jid_por_nome()` | `device_id` OBRIGATORIO | Alto |
| `GrupoWhatsAppService.buscar_por_nome()` | `device_id` OBRIGATORIO | Alto |
| `GrupoWhatsAppService.sincronizar_com_api()` | `device_id` OBRIGATORIO | Alto |
| `GrupoWhatsAppService.listar_para_exibicao()` | `device_id` OBRIGATORIO | Alto |
| Envio WhatsApp grupo | Requer empresa com device_id | Medio |

### Comparacao ANTES/DEPOIS

#### Envio para Grupo WhatsApp

**ANTES (v0.9.4):**
```python
# Buscava grupo sem device_id
grupo = grupo_whatsapp_service.buscar_por_nome(grupo_nome)
```

**DEPOIS (v0.9.5):**
```python
# Busca empresa para obter device_id
empresa = empresa_service.buscar_por_nome_ou_simplificado(empresa_nome)
device_id = empresa.get('whatsapp_device_id')

# Busca grupo com device_id
grupo = grupo_whatsapp_service.buscar_por_nome(grupo_nome, device_id)
```

---

## Migracao de v0.9.4

### Passo 1: Atualizar Schema MongoDB

```python
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["MS_Automatizar"]

# Adicionar whatsapp_device_id a grupos existentes
result = db.grupos_whatsapp.update_many(
    {"whatsapp_device_id": {"$exists": False}},
    {"$set": {"whatsapp_device_id": ""}}
)
print(f"Grupos atualizados: {result.modified_count}")

# Criar indices novos
db.grupos_whatsapp.create_index([
    ("jid", 1),
    ("whatsapp_device_id", 1)
], unique=True, name="idx_jid_device_unico")
```

### Passo 2: Configurar device_id nas Empresas

```python
# Mapear empresas para seus dispositivos
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

Para cada empresa, execute a sincronizacao de grupos via interface.

### Checklist de Validacao

- [ ] Schema MongoDB atualizado
- [ ] Indices compostos criados
- [ ] Empresas com device_id configurado
- [ ] Grupos re-sincronizados por device
- [ ] Teste de envio funcionando

---

## Troubleshooting

### WhatsApp nao conectado

1. Verifique se o container esta rodando: `docker ps`
2. Acesse http://localhost:3000 e reescaneie o QR Code
3. Verifique logs: `docker logs ms-automatizar-whatsapp`

### Erro: "Grupo nao encontrado"

1. Verifique se o grupo foi sincronizado
2. **v0.9.5**: Verifique se a empresa tem `whatsapp_device_id` configurado
3. Execute sincronizacao para a empresa correta

### Erro: "device_id e obrigatorio"

**Causa:** Empresa sem `whatsapp_device_id` configurado ou metodo chamado sem device_id.

**Solucao:**
```python
# Configurar device_id na empresa
db.empresas.update_one(
    {"nome": "Empresa ABC"},
    {"$set": {"whatsapp_device_id": "556993451333@s.whatsapp.net"}}
)
```

### Holerite nao encontrado

1. Verifique se o holerite foi processado e esta no MongoDB
2. Verifique o status do holerite (deve ser "pendente" ou "processado")
3. Verifique se o caminho do arquivo existe

### Contato nao encontrado

1. Verifique se o funcionario tem contatos cadastrados
2. Verifique a colecao `contatos_funcionarios` no MongoDB
3. Use o modo planilha como alternativa

### Performance lenta

1. Use o modo MongoDB com busca em batch (automatico)
2. Verifique a conexao com MongoDB
3. Considere indexar campos de busca frequente

---

## Colecoes MongoDB

| Colecao | Descricao |
|---------|-----------|
| `holerites` | Holerites processados |
| `contatos_funcionarios` | Contatos de funcionarios |
| `templates_mensagens` | Templates configurados |
| `grupos_whatsapp` | Cache de grupos (JID + device_id) |
| `empresas` | Empresas (com whatsapp_device_id) |

---

## Documentacao Relacionada

- [HOLERITE.md](HOLERITE.md) - Processamento e renomeacao de holerites
- [ENVIO_FOLHAS_PONTO.md](ENVIO_FOLHAS_PONTO.md) - Sistema de envio de folhas de ponto

---

## Licenca

Este modulo faz parte do projeto MS-Automatizar.
