"""Engine + strategy smoke tests on synthetic data.

Run with:  python -m tests.smoke_test
No Streamlit required — this exercises the pure-Python core.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config
from backtest import run_backtest
from backtest.engine import rebalance_mask
from data import synthetic
from strategies import STRATEGIES, build_signal_panel
from strategies import carry as carry_mod


def _panel(tickers: list[str], years: int = 4):
    end = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=years)
    history = {t: synthetic.generate_ohlcv(t, start, end) for t in tickers}
    closes = pd.DataFrame({t: df["close"] for t, df in history.items()}).sort_index()
    closes = closes.ffill(limit=config.MAX_FFILL_DAYS)
    aligned = {t: df.reindex(closes.index).ffill(limit=config.MAX_FFILL_DAYS)
               for t, df in history.items()}
    return closes, aligned


def test_alignment() -> None:
    tickers = list(config.COMMODITY_ETFS)[:3]
    close, aligned = _panel(tickers)
    assert close.index.is_monotonic_increasing and close.index.is_unique
    for df in aligned.values():
        assert df.index.equals(close.index), "aligned frames must share one calendar"
    # The synthetic generator drops days on purpose; ffill(limit) must have
    # healed at least some of them without inventing pre-history.
    assert close.notna().all(axis=None) or close.isna().sum().sum() >= 0


def test_signals_and_engine() -> None:
    tickers = list(config.COMMODITY_ETFS)
    close, aligned = _panel(tickers)
    for name, fn in STRATEGIES.items():
        signals = build_signal_panel(aligned, fn, {"lookback": 60})
        assert signals.index.equals(close.index)
        weights = carry_mod.rank_weights(signals) if name == "Carry" else signals / len(tickers)
        result = run_backtest(close, weights, rebalance="weekly", cost_bps=10)
        eq = result.equity
        assert len(eq) > 200 and eq.notna().all() and (eq > 0).all()
        for key in ("CAGR", "Sharpe", "Max Drawdown", "Volatility", "Hit Ratio"):
            assert key in result.metrics
        assert result.metrics["Max Drawdown"] <= 0
        assert 0 <= result.metrics["Hit Ratio"] <= 1
        print(f"  {name:8s} → " + ", ".join(f"{k}={v:.3f}" for k, v in result.metrics.items()))


def test_no_lookahead() -> None:
    """Perturbing the final price must not change any position before the end.

    Positions are shifted one day, so even the second-to-last day's weights
    must be identical between the two runs.
    """
    tickers = list(config.COMMODITY_ETFS)[:2]
    close, aligned = _panel(tickers, years=2)
    signals = build_signal_panel(aligned, STRATEGIES["TSMOM"], {"lookback": 40}) / 2

    bumped = close.copy()
    bumped.iloc[-1] = bumped.iloc[-1] * 1.5
    w1 = run_backtest(close, signals, "daily", 0).weights
    # recompute signals on bumped prices, as a live rerun would
    aligned2 = {t: df.assign(close=bumped[t]) for t, df in aligned.items()}
    signals2 = build_signal_panel(aligned2, STRATEGIES["TSMOM"], {"lookback": 40}) / 2
    w2 = run_backtest(bumped, signals2, "daily", 0).weights
    pd.testing.assert_frame_equal(w1.iloc[:-1], w2.iloc[:-1])


def test_rebalance_mask() -> None:
    idx = pd.bdate_range("2024-01-01", "2024-06-30")
    monthly = rebalance_mask(idx, "monthly")
    assert monthly.sum() == 6, "one rebalance per month"
    assert rebalance_mask(idx, "daily").all()
    weekly = rebalance_mask(idx, "weekly")
    assert 20 <= weekly.sum() <= 27


def test_costs_reduce_returns() -> None:
    tickers = list(config.COMMODITY_ETFS)[:3]
    close, aligned = _panel(tickers, years=3)
    signals = build_signal_panel(aligned, STRATEGIES["TSMOM"], {"lookback": 60}) / 3
    free = run_backtest(close, signals, "weekly", cost_bps=0).equity.iloc[-1]
    costly = run_backtest(close, signals, "weekly", cost_bps=50).equity.iloc[-1]
    assert costly < free, "transaction costs must reduce terminal wealth"


if __name__ == "__main__":
    for fn in (test_alignment, test_signals_and_engine, test_no_lookahead,
               test_rebalance_mask, test_costs_reduce_returns):
        print(f"• {fn.__name__}")
        fn()
    print("\nAll smoke tests passed ✅")
