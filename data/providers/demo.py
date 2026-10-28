"""Synthetic provider: same interface as the Yahoo provider, deterministic
demo data, no network. Used when forced from the sidebar or when public
data sources are unreachable."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

import config
from data import synthetic
from data.providers.base import CompanyData, Quote, session_close

# Synthetic paths are KRW-scaled; scale NASDAQ names to dollar-like prices.
_PRICE_SCALE = {"KOSPI": 1.0, "NASDAQ": 1 / 400}


class SyntheticProvider:
    name = "Synthetic"

    def listing(self, market: str) -> pd.DataFrame:
        names = config.SCREEN_UNIVERSE if market == "KOSPI" else synthetic.SYNTHETIC_NASDAQ
        out = pd.DataFrame({"ticker": list(names), "name": list(names.values())})
        out["market_cap"] = np.linspace(4e11, 1e10, len(out))  # listing order = cap order
        return out

    def company(self, ticker: str, market: str) -> CompanyData:
        listing = self.listing(market).set_index("ticker")
        if ticker not in listing.index:  # don't invent data for unknown tickers
            raise LookupError(f"{ticker} isn't in the synthetic {market} universe")
        metrics = synthetic.generate_fundamentals([ticker]).iloc[0].to_dict()
        cap = listing.at[ticker, "market_cap"] * (1.0 if market == "KOSPI" else 1 / 400)
        return CompanyData(
            ticker=ticker, market=market, name=listing.at[ticker, "name"],
            sector=synthetic.synthetic_sector(ticker),
            currency=config.MARKETS[market]["currency"],
            market_cap=float(cap), metrics=metrics,
            notes={k: "Synthetic demo value." for k in metrics},
        )

    def closes(self, tickers: list[str], market: str, start: pd.Timestamp) -> pd.DataFrame:
        end = pd.Timestamp.today().normalize()
        scale = _PRICE_SCALE[market]
        frame = pd.DataFrame({t: synthetic.generate_ohlcv(t, start, end)["close"] * scale
                              for t in tickers})
        return frame.sort_index()

    def quote(self, ticker: str, market: str) -> Quote:
        close = self.closes([ticker], market, pd.Timestamp.today() - pd.Timedelta(days=14))[ticker]
        close = close.dropna()
        # Only completed sessions: today's bar counts once the market has closed.
        now = datetime.now(tz=session_close(close.index[-1], market).tzinfo)
        close = close[[session_close(d, market) <= now for d in close.index]]
        last_day = close.index[-1]
        as_of: datetime = session_close(last_day, market)
        return Quote(price=float(close.iloc[-1]), prev_close=float(close.iloc[-2]),
                     as_of=as_of, source=self.name,
                     currency=config.MARKETS[market]["currency"])
