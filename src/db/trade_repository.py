"""
Repositório de trades - CRUD para SQLite via aiosqlite.
"""
import json
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any

from src.db.database import get_db

logger = logging.getLogger(__name__)


async def insert_agent(agent_id: str, name: str, symbol: str, timeframe: int,
                       stake: float, strategy: str) -> None:
    """Insere ou substitui um agente no banco de dados."""
    now = datetime.utcnow().isoformat() + "Z"
    async with get_db() as db:
        await db.execute(
            """INSERT OR REPLACE INTO agents
               (id, name, symbol, timeframe, stake, strategy, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (agent_id, name, symbol, timeframe, stake, strategy, now, now)
        )
        await db.commit()


async def update_agent_db(agent_id: str, **kwargs) -> None:
    """Atualiza campos de um agente no banco de dados."""
    if not kwargs:
        return
    now = datetime.utcnow().isoformat() + "Z"
    kwargs["updated_at"] = now
    fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values()) + [agent_id]
    async with get_db() as db:
        await db.execute(
            f"UPDATE agents SET {fields} WHERE id = ?",
            values
        )
        await db.commit()


async def insert_pending_trade(agent_id: str, symbol: str, direction: str,
                                stake: float, strategy: str,
                                opened_at: str) -> int:
    """Insere um trade com result='pending' IMEDIATAMENTE ao iniciar a operação.
    Retorna o rowid gerado para ser usado em finalize_trade() quando o contrato fechar.
    Esta é a função principal para garantir que trades EM CURSO apareçam no banco.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO trades
               (agent_id, symbol, direction, stake, ask_price,
                result, strategy, opened_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (agent_id, symbol, direction, stake, stake, strategy, opened_at)
        )
        await db.commit()
        logger.debug(
            f"[trade_repo] Trade pendente inserido: id={cursor.lastrowid} "
            f"agent={agent_id} dir={direction} stake={stake}"
        )
        return cursor.lastrowid


async def finalize_trade(rowid: int, contract_id: Optional[str],
                          result: str, profit: float,
                          payout: Optional[float] = None,
                          ask_price: Optional[float] = None,
                          entry_price: Optional[float] = None,
                          exit_price: Optional[float] = None,
                          closed_at: Optional[str] = None) -> None:
    """Finaliza um trade pendente inserido por insert_pending_trade().
    Atualiza o registro com o resultado completo vindo da Deriv.
    """
    if not closed_at:
        closed_at = datetime.utcnow().isoformat() + "Z"
    async with get_db() as db:
        await db.execute(
            """UPDATE trades
               SET contract_id = ?, result = ?, profit = ?, payout = ?,
                   ask_price = COALESCE(?, ask_price),
                   entry_price = ?, exit_price = ?, closed_at = ?
               WHERE id = ?""",
            (contract_id, result, profit, payout,
             ask_price, entry_price, exit_price, closed_at, rowid)
        )
        await db.commit()
        logger.debug(
            f"[trade_repo] Trade finalizado: id={rowid} "
            f"contract={contract_id} result={result} profit={profit}"
        )


async def insert_trade(trade_data: Dict[str, Any]) -> int:
    """Insere um novo trade no banco de dados. Retorna o ID gerado.
    ATENÇÃO: Prefira usar insert_pending_trade() + finalize_trade() para
    garantir que trades EM CURSO apareçam no banco durante a execução.
    Esta função é mantida para compatibilidade com código legado.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO trades
               (agent_id, contract_id, symbol, direction, stake, payout,
                ask_price, result, profit, entry_price, exit_price,
                strategy, signal_meta, opened_at, closed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trade_data.get("agent_id"),
                trade_data.get("contract_id"),
                trade_data.get("symbol"),
                trade_data.get("direction"),
                trade_data.get("stake"),
                trade_data.get("payout"),
                trade_data.get("ask_price", trade_data.get("stake")),
                trade_data.get("result", "pending"),
                trade_data.get("profit"),
                trade_data.get("entry_price"),
                trade_data.get("exit_price"),
                trade_data.get("strategy"),
                json.dumps(trade_data.get("signal_meta")) if trade_data.get("signal_meta") else None,
                trade_data.get("opened_at"),
                trade_data.get("closed_at"),
            )
        )
        await db.commit()
        return cursor.lastrowid


async def update_trade_result(contract_id: str, result: str, profit: float,
                               payout: Optional[float] = None,
                               exit_price: Optional[float] = None,
                               closed_at: Optional[str] = None) -> None:
    """Atualiza o resultado de um trade."""
    if not closed_at:
        closed_at = datetime.utcnow().isoformat() + "Z"
    async with get_db() as db:
        await db.execute(
            """UPDATE trades
               SET result = ?, profit = ?, payout = ?, exit_price = ?, closed_at = ?
               WHERE contract_id = ?""",
            (result, profit, payout, exit_price, closed_at, contract_id)
        )
        await db.commit()


async def mark_trade_unknown(contract_id: str) -> None:
    """Marca um trade pendente como desconhecido (recovery de crash) por contract_id."""
    async with get_db() as db:
        await db.execute(
            "UPDATE trades SET result = 'unknown' WHERE contract_id = ? AND result = 'pending'",
            (contract_id,)
        )
        await db.commit()


async def mark_trade_unknown_by_id(rowid: int) -> None:
    """Marca um trade pendente como desconhecido (recovery de crash) por rowid.
    Usado quando o bot é cancelado durante um trade ativo antes de receber o contract_id.
    """
    async with get_db() as db:
        await db.execute(
            "UPDATE trades SET result = 'unknown' WHERE id = ? AND result = 'pending'",
            (rowid,)
        )
        await db.commit()
        logger.debug(f"[trade_repo] Trade id={rowid} marcado como unknown (crash recovery)")


async def get_pending_trades() -> List[Dict]:
    """Retorna todos os trades com resultado pendente."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM trades WHERE result = 'pending'"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_trades_by_agent(agent_id: str, limit: int = 50,
                               offset: int = 0) -> List[Dict]:
    """Retorna os trades de um agente com paginação."""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM trades WHERE agent_id = ?
               ORDER BY opened_at DESC LIMIT ? OFFSET ?""",
            (agent_id, limit, offset)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_all_trades(agent_id: Optional[str] = None,
                          result: Optional[str] = None,
                          limit: int = 50,
                          offset: int = 0,
                          from_date: Optional[str] = None,
                          to_date: Optional[str] = None) -> tuple[List[Dict], int]:
    """Retorna trades com filtros e paginação. Retorna (trades, total)."""
    conditions = []
    params = []

    if agent_id:
        conditions.append("agent_id = ?")
        params.append(agent_id)
    if result:
        conditions.append("result = ?")
        params.append(result)
    if from_date:
        conditions.append("opened_at >= ?")
        params.append(from_date)
    if to_date:
        conditions.append("opened_at <= ?")
        params.append(to_date)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    async with get_db() as db:
        # Total
        count_cursor = await db.execute(
            f"SELECT COUNT(*) FROM trades {where_clause}",
            params
        )
        count_row = await count_cursor.fetchone()
        total = count_row[0] if count_row else 0

        # Trades
        cursor = await db.execute(
            f"SELECT * FROM trades {where_clause} ORDER BY opened_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        )
        rows = await cursor.fetchall()
        trades = [dict(row) for row in rows]

    return trades, total


async def get_agent_stats(agent_id: Optional[str] = None,
                           period: str = "all") -> Dict:
    """Calcula estatísticas agregadas de trades."""
    conditions = ["result IN ('won', 'lost')"]
    params = []

    if agent_id:
        conditions.append("agent_id = ?")
        params.append(agent_id)

    if period == "today":
        conditions.append("date(opened_at) = date('now')")
    elif period == "week":
        conditions.append("opened_at >= datetime('now', '-7 days')")
    elif period == "month":
        conditions.append("opened_at >= datetime('now', '-30 days')")

    where_clause = "WHERE " + " AND ".join(conditions)

    async with get_db() as db:
        cursor = await db.execute(
            f"""SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'lost' THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(CASE WHEN profit > 0 THEN profit ELSE 0 END), 0) as gross_profit,
                COALESCE(SUM(CASE WHEN profit < 0 THEN ABS(profit) ELSE 0 END), 0) as gross_loss,
                COALESCE(SUM(profit), 0) as net_pnl
            FROM trades {where_clause}""",
            params
        )
        row = await cursor.fetchone()

    if not row or row["total_trades"] == 0:
        return {
            "period": period,
            "agent_id": agent_id,
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "net_pnl": 0.0,
            "profit_factor": 0.0,
            "max_consecutive_wins": 0,
            "max_consecutive_losses": 0,
        }

    total = row["total_trades"]
    wins = row["wins"] or 0
    gross_profit = row["gross_profit"] or 0.0
    gross_loss = row["gross_loss"] or 0.0

    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

    return {
        "period": period,
        "agent_id": agent_id,
        "total_trades": total,
        "wins": wins,
        "losses": row["losses"] or 0,
        "win_rate": wins / total if total > 0 else 0.0,
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "net_pnl": round(row["net_pnl"] or 0.0, 2),
        "profit_factor": round(profit_factor, 2),
        "max_consecutive_wins": 0,
        "max_consecutive_losses": 0,
    }


async def get_pnl_history(agent_id: Optional[str] = None,
                           limit: int = 100) -> List[Dict]:
    """Retorna série temporal de P&L acumulado para gráficos."""
    conditions = ["result IN ('won', 'lost')"]
    params = []

    if agent_id:
        conditions.append("agent_id = ?")
        params.append(agent_id)

    where_clause = "WHERE " + " AND ".join(conditions)

    async with get_db() as db:
        cursor = await db.execute(
            f"""SELECT opened_at, profit FROM trades {where_clause}
                ORDER BY opened_at ASC LIMIT ?""",
            params + [limit]
        )
        rows = await cursor.fetchall()

    data_points = []
    cumulative = 0.0
    for row in rows:
        cumulative += (row["profit"] or 0.0)
        data_points.append({
            "timestamp": row["opened_at"],
            "cumulative_pnl": round(cumulative, 2)
        })

    return data_points


async def get_recent_trades_by_agent(agent_id: str, limit: int = 5) -> List[Dict]:
    """Retorna os N últimos trades de um agente, incluindo os pendentes (em curso)."""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT direction, result, profit, opened_at, contract_id, stake, strategy, symbol
               FROM trades WHERE agent_id = ?
               ORDER BY opened_at DESC LIMIT ?""",
            (agent_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_open_trades() -> List[Dict]:
    """Retorna todos os trades com resultado pendente (em curso)."""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM trades WHERE result = 'pending'
               ORDER BY opened_at DESC""",
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
