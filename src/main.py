"""
Entry point da aplicação FastAPI - Binary Options Trading Dashboard.
"""
import logging
import os

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.db.database import init_db
from src.core.agent_manager import agent_manager
from src.api.websocket_hub import connection_manager, websocket_endpoint
from src.api.routes_agents import router as agents_router
from src.api.routes_trades import router as trades_router
from src.api.routes_models import router as models_router
from src.api.routes_analytics import router as analytics_router, account_router
from src.api.routes_symbols import router as symbols_router
from src.api.routes_dev import router as dev_router
from src.db import trade_repository
from src.core.bot_diagnostics import run_diagnostics_loop

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Criar diretórios necessários
Path("src/state").mkdir(parents=True, exist_ok=True)
Path("src/logs").mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicação (startup e shutdown)."""
    # ===== STARTUP =====
    logger.info("🚀 Iniciando Binary Options Trading Dashboard...")

    # 1. Inicializar banco de dados
    await init_db()
    logger.info("✅ Banco de dados inicializado.")

    # 2. Recuperar trades pendentes de crash anterior
    # Usa mark_trade_unknown_by_id (id interno) pois contract_id pode ser NULL
    # para trades inseridos como pending antes da Deriv confirmar.
    try:
        pending_trades = await trade_repository.get_pending_trades()
        if pending_trades:
            from datetime import datetime
            logger.warning(f"⚠️ Encontrados {len(pending_trades)} trades pendentes do crash anterior.")
            for trade in pending_trades:
                opened_at_str = trade.get("opened_at", "")
                trade_id = trade.get("id")
                try:
                    opened_at = datetime.fromisoformat(opened_at_str.replace("Z", "+00:00"))
                    duration_min = 30  # default
                    age_seconds = (datetime.utcnow() - opened_at.replace(tzinfo=None)).total_seconds()
                    if age_seconds > duration_min * 60 + 300:
                        # Usar id interno (sempre presente) em vez de contract_id (pode ser NULL)
                        if trade_id is not None:
                            await trade_repository.mark_trade_unknown_by_id(trade_id)
                            logger.warning(
                                f"Trade id={trade_id} (contract={trade.get('contract_id')}) "
                                f"marcado como 'unknown' (recovery, {age_seconds:.0f}s antigo)."
                            )
                        elif trade.get("contract_id"):
                            await trade_repository.mark_trade_unknown(trade["contract_id"])
                            logger.warning(f"Trade {trade['contract_id']} marcado como 'unknown' (recovery).")
                except Exception as recovery_err:
                    logger.error(
                        f"Erro no recovery de trade id={trade_id} "
                        f"contract={trade.get('contract_id')}: {recovery_err}"
                    )
    except Exception as e:
        logger.error(f"Erro ao verificar trades pendentes: {e}")

    # 3. Configurar função de broadcast no AgentManager
    agent_manager.set_broadcast_fn(connection_manager.broadcast)

    # 4. Carregar agentes e iniciar bots
    await agent_manager.load_from_disk()
    logger.info(f"✅ {len(agent_manager.agents)} agente(s) carregado(s).")

    # 5. Iniciar file watcher para hot-reload do browser
    static_dir = Path(__file__).parent / "static"
    watcher_task = asyncio.create_task(
        _watch_static_files(static_dir, connection_manager.broadcast)
    )
    logger.info("✅ File watcher ativo — edições em /static recarregam o browser automaticamente.")

    # 6. Iniciar loop de diagnóstico dos bots
    def _get_agents():
        state = agent_manager.get_full_state()
        return state.get("agents", [])

    diag_task = asyncio.create_task(
        run_diagnostics_loop(_get_agents, connection_manager.broadcast)
    )
    logger.info("✅ Loop de diagnóstico ativo — tarefas serão reportadas a cada 60 s.")

    logger.info("✅ Dashboard pronto! Acesse http://localhost:8000")

    yield  # Aplicação rodando

    # ===== SHUTDOWN =====
    watcher_task.cancel()
    diag_task.cancel()
    logger.info("🛑 Encerrando aplicação...")
    await agent_manager.stop_all()
    logger.info("✅ Todos os bots parados. Até logo!")


async def _watch_static_files(static_dir: Path, broadcast_fn) -> None:
    """
    Monitora alterações nos arquivos estáticos e emite evento 'reload'
    via WebSocket para todos os browsers conectados.
    """
    def _snapshot(directory: Path) -> dict:
        mtimes = {}
        for path in directory.rglob("*"):
            if path.is_file():
                try:
                    mtimes[str(path)] = path.stat().st_mtime
                except OSError:
                    pass
        return mtimes

    prev = _snapshot(static_dir)
    logger.info(f"[FileWatcher] Monitorando {len(prev)} arquivo(s) em {static_dir}")

    while True:
        await asyncio.sleep(1)
        try:
            curr = _snapshot(static_dir)
            changed = [
                Path(p).name
                for p, mtime in curr.items()
                if prev.get(p) != mtime
            ]
            if changed:
                logger.info(f"[FileWatcher] Mudança detectada: {changed} → recarregando browsers...")
                await broadcast_fn({"type": "reload", "payload": {"files": changed}})
            prev = curr
        except Exception as exc:
            logger.warning(f"[FileWatcher] Erro ao verificar arquivos: {exc}")


# Criar aplicação FastAPI
app = FastAPI(
    title="Binary Options Trading Dashboard",
    description="Dashboard multi-agente para bots de trading de opções binárias na Deriv",
    version="1.0.0",
    lifespan=lifespan,
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers da API REST
app.include_router(agents_router)
app.include_router(trades_router)
app.include_router(models_router)
app.include_router(analytics_router)
app.include_router(account_router)
app.include_router(symbols_router)
app.include_router(dev_router)


# Endpoint WebSocket
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    """Endpoint WebSocket para comunicação em tempo real com o dashboard."""
    await websocket_endpoint(websocket)


# Montar arquivos estáticos
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Servir index.html na raiz
@app.get("/")
async def serve_dashboard():
    """Serve o dashboard principal."""
    index_path = Path(__file__).parent / "static" / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Binary Options Trading Dashboard API", "docs": "/docs"}


@app.get("/benchmark")
async def serve_benchmark():
    """Serve a página de benchmark de modelos."""
    page_path = Path(__file__).parent / "static" / "benchmark.html"
    if page_path.exists():
        return FileResponse(str(page_path))
    return {"message": "Benchmark page not found"}


@app.get("/analytics")
async def serve_analytics():
    """Serve a página de analytics e previsões."""
    page_path = Path(__file__).parent / "static" / "analytics.html"
    if page_path.exists():
        return FileResponse(str(page_path))
    return {"message": "Analytics page not found"}


@app.get("/favicon.ico")
async def favicon():
    """Retorna 404 para favicon."""
    from fastapi import Response
    return Response(status_code=404)
