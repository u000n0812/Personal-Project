"""금(Gold) 매크로 트레이딩 전략.

금 가격을 움직이는 두 핵심 매크로 동인을 신호로 결합하여 매수/매도를 결정한다.

1) **실질금리(real interest rate)**
   금은 이자가 없는 자산이므로, 실질금리가 *낮을수록/하락할수록* 보유 매력이 커진다.
   → 실질금리 하락 = 금 매수 신호.

2) **달러 신뢰(USD confidence)**
   금은 달러의 대체 안전자산이다. 달러 신뢰가 약해질수록(달러 약세) 금 수요가 커진다.
   → 달러 약세 = 금 매수 신호.

두 신호를 각각 '수준(level)'과 '모멘텀(momentum)'의 z-score 로 표준화한 뒤
가중 합산하여 합성 점수를 만들고, 임계값을 넘으면 롱/숏(또는 현금) 포지션을 잡는다.

look-ahead bias 방지: 시점 t 의 신호로 정한 포지션은 t→t+1 수익률에만 적용한다.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..config import Config
from ..data import synthetic
from ..data.loader import load_prices

logger = logging.getLogger(__name__)

_TRADING_DAYS = 252


# ----------------------------------------------------------------------------
# 데이터 적재
# ----------------------------------------------------------------------------
def load_macro_data(cfg: Config) -> pd.DataFrame:
    """금·실질금리·달러 시계열을 받아 공통 날짜로 정렬한 DataFrame 을 반환.

    컬럼: ``gold`` (종가), ``real_rate`` (금리%), ``dollar`` (달러인덱스 종가)
    """
    gs = cfg["gold_strategy"]
    source = cfg["data"].get("source", "synthetic")

    if source == "synthetic":
        days = int(cfg["data"].get("synthetic_days", 1500))
        end = cfg["data"].get("end")
        panel = synthetic.generate_gold_macro(days=days, end=end, seed=7)
        gold = panel["gold"]["Close"]
        real_rate = panel["real_rate"]["Close"]
        dollar = panel["dollar"]["Close"]
    else:
        # yfinance / csv — 각 심볼을 개별 적재 후 종가 사용
        gold = load_prices(gs["gold_symbol"], cfg)["Close"]
        real_rate = load_prices(gs["real_rate_symbol"], cfg)["Close"]
        dollar = load_prices(gs["dollar_symbol"], cfg)["Close"]

    df = pd.concat(
        {"gold": gold, "real_rate": real_rate, "dollar": dollar}, axis=1
    )
    # 금리·달러는 결측을 직전값으로 채우고(휴장일 차이), 금 종가 결측 행은 제거
    df[["real_rate", "dollar"]] = df[["real_rate", "dollar"]].ffill()
    df = df.dropna(subset=["gold"]).dropna()
    return df


# ----------------------------------------------------------------------------
# 신호 계산
# ----------------------------------------------------------------------------
def _zscore(s: pd.Series, window: int) -> pd.Series:
    mean = s.rolling(window, min_periods=window // 2).mean()
    std = s.rolling(window, min_periods=window // 2).std()
    return (s - mean) / std.replace(0.0, np.nan)


def _driver_signal(series: pd.Series, lookback: int, mom_window: int,
                   level_w: float, mom_w: float) -> pd.Series:
    """매크로 동인 시계열을 '금 매수 신호'로 변환한다.

    실질금리·달러 모두 금과 *음(-)* 의 관계이므로 부호를 뒤집는다.
    높은 수준/상승 모멘텀 → 금에 약세(음의 신호).
    """
    level_z = _zscore(series, lookback)
    momentum = series.diff(mom_window)
    mom_z = _zscore(momentum, lookback)
    raw = level_w * level_z + mom_w * mom_z
    return -(raw)  # 음의 관계 반영


def compute_signals(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """매크로 데이터로부터 신호·포지션을 계산한다."""
    sig = cfg["gold_strategy"]["signal"]
    lookback = int(sig.get("lookback", 60))
    mom_window = int(sig.get("momentum_window", 10))
    level_w = float(sig.get("level_weight", 0.4))
    mom_w = float(sig.get("momentum_weight", 0.6))
    w_rr = float(sig.get("weight_real_rate", 0.5))
    w_dx = float(sig.get("weight_dollar", 0.5))
    entry = float(sig.get("entry_threshold", 0.4))
    allow_short = bool(sig.get("allow_short", True))

    out = df.copy()
    out["gold_ret"] = np.log(out["gold"]).diff()

    # 개별 동인 신호
    out["sig_real_rate"] = _driver_signal(out["real_rate"], lookback, mom_window, level_w, mom_w)
    out["sig_dollar"] = _driver_signal(out["dollar"], lookback, mom_window, level_w, mom_w)

    # 가중 합성 후 자체 변동성으로 표준화 -> '점수'
    composite = w_rr * out["sig_real_rate"] + w_dx * out["sig_dollar"]
    out["composite"] = composite
    out["score"] = composite / composite.rolling(lookback, min_periods=lookback // 2).std()

    # 임계값 기반 포지션 결정 (+1 매수 / -1 매도·숏 / 0 관망)
    pos = pd.Series(0.0, index=out.index)
    pos[out["score"] > entry] = 1.0
    pos[out["score"] < -entry] = -1.0 if allow_short else 0.0
    out["position"] = pos

    return out


# ----------------------------------------------------------------------------
# 백테스트
# ----------------------------------------------------------------------------
def _annualized_metrics(returns: pd.Series) -> dict[str, float]:
    r = returns.dropna()
    if r.empty or r.std() == 0:
        return {"ann_return": float("nan"), "ann_vol": float("nan"),
                "sharpe": float("nan"), "max_drawdown": float("nan")}
    ann_return = float(r.mean() * _TRADING_DAYS)
    ann_vol = float(r.std() * np.sqrt(_TRADING_DAYS))
    sharpe = ann_return / ann_vol if ann_vol else float("nan")
    equity = (1 + r).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    return {"ann_return": ann_return, "ann_vol": ann_vol,
            "sharpe": sharpe, "max_drawdown": float(drawdown.min())}


def backtest(signals: pd.DataFrame, cost_bps: float = 1.0) -> tuple[pd.DataFrame, dict]:
    """신호로부터 전략 손익을 계산하고 buy & hold 와 비교한다."""
    df = signals.copy()
    # 어제 정한 포지션이 오늘 수익률을 얻는다 (look-ahead 방지)
    pos = df["position"].shift(1).fillna(0.0)
    gross = pos * df["gold_ret"]
    # 거래비용: 포지션 변화량 * 비용
    turnover = pos.diff().abs().fillna(0.0)
    cost = turnover * (cost_bps / 1e4)
    df["strat_ret"] = gross - cost
    df["bh_ret"] = df["gold_ret"]

    df["strat_equity"] = (1 + df["strat_ret"].fillna(0)).cumprod()
    df["bh_equity"] = (1 + df["bh_ret"].fillna(0)).cumprod()

    strat_m = _annualized_metrics(df["strat_ret"])
    bh_m = _annualized_metrics(df["bh_ret"])

    traded = df["strat_ret"][pos != 0]
    win_rate = float((traded > 0).mean()) if len(traded) else float("nan")
    n_trades = int((turnover > 0).sum())

    metrics = {
        "strategy": {
            **strat_m,
            "total_return": float(df["strat_equity"].iloc[-1] - 1),
            "win_rate": win_rate,
            "n_trades": n_trades,
            "exposure": float((pos != 0).mean()),
        },
        "buy_and_hold": {
            **bh_m,
            "total_return": float(df["bh_equity"].iloc[-1] - 1),
        },
    }
    return df, metrics


def latest_recommendation(signals: pd.DataFrame) -> dict:
    """가장 최근 시점의 매매 권고를 dict 로 반환."""
    last = signals.dropna(subset=["score"]).iloc[-1]
    pos = last["position"]
    if pos > 0:
        action = "매수 (BUY / LONG)"
    elif pos < 0:
        action = "매도·숏 (SELL / SHORT)"
    else:
        action = "관망 (HOLD / CASH)"
    return {
        "date": signals.index[-1],
        "gold_price": float(last["gold"]),
        "real_rate": float(last["real_rate"]),
        "dollar": float(last["dollar"]),
        "sig_real_rate": float(last["sig_real_rate"]),
        "sig_dollar": float(last["sig_dollar"]),
        "score": float(last["score"]),
        "action": action,
    }


# ----------------------------------------------------------------------------
# 오케스트레이션
# ----------------------------------------------------------------------------
def run_gold_strategy(cfg: Config, make_plot: bool = True) -> dict:
    """데이터 적재 → 신호 → 백테스트 → 결과/그래프 저장."""
    from pathlib import Path

    from ..config import PROJECT_ROOT

    df = load_macro_data(cfg)
    signals = compute_signals(df, cfg)
    cost_bps = float(cfg["gold_strategy"]["backtest"].get("cost_bps", 1.0))
    bt, metrics = backtest(signals, cost_bps=cost_bps)
    rec = latest_recommendation(signals)

    out_dir = (PROJECT_ROOT / cfg.get("output_dir", "outputs")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    bt.to_csv(out_dir / "gold_strategy_backtest.csv")

    if make_plot:
        try:
            _plot(bt, out_dir)
        except Exception as exc:  # pragma: no cover
            logger.warning("그래프 생성 실패: %s", exc)

    return {"backtest": bt, "metrics": metrics, "recommendation": rec, "out_dir": out_dir}


def _plot(bt: pd.DataFrame, out_dir) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["axes.unicode_minus"] = False
    view = bt.dropna(subset=["score"]).iloc[-500:]

    fig, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True,
                             height_ratios=[2, 1, 1, 1.5])

    ax = axes[0]
    ax.plot(view.index, view["gold"], color="goldenrod", lw=1.2, label="Gold")
    buys = view[view["position"] > view["position"].shift(1).fillna(0)]
    sells = view[view["position"] < view["position"].shift(1).fillna(0)]
    ax.scatter(buys.index, buys["gold"], marker="^", color="green", s=40, label="Buy", zorder=5)
    ax.scatter(sells.index, sells["gold"], marker="v", color="red", s=40, label="Sell", zorder=5)
    ax.set_title("Gold price with macro signals")
    ax.legend(loc="upper left"); ax.grid(alpha=0.3)

    axes[1].plot(view.index, view["real_rate"], color="steelblue", lw=1)
    axes[1].set_title("Real interest rate proxy"); axes[1].grid(alpha=0.3)

    axes[2].plot(view.index, view["dollar"], color="seagreen", lw=1)
    axes[2].set_title("US Dollar index"); axes[2].grid(alpha=0.3)

    ax3 = axes[3]
    ax3.plot(view.index, view["strat_equity"] / view["strat_equity"].iloc[0],
             label="Strategy", color="purple", lw=1.4)
    ax3.plot(view.index, view["bh_equity"] / view["bh_equity"].iloc[0],
             label="Buy & Hold", color="gray", lw=1.2, ls="--")
    ax3.set_title("Equity curve (normalized)")
    ax3.legend(loc="upper left"); ax3.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_dir / "gold_strategy.png", dpi=110)
    plt.close(fig)
