"""LSTM 기반 수익률 예측기 (선택 — torch 필요).

과거 ``lookback`` 일의 수익률·변동성 시퀀스를 입력으로 다음 거래일 수익률을
회귀하는 소형 LSTM. torch 가 설치되어 있지 않으면 import 시 명확한 오류를 낸다.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from .base import BaseForecaster

logger = logging.getLogger(__name__)

try:
    import torch
    from torch import nn

    _HAS_TORCH = True
except ImportError:  # pragma: no cover
    _HAS_TORCH = False


if _HAS_TORCH:

    class _LSTMNet(nn.Module):
        def __init__(self, n_features: int, hidden_size: int):
            super().__init__()
            self.lstm = nn.LSTM(n_features, hidden_size, batch_first=True)
            self.head = nn.Linear(hidden_size, 1)

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.head(out[:, -1, :]).squeeze(-1)


class LSTMForecaster(BaseForecaster):
    name = "lstm"
    kind = "return"

    def __init__(self, cfg=None):
        if not _HAS_TORCH:
            raise ImportError(
                "LSTM 모델은 torch 가 필요합니다. `pip install torch` 후 사용하세요."
            )
        lstm_cfg = (cfg.get("lstm", {}) if cfg is not None else {}) or {}
        self.lookback = int(lstm_cfg.get("lookback", 20))
        self.hidden_size = int(lstm_cfg.get("hidden_size", 32))
        self.epochs = int(lstm_cfg.get("epochs", 30))
        self.lr = float(lstm_cfg.get("lr", 1e-3))
        self._model = None
        self._mu = 0.0
        self._sd = 1.0

    def _make_series(self, history: pd.DataFrame) -> np.ndarray:
        r = history["log_return"].fillna(0.0).values.astype("float32")
        return r

    def fit(self, history: pd.DataFrame) -> "LSTMForecaster":
        r = self._make_series(history)
        if len(r) < self.lookback + 30:
            self._model = None
            return self
        self._mu, self._sd = float(r.mean()), float(r.std() + 1e-8)
        rn = (r - self._mu) / self._sd
        X, y = [], []
        for i in range(self.lookback, len(rn) - 1):
            X.append(rn[i - self.lookback:i])
            y.append(rn[i + 1])
        X = torch.tensor(np.array(X)).unsqueeze(-1)
        y = torch.tensor(np.array(y))

        self._model = _LSTMNet(n_features=1, hidden_size=self.hidden_size)
        opt = torch.optim.Adam(self._model.parameters(), lr=self.lr)
        loss_fn = nn.MSELoss()
        self._model.train()
        for _ in range(self.epochs):
            opt.zero_grad()
            pred = self._model(X)
            loss = loss_fn(pred, y)
            loss.backward()
            opt.step()
        return self

    def predict_next(self, history: pd.DataFrame) -> float:
        if self._model is None:
            return 0.0
        r = self._make_series(history)
        if len(r) < self.lookback:
            return 0.0
        rn = (r[-self.lookback:] - self._mu) / self._sd
        x = torch.tensor(rn.reshape(1, self.lookback, 1))
        self._model.eval()
        with torch.no_grad():
            pred = float(self._model(x).item())
        return pred * self._sd + self._mu
