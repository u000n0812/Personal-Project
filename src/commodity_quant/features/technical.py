"""기술적 지표 기반 피처 생성.

머신러닝 모델(XGBoost 등)의 입력으로 쓰일 피처를 만든다.
모든 피처는 *과거 정보만* 사용하도록 구성하여 look-ahead bias 를 피한다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def log_returns(close: pd.Series) -> pd.Series:
    """로그 수익률 r_t = ln(P_t / P_{t-1})."""
    return np.log(close).diff()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI (Relative Strength Index)."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD 라인과 시그널 라인."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame({"macd": macd_line, "macd_signal": signal_line,
                         "macd_hist": macd_line - signal_line})


def add_technical_features(
    df: pd.DataFrame,
    ma_windows: list[int] | None = None,
    rsi_period: int = 14,
    vol_window: int = 20,
) -> pd.DataFrame:
    """OHLCV DataFrame 에 기술적 피처를 추가하여 반환한다.

    생성 피처:
      - log_return            : 당일 로그 수익률 (타깃 계산 기반)
      - ret_lag_{1..5}        : 과거 수익률 래그
      - ma_{w}, ma_ratio_{w}  : 이동평균 및 종가/이동평균 비율
      - vol_{w}               : 수익률 롤링 표준편차(변동성)
      - rsi                   : RSI
      - macd, macd_signal, macd_hist
      - volume_z              : 거래량 z-score
    """
    ma_windows = ma_windows or [5, 10, 20, 60]
    out = df.copy()
    close = out["Close"]

    out["log_return"] = log_returns(close)

    # 과거 수익률 래그
    for lag in range(1, 6):
        out[f"ret_lag_{lag}"] = out["log_return"].shift(lag)

    # 이동평균 및 비율
    for w in ma_windows:
        ma = close.rolling(w).mean()
        out[f"ma_{w}"] = ma
        out[f"ma_ratio_{w}"] = close / ma - 1.0

    # 변동성
    out[f"vol_{vol_window}"] = out["log_return"].rolling(vol_window).std()

    # RSI / MACD
    out["rsi"] = rsi(close, rsi_period)
    out = out.join(macd(close))

    # 거래량 z-score (있을 때만)
    if "Volume" in out.columns:
        v = out["Volume"]
        out["volume_z"] = (v - v.rolling(vol_window).mean()) / v.rolling(vol_window).std()

    return out


def feature_columns(df: pd.DataFrame) -> list[str]:
    """모델 입력으로 사용할 피처 컬럼 목록 (원시 OHLCV/타깃 제외)."""
    exclude = {"Open", "High", "Low", "Close", "Volume", "log_return"}
    exclude |= {c for c in df.columns if c.startswith("ma_") and not c.startswith("ma_ratio")}
    return [c for c in df.columns if c not in exclude]
