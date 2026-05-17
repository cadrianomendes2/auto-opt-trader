# 🤖 Binary Options AI — Dashboard de Trading Automatizado

Sistema web completo para gerenciar múltiplos bots de trading de opções binárias e derivativos na **Deriv API**. Cada bot opera como um agente independente com timeframe, estratégia e gestão de risco próprios, e todos são monitorados em tempo real através de um dashboard com dark theme.

---

## 📋 Índice

1. [Stack Tecnológica](#-stack-tecnológica)
2. [Pré-requisitos](#-pré-requisitos)
3. [Instalação](#-instalação)
4. [Configuração](#-configuração)
5. [Como Executar](#-como-executar)
6. [Estrutura de Diretórios](#-estrutura-de-diretórios)
7. [API Endpoints](#-api-endpoints)
8. [Testes](#-testes)
9. [Desenvolvimento e Contribuição](#-desenvolvimento-e-contribuição)
10. [⚡ Troubleshooting](#-troubleshooting)
11. [Licença](#-licença)

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia | Descrição |
|---|---|---|
| **Backend API** | Python 3.11 + FastAPI | Async nativo, WebSocket built-in |
| **Concorrência** | `asyncio` + `asyncio.Queue` | Multi-bot sem threading complexo |
| **Frontend** | HTML5 + CSS3 + Vanilla JS | SPA sem dependências pesadas |
| **Gráficos** | Chart.js 4.x | Gráficos de P&L em tempo real |
| **Banco de Dados** | SQLite via `aiosqlite` | Zero config, async, ideal para dados locais |
| **Config de Agentes** | JSON (`src/state/agents.json`) | Hot-reload sem reiniciar servidor |
| **Broker API** | Deriv WebSocket API | `wss://ws.binaryws.com/websockets/v3` |
| **Indicadores** | `ta` (Technical Analysis) | RSI, EMA, Bollinger em DataFrames |
| **Process Manager** | PM2 | Auto-restart, logs persistentes |
| **Dev Hot Reload** | `uvicorn --reload` | DX rápido durante desenvolvimento |

---

## ✅ Pré-requisitos

- **Python 3.11+** — [`python.org`](https://www.python.org/downloads/)
- **Conta Deriv** — [`deriv.com`](https://deriv.com) (conta real ou virtual/demo)
- **Token de API Deriv** — gerado no painel de configurações da conta
- **Node.js + PM2** (opcional) — apenas para execução em produção via PM2
- **Git**

### Obter Token da Deriv API

1. Acesse [app.deriv.com/account/api-token](https://app.deriv.com/account/api-token)
2. Clique em **"Create new token"**
3. Selecione as permissões: **Read**, **Trade**, **Payments** (pelo menos Read + Trade)
4. Copie o token gerado — ele será usado na variável `DERIV_API_TOKEN`

> ⚠️ **Use conta virtual (demo) para testes!** A conta virtual da Deriv tem saldo fictício e permite testar todas as funcionalidades sem risco de capital real.

---

## 🚀 Instalação

### 1. Clonar o repositório

```bash
git clone https://github.com/seu-usuario/binary-opt-ai.git
cd binary-opt-ai
```

### 2. Criar e ativar o ambiente virtual

```bash
# Criar venv
python3 -m venv .venv

# Ativar (macOS/Linux)
source .venv/bin/activate

# Ativar (Windows)
.venv\Scripts\activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar variáveis de ambiente

```bash
# Copiar o template
cp .env.example .env

# Editar com seu editor preferido
nano .env
# ou
code .env
```

---

## ⚙️ Configuração

Edite o arquivo `.env` na raiz do projeto:

```bash
# ============================================================
# Deriv API
# ============================================================
# Token da sua conta Deriv (real ou virtual)
DERIV_API_TOKEN=seu_token_aqui

# App ID da Deriv (use 1 para desenvolvimento/demo)
DERIV_APP_ID=1

# URL do WebSocket da Deriv (não altere em condições normais)
DERIV_WS_URL=wss://ws.binaryws.com/websockets/v3

# ============================================================
# Servidor
# ============================================================
HOST=0.0.0.0
PORT=8000
DEBUG=false

# ============================================================
# Database
# ============================================================
DB_PATH=src/state/trades.db
AGENTS_JSON_PATH=src/state/agents.json
```

### Variáveis de Ambiente — Referência Completa

| Variável | Obrigatória | Padrão | Descrição |
|---|---|---|---|
| `DERIV_API_TOKEN` | ✅ Sim | — | Token OAuth da Deriv API |
| `DERIV_APP_ID` | ✅ Sim | `1` | ID da aplicação registrada na Deriv |
| `DERIV_WS_URL` | Não | `wss://ws.binaryws.com/websockets/v3` | Endpoint WebSocket da Deriv |
| `HOST` | Não | `0.0.0.0` | Interface de rede do servidor |
| `PORT` | Não | `8000` | Porta HTTP do servidor |
| `DEBUG` | Não | `false` | Modo debug com logs extras |
| `DB_PATH` | Não | `src/state/trades.db` | Caminho para o banco de dados SQLite |
| `AGENTS_JSON_PATH` | Não | `src/state/agents.json` | Caminho para o estado dos agentes |

---

## ▶️ Como Executar

### Opção 1 — Desenvolvimento (uvicorn direto)

Recomendado durante o desenvolvimento. O `--reload` reinicia o servidor automaticamente ao detectar mudanças no código.

```bash
# Ativar venv (se ainda não estiver ativo)
source .venv/bin/activate

# Iniciar com hot reload
python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

O dashboard estará disponível em: **[http://localhost:8000](http://localhost:8000)**

A documentação automática da API (Swagger) estará em: **[http://localhost:8000/docs](http://localhost:8000/docs)**

### Opção 2 — Produção (PM2)

PM2 gerencia o processo com auto-restart, logs persistentes e inicialização automática no boot.

```bash
# Instalar PM2 globalmente (requer Node.js)
npm install -g pm2

# Iniciar com a configuração do ecosystem.config.js
pm2 start ecosystem.config.js

# Ver status dos processos
pm2 status

# Acompanhar logs em tempo real
pm2 logs binary-opt-ai

# Reiniciar sem downtime
pm2 reload binary-opt-ai

# Parar
pm2 stop binary-opt-ai

# Salvar configuração para auto-start no boot do sistema
pm2 save
pm2 startup
```

> **Nota sobre o `ecosystem.config.js`**: o campo `cwd` está configurado para o caminho absoluto `/Users/adrianomendes/Projects/binary-opt-ai`. Ajuste-o para o diretório correto na sua máquina antes de usar PM2.

### Verificar se está funcionando

```bash
# Health check
curl http://localhost:8000/api/v1/agents

# Ou abrir no browser
open http://localhost:8000
```

---

## 📁 Estrutura de Diretórios

```
binary-opt-ai/
│
├── src/
│   ├── main.py                    ← Entry point FastAPI (startup, routers, CORS)
│   │
│   ├── core/                      ← Lógica central dos bots
│   │   ├── agent_manager.py       ← Singleton que gerencia todas as BotTasks
│   │   ├── bot_task.py            ← Loop principal de cada bot (asyncio task)
│   │   ├── deriv_client.py        ← WebSocket Deriv: auth, candles, trade
│   │   ├── signal_generator.py    ← Estratégias: rsi_ema, bb_squeeze, etc.
│   │   └── risk_manager.py        ← Limites de risco e capital
│   │
│   ├── api/                       ← Camada HTTP/WebSocket
│   │   ├── routes_agents.py       ← CRUD de agentes (REST)
│   │   ├── routes_trades.py       ← Histórico e estatísticas de trades
│   │   ├── routes_models.py       ← Modelos preditivos
│   │   ├── routes_analytics.py    ← Analytics e conta
│   │   ├── routes_symbols.py      ← Símbolos disponíveis
│   │   └── websocket_hub.py       ← WebSocket Hub (broadcast para UI)
│   │
│   ├── models/                    ← Pydantic models
│   │   ├── agent_model.py         ← AgentConfig, AgentStatus, AgentState
│   │   └── trade_model.py         ← TradeRecord, TradeResult, TradeStats
│   │
│   ├── db/                        ← Camada de persistência
│   │   ├── database.py            ← init_db(), schema SQLite
│   │   └── trade_repository.py    ← CRUD de trades
│   │
│   ├── state/
│   │   ├── agents.json            ← Config e estado dos agentes (persistido)
│   │   └── trades.db              ← Banco SQLite (gerado automaticamente)
│   │
│   ├── logs/                      ← Logs do servidor (gerado automaticamente)
│   │
│   └── static/                    ← Frontend SPA
│       ├── index.html             ← Dashboard principal
│       ├── analytics.html         ← Página de analytics
│       ├── benchmark.html         ← Benchmark de modelos
│       ├── css/dashboard.css      ← Dark theme
│       └── js/
│           ├── app.js             ← Controlador principal
│           ├── ws-client.js       ← WebSocket com reconnect automático
│           ├── charts.js          ← Chart.js wrappers (P&L)
│           └── api.js             ← REST fetch helpers
│
├── tests/
│   ├── unit/                      ← Testes unitários
│   │   ├── test_risk_manager.py
│   │   ├── test_signal_generator.py
│   │   └── test_contract_logic.py
│   ├── integration/               ← Testes de integração
│   │   ├── test_api_agents.py
│   │   └── test_api_trades.py
│   ├── mocks/
│   │   └── deriv_mock.py          ← Mock da Deriv API para testes
│   └── conftest.py
│
├── reference/                     ← Documentação técnica de referência
│   ├── ARCHITECTURE.md            ← Arquitetura completa do sistema
│   ├── TRADING_BOT_KNOWLEDGE_BASE.md
│   └── strategies/
│
├── ecosystem.config.js            ← Configuração PM2
├── requirements.txt               ← Dependências de produção
├── requirements-dev.txt           ← Dependências de desenvolvimento/testes
├── pytest.ini                     ← Configuração do pytest
├── .env.example                   ← Template de variáveis de ambiente
└── .gitignore
```

---

## 🌐 API Endpoints

**Base URL**: `http://localhost:8000/api/v1`

**Documentação interativa**: `http://localhost:8000/docs` (Swagger UI)

### Agentes

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/agents` | Lista todos os agentes com stats atuais |
| `GET` | `/agents/{id}` | Detalhes completos de um agente |
| `POST` | `/agents` | Cria e inicia um novo agente |
| `PUT` | `/agents/{id}` | Atualiza configuração (reinicia bot) |
| `DELETE` | `/agents/{id}` | Para e remove um agente |
| `POST` | `/agents/{id}/pause` | Pausa um agente |
| `POST` | `/agents/{id}/resume` | Retoma um agente pausado |
| `POST` | `/agents/{id}/reset-stats` | Zera counters de runtime |

### Trades

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/trades` | Lista trades com paginação e filtros |
| `GET` | `/trades/stats` | Estatísticas agregadas (win rate, P&L, etc.) |
| `GET` | `/trades/pnl-history` | Série temporal de P&L para gráficos |

### Símbolos e Modelos

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/symbols` | Lista símbolos disponíveis na Deriv |
| `GET` | `/models` | Lista modelos preditivos disponíveis |
| `GET` | `/analytics/...` | Analytics e dados da conta |

### WebSocket

| Endpoint | Descrição |
|---|---|
| `ws://localhost:8000/ws` | Conexão em tempo real (push de eventos) |

**Eventos WebSocket (server → client)**:
- `full_state` — Estado completo enviado na conexão inicial
- `agent_update` — Atualização de stats de um agente
- `trade_executed` — Novo trade aberto
- `trade_closed` — Trade finalizado com resultado
- `agent_status_changed` — Mudança de status do agente

---

## 🧪 Testes

### Instalar dependências de desenvolvimento

```bash
pip install -r requirements-dev.txt
```

### Executar todos os testes

```bash
pytest
```

### Executar com saída detalhada

```bash
pytest -v
```

### Executar apenas testes unitários

```bash
pytest tests/unit/ -v
```

### Executar apenas testes de integração

```bash
pytest tests/integration/ -v
```

### Executar um arquivo específico

```bash
pytest tests/unit/test_risk_manager.py -v
pytest tests/unit/test_signal_generator.py -v
```

### Verificar cobertura de código

```bash
# Requer pytest-cov (incluído no requirements-dev.txt)
pytest --cov=src --cov-report=term-missing
```

### Estrutura dos testes

```
tests/
├── unit/
│   ├── test_risk_manager.py       ← Testa can_trade(), limites de risco
│   ├── test_signal_generator.py   ← Testa geração de sinais RSI, BB, etc.
│   └── test_contract_logic.py     ← Testa lógica de contratos
├── integration/
│   ├── test_api_agents.py         ← Testa CRUD REST de agentes
│   └── test_api_trades.py         ← Testa endpoints de trades
├── mocks/
│   └── deriv_mock.py              ← Mock WebSocket para testes sem API real
└── conftest.py                    ← Fixtures compartilhadas (pytest)
```

> Os testes de integração usam um banco de dados SQLite em memória e um mock da Deriv API — **nenhuma conexão real** é feita durante os testes.

---

## 👨‍💻 Desenvolvimento e Contribuição

### Configurar ambiente de desenvolvimento

```bash
# 1. Clonar e instalar dependências (produção + dev)
git clone https://github.com/seu-usuario/binary-opt-ai.git
cd binary-opt-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 2. Configurar .env
cp .env.example .env
# Editar .env com seu token Deriv

# 3. Iniciar em modo desenvolvimento
python3 -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Testar conexão com a Deriv API

```bash
# Script de teste de conexão incluído no projeto
python3 src/test_connection.py
```

### Adicionar um agente padrão via script

```bash
python3 src/create_default_agents.py
```

### Estratégias disponíveis

| ID | Nome | Indicadores | Parâmetros |
|---|---|---|---|
| `rsi_ema` | RSI Extremo + EMA | RSI < 25 ou > 75 + cruzamento EMA 9/21 | `rsi_period`, `rsi_oversold`, `rsi_overbought`, `ema_fast`, `ema_slow` |
| `bb_squeeze` | Bollinger Band Squeeze | BB squeeze + breakout | `bb_period`, `bb_std`, `squeeze_threshold_pct` |
| `stochrsi` | StochRSI Extremo | StochRSI oversold/overbought | `rsi_length`, `k_period`, `d_period` |
| `ema_pullback` | EMA Crossover + Pullback | Pullback para EMA após cruzamento | `ema_fast`, `ema_slow`, `ema_filter` |
| `coin_flip` | Aleatório (baseline) | Sinal 50/50 aleatório | — |

---

## ⚡ Troubleshooting

Esta secção documenta os problemas mais comuns encontrados durante o desenvolvimento e operação do sistema. **Leia com atenção antes de reportar bugs.**

---

### ❌ Problema 1: Contratos sempre fechando por timeout (sell forçado)

**Sintoma nos logs:**
```
Timeout (300s) aguardando contrato 123456789. Forçando sell...
```

**Causa:**

O problema ocorre especificamente com contratos do tipo **Multiplier** da Deriv. Diferentemente dos contratos Rise/Fall (que expiram numa data/hora fixa), contratos Multiplier **não expiram por duração** — eles só fecham quando:
- O **Take Profit (TP)** é atingido, ou
- O **Stop Loss (SL)** é atingido, ou
- O trader vende manualmente

Se o TP e o SL forem definidos com valores muito agressivos (ex: TP de 100% ou SL muito abaixo do preço atual), em mercados lateralizados o contrato pode ficar aberto por muito mais tempo do que os 300 segundos de timeout configurados no bot. Quando isso acontece, o bot força o fechamento via sell — que quase sempre resulta em perda.

**Solução:**

1. **Ajuste o `take_profit` e `stop_loss`** nos parâmetros do agente para valores realistas dado o timeframe. Exemplos:
   - Para timeframe de 2 minutos: TP de 2–5%, SL de 1–3%
   - Para timeframe de 5 minutos: TP de 3–8%, SL de 2–5%

2. **Considere usar contratos Rise/Fall** em vez de Multiplier para estratégias de curto prazo. Rise/Fall expiram no tempo exato configurado, independentemente do preço, e são mais adequados para scalping automatizado.

3. **Aumente o timeout** no `deriv_client.py` se precisar manter Multipliers:
   ```python
   # Aumentar de 300s para valor maior (ex: 600s para timeframe de 10min)
   TIMEOUT_SECONDS = 600
   ```

---

### ❌ Problema 2: Risk Manager bloqueando após 5 perdas consecutivas

**Sintoma nos logs:**
```
Trade bloqueado pelo risco: Limite de perdas consecutivas atingido: 5
```

**Causa:**

O `RiskManager` tem uma proteção legítima que bloqueia novas operações após `max_consecutive_losses` perdas consecutivas (configurado como 5 por padrão). No entanto, se o **Problema 1** (sell forçado por timeout) não estiver resolvido, cada venda forçada resulta em perda, tornando as 5 perdas consecutivas inevitáveis — e o bloqueio passa a ser um sintoma do problema anterior, não uma proteção útil.

**Solução:**

1. **Resolver primeiro o Problema 1.** Após corrigir o comportamento dos contratos, o bloqueio voltará a ser uma proteção legítima.

2. Para **desbloquear manualmente** um agente após investigação:
   ```bash
   # Via API REST
   curl -X POST http://localhost:8000/api/v1/agents/agent-2min/reset-stats
   curl -X POST http://localhost:8000/api/v1/agents/agent-2min/resume
   ```

3. Para **ajustar o limite** de perdas consecutivas no `agents.json`:
   ```json
   "risk": {
     "max_consecutive_losses": 10
   }
   ```

> ⚠️ **Atenção**: Aumentar o limite de perdas consecutivas sem resolver a causa raiz pode resultar em perdas maiores. Investigue sempre o motivo das perdas antes de ajustar os limites.

---

### ❌ Problema 3: Todos os contratos resultando em perda mesmo com estratégia aleatória (`coin_flip`)

**Sintoma nos logs:**
```
result=lost  profit=-2.00  strategy=coin_flip
result=lost  profit=-5.00  strategy=coin_flip
result=lost  profit=-2.00  strategy=coin_flip
```

**Causa:**

Este é um problema estrutural relacionado ao **tipo de contrato + método de exit**. Uma estratégia `coin_flip` deveria ter 50% de ganhos e 50% de perdas, então resultados de 100% de perda indicam que o problema não está na estratégia, mas na **mecânica de fechamento**.

Quando um contrato **Multiplier** é vendido antes da expiração natural (sell forçado — veja Problema 1), o valor recebido é `sold_for`, que é **menor do que o `buy_price`** pago. Isso acontece por dois motivos:

- **Spread**: diferença entre preço de compra e venda
- **Financing charge**: custo de manutenção do contrato Multiplier que é cobrado a cada hora

Em resumo: **usar timeout como estratégia de exit em contratos Multiplier perde dinheiro estruturalmente**, independente da direção do mercado.

**Solução:**

1. **Usar TP/SL realistas** em contratos Multiplier, permitindo que fechem naturalmente.

2. **Migrar para contratos Rise/Fall** (ou Up/Down) para estratégias de curto prazo. Nestes contratos:
   - O resultado é determinado exclusivamente na expiração
   - Não existe "sell forçado" com perda garantida
   - O payout é fixo: ganho ou perda total do stake

3. **Comparativo prático:**
   ```
   Rise/Fall:  stake=$2, payout=80% → ganho=$1.60 ou perda=$2.00
   Multiplier: stake=$2, sell forçado → sold_for ≈ $1.60–1.90 (sempre perde)
   ```

---

### ❌ Problema 4: WebSocket desconectando frequentemente

**Sintoma nos logs:**
```
Cliente desconectou normalmente
Total de conexões ativas: 0
```

**Causa:**

Este comportamento é **completamente normal**. O browser fecha a conexão WebSocket ao:
- Navegar para outra página
- Fechar a aba
- Perder conexão de rede momentaneamente
- Colocar o computador em sleep

O `WSClient` no frontend (`src/static/js/ws-client.js`) tem **reconexão automática** com exponential backoff implementada.

**Como verificar:**

1. Abra o Console do browser (F12)
2. Ao navegar de volta para o dashboard, você deverá ver:
   ```
   [WS] Conectado
   ```
   em menos de 5 segundos.

3. Se a reconexão não ocorrer em <5s, verifique:
   - Se o servidor ainda está rodando (`pm2 status` ou `ps aux | grep uvicorn`)
   - Logs de erro no console do browser
   - Se há erros de CORS (`Access-Control-Allow-Origin`)

**Solução** (se a reconexão não estiver ocorrendo):

```bash
# Verificar se o servidor está rodando
pm2 status

# Verificar logs de erro
pm2 logs binary-opt-ai --err

# Reiniciar se necessário
pm2 restart binary-opt-ai
```

---

### ❌ Problema 5: `sqlite3.OperationalError: database is locked`

**Sintoma nos logs:**
```
sqlite3.OperationalError: database is locked
```

**Causa:**

SQLite tem suporte limitado a escritas concorrentes. Quando múltiplos agentes tentam escrever no banco de dados simultaneamente (ex: 5 agentes fechando trades ao mesmo tempo), pode ocorrer contenção.

**Soluções:**

1. **Verificar o uso de `asyncio.Lock()`**: O código usa um lock global para operações de escrita no `agents.json`. Verifique se o `trade_repository.py` também está protegendo as escritas críticas:
   ```python
   # Deve estar presente em trade_repository.py
   _db_lock = asyncio.Lock()
   
   async def insert_trade(trade_data: dict):
       async with _db_lock:
           async with aiosqlite.connect(DB_PATH) as db:
               # ...
   ```

2. **Configurar WAL mode** no SQLite (Write-Ahead Logging), que permite múltiplos leitores simultâneos:
   ```python
   # Em src/db/database.py, após conectar:
   await db.execute("PRAGMA journal_mode=WAL")
   await db.execute("PRAGMA synchronous=NORMAL")
   ```

3. **Migrar para `aiosqlite`** se ainda não estiver sendo usado (já listado no `requirements.txt`). Garante que todas as operações de banco são verdadeiramente assíncronas.

4. Se o problema persistir, considere adicionar retry com backoff:
   ```python
   import asyncio
   
   async def execute_with_retry(db, query, params, max_retries=3):
       for attempt in range(max_retries):
           try:
               await db.execute(query, params)
               return
           except Exception as e:
               if "locked" in str(e) and attempt < max_retries - 1:
                   await asyncio.sleep(0.1 * (attempt + 1))
               else:
                   raise
   ```

---

### 🔍 Outros problemas comuns

| Problema | Possível Causa | Verificação |
|---|---|---|
| `401 Unauthorized` na Deriv | Token inválido ou expirado | Gerar novo token em [app.deriv.com/account/api-token](https://app.deriv.com/account/api-token) |
| Agentes não iniciam após restart | `agents.json` corrompido | Verificar syntax JSON; o backup `agents.bak` é criado automaticamente |
| Dashboard vazio (sem agentes) | `src/state/agents.json` não existe ou está vazio | Executar `python3 src/create_default_agents.py` |
| Port 8000 já em uso | Outro processo usando a porta | `lsof -i :8000` e `kill -9 <PID>` |
| `ModuleNotFoundError` | Venv não ativado ou deps não instaladas | `source .venv/bin/activate && pip install -r requirements.txt` |

---

## 📄 Licença

MIT License — veja o arquivo `LICENSE` para detalhes.

---

*Projeto desenvolvido em Maio 2026 | Versão 1.0.0*
