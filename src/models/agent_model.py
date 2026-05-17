"""
Modelos Pydantic para Agent.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum


class AgentStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    LIMIT_HIT = "limit_hit"


class RiskConfig(BaseModel):
    """Configuração de risco do agente."""
    daily_loss_limit_pct: float = 0.10
    daily_win_target_pct: float = 0.20
    max_consecutive_losses: int = 5
    risk_per_trade_pct: float = 0.02


class RuntimeStats(BaseModel):
    """Estatísticas de runtime do agente."""
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    consecutive_losses: int = 0
    last_trade_at: Optional[str] = None
    started_at: Optional[str] = None
    paused_at: Optional[str] = None
    error_message: Optional[str] = None


class AgentConfig(BaseModel):
    """Configuração completa de um agente de trading."""
    id: str
    name: str
    enabled: bool = True
    symbol: str = "R_75"
    timeframe_minutes: int = 5
    stake: float = 5.0
    strategy: str = "rsi_ema"
    strategy_params: Dict[str, Any] = Field(default_factory=dict)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    status: AgentStatus = AgentStatus.STOPPED
    runtime: RuntimeStats = Field(default_factory=RuntimeStats)
    api_token: Optional[str] = None

    model_config = {"from_attributes": True}


class AgentCreateRequest(BaseModel):
    """Request para criar um novo agente."""
    id: Optional[str] = None  # auto-gerado se não fornecido
    name: Optional[str] = None  # opcional — default gerado pelo backend
    symbol: str = "R_75"
    timeframe_minutes: int = Field(default=5, ge=1, le=1440)
    stake: float = Field(default=5.0, gt=0)
    strategy: str = "rsi_ema"
    strategy_params: Dict[str, Any] = Field(default_factory=dict)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    api_token: Optional[str] = None
    initial_status: Optional[str] = None  # "paused" para criar pausado (ex: agente duplicado)


class AgentUpdateRequest(BaseModel):
    """Request para atualizar um agente (campos parciais)."""
    name: Optional[str] = None
    symbol: Optional[str] = None
    timeframe_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    stake: Optional[float] = Field(default=None, gt=0)
    strategy: Optional[str] = None
    strategy_params: Optional[Dict[str, Any]] = None
    risk: Optional[RiskConfig] = None
    api_token: Optional[str] = None


class AgentSummary(BaseModel):
    """Resumo de um agente para listagem."""
    id: str
    name: str
    symbol: str
    timeframe_minutes: int
    stake: float
    strategy: str
    status: AgentStatus
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    consecutive_losses: int = 0
    last_trade_at: Optional[str] = None
