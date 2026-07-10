"""Carry reference strategy.

Signals are driven by a *carry score* — ideally the futures roll yield or
term-structure slope of each ETF's underlying. Until you wire in the real
source (see ``carry_score`` below), a clearly-labelled placeholder proxy
keeps the strategy runnable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def carry_score(prices: pd.DataFrame, params: dict) -> pd.Series:
    """Annualized carry estimate for one asset.

    Resolution order:
      1. a ``carry`` column on ``prices`` (synthetic mode provides one);
      2. ``params["carry"]`` — a Series you computed elsewhere;
      3. the placeholder proxy below.

    # ------------------------------------------------------------------
    # TODO(you): plug in the REAL carry source here.
    #
    # For commodity futures ETFs the honest inputs are, in rough order of
    # preference:
    #   * roll yield from the underlying futures curve:
    #       (front price / next price) ** (252 / days_between_expiries) - 1
    #   * term-structure slope from two listed contract months
    #   * the ETF issuer's published roll schedule + contract settlements
    # Return an *annualized* rate so scores are comparable across assets.
    # Until then, the fallback below is a crude moving-average slope of the
    # ETF price itself — it is NOT carry, only a stand-in that keeps the
    # pipeline runnable.
    # ------------------------------------------------------------------
    """
    if "carry" in prices.columns:
        return prices["carry"]
    if "carry" in params:
        return params["carry"].reindex(prices.index)

    close = prices["close"]
    fast = close.rolling(21).mean()
    slow = close.rolling(63).mean()
    return (fast / slow - 1.0) * (252 / 42)  # annualize the 42-day MA gap


def compute_signal(prices: pd.DataFrame, params: dict) -> pd.Series:
    """Smoothed carry score for one asset (continuous, annualized).

    Deliberately returns the *score* rather than its sign so the caller can
    rank cross-sectionally over a basket (see ``rank_weights``). For a single
    asset, take ``np.sign`` of this series to get a long/flat/short signal.

    params:
        lookback (int): smoothing window for the score (default 20).
        carry (pd.Series, optional): externally computed carry, see above.
    """
    smoothing = max(int(params.get("lookback", 20)) // 4, 5)
    score = carry_score(prices, params)
    return score.rolling(smoothing, min_periods=1).mean().fillna(0.0)


def rank_weights(scores: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional rank weights from a dates × tickers score panel.

    Each day: rank assets by carry, demean the ranks (long high carry,
    short low carry), scale so gross exposure |w| sums to 1. Days where
    every score is missing come out flat.
    """
    ranks = scores.rank(axis=1)
    centered = ranks.sub(ranks.mean(axis=1), axis=0)
    gross = centered.abs().sum(axis=1)
    return centered.div(gross.replace(0.0, np.nan), axis=0).fillna(0.0)
