"""Dictionary of the terms and concepts used in the app.

Entries live in ``glossary.entries`` as plain data; this module adds lookup
and search. No Streamlit imports, so it is testable on its own.

To add a term: append an ``Entry`` to ``ENTRIES`` with a unique ``id``;
reference other entries by id in ``related``. ``tests/test_glossary.py``
checks that every link resolves and that every scoring input in
``factors.definitions`` has an entry.
"""

from __future__ import annotations

from glossary.entries import CATEGORIES, ENTRIES, Entry

BY_ID: dict[str, Entry] = {e.id: e for e in ENTRIES}

# Scoring inputs (factors.definitions keys) and displayed metric columns
# (ui.metric_views keys) → their dictionary entry. Tests keep this complete.
FOR_METRIC: dict[str, str] = {
    "earnings_yield": "earnings-yield", "dividend_yield": "dividend-yield",
    "book_to_market": "book-to-market", "cash_flow_yield": "cash-flow-yield",
    "fwd_revenue_revision": "revenue-revision", "fwd_op_margin_change": "op-margin-change",
    "fwd_eps_growth": "eps-growth", "long_term_growth": "long-term-growth",
    "eps_revision_1m": "eps-revision", "price_momentum": "price-momentum",
    "foreign_own_chg_3m": "foreign-ownership-change", "fwd_op_margin": "operating-margin",
    "roe": "roe", "roic": "roic", "debt_to_equity": "debt-to-equity",
    "pe": "pe", "pb": "pb", "payout_ratio": "payout-ratio",
    "ret_1M": "trailing-return", "ret_3M": "trailing-return",
    "ret_6M": "trailing-return", "ret_12M": "trailing-return",
}


def get(entry_id: str) -> Entry | None:
    return BY_ID.get(entry_id)


def related(entry: Entry) -> list[Entry]:
    return [BY_ID[r] for r in entry.related if r in BY_ID]


def referenced_by(entry: Entry) -> list[Entry]:
    """Entries that list ``entry`` as related (reverse links)."""
    return [e for e in ENTRIES if entry.id in e.related and e.id not in entry.related]


def search(query: str = "", category: str | None = None) -> list[Entry]:
    """Entries matching ``query`` (case-insensitive), best matches first.

    Ranking: exact term/alias/Korean name → term or alias starts with the
    query → contained in a name → contained in the explanatory text. An empty
    query returns the category (or everything) alphabetically.
    """
    pool = [e for e in ENTRIES if category in (None, "", "All") or e.category == category]
    q = (query or "").strip().casefold()
    if not q:
        return sorted(pool, key=lambda e: e.term.casefold())

    def score(e: Entry) -> int | None:
        names = [n.casefold() for n in (e.term, *e.aliases, e.korean) if n]
        if q in names:
            return 0
        if any(n.startswith(q) for n in names):
            return 1
        if any(q in n for n in names):
            return 2
        if q in e.searchable_text:
            return 3
        return None

    scored = [(s, e) for e in pool if (s := score(e)) is not None]
    return [e for s, e in sorted(scored, key=lambda se: (se[0], se[1].term.casefold()))]


__all__ = ["CATEGORIES", "ENTRIES", "Entry", "BY_ID", "FOR_METRIC", "get", "related",
           "referenced_by", "search"]
