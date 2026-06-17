"""나이브(random-walk) 기준 모델.

효율적 시장 가설 하에서 가격은 random walk 에 가깝고, 이때 다음 수익률의
최적 점예측은 0 (또는 표류항)이다. 다른 모델이 이 기준을 이기지 못하면
사실상 예측력이 없다는 뜻이므로 반드시 포함하는 강력한 베이스라인이다.
"""
from __future__ import annotations

import pandas as pd

from .base import BaseForecaster


class NaiveForecaster(BaseForecaster):
    name = "naive(random-walk)"
    kind = "return"

    def fit(self, history: pd.DataFrame) -> "NaiveForecaster":
        # 학습할 파라미터가 없다.
        return self

    def predict_next(self, history: pd.DataFrame) -> float:
        # 가격 random walk => 다음 수익률 기대값 0.
        return 0.0
