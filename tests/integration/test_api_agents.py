"""
Testes de integração para src/api/routes_agents.py
Usa httpx.AsyncClient com a app FastAPI (sem conexão real à Deriv).
"""
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_agent_manager():
    """Mock do agent_manager para evitar conexões reais."""
    manager = MagicMock()
    manager.agents = {}
    manager.bot_instances = {}
    manager.get_agent_summary = MagicMock(return_value=None)
    manager.get_agent = MagicMock(return_value=None)
    manager.create_agent = AsyncMock()
    manager.pause_agent = AsyncMock()
    manager.resume_agent = AsyncMock()
    manager.delete_agent = AsyncMock()
    manager.update_agent = AsyncMock()
    manager.reset_stats = AsyncMock()
    manager.save_to_disk = AsyncMock()
    manager.set_broadcast_fn = MagicMock()
    manager.load_from_disk = AsyncMock()
    manager.stop_all = AsyncMock()
    return manager


@pytest.fixture
def app_with_mocks(mock_agent_manager):
    """App FastAPI com agent_manager e trade_repository mockados."""
    with patch("src.core.agent_manager.agent_manager", mock_agent_manager), \
         patch("src.api.routes_agents.agent_manager", mock_agent_manager), \
         patch("src.db.trade_repository.get_all_trades", AsyncMock(return_value=([], 0))), \
         patch("src.db.trade_repository.get_open_trades", AsyncMock(return_value=[])), \
         patch("src.db.trade_repository.get_pending_trades", AsyncMock(return_value=[])), \
         patch("src.db.database.init_db", AsyncMock()):
        from src.main import app
        yield app


# ---------------------------------------------------------------------------
# Testes de /api/v1/agents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_agents_returns_200(app_with_mocks):
    """GET /api/v1/agents deve retornar HTTP 200."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/agents")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_agents_returns_list_structure(app_with_mocks):
    """GET /api/v1/agents deve retornar {'agents': [...]}."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/agents")
    data = resp.json()
    assert "agents" in data
    assert isinstance(data["agents"], list)


@pytest.mark.asyncio
async def test_get_agent_by_id_returns_404_when_not_found(app_with_mocks):
    """GET /api/v1/agents/{id} deve retornar 404 para agente inexistente."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/agents/nonexistent-agent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_strategies_returns_200(app_with_mocks):
    """GET /api/v1/strategies deve retornar HTTP 200 com lista de estratégias."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/strategies")
    assert resp.status_code == 200
    data = resp.json()
    assert "strategies" in data
    assert isinstance(data["strategies"], list)
    assert len(data["strategies"]) > 0


@pytest.mark.asyncio
async def test_get_strategies_contains_coin_flip(app_with_mocks):
    """GET /api/v1/strategies deve incluir a estratégia coin_flip."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/strategies")
    data = resp.json()
    strategy_ids = [s["id"] for s in data["strategies"]]
    assert "coin_flip" in strategy_ids


@pytest.mark.asyncio
async def test_health_check_returns_200(app_with_mocks):
    """GET /api/v1/health deve retornar HTTP 200."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_delete_agent_returns_404_when_not_found(app_with_mocks):
    """DELETE /api/v1/agents/{id} deve retornar 404 para agente inexistente."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.delete("/api/v1/agents/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_pause_agent_returns_404_when_not_found(app_with_mocks):
    """POST /api/v1/agents/{id}/pause deve retornar 404 para agente inexistente."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.post("/api/v1/agents/nonexistent-id/pause")
    assert resp.status_code == 404
