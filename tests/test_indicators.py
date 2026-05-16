from __future__ import annotations

import pandas as pd

from src.indicators import add_indicators


def test_add_indicators_creates_expected_columns() -> None:
    dates = pd.date_range("2024-01-01", periods=260, freq="B")
    values = pd.Series(range(100, 360), index=dates, dtype="float64")
    df = pd.DataFrame(
        {
            "Open": values - 1,
            "High": values + 2,
            "Low": values - 2,
            "Close": values,
            "Adj Close": values,
            "Volume": 100000,
        },
        index=dates,
    )

    out = add_indicators(df)

    for column in ["sma_20", "sma_50", "sma_200", "ema_20", "rsi_14", "atr_14", "high_52w"]:
        assert column in out.columns
    assert out["sma_200"].iloc[-1] > 0
    assert out["rsi_14"].iloc[-1] == 100
    assert out["high_52w"].iloc[-1] == out["High"].tail(252).max()
