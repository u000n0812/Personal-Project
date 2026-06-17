"""엔드-투-엔드 파이프라인.

데이터 적재 -> 피처 생성 -> 모델 백테스트(워크-포워드) -> 성능 비교 ->
최우수 모델로 다음 거래일 예측 -> 결과/그래프 저장.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest.evaluator import evaluate_models
from .config import Config, PROJECT_ROOT, load_config
from .data.loader import load_prices
from .features.technical import add_technical_features
from .models import build_model

logger = logging.getLogger(__name__)


def _prepare(symbol: str, cfg: Config) -> pd.DataFrame:
    """심볼의 가격을 받아 피처를 생성한다."""
    raw = load_prices(symbol, cfg)
    feat_cfg = cfg.get("features", {})
    featured = add_technical_features(
        raw,
        ma_windows=feat_cfg.get("ma_windows"),
        rsi_period=feat_cfg.get("rsi_period", 14),
        vol_window=feat_cfg.get("vol_window", 20),
    )
    return featured


def run_symbol(symbol: str, cfg: Config) -> dict:
    """단일 심볼에 대한 전체 분석을 수행하고 결과 dict 를 반환한다."""
    featured = _prepare(symbol, cfg)
    model_names = cfg.get("models", ["naive", "arima", "garch", "xgboost"])
    models = [build_model(name, cfg) for name in model_names]

    bt_cfg = cfg.get("backtest", {})
    summary, predictions = evaluate_models(
        models,
        featured,
        test_size=int(bt_cfg.get("test_size", 120)),
        refit_every=int(bt_cfg.get("refit_every", 5)),
    )
    summary.insert(0, "symbol", symbol)

    # 최우수 수익률 모델(방향 적중률 기준) 선정 후 다음 거래일 예측
    next_forecast = _forecast_next_day(summary, models, featured)

    return {
        "symbol": symbol,
        "name": cfg.symbol_names.get(symbol, symbol),
        "featured": featured,
        "summary": summary,
        "predictions": predictions,
        "next_forecast": next_forecast,
    }


def _forecast_next_day(summary: pd.DataFrame, models, featured: pd.DataFrame) -> dict:
    """수익률 모델 중 방향 적중률이 가장 높은 모델로 다음 거래일을 예측."""
    ret_rows = summary[summary["kind"] == "return"]
    if ret_rows.empty:
        return {}
    best_name = ret_rows.sort_values("directional_acc", ascending=False).iloc[0]["model"]
    best = next((m for m in models if m.name == best_name), None)
    if best is None:
        return {}
    best.fit(featured)
    pred_ret = best.predict_next(featured)
    last_price = float(featured["Close"].iloc[-1])
    pred_price = last_price * float(np.exp(pred_ret))
    return {
        "model": best_name,
        "last_date": featured.index[-1],
        "last_price": last_price,
        "pred_log_return": pred_ret,
        "pred_price": pred_price,
        "direction": "▲ 상승" if pred_ret > 0 else ("▼ 하락" if pred_ret < 0 else "→ 보합"),
    }


def run_pipeline(cfg: Config | None = None, symbols: list[str] | None = None,
                 make_plots: bool = True) -> pd.DataFrame:
    """설정의 모든(또는 지정) 심볼에 대해 파이프라인을 실행한다.

    Returns
    -------
    전체 심볼·모델 성능을 합친 요약 DataFrame.
    """
    cfg = cfg or load_config()
    symbols = symbols or cfg.symbols
    out_dir = (PROJECT_ROOT / cfg.get("output_dir", "outputs")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    all_summaries = []
    forecasts = []
    for sym in symbols:
        try:
            res = run_symbol(sym, cfg)
        except Exception as exc:
            logger.warning("심볼 %s 처리 실패: %s", sym, exc)
            continue
        all_summaries.append(res["summary"])
        if res["next_forecast"]:
            fc = {"symbol": sym, "name": res["name"], **res["next_forecast"]}
            forecasts.append(fc)
        if make_plots:
            try:
                _plot_symbol(res, out_dir)
            except Exception as exc:
                logger.warning("그래프 생성 실패(%s): %s", sym, exc)

    summary = pd.concat(all_summaries, ignore_index=True) if all_summaries else pd.DataFrame()
    if not summary.empty:
        summary.to_csv(out_dir / "backtest_summary.csv", index=False)
    if forecasts:
        fc_df = pd.DataFrame(forecasts)
        fc_df.to_csv(out_dir / "next_day_forecast.csv", index=False)
        _print_forecast_table(fc_df)
    logger.info("결과 저장 위치: %s", out_dir)
    return summary


def _plot_symbol(res: dict, out_dir: Path) -> None:
    """가격 + 예측 비교 그래프를 저장한다."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # 환경에 한글 폰트가 없을 수 있으므로 그래프 라벨은 영문/심볼만 사용한다.
    plt.rcParams["axes.unicode_minus"] = False

    sym = res["symbol"]
    featured = res["featured"]
    preds = res["predictions"]

    fig, axes = plt.subplots(2, 1, figsize=(11, 8), height_ratios=[2, 1])

    ax = axes[0]
    ax.plot(featured.index[-250:], featured["Close"].iloc[-250:], label="price", color="black", lw=1)
    ax.set_title(f"{sym} - recent price")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)

    # 누적 실제 vs 예측 수익률 (방향성 비교)
    ax2 = axes[1]
    any_ret = False
    for name, pdf in preds.items():
        if "actual_return" not in pdf:
            continue
        if not any_ret:
            ax2.plot(pdf.index, pdf["actual_return"].cumsum(), label="actual (cum. return)",
                     color="black", lw=1.5)
            any_ret = True
        # 변동성 모델은 누적 수익률 비교에서 제외
        if name.startswith("garch"):
            continue
        ax2.plot(pdf.index, pdf["pred"].cumsum(), label=f"{name}", lw=1, alpha=0.8)
    ax2.set_title("Backtest: cumulative predicted vs actual return")
    ax2.legend(loc="upper left", fontsize=8)
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    safe = sym.replace("=", "_")
    fig.savefig(out_dir / f"{safe}.png", dpi=110)
    plt.close(fig)


def _print_forecast_table(fc_df: pd.DataFrame) -> None:
    print("\n=== 다음 거래일 예측 ===")
    cols = ["name", "symbol", "model", "last_price", "pred_price", "pred_log_return", "direction"]
    view = fc_df[cols].copy()
    view["last_price"] = view["last_price"].map(lambda x: f"{x:,.2f}")
    view["pred_price"] = view["pred_price"].map(lambda x: f"{x:,.2f}")
    view["pred_log_return"] = view["pred_log_return"].map(lambda x: f"{x:+.4%}")
    print(view.to_string(index=False))
