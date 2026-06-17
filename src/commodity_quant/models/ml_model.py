"""XGBoost 기반 수익률 예측기.

기술적 지표(피처)를 입력으로 다음 거래일 로그수익률을 회귀한다.
타깃 정렬: 시점 t 의 피처 -> t+1 의 수익률.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..features.technical import feature_columns
from .base import BaseForecaster

logger = logging.getLogger(__name__)


class XGBoostForecaster(BaseForecaster):
    name = "xgboost"
    kind = "return"

    def __init__(self, **params):
        self.params = dict(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.03,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            random_state=42,
            n_jobs=2,
        )
        self.params.update(params)
        self._model = None
        self._feat_cols: list[str] = []

    def fit(self, history: pd.DataFrame) -> "XGBoostForecaster":
        from xgboost import XGBRegressor

        self._feat_cols = feature_columns(history)
        # 시점 t 피처 -> t+1 수익률
        X = history[self._feat_cols]
        y = history["log_return"].shift(-1)
        data = X.join(y.rename("__target__")).dropna()
        if len(data) < 50:
            logger.debug("XGBoost 학습 데이터 부족(%d) -> 폴백", len(data))
            self._model = None
            return self
        self._model = XGBRegressor(**self.params)
        self._model.fit(data[self._feat_cols].values, data["__target__"].values)
        return self

    def predict_next(self, history: pd.DataFrame) -> float:
        if self._model is None:
            return 0.0
        last = history[self._feat_cols].iloc[[-1]]
        if last.isnull().any(axis=None):
            # 가장 최근의 결측 없는 피처 행으로 폴백
            valid = history[self._feat_cols].dropna()
            if valid.empty:
                return 0.0
            last = valid.iloc[[-1]]
        return float(self._model.predict(last.values)[0])
