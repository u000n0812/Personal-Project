"""Table helpers shared by pages. Pure pandas (no Streamlit import)."""

from __future__ import annotations

import pandas as pd

SEARCH_COLUMNS = ("ticker", "name", "name_local")


def search_mask(frame: pd.DataFrame, query: str, columns=SEARCH_COLUMNS) -> pd.Series:
    """Rows where any search column contains ``query`` (case-insensitive,
    whitespace-trimmed). Uses the index as the ticker when there's no column.
    An empty query matches everything."""
    query = (query or "").strip().casefold()
    if not query:
        return pd.Series(True, index=frame.index)
    hit = pd.Series(False, index=frame.index)
    for col in columns:
        values = frame.index.to_series() if col == "ticker" and col not in frame.columns \
            else frame.get(col)
        if values is None:
            continue
        hit |= values.astype("string").fillna("").str.casefold().str.contains(query, regex=False)
    return hit
