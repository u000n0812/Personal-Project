"""파이프라인 핵심 동작 스모크 테스트 (synthetic 데이터 기반)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from commodity_quant.config import Config
from commodity_quant.data.synthetic import generate_prices
from commodity_quant.features.technical import add_technical_features, feature_columns
from commodity_quant.backtest.evaluator import evaluate_models
from commodity_quant.backtest.metrics import return_metrics
from commodity_quant.models import build_model, available_models


@pytest.fixture
def featured():
    df = generate_prices("TEST=F", group="energy", days=600, seed=1)
    return add_technical_features(df)


def test_synthetic_shape():
    df = generate_prices("X=F", group="precious_metals", days=300, seed=7)
    assert len(df) == 300
    assert {"Open", "High", "Low", "Close", "Volume"}.issubset(df.columns)
    # High >= Low, 가격 양수
    assert (df["High"] >= df["Low"]).all()
    assert (df["Close"] > 0).all()


def test_synthetic_deterministic():
    a = generate_prices("CL=F", group="energy", days=100, seed=42)
    b = generate_prices("CL=F", group="energy", days=100, seed=42)
    pd.testing.assert_frame_equal(a, b)


def test_features(featured):
    assert "log_return" in featured.columns
    assert "rsi" in featured.columns
    assert len(feature_columns(featured)) > 5


def test_return_metrics_perfect():
    y = pd.Series([0.01, -0.02, 0.03, -0.01])
    m = return_metrics(y, y)
    assert m["rmse"] == pytest.approx(0.0)
    assert m["directional_acc"] == pytest.approx(1.0)


def test_naive_predicts_zero(featured):
    model = build_model("naive")
    model.fit(featured)
    assert model.predict_next(featured) == 0.0


@pytest.mark.parametrize("name", ["naive", "arima", "garch", "xgboost"])
def test_model_backtest_runs(featured, name):
    model = build_model(name)
    summary, preds = evaluate_models([model], featured, test_size=40, refit_every=10)
    assert not summary.empty
    assert model.name in preds
    # 예측 길이가 검증 구간과 일치
    assert len(preds[model.name]) == 40


def test_lstm_optional():
    # torch 미설치 환경에서는 명확한 ImportError 가 나야 한다.
    try:
        import torch  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError):
            build_model("lstm")


def test_available_models():
    assert set(["naive", "arima", "garch", "xgboost", "lstm"]).issubset(available_models())
