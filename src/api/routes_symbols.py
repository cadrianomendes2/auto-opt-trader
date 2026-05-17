"""
Rotas REST para ranking de símbolos por Expected Value e auto-seleção.
"""
import json
import logging
import os
from typing import Optional

import websockets
from fastapi import APIRouter, HTTPException, Query, status

from src.core.symbol_scorer import SymbolScorer, DEFAULT_SYMBOLS
from src.core.agent_manager import agent_manager
from src.db import trade_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["symbols"])


async def _get_active_symbols_from_deriv() -> list:
    """Obtém símbolos Synthetic Indices ativos da Deriv API."""
    ws_url = os.getenv("DERIV_WS_URL", "wss://ws.binaryws.com/websockets/v3")
    app_id = os.getenv("DERIV_APP_ID", "1")
    token = os.getenv("DERIV_API_TOKEN", "eYf2ydKTUpN2cgz")
    url = f"{ws_url}?app_id={app_id}"

    try:
        async with websockets.connect(url, close_timeout=5) as ws:
            await ws.send(json.dumps({"authorize": token, "req_id": 1}))
            auth = json.loads(await ws.recv())
            if "error" in auth:
                return DEFAULT_SYMBOLS

            await ws.send(json.dumps({"active_symbols": "brief", "req_id": 2}))
            sym_resp = json.loads(await ws.recv())
            symbols = sym_resp.get("active_symbols", [])

        # Filtrar apenas Synthetic Indices para scoring (mais relevantes)
        synthetic = [
            {
                "symbol": s["symbol"],
                "display_name": s.get("display_name", s["symbol"]),
            }
            for s in symbols
            if s.get("market") in ("synthetic_index", "volidx")
            and s.get("exchange_is_open", 1) == 1
        ]
        return synthetic if synthetic else DEFAULT_SYMBOLS

    except Exception as e:
        logger.warning(f"Não foi possível obter símbolos da Deriv: {e}. Usando lista padrão.")
        return DEFAULT_SYMBOLS


async def _get_historical_win_rates() -> dict:
    """
    Obtém win rates históricos por símbolo a partir do banco de dados.
    Retorna: { "R_75": 0.58, "R_50": 0.52, ... }
    """
    try:
        trades, _total = await trade_repository.get_all_trades(limit=500)
        symbol_stats: dict = {}

        for t in trades:
            sym = t.get("symbol")  # type: ignore[union-attr]
            result = t.get("result")  # type: ignore[union-attr]
            if not sym or result not in ("won", "lost"):
                continue
            if sym not in symbol_stats:
                symbol_stats[sym] = {"wins": 0, "total": 0}
            symbol_stats[sym]["total"] += 1
            if result == "won":
                symbol_stats[sym]["wins"] += 1

        return {
            sym: round(stats["wins"] / stats["total"], 4)
            for sym, stats in symbol_stats.items()
            if stats["total"] >= 10
        }
    except Exception as e:
        logger.warning(f"Erro ao obter win rates históricos: {e}")
        return {}


@router.get("/symbols/ranked")
async def get_ranked_symbols(
    duration_minutes: int = Query(default=5, ge=1, le=1440, description="Timeframe em minutos"),
    multiplier: int = Query(default=2, ge=1, le=5, description="Multiplicador para cálculo de payout"),
    limit: int = Query(default=10, ge=1, le=50, description="Máximo de símbolos a retornar"),
):
    """
    Retorna todos os símbolos ranqueados por score de EV para o timeframe dado.

    Score = win_rate_estimado × payout_líquido - (1 - win_rate_estimado)

    onde win_rate_estimado = histórico × 0.4 + técnico × 0.6
    """
    try:
        # Obter símbolos disponíveis e win rates históricos em paralelo
        symbols = await _get_active_symbols_from_deriv()

        # Limitar a símbolos mais relevantes para não demorar demais
        # Priorizar os mais conhecidos
        priority = ["R_75", "R_50", "R_100", "1HZ75V", "1HZ100V", "R_25", "1HZ50V", "R_10", "1HZ25V", "1HZ10V"]
        symbols_sorted = sorted(
            symbols,
            key=lambda s: priority.index(s["symbol"]) if s["symbol"] in priority else len(priority)
        )
        symbols_to_score = symbols_sorted[:min(limit, len(symbols_sorted))]

        hist_win_rates = await _get_historical_win_rates()

        scorer = SymbolScorer(multiplier=multiplier)
        rankings = await scorer.rank_all_symbols(
            symbols=symbols_to_score,
            duration_minutes=duration_minutes,
            historical_win_rates=hist_win_rates,
        )

        # Formatar EV como percentagem para exibição
        for r in rankings:
            r["ev_pct"] = round(r["score"] * 100, 2)
            r["win_rate_pct"] = round(r["win_rate_estimate"] * 100, 1)
            r["volatility_pct"] = round(r["volatility_score"] * 100, 1)
            r["trend_pct"] = round(r["trend_strength"] * 100, 1)
            r["signal_freq_pct"] = round(r["signal_frequency"] * 100, 1)

        return {
            "duration_minutes": duration_minutes,
            "multiplier": multiplier,
            "total": len(rankings),
            "rankings": rankings,
            "best_symbol": rankings[0]["symbol"] if rankings else "R_75",
        }

    except Exception as e:
        logger.error(f"Erro ao ranquear símbolos: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Erro ao calcular ranking de símbolos: {e}",
        )


@router.post("/agents/{agent_id}/auto-select-symbol")
async def auto_select_symbol(agent_id: str):
    """
    1. Obtém lista de símbolos disponíveis via Deriv API
    2. Calcula score de EV para cada um
    3. Seleciona o de maior score para o timeframe do agente
    4. Atualiza o símbolo do agente
    5. Reinicia o bot com o novo símbolo

    Retorna: {"old_symbol": "R_75", "new_symbol": "R_50", "score": 0.09, "rankings": [...]}
    """
    if agent_id not in agent_manager.agents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found",
        )

    agent = agent_manager.agents[agent_id]
    old_symbol = agent.get("symbol", "R_75")
    duration_minutes = agent.get("timeframe_minutes", 5)

    try:
        symbols = await _get_active_symbols_from_deriv()

        # Limitar a símbolos prioritários para velocidade
        priority = ["R_75", "R_50", "R_100", "1HZ75V", "1HZ100V", "R_25"]
        symbols_to_score = [
            s for s in symbols if s["symbol"] in priority
        ] or symbols[:6]

        hist_win_rates = await _get_historical_win_rates()

        scorer = SymbolScorer(multiplier=agent.get("multiplier", 2))
        rankings = await scorer.rank_all_symbols(
            symbols=symbols_to_score,
            duration_minutes=duration_minutes,
            historical_win_rates=hist_win_rates,
        )

        if not rankings:
            raise ValueError("Nenhum símbolo pôde ser avaliado")

        best = rankings[0]
        new_symbol = best["symbol"]

        # Adicionar percentagens formatadas
        for r in rankings:
            r["ev_pct"] = round(r["score"] * 100, 2)
            r["win_rate_pct"] = round(r["win_rate_estimate"] * 100, 1)

        # Atualizar o agente se o símbolo mudou
        if new_symbol != old_symbol:
            await agent_manager.update_agent(agent_id, {"symbol": new_symbol})
            logger.info(
                f"Auto-select símbolo para {agent_id}: {old_symbol} → {new_symbol} "
                f"(score={best['score']:.4f})"
            )
        else:
            logger.info(
                f"Auto-select símbolo para {agent_id}: {old_symbol} mantido "
                f"(já é o melhor, score={best['score']:.4f})"
            )

        return {
            "agent_id": agent_id,
            "old_symbol": old_symbol,
            "new_symbol": new_symbol,
            "changed": new_symbol != old_symbol,
            "score": best["score"],
            "ev_pct": round(best["score"] * 100, 2),
            "win_rate_estimate": best["win_rate_estimate"],
            "rankings": rankings,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no auto-select de símbolo para {agent_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro no auto-select de símbolo: {e}",
        )
