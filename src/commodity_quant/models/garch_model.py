"""GARCH(1,1) 변동성 예측기 (arch 패키지).

원자재는 변동성 군집(volatility clustering)이 강해 GARCH 류 모델이 잘 맞는다.
이 모델은 *수익률 방향* 이 아니라 *다음 거래일의 변동성(표준편차)* 을 예측한다.
따라서 ``kind = "volatility"`` 로 분류되어 별도 지표로 평가된다.
"""
from __future__ import annotations

import logging
import warnings

import numpy as np
import pandas as pd

from .base import BaseForecaster

logger = logging.getLogger(__name__)

# arch 는 수익률을 % 스케일(예: 1.5)로 줄 때 수렴이 안정적이다.
_SCALE = 100.0


class GarchForecaster(BaseForecaster):
    name = "garch(1,1)"
    kind = "volatility"

    def __init__(self, p: int = 1, q: int = 1):
        self.p = p
        self.q = q
        self._res = None

    def fit(self, history: pd.DataFrame) -> "GarchForecaster":
        from arch import arch_model

        y = history["log_return"].dropna() * _SCALE
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                am = arch_model(y, vol="Garch", p=self.p, q=self.q, mean="Constant", dist="t")
                self._res = am.fit(disp="off")
        except Exception as exc:
            logger.debug("GARCH fit 실패(%s) -> NaN", exc)
            self._res = None
        return self

    def predict_next(self, history: pd.DataFrame) -> float:
        if self._res is None:
            return float("nan")
        try:
            fc = self._res.forecast(horizon=1, reindex=False)
            var = float(fc.variance.values[-1, 0])
            # % 스케일을 되돌려 일간 수익률 표준편차로 변환
            return float(np.sqrt(var) / _SCALE)
        except Exception as exc:
            logger.debug("GARCH forecast 실패(%s) -> NaN", exc)
            return float("nan")
