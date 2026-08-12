# Modulo Holerite

**Versao:** v0.9.8
**Atualizado:** 2026-08-01

Sistema automatizado para processamento e renomeacao de recibos de pagamento (holerites), utilizando OCR e IA para extracao de nomes de funcionarios.

> **Nota:** Para envios com multiplos dispositivos WhatsApp, veja [ENVIO_HOLERITE.md](ENVIO_HOLERITE.md)

---

## Visao Geral

O módulo de Holerite permite:

- **Renomeação automática** de arquivos PDF de holerites para o nome do funcionário
- **Extração inteligente** de informações via OCR (Mistral) e IA (Gemini)
- **Cache MongoDB** para otimização de chamadas OCR
- **Processamento em lote** com suporte a threads paralelas
- **Filtro por período** (mês e ano) para organização de diretórios

## 🏗️ Arquitetura

```
src/
├── holerite.py                    # Classe principal Holerite
├── comandos/
│   └── holerite.py                # Comandos CLI (argparse)
├── interface/
│   └── interface_holerite.py      # Menu interativo
└── services/
    ├── analise_ai_service.py      # GeminiService, MistralService
    └── cache_service.py           # Cache OCR MongoDB
```

### Componentes Principais

| Componente | Responsabilidade |
|------------|------------------|
| `Holerite` | Classe principal, orquestra o processamento |
| `PdfProcessorService` | Extração de cabeçalhos de PDFs |
| `NomeExtractorOCR` | Extração de nomes via Mistral OCR |
| `NomeExtractorIA` | Extração de nomes via Gemini AI |
| `NomeExtractorComposite` | Combina OCR e IA com fallback |
| `DirectoryFilter` | Filtro de diretórios por critério |
| `ArquivoProcessor` | Processa arquivos individuais |

## 🚀 Uso via CLI

### Renomear Arquivos

```bash
# Renomear todos os PDFs de um diretório
python automatizar.py holerite renomear_arquivos --diretório "C:\Holerites\Janeiro"

# Filtrar por mês e ano (busca subpastas com o padrão MM.AAAA)
python automatizar.py holerite renomear_arquivos --diretório "C:\Holerites" --mês_ano "01.2026"
```

### Parâmetros

| Parâmetro | Descrição | Exemplo |
|-----------|-----------|---------|
| `--diretório` | Caminho do diretório com os PDFs | `"C:\Holerites"` |
| `--mês_ano` | Filtro no formato MM.AAAA | `"01.2026"` |

## 💻 Menu Interativo

Acesse através do menu principal:

```bash
python automatizar.py
# Opção 4 - Operações com Holerite
```

### Menu de Opções

```
╔════════════════════════════════════════════════════╗
║   O que você deseja fazer com o Holerite?          ║
╠════════════════════════════════════════════════════╣
║ 1 - Renomear arquivo(s)                            ║
║ 2 - Processar PDFs com IA (Gemini)                 ║
║ 3 - Enviar Holerites                               ║
║ 4 - Listar Holerites no MongoDB                    ║
║ 5 - Estatísticas do Cache OCR                      ║
║ 6 - Limpar Cache OCR (documentos antigos)          ║
║ 7 - Limpar todo o Cache OCR                        ║
║ 0 - Voltar ao Menu Principal                       ║
╚════════════════════════════════════════════════════╝
```

### Opção 1: Renomear Arquivos

1. Informe o diretório contendo os PDFs
2. (Opcional) Informe o mês/ano para filtrar subpastas
3. O sistema processa os arquivos e exibe o resultado

```
╔═══════════════════════════════════════════════╗
║         📋 RESULTADO DO PROCESSAMENTO         ║
╠═══════════════════════════════════════════════╣
║ ✓ Arquivos processados: 47                    ║
║ ✗ Arquivos com erro: 2                        ║
╚═══════════════════════════════════════════════╝
```

### Opção 2: Estatísticas do Cache

Exibe informações sobre o cache OCR:

```
════════════════════════════════════════════════════════
        📊 ESTATÍSTICAS DO CACHE OCR MONGODB           
════════════════════════════════════════════════════════
 ✓ Status: Conectado                                   
 ✓ Total de documentos: 1.250                          
 ✓ Tamanho total: 15.30 MB                             
 ✓ Banco de dados: MS_Automatizar                      
 ✓ Coleção: cache_ocr                                  
 ✓ Arquivos únicos: 1.180                              
════════════════════════════════════════════════════════
```

### Opção 3: Limpar Cache Antigo

Remove documentos do cache com mais de X dias:

```bash
Informe quantos dias para manter (ex: 30): 30

╔═══════════════════════════════════════════════╗
║      🧹 CACHE LIMPO COM SUCESSO             ║
╠═══════════════════════════════════════════════╣
║ ✓ Documentos removidos: 150                   ║
║ ✓ Mantendo documentos mais novos que 30 dias ║
╚═══════════════════════════════════════════════╝
```

### Opção 4: Limpar Todo o Cache

Remove todos os documentos do cache (com confirmação).

## 🔧 Configuração

### Variáveis de Ambiente

```env
# MongoDB (para cache OCR)
MONGO_URI=mongodb://localhost:27017
MONGO_DATABASE_NAME=MS_Automatizar

# Mistral AI (OCR primário)
KEY_API_MISTRAL=sua_chave_mistral

# Google AI (fallback)
KEY_API_GEMINI=sua_chave_google

# PDF → imagem (pypdfium2, embutido — não usa Poppler)
# Não é necessário instalar Poppler nem configurar poppler_path
```

### Dependências

| Biblioteca | Uso |
|------------|-----|
| `PyPDF2` | Manipulação de PDFs |
| `pypdfium2` | Conversão PDF → Imagem (embutido, cross-platform) |
| `pymongo` | Cache MongoDB |

## 🔄 Fluxo de Processamento

```
┌─────────────────┐
│   PDF Original  │
│ (nome genérico) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Extrair Cabeçalho│
│ (PdfProcessorService)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Verificar Cache │
│ (Hash SHA256)   │
└────────┬────────┘
         │
    ┌────┴────┐
    │ Cache?  │
    └────┬────┘
         │
    ┌────┴────┐
   HIT      MISS
    │         │
    ▼         ▼
┌───────┐ ┌─────────────┐
│ Usar  │ │ Chamar OCR  │
│ Cache │ │ (Mistral)   │
└───┬───┘ └──────┬──────┘
    │            │
    │       ┌────┴────┐
    │      OK      FALHOU
    │       │         │
    │       ▼         ▼
    │   ┌───────┐ ┌─────────┐
    │   │ Salvar│ │ Chamar  │
    │   │ Cache │ │ IA(Gemini)│
    │   └───┬───┘ └────┬────┘
    │       │          │
    └───────┴──────────┘
                │
                ▼
       ┌─────────────────┐
       │ Renomear Arquivo│
       │ → Nome Funcionário│
       └─────────────────┘
```

## 📊 Estrutura do Cache MongoDB

### Collection: `cache_ocr`

```json
{
  "_id": ObjectId("..."),
  "hash_arquivo": "sha256:abc123...",
  "nome_arquivo": "holerite_001.pdf",
  "resultado_ocr": "JOÃO DA SILVA",
  "data_criacao": ISODate("2026-01-14T10:30:00Z"),
  "modelo_utilizado": "mistral-ocr-2512",
  "confianca": 0.98
}
```

## 📁 Estrutura de Diretórios

### Entrada Esperada

```
{DIRETÓRIO}\
└── {MÊS}.{ANO}\
    ├── holerite_001.pdf
    ├── holerite_002.pdf
    └── ...
```

### Saída Gerada

```
{DIRETÓRIO}\
└── {MÊS}.{ANO}\
    ├── Recibo de Pagamento - João da Silva.pdf
    ├── Recibo de Pagamento - Maria Santos.pdf
    └── ...
```

## 📚 Uso Programático

```python
from src.holerite import Holerite

# Instanciar com diretório
holerite = Holerite(diretório="C:\\Holerites\\Janeiro")

# Renomear todos os arquivos
processados, erros = holerite.renomear_arquivos()
print(f"Processados: {processados}, Erros: {erros}")

# Com filtro de mês/ano
processados, erros = holerite.renomear_arquivos(mês_ano="01.2026")

# Ajustar número de workers
processados, erros = holerite.renomear_arquivos(max_workers=10)

# Usar threading ao invés de multiprocessing
processados, erros = holerite.renomear_arquivos(usar_multiprocessing=False)
```

### Manipulação do Cache

```python
from src.services.cache_ocr_service import cache_ocr

# Verificar disponibilidade
if cache_ocr and cache_ocr.disponivel:
    # Obter estatísticas
    stats = cache_ocr.obter_estatisticas()
    print(f"Total: {stats['total_documentos']} docs")
    
    # Listar últimos documentos
    ultimos = cache_ocr.listar_cache(limite=10)
    
    # Limpar cache antigo (mais de 30 dias)
    removidos = cache_ocr.limpar_cache_antigo(dias=30)
    
    # Limpar todo o cache
    cache_ocr.limpar_tudo()
```

## 🤖 Serviços de OCR e IA

### MistralService (OCR Primário)

```python
from src.services.analise_ai_service import MistralService

mistral = MistralService()

# OCR de imagem
nome = mistral.imagem("cabecalho.png")
print(f"Nome extraído: {nome}")
```

### GeminiService (Fallback)

```python
from src.services.analise_ai_service import GeminiService

gemini = GeminiService(model="gemini-2.5-pro")

# Análise com prompt customizado
prompt = "Me informa o nome completo do funcionário..."
nome = gemini.imagem("cabecalho.png", prompt)
```

## ⚡ Performance

### Processamento Paralelo

O sistema utiliza `ThreadPoolExecutor` ou `ProcessPoolExecutor` para processamento paralelo:

```python
# Usar multiprocessing (padrão) - melhor para CPU-bound
holerite.renomear_arquivos(max_workers=5, usar_multiprocessing=True)

# Usar threading - melhor para I/O-bound
holerite.renomear_arquivos(max_workers=10, usar_multiprocessing=False)
```

### Otimização com Cache

O cache MongoDB evita chamadas repetidas ao OCR:

- **Cache HIT**: ~1ms (busca no MongoDB)
- **Cache MISS**: ~2-5s (chamada ao Mistral OCR)

## ⚠️ Troubleshooting

### Erro: "Cache OCR não está disponível"
- Verifique se o MongoDB está rodando
- Confira a variável `MONGO_URI` no `.env`

### Erro: "Poppler não encontrado"
O projeto não usa Poppler — PDF → imagem é feito com `pypdfium2` (embutido).
Caso apareça erro de conversão, garanta a dependência: `uv add pypdfium2`.

### Erro: "Nome não extraído"
- O cabeçalho do PDF pode estar em formato diferente
- Ajuste as coordenadas em `coordenadas_cabecalho`

### Erro de Rate Limit (OCR)
- Reduza o número de `max_workers`
- Aguarde alguns minutos e tente novamente

### Arquivo não renomeado
- Verifique se o PDF está corrompido
- Confira se há permissão de escrita no diretório

---

## Documentacao Relacionada

- [Envio de Holerites](ENVIO_HOLERITE.md) - Sistema de envio de holerites (inclui suporte multidevice v0.9.5)
- [Folha de Ponto](FOLHA_DE_PONTO.md) - Geracao de folhas de ponto
- [Envio de Folhas de Ponto](ENVIO_FOLHAS_PONTO.md) - Sistema de envio de folhas de ponto
- [README Principal](../README.md) - Visao geral do projeto
