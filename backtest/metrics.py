"""Performance metrics for daily-return backtests. Pure pandas/numpy."""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def cagr(equity: pd.Series) -> float:
    """Compound annual growth rate of an equity curve (daily index)."""
    if len(equity) < 2 or equity.iloc[0] <= 0:
        return float("nan")
    years = (len(equity) - 1) / TRADING_DAYS
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1) if years > 0 else float("nan")


def annualized_vol(returns: pd.Series) -> float:
    return float(returns.std(ddof=0) * np.sqrt(TRADING_DAYS))


def sharpe(returns: pd.Series, rf_annual: float = 0.0) -> float:
    """Annualized Sharpe ratio vs. a constant risk-free rate."""
    excess = returns - rf_annual / TRADING_DAYS
    sd = excess.std(ddof=0)
    if sd == 0 or np.isnan(sd):
        return float("nan")
    return float(excess.mean() / sd * np.sqrt(TRADING_DAYS))


def drawdown_series(equity: pd.Series) -> pd.Series:
    """Fractional drawdown from the running peak (≤ 0)."""
    return equity / equity.cummax() - 1.0


def max_drawdown(equity: pd.Series) -> float:
    return float(drawdown_series(equity).min())


def hit_ratio(returns: pd.Series, active: pd.Series | None = None) -> float:
    """Share of positive-return days. When ``active`` (bool mask of days with
    an open position) is given, flat days are excluded — a flat strategy
    shouldn't earn 'hits' for doing nothing."""
    r = returns[active] if active is not None else returns
    r = r[r != 0] if active is None else r
    if len(r) == 0:
        return float("nan")
    return float((r > 0).mean())


def summary(returns: pd.Series, equity: pd.Series, active: pd.Series | None = None) -> dict[str, float]:
    """The metrics dict every page renders. Keys are display names."""
    return {
        "CAGR": cagr(equity),
        "Sharpe": sharpe(returns),
        "Max Drawdown": max_drawdown(equity),
        "Volatility": annualized_vol(returns),
        "Hit Ratio": hit_ratio(returns, active),
    }
