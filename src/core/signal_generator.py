"""
Gerador de sinais de trading - Estratégias baseadas em indicadores técnicos.
Usa a biblioteca `ta` (https://github.com/bukosabino/ta).
Todas as funções recebem um DataFrame OHLCV e retornam 'call', 'put' ou 'wait'.
"""
import logging
import pandas as pd
from typing import Dict, Any, Callable, Optional

logger = logging.getLogger(__name__)


def _calc_ema(series: pd.Series, period: int) -> pd.Series:
    """Calcula EMA manualmente."""
    return series.ewm(span=period, adjust=False).mean()


def _calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calcula RSI usando a fórmula de Wilder."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, float('inf'))
    rsi = 100 - (100 / (1 + rs))
    return rsi


def _calc_bollinger(series: pd.Series, period: int = 20,
                     std: float = 2.0) -> tuple:
    """Calcula Bollinger Bands. Retorna (upper, middle, lower)."""
    mid = series.rolling(period).mean()
    std_dev = series.rolling(period).std()
    upper = mid + std * std_dev
    lower = mid - std * std_dev
    return upper, mid, lower


def _calc_stochrsi(series: pd.Series, rsi_period: int = 14,
                   k_period: int = 3, d_period: int = 3) -> tuple:
    """Calcula StochRSI. Retorna (%K, %D)."""
    rsi = _calc_rsi(series, rsi_period)
    rsi_min = rsi.rolling(rsi_period).min()
    rsi_max = rsi.rolling(rsi_period).max()
    denom = rsi_max - rsi_min
    stoch = ((rsi - rsi_min) / denom.replace(0, float('nan'))) * 100
    k = stoch.rolling(k_period).mean()
    d = k.rolling(d_period).mean()
    return k, d


def rsi_ema_strategy(df: pd.DataFrame,
                      params: Optional[Dict[str, Any]] = None) -> str:
    """
    Estratégia RSI + EMA Confirmação.

    Lógica simplificada para Synthetic Indices (alta volatilidade):
    - RSI > rsi_buy (55) E EMA rápida > EMA lenta → CALL  (momentum + tendência alta)
    - RSI < rsi_sell (45) E EMA rápida < EMA lenta → PUT   (fraqueza + tendência baixa)
    - RSI muito extremo (< rsi_strong_oversold ou > rsi_strong_overbought): sinal RSI prevalece

    Thresholds padrão: rsi_buy=55, rsi_sell=45 (zona neutra estreita, gera mais sinais).
    """
    if params is None:
        params = {}

    rsi_period = params.get("rsi_period", 14)
    rsi_buy = params.get("rsi_buy", params.get("rsi_overbought", 55))
    rsi_sell = params.get("rsi_sell", params.get("rsi_oversold", 45))
    ema_fast = params.get("ema_fast", 9)
    ema_slow = params.get("ema_slow", 21)
    # Threshold para sinal RSI forte que supera confirmação EMA
    rsi_strong_oversold = params.get("rsi_strong_oversold", 30)
    rsi_strong_overbought = params.get("rsi_strong_overbought", 70)

    if len(df) < max(rsi_period, ema_slow) + 5:
        return "wait"

    try:
        close = df["close"]
        rsi = _calc_rsi(close, rsi_period)
        ema_f = _calc_ema(close, ema_fast)
        ema_s = _calc_ema(close, ema_slow)

        rsi_val = rsi.iloc[-1]
        ema_f_val = ema_f.iloc[-1]
        ema_s_val = ema_s.iloc[-1]

        if any(pd.isna(v) for v in [rsi_val, ema_f_val, ema_s_val]):
            return "wait"

        logger.debug(
            f"RSI_EMA: RSI={rsi_val:.2f} (sell<{rsi_sell}/buy>{rsi_buy}) "
            f"EMA{ema_fast}={ema_f_val:.4f} EMA{ema_slow}={ema_s_val:.4f}"
        )

        # Sinal RSI extremo (muito forte) → prevalece sobre EMA
        if rsi_val < rsi_strong_oversold:
            logger.info(f"RSI_EMA STRONG CALL: RSI={rsi_val:.2f} < {rsi_strong_oversold} (forte oversold)")
            return "call"

        if rsi_val > rsi_strong_overbought:
            logger.info(f"RSI_EMA STRONG PUT: RSI={rsi_val:.2f} > {rsi_strong_overbought} (forte overbought)")
            return "put"

        # Sinal principal: RSI indica direção + EMA confirma tendência
        if rsi_val > rsi_buy and ema_f_val > ema_s_val:
            logger.info(f"RSI_EMA CALL: RSI={rsi_val:.2f} > {rsi_buy}, EMA{ema_fast} > EMA{ema_slow}")
            return "call"

        if rsi_val < rsi_sell and ema_f_val < ema_s_val:
            logger.info(f"RSI_EMA PUT: RSI={rsi_val:.2f} < {rsi_sell}, EMA{ema_fast} < EMA{ema_slow}")
            return "put"

    except Exception as e:
        logger.error(f"Erro em rsi_ema_strategy: {e}")

    return "wait"


def bb_squeeze_strategy(df: pd.DataFrame,
                         params: Optional[Dict[str, Any]] = None) -> str:
    """
    Estratégia Bollinger Band — Proximidade de Banda + RSI (adaptada para Synthetic Indices).

    Lógica principal (gera sinal em ~20-30% dos candles):
    - Preço no 20% inferior da banda (pos < 20%) E RSI < rsi_sell (45) → CALL (reversão de alta)
    - Preço no 20% superior da banda (pos > 80%) E RSI > rsi_buy (55)  → PUT  (reversão de baixa)

    Lógica de breakout (fallback, mais raro mas forte):
    - close > upper (breakout acima) → PUT  (reversão extrema — preço retorna)
    - close < lower (breakout abaixo) → CALL (reversão extrema — preço retorna)

    Parâmetro squeeze_required (padrão False): se True, exige squeeze anterior
    antes de emitir sinal (squeeze_threshold_pct=0.90, squeeze_lookback=3).

    Nota: com bb_std=2.0, o breakout ocorre em ~2-3% dos candles apenas.
    A lógica de proximidade garante sinais frequentes em Synthetic Indices.
    """
    if params is None:
        params = {}

    bb_period = params.get("bb_period", 20)
    bb_std = params.get("bb_std", 2.0)
    squeeze_threshold_pct = params.get("squeeze_threshold_pct", 0.90)
    squeeze_required = params.get("squeeze_required", False)
    squeeze_lookback = params.get("squeeze_lookback", 3)
    rsi_period = params.get("rsi_period", 14)
    rsi_buy = params.get("rsi_buy", 55)    # RSI acima → força de alta (overbought na banda sup → PUT)
    rsi_sell = params.get("rsi_sell", 45)  # RSI abaixo → fraqueza (oversold na banda inf → CALL)
    band_zone = params.get("band_zone", 20)  # % da banda (top/bottom) para sinal de proximidade

    if len(df) < bb_period + rsi_period + 5:
        return "wait"

    try:
        close = df["close"]
        upper, mid, lower = _calc_bollinger(close, bb_period, bb_std)
        rsi = _calc_rsi(close, rsi_period)

        bb_width = (upper - lower) / mid
        avg_width = bb_width.rolling(bb_period).mean()

        last_width = bb_width.iloc[-1]
        last_avg = avg_width.iloc[-1]
        last_close = close.iloc[-1]
        last_upper = upper.iloc[-1]
        last_lower = lower.iloc[-1]
        rsi_val = rsi.iloc[-1]

        if any(pd.isna(v) for v in [last_width, last_upper, last_lower]):
            return "wait"

        # Posição percentual do preço dentro das bandas (0% = lower, 100% = upper)
        band_range = last_upper - last_lower
        pct_position = (last_close - last_lower) / band_range * 100 if band_range > 0 else 50

        logger.debug(
            f"BB_Squeeze: close={last_close:.4f} pos_in_band={pct_position:.1f}% "
            f"RSI={rsi_val:.1f} upper={last_upper:.4f} lower={last_lower:.4f}"
        )

        # Verificar squeeze opcional (padrão: desativado)
        if squeeze_required and not pd.isna(last_avg):
            squeeze_window = bb_width.iloc[-squeeze_lookback-1:-1]
            is_squeeze = (squeeze_window < avg_width.iloc[-squeeze_lookback-1:-1] * squeeze_threshold_pct).all()
            if not is_squeeze:
                return "wait"

        # --- Condição 1: Breakout extremo (raro, ~2-3% dos candles) ---
        if last_close > last_upper:
            # Breakout acima da banda → reversão de baixa esperada
            logger.info(f"BB PUT (breakout): close={last_close:.4f} > upper={last_upper:.4f}, pos={pct_position:.1f}%")
            return "put"

        if last_close < last_lower:
            # Breakout abaixo da banda → reversão de alta esperada
            logger.info(f"BB CALL (breakout): close={last_close:.4f} < lower={last_lower:.4f}, pos={pct_position:.1f}%")
            return "call"

        # --- Condição 2: Proximidade de banda + confirmação RSI (~20-30% dos candles) ---
        rsi_ok = not pd.isna(rsi_val)

        # Preço no fundo da banda (próximo à lower) + RSI fraco → reversão de alta
        if pct_position < band_zone:
            if rsi_ok and rsi_val < rsi_sell:
                logger.info(
                    f"BB CALL (proximidade lower): pos={pct_position:.1f}% < {band_zone}%, "
                    f"RSI={rsi_val:.1f} < {rsi_sell}"
                )
                return "call"
            elif not rsi_ok:
                logger.info(f"BB CALL (proximidade lower sem RSI): pos={pct_position:.1f}% < {band_zone}%")
                return "call"

        # Preço no topo da banda (próximo à upper) + RSI forte → reversão de baixa
        if pct_position > (100 - band_zone):
            if rsi_ok and rsi_val > rsi_buy:
                logger.info(
                    f"BB PUT (proximidade upper): pos={pct_position:.1f}% > {100 - band_zone}%, "
                    f"RSI={rsi_val:.1f} > {rsi_buy}"
                )
                return "put"
            elif not rsi_ok:
                logger.info(f"BB PUT (proximidade upper sem RSI): pos={pct_position:.1f}% > {100 - band_zone}%")
                return "put"

    except Exception as e:
        logger.error(f"Erro em bb_squeeze_strategy: {e}")

    return "wait"


def trend_follow_strategy(df: pd.DataFrame,
                           params: Optional[Dict[str, Any]] = None) -> str:
    """
    Estratégia Trend Follow — EMA9 vs EMA21.

    Estratégia simples e de alta frequência de sinais baseada apenas na tendência EMA.
    - EMA9 > EMA21 → CALL (tendência de alta)
    - EMA9 < EMA21 → PUT  (tendência de baixa)

    Opcional: confirmar com RSI não-neutro (rsi_filter=True) e verificar se
    a tendência é suficientemente forte (min_gap_pct).
    """
    if params is None:
        params = {}

    ema_fast = params.get("ema_fast", 9)
    ema_slow = params.get("ema_slow", 21)
    rsi_filter = params.get("rsi_filter", False)
    rsi_period = params.get("rsi_period", 14)
    min_gap_pct = params.get("min_gap_pct", 0.0)  # % mínima de diferença entre EMAs

    if len(df) < max(ema_slow, rsi_period if rsi_filter else 0) + 5:
        return "wait"

    try:
        close = df["close"]
        ema_f = _calc_ema(close, ema_fast)
        ema_s = _calc_ema(close, ema_slow)

        ema_f_val = ema_f.iloc[-1]
        ema_s_val = ema_s.iloc[-1]

        if any(pd.isna(v) for v in [ema_f_val, ema_s_val]):
            return "wait"

        # Verificar gap mínimo entre EMAs
        if min_gap_pct > 0:
            gap_pct = abs(ema_f_val - ema_s_val) / ema_s_val * 100
            if gap_pct < min_gap_pct:
                return "wait"

        # Filtro RSI opcional (não emitir sinal se RSI está muito neutro)
        if rsi_filter:
            rsi = _calc_rsi(close, rsi_period)
            rsi_val = rsi.iloc[-1]
            if not pd.isna(rsi_val) and 45 < rsi_val < 55:
                logger.debug(f"TrendFollow: RSI={rsi_val:.2f} muito neutro (45-55), sem sinal")
                return "wait"

        if ema_f_val > ema_s_val:
            logger.info(f"TrendFollow CALL: EMA{ema_fast}={ema_f_val:.4f} > EMA{ema_slow}={ema_s_val:.4f}")
            return "call"
        elif ema_f_val < ema_s_val:
            logger.info(f"TrendFollow PUT: EMA{ema_fast}={ema_f_val:.4f} < EMA{ema_slow}={ema_s_val:.4f}")
            return "put"

    except Exception as e:
        logger.error(f"Erro em trend_follow_strategy: {e}")

    return "wait"


def stochrsi_strategy(df: pd.DataFrame,
                       params: Optional[Dict[str, Any]] = None) -> str:
    """
    Estratégia StochRSI Zonas Extremas.

    Lógica corrigida: verifica se K está em zona extrema E K > D (momentum de alta/baixa).
    A exigência de cruzamento DENTRO da zona era quasi-impossível — o cruzamento tipicamente
    ocorre SAINDO da zona extrema, não dentro dela.

    - K < stoch_oversold (20) E K > D (momentum de alta saindo do oversold) → CALL
    - K > stoch_overbought (80) E K < D (momentum de baixa saindo do overbought) → PUT

    Thresholds: 20/80 (padrão clássico StochRSI).
    """
    if params is None:
        params = {}

    rsi_length = params.get("rsi_length", 14)
    k_period = params.get("k_period", 3)
    d_period = params.get("d_period", 3)
    stoch_oversold = params.get("stoch_oversold", 20)
    stoch_overbought = params.get("stoch_overbought", 80)

    if len(df) < rsi_length + k_period + d_period + 5:
        return "wait"

    try:
        close = df["close"]
        k, d = _calc_stochrsi(close, rsi_length, k_period, d_period)

        last_k = k.iloc[-1]
        last_d = d.iloc[-1]
        prev_k = k.iloc[-2]
        prev_d = d.iloc[-2]

        if any(pd.isna(v) for v in [last_k, last_d, prev_k, prev_d]):
            return "wait"

        logger.debug(
            f"StochRSI: K={last_k:.2f}, D={last_d:.2f} "
            f"(oversold<{stoch_oversold}/overbought>{stoch_overbought})"
        )

        # CALL: K está em zona oversold E mostra momentum de alta (K > D ou cruzando acima)
        if last_k < stoch_oversold and last_k >= last_d:
            logger.info(f"StochRSI CALL: K={last_k:.2f} < {stoch_oversold} (oversold), K >= D")
            return "call"

        # CALL alternativo: K cruzou acima de D (saindo de oversold)
        if prev_k < stoch_oversold and prev_k <= prev_d and last_k > last_d:
            logger.info(f"StochRSI CALL (cruzamento saindo de oversold): K={last_k:.2f}")
            return "call"

        # PUT: K está em zona overbought E mostra momentum de baixa (K < D ou cruzando abaixo)
        if last_k > stoch_overbought and last_k <= last_d:
            logger.info(f"StochRSI PUT: K={last_k:.2f} > {stoch_overbought} (overbought), K <= D")
            return "put"

        # PUT alternativo: K cruzou abaixo de D (saindo de overbought)
        if prev_k > stoch_overbought and prev_k >= prev_d and last_k < last_d:
            logger.info(f"StochRSI PUT (cruzamento saindo de overbought): K={last_k:.2f}")
            return "put"

    except Exception as e:
        logger.error(f"Erro em stochrsi_strategy: {e}")

    return "wait"


def ema_pullback_strategy(df: pd.DataFrame,
                           params: Optional[Dict[str, Any]] = None) -> str:
    """
    Estratégia EMA Crossover + Pullback.

    Lógica corrigida: o threshold de 0.001 (0.1%) era extremamente restritivo para
    Synthetic Indices (e.g., R_75 ~800 pts → tolerância de apenas 0.8 pts).
    Agora usa RSI como confirmação de direção em vez de exigir toque preciso na EMA.

    - Tendência alta (fast > slow > filter) + RSI indica força (> rsi_threshold) → CALL
    - Tendência baixa (fast < slow < filter) + RSI indica fraqueza (< 100-rsi_threshold) → PUT
    - Fallback: apenas alinhamento das 3 EMAs (sem filtro RSI) gera sinal
    """
    if params is None:
        params = {}

    ema_fast = params.get("ema_fast", 9)
    ema_slow = params.get("ema_slow", 21)
    ema_filter = params.get("ema_filter", 50)
    rsi_period = params.get("rsi_period", 14)
    rsi_threshold = params.get("rsi_threshold", 50)  # RSI > 50 confirma alta, < 50 confirma baixa
    # Threshold de toque relaxado: 0.5% (era 0.1%)
    touch_pct = params.get("touch_pct", 0.005)

    if len(df) < ema_filter + 5:
        return "wait"

    try:
        close = df["close"]
        ema_f = _calc_ema(close, ema_fast)
        ema_s = _calc_ema(close, ema_slow)
        ema_fil = _calc_ema(close, ema_filter)
        rsi = _calc_rsi(close, rsi_period)

        last_f = ema_f.iloc[-1]
        last_s = ema_s.iloc[-1]
        last_fil = ema_fil.iloc[-1]
        last_close = close.iloc[-1]
        prev_close = close.iloc[-2]
        prev_f = ema_f.iloc[-2]
        rsi_val = rsi.iloc[-1]

        if any(pd.isna(v) for v in [last_f, last_s, last_fil]):
            return "wait"

        threshold = last_f * touch_pct  # 0.5% de tolerância (era 0.1%)

        if last_f > last_s > last_fil:
            # Toque na EMA rápida (dentro do threshold relaxado)
            touch_ema = abs(last_close - last_f) <= threshold
            # Ou cruzamento de preço sobre EMA rápida (pullback e retomada)
            crossover = prev_close <= prev_f and last_close > last_f
            # Ou confirmação pelo RSI (momentum de alta)
            rsi_confirms = not pd.isna(rsi_val) and rsi_val > rsi_threshold

            if touch_ema or crossover or rsi_confirms:
                logger.info(
                    f"EMA_PULLBACK CALL: close={last_close:.4f} "
                    f"(touch={touch_ema}, cross={crossover}, rsi={rsi_val:.1f})"
                )
                return "call"

        elif last_f < last_s < last_fil:
            # Toque na EMA rápida
            touch_ema = abs(last_close - last_f) <= threshold
            # Ou cruzamento de preço abaixo da EMA rápida
            crossover = prev_close >= prev_f and last_close < last_f
            # Ou confirmação pelo RSI (momentum de baixa)
            rsi_confirms = not pd.isna(rsi_val) and rsi_val < (100 - rsi_threshold)

            if touch_ema or crossover or rsi_confirms:
                logger.info(
                    f"EMA_PULLBACK PUT: close={last_close:.4f} "
                    f"(touch={touch_ema}, cross={crossover}, rsi={rsi_val:.1f})"
                )
                return "put"

    except Exception as e:
        logger.error(f"Erro em ema_pullback_strategy: {e}")

    return "wait"


def coin_flip_strategy(df: pd.DataFrame,
                       params: Optional[Dict[str, Any]] = None) -> str:
    """
    Estratégia Coin Flip — Cara ou Coroa.

    A cada chamada, sorteia aleatoriamente 'call' ou 'put' com probabilidade 50/50.
    Útil para testar a UI, comparar com baseline aleatório e verificar o ciclo
    completo de trades no sistema.

    Não usa nenhum indicador técnico — apenas random.choice.
    """
    import random as _random
    if params is None:
        params = {}

    # Semente opcional para reprodutibilidade em testes
    seed = params.get("seed", None)
    rng_local = _random.Random(seed) if seed is not None else _random.Random()

    choice = rng_local.choice(["call", "put"])
    logger.info(f"CoinFlip: sorteio → {choice.upper()}")
    return choice


# Mapa de estratégias disponíveis
STRATEGIES: Dict[str, Callable] = {
    "rsi_ema": rsi_ema_strategy,
    "bb_squeeze": bb_squeeze_strategy,
    "trend_follow": trend_follow_strategy,
    "stochrsi": stochrsi_strategy,
    "ema_pullback": ema_pullback_strategy,
    "coin_flip": coin_flip_strategy,
}

STRATEGIES_INFO = [
    {
        "id": "rsi_ema",
        "name": "RSI Momentum + EMA Confirmação",
        "description": (
            "RSI > 55 E EMA rápida > EMA lenta → CALL. "
            "RSI < 45 E EMA rápida < EMA lenta → PUT. "
            "RSI extremo (<30 ou >70) supera confirmação EMA. "
            "Zona neutra estreita (45-55) gera sinais mais frequentes."
        ),
        "params": [
            "rsi_period", "rsi_buy", "rsi_sell",
            "rsi_strong_oversold", "rsi_strong_overbought",
            "ema_fast", "ema_slow",
        ],
        "defaults": {
            "rsi_period": 14, "rsi_buy": 55,
            "rsi_sell": 45, "rsi_strong_oversold": 30,
            "rsi_strong_overbought": 70, "ema_fast": 9, "ema_slow": 21,
        },
    },
    {
        "id": "bb_squeeze",
        "name": "Bollinger Band Breakout",
        "description": (
            "Breakout das Bollinger Bands. "
            "squeeze_required=false (padrão) para mais sinais em Synthetic Indices. "
            "squeeze_threshold_pct=0.90 e squeeze_lookback=3 velas quando ativo."
        ),
        "params": ["bb_period", "bb_std", "squeeze_required", "squeeze_threshold_pct", "squeeze_lookback"],
        "defaults": {
            "bb_period": 20, "bb_std": 2.0,
            "squeeze_required": False, "squeeze_threshold_pct": 0.90,
            "squeeze_lookback": 3,
        },
    },
    {
        "id": "trend_follow",
        "name": "Trend Follow EMA (Alta Frequência)",
        "description": (
            "Sinal pela tendência EMA9 vs EMA21. "
            "Estratégia mais simples e de maior frequência de sinais. "
            "rsi_filter=true adiciona filtro RSI para evitar zonas neutras. "
            "min_gap_pct filtra tendências fracas."
        ),
        "params": ["ema_fast", "ema_slow", "rsi_filter", "rsi_period", "min_gap_pct"],
        "defaults": {
            "ema_fast": 9, "ema_slow": 21,
            "rsi_filter": False, "rsi_period": 14, "min_gap_pct": 0.0,
        },
    },
    {
        "id": "stochrsi",
        "name": "StochRSI Zonas Extremas",
        "description": (
            "K em zona oversold (<20) com momentum de alta → CALL. "
            "K em zona overbought (>80) com momentum de baixa → PUT. "
            "Também captura cruzamento K/D saindo das zonas extremas."
        ),
        "params": ["rsi_length", "k_period", "d_period", "stoch_oversold", "stoch_overbought"],
        "defaults": {
            "rsi_length": 14, "k_period": 3, "d_period": 3,
            "stoch_oversold": 20, "stoch_overbought": 80,
        },
    },
    {
        "id": "ema_pullback",
        "name": "EMA Crossover + Pullback (RSI confirmação)",
        "description": (
            "Tendência confirmada por 3 EMAs alinhadas. "
            "Entrada quando RSI confirma direção (>50 para alta, <50 para baixa), "
            "ou toque na EMA rápida (0.5% de tolerância), ou cruzamento de preço. "
            "touch_pct=0.005 (0.5%) e rsi_threshold=50 por padrão."
        ),
        "params": ["ema_fast", "ema_slow", "ema_filter", "rsi_period", "rsi_threshold", "touch_pct"],
        "defaults": {
            "ema_fast": 9, "ema_slow": 21, "ema_filter": 50,
            "rsi_period": 14, "rsi_threshold": 50, "touch_pct": 0.005,
        },
    },
    {
        "id": "coin_flip",
        "name": "🪙 Coin Flip (Cara ou Coroa)",
        "description": (
            "Sorteia aleatoriamente CALL ou PUT com 50% de probabilidade cada. "
            "Útil para testar a UI e comparar performance com o baseline aleatório. "
            "Parâmetro opcional: seed (int) para reprodutibilidade."
        ),
        "params": ["seed"],
        "defaults": {"seed": None},
    },
]


def generate_signal(df: pd.DataFrame, strategy_name: str,
                    params: Optional[Dict[str, Any]] = None) -> str:
    """
    Gera um sinal de trading usando a estratégia especificada.
    Retorna 'call', 'put' ou 'wait'.
    """
    if df is None or df.empty or len(df) < 10:
        return "wait"

    strategy_fn = STRATEGIES.get(strategy_name)
    if not strategy_fn:
        logger.warning(f"Estratégia desconhecida: {strategy_name}. Usando rsi_ema.")
        strategy_fn = rsi_ema_strategy

    return strategy_fn(df, params or {})


def get_strategy_info(strategy_name: str) -> Dict[str, Any]:
    """Retorna informações sobre uma estratégia pelo nome."""
    for info in STRATEGIES_INFO:
        if info["id"] == strategy_name:
            return info
    return {}
