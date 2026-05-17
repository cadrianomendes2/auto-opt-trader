"""
Rotas REST para histórico de trades e estatísticas.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from src.db import trade_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["trades"])


@router.get("/trades")
async def list_trades(
    agent_id: Optional[str] = Query(default=None),
    result: Optional[str] = Query(default=None, pattern="^(won|lost|pending|unknown)$"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    from_date: Optional[str] = Query(default=None),
    to_date: Optional[str] = Query(default=None),
    include_open: bool = Query(default=True),
):
    """Lista trades com paginação e filtros opcionais.
    
    Por padrão (include_open=True), inclui sempre os trades com status 'pending' (em curso)
    mesmo quando outros filtros estão ativos, garantindo que apareçam no dashboard após refresh.
    """
    trades, total = await trade_repository.get_all_trades(
        agent_id=agent_id,
        result=result,
        limit=limit,
        offset=offset,
        from_date=from_date,
        to_date=to_date,
    )

    # Se include_open=True e não estamos filtrando explicitamente por resultado,
    # garantir que os trades pendentes (em curso) apareçam sempre no topo.
    # Usa t["id"] (rowid do banco) como chave de dedup — contract_id pode ser NULL
    # para trades inseridos como pending antes da Deriv confirmar.
    if include_open and not result:
        open_trades = await trade_repository.get_open_trades()
        # Coletar IDs (rowids) dos trades já presentes no resultado principal
        existing_rowids = {t.get("id") for t in trades if t.get("id") is not None}
        pending_extra = [t for t in open_trades if t.get("id") not in existing_rowids]
        if pending_extra:
            trades = pending_extra + trades
            total += len(pending_extra)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "trades": trades,
    }


@router.get("/trades/stats")
async def get_trade_stats(
    agent_id: Optional[str] = Query(default=None),
    period: str = Query(default="all", pattern="^(today|week|month|all)$"),
):
    """Retorna estatísticas agregadas de trades."""
    stats = await trade_repository.get_agent_stats(agent_id=agent_id, period=period)
    return stats


@router.get("/trades/pnl-history")
async def get_pnl_history(
    agent_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
):
    """Retorna série temporal de P&L acumulado para gráficos.
    
    Retorna diretamente um array de data_points para facilitar consumo por testes
    e clientes que esperam um array na raiz da resposta.
    """
    data_points = await trade_repository.get_pnl_history(agent_id=agent_id, limit=limit)
    return data_points


@router.get("/trades/recent")
async def get_recent_trades(
    agent_id: Optional[str] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
):
    """Retorna os N últimos trades ordenados do mais antigo para o mais recente.
    Usado para exibição dos quadradinhos de histórico nos cards de agente.
    """
    if agent_id:
        # get_recent_trades_by_agent retorna DESC (mais recente primeiro)
        trades_desc = await trade_repository.get_recent_trades_by_agent(agent_id=agent_id, limit=limit)
        trades = list(reversed(trades_desc))  # ASC: mais antigo → mais recente
    else:
        # get_all_trades retorna DESC; inverter para ASC
        trades_raw, _ = await trade_repository.get_all_trades(limit=limit)
        trades = list(reversed(trades_raw))

    return {
        "agent_id": agent_id,
        "trades": trades,  # ordem ASC: mais antigo → mais recente
    }
