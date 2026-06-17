"""가격 데이터 적재기.

세 가지 소스를 지원한다:
  * ``yfinance``  — Yahoo Finance 온라인 수집 (네트워크 allowlist 필요)
  * ``csv``       — ``<csv_dir>/<symbol>.csv``
  * ``synthetic`` — 오프라인 합성 데이터

모든 소스는 동일한 형태(OHLCV, DatetimeIndex)의 DataFrame 을 반환한다.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from ..config import Config, PROJECT_ROOT
from . import synthetic

logger = logging.getLogger(__name__)

_OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def _safe_symbol(symbol: str) -> str:
    """파일명으로 안전한 심볼 (``CL=F`` -> ``CL_F``)."""
    return symbol.replace("=", "_").replace("/", "_")


def _from_yfinance(symbol: str, start: str | None, end: str | None) -> pd.DataFrame:
    import yfinance as yf  # 지연 임포트

    df = yf.download(symbol, start=start, end=end, progress=False, auto_adjust=True)
    if df is None or df.empty:
        raise RuntimeError(f"yfinance 에서 '{symbol}' 데이터를 받지 못했습니다 (네트워크/심볼 확인).")
    # yfinance 가 MultiIndex 컬럼을 줄 수 있으므로 평탄화
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def _from_csv(symbol: str, csv_dir: Path) -> pd.DataFrame:
    path = csv_dir / f"{_safe_symbol(symbol)}.csv"
    if not path.exists():
        raise FileNotFoundError(f"CSV 파일이 없습니다: {path}")
    df = pd.read_csv(path, parse_dates=[0], index_col=0)
    df.index.name = "Date"
    return df


def load_prices(symbol: str, cfg: Config, group: str | None = None) -> pd.DataFrame:
    """단일 심볼의 OHLCV DataFrame 을 반환한다.

    캐싱: 한 번 받은 데이터는 ``cache_dir`` 에 parquet 으로 저장하여 재사용한다.
    """
    data_cfg = cfg["data"]
    source = data_cfg.get("source", "synthetic")
    start = data_cfg.get("start")
    end = data_cfg.get("end")
    csv_dir = (PROJECT_ROOT / data_cfg.get("csv_dir", "data")).resolve()
    cache_dir = (PROJECT_ROOT / data_cfg.get("cache_dir", "data/cache")).resolve()

    group = group or cfg.group_of(symbol)

    if source == "synthetic":
        days = int(data_cfg.get("synthetic_days", 1500))
        df = synthetic.generate_prices(symbol, group=group, days=days, end=end)
    elif source == "csv":
        df = _from_csv(symbol, csv_dir)
    elif source == "yfinance":
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{_safe_symbol(symbol)}.parquet"
        if cache_file.exists():
            logger.info("캐시 사용: %s", cache_file)
            df = pd.read_parquet(cache_file)
        else:
            df = _from_yfinance(symbol, start, end)
            try:
                df.to_parquet(cache_file)
            except Exception as exc:  # parquet 엔진 미설치 등
                logger.warning("캐시 저장 실패(%s): %s", cache_file, exc)
    else:
        raise ValueError(f"알 수 없는 data.source: {source!r}")

    # 표준화: OHLCV 컬럼만, 결측 제거, 정렬
    keep = [c for c in _OHLCV if c in df.columns]
    df = df[keep].sort_index().dropna(subset=["Close"])
    return df


def load_panel(cfg: Config, symbols: list[str] | None = None) -> dict[str, pd.DataFrame]:
    """여러 심볼을 한 번에 적재하여 ``{symbol: DataFrame}`` 으로 반환."""
    symbols = symbols or cfg.symbols
    panel: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            panel[sym] = load_prices(sym, cfg)
        except Exception as exc:
            logger.warning("'%s' 적재 실패: %s", sym, exc)
    return panel
