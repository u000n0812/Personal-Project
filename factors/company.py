"""Score a market universe — or one company within it. Pure pandas, no I/O.

``score_market`` ranks every company in a universe frame (snapshot rows,
plus any extra companies appended), either against the whole market or
within each sector (sector-neutral). ``score_company`` puts one company into
its market's universe and reads off its scores and ranks.

Price momentum is a cross-sectional score, so it is recomputed within
whatever scope the ranking uses.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from factors import price, scoring
from factors.definitions import GROUPS

DESCRIPTIVE = ("name", "name_local", "sector", "industry", "currency", "market")
UNCLASSIFIED = "Unclassified"


def _score(universe: pd.DataFrame, all_round: float, standout: float,
           min_coverage: float) -> scoring.LeaderBoard:
    """Score one ranking scope (a market, or one sector of it)."""
    returns = universe[[c for c in universe.columns if c.startswith("ret_")]]
    returns = returns.apply(pd.to_numeric, errors="coerce")
    numeric = universe.drop(columns=[c for c in (*DESCRIPTIVE, "price_momentum",
                                                 "trend_agreement") if c in universe.columns])
    numeric = numeric.apply(pd.to_numeric, errors="coerce").join(price.price_momentum(returns))
    return scoring.score_universe(numeric, all_round=all_round, standout=standout,
                                  min_coverage=min_coverage)


def concat_boards(boards: list[scoring.LeaderBoard]) -> scoring.LeaderBoard:
    return scoring.LeaderBoard(
        metrics=pd.concat([b.metrics for b in boards]),
        percentiles=pd.concat([b.percentiles for b in boards]),
        groups=pd.concat([b.groups for b in boards]),
        table=pd.concat([b.table for b in boards]),
    )


def sector_of(universe: pd.DataFrame) -> pd.Series:
    sector = universe["sector"] if "sector" in universe.columns else pd.Series("", index=universe.index)
    return sector.fillna("").replace("", UNCLASSIFIED).astype(str)


def score_market(
    universe: pd.DataFrame,
    all_round: float,
    standout: float,
    min_coverage: float = 0.5,
    rank_scope: str = "market",
    min_sector_size: int = 5,
) -> scoring.LeaderBoard:
    """Rank every row of ``universe`` (index ticker).

    rank_scope="market": one ranking across the universe.
    rank_scope="sector": each sector with ≥ ``min_sector_size`` companies is
    ranked on its own; companies in smaller sectors (and "Unclassified") are
    ranked against the whole market. ``table["ranked_vs"]`` records which.

    The table carries the descriptive columns (name, sector, …) and
    ``scope_size`` — the number of companies in the stock's ranking scope.
    """
    sectors = sector_of(universe)
    if rank_scope == "sector":
        sizes = sectors.map(sectors.value_counts())
        own = (sizes >= min_sector_size) & (sectors != UNCLASSIFIED)
        boards = []
        for sector in sorted(sectors[own].unique()):
            b = _score(universe[sectors == sector], all_round, standout, min_coverage)
            b.table["ranked_vs"], b.table["scope_size"] = "Sector", int((sectors == sector).sum())
            boards.append(b)
        if (~own).any():
            whole = _score(universe, all_round, standout, min_coverage)
            rest = sectors.index[~own]
            whole = scoring.LeaderBoard(whole.metrics.loc[rest], whole.percentiles.loc[rest],
                                        whole.groups.loc[rest], whole.table.loc[rest])
            whole.table["ranked_vs"], whole.table["scope_size"] = "Market", len(universe)
            boards.append(whole)
        board = concat_boards(boards)
    else:
        board = _score(universe, all_round, standout, min_coverage)
        board.table["ranked_vs"], board.table["scope_size"] = "Market", len(universe)

    for col in DESCRIPTIVE:
        if col in universe.columns:
            board.table[col] = universe[col].reindex(board.table.index)
    board.table["sector"] = sectors.reindex(board.table.index)
    board.table = board.table.sort_values("composite", ascending=False)
    return board


@dataclass
class CompanyScore:
    ticker: str
    board: scoring.LeaderBoard
    universe_size: int
    composite: float                 # mean of the four group percentiles (0–1)
    rank: float                      # composite rank in the market (1 = best)
    group_pct: pd.Series             # Value…Quality percentiles (0–1)
    group_rank: pd.Series            # Value…Quality ranks (1 = best)
    classification: str
    standout_in: str
    tags: str
    sector: str
    sector_rank: float               # NaN when no sector peers
    sector_size: int
    in_snapshot: bool                # was the company already a peer?


def score_company(
    ticker: str,
    target: pd.Series,
    peers: pd.DataFrame,
    all_round: float,
    standout: float,
    min_coverage: float = 0.5,
) -> CompanyScore:
    """Rank ``target`` (one row: factor inputs, ret_* columns, sector, name)
    within ``peers``. The target replaces its own peer row if it has one, so
    its live data wins."""
    in_snapshot = ticker in peers.index
    universe = pd.concat([peers.drop(index=ticker, errors="ignore"), target.to_frame(ticker).T])
    board = score_market(universe, all_round, standout, min_coverage)

    row = board.table.loc[ticker]
    group_rank = board.groups.rank(ascending=False, method="min").loc[ticker]

    sector = str(target.get("sector") or "")
    sector_rank, sector_size = float("nan"), 0
    if sector:
        same = board.table[board.table["sector"] == sector]["composite"]
        sector_size = int(same.notna().sum())
        if sector_size and not np.isnan(row["composite"]):
            sector_rank = float(same.rank(ascending=False, method="min")[ticker])

    return CompanyScore(
        ticker=ticker, board=board, universe_size=len(board.table),
        composite=float(row["composite"]), rank=float(row["rank"]),
        group_pct=board.groups.loc[ticker, list(GROUPS)], group_rank=group_rank,
        classification=str(row["classification"]), standout_in=str(row["standout_in"]),
        tags=str(row["tags"]), sector=sector, sector_rank=sector_rank,
        sector_size=sector_size, in_snapshot=in_snapshot,
    )
