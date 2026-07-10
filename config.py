"""Central configuration: credentials, tickers, and app-wide defaults.

Credentials are loaded from a `.env` file in the project root (see
`.env.example`). Nothing secret is ever hardcoded here.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# KIS Open API credentials — set these in `.env`, never in code.
# ---------------------------------------------------------------------------
APP_KEY: str = os.getenv("APP_KEY", "")
APP_SECRET: str = os.getenv("APP_SECRET", "")
ACCOUNT_NO: str = os.getenv("ACCOUNT_NO", "")  # e.g. "12345678-01"
KIS_ID: str = os.getenv("KIS_ID", "")  # HTS login id (python-kis needs it)


def has_credentials() -> bool:
    """True when every credential needed for live PyKis access is present."""
    return bool(APP_KEY and APP_SECRET and ACCOUNT_NO)


# ---------------------------------------------------------------------------
# ⚠️  PLACEHOLDER ETF UNIVERSE — replace with your own tickers.
#
# These are examples of Korean-listed commodity ETFs so the app has something
# to render in synthetic mode. Verify each code before trading against it, or
# simply swap in your own list — this dict is the ONLY place the universe is
# defined; every page reads from it.
# ---------------------------------------------------------------------------
COMMODITY_ETFS: dict[str, str] = {
    "132030": "KODEX Gold Futures(H) — PLACEHOLDER",
    "144600": "KODEX Silver Futures(H) — PLACEHOLDER",
    "130680": "TIGER Crude Oil Futures Enhanced(H) — PLACEHOLDER",
    "138910": "KODEX Copper Futures(H) — PLACEHOLDER",
    "137610": "TIGER Agriculture Futures Enhanced(H) — PLACEHOLDER",
}

# ---------------------------------------------------------------------------
# App-wide defaults
# ---------------------------------------------------------------------------
TRADING_DAYS_PER_YEAR: int = 252
DEFAULT_LOOKBACK: int = 120          # trading days
DEFAULT_COST_BPS: float = 10.0       # one-way transaction cost
DEFAULT_HISTORY_YEARS: int = 5
MOMENTUM_WINDOWS: tuple[int, ...] = (20, 60, 120, 252)

# Missing-data policy: forward-fill prices across gaps of at most this many
# trading days (short halts / single holidays). Longer gaps stay NaN and the
# backtest engine treats the asset as non-investable on those days.
MAX_FFILL_DAYS: int = 5
