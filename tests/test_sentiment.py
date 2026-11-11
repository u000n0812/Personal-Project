"""Sentiment tests — offline. Source parsers run on payloads shaped like the
real responses (StockTwits, Reddit, Google News RSS, Yahoo, KIS, CNN).

    python -m tests.test_sentiment
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import config
from sentiment import engine, history
from sentiment import sources as src
from sentiment import text as tx
from sentiment.market import fear_greed, parse_cnn, symbols_for
from sentiment.model import (Reading, aggregate, attention_ratio, band, summarize,
                             to_index)
from sentiment.price import relative_history, rsi

NOW = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)


def test_text_scoring() -> None:
    assert tx.score_text("Nvidia beats earnings, stock rallies to record high") > 0.5
    assert tx.score_text("Shares plunge after guidance cut") < -0.3
    assert tx.score_text("Analyst downgrades Tesla on weak deliveries") < -0.3
    assert tx.score_text("Apple slips as sector cools") < 0                # common market verbs
    assert tx.score_text("Apple schedules investor day") == 0.0            # no opinion → neutral
    assert tx.score_text("삼성전자, 호실적에 신고가 돌파") > 0
    assert tx.score_text("SK하이닉스 급락…업황 우려") < 0
    assert tx.score_text("회사 정기 주주총회 개최") == 0.0                 # no finance stems
    assert tx.clean_headline("Apple rises on demand - Reuters") == "Apple rises on demand"


def test_dedupe_and_outlet_cap() -> None:
    items = [{"text": "Apple rises", "by": "A"}, {"text": "Apple rises!", "by": "B"},  # syndicated
             *({"text": f"Story {i}", "by": "A"} for i in range(5))]
    kept = tx.dedupe(items, per_source_cap=3)
    assert [i["text"] for i in kept] == ["Apple rises", "Story 0", "Story 1"]


def test_shrinkage_and_family_balance() -> None:
    weak = Reading("X", "Crowd", score=1.0, n=3)
    assert np.isclose(weak.adjusted, 3 / 13)
    # Two bullish crowd sources vs one bearish price reading: families weigh equally.
    rs = [Reading("A", "Crowd", score=1.0, n=1e6), Reading("B", "Crowd", score=1.0, n=1e6),
          Reading("P", "Price", score=-1.0, n=1e6)]
    c = aggregate(rs, NOW)
    assert np.isclose(c.index, 50, atol=0.01) and c.coverage == 2
    assert c.agreement_label == "Sources conflict"
    # Unavailable sources are ignored, not counted as neutral.
    c2 = aggregate([Reading("A", "Crowd", score=0.6, n=1e6), Reading("B", "News", status="error")])
    assert np.isclose(c2.index, 80, atol=0.01) and c2.coverage == 1 and c2.low_coverage


def test_bands_and_summary() -> None:
    assert band(10) == "Extreme fear" and band(50) == "Neutral" and band(80) == "Extreme greed"
    assert band(float("nan")) == "No data" and to_index(-1) == 0 and to_index(1) == 100
    c = aggregate([Reading("A", "Crowd", score=0.8, n=1e6), Reading("B", "Price", score=0.7, n=1e6)])
    lines = summarize("Acme", c, 50.0, "Neutral", "US market")
    assert any("+" in line and "points" in line for line in lines)          # company vs market gap
    assert any("contrarily" in line for line in lines)                     # extreme reading caveat


def test_attention_ratio() -> None:
    items = [{"time": NOW - timedelta(hours=h)} for h in (1, 2, 3, 4, 5, 6)]   # all today
    items += [{"time": NOW - timedelta(days=d)} for d in (2, 3, 4, 5, 6, 6.5)]
    assert attention_ratio(items, NOW) > 2
    assert np.isnan(attention_ratio(items[:3], NOW))                       # too few items


def test_parse_stocktwits() -> None:
    payload = {"messages": [
        {"body": "$NVDA to the moon", "created_at": "2026-11-11T10:00:00Z",
         "entities": {"sentiment": {"basic": "Bullish"}}},
        {"body": "overvalued", "created_at": "2026-11-11T09:00:00Z",
         "entities": {"sentiment": {"basic": "Bearish"}}},
        {"body": "earnings tomorrow", "created_at": "2026-11-11T08:00:00Z",
         "entities": {"sentiment": None}},
        {"body": "buying more", "created_at": "2026-11-11T07:00:00Z",
         "entities": {"sentiment": {"basic": "Bullish"}}},
    ]}
    r = src.parse_stocktwits(payload)
    assert r.ok and r.bulls == 2 and r.bears == 1 and r.n == 3
    assert np.isclose(r.score, 1 / 3) and len(r.items) == 4


def test_parse_reddit() -> None:
    payload = {"data": {"children": [
        {"data": {"title": "NVDA beats earnings, rallies", "selftext": "", "score": 500,
                  "created_utc": NOW.timestamp(), "subreddit": "stocks",
                  "permalink": "/r/stocks/x"}},
        {"data": {"title": "Shares plunge after guidance cut", "selftext": "", "score": 2,
                  "created_utc": NOW.timestamp(), "subreddit": "investing",
                  "permalink": "/r/investing/y"}},
    ]}}
    r = src.parse_reddit(payload)
    assert r.ok and r.bulls == 1 and r.bears == 1
    assert r.score > 0                         # the 500-upvote post outweighs the 2-upvote one
    assert src.reddit_query("ON", "ON Semiconductor Corporation") == '"$ON" OR "ON Semiconductor"'


def test_parse_news_rss() -> None:
    xml = """<?xml version="1.0"?><rss><channel>
      <item><title>Acme beats estimates - Reuters</title><link>https://a</link>
        <pubDate>Wed, 11 Nov 2026 09:00:00 GMT</pubDate><source url="x">Reuters</source></item>
      <item><title>Acme beats estimates - Yahoo</title><link>https://b</link>
        <pubDate>Wed, 11 Nov 2026 08:00:00 GMT</pubDate><source url="y">Yahoo</source></item>
      <item><title>Acme shares plunge on probe - Bloomberg</title><link>https://c</link>
        <pubDate>Tue, 10 Nov 2026 08:00:00 GMT</pubDate><source url="z">Bloomberg</source></item>
    </channel></rss>"""
    r = src.parse_news_rss(xml)
    assert r.ok and r.n == 2                    # syndicated duplicate dropped
    assert r.bulls == 1 and r.bears == 1 and r.items[0]["by"] == "Reuters"


def test_parse_analysts() -> None:
    recs = pd.DataFrame({"period": ["0m", "-1m", "-2m", "-3m"], "strongBuy": [10, 9, 8, 6],
                         "buy": [15, 15, 15, 15], "hold": [5, 6, 7, 9], "sell": [0, 0, 0, 0],
                         "strongSell": [0, 0, 0, 0]})
    actions = pd.DataFrame({"action": ["up", "up", "down", "main"]},
                           index=pd.to_datetime(["2026-11-01", "2026-10-01", "2026-09-20",
                                                 "2026-01-01"], utc=True))
    r = src.parse_analysts(recs, actions, NOW)
    level_now = (2 * 10 + 15) / 60
    level_then = (2 * 6 + 15) / 60
    expected = 0.5 * level_now + 0.5 * np.clip(4 * (level_now - level_then), -1, 1)
    assert r.ok and np.isclose(r.score, expected) and r.n == 30
    assert r.detail["upgrades_90d"] == 2 and r.detail["downgrades_90d"] == 1
    assert not src.parse_analysts(pd.DataFrame()).ok


def test_parse_options_and_short_interest() -> None:
    calls = pd.DataFrame({"volume": [12000, 8000], "openInterest": [5e4, 5e4]})
    puts = pd.DataFrame({"volume": [7000, 5000], "openInterest": [4e4, 4e4]})
    r = src.parse_options([(calls, puts)])
    assert np.isclose(r.detail["pcr"], 0.6) and r.score > 0     # below 0.7 → mildly bullish
    assert np.isclose(src.parse_options([(puts, calls)]).detail["pcr"], 20000 / 12000)
    s = src.parse_short_interest({"shortPercentOfFloat": 0.15, "sharesShort": 125,
                                  "sharesShortPriorMonth": 100})
    assert np.isclose(s.score, np.mean([-1.0, -1.0]))           # 15% short, +25% m/m
    assert not src.parse_short_interest({}).ok


def test_parse_kis_investor() -> None:
    rows = [{"stck_bsop_date": f"202611{d:02d}", "frgn_ntby_qty": "1,000",
             "orgn_ntby_qty": "-250", "prsn_ntby_qty": "-750"} for d in range(1, 11)]
    r = src.parse_kis_investor({"output": rows})
    assert np.isclose(r.score, (750 * 10) / (1250 * 10)) and r.detail["retail_20d"] == -7500


def test_market_fear_greed_and_cnn() -> None:
    idx = pd.bdate_range("2024-01-01", periods=600)
    rng = np.random.default_rng(0)
    close = pd.DataFrame({s: 100 * np.exp(np.cumsum(rng.normal(0, .01, 600)))
                          for s in symbols_for("KOSPI")}, index=idx)
    close["^KS11"] = np.r_[np.linspace(100, 80, 500), np.linspace(80, 130, 100)]  # sharp rally
    fg = fear_greed(close, "KOSPI")
    assert fg["index"].between(0, 100).all()
    assert fg["momentum"].iloc[-1] > 90 and fg["strength"].iloc[-1] > 90
    cnn = parse_cnn({"fear_and_greed": {"score": 41.3, "rating": "fear", "previous_1_week": 50}})
    assert cnn["score"] == 41.3 and cnn["previous_1_week"] == 50.0
    assert parse_cnn({}) is None


def test_relative_price() -> None:
    idx = pd.bdate_range("2025-01-01", periods=300)
    up, flat = pd.Series(np.linspace(100, 200, 300), idx), pd.Series(100.0, idx)
    assert rsi(up).iloc[-1] == 100 and rsi(flat).iloc[-1] == 50
    assert relative_history(up, flat).iloc[-1] > 0.5 > -0.5 > relative_history(flat, up).iloc[-1]
    # Moving exactly with the market (constant ratio) reads neutral
    assert np.isclose(relative_history(up, up * 2).iloc[-1], 0.0)


def test_history_roundtrip() -> None:
    s = engine.analyze_stock("synthetic", "NVDA", "NASDAQ", "NVIDIA")
    with tempfile.TemporaryDirectory() as tmp:
        old, config.SENTIMENT_DIR = config.SENTIMENT_DIR, Path(tmp)
        try:
            history.record(s, 55.0)
            history.record(s, 56.0)                 # same day → replaces, not duplicates
            h = history.load("NVDA", "NASDAQ")
        finally:
            config.SENTIMENT_DIR = old
    assert len(h) == 1 and h["market_index"].iloc[0] == 56.0
    assert np.isclose(h["index"].iloc[0], s.composite.index)


def test_engine_synthetic_and_isolation() -> None:
    us = engine.analyze_stock("synthetic", "NVDA", "NASDAQ", "NVIDIA")
    assert us.composite.coverage == 5 and len(us.price_history) > 100
    kr = engine.analyze_stock("synthetic", "005930", "KOSPI", "Samsung Electronics", "삼성전자")
    twits = next(r for r in kr.composite.readings if r.source == "StockTwits")
    assert twits.status == "not applicable"
    boom = engine._safe("X", "News", lambda: (_ for _ in ()).throw(ConnectionError("blocked")))
    assert boom.status == "error" and "blocked" in boom.note
    m = engine.analyze_market("synthetic", "NASDAQ")
    assert 0 <= m.latest <= 100 and len(m.history) > 200


if __name__ == "__main__":
    for fn in (test_text_scoring, test_dedupe_and_outlet_cap, test_shrinkage_and_family_balance,
               test_bands_and_summary, test_attention_ratio, test_parse_stocktwits,
               test_parse_reddit, test_parse_news_rss, test_parse_analysts,
               test_parse_options_and_short_interest, test_parse_kis_investor,
               test_market_fear_greed_and_cnn, test_relative_price, test_history_roundtrip,
               test_engine_synthetic_and_isolation):
        print(f"• {fn.__name__}")
        fn()
    print("\nAll sentiment tests passed ✅")
