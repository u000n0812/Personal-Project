"""데이터 수집: yfinance 로 금·실질금리·달러 시계열을 받아온다.

야후 파이낸스 심볼
------------------
- 금        : GC=F      (COMEX 금 선물)
- 실질금리  : ^TNX      (미국 10년물 국채금리 — 실질금리 프록시*)
- 달러 신뢰 : DX-Y.NYB  (ICE 달러 인덱스 — 달러가 강하면 신뢰↑, 약하면 신뢰↓)

* yfinance 에는 진짜 실질금리(TIPS, FRED DFII10)가 없어서 10년물 명목금리를
  프록시로 쓴다. 신호는 z-score(상대적 변화) 기반이라 실용적으로 잘 작동한다.

네트워크가 없거나 야후가 차단된 환경에서는 ``offline=True`` 또는 자동 폴백으로
통계적 성질(상관관계·추세 지속성)을 흉내 낸 데모 데이터를 생성해 전체 로직을
검증할 수 있다. 데모 데이터는 실제 시장 데이터가 아니다.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

# 컬럼 이름 -> 야후 심볼
TICKERS = {
    "gold": "GC=F",
    "real_rate": "^TNX",
    "dollar": "DX-Y.NYB",
}


def fetch_market_data(start: str = "2015-01-01", end: str | None = None) -> pd.DataFrame:
    """yfinance 로 세 시계열의 종가를 받아 하나의 DataFrame 으로 합친다.

    Returns
    -------
    DataFrame(index=날짜, columns=[gold, real_rate, dollar])
    """
    import yfinance as yf

    series = {}
    for name, ticker in TICKERS.items():
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        if df is None or df.empty:
            raise ConnectionError(
                f"'{ticker}' 데이터를 받지 못했습니다. 인터넷 연결을 확인하세요."
            )
        close = df["Close"]
        if isinstance(close, pd.DataFrame):  # yfinance 가 MultiIndex 를 줄 때
            close = close.iloc[:, 0]
        series[name] = close

    out = pd.DataFrame(series)
    # 금리/달러는 휴장일이 달라 결측이 생김 → 직전 값으로 채우고, 금 결측일은 제거
    out[["real_rate", "dollar"]] = out[["real_rate", "dollar"]].ffill()
    out = out.dropna()
    return out


def demo_market_data(days: int = 2000, seed: int = 7) -> pd.DataFrame:
    """오프라인 데모용 합성 데이터 (실제 시장 데이터 아님).

    실제 시장의 핵심 관계를 흉내 낸다:
      금 수익률 ≈ 상수 − β₁·Δ실질금리 − β₂·달러수익률 + 노이즈
    즉 실질금리 상승·달러 강세는 금에 하락 압력.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)

    def ar1(phi: float, sigma: float) -> np.ndarray:
        """자기상관 있는 충격 — 매크로 변수의 '추세 지속성'을 표현."""
        e = np.empty(days)
        e[0] = rng.normal(0, sigma)
        for t in range(1, days):
            e[t] = phi * e[t - 1] + rng.normal(0, sigma)
        return e

    # 실질금리: 평균회귀 + 지속성 있는 충격 + 완만한 레짐 이동
    rate = np.empty(days)
    rate[0] = 1.0
    regime = np.cumsum(rng.normal(0, 0.004, days))
    shock = ar1(phi=0.4, sigma=0.04)
    for t in range(1, days):
        rate[t] = rate[t - 1] + 0.008 * (1.0 + regime[t] - rate[t - 1]) + shock[t]

    # 달러 인덱스: 추세 지속성 있는 수익률
    fx_ret = ar1(phi=0.35, sigma=0.004)
    dollar = 100.0 * np.exp(np.cumsum(fx_ret))

    # 금: 두 동인에 음(-)으로 반응 + 고유 노이즈
    d_rate = np.diff(rate, prepend=rate[0])
    gold_ret = 0.0002 - 1.5 * d_rate * 0.01 - 1.2 * fx_ret + rng.normal(0, 0.007, days)
    gold = 1800.0 * np.exp(np.cumsum(gold_ret))

    return pd.DataFrame({"gold": gold, "real_rate": rate, "dollar": dollar}, index=dates)


def load_data(start: str = "2015-01-01", end: str | None = None,
              offline: bool = False) -> tuple[pd.DataFrame, bool]:
    """데이터 적재. yfinance 실패 시 데모 데이터로 폴백한다.

    Returns
    -------
    (DataFrame, is_real) — is_real=False 면 데모(합성) 데이터라는 뜻.
    """
    if not offline:
        try:
            return fetch_market_data(start, end), True
        except Exception as exc:
            print(f"[경고] yfinance 다운로드 실패: {type(exc).__name__}", file=sys.stderr)
            print("[경고] 인터넷/야후 접근이 막힌 환경입니다. 데모 데이터로 대신 실행합니다.",
                  file=sys.stderr)
            print("[경고] 본인 PC(일반 인터넷)에서 실행하면 자동으로 실데이터를 씁니다.\n",
                  file=sys.stderr)
    return demo_market_data(), False
