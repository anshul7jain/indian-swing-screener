from __future__ import annotations

from pathlib import Path

APP_NAME = "Indian Swing Screener"
APP_TIMEZONE = "Asia/Kolkata"
DEFAULT_PERIOD = "18mo"
DEFAULT_MIN_SCORE = 80
DEFAULT_MAX_SYMBOLS = 200

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
UNIVERSE_PATH = DATA_DIR / "universe.csv"

REQUIRED_UNIVERSE_COLUMNS = {"symbol", "name", "sector"}


def normalize_nse_symbol(symbol: str) -> str:
    """Return a Yahoo Finance NSE symbol for a plain NSE ticker."""
    cleaned = str(symbol).strip().upper()
    if cleaned.startswith("^") or "." in cleaned:
        return cleaned
    return f"{cleaned}.NS"

