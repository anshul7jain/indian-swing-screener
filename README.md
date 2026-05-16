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

## Deploy Dashboard To Streamlit Cloud

1. Push this folder to a GitHub repository.
2. Go to Streamlit Cloud and create a new app.
3. Select the repo, branch, and `app.py` as the main file.
4. Deploy.

The dashboard does not need WhatsApp secrets unless you also want to reuse the repo secrets for notifications.

## WhatsApp Notification At 8 AM IST

Streamlit Cloud is not a reliable cron runner, so the repo includes a GitHub Actions workflow:

`.github/workflows/morning_whatsapp.yml`

It runs at **02:30 UTC / 08:00 IST**, Monday to Friday.

### Twilio Setup

Create these GitHub repository secrets:

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_WHATSAPP`, for example `whatsapp:+14155238886` for Twilio sandbox
- `WHATSAPP_TO_NUMBER`, for example `whatsapp:+91XXXXXXXXXX`
- `DASHBOARD_URL`, your Streamlit app URL

Optional repository variables:

- `SCREENER_MIN_SCORE`, default `65`
- `SCREENER_MAX_SYMBOLS`, blank means full universe

For Twilio sandbox testing, your phone must join the sandbox first. For production, use an approved WhatsApp sender/template as required by WhatsApp/Twilio.

## Signal Notes

The screener uses end-of-day data, not live intraday ticks. Treat every row as a paper-trading candidate that still needs manual review for liquidity, news, earnings, market regime, and position sizing.

