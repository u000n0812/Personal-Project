"""Cross-sectional scoring and market-leader classification. Pure pandas.

Pipeline (all vectorized across the universe):

1. ``derive_metrics``      fill derivable inputs (long-term growth), sanitize.
2. ``percentile_scores``   each sub-factor → percentile rank in (0, 1],
                           direction-adjusted so 1.0 is always best.
3. ``group_scores``        mean of a group's sub-factor percentiles, then
                           re-ranked to a percentile across the universe.
4. ``classify``            All-round leader: *every* group ≥ ``all_round``.
                           Standout leader: *any* group ≥ ``standout``.

Missing-data policy (explicit): a NaN input drops out of its sub-factor
ranking only. A group score needs at least ``min_coverage`` of its
sub-factors present, otherwise it is NaN — and a stock with any NaN group
cannot be an all-round leader (it can still be a standout in the groups it
does have). Percentiles are *relative to the screened universe*.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from factors.definitions import GROUPS, SUB_FACTORS, by_group

ALL_ROUND = "All-round leader"
STANDOUT = "Standout leader"

# Caveat-tag thresholds (group percentiles)
VALUE_TRAP_VALUE_MIN = 0.70        # cheap …
VALUE_TRAP_OTHERS_MAX = 0.40       # … but no growth and no momentum
SPECULATIVE_MOMENTUM_MIN = 0.70    # strong momentum …
SPECULATIVE_QUALITY_MAX = 0.30     # … on weak fundamentals


@dataclass
class LeaderBoard:
    """Everything the UI needs; every frame is indexed by ticker."""

    metrics: pd.DataFrame       # raw inputs (incl. derived + return columns)
    percentiles: pd.DataFrame   # sub-factor percentiles, 1.0 = best
    groups: pd.DataFrame        # group percentiles (Value…Quality)
    table: pd.DataFrame         # composite, breadth, peak, classification, tags


def _join_true(mask: pd.DataFrame) -> pd.Series:
    """Row-wise comma-joined names of the True columns (vectorized)."""
    labels = pd.Series(mask.columns + ", ", index=mask.columns)
    return mask.fillna(False).astype(bool).dot(labels).str.rstrip(", ")


def derive_metrics(metrics: pd.DataFrame) -> pd.DataFrame:
    """Ensure every sub-factor column exists and fill derivable values.

    * long_term_growth ← roe × (1 − payout_ratio) where not supplied.
    * debt_to_equity < 0 (negative equity) → +inf so it ranks worst under
      lower-is-better, instead of looking like the soundest balance sheet.
    """
    cols = list(dict.fromkeys([sf.key for sf in SUB_FACTORS] + ["payout_ratio", "roe"]))
    m = metrics.copy()
    for col in cols:
        if col not in m.columns:
            m[col] = np.nan
    sustainable = m["roe"] * (1.0 - m["payout_ratio"].clip(0.0, 1.0))
    m["long_term_growth"] = m["long_term_growth"].fillna(sustainable)
    m["debt_to_equity"] = m["debt_to_equity"].mask(m["debt_to_equity"] < 0, np.inf)
    return m


def percentile_scores(metrics: pd.DataFrame) -> pd.DataFrame:
    """Sub-factor percentile ranks, direction-adjusted (1.0 = best)."""
    return pd.DataFrame(
        {sf.key: metrics[sf.key].rank(pct=True, ascending=sf.higher_is_better)
         for sf in SUB_FACTORS},
        index=metrics.index,
    )


def group_scores(percentiles: pd.DataFrame, min_coverage: float = 0.5) -> pd.DataFrame:
    """Group percentile = re-ranked mean of the group's sub-factor percentiles."""
    out = {}
    for group in GROUPS:
        block = percentiles[[sf.key for sf in by_group(group)]]
        coverage = block.notna().mean(axis=1)
        out[group] = block.mean(axis=1).where(coverage >= min_coverage).rank(pct=True)
    return pd.DataFrame(out, index=percentiles.index)


def classify(groups: pd.DataFrame, all_round: float, standout: float) -> pd.DataFrame:
    """Apply the two leader rules.

    breadth = weakest group percentile (NaN if any group is missing)
    peak    = strongest group percentile
    """
    breadth = groups.min(axis=1, skipna=False)
    peak = groups.max(axis=1)
    standout_mask = groups.ge(standout)
    is_all_round = breadth >= all_round
    is_standout = standout_mask.any(axis=1)
    classification = np.select([is_all_round, is_standout], [ALL_ROUND, STANDOUT], "")
    composite = groups.mean(axis=1)
    return pd.DataFrame({
        "composite": composite,
        "rank": composite.rank(ascending=False, method="min"),
        "breadth": breadth,
        "peak": peak,
        "leader": is_all_round | is_standout,
        "classification": classification,
        "standout_in": _join_true(standout_mask),
    }, index=groups.index)


def caveat_tags(metrics: pd.DataFrame, groups: pd.DataFrame) -> pd.Series:
    """Context tags that qualify a score.

    * Operating leverage — revenue estimates AND margin estimates both
      rising: the phase where leaders' prices tend to accelerate.
    * Value-trap risk — cheap, but neither growth nor momentum confirms.
    * Speculative risk — strong momentum on weak quality (theme-driven).
    """
    tags = pd.DataFrame({
        "Operating leverage":
            (metrics["fwd_revenue_revision"] > 0) & (metrics["fwd_op_margin_change"] > 0),
        "Value-trap risk":
            (groups["Value"] >= VALUE_TRAP_VALUE_MIN)
            & (groups["Growth"] < VALUE_TRAP_OTHERS_MAX)
            & (groups["Momentum"] < VALUE_TRAP_OTHERS_MAX),
        "Speculative risk":
            (groups["Momentum"] >= SPECULATIVE_MOMENTUM_MIN)
            & (groups["Quality"] < SPECULATIVE_QUALITY_MAX),
    }, index=metrics.index)
    return _join_true(tags)


def score_universe(
    metrics: pd.DataFrame,
    all_round: float = 0.60,
    standout: float = 0.95,
    min_coverage: float = 0.5,
) -> LeaderBoard:
    """Run the full screen on a tickers × metrics frame."""
    m = derive_metrics(metrics)
    pct = percentile_scores(m)
    groups = group_scores(pct, min_coverage)
    table = classify(groups, all_round, standout)
    table["tags"] = caveat_tags(m, groups)
    return LeaderBoard(metrics=m, percentiles=pct, groups=groups,
                       table=table.sort_values(["rank", "peak"], ascending=[True, False]))
