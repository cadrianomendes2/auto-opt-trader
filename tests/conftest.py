"""
Fixtures partilhadas para todos os testes.
"""
import numpy as np
import pandas as pd
import pytest

from src.core.risk_manager import RiskManager


@pytest.fixture
def risk_manager_default():
    """RiskManager com configuração padrão e capital 1000.0."""
    config = {
        "daily_loss_limit_pct": 0.10,
        "daily_win_target_pct": 0.20,
        "max_consecutive_losses": 5,
        "risk_per_trade_pct": 0.02,
    }
    return RiskManager(risk_config=config, initial_capital=1000.0)


def _make_candles(n: int, start_price: float, step: float, noise: float = 0.0) -> pd.DataFrame:
    """Gera um DataFrame OHLCV sintético."""
    rng = np.random.default_rng(42)
    closes = [start_price + i * step + rng.uniform(-noise, noise) for i in range(n)]
    data = []
    for i, close in enumerate(closes):
        high = close + abs(rng.uniform(0, noise + 0.1))
        low = close - abs(rng.uniform(0, noise + 0.1))
        open_ = closes[i - 1] if i > 0 else close
        volume = rng.uniform(100, 1000)
        data.append({"open": open_, "high": high, "low": low, "close": close, "volume": volume})
    return pd.DataFrame(data)


@pytest.fixture
def sample_candles_up():
    """DataFrame de 100 candles com tendência ascendente."""
    return _make_candles(n=100, start_price=1000.0, step=1.0, noise=0.2)


@pytest.fixture
def sample_candles_down():
    """DataFrame de 100 candles com tendência descendente."""
    return _make_candles(n=100, start_price=1000.0, step=-1.0, noise=0.2)


@pytest.fixture
def sample_candles_flat():
    """DataFrame de 50 candles completamente flat."""
    return _make_candles(n=50, start_price=1000.0, step=0.0, noise=0.0)
