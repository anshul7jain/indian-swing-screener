from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd
import yfinance as yf

from .indicators import add_indicators
from .screener import _sector_scores
from .strategies import evaluate_strategies


@dataclass(frozen=True)
class BacktestConfig:
    start_date: str = "2024-01-01"
    min_score: float = 65
    max_symbols: int | None = 40
    max_holding_days: int = 30
    risk_per_trade_pct: float = 1.0


def _download_start(start_date: str) -> str:
    start = pd.Timestamp(start_date).date() - timedelta(days=430)
    return start.isoformat()


def _fetch_history_range(yahoo_symbol: str, start: str, end: str | None = None) -> pd.DataFrame:
    df = yf.download(
        yahoo_symbol,
        start=start,
        end=end,
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


def _prepare_histories(
    universe: pd.DataFrame,
    config: BacktestConfig,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    histories: dict[str, pd.DataFrame] = {}
    failures: list[str] = []
    sample = universe.head(config.max_symbols) if config.max_symbols else universe

    for stock in sample.itertuples(index=False):
        try:
            history = _fetch_history_range(stock.yahoo_symbol, _download_start(config.start_date))
            if history.empty or len(history) < 230:
                failures.append(f"{stock.symbol}: not enough price history")
                continue

            enriched = add_indicators(history)
            enriched["Close_prev"] = enriched["Close"].shift(1)
            enriched["symbol"] = stock.symbol
            enriched["name"] = stock.name
            enriched["sector"] = stock.sector
            histories[stock.symbol] = enriched
        except Exception as exc:  # noqa: BLE001 - keep backtest resilient per symbol.
            failures.append(f"{stock.symbol}: {exc}")

    return histories, failures


def _build_daily_rows(histories: dict[str, pd.DataFrame], run_date: pd.Timestamp) -> pd.DataFrame:
    rows = []
    for symbol, history in histories.items():
        if run_date not in history.index:
            continue
        row = history.loc[run_date]
        if row[["Close", "sma_50", "sma_200", "rsi_14", "atr_14"]].isna().any():
            continue
        rows.append(
            {
                "symbol": symbol,
                "name": row["name"],
                "sector": row["sector"],
                **row.to_dict(),
            }
        )
    return pd.DataFrame(rows)


def _simulate_exit(
    history: pd.DataFrame,
    signal_date: pd.Timestamp,
    entry: float,
    stop: float,
    target: float,
    max_holding_days: int,
    direction: str = "long",
) -> dict[str, object] | None:
    future = history.loc[history.index > signal_date].head(max_holding_days)
    if future.empty:
        return None

    entry_date = future.index[0]
    entry = float(future.iloc[0]["Open"]) if pd.notna(future.iloc[0]["Open"]) else entry

    if direction == "long":
        if entry <= stop:
            return {
                "entry_date": entry_date.date().isoformat(),
                "exit_date": entry_date.date().isoformat(),
                "entry": round(entry, 2),
                "exit": round(entry, 2),
                "exit_reason": "gap_past_stop",
                "holding_days": 0,
                "return_pct": 0.0,
            }
        if entry >= target:
            return {
                "entry_date": entry_date.date().isoformat(),
                "exit_date": entry_date.date().isoformat(),
                "entry": round(entry, 2),
                "exit": round(entry, 2),
                "exit_reason": "gap_past_target",
                "holding_days": 0,
                "return_pct": 0.0,
            }
    else:
        if entry >= stop:
            return {
                "entry_date": entry_date.date().isoformat(),
                "exit_date": entry_date.date().isoformat(),
                "entry": round(entry, 2),
                "exit": round(entry, 2),
                "exit_reason": "gap_past_stop",
                "holding_days": 0,
                "return_pct": 0.0,
            }
        if entry <= target:
            return {
                "entry_date": entry_date.date().isoformat(),
                "exit_date": entry_date.date().isoformat(),
                "entry": round(entry, 2),
                "exit": round(entry, 2),
                "exit_reason": "gap_past_target",
                "holding_days": 0,
                "return_pct": 0.0,
            }

    for day, row in future.iterrows():
        low = float(row["Low"])
        high = float(row["High"])
        close = float(row["Close"])

        if direction == "long":
            hit_stop = low <= stop
            hit_target = high >= target
        else:
            hit_stop = high >= stop
            hit_target = low <= target

        if hit_stop and hit_target:
            exit_price = stop
            exit_reason = "stop_and_target_same_day"
        elif hit_stop:
            exit_price = stop
            exit_reason = "stop"
        elif hit_target:
            exit_price = target
            exit_reason = "target"
        else:
            continue

        return_pct = ((exit_price / entry) - 1) * 100 if direction == "long" else ((entry / exit_price) - 1) * 100

        return {
            "entry_date": entry_date.date().isoformat(),
            "exit_date": day.date().isoformat(),
            "entry": round(entry, 2),
            "exit": round(exit_price, 2),
            "exit_reason": exit_reason,
            "holding_days": int((day - entry_date).days),
            "return_pct": round(return_pct, 2),
        }

    last_day = future.index[-1]
    last_close = float(future.iloc[-1]["Close"])
    return_pct = ((last_close / entry) - 1) * 100 if direction == "long" else ((entry / last_close) - 1) * 100

    return {
        "entry_date": entry_date.date().isoformat(),
        "exit_date": last_day.date().isoformat(),
        "entry": round(entry, 2),
        "exit": round(last_close, 2),
        "exit_reason": "time_exit",
        "holding_days": int((last_day - entry_date).days),
        "return_pct": round(return_pct, 2),
    }


def run_backtest(
    universe: pd.DataFrame,
    config: BacktestConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float], list[str]]:
    histories, failures = _prepare_histories(universe, config)
    if not histories:
        return pd.DataFrame(), pd.DataFrame(), {}, failures

    all_dates = sorted(set().union(*(set(history.index) for history in histories.values())))
    start = pd.Timestamp(config.start_date)
    signal_dates = [run_date for run_date in all_dates if run_date >= start]
    trades: list[dict[str, object]] = []
    active_until: dict[str, pd.Timestamp] = {}

    for run_date in signal_dates:
        daily_rows = _build_daily_rows(histories, run_date)
        if daily_rows.empty:
            continue

        sector_scores = _sector_scores(daily_rows)
        day_signals: list[dict[str, object]] = []
        for _, row in daily_rows.iterrows():
            sector_score = round(sector_scores.get(row["sector"], 50), 1)
            for signal in evaluate_strategies(row, sector_score):
                if signal.score < config.min_score:
                    continue
                day_signals.append(
                    {
                        "symbol": row["symbol"],
                        "name": row["name"],
                        "sector": row["sector"],
                        "strategy": signal.strategy,
                        "direction": signal.direction,
                        "score": signal.score,
                        "signal_date": run_date.date().isoformat(),
                        "planned_entry": signal.entry,
                        "planned_stop": signal.stop,
                        "planned_target": signal.target,
                        "risk_pct": signal.risk_pct,
                    }
                )

        for candidate in sorted(day_signals, key=lambda item: item["score"], reverse=True):
            symbol = str(candidate["symbol"])
            if active_until.get(symbol, pd.Timestamp.min) >= run_date:
                continue

            exit_plan = _simulate_exit(
                histories[symbol],
                run_date,
                float(candidate["planned_entry"]),
                float(candidate["planned_stop"]),
                float(candidate["planned_target"]),
                config.max_holding_days,
                str(candidate["direction"]),
            )
            if exit_plan is None:
                continue
            active_until[symbol] = pd.Timestamp(str(exit_plan["exit_date"]))

            entry_p = float(exit_plan["entry"])
            exit_p = float(exit_plan["exit"])
            stop_p = float(candidate["planned_stop"])
            if candidate["direction"] == "long":
                risk = max(entry_p - stop_p, 0.01)
                r_multiple = (exit_p - entry_p) / risk
            else:
                risk = max(stop_p - entry_p, 0.01)
                r_multiple = (entry_p - exit_p) / risk

            trades.append({**candidate, **exit_plan, "r_multiple": round(r_multiple, 2)})

    trades_df = pd.DataFrame(trades)
    if trades_df.empty:
        return trades_df, pd.DataFrame(), {}, failures

    trades_df = trades_df.sort_values(["entry_date", "score"], ascending=[True, False]).reset_index(drop=True)
    equity_trades = trades_df.sort_values(["exit_date", "entry_date"], ascending=[True, True]).copy()
    equity_trades["equity_r"] = equity_trades["r_multiple"].cumsum()
    equity_trades["equity_pct"] = equity_trades["equity_r"] * config.risk_per_trade_pct
    equity = equity_trades[["exit_date", "equity_r", "equity_pct"]].copy()
    equity["exit_date"] = pd.to_datetime(equity["exit_date"])

    wins = trades_df[trades_df["r_multiple"] > 0]
    losses = trades_df[trades_df["r_multiple"] <= 0]
    metrics = {
        "trades": float(len(trades_df)),
        "win_rate_pct": round((len(wins) / len(trades_df)) * 100, 2),
        "avg_return_pct": round(float(trades_df["return_pct"].mean()), 2),
        "avg_r": round(float(trades_df["r_multiple"].mean()), 2),
        "total_r": round(float(trades_df["r_multiple"].sum()), 2),
        "profit_factor": round(
            float(wins["r_multiple"].sum() / abs(losses["r_multiple"].sum())) if not losses.empty else 999.0,
            2,
        ),
    }
    return trades_df, equity, metrics, failures
