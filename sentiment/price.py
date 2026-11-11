"""Price behavior of a stock *relative to its market index*. Pure pandas.

Working on the ratio stock / index strips out the market's own move, so the
"Price" family measures company-specific sentiment — a stock rising with a
rising market scores neutral here; one rising while the market falls scores
bullish.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

RSI_DAYS, RANGE_DAYS, TREND_DAYS = 14, 252, 50


def rsi(series: pd.Series, days: int = RSI_DAYS) -> pd.Series:
    """Wilder's Relative Strength Index, 0–100."""
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / days, adjust=False, min_periods=days).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / days, adjust=False, min_periods=days).mean()
    rs = gain / loss.replace(0, np.nan)
    out = (100 - 100 / (1 + rs)).where(loss > 0, 100.0)     # only gains → 100
    out = out.where((gain > 0) | (loss > 0), 50.0)          # no movement → neutral 50
    return out.where(gain.notna())


def relative_components(stock: pd.Series, index: pd.Series) -> pd.DataFrame:
    """Daily component scores in [-1, 1] on the stock/index ratio:

    * rsi    — (RSI14 − 50) / 50
    * range  — position in the 52-week range of the ratio, scaled to [-1, 1]
    * trend  — ratio vs its 50-day average, ±10% → ±1
    """
    both = pd.concat([stock, index], axis=1, keys=["s", "i"]).ffill().dropna()
    ratio = both["s"] / both["i"]
    lo = ratio.rolling(RANGE_DAYS, min_periods=60).min()
    hi = ratio.rolling(RANGE_DAYS, min_periods=60).max()
    position = ((ratio - lo) / (hi - lo).replace(0, np.nan)).where(hi > lo, 0.5)  # flat → middle
    position = position.where(lo.notna())
    trend = ratio / ratio.rolling(TREND_DAYS, min_periods=TREND_DAYS).mean() - 1
    return pd.DataFrame({
        "rsi": (rsi(ratio) - 50) / 50,
        "range": 2 * position - 1,
        "trend": (trend / 0.10).clip(-1, 1),
    })


def relative_history(stock: pd.Series, index: pd.Series) -> pd.Series:
    """Daily price-behavior score in [-1, 1] (mean of the three components)."""
    return relative_components(stock, index).mean(axis=1, skipna=False).dropna()


def excess_returns(stock: pd.Series, index: pd.Series) -> dict[str, float]:
    both = pd.concat([stock, index], axis=1, keys=["s", "i"]).ffill().dropna()
    out = {}
    for label, days in (("1M", 21), ("3M", 63)):
        if len(both) > days:
            r = both.iloc[-1] / both.iloc[-1 - days] - 1
            out[label] = float(r["s"] - r["i"])
    return out
