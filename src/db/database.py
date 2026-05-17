"""
Módulo de banco de dados - Conexão e schema SQLite via aiosqlite.
"""
import aiosqlite
import logging
from pathlib import Path
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "state" / "trades.db"

# Schema atual — contract_id e ask_price são NULLABLE para suportar
# trades inseridos como 'pending' antes da confirmação da Deriv.
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agents (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    symbol      TEXT NOT NULL DEFAULT 'R_75',
    timeframe   INTEGER NOT NULL,
    stake       REAL NOT NULL,
    strategy    TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL REFERENCES agents(id),
    contract_id     TEXT UNIQUE,
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL,
    stake           REAL NOT NULL,
    payout          REAL,
    ask_price       REAL,
    result          TEXT DEFAULT 'pending',
    profit          REAL,
    entry_price     REAL,
    exit_price      REAL,
    strategy        TEXT NOT NULL,
    signal_meta     TEXT,
    opened_at       TEXT NOT NULL,
    closed_at       TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_trades_agent_id ON trades(agent_id);
CREATE INDEX IF NOT EXISTS idx_trades_opened_at ON trades(opened_at);
CREATE INDEX IF NOT EXISTS idx_trades_result ON trades(result);

CREATE TABLE IF NOT EXISTS daily_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL REFERENCES agents(id),
    date            TEXT NOT NULL,
    total_trades    INTEGER DEFAULT 0,
    wins            INTEGER DEFAULT 0,
    losses          INTEGER DEFAULT 0,
    gross_profit    REAL DEFAULT 0.0,
    gross_loss      REAL DEFAULT 0.0,
    net_pnl         REAL DEFAULT 0.0,
    win_rate        REAL DEFAULT 0.0,
    UNIQUE(agent_id, date)
);
"""

# Schema novo (para migração quando a tabela já existe com colunas NOT NULL)
_TRADES_NEW_SCHEMA = """
CREATE TABLE trades_new (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL REFERENCES agents(id),
    contract_id     TEXT UNIQUE,
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL,
    stake           REAL NOT NULL,
    payout          REAL,
    ask_price       REAL,
    result          TEXT DEFAULT 'pending',
    profit          REAL,
    entry_price     REAL,
    exit_price      REAL,
    strategy        TEXT NOT NULL,
    signal_meta     TEXT,
    opened_at       TEXT NOT NULL,
    closed_at       TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


async def _migrate_trades_schema(db) -> None:
    """Migra a tabela trades para o novo schema (contract_id e ask_price nullable).
    Só executa se a versão antiga ainda tiver as colunas com NOT NULL.
    """
    # Verificar se a migração já foi feita consultando table_info
    cursor = await db.execute("PRAGMA table_info(trades)")
    cols = {row[1]: row for row in await cursor.fetchall()}

    # row layout: (cid, name, type, notnull, dflt_value, pk)
    contract_notnull = cols.get("contract_id", (None, None, None, 0))[3]
    askprice_notnull = cols.get("ask_price", (None, None, None, 0))[3]

    if not contract_notnull and not askprice_notnull:
        # Já no schema novo — nada a fazer
        return

    logger.info("Migrando schema da tabela trades: removendo NOT NULL de contract_id e ask_price...")

    await db.execute(_TRADES_NEW_SCHEMA)
    await db.execute("""
        INSERT INTO trades_new
            (id, agent_id, contract_id, symbol, direction, stake, payout,
             ask_price, result, profit, entry_price, exit_price, strategy,
             signal_meta, opened_at, closed_at, created_at)
        SELECT
            id, agent_id, contract_id, symbol, direction, stake, payout,
            ask_price, result, profit, entry_price, exit_price, strategy,
            signal_meta, opened_at, closed_at, created_at
        FROM trades
    """)
    await db.execute("DROP TABLE trades")
    await db.execute("ALTER TABLE trades_new RENAME TO trades")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_trades_agent_id ON trades(agent_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_trades_opened_at ON trades(opened_at)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_trades_result ON trades(result)")
    await db.commit()
    logger.info("Migração da tabela trades concluída.")


async def init_db():
    """Inicializa o banco de dados criando as tabelas se necessário.
    Também executa migrações de schema quando necessário.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.executescript(SCHEMA_SQL)
        await db.commit()
        # Migrar schema antigo se necessário
        await _migrate_trades_schema(db)
    logger.info(f"Banco de dados inicializado em: {DB_PATH}")


@asynccontextmanager
async def get_db():
    """Context manager para conexão com o banco de dados."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def get_db_connection():
    """Retorna uma conexão com o banco de dados."""
    conn = await aiosqlite.connect(str(DB_PATH))
    conn.row_factory = aiosqlite.Row
    return conn
