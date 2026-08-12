# Guia Prático: Múltiplos Dispositivos WhatsApp

> Instruções passo-a-passo para usar a funcionalidade multidevice no MS-Automatizar

## 📋 Índice

1. [Setup Inicial](#setup-inicial)
2. [Configuração de Empresas](#configuração-de-empresas)
3. [Envio com Roteamento Automático](#envio-com-roteamento-automático)
4. [Verificação de Dispositivos](#verificação-de-dispositivos)
5. [Troubleshooting](#troubleshooting)

---

## 🚀 Setup Inicial

### Passo 1: Conectar Dispositivos WhatsApp

> ⚠️ **v9 (deploy atual):** o dashboard embutido foi removido e, no deploy puro de API, `APP_UI_ENABLED=false`. O QR é obtido via `GET /app/login` (retorna `results.qr_link`, URL da imagem) ou por device em `GET /devices/:device_id/login`. O acesso ao painel (`/devices/list`) exige Basic Auth (`Authorization: Basic base64(user:pass)`).

Acesse o painel de controle da API:
```
http://localhost:3000/devices/list
```

Para cada número WhatsApp que você quer usar:
1. Clique em "Gerar QR Code"
2. Escanear com o número WhatsApp
3. Aguardar conexão (status: "conectado")

**Resultado:**
```
✅ Device: 5511999990001@s.whatsapp.net (Conectado)
✅ Device: 5511999990002@s.whatsapp.net (Conectado)
✅ Device: 5511999990003@s.whatsapp.net (Conectado)
```

### Passo 2: Configurar Empresas com Dispositivos

**Opção A: Via MongoDB Compass (Interface Visual)**

1. Abra MongoDB Compass
2. Acesse banco → coleção `empresas`
3. Procure a empresa (ex: "Empresa Cliente A")
4. Clique em "Edit Document"
5. Adicione o campo `whatsapp_device_id`:
   ```javascript
   {
       "whatsapp_device_id": "5511999990001@s.whatsapp.net"
   }
   ```
6. Salve

**Opção B: Via Command Line (mongosh)**

```bash
# Conectar ao MongoDB
mongosh

# Usar banco de dados
use MS_Automatizar

# Atualizar empresa
db.empresas.updateOne(
    { nome: "Empresa Cliente A" },
    {
        $set: {
            whatsapp_device_id: "5511999990001@s.whatsapp.net"
        }
    }
)

# Verificar resultado
db.empresas.findOne({ nome: "Empresa Cliente A" })
```

**Opção C: Via Python**

```python
from src.services.empresa_service import empresa_service

# Buscar empresa
empresa = empresa_service.buscar_por_nome("Empresa Cliente A")

# Atualizar com novo device_id
empresa_atualizada = {
    **empresa,
    "whatsapp_device_id": "5511999990001@s.whatsapp.net"
}

# Salvar
empresa_service.atualizar(empresa_atualizada)

print("✓ Empresa atualizada com sucesso!")
```

### Passo 3: Verificar Configuração

```bash
# Python - Listar dispositivos conectados
uv run python -c "
from src.services.whatsapp_service import whatsapp_service
dispositivos = whatsapp_service.listar_dispositivos()
for d in dispositivos:
    print(f\"✅ {d['id']} - {d.get('estado', 'desconhecido')}\")"
```

---

## 📱 Configuração de Empresas

### Tabela de Mapeamento

Recomenda-se manter uma tabela com o mapeamento de empresas e dispositivos:

| Empresa | Device ID | Número | Status |
|---------|-----------|--------|--------|
| Empresa Cliente A | `5511999990001@s.whatsapp.net` | 11 99999-0001 | ✅ |
| Empresa Cliente B | `5511999990002@s.whatsapp.net` | 11 99999-0002 | ✅ |
| Empresa Cliente C | `5511999990003@s.whatsapp.net` | 11 99999-0003 | ✅ |
| Empresa sem device | `null` (padrão) | 11 99999-9999 | ⚙️ |

### Adicionar Nova Empresa com Device

```javascript
// MongoDB - Inserir nova empresa
db.empresas.insertOne({
    "nome": "Nova Empresa LTDA",
    "cnpj": "12.345.678/0001-90",
    "whatsapp_device_id": "5511999990003@s.whatsapp.net",
    "status": "ativa",
    "criado_em": new Date(),
    "atualizado_em": new Date()
})
```

### Migrar Empresa para Outro Dispositivo

```javascript
// Mudança simples
db.empresas.updateOne(
    { nome: "Empresa Cliente A" },
    {
        $set: {
            whatsapp_device_id: "5511999990002@s.whatsapp.net",
            atualizado_em: new Date()
        }
    }
)
```

---

## 📤 Envio com Roteamento Automático

### Envio de Folhas de Ponto

**Menu Interativo:**
```bash
uv run python -m src.comandos.folha_de_ponto envio
```

O sistema irá:
1. Pedir mês e ano
2. Carregar planilha de contatos
3. **Para cada contato:**
   - Extrair empresa
   - Buscar dispositivo da empresa
   - Enviar pelo device correto
4. Mostrar relatório

**Saída (exemplo):**
```
Enviando folhas de ponto 01/2025
Planilha: planilha_contatos.xlsx

📱 Usando device 5511999990001@s.whatsapp.net para empresa Empresa Cliente A
✓ Arquivo enviado para João (11999990001)
✓ Arquivo enviado para Pedro (11999990002)

📱 Usando device 5511999990002@s.whatsapp.net para empresa Empresa Cliente B
✓ Arquivo enviado para Maria (11999990003)
✓ Arquivo enviado para Ana (11999990004)

📱 Empresa sem device configurado, usando padrão
✓ Arquivo enviado para Lucas (11999990005)

=== RESUMO ===
Total contatos: 6
Total envios: 6
Sucesso: 6
Erro: 0
```

### Envio de Holerites

**Menu Interativo:**
```bash
uv run python -m src.comandos.holerite enviar
```

O sistema oferecerá:
```
--- Escolha o Modo de Envio ---
1. Via Planilha
2. Via MongoDB

--- Utilitários ---
3. Sincronizar Grupos WhatsApp
```

**Via MongoDB (Recomendado):**
- Permite filtro por empresa
- Usa device_id da empresa automaticamente

**Via Planilha:**
- Mesma lógica de roteamento que folha de ponto

---

## 🔍 Verificação de Dispositivos

### Listar Todos os Dispositivos

```bash
# Command Line
uv run python -c "
from src.services.whatsapp_service import whatsapp_service
dispositivos = whatsapp_service.listar_dispositivos()
print(f'\nDispositivos Conectados: {len(dispositivos)}\n')
for d in dispositivos:
    print(f\"📱 {d['id']}\")
    print(f\"   Número: {d.get('numero', 'N/A')}\")
    print(f\"   Estado: {d.get('estado', 'desconhecido')}\n\")
"
```

**Saída:**
```
Dispositivos Conectados: 3

📱 5511999990001@s.whatsapp.net
   Número: 5511999990001
   Estado: conectado

📱 5511999990002@s.whatsapp.net
   Número: 5511999990002
   Estado: conectado

📱 5511999990003@s.whatsapp.net
   Número: 5511999990003
   Estado: conectado
```

### Verificar Status de Um Dispositivo

```bash
uv run python -c "
from src.services.whatsapp_service import whatsapp_service

device_id = '5511999990001@s.whatsapp.net'
status = whatsapp_service.verificar_status_dispositivo(device_id)

print(f\"Device: {device_id}\")
print(f\"Conectado: {'✅' if status.get('conectado') else '❌'}\")
print(f\"Número: {status.get('numero', 'N/A')}\")
print(f\"Mensagem: {status.get('mensagem', '')}\")
"
```

### Verificar Empresa e Seu Device

```bash
uv run python -c "
from src.services.empresa_service import empresa_service

empresa = empresa_service.buscar_por_nome('Empresa Cliente A')
if empresa:
    device_id = empresa.get('whatsapp_device_id') or 'PADRÃO'
    print(f\"Empresa: {empresa['nome']}\")
    print(f\"Device: {device_id}\")
else:
    print('❌ Empresa não encontrada')
"
```

---

## 🔄 Fluxo de Envio (Visual)

```
PLANILHA
└─ Contato: João
   └─ Empresa: Empresa Cliente A
   └─ Telefone: 11999990001
      │
      ▼
   ORQUESTRADOR
   └─ Busca: "Empresa Cliente A" no MongoDB
   └─ Encontra: "Empresa Cliente A"
   └─ Extrai: device_id = "5511999990001@s.whatsapp.net"
      │
      ▼
   LOG: "📱 Usando device 5511999990001@s.whatsapp.net para Empresa Cliente A"
      │
      ▼
   WHATSAPP SERVICE
   └─ Header: X-Device-Id: 5511999990001@s.whatsapp.net
   └─ Envia arquivo para 11999990001
      │
      ▼
   RESULTADO: ✓ Arquivo saiu do número correto!
```

---

## 🐛 Troubleshooting

### ❌ "Empresa não encontrada"

**Sintoma:** Erro ao tentar enviar para um contato

**Solução:**
```bash
# 1. Verificar nome da empresa na planilha
# Verificar campo "empresa" da planilha

# 2. Verificar empresas no MongoDB
uv run python -c "
from src.services.empresa_service import empresa_service
empresas = empresa_service.listar_todos()
for e in empresas:
    print(f\"- {e['nome']}\")
"

# 3. Atualizar planilha ou MongoDB para corresponder
```

### ❌ "Device desconectado"

**Sintoma:** Mensagem de erro sobre device offline

**Solução:**
```bash
# 1. Acessar painel de dispositivos
# http://localhost:3000/devices/list

# 2. Encontrar o device desconectado

# 3. Clicar em "Reconectar"
# e escanear QR Code novamente

# 4. Aguardar status "conectado"

# 5. Testar novamente
```

### ❌ "Sem device configurado"

**Sintoma:** Empresa envia pelo device padrão

**Solução:**
```bash
# 1. Verificar configuração
uv run python -c "
from src.services.empresa_service import empresa_service
empresa = empresa_service.buscar_por_nome('Empresa Cliente A')
print(f\"Device configurado: {empresa.get('whatsapp_device_id')}\")
"

# 2. Se vazio, adicionar device
# Via MongoDB Compass ou mongosh (ver passo acima)

# 3. Verificar se device está conectado
# http://localhost:3000/devices/list
```

### ❌ "Device ID inválido"

**Sintoma:** Erro de validação ao atualizar empresa

**Formato válido:**
```
DD(+código país)NÚMERO@s.whatsapp.net

Exemplos:
✅ 5511999990001@s.whatsapp.net
✅ 5511999990002@s.whatsapp.net
✅ 5585999990003@s.whatsapp.net

❌ 5511999990001 (falta @s.whatsapp.net)
❌ 5511999990001@whatsapp.com (domínio errado)
❌ 11 9999-90001@s.whatsapp.net (caracteres especiais)
```

**Solução:**
```bash
# Verificar formato do device_id no MongoDB
db.empresas.findOne({ nome: "Empresa Cliente A" })

# Copiar device_id correto de um conectado
db.empresas.find({ whatsapp_device_id: { $exists: true } })

# Atualizar com formato correto
```

---

## 📊 Checklist de Uso

- [ ] Conectar dispositivos WhatsApp (`http://localhost:3000`)
- [ ] Verificar dispositivos conectados (comando acima)
- [ ] Configurar todas as empresas com `whatsapp_device_id`
- [ ] Testar com envio de 1 folha de ponto
- [ ] Verificar logs para confirmar roteamento correto
- [ ] Testar com múltiplas empresas
- [ ] Validar planilha de contatos (campos corretos)
- [ ] Pronto para envio em produção!

---

## 📚 Referências

**Documentação Técnica:**
- `AGENTS.md` — visão geral do projeto e integrações
- `src/models/empresa_models.py` — Campo `whatsapp_device_id`
- `src/services/whatsapp_service.py` — Métodos com `device_id`
- `tests/test_whatsapp_multidevice.py` — Suíte de testes multidevice

**Dicas:**
- Verifique os logs em `logs/` para detalhes
- Use MongoDB Compass para inspecionar dados
- Execute testes para validar sistema

---

**Última atualização:** Agosto/2026
**Status:** ✅ Guia consolidado
