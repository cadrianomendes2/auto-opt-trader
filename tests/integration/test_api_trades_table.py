"""
Testes de integração para a rota /api/v1/trades — foco na tabela do dashboard.

Cobre:
- Estrutura do envelope JSON (total, trades, limit, offset)
- Campos obrigatórios em cada trade
- Valores válidos para result (won/lost/pending/unknown)
- Filtro ?result= retorna apenas registros corretos
- Ordenação: pending no topo com include_open=True
- Relação lucro × resultado (won → profit ≥ 0, lost → profit ≤ 0)
- Direção válida (CALL/PUT/MULTUP/MULTDOWN)
- Rota /trades/recent — estrutura e campos
- Rota /trades/pnl-history — retorna array diretamente
- Rota /trades/stats — campos de estatística
- Paginação com offset
"""
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Helpers — trades de exemplo com timestamps FIXOS para evitar flakiness
# ---------------------------------------------------------------------------

# Âncora temporal estática — evita datetime.now() repetido em microssegundos distintos
_BASE_TIME = datetime(2026, 5, 4, 10, 0, 0, tzinfo=timezone.utc)


def _make_trade(
    id: int,
    result: str,
    profit: float | None = None,
    direction: str = "CALL",
    stake: float = 5.0,
    agent_id: str = "agent-test",
    opened_at: str | None = None,
    closed_at: str | None = None,
):
    open_ts  = opened_at  or (_BASE_TIME - timedelta(minutes=id * 10)).isoformat()
    close_ts = closed_at  or (_BASE_TIME - timedelta(minutes=id * 10 - 5)).isoformat() if result != "pending" else None
    return {
        "id": id,
        "agent_id": agent_id,
        "contract_id": f"CONTRACT_{id}",
        "symbol": "R_75",
        "direction": direction,
        "stake": stake,
        "result": result,
        "profit": profit,
        "opened_at": open_ts,
        "closed_at": close_ts,
        "timeframe_minutes": 5,
        "strategy": "rsi_ema",
    }


SAMPLE_WON  = _make_trade(1, "won",  profit=4.50,  direction="CALL")
SAMPLE_LOST = _make_trade(2, "lost", profit=-5.00, direction="PUT")
SAMPLE_PEND = _make_trade(3, "pending", profit=None, direction="CALL", closed_at=None)
SAMPLE_TRADES = [SAMPLE_WON, SAMPLE_LOST, SAMPLE_PEND]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_trade_repo():
    """Mock do trade_repository com trades de exemplo.

    Nota: `get_all_trades` recebe (agent_id, result, limit, offset, ...).
    Para respeitar `limit` nos testes, o side_effect corta a lista.
    """
    repo = MagicMock()

    async def _get_all_trades(
        agent_id=None, result=None, limit=50, offset=0,
        from_date=None, to_date=None
    ):
        trades = SAMPLE_TRADES
        if result:
            trades = [t for t in trades if t["result"] == result]
        # respeitar offset e limit como a implementação real faria
        paginated = trades[offset: offset + limit]
        return paginated, len(trades)

    repo.get_all_trades = _get_all_trades
    repo.get_open_trades = AsyncMock(return_value=[SAMPLE_PEND])
    repo.get_pending_trades = AsyncMock(return_value=[SAMPLE_PEND])
    repo.get_agent_stats = AsyncMock(return_value={
        "total_trades": 3,
        "wins": 1,
        "losses": 1,
        "win_rate": 0.5,
        "total_pnl": -0.50,
    })
    repo.get_pnl_history = AsyncMock(return_value=[
        {"timestamp": SAMPLE_WON["opened_at"], "cumulative_pnl": 4.50},
        {"timestamp": SAMPLE_LOST["opened_at"], "cumulative_pnl": -0.50},
    ])
    repo.get_recent_trades_by_agent = AsyncMock(return_value=[SAMPLE_WON, SAMPLE_LOST])
    return repo


@pytest.fixture
def mock_agent_manager():
    manager = MagicMock()
    manager.agents = {}
    manager.bot_instances = {}
    manager.set_broadcast_fn = MagicMock()
    manager.load_from_disk = AsyncMock()
    manager.stop_all = AsyncMock()
    return manager


@pytest.fixture
def app_with_mocks(mock_trade_repo, mock_agent_manager):
    with patch("src.core.agent_manager.agent_manager", mock_agent_manager), \
         patch("src.api.routes_agents.agent_manager", mock_agent_manager), \
         patch("src.db.trade_repository.get_all_trades",               mock_trade_repo.get_all_trades), \
         patch("src.db.trade_repository.get_open_trades",              mock_trade_repo.get_open_trades), \
         patch("src.db.trade_repository.get_pending_trades",           mock_trade_repo.get_pending_trades), \
         patch("src.db.trade_repository.get_agent_stats",              mock_trade_repo.get_agent_stats), \
         patch("src.db.trade_repository.get_pnl_history",              mock_trade_repo.get_pnl_history), \
         patch("src.db.trade_repository.get_recent_trades_by_agent",   mock_trade_repo.get_recent_trades_by_agent), \
         patch("src.db.database.init_db", AsyncMock()):
        from src.main import app
        yield app


# ---------------------------------------------------------------------------
# GET /api/v1/trades — Envelope JSON
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trades_envelope_fields(app_with_mocks):
    """Deve retornar envelope com total (int), trades (list), limit (int), offset (int)."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades?limit=10&include_open=true")
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    data = resp.json()

    assert isinstance(data.get("total"),  int),  f"total deve ser int, obteve: {type(data.get('total'))}"
    assert isinstance(data.get("trades"), list), f"trades deve ser lista, obteve: {type(data.get('trades'))}"
    assert isinstance(data.get("limit"),  int),  f"limit deve ser int, obteve: {type(data.get('limit'))}"
    assert isinstance(data.get("offset"), int),  f"offset deve ser int, obteve: {type(data.get('offset'))}"
    assert data["limit"] == 10


@pytest.mark.asyncio
async def test_trades_total_consistent(app_with_mocks):
    """total deve ser >= len(trades) retornados."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= len(data["trades"]), (
        f"total={data['total']} mas len(trades)={len(data['trades'])}"
    )


# ---------------------------------------------------------------------------
# Campos obrigatórios em cada trade
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = ["result", "stake", "opened_at", "agent_id"]

@pytest.mark.asyncio
async def test_trade_required_fields(app_with_mocks):
    """Cada trade deve ter: result, stake, opened_at, agent_id — nunca null."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades?limit=50")
    assert resp.status_code == 200
    trades = resp.json()["trades"]

    for t in trades:
        for field in REQUIRED_FIELDS:
            assert field in t, f"Trade id={t.get('id')} sem campo '{field}'"
            assert t[field] is not None, f"Trade id={t.get('id')} campo '{field}' é null"


# ---------------------------------------------------------------------------
# Valores de result
# ---------------------------------------------------------------------------

VALID_RESULTS = {"won", "lost", "pending", "unknown"}

@pytest.mark.asyncio
async def test_trade_result_values(app_with_mocks):
    """result deve ser won | lost | pending | unknown."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades?limit=100")
    assert resp.status_code == 200
    trades = resp.json()["trades"]

    bad = [t for t in trades if t.get("result") not in VALID_RESULTS]
    assert not bad, (
        f"{len(bad)} trade(s) com result inválido: "
        + ", ".join(f"id={t.get('id')} result={t.get('result')!r}" for t in bad[:5])
    )


# ---------------------------------------------------------------------------
# Filtro ?result=
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trades_filter_result_invalid_value(app_with_mocks):
    """?result=invalido deve retornar HTTP 422."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades?result=invalido")
    assert resp.status_code == 422, f"Esperado 422, obteve {resp.status_code}"


@pytest.mark.asyncio
async def test_trades_filter_won_only(app_with_mocks):
    """?result=won deve retornar apenas trades won (filtrado pelo side_effect do mock)."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades?result=won&limit=20")
    assert resp.status_code == 200
    trades = resp.json()["trades"]
    bad = [t for t in trades if t["result"] != "won"]
    assert not bad, f"{len(bad)} trades não-won no filtro ?result=won: {[t['result'] for t in bad]}"


@pytest.mark.asyncio
async def test_trades_filter_lost_only(app_with_mocks):
    """?result=lost deve retornar apenas trades lost."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades?result=lost&limit=20")
    assert resp.status_code == 200
    trades = resp.json()["trades"]
    bad = [t for t in trades if t["result"] != "lost"]
    assert not bad, f"{len(bad)} trades não-lost no filtro ?result=lost"


@pytest.mark.asyncio
async def test_trades_filter_pending_only(app_with_mocks):
    """?result=pending deve retornar apenas trades pending."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades?result=pending&limit=20")
    assert resp.status_code == 200
    trades = resp.json()["trades"]
    bad = [t for t in trades if t["result"] != "pending"]
    assert not bad, f"{len(bad)} trades não-pending no filtro ?result=pending"


# ---------------------------------------------------------------------------
# Ordenação com include_open
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pending_on_top_with_include_open(mock_agent_manager):
    """include_open=true deve inserir pending no topo quando get_open_trades tem
    um trade com id diferente dos retornados por get_all_trades.

    Cria um fixture local para garantir que o patch correto é aplicado.
    """
    # Trade pending com id único (não está em SAMPLE_TRADES)
    extra_pending = _make_trade(99, "pending", profit=None, direction="CALL", closed_at=None)

    async def _only_finished(agent_id=None, result=None, limit=50, offset=0, **kw):
        return [SAMPLE_WON, SAMPLE_LOST], 2

    mock_repo = MagicMock()
    mock_repo.get_all_trades     = _only_finished
    mock_repo.get_open_trades    = AsyncMock(return_value=[extra_pending])
    mock_repo.get_pending_trades = AsyncMock(return_value=[extra_pending])
    mock_repo.get_agent_stats    = AsyncMock(return_value={"total_trades": 2, "wins": 1, "losses": 1, "win_rate": 0.5, "total_pnl": -0.5})
    mock_repo.get_pnl_history    = AsyncMock(return_value=[])
    mock_repo.get_recent_trades_by_agent = AsyncMock(return_value=[])

    with patch("src.core.agent_manager.agent_manager",   mock_agent_manager), \
         patch("src.api.routes_agents.agent_manager",    mock_agent_manager), \
         patch("src.db.trade_repository.get_all_trades",              mock_repo.get_all_trades), \
         patch("src.db.trade_repository.get_open_trades",             mock_repo.get_open_trades), \
         patch("src.db.trade_repository.get_pending_trades",          mock_repo.get_pending_trades), \
         patch("src.db.trade_repository.get_agent_stats",             mock_repo.get_agent_stats), \
         patch("src.db.trade_repository.get_pnl_history",             mock_repo.get_pnl_history), \
         patch("src.db.trade_repository.get_recent_trades_by_agent",  mock_repo.get_recent_trades_by_agent), \
         patch("src.db.database.init_db", AsyncMock()):
        from src.main import app
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            resp = await client.get("/api/v1/trades?limit=50&include_open=true")

    assert resp.status_code == 200
    trades = resp.json()["trades"]
    assert len(trades) >= 1, "Deve ter pelo menos o trade pending"
    assert trades[0]["result"] == "pending", (
        f"Primeiro trade deve ser pending (id=99 não estava em get_all_trades), obteve: {trades[0]['result']}"
    )


@pytest.mark.asyncio
async def test_no_pending_duplication(app_with_mocks, mock_trade_repo):
    """Pending já incluído na listagem principal não deve ser duplicado."""
    # get_all_trades já inclui o pending E get_open_trades também retorna o mesmo
    async def _with_pending(agent_id=None, result=None, limit=50, offset=0, **kw):
        return [SAMPLE_PEND, SAMPLE_WON], 2

    mock_trade_repo.get_all_trades = _with_pending
    mock_trade_repo.get_open_trades = AsyncMock(return_value=[SAMPLE_PEND])

    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades?limit=50&include_open=true")
    assert resp.status_code == 200
    trades = resp.json()["trades"]

    pending_count = sum(1 for t in trades if t["result"] == "pending" and t["id"] == SAMPLE_PEND["id"])
    assert pending_count == 1, f"Trade pending duplicado! Aparece {pending_count} vez(es)"


# ---------------------------------------------------------------------------
# Lucro × Resultado
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_won_trade_has_positive_profit(app_with_mocks, mock_trade_repo):
    """Trade won deve ter profit ≥ 0."""
    mock_trade_repo.get_all_trades = AsyncMock(return_value=([SAMPLE_WON], 1))
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades")
    trades = resp.json()["trades"]
    won = [t for t in trades if t["result"] == "won"]
    for t in won:
        if t.get("profit") is not None:
            assert t["profit"] >= 0, f"Trade won id={t['id']} tem profit={t['profit']} (negativo)"


@pytest.mark.asyncio
async def test_lost_trade_has_negative_profit(app_with_mocks, mock_trade_repo):
    """Trade lost deve ter profit ≤ 0."""
    mock_trade_repo.get_all_trades = AsyncMock(return_value=([SAMPLE_LOST], 1))
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades")
    trades = resp.json()["trades"]
    lost = [t for t in trades if t["result"] == "lost"]
    for t in lost:
        if t.get("profit") is not None:
            assert t["profit"] <= 0, f"Trade lost id={t['id']} tem profit={t['profit']} (positivo)"


@pytest.mark.asyncio
async def test_pending_trade_has_null_profit(app_with_mocks, mock_trade_repo):
    """Trade pending deve ter profit=null (não foi encerrado ainda)."""
    mock_trade_repo.get_all_trades = AsyncMock(return_value=([SAMPLE_PEND], 1))
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades")
    trades = resp.json()["trades"]
    pending = [t for t in trades if t["result"] == "pending"]
    for t in pending:
        assert t.get("profit") is None, (
            f"Trade pending id={t['id']} tem profit={t['profit']} (deveria ser null)"
        )


@pytest.mark.asyncio
async def test_finished_trades_have_profit(app_with_mocks, mock_trade_repo):
    """Trades finalizados (won/lost) devem ter profit definido."""
    mock_trade_repo.get_all_trades = AsyncMock(return_value=([SAMPLE_WON, SAMPLE_LOST], 2))
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades")
    trades = resp.json()["trades"]
    finished_null = [
        t for t in trades
        if t["result"] in ("won", "lost") and t.get("profit") is None
    ]
    assert not finished_null, (
        f"{len(finished_null)} trade(s) finalizado(s) com profit=null: "
        + str([t.get("id") for t in finished_null])
    )


# ---------------------------------------------------------------------------
# Direção
# ---------------------------------------------------------------------------

VALID_DIRECTIONS = {"CALL", "PUT", "MULTUP", "MULTDOWN"}

@pytest.mark.asyncio
async def test_trade_direction_values(app_with_mocks):
    """direction deve ser CALL, PUT, MULTUP ou MULTDOWN quando definido."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades?limit=100")
    assert resp.status_code == 200
    trades = resp.json()["trades"]

    bad = [t for t in trades if t.get("direction") and t["direction"] not in VALID_DIRECTIONS]
    assert not bad, (
        f"{len(bad)} trade(s) com direction inválida: "
        + str({t["direction"] for t in bad})
    )


@pytest.mark.asyncio
async def test_finished_trades_have_direction(app_with_mocks, mock_trade_repo):
    """Trades finalizados (won/lost) não devem ter direction=null."""
    mock_trade_repo.get_all_trades = AsyncMock(return_value=([SAMPLE_WON, SAMPLE_LOST], 2))
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades")
    trades = resp.json()["trades"]
    no_dir = [t for t in trades if t["result"] in ("won", "lost") and not t.get("direction")]
    assert not no_dir, (
        f"{len(no_dir)} trade(s) finalizado(s) sem direction: {[t.get('id') for t in no_dir]}"
    )


# ---------------------------------------------------------------------------
# GET /api/v1/trades/recent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recent_trades_structure(app_with_mocks):
    """GET /api/v1/trades/recent deve retornar envelope com 'trades' lista."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades/recent?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "trades" in data, f"Campo 'trades' ausente: {list(data.keys())}"
    assert isinstance(data["trades"], list)


@pytest.mark.asyncio
async def test_recent_trades_required_fields(app_with_mocks):
    """Trades em /recent devem ter campos obrigatórios."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades/recent?limit=10")
    assert resp.status_code == 200
    trades = resp.json()["trades"]
    for t in trades:
        for field in REQUIRED_FIELDS:
            assert field in t, f"Trade em /recent sem campo '{field}': {t}"


@pytest.mark.asyncio
async def test_recent_trades_asc_order(app_with_mocks, mock_trade_repo):
    """GET /api/v1/trades/recent deve retornar em ordem ASC (mais antigo → mais recente).

    A rota recebe os trades DESC de get_recent_trades_by_agent e inverte para ASC.
    Usamos timestamps completamente distintos (horas diferentes) para evitar
    flakiness por microssegundos idênticos.
    """
    # Timestamps estáticos e claramente ordenados
    ts_oldest  = "2026-05-04T08:00:00+00:00"
    ts_middle  = "2026-05-04T09:00:00+00:00"
    ts_newest  = "2026-05-04T10:00:00+00:00"

    t1 = _make_trade(10, "won",  profit=4.50,  opened_at=ts_oldest)
    t2 = _make_trade(11, "lost", profit=-5.0,  opened_at=ts_middle)
    t3 = _make_trade(12, "won",  profit=4.50,  opened_at=ts_newest)

    # get_recent_trades_by_agent retorna DESC (mais recente primeiro)
    mock_trade_repo.get_recent_trades_by_agent = AsyncMock(return_value=[t3, t2, t1])

    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades/recent?agent_id=agent-test&limit=10")
    assert resp.status_code == 200
    trades = resp.json()["trades"]

    if len(trades) < 2:
        pytest.skip("Insuficiente trades para verificar ordenação")

    timestamps = [t.get("opened_at") or t.get("closed_at") for t in trades]
    timestamps = [ts for ts in timestamps if ts]
    for i in range(len(timestamps) - 1):
        assert timestamps[i] <= timestamps[i + 1], (
            f"Ordem ASC violada na posição {i}: {timestamps[i]} > {timestamps[i+1]}"
        )


# ---------------------------------------------------------------------------
# GET /api/v1/trades/pnl-history
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pnl_history_returns_array(app_with_mocks):
    """GET /api/v1/trades/pnl-history deve retornar um array diretamente (não envelopado)."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades/pnl-history?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list), (
        f"pnl-history deve retornar array, obteve {type(data).__name__}: {str(data)[:200]}"
    )


@pytest.mark.asyncio
async def test_pnl_history_data_points_fields(app_with_mocks):
    """Cada data point deve ter timestamp e cumulative_pnl."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades/pnl-history?limit=50")
    assert resp.status_code == 200
    points = resp.json()
    for p in points:
        assert "timestamp" in p, f"data point sem 'timestamp': {p}"
        assert "cumulative_pnl" in p, f"data point sem 'cumulative_pnl': {p}"
        assert isinstance(p["cumulative_pnl"], (int, float)), (
            f"cumulative_pnl não é número: {p['cumulative_pnl']!r}"
        )


# ---------------------------------------------------------------------------
# GET /api/v1/trades/stats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trades_stats_structure(app_with_mocks):
    """GET /api/v1/trades/stats deve retornar campos de estatística."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades/stats")
    assert resp.status_code == 200
    data = resp.json()
    expected = ["total_trades", "wins", "losses", "win_rate", "total_pnl"]
    for field in expected:
        assert field in data, f"Campo '{field}' ausente em /trades/stats: {list(data.keys())}"


@pytest.mark.asyncio
async def test_trades_stats_win_rate_range(app_with_mocks):
    """win_rate deve estar entre 0.0 e 1.0."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades/stats")
    assert resp.status_code == 200
    wr = resp.json().get("win_rate", 0)
    assert 0.0 <= wr <= 1.0, f"win_rate fora do intervalo [0,1]: {wr}"


@pytest.mark.asyncio
async def test_trades_stats_wins_losses_sum(app_with_mocks):
    """wins + losses deve ser ≤ total_trades."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades/stats")
    assert resp.status_code == 200
    data = resp.json()
    wins   = data.get("wins", 0)
    losses = data.get("losses", 0)
    total  = data.get("total_trades", 0)
    assert wins + losses <= total, (
        f"wins({wins}) + losses({losses}) > total_trades({total})"
    )


# ---------------------------------------------------------------------------
# Paginação
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trades_pagination_limit(app_with_mocks):
    """Parâmetro limit deve ser respeitado com include_open=false.

    Com include_open=true (default), a rota pode acrescentar pending além do limit —
    comportamento intencional para garantir visibilidade de trades em curso.
    Por isso testamos com include_open=false para isolar o comportamento de paginação.
    """
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades?limit=1&include_open=false")
    assert resp.status_code == 200
    data = resp.json()
    assert data["limit"] == 1
    # Com include_open=false, apenas os trades do get_all_trades paginados são retornados
    assert len(data["trades"]) <= 1, (
        f"Retornou {len(data['trades'])} trades para limit=1&include_open=false"
    )


@pytest.mark.asyncio
async def test_trades_pagination_offset_field(app_with_mocks):
    """Parâmetro offset deve ser ecoado na resposta."""
    async with httpx.AsyncClient(app=app_with_mocks, base_url="http://test") as client:
        resp = await client.get("/api/v1/trades?limit=5&offset=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["offset"] == 10, f"offset={data['offset']} mas esperado 10"
