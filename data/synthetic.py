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

# Demo NASDAQ universe for the Company Analysis page in synthetic mode.
SYNTHETIC_NASDAQ: dict[str, str] = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA", "AMZN": "Amazon",
    "GOOGL": "Alphabet", "META": "Meta Platforms", "AVGO": "Broadcom",
    "TSLA": "Tesla", "COST": "Costco", "NFLX": "Netflix", "AMD": "AMD",
    "PEP": "PepsiCo", "ADBE": "Adobe", "CSCO": "Cisco", "QCOM": "Qualcomm",
    "INTC": "Intel", "TXN": "Texas Instruments", "AMGN": "Amgen",
    "INTU": "Intuit", "ISRG": "Intuitive Surgical", "BKNG": "Booking Holdings",
    "HON": "Honeywell", "AMAT": "Applied Materials", "SBUX": "Starbucks",
    "MDLZ": "Mondelez", "GILD": "Gilead Sciences", "ADP": "ADP",
    "VRTX": "Vertex Pharmaceuticals", "REGN": "Regeneron", "LRCX": "Lam Research",
    "PANW": "Palo Alto Networks", "MU": "Micron", "ADI": "Analog Devices",
    "KLAC": "KLA", "SNPS": "Synopsys", "CDNS": "Cadence", "MELI": "MercadoLibre",
    "PYPL": "PayPal", "ASML": "ASML", "PDD": "PDD Holdings",
}

SYNTHETIC_SECTORS = ("Technology", "Financial Services", "Healthcare",
                     "Consumer Cyclical", "Industrials", "Communication Services")


def synthetic_sector(ticker: str) -> str:
    """Deterministic demo sector so sector ranks have something to group by."""
    return SYNTHETIC_SECTORS[_seed(ticker, "sector") % len(SYNTHETIC_SECTORS)]


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


_FUNDAMENTAL_MISSING_RATE = 0.04  # per value — exercises the coverage rule


def generate_fundamentals(tickers: list[str]) -> pd.DataFrame:
    """Synthetic fundamentals/consensus metrics, one row per ticker.

    Driven by three latent traits per company (quality, growth, cheapness —
    cheapness mildly anti-correlated with growth, as in real markets) plus
    noise, so factor groups are internally coherent. Units follow
    ``factors.definitions``: fractions, pp changes as fractions.
    """
    rows = {}
    for ticker in tickers:
        rng = np.random.default_rng(_seed(ticker, "fundamentals"))
        quality, growth = rng.normal(size=2)
        cheap = rng.normal() - 0.3 * growth

        def noise(scale: float) -> float:
            return float(rng.normal(0.0, scale))

        roe = 0.09 + 0.05 * quality + noise(0.03)
        row = {
            "earnings_yield": 0.07 + 0.03 * cheap + 0.01 * quality + noise(0.02),
            "dividend_yield": max(0.0, 0.02 + 0.01 * cheap + noise(0.008)),
            "book_to_market": float(np.exp(np.log(0.9) + 0.4 * cheap + noise(0.3))),
            "cash_flow_yield": 0.09 + 0.04 * cheap + 0.02 * quality + noise(0.03),
            "fwd_revenue_revision": 0.01 + 0.03 * growth + noise(0.02),
            "fwd_op_margin_change": 0.004 * growth + noise(0.008),
            "fwd_eps_growth": 0.08 + 0.15 * growth + noise(0.10),
            "payout_ratio": float(np.clip(0.3 + 0.1 * cheap + noise(0.1), 0.0, 0.9)),
            "roe": roe,
            "eps_revision_1m": 0.01 * growth + noise(0.02),
            "foreign_own_chg_3m": 0.004 * quality + noise(0.012),
            "fwd_op_margin": 0.08 + 0.04 * quality + noise(0.03),
            "roic": 0.07 + 0.04 * quality + noise(0.025),
            "debt_to_equity": float(np.exp(np.log(0.7) - 0.3 * quality + noise(0.4))),
        }
        drop = rng.random(len(row)) < _FUNDAMENTAL_MISSING_RATE
        rows[ticker] = {k: (np.nan if d else v) for (k, v), d in zip(row.items(), drop)}
    frame = pd.DataFrame.from_dict(rows, orient="index")
    frame.index.name = "ticker"
    return frame


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
