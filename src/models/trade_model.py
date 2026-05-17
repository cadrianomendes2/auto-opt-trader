"""
Modelos Pydantic para Trade.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TradeRecord(BaseModel):
    """Registro de um trade individual."""
    id: Optional[int] = None
    agent_id: str
    contract_id: str
    symbol: str
    direction: str  # "CALL" | "PUT"
    stake: float
    payout: Optional[float] = None
    ask_price: float
    result: str = "pending"  # "won" | "lost" | "pending" | "unknown"
    profit: Optional[float] = None
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    strategy: str
    signal_meta: Optional[str] = None  # JSON string com metadados do sinal
    opened_at: str
    closed_at: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class TradeResult(BaseModel):
    """Resultado de um trade fechado."""
    contract_id: str
    result: str  # "won" | "lost"
    profit: float
    payout: Optional[float] = None
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    closed_at: str


class TradeStats(BaseModel):
    """Estatísticas agregadas de trades."""
    period: str
    agent_id: Optional[str] = None
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_pnl: float = 0.0
    profit_factor: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0


class PnlDataPoint(BaseModel):
    """Ponto de dados para gráfico de P&L."""
    timestamp: str
    cumulative_pnl: float


class PnlHistory(BaseModel):
    """Histórico de P&L para um agente."""
    agent_id: Optional[str] = None
    data_points: list[PnlDataPoint] = []
