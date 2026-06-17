"""ARIMA 기반 수익률 예측기 (statsmodels)."""
from __future__ import annotations

import logging
import warnings

import pandas as pd

from .base import BaseForecaster

logger = logging.getLogger(__name__)


class ArimaForecaster(BaseForecaster):
    """로그수익률에 ARIMA(p,d,q) 를 적합하여 1-스텝 예측.

    수익률은 이미 정상(stationary)에 가까우므로 기본 차분 d=0 을 사용한다.
    """

    name = "arima"
    kind = "return"

    def __init__(self, order: tuple[int, int, int] = (2, 0, 2)):
        self.order = order
        self._res = None
        self._fit_len = 0

    def fit(self, history: pd.DataFrame) -> "ArimaForecaster":
        from statsmodels.tsa.arima.model import ARIMA

        y = history["log_return"].dropna()
        self._fit_len = len(y)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self._res = ARIMA(y, order=self.order).fit()
        except Exception as exc:  # 수렴 실패 등
            logger.debug("ARIMA fit 실패(%s) -> 0 예측으로 폴백", exc)
            self._res = None
        return self

    def predict_next(self, history: pd.DataFrame) -> float:
        if self._res is None:
            return 0.0
        y = history["log_return"].dropna()
        try:
            # 마지막 적합 이후 새로 관측된 값이 있으면 재적합 없이 반영
            if len(y) > self._fit_len:
                new_obs = y.iloc[self._fit_len:]
                res = self._res.append(new_obs, refit=False)
            else:
                res = self._res
            return float(res.forecast(steps=1).iloc[0])
        except Exception as exc:
            logger.debug("ARIMA forecast 실패(%s) -> 0", exc)
            return 0.0
