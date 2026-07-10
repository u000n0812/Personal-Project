"""Vectorized backtest engine.

Strategy-agnostic by design: it consumes a *weights panel* (dates × tickers,
produced by any signal function) plus a close-price panel, and returns an
equity curve, a buy-and-hold benchmark, and a metrics dict. No per-row Python
loops — everything is pandas column arithmetic.

Timing convention (no lookahead): a weight decided at the close of rebalance
day *t* is held from day *t+1* on and earns day *t+1*'s return. Transaction
costs are charged on the day the position actually changes, proportional to
one-way turnover.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtest import metrics as m

# UI label → pandas period code used to find "last trading day of period"
REBALANCE_CODES = {"daily": "D", "weekly": "W", "monthly": "M"}


@dataclass
class BacktestResult:
    """Everything a page needs to render one backtest."""

    equity: pd.Series            # strategy growth of ₩1
    benchmark: pd.Series         # equal-weight buy-and-hold growth of ₩1
    returns: pd.Series           # strategy net daily returns
    benchmark_returns: pd.Series
    weights: pd.DataFrame        # positions actually held each day
    turnover: pd.Series          # one-way turnover per day
    metrics: dict[str, float]
    benchmark_metrics: dict[str, float]


def rebalance_mask(index: pd.DatetimeIndex, frequency: str) -> pd.Series:
    """Boolean mask marking the last trading day of each rebalance period."""
    code = REBALANCE_CODES[frequency]
    if code == "D":
        return pd.Series(True, index=index)
    periods = pd.Series(index.to_period(code), index=index)
    return periods.ne(periods.shift(-1))  # True on period boundaries + final day


def run_backtest(
    close: pd.DataFrame,
    signals: pd.DataFrame,
    rebalance: str = "monthly",
    cost_bps: float = 10.0,
) -> BacktestResult:
    """Run one vectorized backtest.

    Args:
        close: dates × tickers close prices (NaN = non-investable that day).
        signals: dates × tickers desired weights from any strategy; sampled
            on rebalance days and held in between. NaN → 0.
        rebalance: "daily" | "weekly" | "monthly".
        cost_bps: one-way transaction cost in basis points of traded notional.

    Returns:
        BacktestResult. Equity curves start at 1.0 on the day before the first
        position is opened (warm-up days from lookback windows are trimmed so
        CAGR/Sharpe aren't diluted by a long flat stretch).
    """
    close = close.sort_index()
    signals = signals.reindex(index=close.index, columns=close.columns)

    rets = close.pct_change(fill_method=None)
    # An asset without a price today is not investable: force weight 0.
    signals = signals.where(close.notna(), 0.0).fillna(0.0)

    # Sample desired weights on rebalance days, hold them in between.
    mask = rebalance_mask(close.index, rebalance)
    target = signals.where(mask).ffill().fillna(0.0)

    # Decided at close of t → held from t+1. This is the no-lookahead shift.
    positions = target.shift(1).fillna(0.0)

    gross = (positions * rets).sum(axis=1)  # NaN rets pair with 0 weights
    turnover = positions.diff().abs().sum(axis=1)
    turnover.iloc[0] = positions.iloc[0].abs().sum()
    net = gross - turnover * cost_bps / 1e4

    # Equal-weight buy-and-hold benchmark on the same assets: buy at each
    # asset's first available price, never rebalance.
    first_price = close.bfill().iloc[0]
    bench_equity = (close / first_price).mean(axis=1)
    bench_equity = bench_equity / bench_equity.iloc[0]
    bench_rets = bench_equity.pct_change(fill_method=None).fillna(0.0)

    # Trim strategy warm-up: start both curves where the first position opens.
    active = positions.abs().sum(axis=1) > 0
    if active.any():
        start = active.idxmax()
        net, turnover, positions = net.loc[start:], turnover.loc[start:], positions.loc[start:]
        active = active.loc[start:]
        bench_rets = bench_rets.loc[start:]

    equity = (1.0 + net.fillna(0.0)).cumprod()
    bench_equity = (1.0 + bench_rets).cumprod()

    return BacktestResult(
        equity=equity,
        benchmark=bench_equity,
        returns=net,
        benchmark_returns=bench_rets,
        weights=positions,
        turnover=turnover,
        metrics=m.summary(net, equity, active=active),
        benchmark_metrics=m.summary(bench_rets, bench_equity),
    )
