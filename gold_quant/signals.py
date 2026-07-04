"""매매 신호: 실질금리 + 달러 신뢰 → 금 매수/매도 점수.

투자 논리
---------
금은 이자가 없는 자산이고 달러의 대체 안전자산이다. 따라서:

  (1) 실질금리 ↓ (낮은 수준 / 하락 추세)  →  금 보유의 기회비용 ↓  →  금 매수
  (2) 달러 신뢰 ↓ (달러 인덱스 약세)      →  대체자산 수요 ↑        →  금 매수

계산 방법
---------
각 동인을 두 관점으로 표준화(z-score)한다:
  - 수준(level)   : 지금 값이 최근 구간 대비 높은가/낮은가
  - 모멘텀(momentum): 최근 며칠간 오르는 중인가/내리는 중인가

둘을 가중 합산한 뒤 부호를 뒤집는다(두 동인 모두 금과 음(-)의 관계이므로).
실질금리 신호와 달러 신호를 다시 가중 합산해 하나의 '합성 점수'를 만들고,
점수가 +임계값보다 크면 매수(+1), -임계값보다 작으면 매도/숏(-1), 그 사이면 관망(0).

look-ahead 방지: 오늘 계산한 점수는 백테스트에서 '내일' 수익률에만 적용된다.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Params:
    """전략 파라미터 (여기 숫자만 바꿔서 실험하면 된다)."""

    lookback: int = 60          # z-score 계산 윈도우 (거래일)
    momentum_window: int = 10   # 모멘텀(변화량) 계산 윈도우
    level_weight: float = 0.4   # 신호 안에서 '수준'의 비중
    momentum_weight: float = 0.6  # 신호 안에서 '모멘텀'의 비중
    weight_real_rate: float = 0.5  # 합성 시 실질금리 신호의 가중
    weight_dollar: float = 0.5     # 합성 시 달러 신호의 가중
    entry_threshold: float = 0.4   # |점수| 가 이 값을 넘어야 진입
    allow_short: bool = True       # False 면 매도 신호 때 숏 대신 현금 보유


def _zscore(s: pd.Series, window: int) -> pd.Series:
    """롤링 z-score: (값 - 롤링평균) / 롤링표준편차."""
    mean = s.rolling(window, min_periods=window // 2).mean()
    std = s.rolling(window, min_periods=window // 2).std()
    return (s - mean) / std.replace(0.0, np.nan)


def _driver_signal(series: pd.Series, p: Params) -> pd.Series:
    """매크로 동인 하나를 '금 매수 신호'로 변환.

    수준·모멘텀 z-score 를 가중 합산 후 부호 반전(동인↑ = 금 약세이므로).
    결과가 + 면 금 매수 우호, - 면 금 매도 우호.
    """
    level_z = _zscore(series, p.lookback)
    momentum_z = _zscore(series.diff(p.momentum_window), p.lookback)
    raw = p.level_weight * level_z + p.momentum_weight * momentum_z
    return -raw


def compute_signals(data: pd.DataFrame, p: Params | None = None) -> pd.DataFrame:
    """가격 데이터 → 신호·포지션 DataFrame.

    추가되는 컬럼
      gold_ret        : 금 일간 로그수익률
      sig_real_rate   : 실질금리 기반 매수 신호
      sig_dollar      : 달러 기반 매수 신호
      score           : 두 신호의 가중 합성 점수 (표준화됨)
      position        : +1 매수 / -1 매도·숏 / 0 관망
    """
    p = p or Params()
    out = data.copy()
    out["gold_ret"] = np.log(out["gold"]).diff()

    out["sig_real_rate"] = _driver_signal(out["real_rate"], p)
    out["sig_dollar"] = _driver_signal(out["dollar"], p)

    composite = (p.weight_real_rate * out["sig_real_rate"]
                 + p.weight_dollar * out["sig_dollar"])
    # 합성 점수를 자체 변동성으로 나눠 시기별 스케일을 맞춘다
    out["score"] = composite / composite.rolling(p.lookback, min_periods=p.lookback // 2).std()

    position = pd.Series(0.0, index=out.index)
    position[out["score"] > p.entry_threshold] = 1.0
    position[out["score"] < -p.entry_threshold] = -1.0 if p.allow_short else 0.0
    out["position"] = position
    return out


def current_recommendation(signals: pd.DataFrame) -> dict:
    """가장 최근 날짜의 매매 권고."""
    last = signals.dropna(subset=["score"]).iloc[-1]
    if last["position"] > 0:
        action = "매수 (BUY)"
    elif last["position"] < 0:
        action = "매도 (SELL/SHORT)"
    else:
        action = "관망 (HOLD)"
    return {
        "date": last.name,
        "gold_price": float(last["gold"]),
        "real_rate": float(last["real_rate"]),
        "dollar": float(last["dollar"]),
        "sig_real_rate": float(last["sig_real_rate"]),
        "sig_dollar": float(last["sig_dollar"]),
        "score": float(last["score"]),
        "action": action,
    }
