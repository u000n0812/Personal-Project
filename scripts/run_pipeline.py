#!/usr/bin/env python3
"""Commodity Quant 파이프라인 실행 진입점.

사용 예::

    python scripts/run_pipeline.py                  # config.yaml 전체 실행
    python scripts/run_pipeline.py --symbols GC=F   # 특정 심볼만
    python scripts/run_pipeline.py --source synthetic --no-plots
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# src 레이아웃을 import 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from commodity_quant.config import load_config  # noqa: E402
from commodity_quant.pipeline import run_pipeline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="원자재 가격 추적·예측 파이프라인")
    parser.add_argument("--config", default=None, help="config.yaml 경로")
    parser.add_argument("--symbols", nargs="*", default=None, help="분석할 심볼 (기본: 전체)")
    parser.add_argument("--source", default=None,
                        choices=["yfinance", "csv", "synthetic"],
                        help="데이터 소스 (config 값 덮어쓰기)")
    parser.add_argument("--test-size", type=int, default=None, help="백테스트 검증 구간 길이")
    parser.add_argument("--no-plots", action="store_true", help="그래프 생성 생략")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    cfg = load_config(args.config) if args.config else load_config()
    if args.source:
        cfg.raw.setdefault("data", {})["source"] = args.source
    if args.test_size:
        cfg.raw.setdefault("backtest", {})["test_size"] = args.test_size

    summary = run_pipeline(cfg, symbols=args.symbols, make_plots=not args.no_plots)

    if summary.empty:
        print("결과가 없습니다. 데이터 소스/네트워크 설정을 확인하세요.", file=sys.stderr)
        return 1

    print("\n=== 백테스트 성능 요약 (수익률 모델) ===")
    ret = summary[summary["kind"] == "return"].copy()
    if not ret.empty:
        ret = ret[["symbol", "model", "rmse", "mae", "directional_acc", "n"]]
        print(ret.to_string(index=False))

    vol = summary[summary["kind"] == "volatility"].copy()
    if not vol.empty:
        print("\n=== 변동성 모델(GARCH) ===")
        print(vol[["symbol", "model", "rmse", "mae", "qlike", "n"]].to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
