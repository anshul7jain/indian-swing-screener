# Indian Swing Screener

Streamlit dashboard for Indian stock swing-trading watchlists with paper-only signals and an optional WhatsApp morning summary.

The app scans an editable NSE universe, computes daily trend/momentum indicators from Yahoo Finance, and produces two non-execution signal types:

- **Sector Momentum Breakout**: strong sector, uptrend, near 52-week high, possible 20-day breakout.
- **Trend Pullback Continuation**: strong uptrend, pullback near the 20 EMA, early bounce confirmation.

This is not a broker bot. It does not place orders.

## Run Locally

```bash
cd indian-swing-screener
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Edit `data/universe.csv` to change the stock universe.

## Backtest

The dashboard includes a historical backtest panel. It replays the same screener rules from a selected start date, such as `2024-01-01`, using Yahoo Finance daily candles.

Backtest assumptions:

- Signals are generated from the daily close.
- Entries are simulated at the next trading session's open.
- Exits happen at the planned stop, 2R target, or the selected max holding period.
- If stop and target are both touched on the same candle, the backtest assumes the stop was hit first.
- Only one paper trade per symbol can be active at a time.
- Brokerage, taxes, slippage, liquidity filters, and position sizing limits are not included yet.

## Deploy Dashboard To Streamlit Cloud

1. Push this folder to a GitHub repository.
2. Go to Streamlit Cloud and create a new app.
3. Select the repo, branch, and `app.py` as the main file.
4. Deploy.

The dashboard does not need WhatsApp secrets unless you also want to reuse the repo secrets for notifications.

## WhatsApp Setup

The app supports two Telegram notification paths:

- A **Send test Telegram** button inside the Streamlit dashboard.
- An automatic **8 AM IST** weekday notification through GitHub Actions.

Both use the Telegram HTTP API.

### 1. Create a Telegram Bot

1. Open Telegram and search for `@BotFather`.
2. Send the `/newbot` command and follow the instructions to create your bot.
3. Once created, BotFather will give you a **Bot Token**. Save this token.
4. Start a conversation with your new bot and send it a message (e.g., "/start").
5. Find your `chat_id`. You can do this by forwarding a message from yourself to `@userinfobot` or by hitting `https://api.telegram.org/bot<YourBotToken>/getUpdates` in your browser.

### 2. Add Streamlit Secrets For Manual App Test

In Streamlit Cloud, open the app settings and add these secrets:

```toml
TELEGRAM_BOT_TOKEN = "your_bot_token_here"
TELEGRAM_CHAT_ID = "your_chat_id_here"
DASHBOARD_URL = "https://your-app-name.streamlit.app"
```

For multiple recipients, put all chat IDs in `TELEGRAM_CHAT_ID`, separated by commas:

```toml
TELEGRAM_CHAT_ID = "12345678,87654321"
```

Then redeploy/reboot the app and click **Send test Telegram** in the sidebar.

### 3. Add GitHub Secrets For 8 AM Notification

Streamlit Cloud is not a reliable cron runner, so the repo includes a GitHub Actions workflow:

`.github/workflows/morning_telegram.yml`

It runs at **02:30 UTC / 08:00 IST**, Monday to Friday.

Because GitHub scheduled workflows are best-effort and may drift, the workflow also has a fallback schedule and the Python job only sends scheduled messages during the **07:30-08:45 IST** window. Manual **Run workflow** executions are not blocked by this window.

Create these GitHub repository secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `DASHBOARD_URL`, your Streamlit app URL

Optional repository variables:

- `SCREENER_MIN_SCORE`, default `65`
- `SCREENER_MAX_SYMBOLS`, blank means full universe

To test immediately, go to GitHub -> Actions -> Morning Telegram Signals -> Run workflow.

## Signal Notes

The screener uses end-of-day data, not live intraday ticks. Treat every row as a paper-trading candidate that still needs manual review for liquidity, news, earnings, market regime, and position sizing.
