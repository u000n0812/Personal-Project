"""Orchestration: gather readings for a stock, compute market mood.

No Streamlit here; the page wraps these in caches, and the collector CLI calls
them directly. Each source runs in isolation — one failing source becomes an
"error" reading and never blocks the others.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import pandas as pd

import config
from data.providers import get_provider
from sentiment import sources as src
from sentiment import synthetic
from sentiment.market import SPECS, fear_greed, parse_cnn, symbols_for
from sentiment.model import Composite, Reading, aggregate
from sentiment.price import excess_returns, relative_components, relative_history

HISTORY_DAYS = 800       # enough for a 252-day percentile window plus a year of index
CNN_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"


@dataclass
class MarketSentiment:
    market: str
    name: str
    history: pd.DataFrame            # components (0–100) + "index", daily
    cnn: dict | None = None          # external reference (US only)

    @property
    def latest(self) -> float:
        return float(self.history["index"].iloc[-1]) if len(self.history) else float("nan")

    def change(self, days: int) -> float:
        s = self.history["index"]
        return float(s.iloc[-1] - s.iloc[-1 - days]) if len(s) > days else float("nan")


@dataclass
class StockSentiment:
    ticker: str
    market: str
    name: str
    composite: Composite
    price_history: pd.Series                        # daily Price-family score, [-1, 1]
    price_detail: dict = field(default_factory=dict)
    as_of: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _safe(source: str, family: str, fn: Callable[[], Reading]) -> Reading:
    try:
        return fn()
    except Exception as err:  # noqa: BLE001 — isolate every source
        return src.failed(source, family, err)


def market_closes(provider_name: str, market: str) -> pd.DataFrame:
    start = pd.Timestamp.today().normalize() - pd.Timedelta(days=HISTORY_DAYS)
    return get_provider(provider_name).raw_closes(symbols_for(market), start)


def fetch_cnn() -> dict | None:
    import requests

    r = requests.get(CNN_URL, timeout=src.TIMEOUT, headers={"User-Agent": src.BROWSER_UA})
    r.raise_for_status()
    return parse_cnn(r.json())


def analyze_market(provider_name: str, market: str, closes: pd.DataFrame | None = None
                   ) -> MarketSentiment:
    closes = market_closes(provider_name, market) if closes is None else closes
    history = fear_greed(closes, market)
    cnn = None
    if market == "NASDAQ" and provider_name != "synthetic":
        try:
            cnn = fetch_cnn()
        except Exception:  # noqa: BLE001 — optional cross-check only
            cnn = None
    return MarketSentiment(market, SPECS[market]["name"], history, cnn)


def price_reading(stock: pd.Series, benchmark: pd.Series) -> tuple[Reading, pd.Series, dict]:
    hist = relative_history(stock, benchmark)
    if hist.empty:
        return (Reading("Price vs market", "Price", status="unavailable",
                        note="Not enough price history."), hist, {})
    comps = relative_components(stock, benchmark).iloc[-1]
    detail = {"rsi_rel": float(comps["rsi"] * 50 + 50), "range_pos": float((comps["range"] + 1) / 2),
              **{f"excess_{k}": v for k, v in excess_returns(stock, benchmark).items()}}
    note = (f"Relative RSI {detail['rsi_rel']:.0f}, {detail['range_pos']:.0%} of 52-week "
            "relative range" + "".join(f", {k} excess {v:+.1%}" for k, v in
                                        excess_returns(stock, benchmark).items()))
    # Daily computation from prices: plenty of evidence, no shrinkage needed.
    return (Reading("Price vs market", "Price", score=float(hist.iloc[-1]), n=1000.0,
                    detail=detail, note=note), hist, detail)


def analyze_stock(provider_name: str, ticker: str, market: str, name: str,
                  name_local: str = "", kis=None, closes: pd.DataFrame | None = None
                  ) -> StockSentiment:
    """All readings for one stock + the family-balanced composite."""
    provider = get_provider(provider_name)
    start = pd.Timestamp.today().normalize() - pd.Timedelta(days=HISTORY_DAYS)
    bench_symbol = SPECS[market]["stock_benchmark"]
    bench = (closes if closes is not None else
             provider.raw_closes([bench_symbol], start))[bench_symbol]
    stock = provider.closes([ticker], market, start)[ticker]
    price, price_hist, price_detail = price_reading(stock.dropna(), bench.dropna())

    if provider_name == "synthetic":
        readings = synthetic.readings(ticker, market, name_local or name) + [price]
        return StockSentiment(ticker, market, name, aggregate(readings), price_hist, price_detail)

    readings = [price,
                _safe("News headlines", "News", lambda: src.fetch_news(name, name_local, market))]
    import yfinance as yf

    from data.providers.yahoo import yahoo_symbol

    t = yf.Ticker(yahoo_symbol(ticker, market))
    readings.append(_safe("Analyst ratings", "Analysts",
                          lambda: src.parse_analysts(t.recommendations, t.upgrades_downgrades)))
    if market == "NASDAQ":
        readings += [
            _safe("StockTwits", "Crowd", lambda: src.fetch_stocktwits(ticker)),
            _safe("Reddit", "Crowd", lambda: src.fetch_reddit(
                ticker, name, config.REDDIT_CLIENT_ID, config.REDDIT_CLIENT_SECRET,
                config.REDDIT_SUBREDDITS)),
            _safe("Options put/call", "Positioning", lambda: src.fetch_options(t)),
            _safe("Short interest", "Positioning", lambda: src.parse_short_interest(t.info)),
        ]
    else:
        readings += [
            src.not_applicable("StockTwits", "Crowd", "StockTwits covers US-listed symbols."),
            _safe("Reddit", "Crowd", lambda: src.fetch_reddit(
                ticker, name, config.REDDIT_CLIENT_ID, config.REDDIT_CLIENT_SECRET,
                config.REDDIT_SUBREDDITS)),
            (_safe("Investor flows (KIS)", "Positioning",
                   lambda: src.fetch_kis_investor(kis, ticker)) if kis is not None else
             Reading("Investor flows (KIS)", "Positioning", status="unavailable",
                     note="Add KIS API keys to .env for foreign/institutional flows.")),
        ]
    return StockSentiment(ticker, market, name, aggregate(readings), price_hist, price_detail)


def daily_item_scores(composite: Composite) -> pd.DataFrame:
    """Per-day mean score and count of timestamped crowd/news items — the
    part of the text history that can be reconstructed after the fact."""
    rows = [{"date": pd.Timestamp(i["time"]).tz_convert(None).normalize(), "score": i["score"]}
            for r in composite.readings if r.ok and r.family in ("Crowd", "News")
            for i in r.items if isinstance(i.get("time"), datetime)]
    if not rows:
        return pd.DataFrame(columns=["score", "count"])
    df = pd.DataFrame(rows)
    return df.groupby("date")["score"].agg(score="mean", count="size")


__all__ = ["MarketSentiment", "StockSentiment", "analyze_market", "analyze_stock",
           "market_closes", "daily_item_scores"]
