"""Thin PyKis client wrapper with caching and a synthetic fallback.

Public API (everything the pages use):

- ``get_holdings(mode)``            → account snapshot DataFrame
- ``get_ohlcv(ticker, start, end, mode)`` → daily OHLCV (+``carry``) DataFrame
- ``get_daily_nav(mode)``           → account NAV series (best effort)
- ``build_close_panel(history)``    → aligned wide close-price DataFrame
- ``align_history(history, index)`` → per-ticker frames on a shared calendar

``mode`` is ``"live"`` or ``"synthetic"`` and is part of every cache key, so
flipping the sidebar toggle never serves stale data from the other mode. All
fetches are cached with ``st.cache_data`` to stay under KIS rate limits.

Missing-data policy (explicit): series are aligned on the *union* of trading
days, forward-filled across gaps of at most ``config.MAX_FFILL_DAYS`` days;
longer gaps and pre-listing history stay NaN and the backtest engine treats
those days as non-investable.

NOTE on live mode: the calls below target python-kis v2.x. Attribute names on
balance/chart objects vary slightly between releases, so the accessors are
defensive (`_first_attr`). If your pykis version differs, this module is the
only place to adjust.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

import config
from data import synthetic

# ---------------------------------------------------------------------------
# Mode handling
# ---------------------------------------------------------------------------


def resolve_mode() -> str:
    """Pick the data source for this rerun.

    Synthetic when credentials are missing, when the user forces it via the
    sidebar toggle, or after a live call has already failed this session.
    """
    if st.session_state.get("force_synthetic", False):
        return "synthetic"
    if st.session_state.get("live_failed", False):
        return "synthetic"
    return "live" if config.has_credentials() else "synthetic"


def _mark_live_failed(err: Exception) -> None:
    st.session_state["live_failed"] = True
    st.warning(
        f"Live KIS call failed — falling back to synthetic data for this "
        f"session. ({type(err).__name__}: {err})"
    )


# ---------------------------------------------------------------------------
# Live PyKis implementation
# ---------------------------------------------------------------------------


@st.cache_resource(show_spinner="Connecting to KIS…")
def _kis_client() -> Any:
    """One PyKis session per Streamlit process."""
    from pykis import PyKis  # imported lazily: optional dependency

    return PyKis(
        id=config.KIS_ID or None,
        account=config.ACCOUNT_NO,
        appkey=config.APP_KEY,
        secretkey=config.APP_SECRET,
        keep_token=True,
    )


def _first_attr(obj: Any, *names: str, default: Any = None) -> Any:
    """Return the first attribute present on ``obj`` — pykis versions rename
    fields between releases, so we probe a small list of known spellings."""
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return default


@st.cache_data(ttl=120, show_spinner="Fetching holdings…")
def _live_holdings() -> pd.DataFrame:
    balance = _kis_client().account().balance()
    rows = []
    for stock in _first_attr(balance, "stocks", "positions", default=[]):
        rows.append(
            {
                "ticker": str(_first_attr(stock, "symbol", "ticker", "code", default="")),
                "name": str(_first_attr(stock, "name", default="")),
                "quantity": float(_first_attr(stock, "qty", "quantity", default=0)),
                "avg_price": float(
                    _first_attr(stock, "purchase_price", "avg_price", "purchase_amount", default=0)
                ),
                "current_price": float(_first_attr(stock, "price", "current_price", default=0)),
            }
        )
    return pd.DataFrame(rows)


@st.cache_data(ttl=600, show_spinner=False)
def _live_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    chart = _kis_client().stock(ticker).chart(
        start=pd.Timestamp(start).date(), end=pd.Timestamp(end).date(), period="day"
    )
    if hasattr(chart, "df"):
        df = chart.df()
    else:  # older releases: iterate bars
        df = pd.DataFrame(
            [
                {
                    "time": _first_attr(bar, "time", "date"),
                    "open": bar.open, "high": bar.high,
                    "low": bar.low, "close": bar.close,
                    "volume": _first_attr(bar, "volume", default=0),
                }
                for bar in _first_attr(chart, "bars", default=[])
            ]
        )
    df.columns = [str(c).lower() for c in df.columns]
    time_col = next(c for c in ("time", "date", "datetime") if c in df.columns)
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.set_index(time_col).sort_index()
    df.index = df.index.tz_localize(None).normalize()
    df.index.name = "date"
    return df[["open", "high", "low", "close", "volume"]].astype(float)


@st.cache_data(ttl=600, show_spinner=False)
def _live_daily_nav() -> pd.Series:
    """Account NAV history. KIS exposes this only via the period-profit
    endpoint, which python-kis wraps differently across versions — probe the
    common spellings and give up gracefully."""
    account = _kis_client().account()
    for name in ("profits", "period_profit", "daily_profits"):
        if hasattr(account, name):
            records = getattr(account, name)()
            rows = {
                pd.Timestamp(_first_attr(r, "time", "date")): float(
                    _first_attr(r, "amount", "eval_amount", "total", default="nan")
                )
                for r in _first_attr(records, "profits", "items", default=records or [])
            }
            if rows:
                return pd.Series(rows).sort_index().rename("nav")
    raise NotImplementedError(
        "Daily NAV endpoint not found on this pykis version — see data/client.py"
    )


# ---------------------------------------------------------------------------
# Synthetic implementation (cached thin wrappers)
# ---------------------------------------------------------------------------


@st.cache_data(ttl=3600, show_spinner=False)
def _synthetic_holdings(as_of: str) -> pd.DataFrame:
    return synthetic.generate_holdings(pd.Timestamp(as_of))


@st.cache_data(ttl=3600, show_spinner=False)
def _synthetic_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    return synthetic.generate_ohlcv(ticker, pd.Timestamp(start), pd.Timestamp(end))


# ---------------------------------------------------------------------------
# Public dispatchers
# ---------------------------------------------------------------------------


def _today() -> str:
    return pd.Timestamp.today().normalize().isoformat()


def get_holdings(mode: str) -> pd.DataFrame:
    """Current account holdings: ticker, name, quantity, avg/current price."""
    if mode == "live":
        try:
            df = _live_holdings()
            if not df.empty:
                return df
            st.info("Live account returned no holdings — showing synthetic sample.")
        except Exception as err:  # noqa: BLE001 — any API failure degrades to demo
            _mark_live_failed(err)
    return _synthetic_holdings(_today())


def get_ohlcv(ticker: str, start: pd.Timestamp, end: pd.Timestamp, mode: str) -> pd.DataFrame:
    """Daily OHLCV for one ticker (synthetic frames also carry a ``carry`` column)."""
    start_s, end_s = pd.Timestamp(start).isoformat(), pd.Timestamp(end).isoformat()
    if mode == "live":
        try:
            return _live_ohlcv(ticker, start_s, end_s)
        except Exception as err:  # noqa: BLE001
            _mark_live_failed(err)
    return _synthetic_ohlcv(ticker, start_s, end_s)


def get_daily_nav(mode: str) -> pd.Series | None:
    """Account NAV series; ``None`` when unavailable (page hides the section)."""
    if mode == "live":
        try:
            return _live_daily_nav()
        except Exception as err:  # noqa: BLE001
            _mark_live_failed(err)
    return None


# ---------------------------------------------------------------------------
# Alignment helpers (the explicit missing-data policy lives here)
# ---------------------------------------------------------------------------


def build_close_panel(history: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Wide close-price panel (dates × tickers) on the union of trading days.

    Gaps up to ``config.MAX_FFILL_DAYS`` are forward-filled; anything longer,
    and days before a ticker's first print, remain NaN on purpose.
    """
    closes = pd.DataFrame({t: df["close"] for t, df in history.items()})
    closes = closes.sort_index()
    return closes.ffill(limit=config.MAX_FFILL_DAYS)


def align_history(
    history: dict[str, pd.DataFrame], index: pd.DatetimeIndex
) -> dict[str, pd.DataFrame]:
    """Reindex each per-ticker frame onto a shared trading calendar so
    strategy signals come out on identical indexes."""
    return {
        t: df.reindex(index).ffill(limit=config.MAX_FFILL_DAYS)
        for t, df in history.items()
    }
