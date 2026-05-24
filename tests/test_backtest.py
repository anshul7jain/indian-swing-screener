from __future__ import annotations

import pandas as pd

from src.backtest import _simulate_exit


def _history() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=5, freq="B")
    return pd.DataFrame(
        {
            "Open": [100, 101, 104, 105, 106],
            "High": [101, 103, 111, 106, 107],
            "Low": [99, 100, 103, 104, 105],
            "Close": [100, 102, 110, 105, 106],
        },
        index=dates,
    )


def test_simulate_exit_enters_next_open_and_hits_target() -> None:
    result = _simulate_exit(
        _history(),
        signal_date=pd.Timestamp("2024-01-01"),
        entry=100,
        stop=96,
        target=110,
        max_holding_days=4,
    )

    assert result is not None
    assert result["entry_date"] == "2024-01-02"
    assert result["entry"] == 101
    assert result["exit_reason"] == "target"
    assert result["exit"] == 110


def test_simulate_exit_uses_time_exit_when_no_level_hit() -> None:
    result = _simulate_exit(
        _history(),
        signal_date=pd.Timestamp("2024-01-01"),
        entry=100,
        stop=80,
        target=140,
        max_holding_days=2,
    )

    assert result is not None
    assert result["exit_reason"] == "time_exit"
    assert result["exit_date"] == "2024-01-03"
    assert result["exit"] == 110
