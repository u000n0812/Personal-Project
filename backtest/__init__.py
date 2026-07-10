"""Vectorized backtesting engine, independent of any specific strategy."""

from backtest.engine import BacktestResult, run_backtest
from backtest.metrics import drawdown_series, summary

__all__ = ["BacktestResult", "run_backtest", "drawdown_series", "summary"]
