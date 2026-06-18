#!/usr/bin/env python3
"""금 매크로 트레이딩 전략 실행 진입점.

금 = f(실질금리, 달러 신뢰) 두 신호를 결합하여 매수/매도를 결정하고 백테스트한다.

사용 예::

    python scripts/run_gold_strategy.py                 # config 기본 소스(synthetic)
    python scripts/run_gold_strategy.py --source yfinance   # 실데이터 (allowlist 필요)
    python scripts/run_gold_strategy.py --no-short          # 숏 금지 (매도=현금)
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from commodity_quant.config import load_config  # noqa: E402
from commodity_quant.strategy import run_gold_strategy  # noqa: E402


def _fmt_metrics(name: str, m: dict) -> str:
    return (
        f"{name:12s} | 연수익 {m['ann_return']:+7.2%} | 변동성 {m['ann_vol']:6.2%} | "
        f"Sharpe {m['sharpe']:5.2f} | MDD {m['max_drawdown']:7.2%} | "
        f"누적 {m['total_return']:+7.2%}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="금 매크로(실질금리+달러) 트레이딩 전략")
    parser.add_argument("--config", default=None)
    parser.add_argument("--source", default=None, choices=["yfinance", "csv", "synthetic"])
    parser.add_argument("--no-short", action="store_true", help="숏 금지 (매도 시 현금 보유)")
    parser.add_argument("--no-plot", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    cfg = load_config(args.config) if args.config else load_config()
    if args.source:
        cfg.raw.setdefault("data", {})["source"] = args.source
    if args.no_short:
        cfg.raw["gold_strategy"]["signal"]["allow_short"] = False

    res = run_gold_strategy(cfg, make_plot=not args.no_plot)
    m = res["metrics"]
    rec = res["recommendation"]

    print("\n=== 금 매크로 전략 백테스트 ===")
    print(_fmt_metrics("전략", m["strategy"]))
    print(_fmt_metrics("Buy&Hold", m["buy_and_hold"]))
    print(f"\n거래 횟수: {m['strategy']['n_trades']} | 승률: {m['strategy']['win_rate']:.1%} | "
          f"시장 노출: {m['strategy']['exposure']:.1%}")

    print("\n=== 현재 매매 권고 ===")
    print(f"기준일      : {rec['date'].date()}")
    print(f"금 가격     : {rec['gold_price']:,.2f}")
    print(f"실질금리    : {rec['real_rate']:.3f}  (신호 {rec['sig_real_rate']:+.2f})")
    print(f"달러 인덱스 : {rec['dollar']:.2f}  (신호 {rec['sig_dollar']:+.2f})")
    print(f"합성 점수   : {rec['score']:+.2f}")
    print(f">>> 결정    : {rec['action']}")
    print(f"\n결과 저장   : {res['out_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
