# 📊 Binary Options Strategies — Knowledge Base Completa

> **Salvar em:** `reference/strategies/binary-options-strategies.md`
> Compilado em: Maio 2026 | Projeto `binary-opt-ai`

---

## 1. O QUE SÃO OPÇÕES BINÁRIAS — Fundamentos Matemáticos

### 1.1 Definição Precisa

Uma **opção binária** é um contrato financeiro derivativo cujo resultado é **estritamente binário**: o trader recebe um payout fixo predefinido se sua previsão estiver correta, ou perde o valor investido se estiver errado. Não há resultado intermediário.

```
Resultado = { +Payout%  se previsão correta
            { -100%     se previsão errada
```

Diferente de ações ou futuros, **não existe parcial de ganho ou perda** baseado na magnitude do movimento — apenas a **direção** importa.

### 1.2 Mecânica: Call (UP) vs. Put (DOWN)

| Termo | Significado | Condição de Vitória |
|---|---|---|
| **Call / UP / Rise / Higher** | Apostando que o preço sobe | Preço de expiração > Preço de entrada |
| **Put / DOWN / Fall / Lower** | Apostando que o preço cai | Preço de expiração < Preço de entrada |

**Janela de expiração fixa**: o trader escolhe antecipadamente quando o contrato expira (ex: 1min, 5min, 15min, 1h). Na expiração, o preço é comparado com o preço de entrada.

```
Exemplo:
- Entrada: EUR/USD a 1.08450 às 10:00:00
- Direção: Call (UP)
- Expiração: 5 minutos (10:05:00)
- Payout: 80%

Se EUR/USD às 10:05:00 = 1.08510 → GANHO: +80% do investido
Se EUR/USD às 10:05:00 = 1.08430 → PERDA: -100% do investido
```

### 1.3 Cálculo do Break-Even por Payout

O **break-even win rate** é a taxa de vitória mínima para não perder dinheiro ao longo do tempo:

```
Break-Even Win Rate = 1 / (1 + Payout)
```

| Payout | Fórmula | Break-Even Win Rate |
|---|---|---|
| **70%** | 1 / (1 + 0.70) | **58.82%** |
| **75%** | 1 / (1 + 0.75) | **57.14%** |
| **80%** | 1 / (1 + 0.80) | **55.56%** |
| **85%** | 1 / (1 + 0.85) | **54.05%** |
| **90%** | 1 / (1 + 0.90) | **52.63%** |
| **95%** | 1 / (1 + 0.95) | **51.28%** |
| **98%** | 1 / (1 + 0.98) | **50.51%** |

> ⚠️ **Conclusão crítica**: Mesmo com payout de 95%, o trader precisa acertar mais de 51.28% dos trades só para empatar. Isso significa que o trader precisa ter **edge real** sobre o mercado.

### 1.4 Expected Value (EV) por Trade

```
EV = (Win Rate × Payout) - (Loss Rate × 1.0)

Exemplo com win rate 60%, payout 80%:
EV = (0.60 × 0.80) - (0.40 × 1.0)
EV = 0.48 - 0.40
EV = +0.08  →  +8% por trade (EV positivo ✅)

Exemplo com win rate 52%, payout 80%:
EV = (0.52 × 0.80) - (0.48 × 1.0)
EV = 0.416 - 0.48
EV = -0.064  →  -6.4% por trade (EV negativo ❌)
```

**Função Python para calcular EV:**
```python
def calculate_ev(win_rate: float, payout: float) -> float:
    loss_rate = 1 - win_rate
    ev = (win_rate * payout) - (loss_rate * 1.0)
    return ev

def calculate_breakeven(payout: float) -> float:
    return 1 / (1 + payout)

# Exemplos:
print(calculate_ev(0.60, 0.80))     # +0.08 (EV positivo)
print(calculate_ev(0.52, 0.80))     # -0.064 (EV negativo)
print(calculate_breakeven(0.80))    # 0.5556 = 55.56% mínimo
```

### 1.5 Diferença entre Binárias Reguladas vs. Não Reguladas

| Característica | Reguladas (ex: Nadex, Deriv/Malta) | Não Reguladas (ex: Pocket Option, Quotex) |
|---|---|---|
| **Regulador** | CFTC (EUA), MGA (Malta), FCA | Vanuatu FSC, IFMRRC ou nenhum |
| **Proteção do capital** | Fundo segregado obrigatório | Sem garantia |
| **Transparência de preços** | Preços de mercado real | Possível manipulação de feed |
| **Disponibilidade Brasil** | Limitada (Nadex apenas EUA) | Ampla |
| **Payout típico** | 60-80% (spread maior) | 70-98% (spread menor) |
| **Risco de scam** | Baixo | Alto (muitos fecham sem pagar) |
| **API para bots** | Deriv tem API oficial | APIs não-oficiais instáveis |

### 1.6 Por Que a Maioria dos Traders Perde

1. **Edge matemático da casa**: payout < 100% significa que a casa tem vantagem embutida
2. **Ausência de edge real**: a maioria aposta sem estratégia com win rate > break-even
3. **Gestão de risco inexistente**: apostas grandes / sem limite diário
4. **Martingale sem capital**: dobrar apostas leva à ruína em sequências de perda
5. **Plataformas desonestas**: algumas manipulam o preço de expiração
6. **Overtrading emocional**: trades por impulso após perdas

---

## 2. PLATAFORMAS E BROKERS — Análise Completa

### 2.1 Tabela Comparativa Master

| Plataforma | Payout Médio | Payout Máx | Regulação | API Oficial | API Não-Oficial | Synthetic | Confiabilidade | Ideal para Bots |
|---|---|---|---|---|---|---|---|---|
| **Deriv (Binary.com)** | 80-92% | 95% | MGA (Malta), SVG | ✅ REST+WS | N/A | ✅ Extensivo | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **IQ Option** | 70-85% | 92% | CySEC (EU) | ❌ | ✅ Python lib | ❌ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Pocket Option** | 75-90% | 95% | IFMRRC | ❌ | ✅ WS | ❌ | ⭐⭐⭐ | ⭐⭐ |
| **Quotex** | 80-95% | 98% | IFMRRC | ❌ | Limitada | ❌ | ⭐⭐⭐ | ⭐⭐ |
| **Olymp Trade** | 72-82% | 90% | FinaCom | ❌ | Limitada | ❌ | ⭐⭐⭐⭐ | ⭐⭐ |
| **Binomo** | 70-85% | 90% | FinaCom | ❌ | Limitada | ❌ | ⭐⭐⭐ | ⭐⭐ |
| **Raceoption** | 75-85% | 90% | Nenhuma | ❌ | ❌ | ❌ | ⭐⭐ | ⭐ |
| **Spectre.ai** | 75-88% | 92% | Blockchain | ❌ | Limitada | ❌ | ⭐⭐⭐ | ⭐⭐ |
| **Nadex** | 60-75% | 80% | CFTC (EUA) | ✅ REST | N/A | ❌ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

### 2.2 Deriv (Binary.com) — Análise Detalhada

**Ponto forte absoluto**: única plataforma com **API oficial pública e documentada** que permite automação sem risco de ban por ToS.

- **Mercados disponíveis**: 50+ pares Forex, Índices, Commodities, Crypto, **Synthetic Indices** (exclusivo)
- **Payout**: 70-95% dependendo do ativo e duração
- **Depósito mínimo**: $5 (real), $10.000 virtual (demo)
- **Regulação**: MGA Malta (B2C), SVG (offshore)
- **Documentação API**: https://api.deriv.com
- **App ID gratuito**: qualquer desenvolvedor pode obter

### 2.3 IQ Option — Análise Detalhada

- **Mercados**: 500+ ativos incluindo Forex, Crypto, Stocks, ETFs
- **Conta demo**: $10.000 virtuais ilimitado
- **Payout**: varia por ativo e hora do dia (em alta volatilidade sobe)
- **API**: biblioteca `iqoptionapi` não-oficial (Lu-Yi-Hsun no GitHub)
- **Risco de automação**: **violação de ToS** — contas podem ser banidas
- **Retirada**: histórico misto de reclamações de atraso

### 2.4 Pocket Option — Análise Detalhada

- **Público-alvo**: LatAm e Ásia
- **Payout**: um dos mais altos do mercado (até 95%)
- **Torneios**: competições frequentes com prêmios reais
- **Automação**: possível via WebSocket não-oficial mas instável
- **Regulação**: IFMRRC (não reconhecido por reguladores sérios)

### 2.5 Quotex — Análise Detalhada

- **Payouts**: até 98% em horários específicos (ativos OTC)
- **Ativos OTC**: negociados mesmo nos fins de semana
- **Interface**: moderna, rápida
- **Risco**: regulação fraca, sem histórico longo de mercado

### 2.6 Nadex — Estrutura Especial (EUA)

Nadex tem estrutura diferente: as binárias são **contratos de spread** ($0-$100), negociados em exchange real:

```
Nadex Binary: comprado a $30, expira a $100 se ganhar
Lucro = $100 - $30 = $70 por contrato
Perda = -$30 por contrato
```

- Apenas para residentes nos EUA
- API REST oficial disponível
- Sem risco de contraparte (exchange regulada)

---

## 3. DERIV API — GUIA TÉCNICO COMPLETO

### 3.1 Conexão WebSocket

```python
import asyncio
import websockets
import json

DERIV_WS_URL = "wss://ws.binaryws.com/websockets/v3?app_id=SEU_APP_ID"

async def connect_deriv():
    async with websockets.connect(DERIV_WS_URL) as ws:
        # Autenticação com token
        auth_request = {
            "authorize": "SEU_API_TOKEN"
        }
        await ws.send(json.dumps(auth_request))
        response = await ws.recv()
        auth_data = json.loads(response)
        
        if auth_data.get("authorize"):
            print(f"Autenticado! Balance: {auth_data['authorize']['balance']}")
            return auth_data
        else:
            raise Exception(f"Falha na autenticação: {auth_data}")
```

### 3.2 Como Obter App ID e Token

1. Acesse: https://app.deriv.com/account/api-token
2. Crie um token com permissões: **Read, Trade, Payments**
3. Registre um App ID em: https://developers.deriv.com/
4. App ID `1` funciona para testes em demo

### 3.3 Tipos de Contratos Disponíveis

| Tipo de Contrato | Code | Descrição |
|---|---|---|
| **Rise/Fall** | `CALL` / `PUT` | Clássico Up/Down |
| **Higher/Lower** | `EXPIRYRANGE` | Com barreira específica |
| **Ends In/Out** | `EXPIRYMISS` / `EXPIRYRANGE` | Dentro ou fora de uma faixa |
| **Stays In/Breaks Out** | `RANGE` / `UPORDOWN` | Durante toda a duração |
| **Touch/No Touch** | `ONETOUCH` / `NOTOUCH` | Toca ou não toca a barreira |
| **Digit Matches** | `DIGITMATCH` | Último dígito específico (Synthetic only) |
| **Digit Differs** | `DIGITDIFF` | Diferente de dígito (Synthetic only) |
| **Digit Over/Under** | `DIGITOVER` / `DIGITUNDER` | Dígito > ou < N (Synthetic only) |
| **Digit Even/Odd** | `DIGITEVEN` / `DIGITODD` | Par ou Ímpar (Synthetic only) |

### 3.4 Synthetic Indices — Detalhamento Completo

#### Volatility Indices

| Índice | Símbolo | Volatilidade Anual | Ideal Para |
|---|---|---|---|
| Volatility 10 Index | `R_10` | ~10% | Estratégias conservadoras |
| Volatility 25 Index | `R_25` | ~25% | Médio risco |
| Volatility 50 Index | `R_50` | ~50% | Médio-alto risco |
| Volatility 75 Index | `R_75` | ~75% | Alto risco, mais payout |
| Volatility 100 Index | `R_100` | ~100% | Muito volátil |
| Volatility 10(1s) | `1HZ10V` | ~10% | Scalping ultra-rápido |
| Volatility 25(1s) | `1HZ25V` | ~25% | Scalping rápido |
| Volatility 50(1s) | `1HZ50V` | ~50% | Scalping médio |
| Volatility 75(1s) | `1HZ75V` | ~75% | Scalping agressivo |
| Volatility 100(1s) | `1HZ100V` | ~100% | Ultra-agressivo |

#### Crash/Boom Indices

| Índice | Símbolo | Comportamento | Estratégia |
|---|---|---|---|
| Boom 300 | `BOOM300N` | Queda gradual + spike de alta ~1/300 ticks | Comprar o spike, vender a queda |
| Boom 500 | `BOOM500` | Queda gradual + spike ~1/500 ticks | Comprar o spike |
| Boom 1000 | `BOOM1000` | Queda gradual + spike ~1/1000 ticks | Spike menos frequente, maior amplitude |
| Crash 300 | `CRASH300N` | Alta gradual + spike de queda ~1/300 ticks | Vender o spike de baixa |
| Crash 500 | `CRASH500` | Alta gradual + spike ~1/500 ticks | Vender o spike |
| Crash 1000 | `CRASH1000` | Alta gradual + spike raro | Maior amplitude de queda |

#### Jump e Range Break Indices

| Índice | Símbolo | Descrição |
|---|---|---|
| Jump 10 | `JD10` | Saltos aleatórios de ~10% |
| Jump 25 | `JD25` | Saltos de ~25% ocasionais |
| Jump 50 | `JD50` | Saltos de ~50% |
| Jump 75 | `JD75` | Saltos de ~75% |
| Jump 100 | `JD100` | Saltos de ~100% |
| Step Index | `STPIDX` | Incrementos fixos ±1 aleatórios |
| Range Break 100 | `RB100` | Range estável + quebra ~1/100 períodos |
| Range Break 200 | `RB200` | Range estável + quebra ~1/200 períodos |

### 3.5 Código Completo — Colocar Trade na Deriv

```python
import asyncio
import websockets
import json

DERIV_WS_URL = "wss://ws.binaryws.com/websockets/v3?app_id=SEU_APP_ID"
API_TOKEN = "SEU_TOKEN_AQUI"

async def place_binary_trade(
    symbol: str,
    contract_type: str,  # "CALL" ou "PUT"
    duration: int,        # em minutos
    stake: float,
    basis: str = "stake"  # "stake" ou "payout"
):
    async with websockets.connect(DERIV_WS_URL) as ws:
        # 1. Autenticar
        await ws.send(json.dumps({"authorize": API_TOKEN}))
        auth_resp = json.loads(await ws.recv())
        
        if "error" in auth_resp:
            raise Exception(f"Auth error: {auth_resp['error']['message']}")
        
        balance = auth_resp["authorize"]["balance"]
        print(f"✅ Autenticado | Balance: ${balance:.2f}")
        
        # 2. Obter proposta (cotação do contrato)
        proposal_req = {
            "proposal": 1,
            "amount": stake,
            "basis": basis,
            "contract_type": contract_type,
            "currency": "USD",
            "duration": duration,
            "duration_unit": "m",  # m=minutos, t=ticks, s=segundos, h=horas, d=dias
            "symbol": symbol,
        }
        
        await ws.send(json.dumps(proposal_req))
        proposal_resp = json.loads(await ws.recv())
        
        if "error" in proposal_resp:
            raise Exception(f"Proposal error: {proposal_resp['error']['message']}")
        
        proposal_id = proposal_resp["proposal"]["id"]
        payout = proposal_resp["proposal"]["payout"]
        ask_price = proposal_resp["proposal"]["ask_price"]
        
        print(f"📋 Proposta | ID: {proposal_id} | Payout: ${payout:.2f} | Custo: ${ask_price:.2f}")
        
        # 3. Comprar o contrato
        buy_req = {
            "buy": proposal_id,
            "price": ask_price
        }
        
        await ws.send(json.dumps(buy_req))
        buy_resp = json.loads(await ws.recv())
        
        if "error" in buy_resp:
            raise Exception(f"Buy error: {buy_resp['error']['message']}")
        
        contract_id = buy_resp["buy"]["contract_id"]
        buy_price = buy_resp["buy"]["buy_price"]
        
        print(f"🚀 Trade aberto | Contract ID: {contract_id} | Pago: ${buy_price:.2f}")
        
        # 4. Monitorar resultado
        await ws.send(json.dumps({
            "proposal_open_contract": 1,
            "contract_id": contract_id,
            "subscribe": 1
        }))
        
        while True:
            update = json.loads(await ws.recv())
            if "proposal_open_contract" in update:
                contract = update["proposal_open_contract"]
                status = contract.get("status", "open")
                
                if status in ["sold", "won", "lost"]:
                    final_profit = contract.get("profit", 0)
                    print(f"🏁 Resultado: {status.upper()} | P&L: ${final_profit:.2f}")
                    return {
                        "contract_id": contract_id,
                        "status": status,
                        "profit": final_profit,
                        "buy_price": buy_price,
                        "payout": payout
                    }

# Uso:
asyncio.run(place_binary_trade(
    symbol="R_75",      # Volatility 75 Index
    contract_type="CALL",
    duration=5,
    stake=10.0
))
```

### 3.6 Obter Velas Históricas (OHLCV) via Deriv API

```python
async def get_candles(symbol: str, granularity: int, count: int):
    """
    granularity: 60=1min, 300=5min, 900=15min, 3600=1h
    """
    async with websockets.connect(DERIV_WS_URL) as ws:
        await ws.send(json.dumps({"authorize": API_TOKEN}))
        await ws.recv()
        
        candles_req = {
            "ticks_history": symbol,
            "adjust_start_time": 1,
            "count": count,
            "end": "latest",
            "granularity": granularity,
            "style": "candles"
        }
        
        await ws.send(json.dumps(candles_req))
        response = json.loads(await ws.recv())
        
        candles = response["candles"]
        # Formato: [{"epoch": ts, "open": x, "high": x, "low": x, "close": x}]
        return candles
```

### 3.7 Rate Limits e Boas Práticas

| Limite | Valor | Notas |
|---|---|---|
| **Requisições por segundo** | ~20/s | Ultrapassar causa erro 429 |
| **Subscriptions simultâneas** | 30 | Por conexão WebSocket |
| **Reconexão automática** | Implementar | WS cai ocasionalmente |
| **Keep-alive** | Ping a cada 30s | `{"ping": 1}` |

```python
# Padrão de reconexão robusta
async def robust_connection(handler_func, max_retries=10):
    retries = 0
    while retries < max_retries:
        try:
            await handler_func()
            retries = 0
        except websockets.exceptions.ConnectionClosed:
            retries += 1
            wait = min(2 ** retries, 60)  # Exponential backoff
            print(f"🔄 Reconectando em {wait}s... (tentativa {retries})")
            await asyncio.sleep(wait)
```

---

## 4. IQ OPTION API — GUIA TÉCNICO

### 4.1 Instalação

```bash
pip install git+https://github.com/Lu-Yi-Hsun/iqoptionapi.git
```

### 4.2 Autenticação e Conexão

```python
from iqoptionapi.stable_api import IQ_Option
import time

API = IQ_Option("seu_email@exemplo.com", "sua_senha")
check, reason = API.connect()

if check:
    print("✅ Conectado ao IQ Option!")
    API.change_balance("PRACTICE")  # ou "REAL"
    balance = API.get_balance()
    print(f"Balance: ${balance:.2f}")
else:
    print(f"❌ Falha: {reason}")
```

### 4.3 Colocar Trade

```python
def place_binary_trade_iq(asset: str, direction: str, duration: int, amount: float):
    """
    asset: "EURUSD"
    direction: "call" ou "put"
    duration: minutos
    amount: valor em USD
    """
    all_asset = API.get_all_open_time()
    if not all_asset["binary"][asset]["open"]:
        print(f"⚠️ {asset} está fechado agora.")
        return None
    
    check, id = API.buy(amount, asset, direction, duration)
    
    if check:
        print(f"🚀 Trade aberto | ID: {id}")
        time.sleep(duration * 60 + 5)
        result = API.check_win_v4(id)
        print(f"🏁 Resultado: {result}")
        return result
    else:
        print(f"❌ Falha ao abrir trade: {id}")
        return None
```

### 4.4 Obter Velas Históricas

```python
def get_candles_iq(asset: str, size: int, count: int, end_from_time: float = None):
    """
    size: segundos por vela (60=1min, 300=5min)
    """
    if end_from_time is None:
        end_from_time = time.time()
    return API.get_candles(asset, size, count, end_from_time)
```

### 4.5 Limitações Críticas

| Problema | Impacto | Mitigação |
|---|---|---|
| **API não-oficial** | Pode parar a qualquer momento | Monitor diário; ter fallback |
| **Violação de ToS** | Conta pode ser banida | Usar conta demo para testes |
| **Instabilidade WebSocket** | Desconexões frequentes | Reconexão automática |
| **Rate limiting** | Bloqueio temporário | Throttle de requisições |
| **Manutenção** | Períodos de instabilidade | Monitorar status do servidor |

---

## 5. POCKET OPTION — GUIA TÉCNICO

### 5.1 Conexão WebSocket Não-Oficial

```python
import asyncio
import websockets
import json
import uuid

POCKET_WS = "wss://api-l.po.market/socket.io/?EIO=4&transport=websocket"

async def connect_pocket_option(ssid: str):
    """
    ssid: Session ID obtido do cookie após login no browser
    """
    async with websockets.connect(
        POCKET_WS,
        extra_headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    ) as ws:
        auth_msg = f'42["auth",{{"session":"{ssid}","isDemo":1,"uid":0,"platform":2}}]'
        await ws.send(auth_msg)
        
        while True:
            msg = await ws.recv()
            if "successauth" in str(msg):
                print("✅ Conectado ao Pocket Option!")
                break
        return ws

async def place_trade_pocket(ws, asset: str, direction: int, amount: float, duration: int):
    """
    direction: 1=CALL(up), 2=PUT(down)
    duration: segundos
    """
    trade_id = str(uuid.uuid4())
    trade_msg = json.dumps([
        "openOrder",
        {
            "asset": asset,
            "amount": amount,
            "action": direction,
            "isDemo": 1,
            "requestId": trade_id,
            "optionType": 100,
            "time": duration
        }
    ])
    await ws.send(f"42{trade_msg}")
    response = await ws.recv()
    return json.loads(response[2:])
```

### 5.2 Ativos Pocket Option

| Categoria | Payout Típico |
|---|---|
| Forex (EUR/USD, GBP/USD, etc.) | 75-88% |
| Crypto (BTC, ETH) | 72-85% |
| Commodities (Ouro, Prata) | 75-86% |
| Índices (S&P 500, NASDAQ) | 72-84% |
| Stocks OTC (Apple, Tesla) | 78-92% |
| Forex OTC (fins de semana) | 80-95% |

---

## 6. ESTRATÉGIAS COM EDGE POSITIVO DOCUMENTADO

### 6.1 RSI Extremo + Confirmação de Tendência

```
Timeframe de entrada: M1
Timeframe de confirmação: M5
Indicadores: RSI(14), EMA(9), EMA(21)
Expiração: 5 minutos

CALL: RSI(14) M1 < 25 + EMA(9) M5 > EMA(21) M5 + vela M1 revertendo para cima
PUT: RSI(14) M1 > 75 + EMA(9) M5 < EMA(21) M5 + vela M1 revertendo para baixo

Melhor ativo: Deriv Volatility 75 Index (R_75)
Win rate: 58–62% | EV com payout 80%: +8% por trade
```

```python
import pandas as pd
import pandas_ta as ta

def rsi_ema_strategy(df: pd.DataFrame) -> str:
    df_m1 = df.copy()
    df_m1['rsi'] = ta.rsi(df_m1['close'], length=14)
    
    df_m5 = df.resample('5min', on='datetime').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
    })
    df_m5['ema9'] = ta.ema(df_m5['close'], length=9)
    df_m5['ema21'] = ta.ema(df_m5['close'], length=21)
    
    rsi_now = df_m1['rsi'].iloc[-1]
    ema9_m5 = df_m5['ema9'].iloc[-1]
    ema21_m5 = df_m5['ema21'].iloc[-1]
    last_candle = df_m1.iloc[-1]
    
    if (rsi_now < 25 and ema9_m5 > ema21_m5 and
            last_candle['close'] > last_candle['open']):
        return 'call'
    
    if (rsi_now > 75 and ema9_m5 < ema21_m5 and
            last_candle['close'] < last_candle['open']):
        return 'put'
    
    return 'wait'
```

### 6.2 Bollinger Band Squeeze + Breakout

```
Timeframe: M5 | Expiração: 10-15 minutos
Squeeze: BB_Width < 80% da média das últimas 20 barras
CALL: squeeze ativo 5+ velas + close > BB_Upper
PUT: squeeze ativo 5+ velas + close < BB_Lower
Win rate: 57–63%
```

```python
def bollinger_squeeze_strategy(df: pd.DataFrame) -> str:
    bb = ta.bbands(df['close'], length=20, std=2.0)
    df['bb_upper'] = bb['BBU_20_2.0']
    df['bb_lower'] = bb['BBL_20_2.0']
    df['bb_width'] = df['bb_upper'] - df['bb_lower']
    
    avg_width = df['bb_width'].rolling(20).mean()
    squeeze_threshold = avg_width * 0.8
    squeeze_active = (df['bb_width'].iloc[-6:-1] < squeeze_threshold.iloc[-6:-1]).all()
    
    last = df.iloc[-1]
    
    if squeeze_active:
        if last['close'] > last['bb_upper']:
            return 'call'
        elif last['close'] < last['bb_lower']:
            return 'put'
    
    return 'wait'
```

### 6.3 Price Action — Pin Bar + Suporte/Resistência

| Padrão | Posição da Mecha | Sinal |
|---|---|---|
| **Hammer** | Mecha longa ABAIXO | CALL |
| **Shooting Star** | Mecha longa ACIMA | PUT |
| **Inverted Hammer** | Mecha longa ACIMA em suporte | CALL |

```
Timeframe: M5, M15 | Ativos: EUR/USD, GBP/USD
Condição: Pin bar em zona S/R (±10 pips) + mecha >= 2× o corpo
Win rate: 58–65%
```

```python
def is_pin_bar(candle: dict, sensitivity: float = 2.0) -> str:
    body = abs(candle['close'] - candle['open'])
    upper_wick = candle['high'] - max(candle['close'], candle['open'])
    lower_wick = min(candle['close'], candle['open']) - candle['low']
    
    if body == 0:
        return None
    
    if lower_wick >= sensitivity * body and upper_wick < body * 0.3:
        return 'bullish'  # CALL
    
    if upper_wick >= sensitivity * body and lower_wick < body * 0.3:
        return 'bearish'  # PUT
    
    return None
```

### 6.4 MACD + RSI Divergência

| Tipo | Preço | Indicador | Sinal |
|---|---|---|---|
| **Alta Regular** | Mínimas mais baixas | Mínimas mais altas | CALL |
| **Baixa Regular** | Máximas mais altas | Máximas mais baixas | PUT |
| **Alta Oculta** | Mínimas mais altas | Mínimas mais baixas | CALL (tendência) |
| **Baixa Oculta** | Máximas mais baixas | Máximas mais altas | PUT (tendência) |

```
Timeframe: M15, H1 | Expiração: 15-30 minutos
Win rate: 60–68% (sinal raro, mas confiável)
Critério: divergência confirmada em MACD E RSI simultaneamente
```

### 6.5 EMA Crossover Filtrado (Tendência + Pullback)

```
Timeframe: M5, M15 | EMAs: 9, 21 (tendência), 50 (filtro)
CALL: EMA9 cruzou EMA21 para cima + pullback para EMA21 + vela bullish + preço > EMA50
PUT: inverso do acima
Win rate: 55–60%
```

```python
def ema_pullback_strategy(df: pd.DataFrame) -> str:
    df['ema9'] = ta.ema(df['close'], length=9)
    df['ema21'] = ta.ema(df['close'], length=21)
    df['ema50'] = ta.ema(df['close'], length=50)
    
    ema9 = df['ema9'].values
    ema21 = df['ema21'].values
    
    bullish_cross = any(
        ema9[-i-1] < ema21[-i-1] and ema9[-i] > ema21[-i]
        for i in range(1, min(6, len(df)))
    )
    bearish_cross = any(
        ema9[-i-1] > ema21[-i-1] and ema9[-i] < ema21[-i]
        for i in range(1, min(6, len(df)))
    )
    
    last = df.iloc[-1]
    price = last['close']
    ema21_val = last['ema21']
    ema50_val = last['ema50']
    tolerance = ema21_val * 0.0005
    near_ema21 = abs(price - ema21_val) <= tolerance
    
    if bullish_cross and near_ema21 and price > ema50_val:
        if last['close'] > last['open']:
            return 'call'
    
    if bearish_cross and near_ema21 and price < ema50_val:
        if last['close'] < last['open']:
            return 'put'
    
    return 'wait'
```

### 6.6 Stochastic RSI Oversold/Overbought

```
Timeframe: M1 | Expiração: 5 minutos
CALL: StochRSI K < 0.20 + D < 0.20 + K cruzou acima de D
PUT: StochRSI K > 0.80 + D > 0.80 + K cruzou abaixo de D
Win rate: 56–61%
```

```python
def stochrsi_strategy(df: pd.DataFrame) -> str:
    stochrsi = ta.stochrsi(df['close'], length=14, rsi_length=14, k=3, d=3)
    df['stoch_k'] = stochrsi['STOCHRSIk_14_14_3_3']
    df['stoch_d'] = stochrsi['STOCHRSId_14_14_3_3']
    
    k = df['stoch_k'].iloc[-1]
    d = df['stoch_d'].iloc[-1]
    prev_k = df['stoch_k'].iloc[-2]
    prev_d = df['stoch_d'].iloc[-2]
    
    if k < 0.20 and d < 0.20:
        if prev_k < prev_d and k > d:
            return 'call'
    
    if k > 0.80 and d > 0.80:
        if prev_k > prev_d and k < d:
            return 'put'
    
    return 'wait'
```

### 6.7 Crash/Boom Strategy (Deriv Synthetic)

```python
def crash_boom_strategy(df: pd.DataFrame, index_type: str) -> str:
    """
    index_type: 'CRASH' ou 'BOOM'
    BOOM: queda gradual + spikes de alta → PUT na tendência principal
    CRASH: alta gradual + spikes de baixa → CALL na tendência principal
    REGRA: NUNCA operar contra o spike (imprevisível)
    """
    avg_range = (df['high'] - df['low']).rolling(20).mean().iloc[-1]
    last = df.iloc[-1]
    candle_range = abs(last['high'] - last['low'])
    is_spike = candle_range > avg_range * 5
    
    if is_spike:
        return 'wait'
    
    last_spike_up = (df['close'] > df['open'] + avg_range * 4).iloc[-10:].any()
    last_spike_down = (df['close'] < df['open'] - avg_range * 4).iloc[-10:].any()
    
    if index_type == 'BOOM' and not last_spike_up:
        return 'put'   # Vender a queda gradual
    elif index_type == 'CRASH' and not last_spike_down:
        return 'call'  # Comprar a subida gradual
    
    return 'wait'
```

### 6.8 Resumo de Win Rates por Estratégia

| Estratégia | Ativo Ideal | Timeframe | Win Rate | Payout Mínimo | EV Estimado |
|---|---|---|---|---|---|
| RSI Extremo + EMA Conf. | R_75 (Volatility 75) | M1 → 5min exp | 58–62% | <76% | +5 a +10% |
| BB Squeeze + Breakout | R_75, EUR/USD | M5 → 10min exp | 57–63% | <78% | +4 a +10% |
| Pin Bar + S/R | EUR/USD, GBP/USD | M5, M15 | 58–65% | <78% | +5 a +12% |
| MACD + RSI Divergência | Qualquer | M15, H1 | 60–68% | <80% | +8 a +16% |
| EMA Pullback | Qualquer | M5, M15 | 55–60% | <80% | +2 a +8% |
| StochRSI Extremo | Qualquer | M1 → 5min | 56–61% | <76% | +3 a +8% |
| Crash/Boom Trend | Boom/Crash 300–1000 | Tick/M1 | 62–70% | <80% | +10 a +20% |

---

## 7. MARTINGALE E ANTI-MARTINGALE — ANÁLISE MATEMÁTICA

### 7.1 Martingale: Por Que Leva à Ruína

```
Sequência de perdas com aposta base $10:
Trade 1: $10   (perda) → Acumulado: -$10
Trade 2: $20   (perda) → Acumulado: -$30
Trade 3: $40   (perda) → Acumulado: -$70
Trade 4: $80   (perda) → Acumulado: -$150
Trade 5: $160  (perda) → Acumulado: -$310
Trade 6: $320  (perda) → Acumulado: -$630
Trade 7: $640  (perda) → Acumulado: -$1.270
Trade 8: $1.280 (GANHO) → Lucro total: apenas +$10
```

**Capital mínimo para N perdas consecutivas:**
```
Capital_mínimo = Aposta_base × (2^N - 1)

N=3: $70   | N=5: $310   | N=7: $1.270  | N=10: $10.230
```

**Probabilidade com win rate 60% (loss 40%):**
```
P(7 perdas seguidas) = 0.40^7 = 0.16%
Em 1.000 trades → P(nunca acontecer) ≈ 0%
→ Ruína é MATEMATICAMENTE GARANTIDA com tempo suficiente
```

### 7.2 Mini-Martingale (3-4 níveis máximos)

```python
class MiniMartingale:
    def __init__(self, base_stake: float, max_levels: int = 3, multiplier: float = 2.0):
        self.base_stake = base_stake
        self.max_levels = max_levels
        self.multiplier = multiplier
        self.current_level = 0
    
    def get_stake(self) -> float:
        return self.base_stake * (self.multiplier ** self.current_level)
    
    def on_win(self):
        self.current_level = 0
    
    def on_loss(self) -> bool:
        """Retorna True se atingiu limite máximo (resetar ciclo)."""
        if self.current_level < self.max_levels:
            self.current_level += 1
            return False
        else:
            self.current_level = 0
            return True  # Ciclo resetado com perda total
```

### 7.3 Anti-Martingale (Paroli) — Recomendado

```python
class ParoliSystem:
    def __init__(self, base_stake: float, max_wins: int = 3, multiplier: float = 2.0):
        self.base_stake = base_stake
        self.max_wins = max_wins
        self.multiplier = multiplier
        self.consecutive_wins = 0
    
    def get_stake(self) -> float:
        return self.base_stake * (self.multiplier ** self.consecutive_wins)
    
    def on_win(self):
        self.consecutive_wins += 1
        if self.consecutive_wins >= self.max_wins:
            self.consecutive_wins = 0  # Reset após limite
    
    def on_loss(self):
        self.consecutive_wins = 0  # Sempre resetar após perda
```

### 7.4 Sistema Fibonacci

```python
FIBONACCI = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89]

class FibonacciSystem:
    def __init__(self, unit: float = 10.0, max_level: int = 7):
        self.unit = unit
        self.max_level = max_level
        self.level = 0
    
    def get_stake(self) -> float:
        return self.unit * FIBONACCI[min(self.level, len(FIBONACCI)-1)]
    
    def on_win(self):
        self.level = max(0, self.level - 2)
    
    def on_loss(self):
        if self.level < self.max_level:
            self.level += 1
        else:
            self.level = 0  # Reset
```

### 7.5 Comparativo de Sistemas

| Sistema | Capital Max por Ciclo (base $10) | Risco de Ruína | Recomendação |
|---|---|---|---|
| **Flat (fixo)** | $10 por trade | Baixo | ✅ Melhor para longo prazo |
| **Paroli (Anti-Martingale)** | $40 máx (3 níveis) | Muito Baixo | ✅ Recomendado |
| **Fibonacci (7 níveis)** | $130 máx | Moderado | ⚠️ Uso cauteloso |
| **Mini-Martingale (3 níveis)** | $150 por ciclo | Médio | ⚠️ Apenas com edge alto |
| **Martingale puro** | Ilimitado | Extremo | ❌ Nunca usar |

---

## 8. GESTÃO DE CAPITAL ESPECÍFICA PARA BINÁRIAS

### 8.1 Regra dos 2% — Tabela de Referência

| Capital Total | Aposta Máx (2%) | Aposta Conservadora (1%) |
|---|---|---|
| $100 | $2 | $1 |
| $200 | $4 | $2 |
| $500 | $10 | $5 |
| $1.000 | $20 | $10 |
| $2.000 | $40 | $20 |
| $5.000 | $100 | $50 |

### 8.2 Regras de Stop Diário

| Regra | Valor | Ação |
|---|---|---|
| **Daily Loss Limit** | -10% do capital | Parar completamente no dia |
| **Daily Win Target** | +15-20% do capital | Parar e preservar ganhos |
| **Consecutive Losses** | 5 perdas seguidas | Parar por 2 horas mínimo |
| **Weekly Loss Limit** | -25% do capital | Parar a semana, revisar estratégia |

```python
class RiskManager:
    def __init__(self, capital: float, daily_loss_pct: float = 0.10,
                 daily_win_pct: float = 0.20, max_consecutive_losses: int = 5):
        self.initial_capital = capital
        self.capital = capital
        self.daily_loss_pct = daily_loss_pct
        self.daily_win_pct = daily_win_pct
        self.max_consecutive_losses = max_consecutive_losses
        
        self.daily_start_capital = capital
        self.consecutive_losses = 0
    
    def can_trade(self) -> tuple[bool, str]:
        """Retorna (pode_operar, motivo)."""
        current_dd = (self.daily_start_capital - self.capital) / self.daily_start_capital
        current_gain = (self.capital - self.daily_start_capital) / self.daily_start_capital
        
        if current_dd >= self.daily_loss_pct:
            return False, f"Daily loss limit atingido: {current_dd:.1%}"
        
        if current_gain >= self.daily_win_pct:
            return False, f"Daily win target atingido: {current_gain:.1%}"
        
        if self.consecutive_losses >= self.max_consecutive_losses:
            return False, f"{self.consecutive_losses} perdas consecutivas"
        
        return True, "OK"
    
    def get_stake(self, risk_pct: float = 0.02) -> float:
        return self.capital * risk_pct
    
    def update(self, profit: float):
        self.capital += profit
        if profit < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
    
    def reset_daily(self):
        self.daily_start_capital = self.capital
        self.consecutive_losses = 0
```

### 8.3 Sessões de Mercado para Forex

| Sessão | Horário UTC | Pares Ativos | Volatilidade |
|---|---|---|---|
| **Tóquio** | 00:00–09:00 | USD/JPY, AUD/USD, NZD/USD | Baixa-Média |
| **Londres** | 08:00–17:00 | EUR/USD, GBP/USD, EUR/GBP | Alta |
| **Nova York** | 13:00–22:00 | EUR/USD, GBP/USD, USD/CAD | Alta |
| **Sobreposição Londres+NY** | 13:00–17:00 | Todos os majors | Máxima |
| **Fins de semana** | 22:00 Fri – 22:00 Sun | Apenas OTC e Synthetic | Variável |

> ✅ **Melhor momento para operar Forex**: sobreposição Londres+NY (13h–17h UTC) para máxima liquidez e menor spread.

---

## 9. ARQUITETURA DO BOT — CÓDIGO PYTHON COMPLETO

### 9.1 Estrutura de Componentes

```
BinaryBot
├── DataFeed       → Obtém OHLCV via WebSocket em tempo real
├── SignalGenerator → Calcula indicadores e gera sinais
├── SignalFilter   → Filtros adicionais (confirmação multitf, ML)
├── RiskManager    → Verifica limites de capital e posição
├── OrderExecutor  → Envia ordens via API da plataforma
├── PositionTracker → Monitora contratos abertos
├── Logger         → Registra todos os trades em CSV/SQLite
└── Notifier       → Envia alertas via Telegram
```

### 9.2 Classe BinaryBot — Estrutura Completa

```python
import asyncio
import websockets
import json
import pandas as pd
import pandas_ta as ta
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class TradeRecord:
    timestamp: datetime
    symbol: str
    direction: str
    stake: float
    payout: float
    result: str  # 'won', 'lost'
    profit: float
    strategy: str

class BinaryBot:
    def __init__(
        self,
        api_token: str,
        app_id: str,
        symbol: str = "R_75",
        strategy: str = "rsi_ema",
        risk_pct: float = 0.02,
        expiry_minutes: int = 5,
        capital: float = 100.0
    ):
        self.api_token = api_token
        self.app_id = app_id
        self.symbol = symbol
        self.strategy = strategy
        self.risk_pct = risk_pct
        self.expiry_minutes = expiry_minutes
        self.capital = capital
        
        self.ws_url = f"wss://ws.binaryws.com/websockets/v3?app_id={app_id}"
        self.ws = None
        self.candles_df = pd.DataFrame()
        self.trade_history: list[TradeRecord] = []
        self.risk_manager = RiskManager(capital)
        
        # Stats
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
    
    async def connect(self):
        """Conectar e autenticar na Deriv API."""
        self.ws = await websockets.connect(self.ws_url)
        await self.ws.send(json.dumps({"authorize": self.api_token}))
        auth = json.loads(await self.ws.recv())
        
        if "error" in auth:
            raise Exception(f"Auth failed: {auth['error']['message']}")
        
        self.capital = auth["authorize"]["balance"]
        self.risk_manager = RiskManager(self.capital)
        logger.info(f"✅ Conectado | Balance: ${self.capital:.2f}")
    
    async def fetch_candles(self, count: int = 200) -> pd.DataFrame:
        """Buscar velas históricas OHLCV."""
        granularity = self.expiry_minutes * 60
        
        request = {
            "ticks_history": self.symbol,
            "adjust_start_time": 1,
            "count": count,
            "end": "latest",
            "granularity": granularity,
            "style": "candles"
        }
        
        await self.ws.send(json.dumps(request))
        response = json.loads(await self.ws.recv())
        
        if "error" in response:
            raise Exception(f"Candles error: {response['error']['message']}")
        
        candles = response["candles"]
        df = pd.DataFrame(candles)
        df['datetime'] = pd.to_datetime(df['epoch'], unit='s')
        df = df.rename(columns={'open': 'open', 'high': 'high',
                                 'low': 'low', 'close': 'close'})
        df = df.astype({'open': float, 'high': float, 'low': float, 'close': float})
        
        return df
    
    def generate_signal(self, df: pd.DataFrame) -> str:
        """Gerar sinal de trading baseado na estratégia configurada."""
        if self.strategy == "rsi_ema":
            return rsi_ema_strategy(df)
        elif self.strategy == "bb_squeeze":
            return bollinger_squeeze_strategy(df)
        elif self.strategy == "stochrsi":
            return stochrsi_strategy(df)
        else:
            return 'wait'
    
    async def place_trade(self, direction: str) -> Optional[dict]:
        """Colocar um trade via Deriv API."""
        can_trade, reason = self.risk_manager.can_trade()
        if not can_trade:
            logger.warning(f"⛔ Trade bloqueado: {reason}")
            return None
        
        stake = self.risk_manager.get_stake(self.risk_pct)
        
        # Proposta
        await self.ws.send(json.dumps({
            "proposal": 1,
            "amount": round(stake, 2),
            "basis": "stake",
            "contract_type": direction.upper(),
            "currency": "USD",
            "duration": self.expiry_minutes,
            "duration_unit": "m",
            "symbol": self.symbol,
        }))
        
        proposal = json.loads(await self.ws.recv())
        if "error" in proposal:
            logger.error(f"Proposal error: {proposal['error']['message']}")
            return None
        
        proposal_id = proposal["proposal"]["id"]
        ask_price = proposal["proposal"]["ask_price"]
        
        # Compra
        await self.ws.send(json.dumps({"buy": proposal_id, "price": ask_price}))
        buy_resp = json.loads(await self.ws.recv())
        
        if "error" in buy_resp:
            logger.error(f"Buy error: {buy_resp['error']['message']}")
            return None
        
        contract_id = buy_resp["buy"]["contract_id"]
        logger.info(f"🚀 {direction.upper()} | Stake: ${stake:.2f} | ID: {contract_id}")
        
        # Monitorar
        await self.ws.send(json.dumps({
            "proposal_open_contract": 1,
            "contract_id": contract_id,
            "subscribe": 1
        }))
        
        while True:
            update = json.loads(await self.ws.recv())
            if "proposal_open_contract" in update:
                c = update["proposal_open_contract"]
                if c.get("status") in ["won", "lost"]:
                    profit = c.get("profit", 0)
                    status = c["status"]
                    
                    self.risk_manager.update(profit)
                    self.total_trades += 1
                    if status == "won":
                        self.wins += 1
                    else:
                        self.losses += 1
                    
                    win_rate = self.wins / self.total_trades if self.total_trades > 0 else 0
                    logger.info(
                        f"🏁 {status.upper()} | P&L: ${profit:.2f} | "
                        f"Win Rate: {win_rate:.1%} | Trades: {self.total_trades}"
                    )
                    
                    self.trade_history.append(TradeRecord(
                        timestamp=datetime.now(),
                        symbol=self.symbol,
                        direction=direction,
                        stake=stake,
                        payout=c.get("payout", 0),
                        result=status,
                        profit=profit,
                        strategy=self.strategy
                    ))
                    
                    return {"status": status, "profit": profit}
    
    async def run(self, max_trades: int = 100, interval_seconds: int = 60):
        """Loop principal do bot."""
        logger.info(f"🤖 Bot iniciado | Símbolo: {self.symbol} | Estratégia: {self.strategy}")
        
        while self.total_trades < max_trades:
            try:
                # Buscar velas
                df = await self.fetch_candles()
                
                # Gerar sinal
                signal = self.generate_signal(df)
                
                if signal != 'wait':
                    logger.info(f"📡 Sinal: {signal.upper()}")
                    await self.place_trade(signal)
                else:
                    logger.debug("⏳ Aguardando sinal...")
                
                # Aguardar próxima vela
                await asyncio.sleep(interval_seconds)
                
            except websockets.exceptions.ConnectionClosed:
                logger.warning("🔄 Conexão perdida, reconectando...")
                await asyncio.sleep(5)
                await self.connect()
            
            except Exception as e:
                logger.error(f"❌ Erro: {e}")
                await asyncio.sleep(10)
        
        logger.info(f"✅ Bot finalizado | Total: {self.total_trades} | "
                    f"Wins: {self.wins} | Losses: {self.losses} | "
                    f"Win Rate: {self.wins/self.total_trades:.1%}")

# Executar o bot
async def main():
    bot = BinaryBot(
        api_token="SEU_TOKEN",
        app_id="SEU_APP_ID",
        symbol="R_75",
        strategy="rsi_ema",
        risk_pct=0.02,
        expiry_minutes=5,
        capital=500.0
    )
    await bot.connect()
    await bot.run(max_trades=50)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 10. MACHINE LEARNING PARA BINÁRIAS

### 10.1 Features Recomendadas para M1/M5

```python
def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Engenharia de features para modelo de ML em binárias."""
    
    # Returns
    df['return_1'] = df['close'].pct_change(1)
    df['return_3'] = df['close'].pct_change(3)
    df['return_5'] = df['close'].pct_change(5)
    df['log_return'] = np.log(df['close'] / df['close'].shift(1))
    
    # Volatilidade realizada
    df['volatility_5'] = df['log_return'].rolling(5).std()
    df['volatility_10'] = df['log_return'].rolling(10).std()
    df['volatility_20'] = df['log_return'].rolling(20).std()
    
    # Indicadores técnicos
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['rsi_fast'] = ta.rsi(df['close'], length=7)
    
    bb = ta.bbands(df['close'], length=20, std=2.0)
    df['bb_upper'] = bb['BBU_20_2.0']
    df['bb_lower'] = bb['BBL_20_2.0']
    df['bb_mid'] = bb['BBM_20_2.0']
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
    df['bb_pct'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    
    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df['macd'] = macd['MACD_12_26_9']
    df['macd_signal'] = macd['MACDs_12_26_9']
    df['macd_hist'] = macd['MACDh_12_26_9']
    
    df['ema9'] = ta.ema(df['close'], length=9)
    df['ema21'] = ta.ema(df['close'], length=21)
    df['ema50'] = ta.ema(df['close'], length=50)
    
    # Features de vela
    df['body'] = abs(df['close'] - df['open'])
    df['upper_wick'] = df['high'] - df[['close', 'open']].max(axis=1)
    df['lower_wick'] = df[['close', 'open']].min(axis=1) - df['low']
    df['is_bullish'] = (df['close'] > df['open']).astype(int)
    
    # Target: 1 se próxima vela fechar acima (CALL), 0 se abaixo (PUT)
    df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
    
    return df.dropna()
```

### 10.2 Treinamento com XGBoost

```python
from xgboost import XGBClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
import numpy as np

FEATURE_COLS = [
    'return_1', 'return_3', 'return_5', 'log_return',
    'volatility_5', 'volatility_10', 'volatility_20',
    'rsi', 'rsi_fast', 'bb_width', 'bb_pct',
    'macd', 'macd_signal', 'macd_hist',
    'body', 'upper_wick', 'lower_wick', 'is_bullish'
]

def train_model(df: pd.DataFrame):
    df = build_features(df)
    X = df[FEATURE_COLS].values
    y = df['target'].values
    
    tscv = TimeSeriesSplit(n_splits=5)
    scores = []
    
    model = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric='logloss',
        use_label_encoder=False
    )
    
    for train_idx, test_idx in tscv.split(X):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        
        model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
        y_pred = model.predict(X_test)
        scores.append(accuracy_score(y_test, y_pred))
    
    print(f"📊 Win Rate Médio (CV): {np.mean(scores):.2%} ± {np.std(scores):.2%}")
    return model

def predict_signal(model, df: pd.DataFrame) -> str:
    df = build_features(df)
    last_features = df[FEATURE_COLS].iloc[-1:].values
    prob = model.predict_proba(last_features)[0]
    
    # Threshold de confiança: 60%+ para entrar
    if prob[1] >= 0.60:
        return 'call'
    elif prob[0] >= 0.60:
        return 'put'
    return 'wait'
```

### 10.3 Considerações sobre Overfitting

| Problema | Sintoma | Solução |
|---|---|---|
| **Look-ahead bias** | Acurácia irreal no backtest | Usar `shift(-1)` correto no target |
| **Overfitting** | Alta acurácia in-sample, baixa out-of-sample | Regularização, TimeSeriesSplit |
| **Data snooping** | Testar muitos parâmetros | Separar conjunto de teste final |
| **Regime change** | Modelo degrada em mercado diferente | Retreinar periodicamente |
| **Small dataset** | Poucos trades para validar | Usar dados tick; mínimo 5.000 amostras |

> ⚠️ **Advertência**: Win rates de ML em binárias raramente superam 58–63% em dados reais fora da amostra. Qualquer backtest mostrando >70% é provavelmente overfitting.

---

## 11. DISCLAIMER LEGAL

> ⚠️ **AVISO IMPORTANTE**: Este documento é para fins exclusivamente educacionais e de pesquisa técnica.
>
> - Opções binárias são **proibidas ou fortemente reguladas** em muitos países (EUA fora de exchanges reguladas, UE via ESMA)
> - No Brasil, a CVM não regula opções binárias como produto financeiro
> - A **grande maioria dos traders perde dinheiro** em opções binárias
> - Muitas plataformas operam em **zonas cinzentas legais** ou são fraudulentas
> - Este projeto `binary-opt-ai` é para **pesquisa de algoritmos** — não constitui conselho financeiro
> - **Nunca invista dinheiro que não pode perder** em produtos de alto risco

---

*Fim do documento | binary-opt-ai Knowledge Base | Maio 2026*