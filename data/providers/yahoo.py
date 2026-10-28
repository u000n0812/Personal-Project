"""Free public-data provider — no API keys.

* Listings: FinanceDataReader (KRX listing cache for KOSPI; Naver's
  market-value ranking for NASDAQ).
* Prices, fundamentals, analyst estimates: Yahoo Finance via yfinance.
  US quotes are near real-time; KRX quotes on Yahoo are delayed ~20 min.
  Every quote carries its own timestamp, and the UI labels freshness from it.

Free sources have no consensus *revision history* and no Korean
foreign-ownership series, so a few inputs are proxies or unavailable — see
``PROXY_NOTES``; the UI shows these notes next to the values.

Network I/O lives in ``YahooProvider``; ``metrics_from_yahoo`` is a pure
function over yfinance-shaped inputs so it can be tested offline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data.providers.base import CompanyData, Quote, session_close

PROXY_NOTES: dict[str, str] = {
    "fwd_revenue_revision": "Proxy: consensus revenue growth for next fiscal year "
                            "(revision history isn't available from free sources).",
    "fwd_op_margin_change": "Proxy: change in operating margin over the last two "
                            "fiscal years (trailing, not forward).",
    "fwd_op_margin": "Proxy: trailing-12M operating margin.",
    "foreign_own_chg_3m": "Not available from free sources.",
    "dividend_yield": "Non-payers count as 0%.",
    "roic": "EBIT × (1 − tax rate) / invested capital, latest fiscal year.",
}

NAN = float("nan")
_DEFAULT_TAX_RATE = 0.25  # when Yahoo has no effective rate for ROIC


def yahoo_symbol(ticker: str, market: str) -> str:
    """KRX code → Yahoo symbol ('005930' → '005930.KS'); US class shares use '-'."""
    return f"{ticker}.KS" if market == "KOSPI" else ticker.replace(".", "-")


def is_common_share(code: str) -> bool:
    """KRX common shares end in 0; preferred classes end in 5/7/9/K."""
    return str(code)[-1:] == "0"


# ---------------------------------------------------------------------------
# Pure parsing
# ---------------------------------------------------------------------------


def _num(value) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return NAN
    return out if np.isfinite(out) else NAN


def _div(a: float, b: float) -> float:
    return a / b if b and not np.isnan(a) and not np.isnan(b) else NAN


def _rows(df: pd.DataFrame | None, *names: str) -> pd.Series:
    """First statement row present, newest fiscal period first."""
    if df is None or df.empty:
        return pd.Series(dtype=float)
    for name in names:
        if name in df.index:
            row = pd.to_numeric(df.loc[name], errors="coerce")
            return row.sort_index(ascending=False)
    return pd.Series(dtype=float)


def _latest(df: pd.DataFrame | None, *names: str) -> float:
    row = _rows(df, *names).dropna()
    return float(row.iloc[0]) if len(row) else NAN


def _estimate(df: pd.DataFrame | None, column: str, periods=("+1y", "0y")) -> float:
    if df is None or df.empty or column not in df.columns:
        return NAN
    for period in periods:
        if period in df.index and not pd.isna(df.at[period, column]):
            return _num(df.at[period, column])
    return NAN


def metrics_from_yahoo(
    info: dict,
    income: pd.DataFrame | None,
    balance: pd.DataFrame | None,
    eps_trend: pd.DataFrame | None,
    revenue_estimate: pd.DataFrame | None,
    fx: float = 1.0,
) -> dict[str, float]:
    """Factor inputs from yfinance payloads.

    ``fx`` converts the *financial-statement* currency into the *quote*
    currency (they differ for ADRs, e.g. a TWD reporter quoted in USD), so
    yields are computed as aggregate / market cap in one currency. Ratios of
    same-currency figures (margins, ROE, ROIC, D/E) need no conversion.
    """
    g = lambda key: _num(info.get(key))  # noqa: E731
    mcap = g("marketCap")
    price = g("currentPrice") if not np.isnan(g("currentPrice")) else g("regularMarketPrice")

    equity = _latest(balance, "StockholdersEquity", "CommonStockEquity")
    debt = _latest(balance, "TotalDebt")
    invested = _latest(balance, "InvestedCapital")
    ebit = _latest(income, "EBIT", "OperatingIncome")
    tax = _latest(income, "TaxRateForCalcs")
    tax = _DEFAULT_TAX_RATE if np.isnan(tax) else float(np.clip(tax, 0.0, 0.5))

    margins = (_rows(income, "OperatingIncome") / _rows(income, "TotalRevenue")).dropna()
    margins = margins.sort_index(ascending=False)

    dps = g("dividendRate")
    if np.isnan(dps):
        dps = g("trailingAnnualDividendRate")
    dividend_yield = _div(dps, price) if not np.isnan(dps) else (0.0 if info else NAN)

    # Forward-12M EPS vs trailing; growth off a loss-making base is meaningless.
    trailing_eps, forward_eps = g("trailingEps"), g("forwardEps")
    eps_growth = forward_eps / trailing_eps - 1.0 if trailing_eps > 0 else NAN

    revision = NAN
    if eps_trend is not None and not eps_trend.empty and "30daysAgo" in eps_trend.columns:
        for period in ("+1y", "0y"):
            if period in eps_trend.index:
                now, before = _num(eps_trend.at[period, "current"]), _num(eps_trend.at[period, "30daysAgo"])
                if not np.isnan(now) and before:
                    revision = (now - before) / abs(before)
                    break

    if not np.isnan(equity) and equity != 0 and not np.isnan(debt):
        debt_to_equity = debt / equity
    else:
        debt_to_equity = g("debtToEquity") / 100.0  # Yahoo reports this one in %

    book = equity if not np.isnan(equity) else g("bookValue") * g("sharesOutstanding")
    return {
        "earnings_yield": _div(g("netIncomeToCommon") * fx, mcap),
        "dividend_yield": dividend_yield,
        "book_to_market": _div(book * fx, mcap),
        "cash_flow_yield": _div(g("operatingCashflow") * fx, mcap),
        "fwd_revenue_revision": _estimate(revenue_estimate, "growth"),
        "fwd_op_margin_change": float(margins.iloc[0] - margins.iloc[1]) if len(margins) > 1 else NAN,
        "fwd_eps_growth": eps_growth,
        "long_term_growth": NAN,  # derived in factors.scoring from roe × (1 − payout)
        "payout_ratio": g("payoutRatio"),
        "eps_revision_1m": revision,
        "foreign_own_chg_3m": NAN,
        "fwd_op_margin": g("operatingMargins"),
        "roe": g("returnOnEquity"),
        "roic": _div(ebit * (1.0 - tax), invested),
        "debt_to_equity": debt_to_equity,
    }


# ---------------------------------------------------------------------------
# Network provider
# ---------------------------------------------------------------------------


def _optional(fn):
    """Call a secondary endpoint; missing data → None, but let rate limits
    propagate so the caller can back off."""
    try:
        return fn()
    except Exception as err:  # noqa: BLE001
        if "RateLimit" in type(err).__name__:
            raise
        return None


class YahooProvider:
    name = "Yahoo Finance"

    def __init__(self) -> None:
        import yfinance  # optional dependency, imported on first use

        self.yf = yfinance
        self._fx: dict[tuple[str, str], float] = {}

    # -- listings -----------------------------------------------------------
    def listing(self, market: str) -> pd.DataFrame:
        try:
            return self._listing(market)
        except Exception as err:  # noqa: BLE001 — FDR's own errors can be cryptic
            source = "KRX listing" if market == "KOSPI" else "Naver NASDAQ listing"
            raise ConnectionError(
                f"{source} via FinanceDataReader unavailable ({type(err).__name__}: {err})"
            ) from err

    def _listing(self, market: str) -> pd.DataFrame:
        import FinanceDataReader as fdr

        if market == "KOSPI":
            raw = fdr.StockListing("KOSPI")
            raw = raw[raw["Code"].map(is_common_share)]
            out = pd.DataFrame({"ticker": raw["Code"].astype(str).str.zfill(6),
                                "name": raw["Name"], "market_cap": pd.to_numeric(raw["Marcap"])})
            out = out.sort_values("market_cap", ascending=False)
        else:
            # Naver ranks the exchange by market value, so row order is cap order.
            raw = fdr.StockListing("NASDAQ")
            out = pd.DataFrame({"ticker": raw["Symbol"].astype(str),
                                "name": raw["Name"], "market_cap": np.nan})
        return out.dropna(subset=["ticker"]).drop_duplicates("ticker").reset_index(drop=True)

    # -- fundamentals -------------------------------------------------------
    def fx_rate(self, src: str | None, dst: str | None) -> float:
        if not src or not dst or src == dst:
            return 1.0
        if (src, dst) not in self._fx:
            hist = _optional(lambda: self.yf.Ticker(f"{src}{dst}=X").history(period="5d"))
            self._fx[(src, dst)] = float(hist["Close"].iloc[-1]) if hist is not None and len(hist) else NAN
        return self._fx[(src, dst)]

    def company(self, ticker: str, market: str) -> CompanyData:
        t = self.yf.Ticker(yahoo_symbol(ticker, market))
        info = t.info or {}
        if not info.get("marketCap") and not info.get("regularMarketPrice"):
            raise LookupError(f"Yahoo Finance has no data for {yahoo_symbol(ticker, market)}")
        metrics = metrics_from_yahoo(
            info,
            income=_optional(lambda: t.get_income_stmt(freq="yearly")),
            balance=_optional(lambda: t.get_balance_sheet(freq="yearly")),
            eps_trend=_optional(lambda: t.eps_trend),
            revenue_estimate=_optional(lambda: t.revenue_estimate),
            fx=self.fx_rate(info.get("financialCurrency"), info.get("currency")),
        )
        return CompanyData(
            ticker=ticker, market=market,
            name=info.get("longName") or info.get("shortName") or ticker,
            sector=info.get("sector") or "", industry=info.get("industry") or "",
            currency=info.get("currency") or "", market_cap=_num(info.get("marketCap")),
            metrics=metrics, notes=dict(PROXY_NOTES),
        )

    def security_names(self, tickers: list[str], market: str) -> dict[str, str]:
        out = {}
        for ticker in tickers:
            info = _optional(lambda: self.yf.Ticker(yahoo_symbol(ticker, market)).info) or {}
            name = info.get("longName") or info.get("shortName")
            if name:
                out[ticker] = name
        return out

    # -- prices -------------------------------------------------------------
    def closes(self, tickers: list[str], market: str, start: pd.Timestamp) -> pd.DataFrame:
        symbols = {yahoo_symbol(t, market): t for t in tickers}
        raw = self.yf.download(list(symbols), start=pd.Timestamp(start).date(), auto_adjust=True,
                               progress=False, threads=True, multi_level_index=True)
        if raw is None or raw.empty:
            return pd.DataFrame(columns=tickers, dtype=float)
        close = raw["Close"]
        if isinstance(close, pd.Series):
            close = close.to_frame(next(iter(symbols)))
        close = close.rename(columns=symbols)
        close.index = pd.DatetimeIndex(close.index).tz_localize(None).normalize()
        return close.reindex(columns=tickers).sort_index()

    def quote(self, ticker: str, market: str) -> Quote:
        t = self.yf.Ticker(yahoo_symbol(ticker, market))
        daily = t.history(period="10d", interval="1d", auto_adjust=False)
        if daily.empty:
            raise LookupError(f"No price history for {ticker}")
        intraday = _optional(lambda: t.history(period="1d", interval="1m", auto_adjust=False))
        if intraday is not None and not intraday.empty:
            price, as_of = float(intraday["Close"].iloc[-1]), intraday.index[-1].to_pydatetime()
        else:
            price, as_of = float(daily["Close"].iloc[-1]), session_close(daily.index[-1], market)
        earlier = daily[daily.index.date < as_of.date()]
        prev = float(earlier["Close"].iloc[-1]) if len(earlier) else NAN
        currency = _optional(lambda: t.fast_info.currency) or ""
        return Quote(price=price, prev_close=prev, as_of=as_of,
                     source=self.name, currency=currency)
