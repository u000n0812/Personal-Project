"""Score one company against its market's peers. Pure pandas, no I/O.

The selected company joins the peer universe (replacing its own snapshot
row if it is already a peer, so its live data wins) and the whole set is
scored with ``factors.scoring.score_universe``. Price momentum is re-ranked
over the combined set because it is a cross-sectional score.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from factors import price, scoring
from factors.definitions import GROUPS


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
    within ``peers`` (snapshot frame indexed by ticker)."""
    in_snapshot = ticker in peers.index
    universe = pd.concat([peers.drop(index=ticker, errors="ignore"), target.to_frame(ticker).T])
    ret_cols = [c for c in universe.columns if c.startswith("ret_")]
    returns = universe[ret_cols].apply(pd.to_numeric, errors="coerce")
    metrics = universe.drop(columns=["price_momentum", "trend_agreement"], errors="ignore")
    metrics = metrics.join(price.price_momentum(returns))

    numeric = metrics.drop(columns=["name", "sector", "industry", "currency"], errors="ignore")
    numeric = numeric.apply(pd.to_numeric, errors="coerce")
    board = scoring.score_universe(numeric, all_round=all_round, standout=standout,
                                   min_coverage=min_coverage)
    for col in ("name", "sector"):
        if col in universe.columns:
            board.table[col] = universe[col].reindex(board.table.index)

    row = board.table.loc[ticker]
    group_rank = board.groups.rank(ascending=False, method="min").loc[ticker]

    sector = str(target.get("sector") or "")
    sector_rank, sector_size = float("nan"), 0
    if sector and "sector" in board.table.columns:
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
