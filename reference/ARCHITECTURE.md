# 🏗️ ARCHITECTURE — binary-opt-ai Dashboard

> **Documento de Arquitetura Técnica Completa**
> Projeto: `binary-opt-ai` | Versão: 1.0 | Maio 2026

---

## ÍNDICE

1. [Visão Geral](#1-visão-geral)
2. [Diagrama de Componentes](#2-diagrama-de-componentes)
3. [Estrutura de Arquivos](#3-estrutura-de-arquivos)
4. [Modelos de Dados](#4-modelos-de-dados)
5. [Fluxo de Dados — Ciclo de Trade](#5-fluxo-de-dados--ciclo-de-trade)
6. [API REST Endpoints](#6-api-rest-endpoints)
7. [WebSocket Messages (Frontend ↔ Backend)](#7-websocket-messages-frontend--backend)
8. [Gerenciamento de Estado dos Bots](#8-gerenciamento-de-estado-dos-bots)
9. [Estratégia de Persistência](#9-estratégia-de-persistência)
10. [Plano de Resiliência](#10-plano-de-resiliência)
11. [Configuração do PM2](#11-configuração-do-pm2)
12. [Sequência de Implementação](#12-sequência-de-implementação)

---

## 1. Visão Geral

### 1.1 Objetivo

Sistema web de dashboard para gerenciar múltiplos bots de trading de opções binárias na **Deriv API**, rodando simultaneamente com timeframes e stakes distintos, com interface visual em dark theme inspirada em plataformas profissionais de trading.

### 1.2 Stack Tecnológica

| Camada | Tecnologia | Justificativa |
|---|---|---|
| **Backend API** | Python 3.11 + FastAPI | Async nativo, WebSocket built-in, alta performance |
| **Asyncio Tasks** | `asyncio` + `asyncio.Queue` | Multi-bot concorrente sem threading complexo |
| **Frontend** | HTML5 + CSS3 + Vanilla JS | Sem dependências pesadas; total controle |
| **Gráficos** | Chart.js 4.x | Leve, responsivo, ótimo para linha do tempo |
| **Banco de Dados** | SQLite via `aiosqlite` | Zero config, async, ideal para dados locais |
| **Config de Agentes** | JSON (`src/state/agents.json`) | Hot-reload sem reiniciar servidor |
| **WebSocket Deriv** | `websockets` lib | Conexão persistente com `wss://ws.binaryws.com` |
| **Real-time Frontend** | WebSocket (FastAPI) | Bidirecional, eficiente para updates frequentes |
| **Process Manager** | PM2 | Auto-restart, logs persistentes, cluster mode |
| **Dev Hot Reload** | `uvicorn --reload` | DX rápido durante desenvolvimento |
| **Indicadores** | `pandas-ta` | Cálculo de RSI, EMA, Bollinger em DataFrames |

### 1.3 Configuração dos Agentes Padrão

| Agente | Timeframe | Stake | Granularidade Deriv |
|---|---|---|---|
| Agent-2min | 2 min | $2 | 120s |
| Agent-5min | 5 min | $5 | 300s |
| Agent-10min | 10 min | $10 | 600s |
| Agent-15min | 15 min | $15 | 900s |
| Agent-30min | 30 min | $30 | 1800s |

---

## 2. Diagrama de Componentes

### 2.1 Arquitetura Geral

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           BROWSER (localhost:8000)                       │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                     Dashboard UI (SPA)                           │    │
│  │                                                                   │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │    │
│  │  │  Agent Cards │  │  Chart.js    │  │  CRUD Modal Forms      │ │    │
│  │  │  (status,    │  │  (P&L Line   │  │  (criar/editar/        │ │    │
│  │  │  P&L, trades)│  │  comparativo)│  │   deletar agentes)     │ │    │
│  │  └──────┬───────┘  └──────┬───────┘  └───────────┬────────────┘ │    │
│  │         └─────────────────┴──────────────────────┘              │    │
│  │                           │                                       │    │
│  │              WebSocket Client (ws://localhost:8000/ws)            │    │
│  │              REST Client (fetch API)                              │    │
│  └───────────────────────────┬───────────────────────────────────────┘    │
└──────────────────────────────┼──────────────────────────────────────────┘
                               │ WS + REST/HTTP
┌──────────────────────────────▼──────────────────────────────────────────┐
│                      FASTAPI SERVER (uvicorn)                            │
│                                                                           │
│  ┌─────────────┐  ┌──────────────────┐  ┌─────────────────────────┐    │
│  │  REST API   │  │  WebSocket Hub   │  │  Static File Server     │    │
│  │  /api/v1/*  │  │  /ws             │  │  /static (HTML/CSS/JS)  │    │
│  └──────┬──────┘  └────────┬─────────┘  └─────────────────────────┘    │
│         │                   │                                             │
│  ┌──────▼───────────────────▼────────────────────────────────────────┐  │
│  │                    AgentManager (Singleton)                         │  │
│  │                                                                     │  │
│  │  - Carrega agents.json na inicialização                             │  │
│  │  - Spawna/cancela asyncio.Task por agente                          │  │
│  │  - Mantém dicionário {agent_id: BotTask}                           │  │
│  │  - Broadcast de eventos para WebSocket Hub                          │  │
│  └───────────────────────────┬───────────────────────────────────────┘  │
│                               │ spawna N tasks                            │
│  ┌────────────────────────────▼─────────────────────────────────────┐   │
│  │              BotTask Pool (asyncio concurrent tasks)              │   │
│  │                                                                    │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ...         │   │
│  │  │ BotTask     │  │ BotTask     │  │ BotTask     │              │   │
│  │  │ agent-2min  │  │ agent-5min  │  │ agent-10min │              │   │
│  │  │             │  │             │  │             │              │   │
│  │  │ DerivWS     │  │ DerivWS     │  │ DerivWS     │              │   │
│  │  │ SignalGen   │  │ SignalGen   │  │ SignalGen   │              │   │
│  │  │ RiskMgr     │  │ RiskMgr     │  │ RiskMgr     │              │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │   │
│  └─────────┼────────────────┼────────────────┼───────────────────┘   │
│            │                │                │                         │
│  ┌─────────▼────────────────▼────────────────▼───────────────────┐   │
│  │                    Persistence Layer                             │   │
│  │                                                                  │   │
│  │  ┌──────────────────┐        ┌─────────────────────────────┐   │   │
│  │  │  agents.json     │        │  trades.db (SQLite/aiosqlite)│   │   │
│  │  │  (config/estado) │        │  (histórico completo)        │   │   │
│  │  └──────────────────┘        └─────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                               │
                               │ wss:// (por agente)
┌──────────────────────────────▼──────────────────────────────────────────┐
│              DERIV API (wss://ws.binaryws.com/websockets/v3)             │
│                                                                           │
│  authorize → ticks_history → proposal → buy → proposal_open_contract    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Diagrama de Módulos Python

```
src/
├── main.py                   ← Ponto de entrada FastAPI
│
├── core/
│   ├── agent_manager.py      ← Singleton que gerencia todas as BotTasks
│   ├── bot_task.py           ← Classe principal de cada bot (asyncio task)
│   ├── deriv_client.py       ← Wrapper WebSocket da Deriv API
│   ├── signal_generator.py   ← Estratégias (RSI, BB, EMA, etc.)
│   └── risk_manager.py       ← Limites de capital e stops
│
├── api/
│   ├── routes_agents.py      ← CRUD de agentes (REST)
│   ├── routes_trades.py      ← Histórico e estatísticas (REST)
│   └── websocket_hub.py      ← WebSocket Hub (broadcast para UI)
│
├── models/
│   ├── agent_model.py        ← Pydantic models de Agent
│   └── trade_model.py        ← Pydantic models de Trade
│
├── db/
│   ├── database.py           ← Conexão aiosqlite + init schema
│   └── trade_repository.py   ← CRUD de trades no SQLite
│
├── state/
│   ├── agents.json           ← Persistência de config/estado dos agentes
│   └── .gitkeep
│
└── static/
    ├── index.html            ← Dashboard SPA
    ├── css/
    │   └── dashboard.css     ← Dark theme, grid layout
    └── js/
        ├── app.js            ← Controlador principal
        ├── ws-client.js      ← WebSocket client
        ├── charts.js         ← Chart.js wrappers
        └── api.js            ← REST fetch helpers
```

---

## 3. Estrutura de Arquivos

```
binary-opt-ai/
│
├── src/
│   ├── main.py                         ← FastAPI app, startup/shutdown hooks
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent_manager.py            ← Singleton: start/stop/reload agentes
│   │   ├── bot_task.py                 ← Loop principal de cada bot
│   │   ├── deriv_client.py             ← WebSocket Deriv: auth, candles, trade
│   │   ├── signal_generator.py         ← Estratégias: rsi_ema, bb_squeeze, stochrsi
│   │   └── risk_manager.py             ← can_trade(), get_stake(), daily limits
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes_agents.py            ← GET/POST/PUT/DELETE /api/v1/agents
│   │   ├── routes_trades.py            ← GET /api/v1/trades, /stats
│   │   └── websocket_hub.py            ← WS /ws + ConnectionManager broadcast
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── agent_model.py              ← AgentConfig, AgentStatus, AgentState
│   │   └── trade_model.py              ← TradeRecord, TradeResult
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py                 ← init_db(), get_db(), schema SQL
│   │   └── trade_repository.py         ← insert_trade(), get_trades_by_agent()
│   │
│   ├── state/
│   │   ├── agents.json                 ← Config + estado persistido dos agentes
│   │   └── .gitkeep
│   │
│   ├── logs/
│   │   └── .gitkeep                    ← Logs por agente (agent-{id}.log)
│   │
│   ├── static/
│   │   ├── index.html                  ← Dashboard SPA
│   │   ├── css/
│   │   │   └── dashboard.css           ← Dark theme profissional
│   │   └── js/
│   │       ├── app.js                  ← Inicialização e orquestração UI
│   │       ├── ws-client.js            ← WebSocket auto-reconnect client
│   │       ├── charts.js               ← Chart.js: P&L linha + comparativo
│   │       └── api.js                  ← fetch helpers para REST
│   │
│   └── test_connection.py              ← [EXISTENTE] Teste de conexão Deriv
│
├── reference/
│   ├── ARCHITECTURE.md                 ← [ESTE ARQUIVO]
│   ├── TRADING_BOT_KNOWLEDGE_BASE.md
│   └── strategies/
│       └── binary-options-strategies.md
│
├── ecosystem.config.js                 ← Configuração PM2
├── requirements.txt                    ← Dependências Python
├── .env                                ← Variáveis de ambiente (token, app_id)
├── .env.example                        ← Template de variáveis
├── .gitignore
└── README.md
```

### 3.1 Responsabilidades por Arquivo

| Arquivo | Responsabilidade |
|---|---|
| `src/main.py` | Inicializa FastAPI, registra routers, monta `/static`, startup hook que carrega `agents.json` e inicia bots |
| `src/core/agent_manager.py` | Singleton global; métodos `start_agent()`, `stop_agent()`, `pause_agent()`, `reload_config()`; mantém mapa `{agent_id → asyncio.Task}` |
| `src/core/bot_task.py` | Classe `BotTask` com loop `async def run()`; busca velas → gera sinal → executa trade → persiste → notifica hub |
| `src/core/deriv_client.py` | Gerencia conexão WebSocket com Deriv; métodos `authorize()`, `get_candles()`, `get_proposal()`, `buy_contract()`, `subscribe_contract()`; reconnect automático |
| `src/core/signal_generator.py` | Funções puras: `generate_signal(df, strategy) → str`; estratégias: `rsi_ema`, `bb_squeeze`, `stochrsi`, `ema_pullback` |
| `src/core/risk_manager.py` | `RiskManager(capital)`; métodos `can_trade()`, `get_stake()`, `update(profit)`, `reset_daily()` |
| `src/api/routes_agents.py` | CRUD REST de agentes; ao criar/editar/deletar, chama `AgentManager` e salva `agents.json` |
| `src/api/routes_trades.py` | GET histórico de trades por agente, estatísticas agregadas (win rate, P&L total) |
| `src/api/websocket_hub.py` | `ConnectionManager`: lista de WS ativos; `broadcast(message)`; endpoint `/ws` |
| `src/models/agent_model.py` | Pydantic: `AgentConfig`, `AgentStatus` (enum), `AgentState` (config + runtime stats) |
| `src/models/trade_model.py` | Pydantic: `TradeRecord`, `TradeResult`, `TradeStats` |
| `src/db/database.py` | `init_db()` cria tabelas; `get_db()` context manager para `aiosqlite` |
| `src/db/trade_repository.py` | `insert_trade()`, `get_trades_by_agent()`, `get_agent_stats()`, `get_pnl_history()` |
| `src/static/index.html` | Estrutura HTML: grid de cards + modais CRUD + área de gráficos |
| `src/static/js/ws-client.js` | WebSocket com reconnect exponential backoff; `onMessage` dispatch por tipo |
| `src/static/js/charts.js` | `initPnlChart(agentId)`, `updatePnlChart(data)`, `initComparativeChart()` |
| `src/static/js/app.js` | Renderiza cards, gerencia estado local, conecta WS e REST |
| `ecosystem.config.js` | PM2 config: `binary-opt-ai`, `--workers 1`, logs, auto-restart |

---

## 4. Modelos de Dados

### 4.1 Schema JSON — `src/state/agents.json`

```json
{
  "version": "1.0",
  "last_updated": "2026-05-03T14:00:00Z",
  "agents": [
    {
      "id": "agent-2min",
      "name": "Scalper 2min",
      "enabled": true,
      "symbol": "R_75",
      "timeframe_minutes": 2,
      "stake": 2.0,
      "strategy": "rsi_ema",
      "strategy_params": {
        "rsi_period": 14,
        "rsi_oversold": 25,
        "rsi_overbought": 75,
        "ema_fast": 9,
        "ema_slow": 21
      },
      "risk": {
        "daily_loss_limit_pct": 0.10,
        "daily_win_target_pct": 0.20,
        "max_consecutive_losses": 5,
        "risk_per_trade_pct": 0.02
      },
      "status": "running",
      "runtime": {
        "total_trades": 42,
        "wins": 25,
        "losses": 17,
        "total_pnl": 18.50,
        "consecutive_losses": 0,
        "last_trade_at": "2026-05-03T13:55:00Z",
        "started_at": "2026-05-03T10:00:00Z",
        "paused_at": null,
        "error_message": null
      }
    },
    {
      "id": "agent-5min",
      "name": "Swing 5min",
      "enabled": true,
      "symbol": "R_75",
      "timeframe_minutes": 5,
      "stake": 5.0,
      "strategy": "bb_squeeze",
      "strategy_params": {
        "bb_period": 20,
        "bb_std": 2.0,
        "squeeze_threshold_pct": 0.80
      },
      "risk": {
        "daily_loss_limit_pct": 0.10,
        "daily_win_target_pct": 0.20,
        "max_consecutive_losses": 5,
        "risk_per_trade_pct": 0.02
      },
      "status": "running",
      "runtime": {
        "total_trades": 18,
        "wins": 11,
        "losses": 7,
        "total_pnl": 22.00,
        "consecutive_losses": 1,
        "last_trade_at": "2026-05-03T13:50:00Z",
        "started_at": "2026-05-03T10:00:00Z",
        "paused_at": null,
        "error_message": null
      }
    }
  ]
}
```

**Campos de `status` possíveis:**

| Valor | Descrição |
|---|---|
| `"running"` | Bot ativo, operando normalmente |
| `"paused"` | Pausado manualmente; mantém config e stats |
| `"stopped"` | Parado; task cancelada |
| `"error"` | Parado por erro; `error_message` preenchido |
| `"limit_hit"` | Parado automaticamente por atingir limite de risco |

---

### 4.2 Schema SQLite — `trades.db`

#### Tabela: `agents`

```sql
CREATE TABLE agents (
    id          TEXT PRIMARY KEY,         -- "agent-2min"
    name        TEXT NOT NULL,
    symbol      TEXT NOT NULL DEFAULT 'R_75',
    timeframe   INTEGER NOT NULL,          -- minutos
    stake       REAL NOT NULL,
    strategy    TEXT NOT NULL,
    created_at  TEXT NOT NULL,             -- ISO 8601
    updated_at  TEXT NOT NULL
);
```

#### Tabela: `trades`

```sql
CREATE TABLE trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL REFERENCES agents(id),
    contract_id     TEXT NOT NULL UNIQUE,   -- ID da Deriv
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL,           -- "CALL" | "PUT"
    stake           REAL NOT NULL,
    payout          REAL,                    -- payout recebido se ganhou
    ask_price       REAL NOT NULL,           -- preço pago
    result          TEXT,                    -- "won" | "lost" | "pending"
    profit          REAL,                    -- positivo (ganho) ou negativo (perda)
    entry_price     REAL,                    -- preço de entrada
    exit_price      REAL,                    -- preço na expiração
    strategy        TEXT NOT NULL,
    signal_meta     TEXT,                    -- JSON com dados do sinal (RSI val, etc.)
    opened_at       TEXT NOT NULL,           -- ISO 8601
    closed_at       TEXT,                    -- NULL enquanto aberto
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_trades_agent_id ON trades(agent_id);
CREATE INDEX idx_trades_opened_at ON trades(opened_at);
CREATE INDEX idx_trades_result ON trades(result);
```

#### Tabela: `daily_stats`

```sql
CREATE TABLE daily_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL REFERENCES agents(id),
    date            TEXT NOT NULL,           -- "2026-05-03"
    total_trades    INTEGER DEFAULT 0,
    wins            INTEGER DEFAULT 0,
    losses          INTEGER DEFAULT 0,
    gross_profit    REAL DEFAULT 0.0,
    gross_loss      REAL DEFAULT 0.0,
    net_pnl         REAL DEFAULT 0.0,
    win_rate        REAL DEFAULT 0.0,
    UNIQUE(agent_id, date)
);
```

---

### 4.3 Schema das Mensagens WebSocket (Frontend ↔ Backend)

#### Envelope padrão

Toda mensagem usa este envelope:

```json
{
  "type": "string",
  "payload": {}
}
```

#### Mensagens do Backend → Frontend (Server Push)

**`agent_update`** — Atualização de estado de um agente:
```json
{
  "type": "agent_update",
  "payload": {
    "agent_id": "agent-2min",
    "status": "running",
    "total_trades": 43,
    "wins": 26,
    "losses": 17,
    "total_pnl": 20.10,
    "win_rate": 0.6047,
    "consecutive_losses": 0,
    "last_trade_at": "2026-05-03T14:01:00Z"
  }
}
```

**`trade_executed`** — Novo trade aberto:
```json
{
  "type": "trade_executed",
  "payload": {
    "agent_id": "agent-2min",
    "contract_id": "12345678",
    "symbol": "R_75",
    "direction": "CALL",
    "stake": 2.0,
    "ask_price": 2.0,
    "strategy": "rsi_ema",
    "opened_at": "2026-05-03T14:01:00Z"
  }
}
```

**`trade_closed`** — Trade finalizado (ganho ou perda):
```json
{
  "type": "trade_closed",
  "payload": {
    "agent_id": "agent-2min",
    "contract_id": "12345678",
    "result": "won",
    "profit": 1.60,
    "payout": 3.60,
    "entry_price": 123456.78,
    "exit_price": 123510.25,
    "closed_at": "2026-05-03T14:03:00Z",
    "cumulative_pnl": 20.10,
    "win_rate": 0.6047
  }
}
```

**`agent_status_changed`** — Mudança de status do agente:
```json
{
  "type": "agent_status_changed",
  "payload": {
    "agent_id": "agent-5min",
    "old_status": "running",
    "new_status": "limit_hit",
    "reason": "Daily loss limit atingido: 10.0%",
    "timestamp": "2026-05-03T14:05:00Z"
  }
}
```

**`agent_created`** — Novo agente adicionado via CRUD:
```json
{
  "type": "agent_created",
  "payload": {
    "agent_id": "agent-15min",
    "name": "Trend 15min",
    "status": "running"
  }
}
```

**`agent_deleted`** — Agente removido:
```json
{
  "type": "agent_deleted",
  "payload": {
    "agent_id": "agent-15min"
  }
}
```

**`full_state`** — Estado completo enviado na conexão inicial:
```json
{
  "type": "full_state",
  "payload": {
    "agents": [
      {
        "id": "agent-2min",
        "name": "Scalper 2min",
        "symbol": "R_75",
        "timeframe_minutes": 2,
        "stake": 2.0,
        "strategy": "rsi_ema",
        "status": "running",
        "total_trades": 43,
        "wins": 26,
        "losses": 17,
        "total_pnl": 20.10,
        "win_rate": 0.6047,
        "last_trades": [
          {
            "direction": "CALL",
            "result": "won",
            "profit": 1.60,
            "opened_at": "2026-05-03T14:01:00Z"
          }
        ]
      }
    ]
  }
}
```

**`error`** — Erro de sistema:
```json
{
  "type": "error",
  "payload": {
    "agent_id": "agent-2min",
    "code": "DERIV_CONNECTION_LOST",
    "message": "WebSocket connection to Deriv closed unexpectedly",
    "timestamp": "2026-05-03T14:10:00Z"
  }
}
```

#### Mensagens do Frontend → Backend (Client Commands)

**`ping`** — Keep-alive da conexão WS:
```json
{ "type": "ping" }
```

**`subscribe_agent`** — Inscrever em updates de agente específico:
```json
{
  "type": "subscribe_agent",
  "payload": { "agent_id": "agent-2min" }
}
```

---

## 5. Fluxo de Dados — Ciclo de Trade

### 5.1 Diagrama de Sequência — Trade Completo

```
Frontend       FastAPI        AgentManager    BotTask        DerivClient      Deriv API
   │               │               │              │                │               │
   │  GET /agents  │               │              │                │               │
   │──────────────►│               │              │                │               │
   │◄──────────────│ 200 + JSON    │              │                │               │
   │               │               │              │                │               │
   │  WS /ws       │               │              │                │               │
   │══════════════►│               │              │                │               │
   │◄══════════════│ full_state    │              │                │               │
   │               │               │              │                │               │
   │               │               │  [loop asyncio a cada N seg]  │               │
   │               │               │              │                │               │
   │               │               │              │ fetch_candles()│               │
   │               │               │              │───────────────►│               │
   │               │               │              │                │ ticks_history │
   │               │               │              │                │──────────────►│
   │               │               │              │                │◄──────────────│
   │               │               │              │◄───────────────│ OHLCV data    │
   │               │               │              │                │               │
   │               │               │              │ generate_signal(df)            │
   │               │               │              │═══════════════►│               │
   │               │               │              │◄═══════════════│ "CALL"        │
   │               │               │              │                │               │
   │               │               │              │ [se signal != 'wait']          │
   │               │               │              │                │               │
   │               │               │              │ get_proposal() │               │
   │               │               │              │───────────────►│               │
   │               │               │              │                │ proposal req  │
   │               │               │              │                │──────────────►│
   │               │               │              │                │◄──────────────│
   │               │               │              │◄───────────────│ proposal_id   │
   │               │               │              │                │               │
   │               │               │              │ buy_contract() │               │
   │               │               │              │───────────────►│               │
   │               │               │              │                │ buy req       │
   │               │               │              │                │──────────────►│
   │               │               │              │                │◄──────────────│
   │               │               │              │◄───────────────│ contract_id   │
   │               │               │              │                │               │
   │               │ broadcast()   │              │ emit trade_executed            │
   │◄══════════════│◄══════════════│◄═════════════│                │               │
   │ trade_executed│               │              │                │               │
   │               │               │              │                │               │
   │               │               │              │ subscribe_contract()           │
   │               │               │              │───────────────►│               │
   │               │               │              │                │ subscribe req │
   │               │               │              │                │──────────────►│
   │               │               │              │                │               │
   │               │               │              │                │ [aguarda expiração]
   │               │               │              │                │──────────────►│
   │               │               │              │                │◄──────────────│
   │               │               │              │◄───────────────│ status: "won" │
   │               │               │              │                │               │
   │               │               │              │ insert_trade() [SQLite]        │
   │               │               │              │═══════════════►│               │
   │               │               │              │                │               │
   │               │               │              │ save agents.json               │
   │               │               │              │═══════════════►│               │
   │               │               │              │                │               │
   │               │ broadcast()   │              │ emit trade_closed              │
   │◄══════════════│◄══════════════│◄═════════════│                │               │
   │ trade_closed  │               │              │                │               │
```

### 5.2 Detalhamento das Etapas

1. **Inicialização**: Na startup do FastAPI, `AgentManager.startup()` lê `agents.json` e para cada agente com `status != "stopped"`, spawna uma `asyncio.Task` via `asyncio.create_task(bot_task.run())`

2. **Loop do BotTask**: Cada `BotTask` executa:
   ```
   while not cancelled:
     if agent.status == "paused": await asyncio.sleep(10); continue
     df = await deriv_client.fetch_candles(granularity, count=200)
     signal = signal_generator.generate(df, strategy, params)
     if signal != 'wait' and risk_manager.can_trade():
       trade = await deriv_client.place_trade(symbol, signal, stake, duration)
       await trade_repo.insert_trade(trade)
       await agent_manager.update_runtime(agent_id, trade)
       await ws_hub.broadcast(TradeExecutedEvent)
       result = await deriv_client.wait_result(trade.contract_id)
       await trade_repo.update_trade(result)
       await agent_manager.update_runtime(agent_id, result)
       await ws_hub.broadcast(TradeClosedEvent)
     wait_time = calculate_next_candle_time(granularity)
     await asyncio.sleep(wait_time)
   ```

3. **Persistência dupla**: Após cada trade, o resultado é salvo no SQLite (permanente) E o `agents.json` é atualizado com os counters de runtime (para recovery pós-crash)

4. **Broadcast**: Após cada evento (trade aberto, trade fechado, status mudado), o `AgentManager` chama `ws_hub.broadcast()` que entrega para todos os clientes WS conectados

---

## 6. API REST Endpoints

### Base URL: `http://localhost:8000/api/v1`

---

### 6.1 Agentes

#### `GET /agents`
Retorna lista de todos os agentes com stats atuais.

**Response 200:**
```json
{
  "agents": [
    {
      "id": "agent-2min",
      "name": "Scalper 2min",
      "symbol": "R_75",
      "timeframe_minutes": 2,
      "stake": 2.0,
      "strategy": "rsi_ema",
      "status": "running",
      "total_trades": 43,
      "wins": 26,
      "losses": 17,
      "total_pnl": 20.10,
      "win_rate": 0.6047,
      "consecutive_losses": 0,
      "last_trade_at": "2026-05-03T14:01:00Z"
    }
  ]
}
```

---

#### `GET /agents/{agent_id}`
Retorna dados completos de um agente específico.

**Response 200:** Objeto completo do agente incluindo `strategy_params` e `risk`.

**Response 404:**
```json
{ "detail": "Agent 'agent-xyz' not found" }
```

---

#### `POST /agents`
Cria um novo agente e inicia sua `asyncio.Task`.

**Request Body:**
```json
{
  "id": "agent-15min",
  "name": "Trend 15min",
  "symbol": "R_75",
  "timeframe_minutes": 15,
  "stake": 15.0,
  "strategy": "ema_pullback",
  "strategy_params": {
    "ema_fast": 9,
    "ema_slow": 21,
    "ema_filter": 50
  },
  "risk": {
    "daily_loss_limit_pct": 0.10,
    "daily_win_target_pct": 0.20,
    "max_consecutive_losses": 5,
    "risk_per_trade_pct": 0.02
  }
}
```

**Response 201:**
```json
{
  "id": "agent-15min",
  "status": "running",
  "message": "Agent created and started successfully"
}
```

**Response 422:** Validation error (campo inválido).

**Response 409:**
```json
{ "detail": "Agent with id 'agent-15min' already exists" }
```

---

#### `PUT /agents/{agent_id}`
Atualiza configuração de um agente. O bot é reiniciado automaticamente com a nova config.

**Request Body:** (campos parciais aceitos — PATCH semântico)
```json
{
  "name": "Trend 15min v2",
  "stake": 20.0,
  "strategy_params": {
    "ema_fast": 12,
    "ema_slow": 26
  }
}
```

**Response 200:**
```json
{
  "id": "agent-15min",
  "status": "running",
  "message": "Agent updated and restarted with new config"
}
```

---

#### `DELETE /agents/{agent_id}`
Para e remove um agente. Histórico de trades é mantido no SQLite.

**Response 200:**
```json
{
  "id": "agent-15min",
  "message": "Agent stopped and removed. Trade history preserved."
}
```

---

#### `POST /agents/{agent_id}/pause`
Pausa um agente (mantém stats, para de operar).

**Response 200:**
```json
{ "agent_id": "agent-2min", "status": "paused" }
```

---

#### `POST /agents/{agent_id}/resume`
Retoma um agente pausado.

**Response 200:**
```json
{ "agent_id": "agent-2min", "status": "running" }
```

---

#### `POST /agents/{agent_id}/reset-stats`
Zera os counters de runtime (não afeta histórico SQLite).

**Response 200:**
```json
{ "agent_id": "agent-2min", "message": "Runtime stats reset" }
```

---

### 6.2 Trades

#### `GET /trades`
Lista trades com paginação e filtros.

**Query Params:**
| Param | Tipo | Default | Descrição |
|---|---|---|---|
| `agent_id` | string | null | Filtrar por agente |
| `result` | string | null | `won`, `lost`, `pending` |
| `limit` | int | 50 | Itens por página |
| `offset` | int | 0 | Offset para paginação |
| `from_date` | string | null | ISO 8601 |
| `to_date` | string | null | ISO 8601 |

**Response 200:**
```json
{
  "total": 243,
  "limit": 50,
  "offset": 0,
  "trades": [
    {
      "id": 1,
      "agent_id": "agent-2min",
      "contract_id": "12345678",
      "symbol": "R_75",
      "direction": "CALL",
      "stake": 2.0,
      "result": "won",
      "profit": 1.60,
      "opened_at": "2026-05-03T14:01:00Z",
      "closed_at": "2026-05-03T14:03:00Z"
    }
  ]
}
```

---

#### `GET /trades/stats`
Estatísticas agregadas globais ou por agente.

**Query Params:** `agent_id` (opcional), `period` (`today`, `week`, `month`, `all`)

**Response 200:**
```json
{
  "period": "today",
  "agent_id": null,
  "total_trades": 61,
  "wins": 37,
  "losses": 24,
  "win_rate": 0.6065,
  "gross_profit": 59.20,
  "gross_loss": 48.00,
  "net_pnl": 11.20,
  "profit_factor": 1.23,
  "max_consecutive_wins": 6,
  "max_consecutive_losses": 3
}
```

---

#### `GET /trades/pnl-history`
Série temporal de P&L acumulado para gráficos.

**Query Params:** `agent_id` (opcional), `limit` (default: 100)

**Response 200:**
```json
{
  "agent_id": "agent-2min",
  "data_points": [
    { "timestamp": "2026-05-03T10:00:00Z", "cumulative_pnl": 0.0 },
    { "timestamp": "2026-05-03T10:02:00Z", "cumulative_pnl": 1.60 },
    { "timestamp": "2026-05-03T10:04:00Z", "cumulative_pnl": 0.00 },
    { "timestamp": "2026-05-03T10:06:00Z", "cumulative_pnl": 1.60 }
  ]
}
```

---

### 6.3 Sistema

#### `GET /health`
Health check do servidor.

**Response 200:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "agents_running": 3,
  "agents_total": 5,
  "uptime_seconds": 3600,
  "db_connected": true
}
```

#### `GET /strategies`
Lista estratégias disponíveis.

**Response 200:**
```json
{
  "strategies": [
    {
      "id": "rsi_ema",
      "name": "RSI Extremo + EMA Confirmação",
      "description": "RSI < 25 ou > 75 + cruzamento EMA 9/21",
      "params": ["rsi_period", "rsi_oversold", "rsi_overbought", "ema_fast", "ema_slow"]
    },
    {
      "id": "bb_squeeze",
      "name": "Bollinger Band Squeeze + Breakout",
      "params": ["bb_period", "bb_std", "squeeze_threshold_pct"]
    },
    {
      "id": "stochrsi",
      "name": "StochRSI Extremo",
      "params": ["rsi_length", "k_period", "d_period"]
    },
    {
      "id": "ema_pullback",
      "name": "EMA Crossover + Pullback",
      "params": ["ema_fast", "ema_slow", "ema_filter"]
    }
  ]
}
```

---

## 7. WebSocket Messages (Frontend ↔ Backend)

### 7.1 Endpoint

```
ws://localhost:8000/ws
```

### 7.2 Lifecycle de Conexão

```
Frontend                               Backend
   │                                      │
   │  CONNECT ws://localhost:8000/ws      │
   │─────────────────────────────────────►│  ConnectionManager.connect(ws)
   │                                      │
   │◄─────────────────────────────────────│  full_state (estado atual de todos)
   │                                      │
   │  [operação normal — recebe eventos]  │
   │◄─────────────────────────────────────│  agent_update
   │◄─────────────────────────────────────│  trade_executed
   │◄─────────────────────────────────────│  trade_closed
   │                                      │
   │  ping                                │
   │─────────────────────────────────────►│
   │◄─────────────────────────────────────│  pong
   │                                      │
   │  DISCONNECT (tab fechada/erro)       │
   │─────────────────────────────────────►│  ConnectionManager.disconnect(ws)
```

### 7.3 ConnectionManager

```python
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        await self.send_full_state(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active_connections.remove(ws)

    async def send_full_state(self, websocket: WebSocket):
        state = await agent_manager.get_full_state()
        await websocket.send_json({"type": "full_state", "payload": state})
```

### 7.4 Frontend — Reconexão Automática

```javascript
// ws-client.js
class WSClient {
  constructor(url) {
    this.url = url;
    this.reconnectDelay = 1000;
    this.maxDelay = 30000;
    this.handlers = {};
  }

  connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log('[WS] Conectado');
      this.reconnectDelay = 1000; // reset backoff
      this.startPing();
    };

    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (this.handlers[msg.type]) {
        this.handlers[msg.type](msg.payload);
      }
    };

    this.ws.onclose = () => {
      console.log(`[WS] Desconectado. Reconectando em ${this.reconnectDelay}ms`);
      setTimeout(() => this.connect(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxDelay);
    };
  }

  on(type, handler) {
    this.handlers[type] = handler;
  }

  startPing() {
    setInterval(() => {
      if (this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
  }
}
```

---

## 8. Gerenciamento de Estado dos Bots

### 8.1 AgentManager como Singleton

```python
# core/agent_manager.py
import asyncio
import json
from pathlib import Path
from typing import dict

AGENTS_JSON_PATH = Path("src/state/agents.json")

class AgentManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.tasks: dict[str, asyncio.Task] = {}
            cls._instance.bot_instances: dict[str, BotTask] = {}
            cls._instance.ws_hub = None
        return cls._instance

    async def startup(self, ws_hub):
        self.ws_hub = ws_hub
        config = self._load_config()
        for agent in config["agents"]:
            if agent["enabled"] and agent["status"] != "stopped":
                await self.start_agent(agent)

    async def start_agent(self, agent_config: dict):
        bot = BotTask(agent_config, self.ws_hub)
        self.bot_instances[agent_config["id"]] = bot
        task = asyncio.create_task(
            bot.run(),
            name=f"bot-{agent_config['id']}"
        )
        self.tasks[agent_config["id"]] = task
        task.add_done_callback(
            lambda t: self._on_task_done(agent_config["id"], t)
        )

    async def stop_agent(self, agent_id: str):
        if agent_id in self.tasks:
            self.tasks[agent_id].cancel()
            try:
                await self.tasks[agent_id]
            except asyncio.CancelledError:
                pass
            del self.tasks[agent_id]
            del self.bot_instances[agent_id]

    async def pause_agent(self, agent_id: str):
        if agent_id in self.bot_instances:
            self.bot_instances[agent_id].paused = True
            await self._update_agent_status(agent_id, "paused")

    async def resume_agent(self, agent_id: str):
        if agent_id in self.bot_instances:
            self.bot_instances[agent_id].paused = False
            await self._update_agent_status(agent_id, "running")

    def _on_task_done(self, agent_id: str, task: asyncio.Task):
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            self._handle_agent_error(agent_id, exc)

    def _load_config(self) -> dict:
        with open(AGENTS_JSON_PATH) as f:
            return json.load(f)

    async def save_config(self):
        """Salva estado atual no agents.json (thread-safe via asyncio)."""
        config = self._build_config_dict()
        with open(AGENTS_JSON_PATH, "w") as f:
            json.dump(config, f, indent=2)
```

### 8.2 BotTask — Estrutura de Loop

```python
# core/bot_task.py
class BotTask:
    def __init__(self, config: dict, ws_hub):
        self.config = config
        self.agent_id = config["id"]
        self.ws_hub = ws_hub
        self.paused = config.get("status") == "paused"
        self.deriv = DerivClient(API_TOKEN, APP_ID)
        self.risk_mgr = RiskManager(config["risk"])
        self.runtime = config["runtime"].copy()

    async def run(self):
        await self.deriv.connect()
        granularity_seconds = self.config["timeframe_minutes"] * 60

        while True:
            try:
                if self.paused:
                    await asyncio.sleep(5)
                    continue

                df = await self.deriv.fetch_candles(
                    self.config["symbol"],
                    granularity_seconds,
                    count=200
                )

                signal = generate_signal(
                    df,
                    self.config["strategy"],
                    self.config.get("strategy_params", {})
                )

                if signal != "wait":
                    can_trade, reason = self.risk_mgr.can_trade()
                    if can_trade:
                        await self._execute_trade(signal)
                    else:
                        # Verifica se deve mudar status
                        if "limit" in reason.lower():
                            await self._set_status("limit_hit", reason)

                # Aguarda próxima vela (alinhado com granularidade)
                sleep_time = self._seconds_to_next_candle(granularity_seconds)
                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                await self.deriv.disconnect()
                raise

            except websockets.ConnectionClosed:
                await self._handle_reconnect()

            except Exception as e:
                logger.error(f"[{self.agent_id}] Erro: {e}")
                await asyncio.sleep(10)

    async def _execute_trade(self, signal: str):
        stake = self.config["stake"]  # Fixo conforme timeframe
        contract_type = "CALL" if signal == "call" else "PUT"

        # Notifica abertura
        await self.ws_hub.broadcast({
            "type": "trade_executed",
            "payload": {
                "agent_id": self.agent_id,
                "direction": contract_type,
                "stake": stake
            }
        })

        result = await self.deriv.place_and_wait(
            symbol=self.config["symbol"],
            contract_type=contract_type,
            duration=self.config["timeframe_minutes"],
            stake=stake
        )

        # Persiste no SQLite
        await trade_repo.insert_trade({**result, "agent_id": self.agent_id})

        # Atualiza runtime
        self._update_runtime(result)

        # Salva agents.json
        await agent_manager.save_config()

        # Notifica resultado
        await self.ws_hub.broadcast({
            "type": "trade_closed",
            "payload": {
                "agent_id": self.agent_id,
                **result,
                "cumulative_pnl": self.runtime["total_pnl"]
            }
        })
```

### 8.3 Concorrência: Por Que asyncio Funciona Aqui

```
┌──────────────────────────────────────────────────────┐
│               asyncio Event Loop (single thread)      │
│                                                        │
│  Task: HTTP Request Handler                           │
│  Task: WebSocket Hub (frontend)                       │
│  Task: BotTask agent-2min  ──► await asyncio.sleep()  │
│  Task: BotTask agent-5min  ──► await ws.recv()         │
│  Task: BotTask agent-10min ──► await ws.recv()         │
│  Task: BotTask agent-15min ──► await asyncio.sleep()  │
│  Task: BotTask agent-30min ──► await asyncio.sleep()  │
│                                                        │
│  Quando qualquer await resolve → próxima task roda    │
│  Nunca bloqueiam uns aos outros                       │
└──────────────────────────────────────────────────────┘
```

Cada `BotTask` usa uma **conexão WebSocket separada** com a Deriv API. Isso permite que cada agente opere independentemente sem interferir nos outros.

---

## 9. Estratégia de Persistência

### 9.1 O Que Vai em Cada Storage

| Dado | Storage | Justificativa |
|---|---|---|
| Config dos agentes (id, timeframe, stake, estratégia) | `agents.json` | Hot-reload sem restart; leitura rápida na startup |
| Estado de runtime (total_trades, wins, losses, pnl) | `agents.json` | Recovery de crash sem precisar recalcular do SQLite |
| Status atual (running/paused/stopped) | `agents.json` | Persistência de intenção entre restarts |
| Histórico completo de trades | SQLite (`trades`) | Queries complexas, agregações, JOIN; dados imutáveis |
| Estatísticas diárias | SQLite (`daily_stats`) | Consultas de dashboard sem recalcular |
| Configurações imutáveis (API tokens) | `.env` | Segurança; nunca no código |
| Logs detalhados | Arquivos em `src/logs/` | PM2 captura stdout; logs por agente separados |

### 9.2 Regra de Ouro da Persistência

```
agents.json → Estado OPERACIONAL (o que preciso para REINICIAR)
SQLite       → Estado HISTÓRICO (o que aconteceu NO PASSADO)
```

### 9.3 Frequência de Persistência

| Evento | agents.json | SQLite |
|---|---|---|
| Trade executado (aberto) | ✅ Imediato | ✅ Imediato (status: pending) |
| Trade fechado (resultado) | ✅ Imediato | ✅ Imediato (status: won/lost) |
| Status de agente mudado | ✅ Imediato | ❌ |
| Criação de agente | ✅ Imediato | ✅ Insert em `agents` table |
| Deleção de agente | ✅ Imediato | ❌ (histórico preservado) |
| Tick de P&L | ❌ (somente no WS) | ❌ |

### 9.4 Controle de Concorrência no agents.json

Para evitar race condition ao salvar `agents.json` de múltiplas tasks simultâneas:

```python
# core/agent_manager.py
class AgentManager:
    def __init__(self):
        self._json_lock = asyncio.Lock()

    async def save_config(self):
        async with self._json_lock:
            config = self._build_config_dict()
            # Write atômico via arquivo temporário
            tmp_path = AGENTS_JSON_PATH.with_suffix(".tmp")
            with open(tmp_path, "w") as f:
                json.dump(config, f, indent=2)
            tmp_path.replace(AGENTS_JSON_PATH)
```

---

## 10. Plano de Resiliência

### 10.1 Cenários e Respostas

| Cenário | Detecção | Resposta |
|---|---|---|
| **Crash total do servidor** | PM2 exit event | PM2 auto-restart; startup lê `agents.json` e retoma |
| **Queda da conexão Deriv** | `ConnectionClosed` exception | `DerivClient` faz reconnect com exponential backoff (1s→2s→4s→...→60s) |
| **Trade aberto antes do crash** | Trade com `result=pending` no SQLite | Na startup, query por trades pending; se aberto há mais de 30min, marcar como `unknown` |
| **agents.json corrompido** | `json.JSONDecodeError` | Fallback para `agents.json.bak`; se falhar, iniciar com lista vazia |
| **Agente em loop de erro** | N erros em sequência | Após 5 erros em 5min, muda status para `error` e cancela task |
| **Múltiplas tabs abertas** | Normal | ConnectionManager gerencia lista de WS; cada tab recebe broadcast |
| **Tab perdendo conexão WS** | `WebSocketDisconnect` | Remove da lista; frontend reconecta automaticamente |
| **Limite de risco atingido** | `RiskManager.can_trade()` | Status `limit_hit`; task parada; broadcast para UI; log registrado |

### 10.2 Recovery de Trades Pendentes na Startup

```python
# main.py startup hook
@app.on_event("startup")
async def startup():
    await init_db()
    # Verificar trades pendentes do crash anterior
    pending = await trade_repo.get_pending_trades()
    for trade in pending:
        age_minutes = (datetime.now() - trade.opened_at).seconds / 60
        if age_minutes > trade.duration_minutes + 5:
            # Trade expirado sem resultado registrado
            await trade_repo.mark_as_unknown(trade.id)
            logger.warning(f"Trade {trade.contract_id} marcado como unknown (recovery)")
    
    # Iniciar AgentManager
    await agent_manager.startup(ws_hub)
```

### 10.3 DerivClient — Reconnect Robusto

```python
# core/deriv_client.py
class DerivClient:
    async def connect(self):
        retries = 0
        while True:
            try:
                self.ws = await websockets.connect(
                    DERIV_WS_URL,
                    ping_interval=30,
                    ping_timeout=10
                )
                await self._authorize()
                self._start_keepalive()
                return
            except Exception as e:
                retries += 1
                delay = min(2 ** retries, 60)
                logger.warning(f"[Deriv] Reconnect {retries} em {delay}s: {e}")
                await asyncio.sleep(delay)

    async def _start_keepalive(self):
        async def ping_loop():
            while True:
                try:
                    await self.ws.send(json.dumps({"ping": 1}))
                    await asyncio.sleep(30)
                except Exception:
                    break
        asyncio.create_task(ping_loop())
```

### 10.4 Proteção do agents.json com Backup

```python
async def save_config(self):
    async with self._json_lock:
        # Backup do arquivo atual
        if AGENTS_JSON_PATH.exists():
            shutil.copy2(AGENTS_JSON_PATH, AGENTS_JSON_PATH.with_suffix(".bak"))
        # Write atômico
        config = self._build_config_dict()
        tmp = AGENTS_JSON_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(config, indent=2, ensure_ascii=False))
        tmp.replace(AGENTS_JSON_PATH)
```

---

## 11. Configuração do PM2

### 11.1 `ecosystem.config.js`

```javascript
// ecosystem.config.js — raiz do projeto
module.exports = {
  apps: [
    {
      name: "binary-opt-ai",
      script: "uvicorn",
      args: "src.main:app --host 0.0.0.0 --port 8000 --workers 1",
      interpreter: "python3",
      interpreter_args: "-m",
      cwd: "/Users/adrianomendes/Projects/binary-opt-ai",

      // Restart automático
      autorestart: true,
      watch: false,             // Desabilitar em produção
      max_memory_restart: "512M",
      restart_delay: 3000,      // 3s antes de reiniciar
      max_restarts: 20,

      // Logs
      log_file: "src/logs/combined.log",
      out_file: "src/logs/out.log",
      error_file: "src/logs/error.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      merge_logs: true,

      // Variáveis de ambiente
      env: {
        NODE_ENV: "production",
        PYTHONPATH: "/Users/adrianomendes/Projects/binary-opt-ai",
        PYTHONUNBUFFERED: "1"
      },
      env_development: {
        NODE_ENV: "development",
        PYTHONPATH: "/Users/adrianomendes/Projects/binary-opt-ai",
        PYTHONUNBUFFERED: "1"
      }
    }
  ]
};
```

### 11.2 Comandos PM2

```bash
# Instalar PM2 (necessário Node.js)
npm install -g pm2

# Iniciar a aplicação
pm2 start ecosystem.config.js

# Ver status
pm2 status

# Ver logs em tempo real
pm2 logs binary-opt-ai

# Reiniciar sem downtime
pm2 reload binary-opt-ai

# Parar
pm2 stop binary-opt-ai

# Salvar configuração para auto-start no boot
pm2 save
pm2 startup

# Monitoramento visual
pm2 monit
```

### 11.3 Alternativa: `supervisord` (sem Node.js)

```ini
; /etc/supervisor/conf.d/binary-opt-ai.conf
[program:binary-opt-ai]
command=/usr/bin/python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 1
directory=/Users/adrianomendes/Projects/binary-opt-ai
autostart=true
autorestart=true
startretries=20
stderr_logfile=/Users/adrianomendes/Projects/binary-opt-ai/src/logs/supervisor_err.log
stdout_logfile=/Users/adrianomendes/Projects/binary-opt-ai/src/logs/supervisor_out.log
environment=PYTHONPATH="/Users/adrianomendes/Projects/binary-opt-ai",PYTHONUNBUFFERED="1"
```

### 11.4 Desenvolvimento com Hot Reload

```bash
# Durante desenvolvimento (sem PM2)
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Com variáveis de ambiente do .env
pip install python-dotenv
# Em src/main.py:
# from dotenv import load_dotenv
# load_dotenv()
```

---

## 12. Sequência de Implementação

### 12.1 Ordem de Criação dos Arquivos

A sequência abaixo respeita dependências: cada camada depende apenas das anteriores.

---

#### Fase 1 — Fundação (Infraestrutura)

| # | Arquivo | O Que Criar |
|---|---|---|
| 1 | `requirements.txt` | Todas as dependências Python |
| 2 | `.env.example` | Template com `DERIV_API_TOKEN`, `DERIV_APP_ID`, `PORT` |
| 3 | `.env` | Valores reais (não versionado) |
| 4 | `.gitignore` | `.env`, `*.db`, `src/logs/*.log`, `__pycache__` |
| 5 | `src/db/database.py` | `init_db()`, schema SQL, `get_db()` |
| 6 | `src/models/trade_model.py` | `TradeRecord`, `TradeResult` Pydantic |
| 7 | `src/models/agent_model.py` | `AgentConfig`, `AgentStatus`, `AgentState` Pydantic |
| 8 | `src/db/trade_repository.py` | `insert_trade()`, `get_trades_by_agent()`, `get_pnl_history()` |

---

#### Fase 2 — Core do Bot

| # | Arquivo | O Que Criar |
|---|---|---|
| 9 | `src/core/risk_manager.py` | `RiskManager`: `can_trade()`, `get_stake()`, `update()`, `reset_daily()` |
| 10 | `src/core/signal_generator.py` | Funções puras: `rsi_ema()`, `bb_squeeze()`, `stochrsi()`, `ema_pullback()`, `generate_signal()` |
| 11 | `src/core/deriv_client.py` | `DerivClient`: `connect()`, `authorize()`, `fetch_candles()`, `get_proposal()`, `buy_contract()`, `subscribe_contract()`, `place_and_wait()`, reconnect lógico |
| 12 | `src/core/bot_task.py` | `BotTask`: `run()`, `_execute_trade()`, `_handle_reconnect()`, `_set_status()` |
| 13 | `src/core/agent_manager.py` | `AgentManager` singleton: `startup()`, `start_agent()`, `stop_agent()`, `pause_agent()`, `resume_agent()`, `save_config()`, `load_config()` |

---

#### Fase 3 — API Backend

| # | Arquivo | O Que Criar |
|---|---|---|
| 14 | `src/api/websocket_hub.py` | `ConnectionManager`: `connect()`, `disconnect()`, `broadcast()`, `send_full_state()`; endpoint `/ws` |
| 15 | `src/api/routes_agents.py` | `GET /agents`, `GET /agents/{id}`, `POST /agents`, `PUT /agents/{id}`, `DELETE /agents/{id}`, `POST /agents/{id}/pause`, `POST /agents/{id}/resume` |
| 16 | `src/api/routes_trades.py` | `GET /trades`, `GET /trades/stats`, `GET /trades/pnl-history` |
| 17 | `src/main.py` | FastAPI app, registrar routers, montar `/static`, startup/shutdown hooks, CORS middleware |

---

#### Fase 4 — Frontend

| # | Arquivo | O Que Criar |
|---|---|---|
| 18 | `src/static/css/dashboard.css` | Dark theme, grid layout cards, modal styles, tabela de trades, cores verde/vermelho, responsive |
| 19 | `src/static/js/api.js` | `fetchAgents()`, `createAgent()`, `updateAgent()`, `deleteAgent()`, `pauseAgent()`, `resumeAgent()`, `fetchPnlHistory()`, `fetchStats()` |
| 20 | `src/static/js/ws-client.js` | `WSClient`: reconnect exponential backoff, `on(type, handler)`, `startPing()` |
| 21 | `src/static/js/charts.js` | `initPnlChart(agentId)`, `updatePnlChart(agentId, data)`, `initComparativeChart()`, `updateComparativeChart(allAgentsData)` |
| 22 | `src/static/js/app.js` | Inicialização, render de cards, modal CRUD, binding de eventos WS, atualização em tempo real |
| 23 | `src/static/index.html` | Estrutura HTML: header, grid de agent cards, seção de gráficos, modal de criação/edição, tabela de últimos trades |

---

#### Fase 5 — Deploy e Operação

| # | Arquivo | O Que Criar |
|---|---|---|
| 24 | `src/state/agents.json` | Arquivo inicial com os 5 agentes padrão (2min, 5min, 10min, 15min, 30min) |
| 25 | `ecosystem.config.js` | Configuração PM2 completa |
| 26 | `README.md` | Instruções de instalação, execução, uso da interface |

---

### 12.2 `requirements.txt`

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
websockets==12.0
aiosqlite==0.20.0
pandas==2.2.2
pandas-ta==0.3.14b0
pydantic==2.7.1
python-dotenv==1.0.1
aiofiles==23.2.1
```

---

### 12.3 `.env.example`

```bash
# Deriv API
DERIV_API_TOKEN=eYf2ydKTUpN2cgz
DERIV_APP_ID=1
DERIV_WS_URL=wss://ws.binaryws.com/websockets/v3

# Servidor
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Database
DB_PATH=src/state/trades.db
AGENTS_JSON_PATH=src/state/agents.json
```

---

### 12.4 Checklist de Implementação

```
FASE 1 — FUNDAÇÃO
[ ] requirements.txt
[ ] .env + .env.example
[ ] .gitignore
[ ] src/db/database.py  →  testar com: python -c "import asyncio; from src.db.database import init_db; asyncio.run(init_db())"
[ ] src/models/trade_model.py
[ ] src/models/agent_model.py
[ ] src/db/trade_repository.py

FASE 2 — CORE DO BOT
[ ] src/core/risk_manager.py  →  unit test manual
[ ] src/core/signal_generator.py  →  testar com dados fake
[ ] src/core/deriv_client.py  →  testar autenticação com token existente
[ ] src/core/bot_task.py  →  testar com um agente dummy
[ ] src/core/agent_manager.py  →  testar start/stop/pause

FASE 3 — API BACKEND
[ ] src/api/websocket_hub.py
[ ] src/api/routes_agents.py
[ ] src/api/routes_trades.py
[ ] src/main.py  →  rodar: uvicorn src.main:app --reload
[ ] Testar: GET http://localhost:8000/api/v1/health
[ ] Testar: GET http://localhost:8000/api/v1/agents

FASE 4 — FRONTEND
[ ] src/static/css/dashboard.css
[ ] src/static/js/api.js
[ ] src/static/js/ws-client.js
[ ] src/static/js/charts.js
[ ] src/static/js/app.js
[ ] src/static/index.html
[ ] Testar dashboard em http://localhost:8000

FASE 5 — DEPLOY
[ ] src/state/agents.json  →  5 agentes padrão
[ ] ecosystem.config.js
[ ] pm2 start ecosystem.config.js
[ ] pm2 save && pm2 startup
[ ] README.md
```

---

## Apêndice A — Diagrama de Estado dos Agentes

```
                     POST /agents
                          │
                          ▼
                      ┌─────────┐
                      │ created │
                      └────┬────┘
                           │ auto-start
                           ▼
                      ┌─────────┐
              ┌──────►│ running │◄──────┐
              │       └────┬────┘       │
              │            │            │
         resume()    pause()│      resume()
              │            ▼            │
              │       ┌─────────┐       │
              └───────│ paused  │───────┘
                       └────────┘
                          
         running ──► limit_hit    (RiskManager trigger)
         running ──► error        (5 falhas consecutivas)
         any     ──► stopped      (DELETE /agents/{id})
         
         limit_hit ──► running    (POST /resume após reset-stats)
         error     ──► running    (POST /resume após investigação)
```

---

## Apêndice B — Paleta de Cores do Dashboard (Dark Theme)

```css
:root {
  /* Backgrounds */
  --bg-primary:     #0d1117;   /* Fundo principal */
  --bg-secondary:   #161b22;   /* Cards e painéis */
  --bg-tertiary:    #21262d;   /* Inputs e tabelas */
  --bg-hover:       #30363d;   /* Hover states */

  /* Texto */
  --text-primary:   #e6edf3;   /* Texto principal */
  --text-secondary: #8b949e;   /* Labels e subtítulos */
  --text-muted:     #484f58;   /* Placeholders */

  /* Status */
  --color-running:  #3fb950;   /* Verde — rodando */
  --color-paused:   #d29922;   /* Amarelo — pausado */
  --color-stopped:  #6e7681;   /* Cinza — parado */
  --color-error:    #f85149;   /* Vermelho — erro */
  --color-limit:    #e3b341;   /* Laranja — limite */

  /* P&L */
  --color-profit:   #3fb950;   /* Verde — ganho */
  --color-loss:     #f85149;   /* Vermelho — perda */

  /* Bordas */
  --border-color:   #30363d;
  --border-radius:  8px;

  /* Accent */
  --accent-blue:    #58a6ff;
  --accent-purple:  #bc8cff;
}
```

---

*Documento gerado em: Maio 2026 | Projeto `binary-opt-ai` | Versão 1.0*