"""Glue: market universes from ``data.company`` → pure scoring in ``factors``.

The only module in ``factors/`` that touches ``data/``. The Portfolio
Dashboard, Market Leaders and Company Analysis pages all rank against the
same per-market peer snapshots, so a stock gets the same scores everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

import config
from data import company as company_data
from data.fundamentals import OverrideInfo, apply_overrides
from factors import scoring
from factors.company import concat_boards, score_market
from factors.price import trailing_returns


def get_thresholds() -> tuple[float, float]:
    """Leader thresholds shared across pages (set by the Market Leaders page)."""
    return st.session_state.get(
        "_leader_thresholds", (config.LEADER_ALL_ROUND_PCT, config.LEADER_STANDOUT_PCT)
    )


def resolve_source() -> str:
    """"synthetic" when forced from the sidebar, else the free Yahoo source."""
    return "synthetic" if st.session_state.get("force_synthetic", False) else "yahoo"


def company_row(source: str, ticker: str, market: str) -> pd.Series:
    """Live factor-input row for one company (daily closes, no intraday quote)."""
    info = company_data.company(source, ticker, market)
    hist = company_data.history(source, ticker, market)
    returns = trailing_returns(hist.to_frame(ticker)).loc[ticker]
    return pd.Series({**info.metrics, **returns.to_dict(), "name": info.name,
                      "name_local": info.name, "sector": info.sector,
                      "industry": info.industry, "market": market})


@dataclass
class MarketBoard:
    market: str
    board: scoring.LeaderBoard
    meta: dict
    overrides: OverrideInfo
    added: list[str] = field(default_factory=list)       # extras fetched live
    failed: dict[str, str] = field(default_factory=dict)  # extras that failed


def market_board(
    source: str,
    market: str,
    all_round: float,
    standout: float,
    rank_scope: str = "market",
    extra_tickers: tuple[str, ...] = (),
) -> MarketBoard | None:
    """Score ``market``'s snapshot universe; ``extra_tickers`` not already in
    it (e.g. your holdings) are fetched live and added. None if no snapshot."""
    universe = company_data.market_universe(source, market)
    if universe is None:
        return None
    frame, meta, overrides = universe

    added, failed, rows = [], {}, []
    for ticker in extra_tickers:
        if ticker in frame.index:
            continue
        try:
            rows.append(company_row(source, ticker, market).rename(ticker))
            added.append(ticker)
        except Exception as err:  # noqa: BLE001 — skip it, report it
            failed[ticker] = f"{type(err).__name__}: {err}"[:160]
    if rows:
        extra = pd.DataFrame(rows)
        if source != "synthetic":
            extra, _ = apply_overrides(extra)
        frame = pd.concat([frame, extra])

    board = score_market(frame, all_round, standout, config.LEADER_MIN_COVERAGE,
                         rank_scope=rank_scope, min_sector_size=config.MIN_SECTOR_SIZE)
    return MarketBoard(market, board, meta, overrides, added, failed)


def combine(boards: list[MarketBoard]) -> scoring.LeaderBoard:
    """One table across markets; each stock keeps its within-market ranks."""
    board = concat_boards([b.board for b in boards])
    board.table = board.table.sort_values("composite", ascending=False)
    return board


def leader_label(table: pd.DataFrame) -> pd.Series:
    """'All-round' / 'Standout · Value, Growth' / '' per ticker."""
    short = table["classification"].str.replace(" leader", "", regex=False)
    return short.where(table["standout_in"] == "", short + " · " + table["standout_in"])
