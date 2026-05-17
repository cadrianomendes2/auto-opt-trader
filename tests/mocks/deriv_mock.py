"""
MockDerivClient — substituto completo do DerivClient para testes.
Não faz nenhuma chamada de rede real.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


class MockDerivClient:
    """Simula o DerivClient sem conexão real à API Deriv."""

    def __init__(self):
        self._connected = True
        self._authorized = True
        self.calls: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        self.calls.append({"method": "connect"})

    async def disconnect(self) -> None:
        self.calls.append({"method": "disconnect"})
        self._connected = False

    async def reconnect(self) -> None:
        self.calls.append({"method": "reconnect"})
        self._connected = True

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    async def get_candles(
        self,
        symbol: str,
        granularity: int,
        count: int = 200,
    ) -> pd.DataFrame:
        """Retorna um DataFrame sintético com 'count' candles."""
        self.calls.append(
            {"method": "get_candles", "symbol": symbol, "granularity": granularity, "count": count}
        )
        rng = np.random.default_rng(42)
        n = count
        closes = 1000.0 + np.cumsum(rng.normal(0, 0.5, n))
        highs = closes + abs(rng.normal(0, 0.2, n))
        lows = closes - abs(rng.normal(0, 0.2, n))
        opens = np.roll(closes, 1)
        opens[0] = closes[0]
        volumes = rng.uniform(100, 1000, n)
        return pd.DataFrame(
            {
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": volumes,
            }
        )

    # ------------------------------------------------------------------
    # Trading
    # ------------------------------------------------------------------

    async def place_and_wait(
        self,
        contract_type: str,
        symbol: str,
        duration: int,
        duration_unit: str,
        stake: float,
        multiplier: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Retorna um resultado de trade simulado (won por padrão)."""
        self.calls.append(
            {
                "method": "place_and_wait",
                "contract_type": contract_type,
                "symbol": symbol,
                "duration": duration,
                "duration_unit": duration_unit,
                "stake": stake,
                "multiplier": multiplier,
            }
        )
        now = datetime.now(timezone.utc).isoformat()
        payout = round(stake * 1.85, 2)
        profit = round(payout - stake, 2)
        return {
            "contract_id": 999000001,
            "result": "won",
            "profit": profit,
            "payout": payout,
            "ask_price": stake,
            "entry_price": 1000.0,
            "exit_price": 1001.0,
            "opened_at": now,
            "closed_at": now,
        }
