"""Sentiment source adapters.

Each source has a pure ``parse_*`` function (tested offline against payloads
shaped like the real API responses) and a ``fetch_*`` function that does the
network call. Every fetch returns a ``Reading`` — on failure a reading with
status "unavailable"/"error" and a note, never invented numbers.

| Source            | Family      | Markets       | Access                         |
|-------------------|-------------|---------------|--------------------------------|
| StockTwits        | Crowd       | NASDAQ        | public API, no key             |
| Reddit            | Crowd       | NASDAQ (+KR names) | official API, free app keys |
| News headlines    | News        | both (en / ko)| Google News RSS, no key        |
| Analyst ratings   | Analysts    | both          | Yahoo Finance                  |
| Options put/call  | Positioning | NASDAQ        | Yahoo Finance option chains    |
| Short interest    | Positioning | NASDAQ        | Yahoo Finance                  |
| Investor flows    | Positioning | KOSPI         | KIS Open API (your keys)       |
| Price vs market   | Price       | both          | Yahoo Finance prices           |
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import numpy as np
import pandas as pd

from sentiment import text as tx
from sentiment.model import ERROR, NOT_APPLICABLE, OK, UNAVAILABLE, Reading

TIMEOUT = 20
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
APP_UA = "python:personal-quant-dashboard:1.0 (personal research tool)"
ITEM_LIMIT = 30          # items kept per source for display

_SUFFIXES = re.compile(r"[,.]?\s+(inc|corp|corporation|co|ltd|plc|holdings|group|company|"
                       r"class [a-c]|common stock|n\.v|s\.a|ag)\.?$", re.I)


def short_name(name: str) -> str:
    """'NVIDIA Corporation' → 'NVIDIA'; strips legal suffixes repeatedly."""
    name = (name or "").strip()
    while True:
        new = _SUFFIXES.sub("", name).strip()
        if new == name:
            return name
        name = new


def _as_reading(source: str, family: str, items: list[dict], weights=None,
                note: str = "") -> Reading:
    """Score = (weighted) mean item score; bulls/bears = classified items."""
    if not items:
        return Reading(source, family, status=UNAVAILABLE, note=note or "No recent items.")
    scores = np.array([i["score"] for i in items], dtype=float)
    w = np.ones_like(scores) if weights is None else np.asarray(weights, dtype=float)
    cls = [tx.classify(s) for s in scores]
    return Reading(source, family, score=float(np.average(scores, weights=w)),
                   n=float(len(items)), bulls=cls.count(1), bears=cls.count(-1),
                   items=items[:ITEM_LIMIT], note=note)


# ---------------------------------------------------------------------------
# StockTwits — users tag their own posts Bullish / Bearish
# ---------------------------------------------------------------------------


def parse_stocktwits(payload: dict) -> Reading:
    items, bulls, bears = [], 0, 0
    for m in (payload or {}).get("messages", []):
        tag = (((m.get("entities") or {}).get("sentiment")) or {}).get("basic")
        label = 1 if tag == "Bullish" else -1 if tag == "Bearish" else 0
        bulls += label == 1
        bears += label == -1
        try:
            when = datetime.fromisoformat(str(m.get("created_at", "")).replace("Z", "+00:00"))
        except ValueError:
            when = None
        items.append({"time": when, "text": m.get("body", ""), "score": float(label),
                      "by": "StockTwits", "url": "", "tag": tag or ""})
    tagged = bulls + bears
    if not items:
        return Reading("StockTwits", "Crowd", status=UNAVAILABLE, note="No recent messages.")
    if tagged == 0:
        return Reading("StockTwits", "Crowd", status=UNAVAILABLE, items=items[:ITEM_LIMIT],
                       note=f"{len(items)} messages, none tagged bullish/bearish.")
    return Reading("StockTwits", "Crowd", score=(bulls - bears) / tagged, n=float(tagged),
                   bulls=bulls, bears=bears, items=items[:ITEM_LIMIT],
                   note=f"{tagged} of {len(items)} recent messages self-tagged.")


def fetch_stocktwits(symbol: str) -> Reading:
    import requests

    r = requests.get(f"https://api.stocktwits.com/api/2/streams/symbol/{quote(symbol)}.json",
                     timeout=TIMEOUT, headers={"User-Agent": BROWSER_UA})
    r.raise_for_status()
    return parse_stocktwits(r.json())


# ---------------------------------------------------------------------------
# Reddit — official API (client-credentials app), titles + text scored
# ---------------------------------------------------------------------------


def reddit_query(ticker: str, name: str) -> str:
    """Cashtag plus the company's short name; a bare ticker like 'ON' or 'ARM'
    would match ordinary words."""
    parts = [f'"${ticker}"']
    if short_name(name) and short_name(name).upper() != ticker:
        parts.append(f'"{short_name(name)}"')
    return " OR ".join(parts)


def parse_reddit(payload: dict) -> Reading:
    items, weights = [], []
    for child in (payload or {}).get("data", {}).get("children", []):
        d = child.get("data", {})
        title, body = d.get("title", ""), (d.get("selftext") or "")[:400]
        upvotes = max(int(d.get("score") or 0), 0)
        when = datetime.fromtimestamp(float(d.get("created_utc") or 0), tz=timezone.utc)
        items.append({"time": when, "text": title, "score": tx.score_text(f"{title}. {body}"),
                      "by": f"r/{d.get('subreddit', '')}",
                      "url": "https://www.reddit.com" + d.get("permalink", ""),
                      "upvotes": upvotes})
        weights.append(1.0 + math.log1p(upvotes))  # popular posts count more, sub-linearly
    return _as_reading("Reddit", "Crowd", items, weights,
                       note="Post titles + text, weighted by log(upvotes).")


def fetch_reddit(ticker: str, name: str, client_id: str, secret: str,
                 subreddits: tuple[str, ...]) -> Reading:
    if not client_id or not secret:
        return Reading("Reddit", "Crowd", status=UNAVAILABLE,
                       note="Add REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET to .env.")
    import requests

    tok = requests.post("https://www.reddit.com/api/v1/access_token", timeout=TIMEOUT,
                        auth=(client_id, secret), data={"grant_type": "client_credentials"},
                        headers={"User-Agent": APP_UA})
    tok.raise_for_status()
    r = requests.get(f"https://oauth.reddit.com/r/{'+'.join(subreddits)}/search",
                     timeout=TIMEOUT,
                     params={"q": reddit_query(ticker, name), "restrict_sr": 1, "sort": "new",
                             "t": "week", "limit": 100},
                     headers={"User-Agent": APP_UA,
                              "Authorization": f"bearer {tok.json()['access_token']}"})
    r.raise_for_status()
    return parse_reddit(r.json())


# ---------------------------------------------------------------------------
# News headlines — Google News RSS (English or Korean)
# ---------------------------------------------------------------------------


def news_url(query: str, korean: bool) -> str:
    locale = "hl=ko&gl=KR&ceid=KR:ko" if korean else "hl=en-US&gl=US&ceid=US:en"
    return f"https://news.google.com/rss/search?q={quote(query + ' when:7d')}&{locale}"


def parse_news_rss(xml_text: str) -> Reading:
    root = ET.fromstring(xml_text)
    items = []
    for it in root.iter("item"):
        title = tx.clean_headline(it.findtext("title", ""))
        try:
            when = parsedate_to_datetime(it.findtext("pubDate", ""))
        except (TypeError, ValueError):
            when = None
        items.append({"time": when, "text": title, "score": tx.score_text(title),
                      "by": (it.findtext("source") or "").strip(),
                      "url": it.findtext("link", "")})
    items.sort(key=lambda i: i["time"] or datetime.min.replace(tzinfo=timezone.utc),
               reverse=True)
    kept = tx.dedupe(items, per_source_cap=3)
    return _as_reading("News headlines", "News", kept,
                       note=f"{len(kept)} of {len(items)} headlines kept after removing "
                            "duplicates and capping each outlet at 3.")


def fetch_news(name: str, name_local: str, market: str) -> Reading:
    import requests

    korean = market == "KOSPI" and tx.is_korean(name_local or "")
    query = f'"{name_local}"' if korean else f'"{short_name(name)}" stock'
    r = requests.get(news_url(query, korean), timeout=TIMEOUT,
                     headers={"User-Agent": BROWSER_UA})
    r.raise_for_status()
    return parse_news_rss(r.text)


# ---------------------------------------------------------------------------
# Analysts — rating level and its 3-month trend, plus up/downgrades
# ---------------------------------------------------------------------------

_RATING_WEIGHTS = {"strongBuy": 2, "buy": 1, "hold": 0, "sell": -1, "strongSell": -2}


def _rating_score(row: pd.Series) -> tuple[float, int]:
    total = sum(int(row.get(k, 0) or 0) for k in _RATING_WEIGHTS)
    if total == 0:
        return float("nan"), 0
    net = sum(w * int(row.get(k, 0) or 0) for k, w in _RATING_WEIGHTS.items())
    return net / (2 * total), total


def parse_analysts(recs: pd.DataFrame | None, actions: pd.DataFrame | None = None,
                   now: datetime | None = None) -> Reading:
    """Sell-side ratings skew bullish (few analysts say 'sell'), so the score
    blends the level with its change over three months:
    score = ½·level + ½·clip(4·Δlevel), plus net up/downgrades in the detail."""
    if recs is None or recs.empty or "period" not in recs.columns:
        return Reading("Analyst ratings", "Analysts", status=UNAVAILABLE,
                       note="No analyst coverage.")
    by_period = recs.set_index("period")
    if "0m" not in by_period.index:
        return Reading("Analyst ratings", "Analysts", status=UNAVAILABLE, note="No current ratings.")
    level, total = _rating_score(by_period.loc["0m"])
    if total == 0:
        return Reading("Analyst ratings", "Analysts", status=UNAVAILABLE, note="No current ratings.")
    then = by_period.loc["-3m"] if "-3m" in by_period.index else None
    change = level - _rating_score(then)[0] if then is not None else float("nan")
    trend = 0.0 if np.isnan(change) else float(np.clip(4 * change, -1, 1))
    detail = {"level": level, "change_3m": change, "analysts": total,
              **{k: int(by_period.loc["0m"].get(k, 0) or 0) for k in _RATING_WEIGHTS}}
    if actions is not None and not actions.empty and "action" in actions.columns:
        now = now or datetime.now(timezone.utc)
        idx = pd.to_datetime(actions.index, utc=True)
        recent = actions[idx >= now - timedelta(days=90)]
        detail["upgrades_90d"] = int((recent["action"] == "up").sum())
        detail["downgrades_90d"] = int((recent["action"] == "down").sum())
    return Reading("Analyst ratings", "Analysts", score=0.5 * level + 0.5 * trend,
                   n=float(total), detail=detail,
                   note=f"{total} analysts; rating trend over 3 months "
                        f"{'n/a' if np.isnan(change) else f'{change:+.2f}'}.")


# ---------------------------------------------------------------------------
# Options — put/call ratio on the nearest expiries
# ---------------------------------------------------------------------------

NEUTRAL_PCR = 0.7   # typical single-stock put/call volume ratio


def parse_options(chains: list[tuple[pd.DataFrame, pd.DataFrame]]) -> Reading:
    """score = −log(PCR / 0.7) / log 3, clipped: PCR 0.7 → 0, ≈0.23 → +1, ≈2.1 → −1.
    Uses volume; falls back to open interest when volume is thin."""
    def total(frames, col):
        return float(sum(pd.to_numeric(f[col], errors="coerce").fillna(0).sum()
                         for f in frames if f is not None and col in f))
    calls, puts = [c for c, _ in chains], [p for _, p in chains]
    cv, pv = total(calls, "volume"), total(puts, "volume")
    co, po = total(calls, "openInterest"), total(puts, "openInterest")
    basis, c, p = ("volume", cv, pv) if cv + pv >= 200 else ("open interest", co, po)
    if c <= 0 or p <= 0:
        return Reading("Options put/call", "Positioning", status=UNAVAILABLE,
                       note="No listed options or no trading.")
    pcr = p / c
    score = float(np.clip(-math.log(pcr / NEUTRAL_PCR) / math.log(3), -1, 1))
    return Reading("Options put/call", "Positioning", score=score,
                   n=min((c + p) / 100.0, 1000.0),
                   detail={"pcr": pcr, "basis": basis, "call": c, "put": p,
                           "pcr_oi": po / co if co else float("nan")},
                   note=f"Put/call {basis} ratio {pcr:.2f} (≈{NEUTRAL_PCR} is typical).")


def fetch_options(t, max_expiries: int = 2) -> Reading:
    expiries = list(t.options or [])[:max_expiries]
    if not expiries:
        return Reading("Options put/call", "Positioning", status=UNAVAILABLE,
                       note="No listed options.")
    chains = []
    for exp in expiries:
        oc = t.option_chain(exp)
        chains.append((oc.calls, oc.puts))
    return parse_options(chains)


# ---------------------------------------------------------------------------
# Short interest — level and month-over-month change
# ---------------------------------------------------------------------------


def parse_short_interest(info: dict) -> Reading:
    """level: 5% of float → 0, 15% → −1, 0% → +0.5; change: −25% shares
    short → +1, +25% → −1. Score = mean of what's available."""
    si = info.get("shortPercentOfFloat")
    now, prior = info.get("sharesShort"), info.get("sharesShortPriorMonth")
    parts, detail = [], {}
    if isinstance(si, (int, float)) and si >= 0:
        parts.append(float(np.clip((0.05 - si) / 0.10, -1, 1)))
        detail["short_pct_float"] = float(si)
    if isinstance(now, (int, float)) and isinstance(prior, (int, float)) and prior > 0:
        change = now / prior - 1
        parts.append(float(np.clip(-change / 0.25, -1, 1)))
        detail["change_1m"] = float(change)
    if not parts:
        return Reading("Short interest", "Positioning", status=UNAVAILABLE,
                       note="No short-interest data.")
    note = ", ".join(x for x in (
        f"{detail['short_pct_float']:.1%} of float sold short" if "short_pct_float" in detail else "",
        f"{detail['change_1m']:+.0%} vs prior month" if "change_1m" in detail else "") if x)
    return Reading("Short interest", "Positioning", score=float(np.mean(parts)), n=50.0,
                   detail=detail, note=note + " (reported twice a month).")


# ---------------------------------------------------------------------------
# Investor flows (KOSPI) — foreign + institutional net buying, KIS API
# ---------------------------------------------------------------------------

KIS_INVESTOR_PATH = "/uapi/domestic-stock/v1/quotations/inquire-investor"
KIS_INVESTOR_TR = "FHKST01010900"


def _qty(row: dict, key: str) -> float:
    try:
        return float(str(row.get(key, "0")).replace(",", "") or 0)
    except ValueError:
        return 0.0


def parse_kis_investor(payload: dict, days: int = 20) -> Reading:
    """score = Σ(foreign + institutional net buy) / Σ(|foreign| + |institutional|)
    over the last ``days`` sessions — the direction and consistency of
    'smart money' flows, scale-free. Retail flow is reported, not scored."""
    rows = [r for r in (payload or {}).get("output", []) if isinstance(r, dict)]
    rows = sorted(rows, key=lambda r: r.get("stck_bsop_date", ""), reverse=True)[:days]
    if not rows:
        return Reading("Investor flows (KIS)", "Positioning", status=UNAVAILABLE,
                       note="No flow data returned.")
    f = np.array([_qty(r, "frgn_ntby_qty") for r in rows])
    o = np.array([_qty(r, "orgn_ntby_qty") for r in rows])
    p = np.array([_qty(r, "prsn_ntby_qty") for r in rows])
    gross = np.abs(f).sum() + np.abs(o).sum()
    if gross == 0:
        return Reading("Investor flows (KIS)", "Positioning", status=UNAVAILABLE,
                       note="No foreign or institutional trading.")
    score = float((f + o).sum() / gross)
    detail = {"foreign_5d": float(f[:5].sum()), "foreign_20d": float(f.sum()),
              "institution_5d": float(o[:5].sum()), "institution_20d": float(o.sum()),
              "retail_20d": float(p.sum()), "days": len(rows)}
    return Reading("Investor flows (KIS)", "Positioning", score=score, n=float(len(rows)) * 2,
                   detail=detail,
                   note=f"{len(rows)}-day net buying, shares: foreign {f.sum():+,.0f}, "
                        f"institutions {o.sum():+,.0f} (retail {p.sum():+,.0f}, not scored).")


def fetch_kis_investor(kis, ticker: str) -> Reading:
    r = kis.request(KIS_INVESTOR_PATH, params={"FID_COND_MRKT_DIV_CODE": "J",
                                               "FID_INPUT_ISCD": ticker},
                    headers={"tr_id": KIS_INVESTOR_TR, "custtype": "P"})
    return parse_kis_investor(r.json())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def not_applicable(source: str, family: str, why: str) -> Reading:
    return Reading(source, family, status=NOT_APPLICABLE, note=why)


def failed(source: str, family: str, err: Exception) -> Reading:
    return Reading(source, family, status=ERROR, note=f"{type(err).__name__}: {err}"[:200])


__all__ = ["OK", "parse_stocktwits", "parse_reddit", "parse_news_rss", "parse_analysts",
           "parse_options", "parse_short_interest", "parse_kis_investor", "fetch_stocktwits",
           "fetch_reddit", "fetch_news", "fetch_options", "fetch_kis_investor", "short_name",
           "reddit_query", "news_url", "not_applicable", "failed"]
