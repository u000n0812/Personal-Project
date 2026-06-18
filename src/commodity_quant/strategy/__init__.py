"""트레이딩 전략 모듈."""
from .gold_macro import (
    load_macro_data,
    compute_signals,
    backtest,
    run_gold_strategy,
    latest_recommendation,
)

__all__ = [
    "load_macro_data",
    "compute_signals",
    "backtest",
    "run_gold_strategy",
    "latest_recommendation",
]
