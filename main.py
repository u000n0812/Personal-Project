#!/usr/bin/env python3
"""금 트레이딩 알고리즘 — 실행 진입점.

실질금리(↓=매수)와 달러 신뢰(약세=매수) 두 매크로 신호를 합쳐
금(GC=F)을 사고파는 전략을 백테스트하고, 오늘의 매매 권고를 출력한다.

사용법 (PowerShell / 터미널 공통):

    python main.py                    # 기본 실행 (2015년~현재, yfinance)
    python main.py --start 2020-01-01 # 시작일 변경
    python main.py --no-short         # 숏 금지 (매도 신호 = 현금 보유)
    python main.py --offline          # 인터넷 없이 데모 데이터로 실행

`python` 이 안 되면 `py main.py` 로 실행하세요 (Windows).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from gold_quant.backtest import run_backtest
from gold_quant.charts import save_report_chart
from gold_quant.data import load_data
from gold_quant.signals import Params, compute_signals, current_recommendation

OUT_DIR = Path(__file__).resolve().parent / "outputs"


def _print_metrics(name: str, m: dict) -> None:
    print(f"  {name:10s} | 연수익 {m['ann_return']:+7.2%} | 변동성 {m['ann_vol']:6.2%}"
          f" | Sharpe {m['sharpe']:5.2f} | 최대낙폭 {m['max_drawdown']:7.2%}"
          f" | 누적 {m['total_return']:+8.2%}")


def main() -> int:
    parser = argparse.ArgumentParser(description="실질금리+달러 기반 금 트레이딩 알고리즘")
    parser.add_argument("--start", default="2015-01-01", help="데이터 시작일 (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="데이터 종료일 (기본: 오늘)")
    parser.add_argument("--no-short", action="store_true", help="숏 금지(매도 신호 시 현금)")
    parser.add_argument("--cost-bps", type=float, default=1.0, help="거래비용 (bps, 기본 1)")
    parser.add_argument("--offline", action="store_true", help="데모 데이터로 실행(인터넷 불필요)")
    args = parser.parse_args()

    # 1) 데이터 -----------------------------------------------------------
    print("데이터 다운로드 중 (금 GC=F / 금리 ^TNX / 달러 DX-Y.NYB)...")
    data, is_real = load_data(start=args.start, end=args.end, offline=args.offline)
    label = "실데이터(yfinance)" if is_real else "데모 데이터(합성)"
    print(f"  → {label}, {len(data):,}일 ({data.index[0].date()} ~ {data.index[-1].date()})")

    # 2) 신호 -------------------------------------------------------------
    params = Params(allow_short=not args.no_short)
    signals = compute_signals(data, params)

    # 3) 백테스트 ----------------------------------------------------------
    bt, metrics = run_backtest(signals, cost_bps=args.cost_bps)

    print("\n=== 백테스트 성과 ===")
    _print_metrics("전략", metrics["strategy"])
    _print_metrics("Buy&Hold", metrics["buy_and_hold"])
    s = metrics["strategy"]
    print(f"\n  거래 횟수 {s['n_trades']}회 | 승률 {s['win_rate']:.1%}"
          f" | 시장 노출 {s['exposure']:.1%}")

    # 4) 오늘의 권고 --------------------------------------------------------
    rec = current_recommendation(signals)
    print("\n=== 오늘의 매매 권고 ===")
    print(f"  기준일       : {rec['date'].date()}")
    print(f"  금 가격      : {rec['gold_price']:,.2f}")
    print(f"  실질금리     : {rec['real_rate']:.3f}%  → 신호 {rec['sig_real_rate']:+.2f}")
    print(f"  달러 인덱스  : {rec['dollar']:.2f}  → 신호 {rec['sig_dollar']:+.2f}")
    print(f"  합성 점수    : {rec['score']:+.2f}  (임계값 ±{params.entry_threshold})")
    print(f"  >>> 결정     : {rec['action']}")

    # 5) 결과 저장 ----------------------------------------------------------
    OUT_DIR.mkdir(exist_ok=True)
    bt.to_csv(OUT_DIR / "backtest_result.csv")
    chart = save_report_chart(bt, OUT_DIR / "gold_report.png")
    print(f"\n결과 저장: {OUT_DIR / 'backtest_result.csv'}")
    print(f"차트 저장: {chart}")
    if not is_real:
        print("\n※ 데모 데이터 결과입니다. 실데이터는 인터넷 연결된 PC에서 실행하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
