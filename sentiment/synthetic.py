"""Deterministic demo readings for synthetic mode.

Only the external text/API sources are faked; the Fear & Greed index and the
price-behavior family run through the real code on synthetic prices.
Every demo item is labelled "[demo]".
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import numpy as np

from sentiment.model import NOT_APPLICABLE, Reading
from sentiment.text import classify, dedupe, score_text

# (bullish, bearish, neutral) phrases; demo items are scored by the real text
# scorer, so each item's tone matches its wording.
_PHRASES_EN = (("{n} beats estimates", "Analysts upgrade {n}", "{n} rallies on strong demand",
                "{n} announces buyback"),
               ("{n} slips as sector cools", "{n} faces regulatory probe",
                "{n} shares drop after guidance cut", "Analyst downgrades {n} on weak outlook"),
               ("{n} holds steady ahead of earnings", "{n} schedules investor day"))
_PHRASES_KO = (("{n}, 호실적 기대에 상승", "{n} 목표가 상향", "{n} 신고가 돌파", "{n} 자사주 매입 발표"),
               ("{n} 급락…업황 우려", "{n} 외국인 순매도 지속", "{n} 실적 부진 우려", "{n} 목표가 하향"),
               ("{n} 보합세 유지", "{n} 정기 주주총회 개최"))


def _rng(*parts: str) -> np.random.Generator:
    seed = int(hashlib.sha256(":".join(parts).encode()).hexdigest()[:8], 16)
    return np.random.default_rng(seed)


def _items(rng, name: str, korean: bool, by: tuple[str, ...], count: int, bias: float):
    """Demo items whose mix of bullish/bearish wording follows ``bias``."""
    bull, bear, neutral = _PHRASES_KO if korean else _PHRASES_EN
    p_bull = float(np.clip(0.5 + bias / 2, 0.05, 0.95))
    now = datetime.now(timezone.utc)
    items = []
    for _ in range(count):
        pool = neutral if rng.random() < 0.2 else bull if rng.random() < p_bull else bear
        text = pool[int(rng.integers(len(pool)))].format(n=name)
        items.append({"time": now - timedelta(hours=float(rng.uniform(0, 7 * 24))),
                      "text": "[demo] " + text, "score": score_text(text),
                      "by": by[int(rng.integers(len(by)))], "url": ""})
    return sorted(items, key=lambda i: i["time"], reverse=True)


def _from_items(source, family, items, note):
    scores = [i["score"] for i in items]
    cls = [classify(s) for s in scores]
    return Reading(source, family, score=float(np.mean(scores)), n=float(len(items)),
                   bulls=cls.count(1), bears=cls.count(-1), items=items, note=note)


def readings(ticker: str, market: str, name: str) -> list[Reading]:
    day = datetime.now(timezone.utc).date().isoformat()
    rng = _rng(ticker, market, day)
    bias = float(rng.normal(0, 0.35))          # the stock's demo "mood" today
    korean = market == "KOSPI"
    news = dedupe(_items(rng, name, korean, ("Outlet A", "Outlet B", "Outlet C", "Outlet D"),
                         int(rng.integers(20, 40)), bias))   # same rules as live headlines
    out = [
        _from_items("News headlines", "News", news, "[demo] Synthetic headlines."),
        Reading("Analyst ratings", "Analysts",
                score=float(np.clip(0.3 + bias * 0.5 + rng.normal(0, 0.1), -1, 1)),
                n=float(rng.integers(5, 40)), note="[demo] Synthetic ratings."),
    ]
    if korean:
        out.append(Reading("Investor flows (KIS)", "Positioning",
                           score=float(np.clip(bias + rng.normal(0, 0.3), -1, 1)), n=40.0,
                           note="[demo] Synthetic foreign/institutional flows."))
        out.append(Reading("StockTwits", "Crowd", status=NOT_APPLICABLE,
                           note="StockTwits covers US-listed symbols."))
    else:
        tw = _items(rng, name, False, ("StockTwits",), 30, bias + 0.1)
        for i in tw:
            i["score"] = float(classify(i["score"]))
        tagged = [i for i in tw if i["score"] != 0]
        out.append(_from_items("StockTwits", "Crowd", tagged or tw,
                               "[demo] Synthetic self-tagged messages."))
        out.append(_from_items("Reddit", "Crowd",
                               _items(rng, name, False, ("r/stocks", "r/investing",
                                                         "r/wallstreetbets"),
                                      int(rng.integers(5, 25)), bias),
                               "[demo] Synthetic posts."))
        out.append(Reading("Options put/call", "Positioning",
                           score=float(np.clip(bias + rng.normal(0, 0.25), -1, 1)),
                           n=float(rng.integers(20, 400)), note="[demo] Synthetic put/call."))
        out.append(Reading("Short interest", "Positioning",
                           score=float(np.clip(rng.normal(0.1, 0.3), -1, 1)), n=50.0,
                           note="[demo] Synthetic short interest."))
    return out
