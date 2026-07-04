"""결과 차트 (matplotlib, PNG 저장).

색·마크 규칙은 검증된 데이터-시각화 팔레트를 따른다:
카테고리 색은 고정 슬롯(파랑/아쿠아/노랑)으로 시리즈에 고정하고,
매수/매도는 상태색(초록/빨강) + 서로 다른 도형(▲/▼)으로 색맹에도 안전하게 표시.
격자선은 실선 헤어라인, 축은 서브플롯당 1개(이중축 금지).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 화면 없는 환경에서도 파일 저장 가능
import matplotlib.pyplot as plt
import pandas as pd

# ---- 팔레트 (light mode) ----
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
GOLD = "#eda100"      # 슬롯3(노랑) — 금 가격
BLUE = "#2a78d6"      # 슬롯1(파랑) — 실질금리 / 전략 자산곡선
AQUA = "#1baf7a"      # 슬롯2(아쿠아) — 달러 인덱스
BUY = "#0ca30c"       # 상태색: 매수
SELL = "#d03b3b"      # 상태색: 매도


def _style_axis(ax, title: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=11, color=INK, fontweight="bold", pad=8)
    ax.grid(True, color=GRID, linewidth=0.8)  # 실선 헤어라인
    ax.tick_params(colors=MUTED, labelsize=8.5)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)
        ax.spines[side].set_linewidth(0.8)


def save_report_chart(bt: pd.DataFrame, out_path: str | Path,
                      last_n_days: int = 500) -> Path:
    """4단 리포트 차트를 PNG 로 저장한다.

    (1) 금 가격 + 매수/매도 시점  (2) 실질금리  (3) 달러 인덱스
    (4) 전략 vs Buy&Hold 자산곡선 (시작=100 으로 지수화, 축 1개)
    """
    view = bt.dropna(subset=["score"]).iloc[-last_n_days:]

    fig, axes = plt.subplots(
        4, 1, figsize=(11, 11), sharex=True,
        height_ratios=[2.2, 1, 1, 1.6], facecolor=SURFACE,
    )

    # (1) 금 가격 + 매매 시점 -------------------------------------------------
    ax = axes[0]
    _style_axis(ax, "Gold price (GC=F) — buy ▲ / sell ▼ markers")
    ax.plot(view.index, view["gold"], color=GOLD, lw=1.8)
    pos_change = view["position"].diff().fillna(0)
    buys = view[(pos_change > 0) & (view["position"] > 0)]
    sells = view[(pos_change < 0) & (view["position"] < 0)]
    exits = view[(view["position"] == 0) & (pos_change != 0)]
    ax.scatter(buys.index, buys["gold"], marker="^", s=48, color=BUY,
               edgecolors=SURFACE, linewidths=1, zorder=5, label="Buy")
    ax.scatter(sells.index, sells["gold"], marker="v", s=48, color=SELL,
               edgecolors=SURFACE, linewidths=1, zorder=5, label="Sell/Short")
    ax.scatter(exits.index, exits["gold"], marker="o", s=22, color=MUTED,
               edgecolors=SURFACE, linewidths=1, zorder=4, label="Exit")
    ax.legend(loc="upper left", fontsize=8.5, frameon=False, labelcolor=INK_2)

    # (2) 실질금리 ------------------------------------------------------------
    ax = axes[1]
    _style_axis(ax, "Driver 1 — real interest rate proxy (^TNX, %)")
    ax.plot(view.index, view["real_rate"], color=BLUE, lw=1.6)

    # (3) 달러 인덱스 ----------------------------------------------------------
    ax = axes[2]
    _style_axis(ax, "Driver 2 — US dollar index (DX-Y.NYB)")
    ax.plot(view.index, view["dollar"], color=AQUA, lw=1.6)

    # (4) 자산곡선 (동일 축, 시작=100 지수화) -----------------------------------
    ax = axes[3]
    _style_axis(ax, "Equity curve — strategy vs buy & hold (start = 100)")
    strat = 100 * view["strat_equity"] / view["strat_equity"].iloc[0]
    bh = 100 * view["bh_equity"] / view["bh_equity"].iloc[0]
    ax.plot(view.index, strat, color=BLUE, lw=1.8, label="Strategy")
    ax.plot(view.index, bh, color=MUTED, lw=1.6, label="Buy & Hold")
    # 끝값만 선택적 직접 라벨
    ax.annotate(f"{strat.iloc[-1]:.0f}", (view.index[-1], strat.iloc[-1]),
                xytext=(6, 0), textcoords="offset points",
                color=INK, fontsize=8.5, fontweight="bold", va="center")
    ax.annotate(f"{bh.iloc[-1]:.0f}", (view.index[-1], bh.iloc[-1]),
                xytext=(6, 0), textcoords="offset points",
                color=INK_2, fontsize=8.5, va="center")
    ax.legend(loc="upper left", fontsize=8.5, frameon=False, labelcolor=INK_2)

    fig.align_ylabels(axes)
    fig.tight_layout()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return out_path
