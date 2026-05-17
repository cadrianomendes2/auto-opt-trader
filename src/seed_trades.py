"""
seed_trades.py — Popula o banco de dados SQLite com 50 trades realistas para testar a UI.

Distribuição:
- 50 trades nos últimos 30 dias
- 5 agentes: r75-2min, r75-5min, r75-10min, r75-15min, r75-30min
- 55% win rate
- Stakes: $2, $5, $10, $15, $30 (por agente)
- Payout win: +stake*0.32, loss: -stake*0.02 (sell forçado)

Execução:
    python3 src/seed_trades.py

Nota: Cada execução gera IDs únicos via uuid4 — pode ser executado múltiplas vezes sem conflito.
"""

import sqlite3
import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "state" / "trades.db"

AGENTS = [
    {"id": "r75-2min",  "name": "R75 2min",  "stake": 2.0,  "timeframe": 2},
    {"id": "r75-5min",  "name": "R75 5min",  "stake": 5.0,  "timeframe": 5},
    {"id": "r75-10min", "name": "R75 10min", "stake": 10.0, "timeframe": 10},
    {"id": "r75-15min", "name": "R75 15min", "stake": 15.0, "timeframe": 15},
    {"id": "r75-30min", "name": "R75 30min", "stake": 30.0, "timeframe": 30},
]

DIRECTIONS = ["MULTUP", "MULTDOWN"]
STRATEGIES = ["rsi_ema", "bb_squeeze", "stochrsi", "ema_pullback"]
WIN_RATE = 0.55
TOTAL_TRADES = 50
DAYS_BACK = 30

rng = random.Random()  # seed aleatório para IDs únicos em cada execução


def main():
    if not DB_PATH.exists():
        print(f"❌ Banco não encontrado em {DB_PATH}")
        print("   Execute o servidor pelo menos uma vez para criar o banco.")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Verificar/garantir que os agentes existem
    now_str = datetime.utcnow().isoformat() + "Z"
    for agent in AGENTS:
        cur.execute(
            """INSERT OR IGNORE INTO agents (id, name, symbol, timeframe, stake, strategy, created_at, updated_at)
               VALUES (?, ?, 'R_75', ?, ?, 'rsi_ema', ?, ?)""",
            (agent["id"], agent["name"], agent["timeframe"], agent["stake"], now_str, now_str)
        )
    conn.commit()

    # Gerar 50 trades distribuídos nos últimos 30 dias
    now = datetime.utcnow()
    
    # Calcular quantos wins e losses
    n_wins = round(TOTAL_TRADES * WIN_RATE)
    n_losses = TOTAL_TRADES - n_wins
    results = ["won"] * n_wins + ["lost"] * n_losses
    rng.shuffle(results)

    # Gerar timestamps distribuídos: ~2 trades/dia, horários aleatórios
    timestamps = []
    for i in range(TOTAL_TRADES):
        days_ago = rng.randint(0, DAYS_BACK - 1)
        hour = rng.randint(8, 22)
        minute = rng.randint(0, 59)
        second = rng.randint(0, 59)
        ts = now - timedelta(days=days_ago, hours=(now.hour - hour), minutes=(now.minute - minute), seconds=second)
        # Garantir que o timestamp não é futuro
        if ts > now:
            ts = now - timedelta(hours=rng.randint(1, 24))
        timestamps.append(ts)
    
    timestamps.sort()  # Ordenar cronologicamente

    # Distribuir entre os 5 agentes (10 por agente)
    agent_cycle = []
    for agent in AGENTS:
        agent_cycle.extend([agent] * 10)
    rng.shuffle(agent_cycle)

    inserted = 0
    total_pnl = 0.0
    wins = 0
    losses = 0

    for i, (ts, result, agent) in enumerate(zip(timestamps, results, agent_cycle)):
        stake = agent["stake"]
        direction = rng.choice(DIRECTIONS)
        strategy = rng.choice(STRATEGIES)

        # Calcular profit
        if result == "won":
            profit = round(stake * 0.32, 2)
            payout = round(stake + profit, 2)
            wins += 1
        else:
            profit = round(-stake * 0.02, 2)  # fee de sell forçado
            payout = round(stake + profit, 2)
            losses += 1

        total_pnl += profit

        opened_at = ts.isoformat() + "Z"
        closed_at = (ts + timedelta(minutes=agent["timeframe"])).isoformat() + "Z"
        # UUID4 garante unicidade entre múltiplas execuções do seed
        contract_id = f"SEED_{uuid.uuid4().hex}"

        # Entrada e saída de preço simuladas
        entry_price = round(rng.uniform(5000, 15000), 3)
        exit_price = round(entry_price * (1 + rng.uniform(-0.01, 0.01)), 3)

        try:
            cur.execute(
                """INSERT OR IGNORE INTO trades
                   (agent_id, contract_id, symbol, direction, stake, payout, ask_price,
                    result, profit, entry_price, exit_price, strategy, opened_at, closed_at)
                   VALUES (?, ?, 'R_75', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    agent["id"], contract_id, direction, stake, payout, stake,
                    result, profit, entry_price, exit_price, strategy,
                    opened_at, closed_at
                )
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass  # contract_id duplicado, ignorar

    conn.commit()
    conn.close()

    actual_wr = (wins / inserted * 100) if inserted > 0 else 0

    print("=" * 50)
    print("✅ Seed de trades concluído!")
    print(f"   Trades inseridos : {inserted}")
    print(f"   Wins             : {wins}")
    print(f"   Losses           : {losses}")
    print(f"   Win rate real    : {actual_wr:.1f}%")
    print(f"   P&L total        : ${total_pnl:+.2f}")
    print(f"   Banco            : {DB_PATH}")
    print("=" * 50)


if __name__ == "__main__":
    main()
