"""핵심 로직 테스트 (인터넷 불필요 — 데모 데이터 사용).

실행:  python -m pytest tests/ -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gold_quant.backtest import run_backtest
from gold_quant.data import demo_market_data, load_data
from gold_quant.signals import Params, compute_signals, current_recommendation


@pytest.fixture(scope="module")
def data() -> pd.DataFrame:
    return demo_market_data(days=800, seed=7)


def test_demo_data_shape(data):
    assert list(data.columns) == ["gold", "real_rate", "dollar"]
    assert len(data) == 800
    assert data.notna().all().all()
    assert (data["gold"] > 0).all()


def test_demo_data_economics(data):
    """금은 실질금리 변화·달러 수익률과 음(-)의 상관이어야 한다."""
    gold_ret = np.log(data["gold"]).diff()
    assert gold_ret.corr(data["real_rate"].diff()) < 0
    assert gold_ret.corr(np.log(data["dollar"]).diff()) < 0


def test_offline_load():
    df, is_real = load_data(offline=True)
    assert is_real is False
    assert len(df) > 100


def test_positions_are_valid(data):
    sig = compute_signals(data)
    assert set(sig["position"].unique()).issubset({-1.0, 0.0, 1.0})


def test_no_short_mode(data):
    sig = compute_signals(data, Params(allow_short=False))
    assert (sig["position"] >= 0).all()


def test_backtest_no_lookahead(data):
    """오늘 포지션은 내일 수익률에 적용: 마지막 날 손익은 전일 포지션 기준."""
    sig = compute_signals(data)
    bt, _ = run_backtest(sig, cost_bps=0.0)  # 비용 0 이면 정확히 일치해야 함
    expected = sig["position"].shift(1).iloc[-1] * sig["gold_ret"].iloc[-1]
    assert bt["strat_ret"].iloc[-1] == pytest.approx(expected)


def test_backtest_metrics(data):
    sig = compute_signals(data)
    bt, metrics = run_backtest(sig)
    for key in ("ann_return", "ann_vol", "sharpe", "max_drawdown", "total_return"):
        assert key in metrics["strategy"]
        assert key in metrics["buy_and_hold"]
    assert (bt["strat_equity"] > 0).all()


def test_costs_reduce_returns(data):
    """거래비용이 클수록 수익은 줄어야 한다."""
    sig = compute_signals(data)
    _, cheap = run_backtest(sig, cost_bps=0.0)
    _, pricey = run_backtest(sig, cost_bps=50.0)
    assert pricey["strategy"]["total_return"] < cheap["strategy"]["total_return"]


def test_recommendation(data):
    rec = current_recommendation(compute_signals(data))
    assert rec["action"] in {"매수 (BUY)", "매도 (SELL/SHORT)", "관망 (HOLD)"}
    assert np.isfinite(rec["score"])
