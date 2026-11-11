"""Record sentiment for a watchlist — run daily so trends build up.

    python -m sentiment.collect                       # config.SENTIMENT_WATCHLIST
    python -m sentiment.collect --market NASDAQ --tickers NVDA TSLA

Suggested cron (KST): ``30 16 * * 1-5`` for KOSPI, ``30 6 * * 2-6`` for NASDAQ.
Uses the free Yahoo source; KIS keys in .env add Korean investor flows.
"""

from __future__ import annotations

import argparse

import pandas as pd

import config
from data import snapshot
from sentiment import engine, history


def _names(market: str) -> pd.DataFrame | None:
    path = snapshot.latest_path(market)
    return snapshot.load(path)[0] if path else None


def _kis():
    if not config.has_credentials():
        return None
    from pykis import PyKis

    return PyKis(id=config.KIS_ID or None, account=config.ACCOUNT_NO, appkey=config.APP_KEY,
                 secretkey=config.APP_SECRET, keep_token=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--market", nargs="+", choices=list(config.MARKETS),
                        default=list(config.SENTIMENT_WATCHLIST))
    parser.add_argument("--tickers", nargs="+", help="Defaults to the watchlist in config.py.")
    args = parser.parse_args()
    kis = _kis()

    for market in args.market:
        tickers = args.tickers or list(config.SENTIMENT_WATCHLIST.get(market, ()))
        mood = engine.analyze_market("yahoo", market)
        print(f"{market}: market Fear & Greed {mood.latest:.0f}")
        peers = _names(market)
        closes = engine.market_closes("yahoo", market)
        for ticker in tickers:
            name = name_local = ticker
            if peers is not None and ticker in peers.index:
                name = str(peers.at[ticker, "name"])
                name_local = str(peers.get("name_local", peers["name"]).get(ticker, name))
            stock = engine.analyze_stock("yahoo", ticker, market, name, name_local,
                                         kis=kis if market == "KOSPI" else None, closes=closes)
            history.record(stock, mood.latest)
            c = stock.composite
            print(f"  {ticker:8s} {c.index:5.1f} {c.label:14s} families={c.coverage} "
                  f"({', '.join(f'{k} {v:+.2f}' for k, v in c.families.items())})")


if __name__ == "__main__":
    main()
