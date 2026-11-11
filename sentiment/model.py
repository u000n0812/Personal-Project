"""Sentiment data model and aggregation. Pure Python/pandas.

Every source produces a ``Reading``: a score in [-1, +1] (−1 = maximally
bearish, +1 = maximally bullish) plus the evidence behind it (``n``).

Aggregation rules — the objectivity safeguards:

1. **Shrinkage.** A reading built on little evidence is pulled toward
   neutral: ``score × n / (n + K)``. Thirty StockTwits messages count; three
   don't move the needle much.
2. **Family balance.** Readings are averaged within their family first
   (Crowd, News, Analysts, Positioning, Price), then families are averaged
   with equal weight — so two chat sites can't outvote analysts and prices.
3. **Agreement and coverage are reported**, not hidden: the spread of family
   scores, and how many families had data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
import pandas as pd

FAMILIES: tuple[str, ...] = ("Crowd", "News", "Analysts", "Positioning", "Price")
FAMILY_NOTES: dict[str, str] = {
    "Crowd": "What retail investors say in communities (StockTwits, Reddit).",
    "News": "Tone of recent news headlines.",
    "Analysts": "Sell-side ratings and their recent trend.",
    "Positioning": "What traders do with money: options, short interest, investor flows.",
    "Price": "How the stock trades relative to its market index.",
}
FAMILY_ADJECTIVE: dict[str, str] = {"Crowd": "Crowd", "News": "News", "Analysts": "Analyst",
                                    "Positioning": "Positioning", "Price": "Price-behavior"}
SHRINK_K = 10.0          # evidence at which a reading keeps half its strength
MIN_FAMILIES = 2         # below this, the composite is flagged low-coverage

OK, UNAVAILABLE, ERROR, NOT_APPLICABLE = "ok", "unavailable", "error", "not applicable"

# Fear & Greed style bands (0–100), as popularized by CNN's index.
BANDS: tuple[tuple[float, str], ...] = (
    (25, "Extreme fear"), (45, "Fear"), (55, "Neutral"), (75, "Greed"), (101, "Extreme greed"),
)


@dataclass
class Reading:
    source: str
    family: str
    score: float = float("nan")      # [-1, +1]
    n: float = 0.0                   # evidence: messages, headlines, analysts, days…
    status: str = OK
    note: str = ""
    bulls: int = 0                   # items classified bullish (for the bull/bear ratio)
    bears: int = 0
    items: list[dict] = field(default_factory=list)   # {"time","text","score","url","by"}
    detail: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == OK and not np.isnan(self.score)

    @property
    def weight(self) -> float:
        """Shrinkage factor n / (n + K), 0 when unavailable."""
        return self.n / (self.n + SHRINK_K) if self.ok and self.n > 0 else 0.0

    @property
    def adjusted(self) -> float:
        return self.score * self.weight if self.ok else float("nan")


@dataclass
class Composite:
    index: float                     # 0–100
    label: str
    families: dict[str, float]       # family → adjusted score in [-1, 1]
    agreement: float                 # std of family scores (0 = full agreement)
    agreement_label: str
    coverage: int                    # families with data
    bull_ratio: float                # bullish share of classified crowd/news items
    bull_n: int
    attention: float                 # last-24h item rate ÷ window average (1 = normal)
    readings: list[Reading]

    @property
    def low_coverage(self) -> bool:
        return self.coverage < MIN_FAMILIES


def to_index(score: float) -> float:
    """[-1, 1] → [0, 100]."""
    return float("nan") if np.isnan(score) else 50.0 + 50.0 * float(np.clip(score, -1, 1))


def band(index: float) -> str:
    if index is None or np.isnan(index):
        return "No data"
    return next(label for upper, label in BANDS if index < upper)


def agreement_label(spread: float) -> str:
    if np.isnan(spread):
        return "n/a"
    return "Sources agree" if spread < 0.25 else "Mixed signals" if spread < 0.5 \
        else "Sources conflict"


def attention_ratio(items: list[dict], now: datetime | None = None, window_days: float = 7.0) -> float:
    """Items in the last 24h relative to the average daily rate over the window.

    2.0 = twice the usual chatter. NaN when there aren't enough timestamped items.
    """
    times = [i["time"] for i in items if isinstance(i.get("time"), datetime)]
    if len(times) < 5:
        return float("nan")
    now = now or datetime.now(timezone.utc)
    ages = np.array([(now - t).total_seconds() / 86400.0 for t in times])
    span = min(window_days, max(ages.max(), 1.0))
    recent = (ages <= 1.0).sum()
    rate = (ages <= span).sum() / span
    return float(recent / rate) if rate > 0 else float("nan")


def aggregate(readings: list[Reading], now: datetime | None = None) -> Composite:
    families = {}
    for fam in FAMILIES:
        vals = [r.adjusted for r in readings if r.family == fam and r.ok]
        if vals:
            families[fam] = float(np.mean(vals))
    scores = np.array(list(families.values()), dtype=float)
    composite = float(scores.mean()) if len(scores) else float("nan")
    spread = float(scores.std(ddof=0)) if len(scores) >= 2 else float("nan")

    crowd_news = [r for r in readings if r.family in ("Crowd", "News") and r.ok]
    bulls = sum(r.bulls for r in crowd_news)
    bears = sum(r.bears for r in crowd_news)
    social_items = [i for r in crowd_news for i in r.items]
    index = to_index(composite)
    return Composite(
        index=index, label=band(index), families=families, agreement=spread,
        agreement_label=agreement_label(spread), coverage=len(families),
        bull_ratio=bulls / (bulls + bears) if bulls + bears else float("nan"),
        bull_n=bulls + bears, attention=attention_ratio(social_items, now),
        readings=readings,
    )


def summarize(name: str, stock: Composite, market_index: float, market_label: str,
              market_name: str) -> list[str]:
    """Rule-based plain-language summary — reproducible, no model in the loop."""
    if np.isnan(stock.index):
        return [f"Not enough data to gauge sentiment toward {name}."]
    lines = [f"Sentiment toward **{name}** reads **{stock.label.lower()}** "
             f"({stock.index:.0f}/100), based on {stock.coverage} of {len(FAMILIES)} "
             "source families."]
    if not np.isnan(market_index):
        gap = stock.index - market_index
        rel = ("well above" if gap > 15 else "above" if gap > 5 else "well below" if gap < -15
               else "below" if gap < -5 else "in line with")
        lines.append(f"That is {rel} the overall {market_name} mood "
                     f"({market_label.lower()}, {market_index:.0f}) — a gap of {gap:+.0f} points, "
                     "i.e. company-specific rather than market-wide.")
    strong = sorted(stock.families.items(), key=lambda kv: -abs(kv[1]))
    for fam, s in strong[:3]:
        if abs(s) >= 0.1:
            lines.append(f"{FAMILY_ADJECTIVE[fam]} signals lean "
                         f"**{'bullish' if s > 0 else 'bearish'}** ({to_index(s):.0f}).")
    if not np.isnan(stock.bull_ratio) and stock.bull_n >= 10:
        lines.append(f"Of {stock.bull_n} classified posts and headlines, "
                     f"{stock.bull_ratio:.0%} are bullish.")
    if not np.isnan(stock.attention) and stock.attention >= 2:
        lines.append(f"Attention is elevated: {stock.attention:.1f}× the usual daily volume "
                     "of posts and headlines.")
    lines.append(f"{stock.agreement_label} across families"
                 + (" — treat the composite with caution." if stock.agreement_label != "Sources agree"
                    else "."))
    if stock.low_coverage:
        lines.append("Coverage is low (fewer than two families), so this reading is fragile.")
    if stock.index >= 75 or stock.index <= 25:
        lines.append("Readings this extreme are often read contrarily: crowded optimism or "
                     "pessimism can precede reversals.")
    return lines


def readings_frame(readings: list[Reading]) -> pd.DataFrame:
    """Tabular view of readings for display and history."""
    return pd.DataFrame([{
        "Source": r.source, "Family": r.family,
        "Score": to_index(r.score) if r.ok else np.nan,
        "Evidence (n)": r.n if r.ok else np.nan,
        "Weight": r.weight, "Adjusted": to_index(r.adjusted) if r.ok else np.nan,
        "Status": r.status, "Note": r.note,
    } for r in readings])
