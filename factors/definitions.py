"""Factor catalogue for the market-leader screen.

Market-leading stocks tend to rank highly across all four factor groups, or
post an exceptionally strong score in at least one. Each group is the
average of its sub-factors' cross-sectional percentiles.

Every sub-factor maps to one column of the *metrics frame* (index = ticker).
All rates are fractions (0.05 = 5%); "pp" changes are fractions too
(0.01 = +1 percentage point). To add or drop a sub-factor, edit
``SUB_FACTORS`` — scoring and the UI pick it up automatically.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

GROUPS: tuple[str, ...] = ("Value", "Growth", "Momentum", "Quality")


@dataclass(frozen=True)
class SubFactor:
    key: str                      # column in the metrics frame
    label: str
    group: str                    # one of GROUPS
    higher_is_better: bool = True
    fmt: str = "pct"              # display: pct | chg | pp | x | score
    note: str = ""


SUB_FACTORS: tuple[SubFactor, ...] = (
    # --- Value -------------------------------------------------------------
    SubFactor("earnings_yield", "Earnings yield (E/P)", "Value",
              note="Net income / market cap. Inverse of P/E, so it compares "
                   "directly with bond yields and loss-makers rank last "
                   "instead of breaking the scale."),
    SubFactor("dividend_yield", "Dividend yield", "Value",
              note="Annual dividends / price."),
    SubFactor("book_to_market", "Book-to-market (B/P)", "Value", fmt="x",
              note="Inverse of P/B — downside protection from net assets."),
    SubFactor("cash_flow_yield", "Cash-flow yield (CF/P)", "Value",
              note="Cash flow / market cap — financial capacity, key in "
                   "capital-intensive industries."),
    # --- Growth ------------------------------------------------------------
    SubFactor("fwd_revenue_revision", "Fwd-12M revenue revision", "Growth", fmt="chg",
              note="% revision to consensus forward-12M revenue."),
    SubFactor("fwd_op_margin_change", "Fwd-12M op-margin change", "Growth", fmt="pp",
              note="Expected change in forward-12M operating margin. Often "
                   "turns before revenue does."),
    SubFactor("fwd_eps_growth", "Fwd-12M EPS growth", "Growth", fmt="chg",
              note="Growth rate of forward-12M EPS estimates."),
    SubFactor("long_term_growth", "Long-term growth (ROE × retention)", "Growth",
              note="Sustainable growth = ROE × (1 − payout). Derived from "
                   "roe and payout_ratio when not supplied directly."),
    # --- Momentum ----------------------------------------------------------
    SubFactor("eps_revision_1m", "EPS revision (1M)", "Momentum", fmt="chg",
              note="% change in forward-12M EPS estimate over the past month."),
    SubFactor("price_momentum", "Price momentum (1/3/6/12M)", "Momentum", fmt="score",
              note="Average cross-sectional rank of 1/3/6/12-month returns, "
                   "shrunk toward neutral when the horizons disagree in "
                   "direction. Computed from prices, not the fundamentals file."),
    SubFactor("foreign_own_chg_3m", "Foreign ownership Δ (3M)", "Momentum", fmt="pp",
              note="Change in foreign ownership ratio over 3 months."),
    # --- Quality -----------------------------------------------------------
    SubFactor("fwd_op_margin", "Fwd-12M operating margin", "Quality",
              note="Pricing power: ability to pass costs on to customers."),
    SubFactor("roe", "ROE", "Quality", note="Net income / shareholders' equity."),
    SubFactor("roic", "ROIC", "Quality",
              note="Return on equity + debt capital; unlike ROE it can't be "
                   "inflated with leverage."),
    SubFactor("debt_to_equity", "Debt-to-equity", "Quality",
              higher_is_better=False, fmt="x",
              note="Financial soundness. Ranked lower-is-better, which is "
                   "rank-equivalent to scoring the inverse. Negative equity "
                   "ranks worst."),
)

# Columns the fundamentals source should provide (price_momentum is
# computed from OHLCV; payout_ratio is an input to long_term_growth).
FUNDAMENTAL_COLUMNS: tuple[str, ...] = tuple(
    sf.key for sf in SUB_FACTORS if sf.key != "price_momentum"
) + ("payout_ratio",)


def by_group(group: str) -> list[SubFactor]:
    return [sf for sf in SUB_FACTORS if sf.group == group]


def format_value(sf: SubFactor, value: float) -> str:
    """Human-readable raw value for a sub-factor (display only)."""
    if value is None or np.isnan(value):
        return "n/a"
    if np.isinf(value):
        return "neg. equity" if sf.key == "debt_to_equity" else "∞"
    return {
        "pct": f"{value:.2%}",
        "chg": f"{value:+.2%}",
        "pp": f"{value * 100:+.2f}pp",
        "x": f"{value:.2f}x",
        "score": f"{value:.2f}",
    }[sf.fmt]
