"""Key-metric value tables: the numbers behind each factor score.

``metric_values`` (pure pandas) prepares display values from a scored
metrics frame; ``column_config`` maps each view to Streamlit column formats.
Values stay numeric so table columns sort correctly.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from factors.definitions import GROUPS


@dataclass(frozen=True)
class MetricCol:
    key: str
    label: str
    kind: str        # pct | pp | x
    help: str = ""


METRICS: dict[str, list[MetricCol]] = {
    "Value": [
        MetricCol("pe", "P/E", "x", "Price / earnings. None for loss-makers (negative earnings)."),
        MetricCol("earnings_yield", "Earnings yield", "pct", "Net income / market cap (E/P)."),
        MetricCol("pb", "P/B", "x", "Price / book. None for negative equity."),
        MetricCol("dividend_yield", "Div. yield", "pct", "Annual dividends / price."),
        MetricCol("cash_flow_yield", "CF yield", "pct", "Operating cash flow / market cap."),
    ],
    "Growth": [
        MetricCol("fwd_revenue_revision", "Revenue (fwd)", "pct",
                  "Consensus forward-12M revenue revision. Free data: next-year revenue "
                  "growth estimate."),
        MetricCol("fwd_op_margin_change", "Op-margin Δ", "pp",
                  "Change in operating margin, percentage points. Free data: last two "
                  "fiscal years."),
        MetricCol("fwd_eps_growth", "EPS growth (fwd)", "pct",
                  "Forward-12M EPS vs trailing EPS. None when trailing EPS ≤ 0."),
        MetricCol("long_term_growth", "LT growth", "pct", "ROE × (1 − payout ratio)."),
    ],
    "Momentum": [
        MetricCol("ret_1M", "1M", "pct", "Price return, last 21 trading days."),
        MetricCol("ret_3M", "3M", "pct", "Price return, last 63 trading days."),
        MetricCol("ret_6M", "6M", "pct", "Price return, last 126 trading days."),
        MetricCol("ret_12M", "12M", "pct", "Price return, last 252 trading days."),
        MetricCol("eps_revision_1m", "EPS rev. 1M", "pct",
                  "Change in the forward EPS estimate over the past month."),
        MetricCol("foreign_own_chg_3m", "Foreign Δ 3M", "pp",
                  "Change in foreign ownership, percentage points (not in free data)."),
    ],
    "Quality": [
        MetricCol("fwd_op_margin", "Op. margin", "pct",
                  "Operating margin (forward-12M; free data: trailing-12M)."),
        MetricCol("roe", "ROE", "pct", "Return on equity."),
        MetricCol("roic", "ROIC", "pct", "Return on invested capital."),
        MetricCol("debt_to_equity", "Debt/Equity", "x",
                  "Total debt / equity. None for negative equity."),
    ],
}

VIEWS = ("Scores", *GROUPS, "All metrics")


def metric_values(metrics: pd.DataFrame) -> pd.DataFrame:
    """Display values for every MetricCol, indexed like ``metrics``.

    Adds P/E and P/B (inverses of the yields the model ranks on; blank when
    the yield is ≤ 0), turns the scorer's +inf debt/equity marker for
    negative equity back into a blank, and scales pp columns to points.
    """
    m = metrics.copy()
    ey = pd.to_numeric(m.get("earnings_yield"), errors="coerce")
    bm = pd.to_numeric(m.get("book_to_market"), errors="coerce")
    m["pe"] = (1.0 / ey).where(ey > 0)
    m["pb"] = (1.0 / bm).where(bm > 0)
    out = pd.DataFrame(index=m.index)
    for col in (c for cols in METRICS.values() for c in cols):
        values = pd.to_numeric(m[col.key], errors="coerce") if col.key in m.columns \
            else pd.Series(np.nan, index=m.index)
        values = values.replace([np.inf, -np.inf], np.nan)
        out[col.key] = values * 100.0 if col.kind == "pp" else values
    return out


def view_columns(view: str) -> list[MetricCol]:
    if view == "All metrics":
        return [c for cols in METRICS.values() for c in cols]
    return METRICS.get(view, [])


def column_config(view: str) -> dict:
    """Streamlit column formats for a view's metric columns."""
    import streamlit as st

    fmt = {"pct": "percent", "pp": "%+.2f pp", "x": "%.2fx"}
    return {c.key: st.column_config.NumberColumn(c.label, format=fmt[c.kind], help=c.help)
            for c in view_columns(view)}
