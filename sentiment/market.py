"""Market-wide Fear & Greed index, per market. Pure pandas (+ one parser).

Method (in the spirit of CNN's index, but fully transparent and available
for Korea too): each component is a daily series where higher means more
greed; each is converted to its percentile within its own trailing year;
the index is the average of the component percentiles (0 = extreme fear,
100 = extreme greed). Every input is a Yahoo Finance price series.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

WINDOW = 252  # each component is judged against its own past year


@dataclass(frozen=True)
class Component:
    key: str
    label: str
    explain: str
    symbols: tuple[str, ...]


SPECS: dict[str, dict] = {
    "NASDAQ": {
        "name": "US market",
        "index_symbol": "^GSPC",
        "stock_benchmark": "^IXIC",
        "components": (
            Component("momentum", "Market momentum",
                      "S&P 500 vs its 125-day average.", ("^GSPC",)),
            Component("strength", "Price strength",
                      "S&P 500 distance from its 52-week high.", ("^GSPC",)),
            Component("volatility", "Volatility (VIX)",
                      "VIX vs its 50-day average — rising fear gauge = fear.", ("^VIX",)),
            Component("safe_haven", "Safe-haven demand",
                      "20-day return of stocks (SPY) minus long Treasuries (TLT).",
                      ("SPY", "TLT")),
            Component("junk", "Junk-bond demand",
                      "20-day return of high-yield (HYG) minus investment-grade bonds (LQD).",
                      ("HYG", "LQD")),
            Component("breadth", "Market breadth",
                      "20-day return of equal-weight (RSP) minus cap-weight S&P 500 (SPY).",
                      ("RSP", "SPY")),
        ),
    },
    "KOSPI": {
        "name": "Korean market",
        "index_symbol": "^KS11",
        "stock_benchmark": "^KS11",
        "components": (
            Component("momentum", "Market momentum",
                      "KOSPI vs its 125-day average.", ("^KS11",)),
            Component("strength", "Price strength",
                      "KOSPI distance from its 52-week high.", ("^KS11",)),
            Component("volatility", "Volatility",
                      "KOSPI 20-day realized volatility — higher = fear.", ("^KS11",)),
            Component("currency", "Won strength",
                      "20-day change in USD/KRW — a weakening won = risk-off.", ("KRW=X",)),
            Component("risk_appetite", "Risk appetite",
                      "20-day return of KOSDAQ minus KOSPI — speculative appetite.",
                      ("^KQ11", "^KS11")),
        ),
    },
}


def symbols_for(market: str) -> list[str]:
    spec = SPECS[market]
    syms = {spec["index_symbol"], spec["stock_benchmark"]}
    for c in spec["components"]:
        syms.update(c.symbols)
    return sorted(syms)


def _ret(s: pd.Series, days: int = 20) -> pd.Series:
    return s / s.shift(days) - 1


def raw_components(close: pd.DataFrame, market: str) -> pd.DataFrame:
    """Component values, higher = greedier, one column per available component."""
    c = close.ffill(limit=5)
    get = lambda sym: c[sym] if sym in c.columns else None  # noqa: E731
    out = {}
    idx = get(SPECS[market]["index_symbol"])
    if idx is not None:
        out["momentum"] = idx / idx.rolling(125, min_periods=100).mean() - 1
        out["strength"] = idx / idx.rolling(WINDOW, min_periods=120).max() - 1
    if market == "NASDAQ":
        vix = get("^VIX")
        if vix is not None:
            out["volatility"] = -(vix / vix.rolling(50, min_periods=40).mean() - 1)
        for key, (a, b) in {"safe_haven": ("SPY", "TLT"), "junk": ("HYG", "LQD"),
                            "breadth": ("RSP", "SPY")}.items():
            if get(a) is not None and get(b) is not None:
                out[key] = _ret(get(a)) - _ret(get(b))
    else:
        if idx is not None:
            out["volatility"] = -(idx.pct_change().rolling(20, min_periods=15).std() * np.sqrt(252))
        krw = get("KRW=X")
        if krw is not None:
            out["currency"] = -_ret(krw)
        kq = get("^KQ11")
        if kq is not None and idx is not None:
            out["risk_appetite"] = _ret(kq) - _ret(idx)
    return pd.DataFrame(out).dropna(how="all")


def fear_greed(close: pd.DataFrame, market: str) -> pd.DataFrame:
    """Daily Fear & Greed history: one 0–100 column per component + 'index'.

    Each component is its percentile within the trailing WINDOW days
    (needs half a window of history); the index averages whatever is present.
    """
    raw = raw_components(close, market)
    # Ties rank at the top ("max"): during a rally "distance from the 52-week
    # high" is 0 on every new-high day, and today's new high should read 100.
    pct = raw.rolling(WINDOW, min_periods=WINDOW // 2).rank(pct=True, method="max") * 100
    pct["index"] = pct.mean(axis=1, skipna=True)
    return pct.dropna(subset=["index"])


def parse_cnn(payload: dict) -> dict | None:
    """CNN's Fear & Greed JSON → {"score", "rating", "previous_1_week", …}."""
    node = (payload or {}).get("fear_and_greed") or {}
    score = node.get("score")
    if score is None:
        return None
    keys = ("previous_close", "previous_1_week", "previous_1_month", "previous_1_year")
    return {"score": float(score), "rating": str(node.get("rating", "")),
            **{k: float(node[k]) for k in keys if isinstance(node.get(k), (int, float))}}
