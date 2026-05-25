import pandas as pd
from src.backtest import BacktestConfig, run_backtest
from src.data import load_universe

# Use the specific 20 portfolio
universe = pd.read_csv("data/portfolio_20.csv")
universe["yahoo_symbol"] = universe["symbol"] + ".NS"

config = BacktestConfig(start_date="2024-01-01", max_symbols=20)
trades, equity, metrics, failures = run_backtest(universe, config)
print(metrics)

if not trades.empty:
    print(trades['strategy'].value_counts())
    wins = trades[trades['r_multiple'] > 0]
    losses = trades[trades['r_multiple'] <= 0]

    print("\nWin trades stats:")
    print(wins[['holding_days', 'risk_pct', 'return_pct', 'r_multiple']].describe())

    print("\nLoss trades stats:")
    print(losses[['holding_days', 'risk_pct', 'return_pct', 'r_multiple']].describe())

    stops = losses[losses['exit_reason'] == 'stop']
    print("\nStopped out trades:")
    print(stops[['symbol', 'strategy', 'direction', 'holding_days', 'risk_pct', 'return_pct', 'score']].head(5))
