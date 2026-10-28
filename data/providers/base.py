"""Provider interface for the Company Analysis page.

A provider supplies four things for a market ("KOSPI" | "NASDAQ"):

- ``listing(market)``           → DataFrame[ticker, name, market_cap], largest first
- ``company(ticker, market)``   → CompanyData (profile + factor inputs)
- ``closes(tickers, market, start)`` → dates × tickers adjusted closes
- ``quote(ticker, market)``     → Quote (latest price + timestamp)
- ``security_names(tickers, market)`` → {ticker: name at the source}

Factor inputs follow ``factors.definitions.FUNDAMENTAL_COLUMNS`` (fractions).
To add a data vendor, implement these four methods and register the class in
``data.providers.PROVIDERS`` — nothing else changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Protocol
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

import config


@dataclass
class Quote:
    price: float
    prev_close: float
    as_of: datetime            # tz-aware timestamp of the price
    source: str                # e.g. "KIS", "Yahoo Finance", "Synthetic"
    currency: str

    @property
    def change(self) -> float:
        if not self.prev_close or np.isnan(self.prev_close):
            return float("nan")
        return self.price / self.prev_close - 1.0


@dataclass
class CompanyData:
    ticker: str
    market: str
    name: str
    sector: str = ""
    industry: str = ""
    currency: str = ""
    market_cap: float = float("nan")
    metrics: dict[str, float] = field(default_factory=dict)  # FUNDAMENTAL_COLUMNS
    notes: dict[str, str] = field(default_factory=dict)      # per-input provenance


class Provider(Protocol):
    name: str

    def listing(self, market: str) -> pd.DataFrame: ...
    def company(self, ticker: str, market: str) -> CompanyData: ...
    def closes(self, tickers: list[str], market: str, start: pd.Timestamp) -> pd.DataFrame: ...
    def quote(self, ticker: str, market: str) -> Quote: ...
    def security_names(self, tickers: list[str], market: str) -> dict[str, str]: ...


def _session(market: str) -> tuple[ZoneInfo, time, time]:
    m = config.MARKETS[market]
    return (ZoneInfo(m["tz"]), time.fromisoformat(m["open"]), time.fromisoformat(m["close"]))


def session_close(day: pd.Timestamp, market: str) -> datetime:
    """Tz-aware closing time of ``day`` on ``market`` (stamps daily bars)."""
    tz, _, close = _session(market)
    return datetime.combine(pd.Timestamp(day).date(), close, tzinfo=tz)


def describe_freshness(as_of: datetime, market: str, now: datetime) -> tuple[str, str]:
    """Classify how current a quote is, from its timestamp alone.

    Returns ``(level, label)``: level is "live" | "delayed" | "close".
    Exchange holidays aren't modelled; a holiday reads as "previous close",
    which is what the data is.
    """
    tz, open_t, close_t = _session(market)
    now_l, as_l = now.astimezone(tz), as_of.astimezone(tz)
    in_session = now_l.weekday() < 5 and open_t <= now_l.time() <= close_t
    if in_session and as_l.date() == now_l.date():
        lag_min = max((now_l - as_l).total_seconds() / 60.0, 0.0)
        stamp = as_l.strftime("%H:%M %Z")
        if lag_min <= 3:
            return "live", f"Real-time · {stamp}"
        return "delayed", f"Intraday · {stamp} (~{lag_min:.0f} min delayed)"
    if as_l.date() == now_l.date():
        return "close", f"Today's close · {as_l:%b %d}"
    return "close", f"Previous close · {as_l:%a %b %d}"
