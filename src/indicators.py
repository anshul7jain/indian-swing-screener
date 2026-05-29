from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss
    out = 100 - (100 / (1 + rs))
    out = out.mask((avg_loss == 0) & (avg_gain > 0), 100)
    out = out.mask((avg_gain == 0) & (avg_loss > 0), 0)
    out = out.mask((avg_gain == 0) & (avg_loss == 0), 50)
    return out


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    close = out["Close"]

    out["sma_20"] = close.rolling(20, min_periods=20).mean()
    out["sma_50"] = close.rolling(50, min_periods=50).mean()
    out["sma_150"] = close.rolling(150, min_periods=150).mean()
    out["sma_200"] = close.rolling(200, min_periods=200).mean()
    out["ema_20"] = close.ewm(span=20, min_periods=20, adjust=False).mean()
    out["rsi_14"] = rsi(close, 14)
    out["atr_14"] = atr(out, 14)
    out["volume_sma_20"] = out["Volume"].rolling(20, min_periods=20).mean()

    # Bollinger Bands (20, 2)
    std_20 = close.rolling(20, min_periods=20).std()
    out["bb_mid"] = close.rolling(20, min_periods=20).mean()
    out["bb_upper"] = out["bb_mid"] + (2 * std_20)
    out["bb_lower"] = out["bb_mid"] - (2 * std_20)

    out["high_20_prev"] = out["High"].rolling(20, min_periods=20).max().shift(1)
    out["low_10_prev"] = out["Low"].rolling(10, min_periods=10).min().shift(1)
    out["low_20_prev"] = out["Low"].rolling(20, min_periods=20).min().shift(1)
    out["high_10_prev"] = out["High"].rolling(10, min_periods=10).max().shift(1)
    out["high_52w"] = out["High"].rolling(252, min_periods=120).max()
    out["low_52w"] = out["Low"].rolling(252, min_periods=120).min()

    out["ret_1m"] = close.pct_change(21)
    out["ret_3m"] = close.pct_change(63)
    out["ret_6m"] = close.pct_change(126)
    out["distance_to_52w_high"] = (close / out["high_52w"]) - 1
    out["distance_to_52w_low"] = (close / out["low_52w"]) - 1
    out["distance_to_ema_20"] = (close / out["ema_20"]) - 1
    out["volume_ratio"] = out["Volume"] / out["volume_sma_20"]
    return out


def latest_complete_row(df: pd.DataFrame) -> pd.Series:
    clean = df.dropna(subset=["Close", "sma_50", "sma_200", "rsi_14", "atr_14"])
    if clean.empty:
        return pd.Series(dtype="float64")
    return clean.iloc[-1]
