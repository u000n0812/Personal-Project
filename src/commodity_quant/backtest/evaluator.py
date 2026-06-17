"""워크-포워드(walk-forward) 백테스트 엔진.

look-ahead bias 없이, 매 시점마다 *그 시점까지의 데이터만* 으로 학습/예측하여
1-스텝 예측을 누적한다. 그 후 모델별 성능 지표를 계산한다.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..models.base import BaseForecaster
from .metrics import return_metrics, volatility_metrics

logger = logging.getLogger(__name__)


def walk_forward(
    model: BaseForecaster,
    featured: pd.DataFrame,
    test_size: int = 120,
    refit_every: int = 5,
) -> pd.DataFrame:
    """단일 모델의 워크-포워드 예측을 수행한다.

    Returns
    -------
    DataFrame(index=날짜) with columns:
      - actual_return : 해당일 실제 로그수익률
      - pred          : 모델 예측값 (kind 에 따라 수익률 또는 변동성)
    """
    df = featured
    n = len(df)
    test_size = min(test_size, n - 60)  # 최소 학습량 확보
    if test_size <= 0:
        raise ValueError("데이터가 너무 적어 백테스트할 수 없습니다.")

    test_index = df.index[-test_size:]
    records = []
    for i, t in enumerate(test_index):
        loc = df.index.get_loc(t)
        history = df.iloc[:loc]  # t 이전까지 (t 미포함)
        if i % refit_every == 0:
            model.fit(history)
        pred = model.predict_next(history)
        records.append((t, df["log_return"].iloc[loc], pred))

    out = pd.DataFrame(records, columns=["date", "actual_return", "pred"]).set_index("date")
    return out


def evaluate_models(
    models: list[BaseForecaster],
    featured: pd.DataFrame,
    test_size: int = 120,
    refit_every: int = 5,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """여러 모델을 백테스트하고 성능 비교 테이블을 만든다.

    Returns
    -------
    (summary, predictions)
      summary     : 모델별 지표 DataFrame
      predictions : {model_name: walk_forward 결과 DataFrame}
    """
    rows = []
    predictions: dict[str, pd.DataFrame] = {}
    for model in models:
        logger.info("백테스트: %s", model.name)
        try:
            preds = walk_forward(model, featured, test_size, refit_every)
        except Exception as exc:
            logger.warning("모델 %s 백테스트 실패: %s", model.name, exc)
            continue
        predictions[model.name] = preds
        if model.kind == "volatility":
            m = volatility_metrics(preds["actual_return"], preds["pred"])
            m = {"model": model.name, "kind": "volatility", **m}
        else:
            m = return_metrics(preds["actual_return"], preds["pred"])
            m = {"model": model.name, "kind": "return", **m}
        rows.append(m)

    summary = pd.DataFrame(rows)
    return summary, predictions
