"""백테스트: 신호대로 사고팔았으면 얼마를 벌었을까?

원칙
----
- look-ahead 금지: 오늘 정한 포지션은 '내일' 수익률에 적용 (position.shift(1))
- 거래비용 반영: 포지션이 바뀔 때마다 비용 차감
- 비교 기준: 그냥 사서 들고 있기(Buy & Hold) 대비 성과
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252  # 1년 거래일 수


def run_backtest(signals: pd.DataFrame, cost_bps: float = 1.0) -> tuple[pd.DataFrame, dict]:
    """신호 DataFrame → (손익 DataFrame, 성과지표 dict).

    Parameters
    ----------
    cost_bps : 포지션 1단위 변경당 거래비용 (bps, 1bp = 0.01%)
    """
    df = signals.copy()

    # 어제 정한 포지션이 오늘 수익률을 얻는다 (미래 정보 사용 방지)
    pos = df["position"].shift(1).fillna(0.0)
    turnover = pos.diff().abs().fillna(0.0)          # 포지션 변화량
    cost = turnover * (cost_bps / 10_000)            # 거래비용

    df["strat_ret"] = pos * df["gold_ret"] - cost    # 전략 일간 수익률
    df["bh_ret"] = df["gold_ret"]                    # 비교용: 그냥 보유

    df["strat_equity"] = (1 + df["strat_ret"].fillna(0)).cumprod()
    df["bh_equity"] = (1 + df["bh_ret"].fillna(0)).cumprod()

    active = df["strat_ret"][pos != 0]
    metrics = {
        "strategy": {
            **_performance(df["strat_ret"]),
            "win_rate": float((active > 0).mean()) if len(active) else float("nan"),
            "n_trades": int((turnover > 0).sum()),
            "exposure": float((pos != 0).mean()),  # 시장에 들어가 있던 날의 비율
        },
        "buy_and_hold": _performance(df["bh_ret"]),
    }
    return df, metrics


def _performance(returns: pd.Series) -> dict:
    """일간 수익률 → 연환산 성과지표."""
    r = returns.dropna()
    if r.empty or r.std() == 0:
        return {k: float("nan") for k in
                ("ann_return", "ann_vol", "sharpe", "max_drawdown", "total_return")}
    ann_return = float(r.mean() * TRADING_DAYS)
    ann_vol = float(r.std() * np.sqrt(TRADING_DAYS))
    equity = (1 + r).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    return {
        "ann_return": ann_return,                       # 연 수익률
        "ann_vol": ann_vol,                             # 연 변동성
        "sharpe": ann_return / ann_vol,                 # 위험 대비 수익 (높을수록 좋음)
        "max_drawdown": float(drawdown.min()),          # 최대 낙폭 (0에 가까울수록 좋음)
        "total_return": float(equity.iloc[-1] - 1.0),   # 기간 전체 누적 수익률
    }
