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

The app supports two WhatsApp paths:

- A **Send test WhatsApp** button inside the Streamlit dashboard.
- An automatic **8 AM IST** weekday notification through GitHub Actions.

Both use Twilio WhatsApp.

### 1. Create Twilio WhatsApp Sandbox

1. Create or open a Twilio account.
2. Go to Twilio Console -> Messaging -> Try it out -> Send a WhatsApp message.
3. Open the WhatsApp Sandbox instructions.
4. Join the sandbox from your phone by scanning the QR code or sending the displayed `join ...` message to Twilio's sandbox WhatsApp number.
5. Copy your Account SID and Auth Token from Twilio Console.

For sandbox testing, your phone must join the sandbox first. For production, use an approved WhatsApp sender/template as required by WhatsApp/Twilio.

### 2. Add Streamlit Secrets For Manual App Test

In Streamlit Cloud, open the app settings and add these secrets:

```toml
TWILIO_ACCOUNT_SID = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
TWILIO_AUTH_TOKEN = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
TWILIO_FROM_WHATSAPP = "whatsapp:+14155238886"
WHATSAPP_TO_NUMBER = "whatsapp:+91XXXXXXXXXX"
DASHBOARD_URL = "https://your-app-name.streamlit.app"
```

For multiple recipients, put all numbers in `WHATSAPP_TO_NUMBER`, separated by commas:

```toml
WHATSAPP_TO_NUMBER = "whatsapp:+91XXXXXXXXXX,whatsapp:+91YYYYYYYYYY,whatsapp:+91ZZZZZZZZZZ"
```

Then redeploy/reboot the app and click **Send test WhatsApp** in the sidebar.

### 3. Add GitHub Secrets For 8 AM Notification

Streamlit Cloud is not a reliable cron runner, so the repo includes a GitHub Actions workflow:

`.github/workflows/morning_whatsapp.yml`

It runs at **02:30 UTC / 08:00 IST**, Monday to Friday.

Because GitHub scheduled workflows are best-effort and may drift, the workflow also has a fallback schedule and the Python job only sends scheduled messages during the **07:30-08:45 IST** window. Manual **Run workflow** executions are not blocked by this window.

Create these GitHub repository secrets:

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_WHATSAPP`, for example `whatsapp:+14155238886` for Twilio sandbox
- `WHATSAPP_TO_NUMBER`, for example `whatsapp:+91XXXXXXXXXX,whatsapp:+91YYYYYYYYYY`
- `DASHBOARD_URL`, your Streamlit app URL
- `TWILIO_CONTENT_SID`, optional for production template messages

Optional repository variables:

- `SCREENER_MIN_SCORE`, default `65`
- `SCREENER_MAX_SYMBOLS`, blank means full universe

To test immediately, go to GitHub -> Actions -> Morning WhatsApp Signals -> Run workflow.

### Production Template Note

For a real production WhatsApp sender, Meta/Twilio may require an approved template for business-initiated morning messages. Create a Twilio Content Template such as:

```text
Daily swing screener update:
{{1}}
```

After approval, add its Content SID as `TWILIO_CONTENT_SID`. If `TWILIO_CONTENT_SID` is blank, the app sends a normal text body, which is best for sandbox testing.

## Signal Notes

The screener uses end-of-day data, not live intraday ticks. Treat every row as a paper-trading candidate that still needs manual review for liquidity, news, earnings, market regime, and position sizing.
