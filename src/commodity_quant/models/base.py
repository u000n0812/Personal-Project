"""예측 모델 공통 인터페이스."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseForecaster(ABC):
    """1-스텝 예측기의 추상 베이스.

    워크-포워드 백테스트에서 평가기는 다음 절차를 반복한다::

        if step % refit_every == 0:
            model.fit(history)        # (재)학습 — 비쌀 수 있음
        pred = model.predict_next(history)   # 항상 최신 history 로 1-스텝 예측

    Attributes
    ----------
    name : 결과 테이블에 표시될 모델 이름
    kind : "return"  -> 다음 거래일 로그수익률을 예측
           "volatility" -> 다음 거래일 변동성(표준편차)을 예측
    """

    name: str = "base"
    kind: str = "return"

    @abstractmethod
    def fit(self, history: pd.DataFrame) -> "BaseForecaster":
        """``history`` (피처가 포함된 OHLCV DataFrame) 로 모델을 학습한다."""

    @abstractmethod
    def predict_next(self, history: pd.DataFrame) -> float:
        """``history`` 마지막 시점 다음 거래일의 값을 예측한다."""

    def __repr__(self) -> str:  # pragma: no cover - 디버깅 편의
        return f"<{self.__class__.__name__} name={self.name!r} kind={self.kind!r}>"
