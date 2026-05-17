"""
SymbolScorer — Engine de seleção automática de símbolo por Expected Value.

Avalia e ranqueia símbolos disponíveis pelo Expected Value esperado:
    Score = win_rate_estimado × payout_líquido - (1 - win_rate_estimado)

Win rate técnico baseado nos últimos N candles:
    - Frequência de RSI oversold → subida no próximo período
    - Frequência de RSI overbought → queda no próximo período
    - Volatilidade relativa
    - Força da tendência EMA
"""
import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

import pandas as pd
import websockets

logger = logging.getLogger(__name__)

DERIV_WS_URL = os.getenv("DERIV_WS_URL", "wss://ws.binaryws.com/websockets/v3")
DERIV_APP_ID = os.getenv("DERIV_APP_ID", "1")
DERIV_API_TOKEN = os.getenv("DERIV_API_TOKEN", "eYf2ydKTUpN2cgz")

# Símbolos Synthetic Indices disponíveis para scoring
DEFAULT_SYMBOLS = [
    {"symbol": "R_75",    "display_name": "Volatility 75 Index"},
    {"symbol": "R_50",    "display_name": "Volatility 50 Index"},
    {"symbol": "R_100",   "display_name": "Volatility 100 Index"},
    {"symbol": "R_25",    "display_name": "Volatility 25 Index"},
    {"symbol": "R_10",    "display_name": "Volatility 10 Index"},
    {"symbol": "1HZ75V",  "display_name": "Volatility 75 (1s) Index"},
    {"symbol": "1HZ100V", "display_name": "Volatility 100 (1s) Index"},
    {"symbol": "1HZ50V",  "display_name": "Volatility 50 (1s) Index"},
    {"symbol": "1HZ25V",  "display_name": "Volatility 25 (1s) Index"},
    {"symbol": "1HZ10V",  "display_name": "Volatility 10 (1s) Index"},
]

# Payout efetivo por multiplicador para contratos Multiplier
MULTIPLIER_PAYOUTS = {
    1: 0.50,
    2: 0.80,
    3: 0.90,
    5: 0.95,
}


def _calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, float("inf"))
    return 100 - (100 / (1 + rs))


def _calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _calc_volatility_score(df: pd.DataFrame) -> float:
    """
    Normaliza a volatilidade do símbolo num score 0-1.
    Usa o desvio padrão relativo (coef. de variação) dos retornos.
    Mais volátil = mais oportunidades de sinal.
    """
    if len(df) < 20:
        return 0.5
    returns = df["close"].pct_change().dropna()
    cv = returns.std() / (abs(returns.mean()) + 1e-10)
    # Normalizar: cv > 1.5 → score 1.0
    score = min(float(cv) / 1.5, 1.0)
    return round(score, 4)


def _calc_trend_strength(df: pd.DataFrame) -> float:
    """
    Calcula a força da tendência atual (0-1) baseada em EMA9 vs EMA21.
    Tendência clara = maior probabilidade de sinal fiável.
    """
    if len(df) < 25:
        return 0.5
    close = df["close"]
    ema9 = _calc_ema(close, 9)
    ema21 = _calc_ema(close, 21)
    diff_pct = abs(ema9.iloc[-1] - ema21.iloc[-1]) / ema21.iloc[-1] * 100
    # Normalizar: diferença > 0.5% = score 1.0
    score = min(float(diff_pct) / 0.5, 1.0)
    return round(score, 4)


def _calc_technical_win_rate(df: pd.DataFrame, candles_to_check: int = 50) -> float:
    """
    Estima o win rate técnico analisando os últimos N candles:
    - % de vezes que RSI < 35 → próximo candle fechou acima (CALL correto)
    - % de vezes que RSI > 65 → próximo candle fechou abaixo (PUT correto)

    Retorna a média das acurácias observadas.
    """
    if len(df) < candles_to_check + 15:
        return 0.50

    recent = df.tail(candles_to_check + 15).reset_index(drop=True)
    close = recent["close"]
    rsi = _calc_rsi(close, 14)

    call_correct = 0
    call_total = 0
    put_correct = 0
    put_total = 0

    for i in range(14, len(recent) - 1):
        rsi_val = rsi.iloc[i]
        if pd.isna(rsi_val):
            continue
        next_close = close.iloc[i + 1]
        curr_close = close.iloc[i]

        if rsi_val < 35:
            call_total += 1
            if next_close > curr_close:
                call_correct += 1
        elif rsi_val > 65:
            put_total += 1
            if next_close < curr_close:
                put_correct += 1

    call_rate = call_correct / call_total if call_total > 0 else 0.50
    put_rate = put_correct / put_total if put_total > 0 else 0.50

    if call_total == 0 and put_total == 0:
        return 0.50

    weights = []
    rates = []
    if call_total > 0:
        weights.append(call_total)
        rates.append(call_rate)
    if put_total > 0:
        weights.append(put_total)
        rates.append(put_rate)

    total_w = sum(weights)
    win_rate = sum(r * w / total_w for r, w in zip(rates, weights))
    return round(float(win_rate), 4)


def _calc_signal_frequency(df: pd.DataFrame) -> float:
    """
    Calcula a % de candles que gerariam um sinal (RSI extremo ou BB breakout).
    Frequência mais alta = mais oportunidades de trade.
    """
    if len(df) < 30:
        return 0.2

    close = df["close"]
    rsi = _calc_rsi(close, 14)

    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std

    valid = rsi.dropna()
    if len(valid) == 0:
        return 0.2

    rsi_signals = ((valid < 40) | (valid > 60)).sum()

    bb_valid_idx = bb_upper.dropna().index
    bb_signals = ((close.loc[bb_valid_idx] > bb_upper.loc[bb_valid_idx]) |
                  (close.loc[bb_valid_idx] < bb_lower.loc[bb_valid_idx])).sum()

    total = len(valid)
    freq = max(int(rsi_signals), int(bb_signals)) / total
    return round(float(min(freq, 1.0)), 4)


def _calc_ev_score(
    win_rate: float,
    payout: float,
    historical_win_rate: float = 0.50,
    hist_weight: float = 0.4,
) -> float:
    """
    Calcula o Expected Value combinando win rate histórico e técnico.
        combined_wr = hist_wr × 0.4 + tech_wr × 0.6
        EV = combined_wr × payout - (1 - combined_wr)
    """
    combined_wr = historical_win_rate * hist_weight + win_rate * (1 - hist_weight)
    ev = combined_wr * payout - (1 - combined_wr)
    return round(float(ev), 4)


class SymbolScorer:
    """
    Avalia e ranqueia símbolos disponíveis pelo Expected Value esperado.
    Conecta à Deriv API para obter candles e calcular indicadores técnicos.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        app_id: Optional[str] = None,
        multiplier: int = 2,
    ):
        self.token = token or DERIV_API_TOKEN
        self.app_id = app_id or DERIV_APP_ID
        self.ws_url = f"{DERIV_WS_URL}?app_id={self.app_id}"
        self.multiplier = multiplier
        self.payout_estimate = MULTIPLIER_PAYOUTS.get(multiplier, 0.80)

    async def _fetch_candles(
        self,
        ws: Any,
        symbol: str,
        granularity: int,
        count: int = 200,
    ) -> pd.DataFrame:
        """Busca candles de um símbolo via WebSocket já autenticado."""
        await ws.send(json.dumps({
            "ticks_history": symbol,
            "adjust_start_time": 1,
            "count": count,
            "end": "latest",
            "granularity": granularity,
            "style": "candles",
        }))
        resp = json.loads(await ws.recv())

        if "error" in resp:
            raise ValueError(f"Deriv error for {symbol}: {resp['error'].get('message')}")

        candles = resp.get("candles", [])
        if not candles:
            return pd.DataFrame()

        df = pd.DataFrame(candles)
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    async def score_symbol(
        self,
        symbol: str,
        display_name: str,
        duration_minutes: int,
        ws: Any = None,
        historical_win_rate: float = 0.50,
    ) -> Dict[str, Any]:
        """
        Calcula score de EV para um símbolo.

        Retorna:
        {
            "symbol": "R_75",
            "display_name": "Volatility 75 Index",
            "score": 0.087,
            "win_rate_estimate": 0.62,
            "payout_estimate": 0.82,
            "volatility_score": 0.75,
            "trend_strength": 0.65,
            "signal_frequency": 0.45,
            "recommended": True,
            "rank": 1
        }
        """
        granularity = duration_minutes * 60
        if granularity < 60:
            granularity = 60

        try:
            if ws is None:
                async with websockets.connect(self.ws_url, close_timeout=10) as _ws:
                    await _ws.send(json.dumps({"authorize": self.token}))
                    await _ws.recv()
                    df = await self._fetch_candles(_ws, symbol, granularity)
            else:
                df = await self._fetch_candles(ws, symbol, granularity)

            if df.empty or len(df) < 30:
                return self._default_score(symbol, display_name)

            volatility_score = _calc_volatility_score(df)
            trend_strength = _calc_trend_strength(df)
            tech_win_rate = _calc_technical_win_rate(df)
            signal_frequency = _calc_signal_frequency(df)

            # Win rate estimado combinando histórico e técnico
            win_rate_estimate = historical_win_rate * 0.4 + tech_win_rate * 0.6
            win_rate_estimate = round(float(win_rate_estimate), 4)

            # Payout efetivo estimado para Multiplier
            # Ajustar baseado na volatilidade: mais volátil = TP dispara mais rápido
            adjusted_payout = self.payout_estimate * (0.8 + 0.2 * volatility_score)
            adjusted_payout = round(float(min(adjusted_payout, 0.95)), 4)

            score = _calc_ev_score(tech_win_rate, adjusted_payout, historical_win_rate)

            logger.debug(
                f"Score {symbol}: EV={score:.4f} | WR={win_rate_estimate:.3f} | "
                f"Vol={volatility_score:.3f} | Trend={trend_strength:.3f} | "
                f"Freq={signal_frequency:.3f}"
            )

            return {
                "symbol": symbol,
                "display_name": display_name,
                "score": score,
                "win_rate_estimate": win_rate_estimate,
                "payout_estimate": adjusted_payout,
                "volatility_score": volatility_score,
                "trend_strength": trend_strength,
                "signal_frequency": signal_frequency,
                "recommended": score > 0.05,
                "rank": 0,  # será preenchido após ordenação
            }

        except Exception as e:
            logger.warning(f"Erro ao calcular score de {symbol}: {e}")
            return self._default_score(symbol, display_name)

    def _default_score(self, symbol: str, display_name: str) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "display_name": display_name,
            "score": 0.0,
            "win_rate_estimate": 0.50,
            "payout_estimate": self.payout_estimate,
            "volatility_score": 0.5,
            "trend_strength": 0.5,
            "signal_frequency": 0.2,
            "recommended": False,
            "rank": 0,
        }

    async def rank_all_symbols(
        self,
        symbols: Optional[List[Dict[str, str]]] = None,
        duration_minutes: int = 5,
        historical_win_rates: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Ranqueia todos os símbolos por score de EV para o timeframe dado.
        Usa uma única conexão WebSocket para todos os símbolos.
        """
        if symbols is None:
            symbols = DEFAULT_SYMBOLS

        if historical_win_rates is None:
            historical_win_rates = {}

        results: List[Dict[str, Any]] = []

        try:
            async with websockets.connect(self.ws_url, close_timeout=15) as ws:
                await ws.send(json.dumps({"authorize": self.token}))
                auth_resp = json.loads(await ws.recv())
                if "error" in auth_resp:
                    logger.error(f"Erro de autenticação: {auth_resp['error']}")
                    return [self._default_score(s["symbol"], s.get("display_name", s["symbol"])) for s in symbols]

                for sym_info in symbols:
                    sym = sym_info["symbol"]
                    name = sym_info.get("display_name", sym)
                    hist_wr = historical_win_rates.get(sym, 0.50)

                    try:
                        result = await asyncio.wait_for(
                            self.score_symbol(sym, name, duration_minutes, ws, hist_wr),
                            timeout=15.0,
                        )
                        results.append(result)
                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout ao calcular score de {sym}")
                        results.append(self._default_score(sym, name))
                    except Exception as e:
                        logger.warning(f"Erro ao calcular score de {sym}: {e}")
                        results.append(self._default_score(sym, name))

                    # Pequena pausa para não sobrecarregar a API
                    await asyncio.sleep(0.3)

        except Exception as e:
            logger.error(f"Erro na conexão WebSocket para ranking: {e}")
            return [self._default_score(s["symbol"], s.get("display_name", s["symbol"])) for s in symbols]

        # Ordenar por score (maior primeiro)
        results.sort(key=lambda x: x["score"], reverse=True)

        # Atribuir ranks
        for i, r in enumerate(results):
            r["rank"] = i + 1

        return results

    async def get_best_symbol(
        self,
        available_symbols: Optional[List[Dict[str, str]]] = None,
        duration_minutes: int = 5,
        historical_win_rates: Optional[Dict[str, float]] = None,
    ) -> str:
        """Retorna o símbolo com maior score para o timeframe dado."""
        rankings = await self.rank_all_symbols(
            available_symbols, duration_minutes, historical_win_rates
        )
        if rankings:
            return rankings[0]["symbol"]
        return "R_75"  # fallback
