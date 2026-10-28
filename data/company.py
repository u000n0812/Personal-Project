"""Streamlit-facing access layer for the Company Analysis page.

Adds caching, the KIS real-time quote override, and the fallback policy on
top of ``data.providers`` and ``data.snapshot``:

* Source: Yahoo (free, no keys) unless "Force synthetic data" is on.
  If the public sources can't be reached at all (listing fetch fails),
  the page falls back to synthetic data and says so.
* Quotes: KIS when API keys are configured (real-time), else Yahoo.
* A failed fetch for the *selected* company is reported, never replaced
  with synthetic numbers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import config
from data import client, snapshot
from data.fundamentals import OverrideInfo, apply_overrides
from data.providers import CompanyData, Quote, get_provider

QUOTE_TTL = 60            # seconds — live price refresh
COMPANY_TTL = 6 * 3600    # fundamentals change slowly
LISTING_TTL = 24 * 3600


@st.cache_resource(show_spinner=False)
def provider(name: str):
    return get_provider(name)


@st.cache_data(ttl=LISTING_TTL, show_spinner="Loading listings…")
def listing(source: str, market: str) -> pd.DataFrame:
    return provider(source).listing(market)


@st.cache_data(ttl=COMPANY_TTL, show_spinner="Fetching fundamentals…")
def company(source: str, ticker: str, market: str) -> CompanyData:
    return provider(source).company(ticker, market)


@st.cache_data(ttl=COMPANY_TTL, show_spinner=False)
def history(source: str, ticker: str, market: str) -> pd.Series:
    start = pd.Timestamp.today().normalize() - pd.Timedelta(days=snapshot.PRICE_HISTORY_DAYS)
    return provider(source).closes([ticker], market, start)[ticker].dropna()


def _kis_quote(ticker: str, market: str) -> Quote:
    """Real-time quote from KIS (domestic or overseas). Attribute names are
    probed defensively — python-kis renames fields between releases."""
    kis = client._kis_client()
    stock = kis.stock(ticker, market="KRX" if market == "KOSPI" else "NASDAQ")
    q = stock.quote()
    price = float(client._first_attr(q, "price", "close"))
    prev = client._first_attr(q, "prev_price", "base", "prev_close", "previous_close")
    stamp = client._first_attr(q, "time", "timestamp")
    as_of = pd.Timestamp(stamp).to_pydatetime() if stamp is not None else datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    return Quote(price=price, prev_close=float(prev) if prev is not None else np.nan,
                 as_of=as_of, source="KIS", currency=config.MARKETS[market]["currency"])


@st.cache_data(ttl=QUOTE_TTL, show_spinner=False)
def quote(source: str, ticker: str, market: str) -> Quote:
    """Latest price: KIS real-time if configured, else the source's quote."""
    if source != "synthetic" and config.has_credentials():
        try:
            return _kis_quote(ticker, market)
        except Exception:  # noqa: BLE001 — fall through to the free quote
            pass
    return provider(source).quote(ticker, market)


# ---------------------------------------------------------------------------
# Peer snapshots
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def _load_snapshot(path: str, mtime: float) -> tuple[pd.DataFrame, dict]:
    return snapshot.load(Path(path))


@st.cache_data(ttl=3600, show_spinner="Building synthetic peers…")
def _synthetic_snapshot(market: str) -> tuple[pd.DataFrame, dict]:
    return snapshot.build(provider("synthetic"), market, top_n=10_000)


def peers(source: str, market: str) -> tuple[pd.DataFrame, dict] | None:
    """Latest peer snapshot for ``market``; None if none has been built yet."""
    if source == "synthetic":
        return _synthetic_snapshot(market)
    path = snapshot.latest_path(market)
    if path is None:
        return None
    return _load_snapshot(str(path), path.stat().st_mtime)


def market_universe(source: str, market: str) -> tuple[pd.DataFrame, dict, OverrideInfo] | None:
    """Peer snapshot with fundamentals-file overrides applied and a ``market``
    column — the one universe every page ranks against."""
    snap = peers(source, market)
    if snap is None:
        return None
    frame, meta = snap
    info = OverrideInfo()
    if source != "synthetic":  # never mix real overrides into demo data
        frame, info = apply_overrides(frame)
    frame = frame.assign(market=market)
    if "name_local" not in frame.columns:  # snapshots built before name_local existed
        frame["name_local"] = frame["name"]
    return frame, meta, info


# ---------------------------------------------------------------------------
# Sector ETFs
# ---------------------------------------------------------------------------


@st.cache_data(ttl=3600, show_spinner="Fetching ETF prices…")
def etf_closes(source: str, tickers: tuple[str, ...], market: str, years: int = 3) -> pd.DataFrame:
    start = pd.Timestamp.today().normalize() - pd.DateOffset(years=years, days=10)
    close = provider(source).closes(list(tickers), market, start)
    if close.dropna(how="all").empty:
        raise LookupError(f"No ETF prices returned for {market}")
    return close.ffill(limit=config.MAX_FFILL_DAYS)


@st.cache_data(ttl=LISTING_TTL, show_spinner=False)
def security_names(source: str, tickers: tuple[str, ...], market: str) -> dict[str, str]:
    """Names as the data source knows them — shown next to configured labels
    so a mistyped ETF code is obvious."""
    try:
        return provider(source).security_names(list(tickers), market)
    except Exception:  # noqa: BLE001 — names are a nice-to-have
        return {}


def rebuild_peers(market: str, progress) -> dict:
    """Build + save a fresh Yahoo snapshot, reporting to a st.progress bar."""
    def on_progress(done: int, total: int, ticker: str) -> None:
        progress.progress(done / total, text=f"{market}: {done}/{total} · {ticker}")

    frame, meta = snapshot.build(provider("yahoo"), market, config.PEER_TOP_N,
                                 on_progress=on_progress)
    snapshot.save(frame, meta)
    _load_snapshot.clear()
    return meta


def snapshot_age_days(meta: dict) -> int | None:
    if not meta.get("price_date"):
        return None
    return (pd.Timestamp.today().normalize() - pd.Timestamp(meta["price_date"])).days
