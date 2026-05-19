from __future__ import annotations

import json
import os
from datetime import datetime

from dotenv import load_dotenv

from .config import APP_TIMEZONE, DEFAULT_MIN_SCORE, UNIVERSE_PATH
from .data import load_universe
from .screener import screen_universe


def _today_label() -> str:
    try:
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo(APP_TIMEZONE))
    except Exception:  # noqa: BLE001
        now = datetime.now()
    return now.strftime("%d %b %Y")


def build_message(signals, dashboard_url: str = "", max_rows: int = 8) -> str:
    title = f"Indian Swing Paper Signals - {_today_label()}"
    if signals.empty:
        lines = [title, "", "No candidates passed today's filters."]
    else:
        lines = [title, "", f"Top {min(max_rows, len(signals))} candidates:"]
        for idx, row in signals.head(max_rows).iterrows():
            lines.append(
                f"{idx + 1}. {row.symbol} | {row.strategy} | score {row.score} | "
                f"entry {row.entry} | stop {row.stop} | target {row.target}"
            )
        lines.append("")
        lines.append("Paper signals only. Validate liquidity, news, and risk before acting.")

    if dashboard_url:
        lines.extend(["", f"Dashboard: {dashboard_url}"])
    return "\n".join(lines)


def parse_recipients(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [recipient.strip() for recipient in raw.split(",") if recipient.strip()]


def send_whatsapp(message: str) -> str:
    dry_run = os.getenv("NOTIFY_DRY_RUN", "false").lower() == "true"
    require_config = os.getenv("REQUIRE_WHATSAPP_CONFIG", "false").lower() == "true"
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_WHATSAPP")
    to_numbers = parse_recipients(os.getenv("WHATSAPP_TO_NUMBER"))
    content_sid = os.getenv("TWILIO_CONTENT_SID")
    missing = [
        name
        for name, value in {
            "TWILIO_ACCOUNT_SID": sid,
            "TWILIO_AUTH_TOKEN": token,
            "TWILIO_FROM_WHATSAPP": from_number,
            "WHATSAPP_TO_NUMBER": ",".join(to_numbers),
        }.items()
        if not value
    ]

    if dry_run:
        print(message)
        return "dry-run"

    if missing:
        if require_config:
            raise RuntimeError(f"Missing WhatsApp environment variables: {', '.join(missing)}")
        print(message)
        return "dry-run"

    from twilio.rest import Client

    client = Client(sid, token)
    sent_ids = []
    for to_number in to_numbers:
        if content_sid:
            sent = client.messages.create(
                from_=from_number,
                to=to_number,
                content_sid=content_sid,
                content_variables=json.dumps({"1": message[:1500]}),
            )
        else:
            sent = client.messages.create(from_=from_number, to=to_number, body=message)
        sent_ids.append(sent.sid)
    return ",".join(sent_ids)


def main() -> None:
    load_dotenv()
    min_score = float(os.getenv("SCREENER_MIN_SCORE", DEFAULT_MIN_SCORE))
    max_symbols_raw = os.getenv("SCREENER_MAX_SYMBOLS", "").strip()
    max_symbols = int(max_symbols_raw) if max_symbols_raw else None
    dashboard_url = os.getenv("DASHBOARD_URL", "").strip()

    universe = load_universe(UNIVERSE_PATH)
    signals, _, failures = screen_universe(universe, min_score=min_score, max_symbols=max_symbols)
    if failures:
        print(f"Skipped {len(failures)} symbols. First few: {failures[:5]}")

    message = build_message(signals, dashboard_url=dashboard_url)
    result = send_whatsapp(message)
    print(f"WhatsApp notification result: {result}")


if __name__ == "__main__":
    main()
