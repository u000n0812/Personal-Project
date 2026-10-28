"""Optional fundamentals override file.

Market data comes from the peer snapshots (``data.snapshot``). If you have
better inputs — e.g. real consensus revisions from FnGuide/DataGuide in place
of the free-data proxies — export them to ``config.FUNDAMENTALS_PATH`` (CSV or
Parquet) and they override the snapshot values wherever they are provided.

File schema: a ``ticker`` column (KRX 6-digit codes get their leading zeros
restored; NASDAQ symbols as-is) plus any subset of the metric columns in
``factors.definitions.FUNDAMENTAL_COLUMNS``. Blank cells don't override.
Unknown columns are ignored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import streamlit as st

import config
from factors.definitions import FUNDAMENTAL_COLUMNS


@dataclass
class OverrideInfo:
    path: str = ""
    columns: list[str] = field(default_factory=list)   # metric columns applied
    tickers: int = 0                                   # rows that matched


def _normalize(ticker: str) -> str:
    ticker = str(ticker).strip().upper()
    return ticker.zfill(6) if ticker.isdigit() else ticker


@st.cache_data(show_spinner=False)
def _load_file(path: str, mtime: float) -> pd.DataFrame:
    """Read the override file. ``mtime`` is only a cache key, so editing the
    file invalidates the cache on the next rerun."""
    p = Path(path)
    if p.suffix.lower() == ".parquet":
        df = pd.read_parquet(p)
    else:
        df = pd.read_csv(p, dtype={"ticker": str}, encoding="utf-8-sig")
    df["ticker"] = df["ticker"].map(_normalize)
    df = df.drop_duplicates("ticker", keep="last").set_index("ticker")
    return df[[c for c in FUNDAMENTAL_COLUMNS if c in df.columns]].apply(
        pd.to_numeric, errors="coerce")


def overrides() -> pd.DataFrame | None:
    path = config.fundamentals_path()
    if not path.exists():
        return None
    return _load_file(str(path), path.stat().st_mtime)


def apply_overrides(frame: pd.DataFrame) -> tuple[pd.DataFrame, OverrideInfo]:
    """Return ``frame`` with file values (where present) replacing its own."""
    file = overrides()
    if file is None or file.empty:
        return frame, OverrideInfo()
    hits = file.index.intersection(frame.index)
    out = frame.copy()
    if len(hits):
        patch = file.loc[hits]
        for col in patch.columns:
            if col not in out.columns:
                out[col] = float("nan")
            out[col] = out[col].astype(float)
        out.update(patch)  # NaN cells in the file leave snapshot values alone
    return out, OverrideInfo(path=config.fundamentals_path().name,
                             columns=list(file.columns), tickers=len(hits))
