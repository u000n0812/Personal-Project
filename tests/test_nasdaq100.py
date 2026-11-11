"""Nasdaq-100 coverage and key-metric display tests — offline.

Parsers are tested on payloads shaped like the real sources (Nasdaq's
list-type API JSON; Wikipedia's constituents table).

    python -m tests.test_nasdaq100
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

import config
from data import indexes, snapshot
from data.providers import get_provider
from ui.metric_views import METRICS, metric_values

NASDAQ_JSON = {"data": {"headers": {"symbol": "Symbol"}, "data": {"rows": [
    {"symbol": "AAPL", "companyName": "Apple Inc. Common Stock", "marketCap": "3,0"},
    {"symbol": "GOOGL", "companyName": "Alphabet Inc. Class A"},
    {"symbol": "GOOG", "companyName": "Alphabet Inc. Class C"},
    {"symbol": " msft ", "companyName": "Microsoft"},
]}}, "message": None}

WIKI_HTML = """<html><body>
<table class="wikitable"><tr><th>Year</th><th>Change</th></tr><tr><td>2024</td><td>x</td></tr></table>
<table class="wikitable sortable" id="constituents">
<tr><th>Company</th><th>Ticker</th><th>GICS Sector</th></tr>
<tr><td>Apple Inc.</td><td>AAPL</td><td>Information Technology</td></tr>
<tr><td>Alphabet Inc. (Class C)</td><td>GOOG</td><td>Communication Services</td></tr>
<tr><td>Alphabet Inc. (Class A)</td><td>GOOGL</td><td>Communication Services</td></tr>
</table></body></html>"""


def test_parse_nasdaq() -> None:
    f = indexes.parse_nasdaq_json(NASDAQ_JSON)
    assert f["ticker"].tolist() == ["AAPL", "GOOGL", "MSFT"]   # GOOG folded, trimmed, upper
    assert f.loc[f.ticker == "AAPL", "name"].item() == "Apple Inc. Common Stock"


def test_parse_wikipedia() -> None:
    f = indexes.parse_wikipedia_html(WIKI_HTML)
    assert f["ticker"].tolist() == ["AAPL", "GOOGL"]           # one line per company
    assert f.loc[f.ticker == "AAPL", "name"].item() == "Apple Inc."


def test_size_check() -> None:
    small = pd.DataFrame({"ticker": ["A"], "name": ["a"]})
    try:
        indexes.check_size(small, "x")
        raise AssertionError("1-row list should be rejected")
    except ValueError:
        pass
    indexes.check_size(pd.DataFrame({"ticker": [f"T{i}" for i in range(100)], "name": ""}), "x")


def test_snapshot_covers_all_members() -> None:
    """Even with top_n=5, every Nasdaq-100 member lands in the NASDAQ snapshot."""
    frame, meta = snapshot.build(get_provider("synthetic"), "NASDAQ", top_n=5)
    ndx = meta["indexes"]["NDX"]
    assert ndx["members"] == 100 and ndx["covered"] == 100 and ndx["missing"] == []
    assert int(frame["in_ndx"].sum()) == 100
    assert ndx["added_beyond_top_n"] == 95


def test_membership_failure_is_reported() -> None:
    class NoIndex:
        name = "NoIndex"

        def __init__(self):
            self.inner = get_provider("synthetic")

        def __getattr__(self, item):
            return getattr(self.inner, item)

        def index_members(self, index):
            raise ConnectionError("blocked")

    frame, meta = snapshot.build(NoIndex(), "NASDAQ", top_n=10)
    assert "in_ndx" not in frame.columns and "blocked" in meta["indexes"]["NDX"]["error"]
    assert len(frame) == 10                                    # snapshot still built


def test_cache_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        old, config.SNAPSHOT_DIR = config.SNAPSHOT_DIR, Path(tmp)
        try:
            members = indexes.Members(pd.DataFrame({"ticker": ["AAPL"], "name": ["Apple"]}),
                                      "Nasdaq", "2026-11-11")
            indexes._save(members)
            cached = indexes.load_cached()
        finally:
            config.SNAPSHOT_DIR = old
    assert cached.source == "cache (Nasdaq)" and cached.frame["ticker"].tolist() == ["AAPL"]


def test_metric_values() -> None:
    m = pd.DataFrame({
        "earnings_yield": [0.05, -0.02], "book_to_market": [0.5, -0.1],
        "debt_to_equity": [0.8, np.inf], "fwd_op_margin_change": [0.012, -0.003],
        "roe": [0.2, 0.1], "ret_3M": [0.1, -0.05],
    }, index=["A", "B"])
    v = metric_values(m)
    assert np.isclose(v.at["A", "pe"], 20.0) and np.isnan(v.at["B", "pe"])   # loss → blank
    assert np.isclose(v.at["A", "pb"], 2.0) and np.isnan(v.at["B", "pb"])    # neg. equity
    assert np.isnan(v.at["B", "debt_to_equity"])                             # inf → blank
    assert np.isclose(v.at["A", "fwd_op_margin_change"], 1.2)                # pp scaled
    assert np.isclose(v.at["A", "roe"], 0.2)                                 # pct untouched
    expected = {c.key for cols in METRICS.values() for c in cols}
    assert set(v.columns) == expected and np.isnan(v.at["A", "roic"])        # missing → NaN


if __name__ == "__main__":
    for fn in (test_parse_nasdaq, test_parse_wikipedia, test_size_check,
               test_snapshot_covers_all_members, test_membership_failure_is_reported,
               test_cache_roundtrip, test_metric_values):
        print(f"• {fn.__name__}")
        fn()
    print("\nAll Nasdaq-100 / metric tests passed ✅")
