"""
Gerenciador de risco - controla limites de capital e stops automáticos.
"""
import logging
from datetime import datetime, date
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


class RiskManager:
    """Gerencia os limites de risco de um agente de trading."""

    def __init__(self, risk_config: Dict[str, Any], initial_capital: float = 1000.0):
        self.daily_loss_limit_pct = risk_config.get("daily_loss_limit_pct", 0.10)
        self.daily_win_target_pct = risk_config.get("daily_win_target_pct", 0.20)
        self.max_consecutive_losses = risk_config.get("max_consecutive_losses", 5)
        self.risk_per_trade_pct = risk_config.get("risk_per_trade_pct", 0.02)

        self.initial_capital = initial_capital
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.total_trades_today = 0
        self.last_reset_date = date.today()

    def _check_daily_reset(self) -> None:
        """Reseta os contadores diários se for um novo dia."""
        today = date.today()
        if today != self.last_reset_date:
            logger.info("Reset diário do RiskManager executado.")
            self.daily_pnl = 0.0
            self.consecutive_losses = 0
            self.total_trades_today = 0
            self.last_reset_date = today

    def can_trade(self) -> Tuple[bool, str]:
        """
        Verifica se o agente pode operar.
        Retorna (pode_operar, motivo).
        """
        self._check_daily_reset()

        # Verificar limite de perda diária
        daily_loss_limit = self.initial_capital * self.daily_loss_limit_pct
        if self.daily_pnl <= -daily_loss_limit:
            return False, f"Daily loss limit atingido: {self.daily_loss_limit_pct * 100:.1f}%"

        # Verificar alvo diário de ganho
        daily_win_target = self.initial_capital * self.daily_win_target_pct
        if self.daily_pnl >= daily_win_target:
            return False, f"Daily win target atingido: {self.daily_win_target_pct * 100:.1f}%"

        # Verificar perdas consecutivas
        if self.consecutive_losses >= self.max_consecutive_losses:
            return False, f"Limite de perdas consecutivas atingido: {self.consecutive_losses}"

        return True, "OK"

    def get_stake(self, base_stake: float) -> float:
        """
        Calcula o stake para o próximo trade.
        Por padrão usa o stake fixo configurado.
        """
        return base_stake

    def update(self, profit: float, result: str) -> None:
        """Atualiza os contadores após um trade."""
        self._check_daily_reset()
        self.daily_pnl += profit
        self.total_trades_today += 1

        if result == "lost":
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        logger.debug(
            f"RiskManager update: profit={profit:.2f}, daily_pnl={self.daily_pnl:.2f}, "
            f"consecutive_losses={self.consecutive_losses}"
        )

    def reset_daily(self) -> None:
        """Força um reset dos contadores diários."""
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.total_trades_today = 0
        self.last_reset_date = date.today()
        logger.info("RiskManager: reset manual executado.")

    def get_status(self) -> Dict[str, Any]:
        """Retorna o status atual do gerenciador de risco."""
        self._check_daily_reset()
        daily_loss_limit = self.initial_capital * self.daily_loss_limit_pct
        daily_win_target = self.initial_capital * self.daily_win_target_pct

        return {
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_loss_limit": round(daily_loss_limit, 2),
            "daily_win_target": round(daily_win_target, 2),
            "consecutive_losses": self.consecutive_losses,
            "max_consecutive_losses": self.max_consecutive_losses,
            "total_trades_today": self.total_trades_today,
            "can_trade": self.can_trade()[0],
        }
