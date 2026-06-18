"""금 매크로 전략 테스트 (synthetic 데이터)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from commodity_quant.config import load_config
from commodity_quant.data import synthetic
from commodity_quant.strategy import (
    load_macro_data,
    compute_signals,
    backtest,
    latest_recommendation,
)


@pytest.fixture
def cfg():
    c = load_config()
    c.raw["data"]["source"] = "synthetic"
    c.raw["data"]["synthetic_days"] = 800
    return c


def test_macro_panel_correlation():
    panel = synthetic.generate_gold_macro(days=600, seed=7)
    assert set(panel) == {"gold", "real_rate", "dollar"}
    gold_ret = np.log(panel["gold"]["Close"]).diff()
    d_rr = panel["real_rate"]["Close"].diff()
    # 금 수익률은 실질금리 변화와 음의 상관이어야 한다
    corr = gold_ret.corr(d_rr)
    assert corr < 0


def test_load_macro_data(cfg):
    df = load_macro_data(cfg)
    assert {"gold", "real_rate", "dollar"}.issubset(df.columns)
    assert df.notna().all().all()
    assert len(df) > 100


def test_signals_positions(cfg):
    df = load_macro_data(cfg)
    sig = compute_signals(df, cfg)
    assert set(sig["position"].dropna().unique()).issubset({-1.0, 0.0, 1.0})
    assert "score" in sig.columns


def test_no_short_mode(cfg):
    cfg.raw["gold_strategy"]["signal"]["allow_short"] = False
    df = load_macro_data(cfg)
    sig = compute_signals(df, cfg)
    # 숏 금지면 -1 포지션이 없어야 한다
    assert (sig["position"] >= 0).all()


def test_backtest_metrics(cfg):
    df = load_macro_data(cfg)
    sig = compute_signals(df, cfg)
    bt, metrics = backtest(sig, cost_bps=1.0)
    assert "strategy" in metrics and "buy_and_hold" in metrics
    for key in ["ann_return", "ann_vol", "sharpe", "max_drawdown", "total_return"]:
        assert key in metrics["strategy"]
    # 자산곡선은 항상 양수
    assert (bt["strat_equity"] > 0).all()


def test_no_lookahead(cfg):
    # 마지막 행의 포지션은 그 다음날 수익률에만 영향 → 마지막 strat_ret 는 직전 포지션 사용
    df = load_macro_data(cfg)
    sig = compute_signals(df, cfg)
    bt, _ = backtest(sig)
    expected_last = sig["position"].iloc[-2] * sig["gold_ret"].iloc[-1]
    # 거래비용 제외한 gross 부분이 일치하는지(부호/크기) 대략 확인
    assert np.sign(bt["strat_ret"].iloc[-1]) == np.sign(expected_last) or expected_last == 0


def test_recommendation(cfg):
    df = load_macro_data(cfg)
    sig = compute_signals(df, cfg)
    rec = latest_recommendation(sig)
    assert rec["action"] in {
        "매수 (BUY / LONG)", "매도·숏 (SELL / SHORT)", "관망 (HOLD / CASH)"
    }
    assert "score" in rec
