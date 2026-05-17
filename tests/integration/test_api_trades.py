"""
Testes de integração para src/api/routes_trades.py
Usa httpx.AsyncClient com a app FastAPI mockada.
"""
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_trade_repo():
    """Mock do trade_repository com retornos padrão."""
    repo = MagicMock()
    repo.get_all_trades = AsyncMock(return_value=([], 0))
    repo.get_open_trades = AsyncMock(return_value=[])
    repo.get_pending_trades = AsyncMock(return_value=[])
    repo.get_agent_stats = AsyncMock(return_value={
        "total": 0, "won": 0, "lost": 0,
        "win_rate": 0.0, "total_pnl": 0.0,
    })
    repo.get_pnl_history = AsyncMock(return_value=[])
    repo.get_recent_trades_by_agent = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_agent_manager():
    """Mock do agent_manager para lifespan da app."""
    manager = MagicMock()
    manager.agents = {}
    manager.bot_instances = {}
    manager.set_broadcast_fn = MagicMock()
    manager.load_from_disk = AsyncMock()
    manager.stop_all = AsyncMock()
    return manager


@pytest.fixture
def app_with_mocks(mock_trade_repo, mock_agent_manager):
    """App com trade_repository e agent_manager mockados."""
    with patch("src.core.agent_manager.agent_manager", mock_agent_manager), \
         patch("src.api.routes_agents.agent_manager", mock_agent_manager), \
         patch("src.db.trade_repository.get_all_trades", mock_trade_repo.get_all_trades), \
         patch("src.db.trade_repository.get_open_trades", mock_trade_repo.get_open_trades), \
         patch("src.db.trade_repository.get_pending_trades", mock_trade_repo.get_pending_trades), \
         patch("src.db.trade_repository.get_agent_stats", mock_trade_repo.get_agent_stats), \
         patch("src.db.trade_repository.get_pnl_history", mock_trade_repo.get_pnl_history), \
         patch("src.db.trade_repository.get_recent_trades_by_agent", mock_trade_repo.get_recent_trades_by_agent), \
         patch("src.db.database.init_db", AsyncMock()):
        from src.main import app
        yield app


# ---------------------------------------------------------------------------
# Testes GET /api/v1/trades
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_trades_returns_200(app_with_mocks):
    """GET /api/v1/trades deve retornar HTTP 200."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_trades_returns_list(app_with_mocks):
    """GET /api/v1/trades deve retornar dict com 'trades' lista."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades")
    data = resp.json()
    assert "trades" in data
    assert isinstance(data["trades"], list)
    assert "total" in data


@pytest.mark.asyncio
async def test_get_trades_respects_limit_param(app_with_mocks):
    """GET /api/v1/trades?limit=10 deve aceitar parâmetro de paginação."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["limit"] == 10


# ---------------------------------------------------------------------------
# Testes GET /api/v1/trades/recent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_recent_trades_returns_200(app_with_mocks):
    """GET /api/v1/trades/recent deve retornar HTTP 200."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades/recent")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_recent_trades_returns_list(app_with_mocks):
    """GET /api/v1/trades/recent deve retornar dict com 'trades' lista."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades/recent")
    data = resp.json()
    assert "trades" in data
    assert isinstance(data["trades"], list)


# ---------------------------------------------------------------------------
# Testes GET /api/v1/trades/pnl-history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pnl_history_returns_200(app_with_mocks):
    """GET /api/v1/trades/pnl-history deve retornar HTTP 200."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades/pnl-history")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_pnl_history_returns_data_points(app_with_mocks):
    """GET /api/v1/trades/pnl-history deve conter 'data_points'."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades/pnl-history")
    data = resp.json()
    assert "data_points" in data
    assert isinstance(data["data_points"], list)


# ---------------------------------------------------------------------------
# Testes GET /api/v1/trades/stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_trade_stats_returns_200(app_with_mocks):
    """GET /api/v1/trades/stats deve retornar HTTP 200."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades/stats")
    assert resp.status_code == 200
