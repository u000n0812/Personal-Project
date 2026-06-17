"""예측 모델 모음.

모든 모델은 :class:`~commodity_quant.models.base.BaseForecaster` 인터페이스를 따른다.
``build_model(name, cfg)`` 팩토리로 이름을 통해 생성한다.
"""
from __future__ import annotations

from .base import BaseForecaster
from .naive import NaiveForecaster
from .arima_model import ArimaForecaster
from .garch_model import GarchForecaster
from .ml_model import XGBoostForecaster

_REGISTRY = {
    "naive": NaiveForecaster,
    "arima": ArimaForecaster,
    "garch": GarchForecaster,
    "xgboost": XGBoostForecaster,
}


def build_model(name: str, cfg=None) -> BaseForecaster:
    """이름으로 모델 인스턴스를 생성한다."""
    key = name.lower()
    if key == "lstm":
        # 무거운 의존성(torch)은 필요할 때만 임포트
        from .lstm_model import LSTMForecaster

        return LSTMForecaster(cfg)
    if key not in _REGISTRY:
        raise KeyError(f"알 수 없는 모델: {name!r}. 사용 가능: {list(_REGISTRY) + ['lstm']}")
    return _REGISTRY[key]()


def available_models() -> list[str]:
    return list(_REGISTRY) + ["lstm"]


__all__ = ["BaseForecaster", "build_model", "available_models"]
