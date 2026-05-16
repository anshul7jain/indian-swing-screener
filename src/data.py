from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf

from .config import REQUIRED_UNIVERSE_COLUMNS, normalize_nse_symbol


def load_universe(path: str | Path) -> pd.DataFrame:
    universe = pd.read_csv(path)
    missing = REQUIRED_UNIVERSE_COLUMNS - set(universe.columns)
    if missing:
        raise ValueError(f"Universe CSV is missing columns: {', '.join(sorted(missing))}")

    universe = universe.copy()
    universe["symbol"] = universe["symbol"].astype(str).str.strip().str.upper()
    universe["name"] = universe["name"].astype(str).str.strip()
    universe["sector"] = universe["sector"].astype(str).str.strip()
    universe["yahoo_symbol"] = universe["symbol"].map(normalize_nse_symbol)
    return universe.drop_duplicates(subset=["symbol"]).reset_index(drop=True)


def fetch_history(yahoo_symbol: str, period: str = "18mo") -> pd.DataFrame:
    df = yf.download(
        yahoo_symbol,
        period=period,
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )

    if df.empty:
        return df

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    expected = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    available = [col for col in expected if col in df.columns]
    df = df[available].dropna(subset=["Open", "High", "Low", "Close"])
    df.index = pd.to_datetime(df.index)
    return df

