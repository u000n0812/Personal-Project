"""Sector scoring, search, ETF analytics and override tests — offline.

    python -m tests.test_sectors
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

import config
from data import fundamentals, snapshot
from data.providers import get_provider
from factors.company import score_market
from factors.sector import performance, period_start, rebased, sector_summary
from ui.tables import search_mask


def _universe(market: str = "NASDAQ") -> pd.DataFrame:
    frame, _ = snapshot.build(get_provider("synthetic"), market, top_n=10_000)
    return frame.assign(market=market)


def test_search() -> None:
    t = pd.DataFrame({"name": ["Samsung Electronics", "NVIDIA", None],
                      "name_local": ["삼성전자", "NVIDIA", "카카오"]},
                     index=["005930", "NVDA", "035720"])
    assert search_mask(t, "삼성").tolist() == [True, False, False]
    assert search_mask(t, "  nvd ").tolist() == [False, True, False]   # trim + casefold
    assert search_mask(t, "0357").tolist() == [False, False, True]     # ticker from index
    assert search_mask(t, "").all() and not search_mask(t, "zzz").any()
    assert search_mask(t, "a+b").sum() == 0                             # literal, not regex


def test_sector_scope() -> None:
    u = _universe()
    sizes = u["sector"].value_counts()
    board = score_market(u, 0.6, 0.95, rank_scope="sector", min_sector_size=5)
    t = board.table
    assert set(t.index) == set(u.index)
    small = sizes[sizes < 5].index
    assert (t.loc[t["sector"].isin(small), "ranked_vs"] == "Market").all()
    big = t[~t["sector"].isin(small)]
    assert (big["ranked_vs"] == "Sector").all()
    for sector, grp in big.groupby("sector"):
        # each big sector is its own ranking: ranks 1..n, percentile tops at 1.0
        assert grp["rank"].min() == 1 and (grp["scope_size"] == len(grp)).all()
        assert np.isclose(board.groups.loc[grp.index, "Value"].max(), 1.0)
    market = score_market(u, 0.6, 0.95, rank_scope="market").table
    assert market["rank"].min() == 1 and (market["ranked_vs"] == "Market").all()


def test_sector_summary() -> None:
    t = pd.DataFrame({
        "market": ["A", "A", "A", "B"], "sector": ["X", "X", "Y", "X"],
        "leader": [True, False, True, False], "composite": [0.8, 0.4, 0.6, 0.5],
        "Value": [0.9, 0.1, 0.5, 0.5], "Growth": 0.5, "Momentum": 0.5, "Quality": 0.5,
    })
    s = sector_summary(t).set_index(["market", "sector"])
    assert s.at[("A", "X"), "companies"] == 2 and s.at[("A", "X"), "leaders"] == 1
    assert np.isclose(s.at[("A", "X"), "composite"], 0.6)
    assert np.isclose(s.at[("A", "X"), "leader_share"], 0.5)


def test_etf_performance() -> None:
    idx = pd.bdate_range("2025-01-01", periods=300)
    close = pd.DataFrame({
        "UP": np.linspace(100, 200, 300),     # steady riser
        "BENCH": np.full(300, 100.0),         # flat
        "DIP": np.r_[np.full(150, 100.0), np.full(150, 80.0)],
    }, index=idx)
    p = performance(close, "BENCH")
    assert np.isclose(p.at["UP", "ret_1M"], close["UP"].iloc[-1] / close["UP"].iloc[-22] - 1)
    assert np.isclose(p.at["UP", "excess_1M"], p.at["UP", "ret_1M"])       # bench flat
    assert np.isclose(p.at["DIP", "mdd_1Y"], -0.20)
    ytd_base = close["UP"][close.index.year < idx[-1].year].iloc[-1]
    assert np.isclose(p.at["UP", "ret_YTD"], close["UP"].iloc[-1] / ytd_base - 1)
    g = rebased(close, period_start(idx, "3M"))
    assert np.allclose(g.iloc[0], 100.0) and g["UP"].iloc[-1] > 100


def test_overrides() -> None:
    frame = pd.DataFrame({"roe": [0.10, 0.20], "fwd_eps_growth": [0.05, np.nan],
                          "name": ["A", "B"]}, index=["005930", "AAPL"])
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "fundamentals.csv"
        # leading zeros dropped (as Excel does), blank cell, one unknown ticker
        path.write_text("ticker,roe,fwd_eps_growth,unknown_col\n"
                        "5930,0.15,,1\naapl,,0.30,2\nZZZZ,0.5,0.5,3\n", encoding="utf-8")
        old, config.FUNDAMENTALS_PATH = config.FUNDAMENTALS_PATH, str(path)
        try:
            out, info = fundamentals.apply_overrides(frame)
        finally:
            config.FUNDAMENTALS_PATH = old
    assert info.tickers == 2 and set(info.columns) == {"roe", "fwd_eps_growth"}
    assert np.isclose(out.at["005930", "roe"], 0.15)                 # overridden
    assert np.isclose(out.at["005930", "fwd_eps_growth"], 0.05)      # blank cell kept
    assert np.isclose(out.at["AAPL", "roe"], 0.20)
    assert np.isclose(out.at["AAPL", "fwd_eps_growth"], 0.30)        # NaN filled from file
    assert "ZZZZ" not in out.index and out.at["AAPL", "name"] == "B"


if __name__ == "__main__":
    for fn in (test_search, test_sector_scope, test_sector_summary,
               test_etf_performance, test_overrides):
        print(f"• {fn.__name__}")
        fn()
    print("\nAll sector tests passed ✅")
