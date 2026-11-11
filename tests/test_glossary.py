"""Dictionary integrity and search tests — offline.

    python -m tests.test_glossary
"""

from __future__ import annotations

from collections import Counter

import glossary
from factors.definitions import SUB_FACTORS
from ui.metric_views import METRICS


def test_ids_unique_and_links_resolve() -> None:
    dupes = [i for i, n in Counter(e.id for e in glossary.ENTRIES).items() if n > 1]
    assert not dupes, f"duplicate ids: {dupes}"
    for e in glossary.ENTRIES:
        missing = [r for r in e.related if r not in glossary.BY_ID]
        assert not missing, f"{e.id}: unknown related ids {missing}"
        assert e.id not in e.related, f"{e.id} lists itself as related"


def test_required_fields_and_categories() -> None:
    for e in glossary.ENTRIES:
        assert e.term and e.definition, f"{e.id}: term and definition are required"
        assert e.category in glossary.CATEGORIES, f"{e.id}: unknown category {e.category}"
    empty = [c for c in glossary.CATEGORIES if not glossary.search(category=c)]
    assert not empty, f"empty categories: {empty}"


def test_every_scored_and_displayed_metric_has_an_entry() -> None:
    keys = {sf.key for sf in SUB_FACTORS} | {c.key for cols in METRICS.values() for c in cols}
    unmapped = sorted(keys - set(glossary.FOR_METRIC))
    assert not unmapped, f"metrics without a dictionary entry: {unmapped}"
    for key, entry_id in glossary.FOR_METRIC.items():
        assert entry_id in glossary.BY_ID, f"{key} → unknown entry {entry_id}"


def test_scoring_metrics_explain_meaning_and_calculation() -> None:
    """Each scoring input (and P/E, P/B) says what it measures and how it's computed."""
    ids = {glossary.FOR_METRIC[sf.key] for sf in SUB_FACTORS} | {"pe", "pb"}
    for entry_id in ids:
        e = glossary.BY_ID[entry_id]
        assert e.measures, f"{entry_id}: missing 'measures'"
        assert e.formula, f"{entry_id}: missing 'formula'"
        assert e.in_app, f"{entry_id}: missing 'in_app'"


def test_formulas_have_balanced_braces() -> None:
    for e in glossary.ENTRIES:
        if e.formula:
            assert e.formula.count("{") == e.formula.count("}"), f"{e.id}: unbalanced braces"
            assert e.formula.count("(") == e.formula.count(")"), f"{e.id}: unbalanced parens"


def test_search() -> None:
    first = lambda q, **kw: glossary.search(q, **kw)[0].id  # noqa: E731
    assert first("PER") == "pe" and first("pbr") == "pb"          # Korean-market aliases
    assert first("주가순자산비율") == "pb"                          # Korean name
    assert first("P/E") == "pe" and first("sharpe") == "sharpe"
    assert first("roe") == "roe"                                    # exact beats contains
    assert glossary.search("  Mdd ")[0].id == "max-drawdown"        # trim + casefold
    assert {e.id for e in glossary.search("roll", category="Backtesting")} >= {"roll-yield"}
    assert all(e.category == "Value metrics" for e in glossary.search(category="Value metrics"))
    everything = glossary.search()
    assert len(everything) == len(glossary.ENTRIES)
    assert [e.term.casefold() for e in everything] == sorted(e.term.casefold() for e in everything)
    assert glossary.search("zzzz-no-match") == []


def test_reverse_links() -> None:
    """'Also referenced by' lists entries that link here but aren't already linked back."""
    pe = glossary.get("pe")
    back = {e.id for e in glossary.referenced_by(pe)}
    assert back, "P/E should be referenced by other entries"
    assert all(pe.id in glossary.get(i).related and i not in pe.related for i in back)


if __name__ == "__main__":
    for fn in (test_ids_unique_and_links_resolve, test_required_fields_and_categories,
               test_every_scored_and_displayed_metric_has_an_entry,
               test_scoring_metrics_explain_meaning_and_calculation,
               test_formulas_have_balanced_braces, test_search, test_reverse_links):
        print(f"• {fn.__name__}")
        fn()
    print(f"\nAll dictionary tests passed ✅  ({len(glossary.ENTRIES)} entries)")
