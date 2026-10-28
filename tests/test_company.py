"""Company Analysis tests — offline.

Yahoo parsing is tested against fixtures shaped like yfinance 1.x output
(statement rows × fiscal-year columns, newest first; eps_trend indexed by
period with current/30daysAgo columns). Run with:

    python -m tests.test_company
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

import config
from data import snapshot
from data.providers import describe_freshness, get_provider
from data.providers.base import CompanyData
from data.providers.yahoo import is_common_share, metrics_from_yahoo, yahoo_symbol
from factors.company import score_company

FY = [pd.Timestamp("2025-12-31"), pd.Timestamp("2024-12-31")]


def _statements():
    income = pd.DataFrame(
        {FY[0]: [1000.0, 200.0, 180.0, 0.20], FY[1]: [900.0, 150.0, 140.0, 0.22]},
        index=["TotalRevenue", "OperatingIncome", "EBIT", "TaxRateForCalcs"],
    )
    balance = pd.DataFrame(
        {FY[0]: [500.0, 250.0, 720.0], FY[1]: [450.0, 260.0, 680.0]},
        index=["StockholdersEquity", "TotalDebt", "InvestedCapital"],
    )
    eps_trend = pd.DataFrame(
        {"current": [2.0, 2.4], "30daysAgo": [1.9, 2.0]}, index=["0y", "+1y"])
    revenue_est = pd.DataFrame({"growth": [0.08, 0.12]}, index=["0y", "+1y"])
    return income, balance, eps_trend, revenue_est


def _info(**overrides):
    info = {"marketCap": 4000.0, "currentPrice": 40.0, "netIncomeToCommon": 160.0,
            "operatingCashflow": 240.0, "dividendRate": 0.8, "trailingEps": 1.6,
            "forwardEps": 2.0, "payoutRatio": 0.3, "returnOnEquity": 0.32,
            "operatingMargins": 0.21, "debtToEquity": 55.0,
            "currency": "USD", "financialCurrency": "USD"}
    info.update(overrides)
    return info


def test_yahoo_metrics() -> None:
    income, balance, trend, rev = _statements()
    m = metrics_from_yahoo(_info(), income, balance, trend, rev)
    assert np.isclose(m["earnings_yield"], 160 / 4000)
    assert np.isclose(m["dividend_yield"], 0.8 / 40)
    assert np.isclose(m["book_to_market"], 500 / 4000)
    assert np.isclose(m["cash_flow_yield"], 240 / 4000)
    assert np.isclose(m["fwd_revenue_revision"], 0.12)              # +1y preferred
    assert np.isclose(m["fwd_op_margin_change"], 0.20 - 150 / 900)  # newest − prior FY
    assert np.isclose(m["fwd_eps_growth"], 2.0 / 1.6 - 1)
    assert np.isclose(m["eps_revision_1m"], (2.4 - 2.0) / 2.0)
    assert np.isclose(m["roic"], 180 * (1 - 0.20) / 720)
    assert np.isclose(m["debt_to_equity"], 250 / 500)               # from balance sheet
    assert np.isnan(m["foreign_own_chg_3m"])


def test_yahoo_edge_cases() -> None:
    income, balance, trend, rev = _statements()
    # non-payer → 0% (ranks low, not missing); loss-maker → no EPS growth
    m = metrics_from_yahoo(_info(dividendRate=None, trailingEps=-0.5), income, balance, trend, rev)
    assert m["dividend_yield"] == 0.0 and np.isnan(m["fwd_eps_growth"])
    # no statements: D/E falls back to Yahoo's percentage field, scaled to a ratio
    m = metrics_from_yahoo(_info(), None, None, None, None)
    assert np.isclose(m["debt_to_equity"], 0.55)
    assert np.isnan(m["roic"]) and np.isnan(m["eps_revision_1m"])
    # ADR: TWD financials, USD quote → aggregates converted before dividing by USD cap
    m = metrics_from_yahoo(_info(financialCurrency="TWD", netIncomeToCommon=3200.0),
                           income, balance, trend, rev, fx=1 / 32)
    assert np.isclose(m["earnings_yield"], 100 / 4000)


def test_symbols() -> None:
    assert yahoo_symbol("005930", "KOSPI") == "005930.KS"
    assert yahoo_symbol("BRK.B", "NASDAQ") == "BRK-B"
    assert is_common_share("005930") and not is_common_share("005935")


def test_freshness() -> None:
    seoul, ny = ZoneInfo("Asia/Seoul"), ZoneInfo("America/New_York")
    now = datetime(2026, 10, 28, 10, 30, tzinfo=seoul)  # Wednesday, in session
    assert describe_freshness(datetime(2026, 10, 28, 10, 29, tzinfo=seoul), "KOSPI", now)[0] == "live"
    level, label = describe_freshness(datetime(2026, 10, 28, 10, 10, tzinfo=seoul), "KOSPI", now)
    assert level == "delayed" and "~20 min" in label
    level, label = describe_freshness(datetime(2026, 10, 27, 15, 30, tzinfo=seoul), "KOSPI", now)
    assert level == "close" and label.startswith("Previous close")
    # Saturday: Friday's close is the latest available
    sat = datetime(2026, 10, 31, 12, 0, tzinfo=ny)
    assert describe_freshness(datetime(2026, 10, 30, 16, 0, tzinfo=ny), "NASDAQ", sat)[0] == "close"


def _peers(n: int = 20) -> pd.DataFrame:
    provider = get_provider("synthetic")
    frame, _ = snapshot.build(provider, "NASDAQ", top_n=n)
    return frame


def test_score_company() -> None:
    peers = _peers()
    # Target outside the peer set, strictly best on every input → rank 1.
    best = peers.drop(columns=["name", "sector", "industry", "currency"], errors="ignore")
    best = best.apply(pd.to_numeric, errors="coerce")
    row = (best.max() * 2).astype(object)
    row["debt_to_equity"] = best["debt_to_equity"].min() / 2
    row["payout_ratio"] = 0.0  # full retention → highest ROE × (1 − payout)
    for col in [c for c in best.columns if c.startswith("ret_")]:
        row[col] = abs(best[col]).max() * 2  # all horizons up → full trend agreement
    row["name"], row["sector"] = "Best Co", peers["sector"].iloc[0]
    s = score_company("ZZZZ", row, peers, all_round=0.6, standout=0.95)
    assert not s.in_snapshot and s.universe_size == len(peers) + 1
    assert s.rank == 1 and s.classification == "All-round leader"
    assert (s.group_rank == 1).all() and s.sector_rank == 1
    # A peer re-scored with its own row stays in a universe of the same size.
    t = peers.index[3]
    s2 = score_company(t, peers.loc[t], peers, 0.6, 0.95)
    assert s2.in_snapshot and s2.universe_size == len(peers)


def test_snapshot_roundtrip_and_failures() -> None:
    class Flaky:  # synthetic provider whose company() fails for one ticker
        name = "Flaky"

        def __init__(self):
            self.inner = get_provider("synthetic")

        def listing(self, market):
            return self.inner.listing(market)

        def closes(self, *args):
            return self.inner.closes(*args)

        def company(self, ticker, market) -> CompanyData:
            if ticker == "MSFT":
                raise LookupError("no data")
            return self.inner.company(ticker, market)

    with tempfile.TemporaryDirectory() as tmp:
        old, config.SNAPSHOT_DIR = config.SNAPSHOT_DIR, Path(tmp)
        try:
            frame, meta = snapshot.build(Flaky(), "NASDAQ", top_n=10)
            assert "MSFT" not in frame.index and "MSFT" in meta["failed"]
            assert len(frame) == 9 and {"ret_12M", "roe", "name", "sector"} <= set(frame.columns)
            snapshot.save(frame, meta)
            loaded, meta2 = snapshot.load(snapshot.latest_path("NASDAQ"))
            pd.testing.assert_frame_equal(frame, loaded, check_freq=False)
            assert meta2["companies"] == 9
        finally:
            config.SNAPSHOT_DIR = old


if __name__ == "__main__":
    for fn in (test_yahoo_metrics, test_yahoo_edge_cases, test_symbols, test_freshness,
               test_score_company, test_snapshot_roundtrip_and_failures):
        print(f"• {fn.__name__}")
        fn()
    print("\nAll company-analysis tests passed ✅")
