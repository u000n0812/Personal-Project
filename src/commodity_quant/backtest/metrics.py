"""예측 성능 지표."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _clean(y_true: pd.Series, y_pred: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    df = pd.concat([y_true, y_pred], axis=1).dropna()
    return df.iloc[:, 0].to_numpy(), df.iloc[:, 1].to_numpy()


def return_metrics(y_true: pd.Series, y_pred: pd.Series) -> dict[str, float]:
    """수익률 점예측에 대한 지표.

    - RMSE / MAE      : 예측 오차 크기
    - directional_acc : 방향(부호) 적중률 — 트레이딩 관점에서 가장 중요
    - hit_rate_vs_zero: 0 대비 부호 일치율과 동일 의미 (참고용)
    - r2              : 결정계수 (음수면 평균보다 못함)
    """
    t, p = _clean(y_true, y_pred)
    if len(t) == 0:
        return {k: float("nan") for k in
                ["rmse", "mae", "directional_acc", "r2", "n"]}
    err = t - p
    rmse = float(np.sqrt(np.mean(err**2)))
    mae = float(np.mean(np.abs(err)))
    # 방향 적중률 (실제·예측 부호 일치 비율). 0 은 중립으로 제외.
    mask = (t != 0) & (p != 0)
    if mask.any():
        directional = float(np.mean(np.sign(t[mask]) == np.sign(p[mask])))
    else:
        directional = float("nan")
    ss_res = float(np.sum(err**2))
    ss_tot = float(np.sum((t - t.mean()) ** 2)) or float("nan")
    r2 = 1.0 - ss_res / ss_tot if ss_tot == ss_tot else float("nan")
    return {"rmse": rmse, "mae": mae, "directional_acc": directional,
            "r2": r2, "n": float(len(t))}


def volatility_metrics(realized: pd.Series, pred_vol: pd.Series) -> dict[str, float]:
    """변동성 예측 지표. 실현 변동성 대용치로 |수익률| 을 사용한다.

    QLIKE 는 변동성 예측 평가에 널리 쓰이는 손실함수다(작을수록 좋음).
    """
    t, p = _clean(realized.abs(), pred_vol)
    if len(t) == 0:
        return {k: float("nan") for k in ["rmse", "mae", "qlike", "n"]}
    err = t - p
    rmse = float(np.sqrt(np.mean(err**2)))
    mae = float(np.mean(np.abs(err)))
    # QLIKE: var 기준. p,t 를 분산으로 환산.
    var_p = np.clip(p**2, 1e-12, None)
    var_t = t**2
    qlike = float(np.mean(np.log(var_p) + var_t / var_p))
    return {"rmse": rmse, "mae": mae, "qlike": qlike, "n": float(len(t))}
