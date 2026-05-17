"""
Testes unitários para src/core/risk_manager.py
"""
import pytest
from freezegun import freeze_time

from src.core.risk_manager import RiskManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_rm(
    daily_loss_limit_pct: float = 0.10,
    daily_win_target_pct: float = 0.20,
    max_consecutive_losses: int = 5,
    initial_capital: float = 1000.0,
) -> RiskManager:
    config = {
        "daily_loss_limit_pct": daily_loss_limit_pct,
        "daily_win_target_pct": daily_win_target_pct,
        "max_consecutive_losses": max_consecutive_losses,
    }
    return RiskManager(risk_config=config, initial_capital=initial_capital)


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


class TestRiskManagerCanTrade:
    def test_can_trade_initial_state(self):
        """Estado inicial deve permitir trading."""
        rm = make_rm()
        can, reason = rm.can_trade()
        assert can is True
        assert reason == "OK"

    def test_can_trade_returns_ok_reason(self):
        """Quando pode operar, o motivo deve ser exatamente 'OK'."""
        rm = make_rm()
        _, reason = rm.can_trade()
        assert reason == "OK"

    def test_blocks_after_max_consecutive_losses(self):
        """Deve bloquear após N perdas consecutivas (padrão = 5)."""
        rm = make_rm(max_consecutive_losses=5)
        for _ in range(5):
            rm.update(profit=-10.0, result="lost")
        can, reason = rm.can_trade()
        assert can is False
        assert "consecutivas" in reason.lower() or "consecutive" in reason.lower()

    def test_does_not_block_before_max_consecutive_losses(self):
        """Não deve bloquear com N-1 perdas consecutivas."""
        rm = make_rm(max_consecutive_losses=5)
        for _ in range(4):
            rm.update(profit=-10.0, result="lost")
        can, _ = rm.can_trade()
        assert can is True

    def test_blocks_on_daily_loss_limit(self):
        """Deve bloquear ao atingir o limite de perda diária (10% de 1000 = -100)."""
        rm = make_rm(daily_loss_limit_pct=0.10, initial_capital=1000.0)
        # Registrar perda exatamente no limite
        rm.update(profit=-100.0, result="lost")
        can, reason = rm.can_trade()
        assert can is False
        assert "loss" in reason.lower()

    def test_blocks_on_daily_win_target(self):
        """Deve bloquear ao atingir a meta diária de lucro (20% de 1000 = +200)."""
        rm = make_rm(daily_win_target_pct=0.20, initial_capital=1000.0)
        rm.update(profit=200.0, result="won")
        can, reason = rm.can_trade()
        assert can is False
        assert "win" in reason.lower()

    def test_resets_consecutive_losses_on_win(self):
        """Uma vitória deve zerar o contador de perdas consecutivas."""
        rm = make_rm(max_consecutive_losses=5)
        for _ in range(3):
            rm.update(profit=-10.0, result="lost")
        assert rm.consecutive_losses == 3
        rm.update(profit=15.0, result="won")
        assert rm.consecutive_losses == 0

    def test_daily_reset_via_freezegun(self):
        """Usar freezegun para simular mudança de dia e garantir reset dos contadores."""
        with freeze_time("2025-01-01"):
            rm = make_rm()
            for _ in range(5):
                rm.update(profit=-10.0, result="lost")
            can_before, _ = rm.can_trade()
            assert can_before is False

        # Avançar para o dia seguinte
        with freeze_time("2025-01-02"):
            can_after, reason = rm.can_trade()
            assert can_after is True
            assert reason == "OK"
            assert rm.consecutive_losses == 0
            assert rm.daily_pnl == 0.0


class TestRiskManagerUpdate:
    def test_daily_pnl_accumulates(self):
        """O PnL diário deve acumular corretamente."""
        rm = make_rm()
        rm.update(profit=10.0, result="won")
        rm.update(profit=-5.0, result="lost")
        assert rm.daily_pnl == pytest.approx(5.0)

    def test_total_trades_increments(self):
        """O total de trades do dia deve incrementar a cada update."""
        rm = make_rm()
        rm.update(profit=5.0, result="won")
        rm.update(profit=-5.0, result="lost")
        assert rm.total_trades_today == 2

    def test_get_status_returns_dict(self):
        """get_status() deve retornar um dict com chaves esperadas."""
        rm = make_rm()
        status = rm.get_status()
        assert "daily_pnl" in status
        assert "consecutive_losses" in status
        assert "can_trade" in status

    def test_get_stake_returns_base_stake(self):
        """get_stake() deve retornar o mesmo stake passado (implementação padrão)."""
        rm = make_rm()
        assert rm.get_stake(10.0) == pytest.approx(10.0)
        assert rm.get_stake(5.5) == pytest.approx(5.5)
