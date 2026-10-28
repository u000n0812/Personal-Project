"""Fundamental / consensus metrics for the market-leader screen.

Resolution order:
  1. A file at ``config.FUNDAMENTALS_PATH`` (CSV or Parquet) — the intended
     plug-in point: export it from your own warehouse/vendor pipeline.
  2. Synthetic fundamentals (``data.synthetic``) so the page always renders.

File schema: one row per stock, a ``ticker`` column (6-digit KRX code;
leading zeros restored automatically), an optional ``name`` column, and the
metric columns in ``factors.definitions.FUNDAMENTAL_COLUMNS``. Missing
columns are reported and treated as NaN; extra columns are ignored.

# ----------------------------------------------------------------------
# TODO(you): wire a live source here if you'd rather not go via a file.
#
# The KIS Open API covers only part of this schema — trailing ratios
# (ROE, debt ratio, EPS/BPS) under its domestic financial-ratio endpoints,
# and the current foreign-ownership ratio on the price quote. The
# forward-12M consensus inputs (revenue/EPS/op-margin estimates and their
# revisions) need a consensus vendor such as FnGuide/DataGuide.
# ----------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import streamlit as st

import config
from data import synthetic
from factors.definitions import FUNDAMENTAL_COLUMNS


@dataclass
class Fundamentals:
    frame: pd.DataFrame                 # tickers × FUNDAMENTAL_COLUMNS
    source: str                         # "file" | "synthetic"
    detail: str = ""                    # human-readable provenance
    missing_columns: list[str] = field(default_factory=list)
    missing_tickers: list[str] = field(default_factory=list)


@st.cache_data(show_spinner=False)
def _load_file(path: str, mtime: float) -> pd.DataFrame:
    """Read the fundamentals file. ``mtime`` is only a cache key, so editing
    the file invalidates the cache on the next rerun."""
    p = Path(path)
    if p.suffix.lower() == ".parquet":
        df = pd.read_parquet(p)
    else:
        df = pd.read_csv(p, dtype={"ticker": str})
    df["ticker"] = df["ticker"].astype(str).str.strip().str.zfill(6)
    return df.drop_duplicates("ticker", keep="last").set_index("ticker")


@st.cache_data(ttl=3600, show_spinner=False)
def _synthetic(tickers: tuple[str, ...]) -> pd.DataFrame:
    return synthetic.generate_fundamentals(list(tickers))


def file_universe() -> dict[str, str] | None:
    """Ticker → name from the fundamentals file, or None if there is no file."""
    path = config.fundamentals_path()
    if not path.exists():
        return None
    df = _load_file(str(path), path.stat().st_mtime)
    names = df["name"] if "name" in df.columns else pd.Series(df.index, index=df.index)
    return names.astype(str).to_dict()


def get_fundamentals(tickers: list[str]) -> Fundamentals:
    """Fundamentals for ``tickers`` from the file if present, else synthetic."""
    path = config.fundamentals_path()
    if path.exists():
        df = _load_file(str(path), path.stat().st_mtime)
        present = [c for c in FUNDAMENTAL_COLUMNS if c in df.columns]
        missing = [c for c in FUNDAMENTAL_COLUMNS if c not in df.columns]
        if {"roe", "payout_ratio"} <= set(present):
            # derived as ROE × (1 − payout) in factors.scoring — not really missing
            missing = [c for c in missing if c != "long_term_growth"]
        return Fundamentals(
            frame=df[present].reindex(index=tickers, columns=list(FUNDAMENTAL_COLUMNS)),
            source="file",
            detail=str(path.name),
            missing_columns=missing,
            missing_tickers=[t for t in tickers if t not in df.index],
        )
    return Fundamentals(frame=_synthetic(tuple(tickers)), source="synthetic",
                        detail="deterministic demo data")
