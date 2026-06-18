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


def _ohlcv_from_close(close: np.ndarray, dates: pd.DatetimeIndex,
                      rng: np.random.Generator, vol: float) -> pd.DataFrame:
    """종가 배열로부터 그럴듯한 OHLCV DataFrame 을 합성한다."""
    intraday = np.abs(rng.normal(0, vol * 0.5, len(close))) * close
    open_ = np.concatenate([[close[0]], close[:-1]]) + rng.normal(0, intraday * 0.3)
    low = np.minimum.reduce([close - intraday, open_, close])
    high = np.maximum.reduce([close + intraday, open_, close])
    volume = rng.integers(50_000, 300_000, len(close))
    df = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )
    df.index.name = "Date"
    return df


def generate_gold_macro(
    days: int = 1500,
    end: pd.Timestamp | None = None,
    seed: int = 7,
) -> dict[str, pd.DataFrame]:
    """금-매크로 전략용 *상관관계가 있는* 합성 데이터 생성.

    실제 시장의 핵심 관계를 흉내 낸다::

        금 수익률 ≈ drift - β_r · Δ(실질금리) - β_d · (달러 수익률) + 노이즈

    즉 실질금리가 오르거나 달러가 강해지면 금은 하락 압력을 받는다.
    반환 dict 키: ``gold`` (OHLCV), ``real_rate`` (Close=금리%), ``dollar`` (OHLCV).
    """
    rng = np.random.default_rng(seed)
    end = pd.Timestamp(end) if end is not None else pd.Timestamp.today().normalize()
    dates = pd.bdate_range(end=end, periods=days)

    # AR(1) 자기상관 충격 — 매크로 변수는 추세가 며칠씩 지속되는 성질이 있다.
    # 이 지속성이 있어야 추세/모멘텀 기반 매매 신호가 예측력을 가진다(실데이터도 마찬가지).
    def _ar1(phi: float, sigma: float) -> np.ndarray:
        e = np.empty(days)
        e[0] = rng.normal(0, sigma)
        for t in range(1, days):
            e[t] = phi * e[t - 1] + rng.normal(0, sigma)
        return e

    # --- 실질금리: 평균회귀(OU) + 자기상관 충격, 장기평균 1.0%, 레짐 이동 ---
    rr = np.empty(days)
    rr[0] = 1.0
    kappa, rr_mu = 0.008, 1.0
    regime = np.cumsum(rng.normal(0, 0.004, days))   # 완만한 장기 추세
    rr_shock = _ar1(phi=0.4, sigma=0.04)              # 며칠 지속되는 금리 충격
    for t in range(1, days):
        rr[t] = rr[t - 1] + kappa * (rr_mu + regime[t] - rr[t - 1]) + rr_shock[t]
    d_rr = np.diff(rr, prepend=rr[0])

    # --- 달러 인덱스: 자기상관(추세) 있는 수익률 ---
    dxy_ret = _ar1(phi=0.35, sigma=0.004)
    dxy_ret[0] = 0.0
    dxy = 100.0 * np.exp(np.cumsum(dxy_ret))

    # --- 금: 실질금리 변화·달러에 음의 반응 + 노이즈 ---
    beta_r, beta_d = 1.5, 1.2
    gold_ret = 0.0002 - beta_r * d_rr * 0.01 - beta_d * dxy_ret + rng.normal(0, 0.007, days)
    gold_ret[0] = 0.0
    gold = 1800.0 * np.exp(np.cumsum(gold_ret))

    return {
        "gold": _ohlcv_from_close(gold, dates, rng, vol=0.007),
        "real_rate": pd.DataFrame({"Close": rr}, index=dates).rename_axis("Date"),
        "dollar": _ohlcv_from_close(dxy, dates, rng, vol=0.004),
    }
