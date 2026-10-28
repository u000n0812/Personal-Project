"""Central configuration: credentials, tickers, and app-wide defaults.

Credentials are loaded from a `.env` file in the project root (see
`.env.example`). Nothing secret is ever hardcoded here.
"""

from __future__ import annotations

import os
from pathlib import Path

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
# Demo KOSPI universe for synthetic mode. Live rankings use the real top-N
# companies from the peer snapshots (PEER_TOP_N below), not this list.
# ---------------------------------------------------------------------------
SCREEN_UNIVERSE: dict[str, str] = {
    "005930": "Samsung Electronics", "000660": "SK Hynix",
    "373220": "LG Energy Solution", "207940": "Samsung Biologics",
    "005380": "Hyundai Motor", "000270": "Kia",
    "068270": "Celltrion", "035420": "NAVER",
    "005490": "POSCO Holdings", "051910": "LG Chem",
    "105560": "KB Financial Group", "055550": "Shinhan Financial Group",
    "086790": "Hana Financial Group", "316140": "Woori Financial Group",
    "035720": "Kakao", "012330": "Hyundai Mobis",
    "028260": "Samsung C&T", "006400": "Samsung SDI",
    "066570": "LG Electronics", "096770": "SK Innovation",
    "034730": "SK Inc.", "015760": "KEPCO",
    "032830": "Samsung Life Insurance", "012450": "Hanwha Aerospace",
    "329180": "HD Hyundai Heavy Industries", "009540": "HD Korea Shipbuilding",
    "042660": "Hanwha Ocean", "017670": "SK Telecom",
    "030200": "KT", "033780": "KT&G",
    "011200": "HMM", "010130": "Korea Zinc",
    "018260": "Samsung SDS", "003550": "LG Corp.",
    "259960": "Krafton", "003670": "POSCO Future M",
}

# Optional fundamentals override file (CSV or Parquet; schema in README and
# factors/definitions.py): its values replace the peer snapshot's for matching
# tickers. Relative paths resolve against the project root.
FUNDAMENTALS_PATH: str = os.getenv("FUNDAMENTALS_PATH", "data/fundamentals.csv")


def fundamentals_path() -> Path:
    path = Path(FUNDAMENTALS_PATH)
    return path if path.is_absolute() else Path(__file__).parent / path


# ---------------------------------------------------------------------------
# Company Analysis page — markets, peer snapshots
# ---------------------------------------------------------------------------
MARKETS: dict[str, dict] = {
    "KOSPI": {"currency": "KRW", "tz": "Asia/Seoul", "open": "09:00", "close": "15:30"},
    "NASDAQ": {"currency": "USD", "tz": "America/New_York", "open": "09:30", "close": "16:00"},
}
# Peers = the N largest companies by market cap in the selected company's market.
PEER_TOP_N: int = int(os.getenv("PEER_TOP_N", "300"))
SNAPSHOT_DIR: Path = Path(os.getenv("SNAPSHOT_DIR", str(Path(__file__).parent / "data" / "snapshots")))
SNAPSHOT_STALE_DAYS: int = 5  # warn when the peer snapshot is older than this

# Sector-relative ranking: sectors with fewer companies than this are ranked
# against the whole market instead (percentiles of 2–3 stocks mean little).
MIN_SECTOR_SIZE: int = 5

# ---------------------------------------------------------------------------
# Sector ETFs page. Sector keys use Yahoo's sector names so each ETF links to
# the matching stocks on the Market Leaders page.
#
# US: the Select Sector SPDRs (the standard S&P 500 sector set).
# ⚠️ KOREA: PLACEHOLDER codes (TIGER 200 sector series, tracking KOSPI 200
# sector indices) — verify each code before relying on it. The page shows
# the name each code resolves to at the data source, so a wrong code is
# visible immediately. Edit this dict to swap in your own ETFs.
# ---------------------------------------------------------------------------
SECTOR_ETFS: dict[str, dict] = {
    "NASDAQ": {
        "label": "US sectors (S&P 500)",
        "benchmark": ("SPY", "SPDR S&P 500"),
        "etfs": [
            ("Technology", "XLK", "Technology Select Sector SPDR"),
            ("Communication Services", "XLC", "Communication Services Select Sector SPDR"),
            ("Consumer Cyclical", "XLY", "Consumer Discretionary Select Sector SPDR"),
            ("Consumer Defensive", "XLP", "Consumer Staples Select Sector SPDR"),
            ("Energy", "XLE", "Energy Select Sector SPDR"),
            ("Financial Services", "XLF", "Financial Select Sector SPDR"),
            ("Healthcare", "XLV", "Health Care Select Sector SPDR"),
            ("Industrials", "XLI", "Industrial Select Sector SPDR"),
            ("Basic Materials", "XLB", "Materials Select Sector SPDR"),
            ("Real Estate", "XLRE", "Real Estate Select Sector SPDR"),
            ("Utilities", "XLU", "Utilities Select Sector SPDR"),
        ],
    },
    "KOSPI": {
        "label": "Korea sectors (KOSPI 200) — PLACEHOLDER codes",
        "benchmark": ("069500", "KODEX 200"),
        "etfs": [
            ("Technology", "139260", "TIGER 200 IT"),
            ("Financial Services", "139270", "TIGER 200 Financials"),
            ("Healthcare", "227540", "TIGER 200 Health Care"),
            ("Consumer Cyclical", "139290", "TIGER 200 Consumer Discretionary"),
            ("Consumer Defensive", "227560", "TIGER 200 Consumer Staples"),
            ("Energy", "139250", "TIGER 200 Energy & Chemicals"),
            ("Basic Materials", "139240", "TIGER 200 Steel & Materials"),
            ("Industrials", "139230", "TIGER 200 Heavy Industries"),
            ("Industrials", "139220", "TIGER 200 Construction"),
        ],
    },
}

# Leader classification defaults (percentiles within the screened universe).
LEADER_ALL_ROUND_PCT: float = 0.60   # every factor group at or above this
LEADER_STANDOUT_PCT: float = 0.95    # any single factor group at or above this
LEADER_MIN_COVERAGE: float = 0.5     # share of a group's sub-factors required

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
