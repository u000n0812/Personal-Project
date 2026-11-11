"""Text sentiment for headlines and posts, plus de-duplication.

English: VADER with a finance vocabulary added — stock VADER is tuned for
social media and scores "beats earnings, rallies to record high" as neutral.
Korean: a finance stem lexicon (상승/하락, 호재/악재, …), scored as
(pos − neg) / (pos + neg). Both are deliberately simple and transparent;
swap ``score_text`` for a model such as FinBERT if you need more nuance.
"""

from __future__ import annotations

import re
from collections import Counter

# VADER valences run from −4 to +4.
FINANCE_LEXICON: dict[str, float] = {
    # bullish
    "beat": 2.0, "beats": 2.0, "rally": 2.2, "rallies": 2.2, "rallied": 2.2,
    "surge": 2.4, "surges": 2.4, "surged": 2.4, "soar": 2.6, "soars": 2.6, "soared": 2.6,
    "jump": 1.8, "jumps": 1.8, "jumped": 1.8, "climb": 1.5, "climbs": 1.5, "gain": 1.5,
    "gains": 1.5, "rebound": 1.6, "rebounds": 1.6, "record": 1.2, "upgrade": 2.2,
    "upgrades": 2.2, "upgraded": 2.2, "outperform": 2.0, "outperforms": 2.0,
    "bullish": 2.8, "bull": 1.6, "buy": 1.2, "breakout": 1.8, "raises": 1.2, "raised": 1.2,
    "tops": 1.5, "strong": 1.2, "upside": 1.5, "calls": 0.6, "moon": 2.0, "undervalued": 1.5,
    "dividend": 0.6, "buyback": 1.4, "profit": 1.0, "growth": 1.0, "approval": 1.5,
    "skyrocket": 3.0, "skyrockets": 3.0, "boost": 1.5, "boosts": 1.5, "boosted": 1.5,
    # bearish
    "miss": -2.0, "misses": -2.0, "missed": -2.0, "plunge": -3.0, "plunges": -3.0,
    "plunged": -3.0, "tumble": -2.6, "tumbles": -2.6, "tumbled": -2.6, "slump": -2.2,
    "slumps": -2.2, "sink": -2.0, "sinks": -2.0, "slide": -1.8, "slides": -1.8,
    "drop": -1.6, "drops": -1.6, "dropped": -1.6, "fall": -1.6, "falls": -1.6, "fell": -1.6,
    "decline": -1.5, "declines": -1.5, "downgrade": -2.2, "downgrades": -2.2,
    "downgraded": -2.2, "underperform": -2.0, "bearish": -2.8, "bear": -1.6, "sell": -1.2,
    "selloff": -2.4, "sell-off": -2.4, "cut": -1.6, "cuts": -1.6, "slash": -2.0,
    "slashes": -2.0, "warns": -2.0, "warning": -1.8, "weak": -1.4, "downside": -1.5,
    "puts": -0.6, "short": -1.0, "overvalued": -1.5, "lawsuit": -2.0, "probe": -1.6,
    "investigation": -1.6, "recall": -1.6, "layoffs": -1.6, "bankruptcy": -3.2,
    "loss": -1.6, "losses": -1.6, "crash": -3.0, "tariff": -1.0, "tariffs": -1.0,
    "slip": -1.4, "slips": -1.4, "slipped": -1.4, "cools": -0.8, "plummet": -3.0,
    "plummets": -3.0, "plummeted": -3.0, "rout": -2.6, "slashed": -2.0,
}

KO_POSITIVE: tuple[str, ...] = (
    "상승", "급등", "강세", "호재", "신고가", "최고", "돌파", "반등", "회복", "매수", "상향",
    "흑자", "개선", "성장", "수혜", "기대", "호실적", "깜짝", "순매수", "최대", "증가", "확대",
    "해소", "목표가 상향", "배당", "자사주", "수주", "승인", "턴어라운드",
)
KO_NEGATIVE: tuple[str, ...] = (
    "하락", "급락", "약세", "악재", "신저가", "최저", "폭락", "매도", "하향", "적자", "부진",
    "감소", "우려", "리스크", "손실", "쇼크", "경고", "순매도", "축소", "둔화", "위기", "소송",
    "조사", "제재", "리콜", "부담", "목표가 하향", "털썩", "추락",
)

_HANGUL = re.compile(r"[가-힣]")
_analyzer = None


def _vader():
    global _analyzer
    if _analyzer is None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        _analyzer = SentimentIntensityAnalyzer()
        _analyzer.lexicon.update(FINANCE_LEXICON)
    return _analyzer


def is_korean(text: str) -> bool:
    return len(_HANGUL.findall(text or "")) >= 2


def english_score(text: str) -> float:
    """VADER compound score in [-1, 1] with the finance vocabulary."""
    return float(_vader().polarity_scores(text or "")["compound"])


def korean_score(text: str) -> float:
    """(pos − neg) / (pos + neg) over finance stems; 0 when none match.

    Negative stems that contain a positive one ("목표가 하향" vs "상향") are
    matched as whole stems, so each phrase counts once.
    """
    text = text or ""
    pos = sum(text.count(w) for w in KO_POSITIVE)
    neg = sum(text.count(w) for w in KO_NEGATIVE)
    return 0.0 if pos + neg == 0 else (pos - neg) / (pos + neg)


def score_text(text: str) -> float:
    return korean_score(text) if is_korean(text) else english_score(text)


def classify(score: float, threshold: float = 0.05) -> int:
    """+1 bullish, −1 bearish, 0 neutral."""
    return 1 if score > threshold else -1 if score < -threshold else 0


def clean_headline(title: str) -> str:
    """Drop the trailing ' - Publisher' that Google News appends."""
    return re.sub(r"\s+-\s+[^-]{2,60}$", "", (title or "").strip())


def _fingerprint(text: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", text.casefold())[:60]


def dedupe(items: list[dict], per_source_cap: int = 3) -> list[dict]:
    """Remove near-identical items (syndicated copies) and cap each outlet's
    contribution, so one publisher can't dominate the tone. Keeps order."""
    seen, per_source, out = set(), Counter(), []
    for item in items:
        fp = _fingerprint(item.get("text", ""))
        by = item.get("by", "")
        if not fp or fp in seen or (by and per_source[by] >= per_source_cap):
            continue
        seen.add(fp)
        per_source[by] += 1
        out.append(item)
    return out
