from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class StrategySignal:
    strategy: str
    direction: str
    signal: str
    score: float
    entry: float
    stop: float
    target: float
    risk_pct: float
    reward_risk: float
    reasons: str


def _safe_float(value: object, default: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out


def _risk_plan(close: float, atr: float, swing_extreme: float) -> tuple[float, float, float, float, float]:
    entry = close

    # Standard long configuration tailored for extremely high probability bounces
    atr_stop = close - (3.5 * atr)
    swing_stop = swing_extreme if not math.isnan(swing_extreme) else atr_stop
    stop = max(min(atr_stop, swing_stop), close * 0.80)
    risk = max(entry - stop, 0.01)

    # Dynamic target calculated outside this function for Mean Reversion
    target = entry + risk
    risk_pct = (risk / entry) * 100
    reward_risk = (target - entry) / risk

    return entry, stop, target, risk_pct, reward_risk

def deep_reversion_long(row: pd.Series, sector_score: float = 50) -> StrategySignal | None:
    """
    High Win-Rate Deep Reversion Strategy (Long Only):
    Identifies extreme oversold conditions in structurally sound stocks.
    - Buys when price pierces the Lower Bollinger Band.
    - Requires RSI < 35 (Deeply Oversold).
    - Requires Long-Term Trend (SMA 200) to still be positive.
    - Exits quickly at the 20 EMA mean.
    """
    close = _safe_float(row.get("Close"))
    low = _safe_float(row.get("Low"))
    sma_50 = _safe_float(row.get("sma_50"))
    sma_200 = _safe_float(row.get("sma_200"))
    ema_20 = _safe_float(row.get("ema_20"))
    bb_lower = _safe_float(row.get("bb_lower"))
    bb_mid = _safe_float(row.get("bb_mid"))
    rsi = _safe_float(row.get("rsi_14"))
    atr = _safe_float(row.get("atr_14"))
    low_10 = _safe_float(row.get("low_10_prev"))

    if any(math.isnan(value) for value in [close, low, sma_50, sma_200, ema_20, bb_lower, rsi, atr]):
        return None

    macro_ok = sma_50 > sma_200 or close > sma_200 * 0.90
    pierced_bb = low <= bb_lower
    oversold_rsi = rsi < 35

    score = 0
    score += 30 if macro_ok else 0
    score += 30 if pierced_bb else 0
    score += 20 if oversold_rsi else 0
    score += min(20, max(0, sector_score / 5))

    if score < 70 or not pierced_bb or not oversold_rsi or not macro_ok:
        return None

    entry, stop, target, risk_pct, reward_risk = _risk_plan(close, atr, low_10)

    # Target bb mid
    target = bb_mid if bb_mid > entry else entry + (0.5 * (entry - stop))
    reward_risk = (target - entry) / (entry - stop)

    if reward_risk < 0.15:
        return None

    signal = "Deep Reversion Buy"
    reasons = ["pierced lower bollinger band", "oversold RSI"]

    return StrategySignal(
        strategy="Mean Reversion (Long)",
        direction="long",
        signal=signal,
        score=round(score, 1),
        entry=round(entry, 2),
        stop=round(stop, 2),
        target=round(target, 2),
        risk_pct=round(risk_pct, 2),
        reward_risk=round(reward_risk, 2),
        reasons=", ".join(reasons),
    )

def evaluate_strategies(row: pd.Series, sector_score: float = 50) -> list[StrategySignal]:
    signals = []
    for evaluator in [deep_reversion_long]:
        signal = evaluator(row, sector_score)
        if signal is not None:
            signals.append(signal)
    return signals
