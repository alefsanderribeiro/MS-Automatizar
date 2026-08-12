# Modulo Folha de Ponto

**Versao:** v0.9.8
**Atualizado:** 2026-08-01

Sistema completo para geracao automatizada de folhas de ponto para funcionarios, com suporte a MongoDB, analise por IA e exportacao em PDF (HTML → WeasyPrint).

> **Nota:** Para envios com multiplos dispositivos WhatsApp, veja [ENVIO_FOLHAS_PONTO.md](ENVIO_FOLHAS_PONTO.md)

---

## Visao Geral

O módulo de Folha de Ponto permite:

- **Criação automatizada** de folhas de ponto com cálculo de dias úteis e feriados
- **Preenchimento inteligente** de dados (nome, cargo, departamento, horário)
- **Integração com MongoDB** para persistência e relacionamentos
- **Processamento de PDFs manuscritos** com IA (Gemini 2.5 Pro)
- **Filtros avançados** por ID, nome, lotação ou contrato
- **Exportação** em PDF
- **Integração com OneDrive** para acesso online aos dados

## 🏗️ Arquitetura

```
src/
├── folha_de_ponto.py              # Classe principal Folha_de_Ponto
├── comandos/
│   └── folha_de_ponto.py          # Comandos CLI (argparse)
├── interface/
│   └── interface_folha_de_ponto.py # Menu interativo
├── models/
│   ├── folha_de_ponto_models.py   # Models Pydantic para MongoDB
│   ├── funcionario_models.py      # Model de Funcionário
│   └── empresa_models.py          # Model de Empresa
├── services/
│   ├── cache_service.py           # CacheService (Redis + memória)
│   ├── funcionario_service.py     # CRUD de funcionários
│   ├── empresa_service.py         # CRUD de empresas
│   ├── contrato_service.py        # CRUD de contratos
│   ├── funcao_service.py          # CRUD de funções
│   ├── horario_service.py         # CRUD de horários
│   └── feriado_service.py         # CRUD de feriados
├── processadores/
│   └── processador_folha_ponto.py # Processamento com IA
└── utils/
    └── logger_config.py           # Configuração de logs
```

## 🚀 Uso via CLI

### Criar Folhas de Ponto

```bash
# Criar para todos os funcionários ativos
python automatizar.py folha_de_ponto criar --data 2026-01-14

# Filtrar por ID(s) específico(s)
python automatizar.py folha_de_ponto criar --id_funcionario 1,2,3 --data 2026-01-14

# Filtrar por nome(s)
python automatizar.py folha_de_ponto criar --nome_funcionario "João Silva,Maria Santos" --data 2026-01-14

# Filtrar por lotação
python automatizar.py folha_de_ponto criar --lotacao "ADMINISTRATIVO" --data 2026-01-14

# Filtrar por contrato
python automatizar.py folha_de_ponto criar --contrato "MS SERVIÇOS" --data 2026-01-14

# Especificar diretório de saída
python automatizar.py folha_de_ponto criar --data 2026-01-14 --diretorio_destino "C:\Folhas"
```

### Gerar DataFrame

```bash
# Exibir DataFrame no terminal
python automatizar.py folha_de_ponto gerar_dataframe

# Exportar para arquivo
python automatizar.py folha_de_ponto gerar_dataframe --diretorio_destino "C:\Exports"

# Manter em memória (para integração com outros sistemas)
python automatizar.py folha_de_ponto gerar_dataframe --memória True
```

### Análise de Folha Existente

```bash
python automatizar.py folha_de_ponto análise --arquivo "caminho/folha.xlsx"
```

### Operações MongoDB

```bash
# Processar e salvar em MongoDB
python automatizar.py folha_de_ponto mongodb --data 2026-01-14

# Filtrar por nome
python automatizar.py folha_de_ponto mongodb --nome_funcionario "João Silva" --data 2026-01-14

# Filtrar por lotação
python automatizar.py folha_de_ponto mongodb --lotacao "ADMINISTRATIVO" --data 2026-01-14
```

### Processar PDFs Manuscritos com IA

```bash
# Processar diretório com PDFs
python automatizar.py folha_de_ponto processar_pdf --diretorio "C:\PDFs"

# Processar arquivo único
python automatizar.py folha_de_ponto processar_pdf --arquivo "folha.pdf"

# Processar múltiplos arquivos
python automatizar.py folha_de_ponto processar_pdf --arquivos "folha1.pdf,folha2.pdf,folha3.pdf"
```

### Criar a partir do MongoDB

```bash
# Por IDs do MongoDB
python automatizar.py folha_de_ponto criar_mongodb_id \
    --funcionario_id "65abc123def456789" \
    --empresa_id "65xyz789abc123456" \
    --data 2026-01-14

# Por filtros
python automatizar.py folha_de_ponto criar_mongodb_filtro \
    --lotacao "ADMINISTRATIVO" \
    --ativo True \
    --data 2026-01-14
```

## 💻 Menu Interativo

Acesse através do menu principal:

```bash
python automatizar.py
# Opção 3 - Operações com Folha de Ponto
```

### Menu de Opções

```
╔═══════════════════════════════════════════════════╗
║   O que você deseja fazer com a Folha de Ponto?   ║
╠═══════════════════════════════════════════════════╣
║ 1 - Gerar Folha de Ponto (PDF + MongoDB)          ║
║ 2 - Processar PDFs Preenchidos com IA             ║
║ 3 - Ler/Exportar DataFrame                        ║
║ 4 - Enviar Folhas de Ponto (E-mail/WhatsApp)      ║
║ 0 - Voltar ao Menu Principal                      ║
╚═══════════════════════════════════════════════════╝
```

## 🔧 Configuração

### Variáveis de Ambiente

```env
# MongoDB
MONGO_URI=mongodb://localhost:27017
MONGO_DATABASE_NAME=MS_Automatizar

# OneDrive (opcional)
ONEDRIVE_URL_DADOS=https://1drv.ms/x/...
ONEDRIVE_URL_MODELOS=https://1drv.ms/x/...

# Google AI (para processamento de PDFs)
KEY_API_GEMINI=sua_chave_api
KEY_API_MISTRAL=sua_chave_mistral
```

### Planilha de Dados *(legado — modo Excel)*

> Desde a v0.9.7, a geração de folhas de ponto usa **somente MongoDB** como fonte de dados
> (a pipeline Excel → win32com foi removida). A planilha abaixo é referente apenas ao modo
> Excel legado (`MODO_OPERACAO=excel`), mantido para fins de compatibilidade.

O sistema lê dados de uma planilha Excel com as seguintes abas:

| Aba | Descrição |
|-----|-----------|
| `Funcionários` | Dados dos funcionários (nome, cargo, lotação, horário) |
| `Empresas` | Dados das empresas (nome, CNPJ, endereço) |
| `Feriados` | Lista de feriados nacionais e locais |
| `Horários` | Tabela de horários de trabalho |

## 📊 Estrutura de Dados MongoDB

### Collection: `funcionarios`

```json
{
  "_id": ObjectId("..."),
  "nome": "João da Silva",
  "pis": "123.45678.90-1",
  "lotacao": "ADMINISTRATIVO",
  "funcao_id": ObjectId("..."),
  "horario_id": ObjectId("..."),
  "empresas_ids": [ObjectId("...")],
  "contrato_empresa_id": ObjectId("..."),
  "status": "ativo",
  "criado_em": ISODate("...")
}
```

### Collection: `folha_de_ponto`

```json
{
  "_id": ObjectId("..."),
  "funcionario_id": ObjectId("..."),
  "empresa_id": ObjectId("..."),
  "mes_referencia": "2026-01",
  "status": "gerado",
  "folha_data": {
    "data_inicio": "2026-01-01",
    "data_fim": "2026-01-31",
    "total_horas_mes": "220:00",
    "total_faltas": 0,
    "total_feriados": 1,
    "dias": [...]
  },
  "data_criacao": ISODate("..."),
  "data_atualizacao": ISODate("...")
}
```

## 🤖 Processamento com IA

O sistema utiliza **Gemini 2.5 Pro** para processar PDFs manuscritos de folhas de ponto:

1. **Upload do PDF** via File API do Google
2. **Análise visual** do documento
3. **Extração estruturada** de dados com JSON Schema
4. **Validação** com modelos Pydantic
5. **Armazenamento** no MongoDB

### Dados Extraídos

- Nome do funcionário
- Período de referência
- Entradas e saídas diárias
- Faltas e justificativas
- Horas extras
- Observações

## 📁 Estrutura de Diretórios de Saída

```
{DIRETÓRIO BASE}\
└── {ANO}\
    └── {MÊS:02d}.{ANO}\
        └── {EMPRESA}\{LOTAÇÃO}\
            ├── Folha de Ponto - João Silva.pdf
            ├── Folha de Ponto - Maria Santos.pdf
            └── ...
```

## 🔄 Fluxo de Processamento

```
┌─────────────────┐
│ Fonte de Dados  │
│    (MongoDB)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Aplicar Filtros │
│ (ID/Nome/Lotação)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Calcular Dias   │
│ (Úteis/Feriados)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Renderizar HTML │
│ (template Jinja2)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Exportar PDF    │
│ (WeasyPrint)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Salvar MongoDB  │
│ (Registro)      │
└─────────────────┘
```

## 📚 Exemplos de Uso Programático

```python
from src.folha_de_ponto import Folha_de_Ponto
from datetime import date

# Instanciar classe
fp = Folha_de_Ponto()

# Criar folha a partir do MongoDB usando IDs
fp.criar_mongodb_por_id(
    funcionario_id="65abc123def456789",
    empresa_id="65xyz789abc123456",
    data=date(2026, 1, 14)
)

# Criar folhas por filtros
fp.criar_mongodb_por_filtros(
    filtros={"lotacao": "ADMINISTRATIVO", "status": "ativo"},
    data=date(2026, 1, 14),
    diretorio_destino="C:\\Folhas"
)

# Exportar DataFrame
fp.exportar_dataframe("C:\\Exports")
```

> **Nota**: A geração de PDF usa HTML → WeasyPrint. Não é necessário Microsoft Excel nem `win32com`.

## ⚠️ Troubleshooting

### Erro: "Funcionário não encontrado"
- Verifique se o funcionário está cadastrado no MongoDB ou na planilha
- Confira a ortografia do nome (busca é case-insensitive)

### Erro: "Empresa não vinculada"
- O funcionário precisa ter pelo menos uma empresa em `empresas_ids`
- Use o menu de gerenciamento para vincular empresas

### Erro ao gerar PDF
- Verifique se a dependência WeasyPrint está instalada: `uv add weasyprint`
- O sistema gera PDF via HTML → WeasyPrint (não precisa de Excel/win32com)

### MongoDB não disponível
- Verifique se o MongoDB está rodando em `localhost:27017`
- Confira a variável `MONGO_URI` no `.env`

---

## Documentacao Relacionada

- [Envio de Folhas de Ponto](ENVIO_FOLHAS_PONTO.md) - Sistema de envio automatizado (inclui suporte multidevice v0.9.5)
- [Holerite](HOLERITE.md) - Processamento de holerites
- [Envio de Holerites](ENVIO_HOLERITE.md) - Sistema de envio de holerites
- [README Principal](../README.md) - Visao geral do projeto
