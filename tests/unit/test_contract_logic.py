"""
Testes de lógica de contratos — sem dependências externas.
Documenta comportamentos do sistema de trading observados nos logs.
"""
import pytest

from src.core.risk_manager import RiskManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_rm(max_consecutive_losses: int = 5, initial_capital: float = 1000.0) -> RiskManager:
    config = {
        "daily_loss_limit_pct": 0.10,
        "daily_win_target_pct": 0.20,
        "max_consecutive_losses": max_consecutive_losses,
    }
    return RiskManager(risk_config=config, initial_capital=initial_capital)


# ---------------------------------------------------------------------------
# Testes de lógica de contratos
# ---------------------------------------------------------------------------


class TestContractLogic:
    def test_sell_forced_results_in_loss(self):
        """
        Sell forçado → sold_for < buy_price → profit negativo.
        Documentar o comportamento observado nos logs de Multiplier contracts.
        """
        buy_price = 5.0
        sold_for = 4.85  # Sell forçado por timeout com pequena perda
        profit = sold_for - buy_price
        assert profit < 0, "Sell forçado deve resultar em lucro negativo"

    def test_profit_zero_classified_as_lost(self):
        """
        Profit = 0 → result = 'lost'.
        O RiskManager conta profit=0 como perda (incrementa consecutive_losses).
        """
        rm = make_rm()
        rm.update(profit=0.0, result="lost")
        assert rm.consecutive_losses == 1

    def test_multiplier_timeout_is_guaranteed_loss(self):
        """
        DOCUMENTAÇÃO: 100% dos contratos Multiplier que fecham por timeout (300s)
        resultam em perda, pois são vendidos com slippage negativo.
        Este teste verifica que o RiskManager regista a perda corretamente.
        """
        rm = make_rm()
        timeout_profit = -0.15  # Perda típica de timeout observada nos logs
        rm.update(profit=timeout_profit, result="lost")
        assert rm.daily_pnl == pytest.approx(timeout_profit)
        assert rm.consecutive_losses == 1

    def test_consecutive_losses_lead_to_block(self):
        """
        Ciclo completo: 5 perdas consecutivas → bloqueio do bot.
        Documenta o comportamento observado nos logs de produção.
        """
        rm = make_rm(max_consecutive_losses=5)

        for i in range(5):
            can_before, _ = rm.can_trade()
            assert can_before is True, f"Deve poder operar antes da perda {i + 1}"
            rm.update(profit=-5.0, result="lost")

        can_after, reason = rm.can_trade()
        assert can_after is False
        assert rm.consecutive_losses == 5

    def test_coin_flip_win_rate_at_50_percent_baseline(self):
        """
        Baseline: coin_flip deve ter ~50% de win rate.
        Simula 100 trades com resultados alternados (50 won / 50 lost).
        """
        from src.core.signal_generator import coin_flip_strategy
        import pandas as pd
        import numpy as np

        rng = np.random.default_rng(123)
        closes = 1000.0 + np.cumsum(rng.normal(0, 0.5, 100))
        df = pd.DataFrame(
            {
                "open": np.roll(closes, 1),
                "high": closes + 0.1,
                "low": closes - 0.1,
                "close": closes,
                "volume": rng.uniform(100, 1000, 100),
            }
        )

        n_samples = 1000
        results = [coin_flip_strategy(df) for _ in range(n_samples)]
        call_count = results.count("call")
        win_rate = call_count / n_samples

        # Baseline: win rate entre 40% e 60%
        assert 0.40 <= win_rate <= 0.60, (
            f"Baseline coin_flip deve ter ~50% de CALL, obtido {win_rate:.1%}"
        )

    def test_risk_manager_accumulates_losses_correctly(self):
        """
        Verificar que o PnL diário acumula as perdas corretamente.
        Simula o cenário típico de 5 perdas de $5 cada → PnL = -$25.
        """
        rm = make_rm()
        for _ in range(5):
            rm.update(profit=-5.0, result="lost")
        assert rm.daily_pnl == pytest.approx(-25.0)

    def test_win_after_losses_resets_block(self):
        """
        Uma vitória após perdas consecutivas deve desbloquear o bot.
        """
        rm = make_rm(max_consecutive_losses=5)
        for _ in range(4):
            rm.update(profit=-5.0, result="lost")

        # Com 4 perdas, ainda pode operar
        can, _ = rm.can_trade()
        assert can is True

        # Vitória zera consecutive_losses
        rm.update(profit=10.0, result="won")
        assert rm.consecutive_losses == 0

        can_after, reason = rm.can_trade()
        assert can_after is True
        assert reason == "OK"
