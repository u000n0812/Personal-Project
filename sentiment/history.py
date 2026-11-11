"""Daily sentiment records, so changes can be tracked over time.

One row per (date, market, ticker) in ``<SENTIMENT_DIR>/history.parquet``,
re-recording the same day overwrites it. The page records each live
analysis; ``python -m sentiment.collect`` records a watchlist on a schedule.
Synthetic (demo) readings are never recorded.
"""

from __future__ import annotations

import pandas as pd

import config
from sentiment.model import FAMILIES, to_index


def _path():
    return config.SENTIMENT_DIR / "history.parquet"


def row(stock, market_index: float) -> dict:
    c = stock.composite
    out = {
        "date": pd.Timestamp(stock.as_of).tz_convert(None).normalize(),
        "market": stock.market, "ticker": stock.ticker, "index": c.index,
        "coverage": c.coverage, "agreement": c.agreement, "bull_ratio": c.bull_ratio,
        "bull_n": c.bull_n, "attention": c.attention, "market_index": market_index,
    }
    for fam in FAMILIES:
        out[f"family_{fam}"] = to_index(c.families[fam]) if fam in c.families else float("nan")
    for r in c.readings:
        out[f"source_{r.source}"] = to_index(r.score) if r.ok else float("nan")
    return out


def record(stock, market_index: float) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    new = pd.DataFrame([row(stock, market_index)])
    if path.exists():
        old = pd.read_parquet(path)
        key = ["date", "market", "ticker"]
        old = old.merge(new[key], on=key, how="left", indicator=True)
        old = old[old["_merge"] == "left_only"].drop(columns="_merge")
        new = pd.concat([old, new], ignore_index=True)
    new.sort_values(["market", "ticker", "date"]).to_parquet(path, index=False)


def load(ticker: str, market: str) -> pd.DataFrame:
    path = _path()
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df = df[(df["ticker"] == ticker) & (df["market"] == market)]
    return df.set_index("date").sort_index()
