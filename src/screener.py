from __future__ import annotations

import pandas as pd

from .data import fetch_history
from .indicators import add_indicators, latest_complete_row
from .strategies import evaluate_strategies


def _sector_scores(latest_rows: pd.DataFrame) -> dict[str, float]:
    if latest_rows.empty:
        return {}

    sector_strength = (
        latest_rows.assign(
            weighted_return=lambda df: (df["ret_3m"].fillna(0) * 0.65)
            + (df["ret_6m"].fillna(0) * 0.35)
        )
        .groupby("sector", as_index=False)["weighted_return"]
        .mean()
    )
    sector_strength["sector_score"] = sector_strength["weighted_return"].rank(pct=True) * 100
    return dict(zip(sector_strength["sector"], sector_strength["sector_score"], strict=False))


def collect_latest_rows(
    universe: pd.DataFrame,
    period: str = "18mo",
    max_symbols: int | None = None,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[str]]:
    rows: list[dict[str, object]] = []
    histories: dict[str, pd.DataFrame] = {}
    failures: list[str] = []

    sample = universe.head(max_symbols) if max_symbols else universe
    for stock in sample.itertuples(index=False):
        try:
            history = fetch_history(stock.yahoo_symbol, period)
            if history.empty or len(history) < 210:
                failures.append(f"{stock.symbol}: not enough price history")
                continue

            enriched = add_indicators(history)
            enriched["Close_prev"] = enriched["Close"].shift(1)
            latest = latest_complete_row(enriched)
            if latest.empty:
                failures.append(f"{stock.symbol}: indicators unavailable")
                continue

            histories[stock.symbol] = enriched
            rows.append(
                {
                    "symbol": stock.symbol,
                    "yahoo_symbol": stock.yahoo_symbol,
                    "name": stock.name,
                    "sector": stock.sector,
                    "date": latest.name.date().isoformat(),
                    **latest.to_dict(),
                }
            )
        except Exception as exc:  # noqa: BLE001 - keep the dashboard resilient per-symbol.
            failures.append(f"{stock.symbol}: {exc}")

    return pd.DataFrame(rows), histories, failures


def _get_current_market_regime() -> int:
    try:
        import yfinance as yf
        df = yf.download("^NSEI", period="6mo", interval="1d", auto_adjust=False, progress=False)
        if df.empty:
            return 0
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        df["sma_20"] = df["Close"].rolling(20, min_periods=20).mean()
        df["sma_50"] = df["Close"].rolling(50, min_periods=50).mean()

        if df["sma_50"].isna().iloc[-1] or df["sma_20"].isna().iloc[-1]:
            return 0

        close = float(df["Close"].iloc[-1])
        sma_20 = float(df["sma_20"].iloc[-1])
        sma_50 = float(df["sma_50"].iloc[-1])

        if close > sma_20 and sma_20 > sma_50:
            return 1
        elif close < sma_20 and sma_20 < sma_50:
            return -1
        return 0
    except Exception:
        return 0


def screen_universe(
    universe: pd.DataFrame,
    period: str = "18mo",
    min_score: float = 65,
    max_symbols: int | None = None,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[str], int]:
    latest_rows, histories, failures = collect_latest_rows(universe, period, max_symbols)
    market_regime = _get_current_market_regime()

    if latest_rows.empty:
        return pd.DataFrame(), histories, failures, market_regime

    sector_scores = _sector_scores(latest_rows)
    signal_rows: list[dict[str, object]] = []

    for _, row in latest_rows.iterrows():
        sector_score = round(sector_scores.get(row["sector"], 50), 1)
        for signal in evaluate_strategies(row, sector_score):
            if signal.score < min_score:
                continue

            if market_regime == 1 and signal.direction != "long":
                continue
            if market_regime == -1 and signal.direction != "short":
                continue

            signal_rows.append(
                {
                    "date": row["date"],
                    "symbol": row["symbol"],
                    "name": row["name"],
                    "sector": row["sector"],
                    "sector_score": sector_score,
                    "strategy": signal.strategy,
                    "signal": signal.signal,
                    "score": signal.score,
                    "close": round(float(row["Close"]), 2),
                    "entry": signal.entry,
                    "stop": signal.stop,
                    "target": signal.target,
                    "risk_pct": signal.risk_pct,
                    "reward_risk": signal.reward_risk,
                    "rsi_14": round(float(row["rsi_14"]), 1),
                    "volume_ratio": round(float(row["volume_ratio"]), 2),
                    "ret_1m_pct": round(float(row["ret_1m"]) * 100, 2),
                    "ret_3m_pct": round(float(row["ret_3m"]) * 100, 2),
                    "ret_6m_pct": round(float(row["ret_6m"]) * 100, 2),
                    "distance_to_52w_high_pct": round(float(row["distance_to_52w_high"]) * 100, 2),
                    "reasons": signal.reasons,
                }
            )

    signals = pd.DataFrame(signal_rows)
    if signals.empty:
        return signals, histories, failures, market_regime

    signals = signals.sort_values(
        by=["score", "sector_score", "ret_3m_pct"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    return signals, histories, failures, market_regime

