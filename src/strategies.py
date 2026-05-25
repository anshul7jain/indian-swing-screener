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


def _risk_plan(close: float, atr: float, swing_extreme: float, direction: str = "long") -> tuple[float, float, float, float, float]:
    entry = close

    if direction == "long":
        atr_stop = close - (2.5 * atr)
        swing_stop = swing_extreme if not math.isnan(swing_extreme) else atr_stop
        # Don't restrict the stop too tightly to allow trades to breathe
        stop = max(min(atr_stop, swing_stop), close * 0.85)
        risk = max(entry - stop, 0.01)
        target = entry + (2 * risk)
        risk_pct = (risk / entry) * 100
        reward_risk = (target - entry) / risk
    else:
        atr_stop = close + (2.5 * atr)
        swing_stop = swing_extreme if not math.isnan(swing_extreme) else atr_stop
        stop = min(max(atr_stop, swing_stop), close * 1.15)
        risk = max(stop - entry, 0.01)
        target = entry - (2 * risk)
        risk_pct = (risk / entry) * 100
        reward_risk = (entry - target) / risk

    return entry, stop, target, risk_pct, reward_risk


def breakout_signal(row: pd.Series, sector_score: float = 50) -> StrategySignal | None:
    close = _safe_float(row.get("Close"))
    sma_50 = _safe_float(row.get("sma_50"))
    sma_200 = _safe_float(row.get("sma_200"))
    rsi = _safe_float(row.get("rsi_14"))
    atr = _safe_float(row.get("atr_14"))
    low_10 = _safe_float(row.get("low_10_prev"))
    high_20 = _safe_float(row.get("high_20_prev"))
    dist_high = _safe_float(row.get("distance_to_52w_high"))
    volume_ratio = _safe_float(row.get("volume_ratio"), 1)
    ret_3m = _safe_float(row.get("ret_3m"), 0)
    ret_6m = _safe_float(row.get("ret_6m"), 0)

    if any(math.isnan(value) for value in [close, sma_50, sma_200, rsi, atr, dist_high]):
        return None

    trend_ok = close > sma_50 > sma_200
    near_high = dist_high >= -0.08
    breakout_ok = close > high_20 if not math.isnan(high_20) else near_high
    rsi_ok = 50 <= rsi <= 76
    strength_ok = ret_3m > 0 and ret_6m > 0

    score = 0
    score += 25 if trend_ok else 0
    score += 20 if near_high else max(0, 20 + (dist_high * 200))
    score += 15 if breakout_ok else 0
    score += 10 if volume_ratio >= 1.2 else min(10, max(0, volume_ratio * 6))
    score += 15 if rsi_ok else max(0, 15 - abs(rsi - 62) * 0.8)
    score += 10 if strength_ok else max(0, ret_3m * 40)
    score += min(5, max(0, sector_score / 20))

    if score < 55 or not trend_ok:
        return None

    entry, stop, target, risk_pct, reward_risk = _risk_plan(close, atr, low_10, "long")
    signal = "Breakout watch" if score < 75 else "Paper buy watch"
    reasons = []
    if near_high:
        reasons.append("near 52w high")
    if breakout_ok:
        reasons.append("20d breakout")
    if volume_ratio >= 1.2:
        reasons.append("volume expansion")
    if sector_score >= 60:
        reasons.append("strong sector")

    return StrategySignal(
        strategy="Sector Momentum Breakout",
        direction="long",
        signal=signal,
        score=round(score, 1),
        entry=round(entry, 2),
        stop=round(stop, 2),
        target=round(target, 2),
        risk_pct=round(risk_pct, 2),
        reward_risk=round(reward_risk, 2),
        reasons=", ".join(reasons) or "trend and momentum setup",
    )


def breakdown_signal(row: pd.Series, sector_score: float = 50) -> StrategySignal | None:
    close = _safe_float(row.get("Close"))
    sma_50 = _safe_float(row.get("sma_50"))
    sma_200 = _safe_float(row.get("sma_200"))
    rsi = _safe_float(row.get("rsi_14"))
    atr = _safe_float(row.get("atr_14"))
    high_10 = _safe_float(row.get("high_10_prev"))
    low_20 = _safe_float(row.get("low_20_prev"))
    dist_low = _safe_float(row.get("distance_to_52w_low"))
    volume_ratio = _safe_float(row.get("volume_ratio"), 1)
    ret_3m = _safe_float(row.get("ret_3m"), 0)
    ret_6m = _safe_float(row.get("ret_6m"), 0)

    if any(math.isnan(value) for value in [close, sma_50, sma_200, rsi, atr, dist_low]):
        return None

    trend_ok = close < sma_50 < sma_200
    near_low = dist_low <= 0.08
    breakdown_ok = close < low_20 if not math.isnan(low_20) else near_low
    rsi_ok = 24 <= rsi <= 50
    weakness_ok = ret_3m < 0 and ret_6m < 0

    score = 0
    score += 25 if trend_ok else 0
    score += 20 if near_low else max(0, 20 - (dist_low * 200))
    score += 15 if breakdown_ok else 0
    score += 10 if volume_ratio >= 1.2 else min(10, max(0, volume_ratio * 6))
    score += 15 if rsi_ok else max(0, 15 - abs(rsi - 38) * 0.8)
    score += 10 if weakness_ok else max(0, -ret_3m * 40)
    score += min(5, max(0, (100 - sector_score) / 20))

    if score < 55 or not trend_ok:
        return None

    entry, stop, target, risk_pct, reward_risk = _risk_plan(close, atr, high_10, "short")
    signal = "Breakdown watch" if score < 75 else "Paper short watch"
    reasons = []
    if near_low:
        reasons.append("near 52w low")
    if breakdown_ok:
        reasons.append("20d breakdown")
    if volume_ratio >= 1.2:
        reasons.append("volume expansion")
    if sector_score <= 40:
        reasons.append("weak sector")

    return StrategySignal(
        strategy="Sector Momentum Breakdown",
        direction="short",
        signal=signal,
        score=round(score, 1),
        entry=round(entry, 2),
        stop=round(stop, 2),
        target=round(target, 2),
        risk_pct=round(risk_pct, 2),
        reward_risk=round(reward_risk, 2),
        reasons=", ".join(reasons) or "downtrend and momentum setup",
    )


def pullback_signal(row: pd.Series, sector_score: float = 50) -> StrategySignal | None:
    close = _safe_float(row.get("Close"))
    low = _safe_float(row.get("Low"))
    prev_close = _safe_float(row.get("Close_prev"))
    sma_50 = _safe_float(row.get("sma_50"))
    sma_200 = _safe_float(row.get("sma_200"))
    ema_20 = _safe_float(row.get("ema_20"))
    rsi = _safe_float(row.get("rsi_14"))
    atr = _safe_float(row.get("atr_14"))
    low_10 = _safe_float(row.get("low_10_prev"))
    dist_ema = _safe_float(row.get("distance_to_ema_20"))
    dist_high = _safe_float(row.get("distance_to_52w_high"), -1)
    ret_3m = _safe_float(row.get("ret_3m"), 0)

    if any(math.isnan(value) for value in [close, low, sma_50, sma_200, ema_20, rsi, atr, dist_ema]):
        return None

    trend_ok = close > sma_50 > sma_200
    touched_ema = low <= ema_20 * 1.02 or abs(dist_ema) <= 0.035
    bounce_ok = math.isnan(prev_close) or close > prev_close
    not_too_extended = dist_high < -0.02
    rsi_ok = 45 <= rsi <= 68

    score = 0
    score += 30 if trend_ok else 0
    score += 20 if touched_ema else max(0, 20 - abs(dist_ema) * 300)
    score += 15 if bounce_ok else 0
    score += 15 if rsi_ok else max(0, 15 - abs(rsi - 56) * 0.8)
    score += 10 if ret_3m > 0 else max(0, ret_3m * 50)
    score += 5 if not_too_extended else 0
    score += min(5, max(0, sector_score / 20))

    if score < 55 or not trend_ok or not touched_ema:
        return None

    entry, stop, target, risk_pct, reward_risk = _risk_plan(close, atr, low_10, "long")
    signal = "Pullback watch" if score < 75 else "Paper buy watch"
    reasons = ["uptrend pullback"]
    if touched_ema:
        reasons.append("near 20 EMA")
    if bounce_ok:
        reasons.append("bounce candle")
    if sector_score >= 60:
        reasons.append("strong sector")

    return StrategySignal(
        strategy="Trend Pullback Continuation",
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


def short_pullback_signal(row: pd.Series, sector_score: float = 50) -> StrategySignal | None:
    close = _safe_float(row.get("Close"))
    high = _safe_float(row.get("High"))
    prev_close = _safe_float(row.get("Close_prev"))
    sma_50 = _safe_float(row.get("sma_50"))
    sma_200 = _safe_float(row.get("sma_200"))
    ema_20 = _safe_float(row.get("ema_20"))
    rsi = _safe_float(row.get("rsi_14"))
    atr = _safe_float(row.get("atr_14"))
    high_10 = _safe_float(row.get("high_10_prev"))
    dist_ema = _safe_float(row.get("distance_to_ema_20"))
    dist_low = _safe_float(row.get("distance_to_52w_low"), 1)
    ret_3m = _safe_float(row.get("ret_3m"), 0)

    if any(math.isnan(value) for value in [close, high, sma_50, sma_200, ema_20, rsi, atr, dist_ema]):
        return None

    trend_ok = close < sma_50 < sma_200
    touched_ema = high >= ema_20 * 0.98 or abs(dist_ema) <= 0.035
    bounce_ok = math.isnan(prev_close) or close < prev_close
    not_too_extended = dist_low > 0.02
    rsi_ok = 32 <= rsi <= 55

    score = 0
    score += 30 if trend_ok else 0
    score += 20 if touched_ema else max(0, 20 - abs(dist_ema) * 300)
    score += 15 if bounce_ok else 0
    score += 15 if rsi_ok else max(0, 15 - abs(rsi - 44) * 0.8)
    score += 10 if ret_3m < 0 else max(0, -ret_3m * 50)
    score += 5 if not_too_extended else 0
    score += min(5, max(0, (100 - sector_score) / 20))

    if score < 55 or not trend_ok or not touched_ema:
        return None

    entry, stop, target, risk_pct, reward_risk = _risk_plan(close, atr, high_10, "short")
    signal = "Short pullback watch" if score < 75 else "Paper short watch"
    reasons = ["downtrend pullback"]
    if touched_ema:
        reasons.append("near 20 EMA")
    if bounce_ok:
        reasons.append("rejection candle")
    if sector_score <= 40:
        reasons.append("weak sector")

    return StrategySignal(
        strategy="Downtrend Pullback Continuation",
        direction="short",
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
    for evaluator in (breakout_signal, pullback_signal, breakdown_signal, short_pullback_signal):
        signal = evaluator(row, sector_score)
        if signal is not None:
            signals.append(signal)
    return signals

