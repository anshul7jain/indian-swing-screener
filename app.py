from __future__ import annotations

import os
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.backtest import BacktestConfig, run_backtest
from src.config import APP_NAME, DEFAULT_MAX_SYMBOLS, DEFAULT_MIN_SCORE, DEFAULT_PERIOD, UNIVERSE_PATH
from src.data import load_universe
from src.notify_whatsapp import build_message, send_whatsapp
from src.screener import screen_universe

st.set_page_config(page_title=APP_NAME, layout="wide")


@st.cache_data(ttl=60 * 60)
def cached_universe() -> pd.DataFrame:
    return load_universe(UNIVERSE_PATH)


@st.cache_data(ttl=60 * 60)
def cached_screen(period: str, min_score: int, max_symbols: int | None):
    universe = cached_universe()
    return screen_universe(universe, period=period, min_score=min_score, max_symbols=max_symbols)


@st.cache_data(ttl=6 * 60 * 60)
def cached_backtest(
    start_date: str,
    min_score: int,
    max_symbols: int | None,
    max_holding_days: int,
    risk_per_trade_pct: float,
):
    universe = cached_universe()
    config = BacktestConfig(
        start_date=start_date,
        min_score=min_score,
        max_symbols=max_symbols,
        max_holding_days=max_holding_days,
        risk_per_trade_pct=risk_per_trade_pct,
    )
    return run_backtest(universe, config)


def render_chart(symbol: str, history: pd.DataFrame) -> None:
    recent = history.tail(180)
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=recent.index,
            open=recent["Open"],
            high=recent["High"],
            low=recent["Low"],
            close=recent["Close"],
            name=symbol,
        )
    )
    fig.add_trace(go.Scatter(x=recent.index, y=recent["ema_20"], name="20 EMA", line=dict(width=1.5)))
    fig.add_trace(go.Scatter(x=recent.index, y=recent["sma_50"], name="50 SMA", line=dict(width=1.5)))
    fig.add_trace(go.Scatter(x=recent.index, y=recent["sma_200"], name="200 SMA", line=dict(width=1.5)))
    fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    st.plotly_chart(fig, width="stretch")


def apply_streamlit_secrets_to_env() -> None:
    for key in [
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_FROM_WHATSAPP",
        "WHATSAPP_TO_NUMBER",
        "TWILIO_CONTENT_SID",
        "DASHBOARD_URL",
    ]:
        try:
            value = st.secrets.get(key)
        except Exception:  # noqa: BLE001 - secrets are absent in local dev until configured.
            value = None

        if value and not os.getenv(key):
            os.environ[key] = str(value)


def missing_whatsapp_settings() -> list[str]:
    required = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_WHATSAPP", "WHATSAPP_TO_NUMBER"]
    return [key for key in required if not os.getenv(key)]


st.title(APP_NAME)
st.caption("Daily NSE swing-trading screener with paper-only signals. No broker connection, no order placement.")

with st.sidebar:
    st.header("Scan Settings")
    period = st.selectbox("Price history", ["12mo", "18mo", "2y", "5y"], index=1)
    min_score = st.slider("Minimum signal score", 50, 90, DEFAULT_MIN_SCORE, 1)
    scan_all = st.checkbox("Scan full universe", value=False)
    max_symbols = None if scan_all else st.number_input("Max symbols", 20, 200, DEFAULT_MAX_SYMBOLS, 10)
    run_scan = st.button("Run scan", type="primary", width="stretch")
    st.divider()
    st.caption("Edit data/universe.csv to add/remove NSE symbols.")
    st.divider()
    st.header("WhatsApp")
    send_test_whatsapp = st.button("Send test WhatsApp", width="stretch")

if run_scan:
    st.cache_data.clear()

with st.spinner("Scanning NSE symbols from Yahoo Finance..."):
    signals, histories, failures, market_regime = cached_screen(period, min_score, None if scan_all else int(max_symbols))

if send_test_whatsapp:
    apply_streamlit_secrets_to_env()
    missing = missing_whatsapp_settings()
    if missing:
        st.sidebar.error(f"Missing WhatsApp settings: {', '.join(missing)}")
    else:
        message = build_message(signals, dashboard_url=os.getenv("DASHBOARD_URL", ""))
        try:
            result = send_whatsapp(message)
            if result == "dry-run":
                st.sidebar.warning("WhatsApp ran in dry-run mode. Check secrets and NOTIFY_DRY_RUN.")
            else:
                st.sidebar.success(f"WhatsApp API accepted message(s): {result}")
        except Exception as exc:  # noqa: BLE001 - surface Twilio's actionable message in the app.
            st.sidebar.error(f"WhatsApp send failed: {exc}")

if market_regime == 1:
    st.info("📈 Market Regime (Nifty 50): **Uptrend** (Filtering for Long setups only)")
elif market_regime == -1:
    st.warning("📉 Market Regime (Nifty 50): **Downtrend** (Filtering for Short setups only)")
else:
    st.info("Market Regime: Neutral")

if signals.empty:
    st.warning("No paper signals passed the current filters. Try lowering the score or scanning more symbols.")
else:
    top = signals.iloc[0]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Signals", len(signals))
    col2.metric("Top score", f"{top.score:.1f}")
    col3.metric("Strongest sector", signals.groupby("sector")["sector_score"].mean().idxmax())
    col4.metric("Avg risk", f"{signals['risk_pct'].mean():.1f}%")

    sectors = ["All"] + sorted(signals["sector"].unique().tolist())
    strategies = ["All"] + sorted(signals["strategy"].unique().tolist())
    filter_col1, filter_col2 = st.columns(2)
    selected_sector = filter_col1.selectbox("Sector", sectors)
    selected_strategy = filter_col2.selectbox("Strategy", strategies)

    filtered = signals.copy()
    if selected_sector != "All":
        filtered = filtered[filtered["sector"] == selected_sector]
    if selected_strategy != "All":
        filtered = filtered[filtered["strategy"] == selected_strategy]

    display_columns = [
        "symbol",
        "name",
        "sector",
        "strategy",
        "signal",
        "score",
        "close",
        "entry",
        "stop",
        "target",
        "risk_pct",
        "rsi_14",
        "ret_3m_pct",
        "distance_to_52w_high_pct",
        "reasons",
    ]
    st.subheader("Today's Paper Signal List")
    st.dataframe(
        filtered[display_columns],
        hide_index=True,
        width="stretch",
        column_config={
            "score": st.column_config.NumberColumn("Score", format="%.1f"),
            "risk_pct": st.column_config.NumberColumn("Risk %", format="%.2f%%"),
            "ret_3m_pct": st.column_config.NumberColumn("3M %", format="%.2f%%"),
            "distance_to_52w_high_pct": st.column_config.NumberColumn("From 52W High", format="%.2f%%"),
        },
    )

    st.download_button(
        "Download signals CSV",
        data=filtered.to_csv(index=False),
        file_name="indian_swing_paper_signals.csv",
        mime="text/csv",
    )

    st.subheader("Chart Check")
    selected_symbol = st.selectbox("Symbol", filtered["symbol"].drop_duplicates().tolist())
    if selected_symbol in histories:
        render_chart(selected_symbol, histories[selected_symbol])

with st.expander("Skipped symbols / data issues"):
    if failures:
        st.write("\n".join(failures[:80]))
    else:
        st.write("No data issues in this scan.")

st.info(
    "This dashboard is for education and paper tracking only. Signals are generated from end-of-day data and "
    "should be checked manually for liquidity, news, earnings, and personal risk limits."
)

st.divider()
st.header("Backtest")
st.caption(
    "Replays the same signal rules historically. Only takes Long trades in uptrends and Short trades in downtrends. "
    "Maximum 10 concurrent trades active at any time. Signals are generated on close, entered at the next session open, "
    "and exited at stop, 2R target, or max holding period."
)

backtest_col1, backtest_col2, backtest_col3, backtest_col4 = st.columns(4)
backtest_start = backtest_col1.date_input("Start date", value=date(2024, 1, 1))
backtest_min_score = backtest_col2.slider("Backtest min score", 50, 90, DEFAULT_MIN_SCORE, 1)
backtest_max_symbols = backtest_col3.number_input("Backtest max symbols", 5, 100, 30, 5)
backtest_max_hold = backtest_col4.number_input("Max holding days", 5, 90, 30, 5)
risk_per_trade_pct = st.slider("Risk per trade used for equity curve", 0.25, 3.0, 1.0, 0.25)
run_backtest_clicked = st.button("Run backtest from selected date", type="primary")

if run_backtest_clicked:
    with st.spinner("Running historical replay. This can take a minute while Yahoo Finance data downloads..."):
        trades, equity, metrics, backtest_failures = cached_backtest(
            backtest_start.isoformat(),
            backtest_min_score,
            int(backtest_max_symbols),
            int(backtest_max_hold),
            float(risk_per_trade_pct),
        )

    if trades.empty:
        st.warning("No historical trades matched the selected backtest settings.")
    else:
        metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)
        metric_col1.metric("Trades", f"{int(metrics['trades'])}")
        metric_col2.metric("Win rate", f"{metrics['win_rate_pct']:.1f}%")
        metric_col3.metric("Avg R", f"{metrics['avg_r']:.2f}")
        metric_col4.metric("Total R", f"{metrics['total_r']:.2f}")
        metric_col5.metric("Profit factor", f"{metrics['profit_factor']:.2f}")

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=equity["exit_date"],
                y=equity["equity_pct"],
                mode="lines",
                name="Equity %",
            )
        )
        fig.update_layout(
            height=420,
            margin=dict(l=10, r=10, t=30, b=10),
            yaxis_title="Cumulative return at selected risk/trade (%)",
        )
        st.plotly_chart(fig, width="stretch")

        st.subheader("Backtest Trade Log")
        display_backtest_columns = [
            "signal_date",
            "entry_date",
            "exit_date",
            "symbol",
            "strategy",
            "score",
            "entry",
            "planned_stop",
            "planned_target",
            "exit",
            "exit_reason",
            "return_pct",
            "r_multiple",
            "holding_days",
        ]
        st.dataframe(
            trades[display_backtest_columns],
            hide_index=True,
            width="stretch",
            column_config={
                "return_pct": st.column_config.NumberColumn("Return %", format="%.2f%%"),
                "r_multiple": st.column_config.NumberColumn("R", format="%.2f"),
            },
        )
        st.download_button(
            "Download backtest trades CSV",
            data=trades.to_csv(index=False),
            file_name="backtest_trades.csv",
            mime="text/csv",
        )

    with st.expander("Backtest skipped symbols / data issues"):
        if backtest_failures:
            st.write("\n".join(backtest_failures[:120]))
        else:
            st.write("No data issues in this backtest.")
else:
    st.write("Choose backtest settings and run the historical replay when you are ready.")
