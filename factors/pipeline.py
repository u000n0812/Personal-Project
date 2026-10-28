"""Glue: fetch prices + fundamentals, then run the pure scoring.

The only module in ``factors/`` that touches ``data/``; both the Portfolio
Dashboard and the Market Leaders page call ``build_leaderboard`` so their
leader labels always agree.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import config
from data import client, fundamentals
from factors import price, scoring

# ~13 months of calendar days → enough trading days for the 12M return.
PRICE_HISTORY_DAYS = 400


def resolve_universe(holdings: pd.DataFrame, include_screen: bool = True) -> dict[str, str]:
    """Ticker → name for the screen.

    Screening universe = tickers in the fundamentals file if one exists,
    else ``config.SCREEN_UNIVERSE``. Holdings are always included.
    """
    names: dict[str, str] = {}
    if include_screen:
        names.update(fundamentals.file_universe() or config.SCREEN_UNIVERSE)
    names.update(dict(zip(holdings["ticker"], holdings["name"])))
    return names


def get_thresholds() -> tuple[float, float]:
    """Leader thresholds shared across pages (set by the Market Leaders page)."""
    return st.session_state.get(
        "_leader_thresholds", (config.LEADER_ALL_ROUND_PCT, config.LEADER_STANDOUT_PCT)
    )


def build_leaderboard(
    names: dict[str, str],
    mode: str,
    all_round: float,
    standout: float,
) -> tuple[scoring.LeaderBoard, fundamentals.Fundamentals]:
    """Score every ticker in ``names``; returns the board and data provenance."""
    tickers = list(names)
    fund = fundamentals.get_fundamentals(tickers)

    end = pd.Timestamp.today().normalize()
    start = end - pd.Timedelta(days=PRICE_HISTORY_DAYS)
    history = {t: client.get_ohlcv(t, start, end, mode) for t in tickers}
    close = client.build_close_panel(history).reindex(columns=tickers)

    returns = price.trailing_returns(close)
    metrics = fund.frame.join([returns, price.price_momentum(returns)])

    board = scoring.score_universe(
        metrics, all_round=all_round, standout=standout,
        min_coverage=config.LEADER_MIN_COVERAGE,
    )
    board.table.insert(0, "name", pd.Series(names).reindex(board.table.index))
    return board, fund
