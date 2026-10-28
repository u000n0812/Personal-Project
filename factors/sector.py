"""Sector analytics: ETF performance and per-sector factor summaries. Pure pandas."""

from __future__ import annotations

import numpy as np
import pandas as pd

from factors.definitions import GROUPS

# label → trading days
RETURN_HORIZONS: dict[str, int] = {"1W": 5, "1M": 21, "3M": 63, "6M": 126, "1Y": 252}
CHART_PERIODS = ("1M", "3M", "6M", "YTD", "1Y", "3Y")


def _trailing(series: pd.Series, days: int) -> float:
    s = series.dropna()
    return float(s.iloc[-1] / s.iloc[-1 - days] - 1.0) if len(s) > days else np.nan


def _ytd(series: pd.Series) -> float:
    s = series.dropna()
    if s.empty:
        return np.nan
    before = s[s.index.year < s.index[-1].year]
    return float(s.iloc[-1] / before.iloc[-1] - 1.0) if len(before) else np.nan


def performance(close: pd.DataFrame, benchmark: str) -> pd.DataFrame:
    """Per-ticker performance table from a dates × tickers close panel.

    Columns: last, as_of, ret_1D, ret_1W…ret_1Y, ret_YTD, vol_1Y (annualized),
    mdd_1Y (max drawdown over the last year), and excess_<h> = return minus
    the benchmark's return over the same horizon (relative strength).
    """
    rows = {}
    for ticker in close.columns:
        s = close[ticker].dropna()
        if s.empty:
            rows[ticker] = {}
            continue
        year = s.iloc[-253:]
        daily = year.pct_change().dropna()
        rows[ticker] = {
            "last": float(s.iloc[-1]),
            "as_of": s.index[-1],
            "ret_1D": _trailing(s, 1),
            **{f"ret_{k}": _trailing(s, d) for k, d in RETURN_HORIZONS.items()},
            "ret_YTD": _ytd(s),
            "vol_1Y": float(daily.std(ddof=0) * np.sqrt(252)) if len(daily) > 20 else np.nan,
            "mdd_1Y": float((year / year.cummax() - 1.0).min()),
        }
    out = pd.DataFrame.from_dict(rows, orient="index")
    if benchmark in out.index:
        for k in (*RETURN_HORIZONS, "YTD"):
            out[f"excess_{k}"] = out[f"ret_{k}"] - out.at[benchmark, f"ret_{k}"]
    return out


def period_start(index: pd.DatetimeIndex, period: str) -> pd.Timestamp:
    """First date of a chart period ending at the last date of ``index``."""
    last = index.max()
    if period == "YTD":
        return pd.Timestamp(year=last.year, month=1, day=1)
    months = {"1M": 1, "3M": 3, "6M": 6, "1Y": 12, "3Y": 36}[period]
    return last - pd.DateOffset(months=months)


def rebased(close: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    """Growth of 100 from each series' first price on/after ``start``."""
    window = close.loc[close.index >= start].ffill()
    return window / window.bfill().iloc[0] * 100.0


def sector_summary(table: pd.DataFrame) -> pd.DataFrame:
    """Per (market, sector) summary of a scored universe.

    ``table`` needs: sector, leader, composite, the four group columns, and
    optionally market / ret_3M / ret_12M. Group columns should be
    *market-relative* percentiles so sectors can be compared with each other.
    """
    keys = [k for k in ("market", "sector") if k in table.columns]
    agg = {
        "companies": ("composite", "size"),
        "leaders": ("leader", "sum"),
        "composite": ("composite", "median"),
        **{g: (g, "median") for g in GROUPS},
    }
    for col in ("ret_3M", "ret_12M"):
        if col in table.columns:
            agg[col] = (col, "median")
    out = table.groupby(keys, dropna=False).agg(**agg).reset_index()
    out["leader_share"] = out["leaders"] / out["companies"]
    return out.sort_values(["composite"], ascending=False).reset_index(drop=True)
