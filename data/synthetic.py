"""Deterministic synthetic market data.

Lets the whole app run before any API keys exist. Every series is seeded from
the ticker string, so reruns (and Streamlit cache misses) always produce the
same data. A small fraction of trading days is deliberately dropped from each
series so the alignment / missing-data handling in the rest of the app is
exercised for real.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

# Synthetic KOSPI-style holdings used when no live account is available.
# (ticker, name, quantity) — prices are derived from the generated series.
_SYNTHETIC_POSITIONS: list[tuple[str, str, int]] = [
    ("005930", "Samsung Electronics", 120),
    ("000660", "SK Hynix", 35),
    ("035420", "NAVER", 22),
    ("005380", "Hyundai Motor", 18),
    ("051910", "LG Chem", 9),
    ("105560", "KB Financial Group", 40),
    ("005490", "POSCO Holdings", 12),
    ("035720", "Kakao", 55),
    ("068270", "Celltrion", 15),
]

_MISSING_RATE = 0.005  # fraction of trading days dropped per ticker


def _seed(ticker: str, salt: str = "") -> int:
    digest = hashlib.sha256(f"{ticker}:{salt}".encode()).hexdigest()
    return int(digest[:8], 16)


def _base_price(ticker: str) -> float:
    """A plausible KRW price level, stable per ticker (₩5,000–₩150,000)."""
    rng = np.random.default_rng(_seed(ticker, "level"))
    return float(rng.uniform(5_000, 150_000))


def generate_ohlcv(ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Generate a daily OHLCV DataFrame for one ticker.

    Returns columns ``open/high/low/close/volume`` plus a synthetic ``carry``
    column (annualized roll-yield proxy) indexed by trading day. A few days
    are randomly dropped to simulate exchange holidays / halts.
    """
    days = pd.bdate_range(start, end)
    n = len(days)
    rng = np.random.default_rng(_seed(ticker, "path"))

    # Geometric random walk with a mild, ticker-specific drift and vol.
    drift = rng.normal(0.04, 0.06) / 252.0
    vol = rng.uniform(0.15, 0.35) / np.sqrt(252.0)
    rets = rng.normal(drift, vol, n)
    close = _base_price(ticker) * np.exp(np.cumsum(rets))

    gap = rng.normal(0.0, vol * 0.4, n)
    open_ = np.roll(close, 1) * (1 + gap)
    open_[0] = close[0]
    span = np.abs(rng.normal(0.0, vol, n))
    high = np.maximum(open_, close) * (1 + span)
    low = np.minimum(open_, close) * (1 - span)
    volume = np.exp(rng.normal(12.5, 0.6, n)).astype(np.int64)

    # Slow AR(1) carry proxy (annualized roll yield, roughly ±8%).
    carry = np.empty(n)
    carry[0] = rng.normal(0.0, 0.03)
    shocks = rng.normal(0.0, 0.004, n)
    for i in range(1, n):  # tiny series; clarity beats vectorizing here
        carry[i] = 0.985 * carry[i - 1] + shocks[i]

    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "volume": volume, "carry": carry},
        index=days,
    )
    df.index.name = "date"

    # Drop a deterministic sprinkling of days → downstream code must align.
    if n > 40:
        drop = rng.random(n) < _MISSING_RATE
        drop[0] = drop[-1] = False
        df = df.loc[~drop]
    return df


def generate_holdings(as_of: pd.Timestamp) -> pd.DataFrame:
    """Synthetic account snapshot mirroring what PyKis balance returns.

    Average price is taken from the same synthetic price path ~6 months back,
    so unrealized P/L is internally consistent with the charts.
    """
    start = as_of - pd.Timedelta(days=400)
    rows = []
    for ticker, name, qty in _SYNTHETIC_POSITIONS:
        prices = generate_ohlcv(ticker, start, as_of)["close"]
        rng = np.random.default_rng(_seed(ticker, "avg"))
        anchor = prices.iloc[max(len(prices) - 126, 0)]
        rows.append(
            {
                "ticker": ticker,
                "name": name,
                "quantity": qty,
                "avg_price": float(anchor * rng.uniform(0.92, 1.08)),
                "current_price": float(prices.iloc[-1]),
            }
        )
    return pd.DataFrame(rows)
