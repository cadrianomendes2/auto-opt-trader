"""
Rotas REST para gerenciamento de agentes de trading.
"""
import json
import logging
import os
import re
import uuid
from datetime import datetime
from typing import Optional

import websockets
from fastapi import APIRouter, HTTPException, status

from src.core.agent_manager import agent_manager
from src.core.signal_generator import STRATEGIES_INFO
from src.models.agent_model import AgentCreateRequest, AgentUpdateRequest
from src.db import trade_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["agents"])


@router.get("/agents")
async def list_agents():
    """Lista todos os agentes com estatísticas atuais."""
    agents = [agent_manager.get_agent_summary(aid) for aid in agent_manager.agents.keys()]
    return {"agents": [a for a in agents if a is not None]}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Retorna dados completos de um agente específico."""
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found"
        )
    return agent


@router.post("/agents", status_code=status.HTTP_201_CREATED)
async def create_agent(request: AgentCreateRequest):
    """Cria um novo agente e inicia seu bot de trading."""
    # Auto-gerar id se não fornecido
    if not request.id:
        if request.name:
            base = re.sub(r'[^a-z0-9]+', '-', request.name.lower()).strip('-')
            request.id = f"{base}-{uuid.uuid4().hex[:6]}"
        else:
            request.id = f"agent-{uuid.uuid4().hex[:8]}"

    # Garantir name padrão se não fornecido
    if not request.name:
        request.name = f"Agent {request.id}"

    if request.id in agent_manager.agents:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent with id '{request.id}' already exists"
        )

    # Remover initial_status do config antes de criar (não é campo do AgentConfig)
    initial_status = request.initial_status
    agent_config = request.model_dump(exclude={"initial_status"})
    if "risk" in agent_config and hasattr(agent_config["risk"], "model_dump"):
        agent_config["risk"] = agent_config["risk"].model_dump()

    try:
        await agent_manager.create_agent(agent_config)

        # Se solicitado criar pausado (ex: agente duplicado), pausar imediatamente
        if initial_status == "paused":
            await agent_manager.pause_agent(request.id)
            return {
                "id": request.id,
                "status": "paused",
                "message": "Agent created in paused state (duplicate configuration)"
            }

        return {
            "id": request.id,
            "status": "running",
            "message": "Agent created and started successfully"
        }
    except Exception as e:
        logger.error(f"Erro ao criar agente {request.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/agents/{agent_id}")
async def update_agent(agent_id: str, request: AgentUpdateRequest):
    """Atualiza a configuração de um agente. O bot é reiniciado automaticamente."""
    if agent_id not in agent_manager.agents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found"
        )

    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    if "risk" in updates and hasattr(updates["risk"], "model_dump"):
        updates["risk"] = updates["risk"].model_dump()

    try:
        await agent_manager.update_agent(agent_id, updates)
        return {
            "id": agent_id,
            "status": "running",
            "message": "Agent updated and restarted with new config"
        }
    except Exception as e:
        logger.error(f"Erro ao atualizar agente {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    """Para e remove um agente. O histórico de trades é preservado."""
    if agent_id not in agent_manager.agents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found"
        )

    try:
        await agent_manager.delete_agent(agent_id)
        return {
            "id": agent_id,
            "message": "Agent stopped and removed. Trade history preserved."
        }
    except Exception as e:
        logger.error(f"Erro ao deletar agente {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/agents/{agent_id}/pause")
async def pause_agent(agent_id: str):
    """Pausa um agente em execução."""
    if agent_id not in agent_manager.agents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found"
        )

    try:
        await agent_manager.pause_agent(agent_id)
        return {"agent_id": agent_id, "status": "paused"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/agents/{agent_id}/resume")
async def resume_agent(agent_id: str):
    """Retoma um agente pausado."""
    if agent_id not in agent_manager.agents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found"
        )

    try:
        await agent_manager.resume_agent(agent_id)
        return {"agent_id": agent_id, "status": "running"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/agents/{agent_id}/reset-stats")
async def reset_agent_stats(agent_id: str):
    """Zera os contadores de runtime de um agente."""
    if agent_id not in agent_manager.agents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found"
        )

    try:
        await agent_manager.reset_stats(agent_id)
        return {"agent_id": agent_id, "message": "Runtime stats reset"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/agents/{agent_id}/restart")
async def restart_agent(agent_id: str):
    """Para e reinicia um agente (reset completo do loop de trading)."""
    if agent_id not in agent_manager.agents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found"
        )

    try:
        # Usar update_agent sem mudanças de config — apenas reinicia o bot
        config_snapshot = {
            k: v for k, v in agent_manager.agents[agent_id].items()
            if k not in ("runtime", "status")
        }
        await agent_manager.update_agent(agent_id, config_snapshot)
        return {
            "agent_id": agent_id,
            "status": "running",
            "message": "Agent restarted successfully",
        }
    except Exception as e:
        logger.error(f"Erro ao reiniciar agente {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/agents/{agent_id}/coin-flip-test")
async def coin_flip_test(agent_id: str):
    """Executa um sorteio de coin flip manual para o agente especificado.
    Não abre trades reais — apenas simula o sorteio e retorna o resultado.
    Útil para testar o painel de debug.
    """
    if agent_id not in agent_manager.agents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found"
        )

    import random

    agent_config = agent_manager.agents[agent_id]
    strategy_params = agent_config.get("strategy_params", {})

    # Sorteio coin flip — respeita seed se configurado nos params
    seed = strategy_params.get("seed", None)
    rng = random.Random(seed) if seed is not None else random.Random()
    result = rng.choice(["CALL", "PUT"])
    timestamp = datetime.utcnow().isoformat() + "Z"

    # Buscar countdown_log do bot ativo (se existir)
    bot_task = agent_manager.bot_instances.get(agent_id)
    countdown_log = []
    if bot_task and hasattr(bot_task, "get_countdown_log"):
        countdown_log = bot_task.get_countdown_log()

    return {
        "agent_id": agent_id,
        "agent_name": agent_config.get("name", agent_id),
        "strategy": agent_config.get("strategy", "unknown"),
        "result": result,           # "CALL" ou "PUT"
        "timestamp": timestamp,
        "timeframe_minutes": agent_config.get("timeframe_minutes", 5),
        "symbol": agent_config.get("symbol", "R_75"),
        "recent_countdown_log": countdown_log,
        "note": "Sorteio simulado — nenhum trade real foi aberto",
    }


@router.get("/agents/{agent_id}/trades")
async def get_agent_trades(agent_id: str, limit: int = 20, offset: int = 0):
    """Retorna o histórico de trades de um agente."""
    if agent_id not in agent_manager.agents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found"
        )

    trades = await trade_repository.get_trades_by_agent(agent_id, limit, offset)
    return {"agent_id": agent_id, "trades": trades}


@router.post("/panic")
async def panic_stop():
    """Para TODOS os agentes imediatamente (PANIC STOP)."""
    stopped_agents = []
    
    for agent_id in list(agent_manager.agents.keys()):
        try:
            await agent_manager._stop_bot(agent_id)
            agent_manager.agents[agent_id]["status"] = "stopped"
            stopped_agents.append(agent_id)
        except Exception as e:
            logger.error(f"Erro ao parar agente {agent_id} no PANIC: {e}")

    await agent_manager.save_to_disk()
    
    logger.warning(f"🚨 PANIC STOP executado! {len(stopped_agents)} agentes parados: {stopped_agents}")
    
    return {
        "stopped": len(stopped_agents),
        "agents": stopped_agents,
        "message": "PANIC STOP executado com sucesso",
    }


@router.get("/strategies")
async def list_strategies():
    """Lista as estratégias disponíveis.
    
    Retorna diretamente um array de estratégias para facilitar consumo por testes
    e clientes que esperam um array na raiz da resposta.
    """
    return STRATEGIES_INFO


@router.get("/symbols")
async def list_symbols():
    """
    Lista todos os símbolos disponíveis na conta Deriv agrupados por mercado.
    Consulta a API Deriv em tempo real via active_symbols.
    """
    ws_url = os.getenv("DERIV_WS_URL", "wss://ws.binaryws.com/websockets/v3")
    app_id = os.getenv("DERIV_APP_ID", "1")
    token = os.getenv("DERIV_API_TOKEN", "eYf2ydKTUpN2cgz")
    url = f"{ws_url}?app_id={app_id}"

    try:
        async with websockets.connect(url, close_timeout=5) as ws:
            # Autenticar
            await ws.send(json.dumps({"authorize": token, "req_id": 1}))
            auth_raw = await ws.recv()
            auth = json.loads(auth_raw)
            if "error" in auth:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Erro de autenticação Deriv: {auth['error'].get('message')}"
                )

            # Buscar símbolos ativos
            await ws.send(json.dumps({"active_symbols": "brief", "req_id": 2}))
            sym_raw = await ws.recv()
            sym_resp = json.loads(sym_raw)

            if "error" in sym_resp:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Erro ao buscar símbolos: {sym_resp['error'].get('message')}"
                )

            symbols = sym_resp.get("active_symbols", [])

        # Agrupar por mercado com sugestão de timeframe
        MARKET_LABELS = {
            "synthetic_index": "Synthetic Indices",
            "volidx": "Synthetic Indices",
            "forex": "Forex",
            "cryptocurrency": "Crypto",
            "indices": "Stock Indices",
            "commodities": "Commodities",
        }

        # Mapeamento de símbolo → timeframes recomendados
        TIMEFRAME_HINTS = {
            "R_75": ["2", "5", "10"],
            "R_50": ["2", "5", "10"],
            "R_100": ["2", "5", "10"],
            "1HZ75V": ["1", "2", "5"],
            "1HZ100V": ["1", "2", "5"],
            "1HZ50V": ["1", "2", "5"],
        }
        DEFAULT_FOREX_TF = ["10", "15", "30"]
        DEFAULT_CRYPTO_TF = ["5", "10", "15"]

        grouped: dict = {}
        for s in symbols:
            market = s.get("market", "other")
            label = MARKET_LABELS.get(market, market.replace("_", " ").title())

            if label not in grouped:
                grouped[label] = []

            sym_id = s["symbol"]
            hints = TIMEFRAME_HINTS.get(
                sym_id,
                DEFAULT_FOREX_TF if market == "forex" else (
                    DEFAULT_CRYPTO_TF if market == "cryptocurrency" else ["5", "10"]
                )
            )

            grouped[label].append({
                "symbol": sym_id,
                "display_name": s.get("display_name", sym_id),
                "market": market,
                "market_label": label,
                "is_open": s.get("exchange_is_open", 1) == 1,
                "recommended_timeframes": hints,
            })

        # Ordenação: Synthetic primeiro, depois Forex, Crypto, outros
        ORDER = ["Synthetic Indices", "Forex", "Crypto", "Stock Indices", "Commodities"]
        result = []
        for cat in ORDER:
            if cat in grouped:
                result.append({"category": cat, "symbols": grouped[cat]})
        # Categorias não previstas
        for cat, syms in grouped.items():
            if cat not in ORDER:
                result.append({"category": cat, "symbols": syms})

        return {
            "total": len(symbols),
            "categories": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao listar símbolos: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Não foi possível conectar à Deriv API: {e}"
        )


@router.get("/health")
async def health_check():
    """Health check do servidor."""
    import time
    from src.db.database import DB_PATH

    running = sum(
        1 for aid in agent_manager.agents
        if agent_manager.agents[aid].get("status") == "running"
    )

    return {
        "status": "ok",
        "version": "1.0.0",
        "agents_running": running,
        "agents_total": len(agent_manager.agents),
        "db_connected": DB_PATH.exists(),
    }
