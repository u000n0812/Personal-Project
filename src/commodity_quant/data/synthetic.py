"""오프라인용 합성 원자재 가격 생성기.

네트워크가 차단된 환경에서도 전체 파이프라인을 끝까지 실행/테스트할 수 있도록,
자산군별 특성(추세·변동성·평균회귀·점프·계절성)을 반영한 OHLCV 시계열을 만든다.
실제 시장 데이터는 아니지만 통계적 성질은 어느 정도 흉내 낸다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# 자산군별 일간 수익률 파라미터 (drift/vol 은 일간 기준)
_GROUP_PROFILE = {
    # mu: 연 추세, sigma: 연 변동성, mr: 평균회귀 강도, jump: 점프 확률, season: 계절성 진폭
    "energy": dict(mu=0.05, sigma=0.40, mr=0.02, jump=0.01, season=0.00, base=70.0),
    "precious_metals": dict(mu=0.06, sigma=0.16, mr=0.01, jump=0.003, season=0.00, base=1800.0),
    "industrial_metals": dict(mu=0.04, sigma=0.25, mr=0.015, jump=0.005, season=0.00, base=4.0),
    "agriculture": dict(mu=0.02, sigma=0.28, mr=0.02, jump=0.006, season=0.06, base=500.0),
    "_default": dict(mu=0.03, sigma=0.30, mr=0.01, jump=0.005, season=0.0, base=100.0),
}

_TRADING_DAYS = 252


def generate_prices(
    symbol: str,
    group: str | None = None,
    days: int = 1500,
    end: pd.Timestamp | None = None,
    seed: int | None = None,
) -> pd.DataFrame:
    """단일 심볼에 대한 합성 OHLCV DataFrame 생성.

    Parameters
    ----------
    symbol : 심볼 (시드 안정화에 사용)
    group  : 자산군 이름 (파라미터 프로필 선택)
    days   : 생성할 거래일 수
    end    : 마지막 날짜 (기본: 오늘)
    seed   : 난수 시드 (None 이면 심볼 해시 기반으로 결정적 생성)
    """
    prof = _GROUP_PROFILE.get(group or "_default", _GROUP_PROFILE["_default"])
    if seed is None:
        # 심볼별로 결정적이되 서로 다른 시드
        seed = abs(hash(symbol)) % (2**32)
    rng = np.random.default_rng(seed)

    end = pd.Timestamp(end) if end is not None else pd.Timestamp.today().normalize()
    dates = pd.bdate_range(end=end, periods=days)

    dt = 1.0 / _TRADING_DAYS
    mu = prof["mu"]
    sigma = prof["sigma"]
    mr = prof["mr"]
    jump_p = prof["jump"]
    season_amp = prof["season"]
    log_base = np.log(prof["base"])

    log_p = np.empty(days)
    log_p[0] = log_base
    # 장기 평균 수준(평균회귀 타깃) — 완만한 추세를 가짐
    trend = log_base + mu * dt * np.arange(days)

    for t in range(1, days):
        # 계절성(연간 사인파) — 농산물 등에서 의미
        doy = dates[t].dayofyear
        season = season_amp * np.sin(2 * np.pi * doy / 365.0)
        # 평균회귀 + 추세
        drift = mr * (trend[t] + season - log_p[t - 1])
        shock = sigma * np.sqrt(dt) * rng.standard_normal()
        jump = 0.0
        if rng.random() < jump_p:
            jump = rng.normal(0, sigma * 0.5)  # 가끔 큰 충격
        log_p[t] = log_p[t - 1] + drift + shock + jump

    close = np.exp(log_p)
    # OHLC 를 종가 주변 일중 변동으로 합성
    intraday = np.abs(rng.normal(0, sigma * np.sqrt(dt) * 0.5, days)) * close
    high = close + intraday
    low = close - intraday
    open_ = np.concatenate([[close[0]], close[:-1]]) + rng.normal(0, intraday * 0.3)
    low = np.minimum.reduce([low, open_, close])
    high = np.maximum.reduce([high, open_, close])
    volume = rng.integers(10_000, 200_000, days)

    df = pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        },
        index=dates,
    )
    df.index.name = "Date"
    return df
