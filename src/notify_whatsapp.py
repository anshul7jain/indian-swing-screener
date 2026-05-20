from __future__ import annotations

import json
import os
from datetime import datetime

from dotenv import load_dotenv

from .config import APP_TIMEZONE, DEFAULT_MIN_SCORE, UNIVERSE_PATH
from .data import load_universe
from .screener import screen_universe

SEND_WINDOW_START = (7, 30)
SEND_WINDOW_END = (8, 45)


def _today_label() -> str:
    try:
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo(APP_TIMEZONE))
    except Exception:  # noqa: BLE001
        now = datetime.now()
    return now.strftime("%d %b %Y")


def _now_ist() -> datetime:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(APP_TIMEZONE))
    except Exception:  # noqa: BLE001
        return datetime.now()


def inside_send_window(now: datetime | None = None) -> bool:
    now = now or _now_ist()
    current_minutes = now.hour * 60 + now.minute
    start_minutes = SEND_WINDOW_START[0] * 60 + SEND_WINDOW_START[1]
    end_minutes = SEND_WINDOW_END[0] * 60 + SEND_WINDOW_END[1]
    return start_minutes <= current_minutes <= end_minutes


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


def mask_recipient(recipient: str) -> str:
    if len(recipient) <= 6:
        return "***"
    return f"{recipient[:10]}...{recipient[-4:]}"


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
        print(f"WhatsApp dry run for {len(to_numbers)} recipient(s): {[mask_recipient(n) for n in to_numbers]}")
        print(message)
        return "dry-run"

    if missing:
        if require_config:
            raise RuntimeError(f"Missing WhatsApp environment variables: {', '.join(missing)}")
        print(f"WhatsApp config missing ({', '.join(missing)}); falling back to dry-run.")
        print(message)
        return "dry-run"

    from twilio.rest import Client

    client = Client(sid, token)
    sent_ids = []
    failures = []
    print(f"Sending WhatsApp message to {len(to_numbers)} recipient(s): {[mask_recipient(n) for n in to_numbers]}")
    for to_number in to_numbers:
        try:
            if content_sid:
                sent = client.messages.create(
                    from_=from_number,
                    to=to_number,
                    content_sid=content_sid,
                    content_variables=json.dumps({"1": message[:1500]}),
                )
            else:
                sent = client.messages.create(from_=from_number, to=to_number, body=message)
            print(f"Sent to {mask_recipient(to_number)} with SID {sent.sid}")
            sent_ids.append(sent.sid)
        except Exception as exc:  # noqa: BLE001 - keep all recipient failures visible.
            failures.append(f"{mask_recipient(to_number)}: {exc}")

    if failures:
        raise RuntimeError("WhatsApp send failed for recipient(s): " + " | ".join(failures))
    return ",".join(sent_ids)


def main() -> None:
    load_dotenv()
    enforce_send_window = os.getenv("ENFORCE_SEND_WINDOW", "false").lower() == "true"
    if enforce_send_window and not inside_send_window():
        now = _now_ist().strftime("%d %b %Y %H:%M %Z")
        print(f"Skipping scheduled WhatsApp send outside 07:30-08:45 IST window. Current time: {now}")
        return

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
